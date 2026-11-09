"""M29:PR #31 / #32 審查意見的回歸測試(每項先重現、修正後鎖住行為)。"""
import unittest
import xml.etree.ElementTree as ET

from plc_st.checker import check
from plc_st.export import export, validate_plcopen
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError


def bools(n):
    return ("TYPE B : STRUCT " + " ".join(f"b{i} : BOOL;" for i in range(n))
            + " END_STRUCT END_TYPE PROGRAM P VAR x : B; END_VAR END_PROGRAM")


def l5x(src):
    return ET.fromstring(export(src, "l5x"))


def tags(root):
    return {t.get("Name"): t for t in root.iter("Tag")}


class L5xBoolHost(unittest.TestCase):
    """#31-1:隱藏 SINT 主機可容納 8 個 BOOL;第 9 個才拒絕。"""

    def test_eight_bools_fit(self):
        dt = l5x(bools(8)).find(".//DataType[@Name='B']")
        bits = [m.get("BitNumber") for m in dt.iter("Member") if m.get("DataType") == "BIT"]
        self.assertEqual(bits, [str(i) for i in range(8)])

    def test_seven_bools(self):
        self.assertEqual(len([m for m in l5x(bools(7)).iter("Member") if m.get("DataType") == "BIT"]), 7)

    def test_nine_bools_rejected(self):
        with self.assertRaisesRegex(STError, "超過 8 個"):
            export(bools(9), "l5x")


class L5xDimensions(unittest.TestCase):
    """#31-2:目前 Tag Dimensions 以空白分隔;鎖住現況,待 Studio 5000 實機匯入確認。"""

    def test_multidim_tag_format(self):
        t = tags(l5x("PROGRAM P VAR a : ARRAY[0..1, 0..2] OF INT; END_VAR END_PROGRAM"))["a"]
        self.assertEqual(t.get("Dimensions"), "2 3")


class ArrayBoundExpressions(unittest.TestCase):
    """#31-3:邊界運算式完整計算或明確拒絕,不可部分比對而靜默改變大小。"""

    def test_l5x_expression_bounds(self):
        t = tags(l5x("PROGRAM P VAR a : ARRAY[0..2+1] OF INT; b : ARRAY[0..(1+1)*2] OF INT; "
                     "c : ARRAY[0..10 MOD 4, 0..7/2] OF INT; END_VAR END_PROGRAM"))
        self.assertEqual(t["a"].get("Dimensions"), "4")
        self.assertEqual(t["b"].get("Dimensions"), "5")
        self.assertEqual(t["c"].get("Dimensions"), "3 4")

    def test_matches_runtime_size(self):
        src = "PROGRAM P VAR a : ARRAY[0..2+1] OF INT; END_VAR END_PROGRAM"
        n = len(VirtualPLC(src).vars["a"])
        self.assertEqual(tags(l5x(src))["a"].get("Dimensions"), str(n))

    def test_plcopen_expression_bounds(self):
        x = export("PROGRAM P VAR a : ARRAY[-1..2+1] OF INT; END_VAR END_PROGRAM", "plcopen")
        self.assertIn('<dimension lower="-1" upper="3"/>', x)

    def test_udt_member_expression_bound(self):
        r = l5x("TYPE S : STRUCT v : ARRAY[0..2+1] OF INT; END_STRUCT END_TYPE "
                "PROGRAM P VAR s : S; END_VAR END_PROGRAM")
        self.assertEqual(r.find(".//Member[@Name='v']").get("Dimension"), "4")

    def test_unsupported_bounds_rejected(self):
        for decl in ("ARRAY[0..N] OF INT", "ARRAY[0..1.5] OF INT", "ARRAY[0..2+] OF INT",
                     "ARRAY[0..1/0] OF INT", "ARRAY[3..1] OF INT"):
            for fmt in ("l5x", "plcopen"):
                with self.subTest(decl=decl, fmt=fmt), self.assertRaises(STError):
                    export(f"PROGRAM P VAR a : {decl}; END_VAR END_PROGRAM", fmt)


STRSRC = """TYPE S : STRUCT t : STRING := 'http://host'; u : STRING := 'a;b(*c*)'; k : INT; END_STRUCT END_TYPE
PROGRAM P VAR s : S; m : STRING := 'x;y//z'; n : INT; END_VAR
m := 'p;q'; (* note; with semicolon *)
END_PROGRAM"""


class StringLiterals(unittest.TestCase):
    """#31-4:字串中的 '//'、'(*'、';' 不可被當成註解或分隔符。"""

    def test_l5x_udt_keeps_all_members(self):
        r = l5x(STRSRC)
        names = [m.get("Name") for m in r.find(".//DataType[@Name='S']").iter("Member")]
        self.assertEqual(names, ["t", "u", "k"])
        self.assertEqual(set(tags(r)), {"s", "m", "n"})

    def test_plcopen_keeps_strings(self):
        x = export(STRSRC, "plcopen")
        ET.fromstring(x)
        self.assertIn("'http://host'", x)
        self.assertIn("'a;b(*c*)'", x)
        self.assertIn("'x;y//z'", x)
        self.assertIn('<variable name="k">', x)

    def test_scl_keeps_strings(self):
        x = export(STRSRC, "scl")
        self.assertIn("t : STRING := 'http://host';", x)
        self.assertIn("u : STRING := 'a;b(*c*)';", x)
        self.assertIn("k : INT;", x)

    def test_body_comment_preserved(self):
        self.assertIn("(* note; with semicolon *)", export(STRSRC, "l5x"))

    def test_runs_in_virtual_plc(self):
        p = VirtualPLC(STRSRC)
        p.scan(1)
        self.assertEqual(p.get("s.u"), "a;b(*c*)")


