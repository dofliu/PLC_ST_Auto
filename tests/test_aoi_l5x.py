"""M35:自訂 FUNCTION_BLOCK → Rockwell L5X Add-On Instruction 匯出。"""
import os
import unittest
import xml.etree.ElementTree as ET

from plc_st.export import export, to_l5x
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

HERE = os.path.dirname(__file__)
with open(os.path.join(HERE, "..", "examples", "aoi_l5x.st"), encoding="utf-8") as f:
    SRC = f.read()

FB = ("FUNCTION_BLOCK Cnt\nVAR_INPUT en : BOOL; step : INT := 2; END_VAR\nVAR_IN_OUT acc : DINT; END_VAR\n"
      "VAR_OUTPUT q : BOOL; END_VAR\nVAR_TEMP t : INT := 5; END_VAR\n"
      "IF en THEN acc := acc + step + t; END_IF;\nq := acc > 10;\nEND_FUNCTION_BLOCK\n")


def prog(decl, body, fb=FB):
    return f"{fb}PROGRAM P\nVAR {decl} END_VAR\n{body}\nEND_PROGRAM"


def lines(root, routine):
    r = root.find(f".//Routine[@Name='{routine}']")
    return [ln.text for ln in r.findall("STContent/Line")]


class AoiDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(to_l5x(SRC))
        self.aoi = {a.get("Name"): a for a in self.root.findall(".//AddOnInstructionDefinition")}

    def test_order_and_location(self):
        ctl = self.root.find("Controller")
        self.assertEqual([c.tag for c in ctl], ["AddOnInstructionDefinitions", "Programs"])
        self.assertEqual(list(self.aoi), ["Latch", "Accum"])

    def test_system_and_user_parameters(self):
        ps = {p.get("Name"): p for p in self.aoi["Latch"].findall("Parameters/Parameter")}
        self.assertEqual(list(ps), ["EnableIn", "EnableOut", "set", "rst", "q", "n"])
        self.assertEqual(ps["EnableIn"].get("Visible"), "false")
        self.assertEqual((ps["set"].get("Usage"), ps["set"].get("Required"), ps["set"].get("ExternalAccess")),
                         ("Input", "false", "Read/Write"))
        self.assertEqual((ps["n"].get("Usage"), ps["n"].get("DataType"), ps["n"].get("ExternalAccess")),
                         ("Output", "INT", "Read Only"))

    def test_inout_required_and_default_data(self):
        ps = {p.get("Name"): p for p in self.aoi["Accum"].findall("Parameters/Parameter")}
        self.assertEqual((ps["shared"].get("Usage"), ps["shared"].get("Required")), ("InOut", "true"))
        self.assertIsNone(ps["shared"].get("ExternalAccess"))
        self.assertEqual(ps["add"].find("DefaultData/DataValue").get("Value"), "1")

    def test_local_tags(self):
        ls = {t.get("Name"): t for t in self.aoi["Accum"].findall("LocalTags/LocalTag")}
        self.assertEqual(ls["inner"].get("DataType"), "Latch")
        self.assertEqual(ls["buf"].get("Dimensions"), "4")
        self.assertEqual(ls["LAST"].find("DefaultData/DataValue").get("Value"), "3")
        self.assertIn("CONSTANT", ls["LAST"].find("Description").text)

    def test_nested_call_converted_inside_aoi(self):
        ls = [x.strip() for x in lines(self.aoi["Accum"], "Logic")]
        self.assertEqual(ls[:3], ["inner.set := go;", "inner.rst := FALSE;", "Latch(inner);"])

    def test_program_calls_converted(self):
        ls = [x.strip() for x in lines(self.root, "MainRoutine")]
        self.assertEqual(ls[:4], ["l1.set := start;", "l1.rst := stop;", "Latch(l1);", "pump := l1.q;"])
        self.assertIn("Accum(acc, pool);", ls)
        self.assertIn("sum := acc.total;", ls)
        tags = {t.get("Name"): t.get("DataType") for t in self.root.findall(".//Program/Tags/Tag")}
        self.assertEqual((tags["l1"], tags["acc"]), ("Latch", "Accum"))

    def test_indentation_kept(self):
        self.assertIn("  acc.add := 10;", lines(self.root, "MainRoutine"))

    def test_source_still_runs_on_virtual_plc(self):
        plc = VirtualPLC(SRC)
        plc.set_input("start", True)
        plc.scan(2)
        self.assertEqual(plc.get("sum"), 90)
        self.assertEqual(plc.get("pool"), 140)


