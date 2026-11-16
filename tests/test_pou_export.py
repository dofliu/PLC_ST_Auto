"""M33:自訂 FUNCTION / FUNCTION_BLOCK 匯出(PLCopen XML、Siemens SCL)。"""
import os
import unittest
import xml.etree.ElementTree as ET

from plc_st.export import export, split_pous, to_plcopen, to_scl, validate_plcopen, _scl_calls
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

HERE = os.path.dirname(__file__)
with open(os.path.join(HERE, "..", "examples", "userpou_export.st"), encoding="utf-8") as f:
    SRC = f.read()
NS = {"p": "http://www.plcopen.org/xml/tc6_0201"}


class SplitTests(unittest.TestCase):
    def test_order_kinds_and_return_type(self):
        ps = split_pous(SRC)
        self.assertEqual([(p["kind"], p["name"], p["rtype"]) for p in ps],
                         [("function", "Scale", "REAL"), ("function", "Clamp", "INT"),
                          ("fb", "Latch", None), ("program", "Main", None)])
        self.assertEqual(ps[0]["blocks"], [("VAR_INPUT", [("raw", "INT", None), ("hi", "REAL", None)]),
                                           ("VAR", [("k", "REAL", "100.0")])])
        self.assertTrue(ps[0]["body"].startswith("Scale :="))

    def test_keywords_in_comment_or_string_ignored(self):
        ps = split_pous("(* FUNCTION X : INT END_FUNCTION *)\nPROGRAM P\nVAR s : STRING := 'END_PROGRAM'; END_VAR\n"
                        "s := 'FUNCTION_BLOCK B';\nEND_PROGRAM")
        self.assertEqual([p["name"] for p in ps], ["P"])
        self.assertIn("FUNCTION_BLOCK B", ps[0]["body"])

    def test_requires_single_program(self):
        with self.assertRaises(STError):
            split_pous("FUNCTION F : INT END_FUNCTION")
        with self.assertRaises(STError):
            split_pous("PROGRAM A END_PROGRAM PROGRAM B END_PROGRAM")


class PlcopenTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(to_plcopen(SRC).encode("utf-8"))
        self.pous = {p.get("name"): p for p in self.root.findall(".//p:pou", NS)}

    def test_pou_types(self):
        self.assertEqual({n: p.get("pouType") for n, p in self.pous.items()},
                         {"Scale": "function", "Clamp": "function", "Latch": "functionBlock", "Main": "program"})

    def test_return_type_first_in_interface(self):
        itf = self.pous["Scale"].find("p:interface", NS)
        self.assertTrue(itf[0].tag.endswith("returnType"))
        self.assertTrue(itf[0][0].tag.endswith("REAL"))
        self.assertIsNone(self.pous["Latch"].find("p:interface/p:returnType", NS))

    def test_sections_and_fb_instance_type(self):
        self.assertEqual([v.get("name") for v in self.pous["Latch"].findall("p:interface/p:outputVars/p:variable", NS)], ["q", "n"])
        l1 = [v for v in self.pous["Main"].findall("p:interface/p:localVars/p:variable", NS) if v.get("name") == "l1"][0]
        self.assertEqual(l1.find("p:type/p:derived", NS).get("name"), "Latch")

    def test_bodies_separate(self):
        body = "".join(self.pous["Clamp"].find("p:body", NS).itertext())
        self.assertIn("RETURN;", body)
        self.assertNotIn("l1(", body)

    def test_only_program_instantiated(self):
        inst = self.root.findall(".//p:pouInstance", NS)
        self.assertEqual([i.get("typeName") for i in inst], ["Main"])

    def test_schema_valid(self):
        try:
            import lxml  # noqa: F401
        except ImportError:
            self.skipTest("lxml not installed")
        self.assertEqual(validate_plcopen(to_plcopen(SRC)), [])