class HiddenHostName(unittest.TestCase):
    """#31-5:隱藏主機名稱不可與既有欄位撞名(不分大小寫)。"""

    def test_unique_host(self):
        r = l5x("TYPE A : STRUCT ZZZZZZZZZZA0 : INT; zzzzzzzzzza1 : INT; run : BOOL; END_STRUCT END_TYPE "
                "PROGRAM P VAR a : A; END_VAR END_PROGRAM")
        ms = list(r.find(".//DataType[@Name='A']").iter("Member"))
        names = [m.get("Name").lower() for m in ms]
        self.assertEqual(len(names), len(set(names)))
        host = [m for m in ms if m.get("Hidden") == "true"][0].get("Name")
        self.assertEqual(host, "ZZZZZZZZZZA2")
        self.assertEqual(r.find(".//Member[@Name='run']").get("Target"), host)


H = "TYPE R : STRUCT buf : ARRAY[0..1] OF INT := [9, 9]; END_STRUCT END_TYPE\n"


class UnindexedArrayWrite(unittest.TestCase):
    """#32-6:未加索引寫入陣列(STRUCT 欄位或一般陣列)須拒絕,不可破壞內部狀態。"""

    def run_body(self, body, decl="a : R; x : ARRAY[0..1] OF INT;"):
        p = VirtualPLC(H + f"PROGRAM P VAR {decl} END_VAR {body} END_PROGRAM")
        p.scan(1)
        return p

    def test_struct_field_unindexed_write_rejected(self):
        with self.assertRaisesRegex(STError, "whole array"):
            self.run_body("a.buf := 7;")

    def test_plain_array_unindexed_write_rejected(self):
        with self.assertRaisesRegex(STError, "whole array"):
            self.run_body("x := 7;")

    def test_state_intact_after_rejection(self):
        p = VirtualPLC(H + "PROGRAM P VAR a : R; END_VAR a.buf := 7; END_PROGRAM")
        with self.assertRaises(STError):
            p.scan(1)
        self.assertEqual(p.vars["a.buf"], [9, 9])
        self.assertIn("a.buf[1]", p.snapshot())

    def test_indexed_write_ok(self):
        self.assertEqual(self.run_body("a.buf[1] := 7;").vars["a.buf"], [9, 7])

    def test_checker_flags_unindexed_write(self):
        msgs = [str(i) for i in check(H + "PROGRAM P VAR a : R; END_VAR a.buf := 7; END_PROGRAM")]
        self.assertTrue(any("without index" in m for m in msgs), msgs)


class InstanceArrayInit(unittest.TestCase):
    """#32-7:STRUCT 實例初始值可指定陣列欄位,含巢狀;各實例彼此獨立。"""

    SRC = H + """TYPE O : STRUCT r : R; k : INT; END_STRUCT END_TYPE
PROGRAM P VAR
  a : R := (buf := [3, 4]);
  b : R;
  c : R := (buf := [5]);
  o : O := (r := (buf := [1, 2]), k := 3);
END_VAR
a.buf[0] := 100;
END_PROGRAM"""

    def setUp(self):
        self.p = VirtualPLC(self.SRC)
        self.p.scan(1)

    def test_instance_override(self):
        self.assertEqual(self.p.vars["a.buf"], [100, 4])

    def test_type_default_untouched(self):
        self.assertEqual(self.p.vars["b.buf"], [9, 9])

    def test_partial_override_fills_default(self):
        self.assertEqual(self.p.vars["c.buf"], [5, 0])

    def test_nested(self):
        self.assertEqual(self.p.vars["o.r.buf"], [1, 2])
        self.assertEqual(self.p.get("o.k"), 3)

    def test_instances_independent(self):
        p = VirtualPLC(H + "PROGRAM P VAR a, b : R := (buf := [1, 2]); END_VAR a.buf[0] := 50; END_PROGRAM")
        p.scan(1)
        self.assertEqual(p.vars["b.buf"], [1, 2])
        self.assertIsNot(p.vars["a.buf"], p.vars["b.buf"])

    def test_checker_clean(self):
        self.assertEqual([str(i) for i in check(self.SRC)], [])

    def test_bad_initialisers(self):
        for decl in ("a : R := (buf := 5);", "a : R := (buf := [1, 2, 3]);",
                     "x : INT := [1];", "x : ARRAY[0..1] OF INT := 5;"):
            with self.subTest(decl=decl), self.assertRaises(STError):
                VirtualPLC(H + f"PROGRAM P VAR {decl} END_VAR END_PROGRAM")

    def test_export_plcopen_instance_init(self):
        x = export(self.SRC, "plcopen")
        ET.fromstring(x)
        self.assertIn('<value member="buf"><arrayValue>', x)


try:
    import lxml  # noqa: F401
    HAVE_LXML = True
except ImportError:
    HAVE_LXML = False


@unittest.skipUnless(HAVE_LXML, "lxml not installed")
class Tc6Schema(unittest.TestCase):
    def test_new_outputs_validate(self):
        for src in (STRSRC, InstanceArrayInit.SRC,
                    "PROGRAM P VAR a : ARRAY[-1..2+1, 0..3] OF INT; END_VAR END_PROGRAM"):
            with self.subTest(src=src[:30]):
                self.assertEqual(validate_plcopen(export(src, "plcopen")), [])


if __name__ == "__main__":
    unittest.main()