class CallConversionTests(unittest.TestCase):
    def body(self, decl, body, fb=FB):
        return [x.strip() for x in lines(ET.fromstring(to_l5x(prog(decl, body, fb))), "MainRoutine")]

    def test_positional_args(self):
        self.assertEqual(self.body("c : Cnt; x : BOOL; a : DINT;", "c(x, 3, a);"),
                         ["c.en := x;", "c.step := 3;", "Cnt(c, a);"])

    def test_no_input_args(self):
        self.assertEqual(self.body("c : Cnt; a : DINT;", "c(acc := a);"), ["Cnt(c, a);"])

    def test_temp_reinit_in_aoi(self):
        root = ET.fromstring(to_l5x(prog("c : Cnt; a : DINT;", "c(acc := a);")))
        self.assertEqual(lines(root, "Logic")[0], "t := 5;")

    def test_inside_if_and_case(self):
        out = self.body("c : Cnt; a : DINT; k : INT;", "IF a > 0 THEN c(acc := a); END_IF;\nCASE k OF 1: c(acc := a); END_CASE;")
        self.assertEqual("\n".join(out).count("Cnt(c, a);"), 2)
        self.assertIn("IF a > 0 THEN Cnt(c, a); END_IF;", out)

    def test_string_and_comment_untouched(self):
        out = self.body("c : Cnt; a : DINT; s : STRING;", "s := 'c(acc := a);'; (* c(acc := a); *)\nc(acc := a);")
        self.assertIn("s := 'c(acc := a);'; (* c(acc := a); *)", out)
        self.assertEqual(out[-1], "Cnt(c, a);")

    def test_case_insensitive_names(self):
        self.assertEqual(self.body("c : Cnt; a : DINT;", "C(ACC := a, Q => a);")[-2:], ["Cnt(C, a);", "a := C.q;"])


class ErrorTests(unittest.TestCase):
    def err(self, src, text):
        with self.assertRaises(STError) as c:
            to_l5x(src)
        self.assertIn(text, str(c.exception))

    def test_missing_inout(self):
        self.err(prog("c : Cnt;", "c(en := TRUE);"), "VAR_IN_OUT")

    def test_output_with_assign(self):
        self.err(prog("c : Cnt; a : DINT;", "c(acc := a, q := TRUE);"), "=>")

    def test_unknown_param(self):
        self.err(prog("c : Cnt; a : DINT;", "c(acc := a, zz := 1);"), "zz")

    def test_call_in_expression(self):
        self.err(prog("c : Cnt; a : DINT; b : BOOL;", "b := c(acc := a);"), "獨立敘述")

    def test_array_input_param(self):
        fb = "FUNCTION_BLOCK F\nVAR_INPUT v : ARRAY[0..2] OF INT; END_VAR\nEND_FUNCTION_BLOCK\n"
        self.err(prog("f : F;", "f();", fb), "VAR_IN_OUT")

    def test_string_and_timer_output(self):
        for t in ("STRING", "TON"):
            fb = f"FUNCTION_BLOCK F\nVAR_OUTPUT v : {t}; END_VAR\nEND_FUNCTION_BLOCK\n"
            self.err(prog("f : F;", "f();", fb), "基本型別")

    def test_reserved_name(self):
        fb = "FUNCTION_BLOCK F\nVAR_INPUT EnableIn : BOOL; END_VAR\nEND_FUNCTION_BLOCK\n"
        self.err(prog("f : F;", "f();", fb), "系統參數")

    def test_instance_array(self):
        self.err(prog("cs : ARRAY[0..1] OF Cnt; a : DINT;", "a := a;"), "實例陣列")

    def test_located_var_in_fb(self):
        fb = "FUNCTION_BLOCK F\nVAR x AT %IX0.0 : BOOL; END_VAR\nEND_FUNCTION_BLOCK\n"
        self.err(prog("f : F;", "f();", fb), "AT")

    def test_function_still_rejected(self):
        src = "FUNCTION G : INT\nVAR_INPUT a : INT; END_VAR\nG := a;\nEND_FUNCTION\n" + prog("x : INT;", "x := G(1);", "")
        with self.assertRaises(STError) as c:
            export(src, "l5x")
        self.assertIn("FUNCTION_BLOCK", str(c.exception))

    def test_fb_only_export_gate_open(self):
        self.assertIn("<AddOnInstructionDefinitions>", export(SRC, "l5x"))


if __name__ == "__main__":
    unittest.main()
