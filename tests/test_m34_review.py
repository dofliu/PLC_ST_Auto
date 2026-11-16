"""M34 審查意見修正的回歸測試:FB 內 RETAIN、SCL 不改字串、VAR_TEMP 陣列、L5X 初值範圍、常數回寫。"""
import unittest

from plc_st.checker import check
from plc_st.export import to_gxworks, to_l5x, to_plcopen, to_scl, to_sysmac
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError


def prog(decl, body=""):
    return f"PROGRAM P\n{decl}\n{body}\nEND_PROGRAM\n"


def errors(src):
    return [i.msg for i in check(src) if i.severity == "error"]


CNT = ("FUNCTION_BLOCK Cnt\nVAR_INPUT inc : BOOL; END_VAR\nVAR_OUTPUT n, t : DINT; END_VAR\n"
       "VAR RETAIN keep : DINT; END_VAR\nVAR tmp : DINT; END_VAR\n"
       "IF inc THEN keep := keep + 1; tmp := tmp + 1; END_IF;\nn := keep; t := tmp;\nEND_FUNCTION_BLOCK\n")


class RetainInFbTest(unittest.TestCase):
    def test_retain_inside_fb_survives_warm_restart(self):
        plc = VirtualPLC(CNT + prog("VAR c : Cnt; r, t : DINT; END_VAR", "c(inc := TRUE); r := c.n; t := c.t;"))
        plc.scan(3)
        plc.restart(warm=True)
        plc.scan(1)
        self.assertEqual((plc.get("r"), plc.get("t")), (4, 1))  # keep 保留,非 RETAIN 的 tmp 回初值

    def test_cold_restart_clears_fb_retain(self):
        plc = VirtualPLC(CNT + prog("VAR c : Cnt; r : DINT; END_VAR", "c(inc := TRUE); r := c.n;"))
        plc.scan(3)
        plc.restart(warm=False)
        plc.scan(1)
        self.assertEqual(plc.get("r"), 1)

    def test_nested_fb_retain(self):
        outer = ("FUNCTION_BLOCK Outer\nVAR_OUTPUT n : DINT; END_VAR\nVAR inner : Cnt; calls : INT; END_VAR\n"
                 "inner(inc := TRUE); n := inner.n; calls := calls + 1;\nEND_FUNCTION_BLOCK\n")
        plc = VirtualPLC(CNT + outer + prog("VAR o : Outer; r : DINT; END_VAR", "o(); r := o.n;"))
        plc.scan(5)
        plc.restart()
        plc.scan(1)
        self.assertEqual(plc.get("r"), 6)

    def test_retain_array_and_struct_array(self):
        src = ("TYPE S : STRUCT x : INT; END_STRUCT END_TYPE\n"
               + prog("VAR RETAIN a : ARRAY[0..2] OF INT; s : ARRAY[0..1] OF S; END_VAR\nVAR i : INT; END_VAR",
                      "a[1] := a[1] + 1; s[1].x := s[1].x + 2; i := i + 1;"))
        plc = VirtualPLC(src)
        plc.scan(3)
        plc.restart()
        self.assertEqual((plc.get("a[1]"), plc.get("s[1].x"), plc.get("i")), (3, 6, 0))