class SclTests(unittest.TestCase):
    def setUp(self):
        self.out = to_scl(SRC)

    def test_block_order_and_headers(self):
        idx = [self.out.index(h) for h in ('FUNCTION "Scale" : REAL', 'FUNCTION "Clamp" : INT',
                                           'FUNCTION_BLOCK "Latch"', 'ORGANIZATION_BLOCK "Main"')]
        self.assertEqual(idx, sorted(idx))
        for end in ("END_FUNCTION\n", "END_FUNCTION_BLOCK\n", "END_ORGANIZATION_BLOCK\n"):
            self.assertIn(end, self.out)
        self.assertEqual(self.out.count("BEGIN"), 4)

    def test_function_locals_become_temp_with_init_in_body(self):
        fc = self.out[:self.out.index('FUNCTION "Clamp"')]
        self.assertIn("VAR_TEMP", fc)
        self.assertNotIn(":= 100.0;\n   END_VAR", fc)
        self.assertLess(fc.index("BEGIN"), fc.index("k := 100.0;"))
        self.assertLess(fc.index("k := 100.0;"), fc.index("Scale := INT_TO_REAL"))

    def test_uninitialised_temps_zeroed(self):
        out = to_scl("FUNCTION F : INT\nVAR a : INT; b : BOOL; r : REAL; t : TIME; END_VAR\nF := a;\nEND_FUNCTION\n"
                     "PROGRAM P\nVAR x : INT; END_VAR\nx := F();\nEND_PROGRAM")
        for stmt in ("a := 0;", "b := FALSE;", "r := 0.0;", "t := T#0s;"):
            self.assertIn(stmt, out)
        self.assertIn('x := "F"();', out)

    def test_temp_array_expanded_or_rejected(self):
        # M34 審查修正:小型基本型別陣列逐元素指派(行為與虛擬 PLC 一致);過大的陣列才提醒或報錯
        base = "FUNCTION F : INT\nVAR a : ARRAY[0..%d] OF INT%s; END_VAR\nF := a[0];\nEND_FUNCTION\nPROGRAM P\nEND_PROGRAM"
        self.assertIn("   a[0] := 1;\n   a[1] := 2;", to_scl(base % (1, " := [1, 2]")))
        self.assertIn("   a[0] := 0;\n   a[1] := 0;", to_scl(base % (1, "")))
        with self.assertRaises(STError):
            to_scl(base % (99, " := [1, 2]"))
        self.assertIn("// 注意:a 為暫存變數", to_scl(base % (99, "")))

    def test_calls_quoted_and_positional_args_named(self):
        self.assertIn('level := "Scale"(raw := level_raw, hi := 200.0);', self.out)
        self.assertIn('duty := "Clamp"(x := REAL_TO_INT("Scale"(raw := level_raw, hi := 100.0)), lo := 0, top := 80);', self.out)

    def test_string_and_comment_untouched(self):
        self.assertIn("msg : STRING := 'Clamp(1, 2)';", self.out)
        self.assertIn("(* 位置引數 *)", self.out)

    def test_fb_instance_type_quoted_and_calls_kept(self):
        self.assertIn('l1 : "Latch";', self.out)
        self.assertIn("l1(set := start, rst := stop);", self.out)
        self.assertIn("rt : R_TRIG;", self.out)      # 標準 FB 不加引號

    def test_call_rewrite_edge_cases(self):
        f = {"f": ("F", ["a", "b"])}
        self.assertEqual(_scl_calls("y := F(g(1, 2), 'x,(y');", f), "y := \"F\"(a := g(1, 2), b := 'x,(y');")
        self.assertEqual(_scl_calls("y := inst.F(1);", f), "y := inst.F(1);")     # 成員呼叫不改
        self.assertEqual(_scl_calls("y := F(b := (1 + 2), a := 3);", f), 'y := "F"(b := (1 + 2), a := 3);')
        self.assertEqual(_scl_calls("y := F(F(1, 2), 3);", f), 'y := "F"(a := "F"(a := 1, b := 2), b := 3);')
        with self.assertRaises(STError):
            _scl_calls("y := F(1, 2, 3);", f)
        with self.assertRaises(STError):
            _scl_calls("y := F(1, 2;", f)

    def test_struct_udt_with_function(self):
        out = to_scl("TYPE Pt : STRUCT x : INT; END_STRUCT END_TYPE\nFUNCTION GetX : INT\nVAR_INPUT p : Pt; END_VAR\n"
                     "GetX := p.x;\nEND_FUNCTION\nPROGRAM P\nVAR a : Pt; r : INT; END_VAR\nr := GetX(a);\nEND_PROGRAM")
        self.assertLess(out.index('TYPE "Pt"'), out.index('FUNCTION "GetX"'))
        self.assertIn('p : "Pt";', out)
        self.assertIn('r := "GetX"(p := a);', out)


class GateTests(unittest.TestCase):
    def test_other_formats_reject_with_reason(self):
        with self.assertRaises(STError) as c:
            export(SRC, "l5x")
        self.assertIn("Add-On Instruction", str(c.exception))
        for fmt in ("gxworks", "sysmac"):
            with self.assertRaises(STError):
                export(SRC, fmt)

    def test_st_passthrough_and_example_runs(self):
        self.assertEqual(export(SRC, "st"), SRC)
        p = VirtualPLC(SRC)
        p.set_input("start", True); p.set_input("level_raw", 50); p.scan(2)
        self.assertEqual((p.get("level"), p.get("duty"), p.get("pump"), p.get("starts")), (100.0, 50, True, 1))

    def test_program_only_output_unchanged_shape(self):
        out = export("PROGRAM P VAR x : INT; END_VAR x := 1; END_PROGRAM", "scl")
        self.assertTrue(out.startswith("ORGANIZATION_BLOCK"))
        self.assertTrue(out.endswith("END_ORGANIZATION_BLOCK\n"))


if __name__ == "__main__":
    unittest.main()