class SclStringTest(unittest.TestCase):
    SRC = prog("VAR\n start AT %IX0.0 : BOOL;\n msg : STRING;\n m2 : STRING := 'VAR END_VAR';\n m3 : STRING := 'x: Rec';\n r : Rec;\nEND_VAR",
               "IF start THEN msg := 'it$'s start now'; END_IF;\nmsg := 'a, start := 1'; (* start *)")
    TYPES = "TYPE Rec : STRUCT v : INT; END_STRUCT END_TYPE\n"

    def test_strings_survive_scl_export(self):
        s = to_scl(self.TYPES + self.SRC)
        for lit in ("'VAR END_VAR'", "'x: Rec'", "'it$'s start now'", "'a, start := 1'", "(* start *)"):
            self.assertIn(lit, s)
        self.assertIn('IF "start" THEN', s)
        self.assertIn('r : "Rec";', s)

    def test_every_string_literal_identical_in_all_text_exports(self):
        lits = ["'VAR END_VAR'", "'x: Rec'", "'it$'s start now'", "'a, start := 1'"]
        for fn in (to_scl, to_plcopen):
            out = fn(self.TYPES + self.SRC).replace("&apos;", "'")
            for lit in lits:
                self.assertIn(lit, out, fn.__name__)
        for fn in (to_gxworks, to_sysmac, to_l5x):
            out = fn(self.SRC.replace(" r : Rec;\n", ""))
            for lit in lits[2:]:
                self.assertIn(lit, out, fn.__name__)

    def test_empty_block_removed_but_comment_block_kept(self):
        s = to_scl(prog("VAR\n a AT %IX0.0 : BOOL;\nEND_VAR\nVAR (* keep me *) END_VAR\nVAR q : BOOL; END_VAR", "q := a;"))
        self.assertIn("(* keep me *)", s)
        self.assertEqual(s.count("END_VAR"), 2)

    def test_struct_init_with_escaped_quote(self):
        x = to_plcopen("TYPE R : STRUCT a : STRING; b : INT; END_STRUCT END_TYPE\n"
                       + prog("VAR r : R := (a := 'x$', y', b := 2); END_VAR", "r.b := 1;"))
        self.assertIn('<value member="b"><simpleValue value="2"/></value>', x)
        self.assertEqual(x.count("<value member="), 2)


class TempArrayTest(unittest.TestCase):
    def test_temp_struct_array_and_struct_reinitialised(self):
        src = ("TYPE S : STRUCT x : INT; END_STRUCT END_TYPE\n"
               + prog("VAR_TEMP s : ARRAY[0..1] OF S; q : S; END_VAR\nVAR o : INT; END_VAR",
                      "s[1].x := s[1].x + 1; q.x := q.x + 1; o := s[1].x + q.x;"))
        plc = VirtualPLC(src)
        plc.scan(3)
        self.assertEqual(plc.get("o"), 2)

    def test_temp_array_reinitialised(self):
        plc = VirtualPLC(prog("VAR_TEMP a : ARRAY[0..2] OF INT := [1, 2, 3]; END_VAR\nVAR o : INT; END_VAR",
                              "a[0] := a[0] + 1; o := a[0] + a[2];"))
        plc.scan(4)
        self.assertEqual(plc.get("o"), 5)

    SRC = prog("VAR CONSTANT N : INT := 1; END_VAR\nVAR_TEMP a : ARRAY[0..2] OF INT; b : ARRAY[0..N, 0..1] OF REAL := [1.5, 2(2.5)]; END_VAR\nVAR o : INT; END_VAR",
               "a[0] := a[0] + 1; o := a[0];")

    def test_export_assigns_every_element(self):
        want = ["a[0] := 0;", "a[1] := 0;", "a[2] := 0;", "b[0, 0] := 1.5;", "b[0, 1] := 2.5;", "b[1, 0] := 2.5;", "b[1, 1] := 0.0;"]
        for fn in (to_scl, to_gxworks, to_sysmac):
            lines = fn(self.SRC).splitlines()
            k = lines.index(want[0])
            self.assertEqual(lines[k:k + 7], want, fn.__name__)
        x = to_l5x(self.SRC)
        for k, w in enumerate(want):
            self.assertIn(f'<Line Number="{k}"><![CDATA[{w}]]></Line>', x)
        self.assertNotIn(":= [", to_scl(self.SRC).split("BEGIN")[0].split("VAR_TEMP")[1])

    def test_large_or_struct_temp(self):
        big = prog("VAR_TEMP a : ARRAY[0..99] OF INT%s; END_VAR\nVAR o : INT; END_VAR", "o := a[0];")
        self.assertIn("// 注意:a 為暫存變數", to_scl(big % ""))
        with self.assertRaises(STError):
            to_scl(big % " := [1]")
        with self.assertRaises(STError):
            to_scl(prog("VAR_TEMP a : ARRAY[0..1] OF INT := [1, 2, 3]; END_VAR", "a[0] := 1;"))


class L5xRangeTest(unittest.TestCase):
    def tag(self, decl):
        return to_l5x(prog(f"VAR {decl} END_VAR", "x := x;"))

    def test_out_of_range_rejected_with_reason(self):
        for decl, word in (("x : INT := 70000;", "INT 範圍"), ("x : UINT := 60000;", "原型別 UINT 對映為 INT"),
                           ("x : USINT := 200;", "對映為 SINT"), ("x : SINT := -129;", "SINT 範圍"),
                           ("x : UDINT := 4000000000;", "對映為 DINT"), ("x : TIME := T#30d;", "原型別 TIME 對映為 DINT"),
                           ("x : REAL := 1e39;", "REAL(單精度)"), ("x : LREAL := 1e300;", "原型別 LREAL 對映為 REAL"),
                           ("x : WORD := 16#FFFF;", "對映為 INT")):
            with self.assertRaises(STError) as c:
                self.tag(decl)
            self.assertIn(word, str(c.exception), decl)
            self.assertIn("標籤 x", str(c.exception))

    def test_boundaries_accepted(self):
        for decl, val in (("x : INT := 32767;", "32767"), ("x : INT := -32768;", "-32768"), ("x : SINT := -128;", "-128"),
                          ("x : UINT := 32767;", "32767"), ("x : DINT := -2147483648;", "-2147483648"),
                          ("x : TIME := T#24d;", "2073600000"), ("x : LINT := 9223372036854775807;", "9223372036854775807"),
                          ("x : REAL := -3.4e38;", "-3.4e+38"), ("x : INT := INT#-5;", "-5")):
            self.assertIn(f'Value="{val}"', self.tag(decl), decl)

    def test_constant_out_of_range_also_rejected(self):
        with self.assertRaises(STError):
            to_l5x(prog("VAR CONSTANT K : UINT := 65535; END_VAR\nVAR x : UINT; END_VAR", "x := K;"))


FN = ("FUNCTION Bump : INT\nVAR_IN_OUT v : INT; END_VAR\nVAR_INPUT d : INT; END_VAR\nVAR_OUTPUT w : INT; END_VAR\n"
      "v := v + 1; w := v; Bump := v + d;\nEND_FUNCTION\n")
FB = "FUNCTION_BLOCK B\nVAR_IN_OUT v : INT; END_VAR\nVAR_INPUT d : INT; END_VAR\nv := v + d;\nEND_FUNCTION_BLOCK\n"
K = "VAR CONSTANT K : INT := 1; A : ARRAY[0..1] OF INT := [1, 2]; END_VAR\nVAR r, x : INT; b : B; END_VAR"


class ConstWriteBackTest(unittest.TestCase):
    def test_checker_flags_constant_written_back(self):
        for body in ("r := Bump(v := K);", "r := Bump(K);", "r := Bump(v := A[0]);", "r := Bump(v := x, w => K);",
                     "Bump(v := K);", "b(v := K);", "b(v := A[1], d := 1);"):
            self.assertIn("write to CONSTANT", " ".join(errors(FN + FB + prog(K, body))), body)

    def test_constant_as_plain_input_is_fine(self):
        for body in ("r := Bump(v := x, d := K);", "r := Bump(x, K);", "b(v := x, d := K);", "r := Bump(v := x, w => r);"):
            self.assertEqual(errors(FN + FB + prog(K, body)), [], body)

    def test_runtime_matches_checker(self):
        for body in ("r := Bump(v := K);", "b(v := K);", "FOR K := 0 TO 1 DO x := x + 1; END_FOR;"):
            plc = VirtualPLC(FN + FB + prog(K, body))
            with self.assertRaises(STError) as c:
                plc.scan(1)
            self.assertIn("CONSTANT K", str(c.exception), body)
            self.assertEqual(plc.get("K"), 1, body)
        plc = VirtualPLC(FN + FB + prog(K, "r := Bump(v := x, d := K);"))
        plc.scan(2)
        self.assertEqual((plc.get("x"), plc.get("r")), (2, 3))


if __name__ == "__main__":
    unittest.main()
