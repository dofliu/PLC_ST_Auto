"""M36:整個陣列傳入 VAR_IN_OUT / VAR_INPUT、陣列整體賦值、L5X COP 改寫、初值超出型別範圍的靜態檢查。"""
import unittest

from plc_st.checker import check
from plc_st.export import export
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

EX = open("examples/array_inout.st", encoding="utf-8").read()


def errors(src):
    return [str(i) for i in check(src) if i.severity == "error"]


FN = """FUNCTION Fill : INT
VAR_IN_OUT d : ARRAY[1..3] OF INT; END_VAR
VAR_INPUT v : INT; END_VAR
VAR i : INT; END_VAR
FOR i := 1 TO 3 DO d[i] := v + i; END_FOR;
Fill := 3;
END_FUNCTION
"""


class Runtime(unittest.TestCase):
    def test_example_shift_and_peak(self):
        p = VirtualPLC(EX)
        for v in (5, 12, 3):
            p.set_input("sample", v)
            p.scan()
        self.assertEqual([p.get(f"hist[{i}]") for i in range(5)], [3, 12, 5, 0, 0])
        self.assertEqual([p.get(f"snap[{i}]") for i in range(5)], [3, 12, 5, 0, 0])
        self.assertEqual(p.get("peak"), 12)

    def test_function_inout_writes_back_and_returns(self):
        src = EX.replace("sh(nv := sample, buf := hist);",
                         "hist[0] := 1; hist[1] := 2; hist[2] := 3; hist[3] := 4; hist[4] := 5;\n"
                         "peak := DINT_TO_INT(SumAndDouble(data := hist));").replace("peak := MaxOf(snap);", "")
        p = VirtualPLC(src)
        p.scan()
        self.assertEqual(p.get("peak"), 15)
        self.assertEqual([p.get(f"hist[{i}]") for i in range(5)], [2, 4, 6, 8, 10])

    def test_input_array_is_a_copy(self):
        src = """FUNCTION Clr : INT
VAR_INPUT a : ARRAY[0..1] OF INT; END_VAR
a[0] := 0; Clr := a[1];
END_FUNCTION
PROGRAM P VAR x : ARRAY[0..1] OF INT := [7, 8]; r : INT; END_VAR
r := Clr(x);
END_PROGRAM"""
        p = VirtualPLC(src)
        p.scan()
        self.assertEqual((p.get("x[0]"), p.get("r")), (7, 8))

    def test_bounds_may_differ_if_shape_matches(self):
        src = FN + "PROGRAM P VAR z : ARRAY[0..2] OF INT; n : INT; END_VAR n := Fill(z, 10); END_PROGRAM"
        p = VirtualPLC(src)
        p.scan()
        self.assertEqual([p.get(f"z[{i}]") for i in range(3)], [11, 12, 13])

    def test_shape_mismatch_rejected(self):
        src = FN + "PROGRAM P VAR z : ARRAY[0..3] OF INT; n : INT; END_VAR n := Fill(z, 1); END_PROGRAM"
        with self.assertRaisesRegex(STError, "does not match"):
            VirtualPLC(src).scan()

    def test_scalar_to_array_param_rejected(self):
        src = FN + "PROGRAM P VAR z : INT; n : INT; END_VAR n := Fill(z, 1); END_PROGRAM"
        with self.assertRaisesRegex(STError, "is an ARRAY"):
            VirtualPLC(src).scan()

    def test_array_assign_is_deep_copy(self):
        p = VirtualPLC("PROGRAM P VAR a : ARRAY[0..2] OF INT := [1,2,3]; b : ARRAY[1..3] OF INT; END_VAR "
                       "b := a; a[0] := 9; END_PROGRAM")
        p.scan()
        self.assertEqual([p.get(f"b[{i}]") for i in (1, 2, 3)], [1, 2, 3])
        self.assertEqual(p.get("a[0]"), 9)

    def test_array_assign_wraps_to_target_type(self):
        p = VirtualPLC("PROGRAM P VAR a : ARRAY[0..1] OF INT := [300, 2]; b : ARRAY[0..1] OF SINT; END_VAR "
                       "b := a; END_PROGRAM")
        p.scan()
        self.assertEqual(p.get("b[0]"), 44)

    def test_array_assign_shape_mismatch(self):
        with self.assertRaisesRegex(STError, "same shape"):
            VirtualPLC("PROGRAM P VAR a : ARRAY[0..2] OF INT; b : ARRAY[0..1] OF INT; END_VAR b := a; "
                       "END_PROGRAM").scan()

    def test_constant_array_not_written(self):
        src = FN + ("PROGRAM P VAR CONSTANT z : ARRAY[0..2] OF INT := [1,2,3]; END_VAR VAR n : INT; END_VAR "
                    "n := Fill(z, 1); END_PROGRAM")
        with self.assertRaisesRegex(STError, "CONSTANT"):
            VirtualPLC(src).scan()

    def test_struct_field_array_argument(self):
        src = "TYPE R : STRUCT buf : ARRAY[1..3] OF INT; END_STRUCT END_TYPE\n" + FN + (
                    "PROGRAM P VAR r : R; n : INT; END_VAR n := Fill(r.buf, 0); END_PROGRAM")
        p = VirtualPLC(src)
        p.scan()
        self.assertEqual(p.get("r.buf[3]"), 3)
        self.assertEqual(errors(src), [])


class Checker(unittest.TestCase):
    def test_example_clean(self):
        self.assertEqual(errors(EX), [])

    def test_type_mismatch(self):
        src = FN + "PROGRAM P VAR z : ARRAY[1..3] OF DINT; n : INT; END_VAR n := Fill(z, 1); END_PROGRAM"
        self.assertTrue(any("ARRAY OF DINT given" in m for m in errors(src)), errors(src))

    def test_shape_mismatch(self):
        src = FN + "PROGRAM P VAR z : ARRAY[1..4] OF INT; n : INT; END_VAR n := Fill(z, 1); END_PROGRAM"
        self.assertTrue(any("shape [4] does not match [3]" in m for m in errors(src)), errors(src))

    def test_constant_bound_shape(self):
        src = FN + ("PROGRAM P VAR CONSTANT CNT : INT := 3; END_VAR VAR z : ARRAY[1..CNT] OF INT; n : INT; END_VAR "
                    "n := Fill(z, 1); END_PROGRAM")
        self.assertEqual(errors(src), [])

    def test_scalar_argument(self):
        src = FN + "PROGRAM P VAR z : INT; n : INT; END_VAR n := Fill(z, 1); END_PROGRAM"
        self.assertTrue(any("is an ARRAY" in m for m in errors(src)), errors(src))

    def test_element_argument(self):
        src = FN + "PROGRAM P VAR z : ARRAY[1..3] OF INT; n : INT; END_VAR n := Fill(z[1], 1); END_PROGRAM"
        self.assertTrue(any("is an ARRAY" in m for m in errors(src)), errors(src))

    def test_fb_param(self):
        bad = EX.replace("hist : ARRAY[0..4] OF INT;", "hist : ARRAY[0..5] OF INT;")
        self.assertTrue(any("argument buf of ShiftReg" in m for m in errors(bad)), errors(bad))

    def test_array_assignment(self):
        ok = "PROGRAM P VAR a : ARRAY[0..2] OF INT; b : ARRAY[1..3] OF INT; END_VAR b := a; END_PROGRAM"
        self.assertEqual(errors(ok), [])
        bad = ok.replace("b : ARRAY[1..3] OF INT", "b : ARRAY[1..3] OF REAL")
        self.assertTrue(any("array assignment" in m for m in errors(bad)), errors(bad))
        scalar = ok.replace("b := a;", "b := 5;")
        self.assertTrue(any("whole array b" in m for m in errors(scalar)), errors(scalar))

    def test_array_of_struct_param_reported(self):
        src = ("TYPE S : STRUCT x : INT; END_STRUCT END_TYPE\n"
               "FUNCTION F : INT VAR_IN_OUT d : ARRAY[0..1] OF S; END_VAR F := d[0].x; END_FUNCTION\n"
               "PROGRAM P VAR a : ARRAY[0..1] OF S; n : INT; END_VAR n := F(a); END_PROGRAM")
        self.assertTrue(any("ARRAY OF STRUCT" in m for m in errors(src)), errors(src))

    def test_constant_array_inout(self):
        src = FN + ("PROGRAM P VAR CONSTANT z : ARRAY[1..3] OF INT := [1,2,3]; END_VAR VAR n : INT; END_VAR "
                    "n := Fill(z, 1); END_PROGRAM")
        self.assertTrue(any("CONSTANT" in m for m in errors(src)), errors(src))


class InitRange(unittest.TestCase):
    def test_scalar_out_of_range(self):
        m = errors("PROGRAM P VAR a : SINT := 300; b : USINT := -1; c : INT := -32768; END_VAR END_PROGRAM")
        self.assertEqual(len(m), 2, m)
        self.assertIn("300 of a out of range for SINT [-128..127]", m[0])
        self.assertIn("-1 of b out of range for USINT", m[1])

    def test_array_elements_and_repeat(self):
        m = errors("PROGRAM P VAR a : ARRAY[0..3] OF BYTE := [2(256), 1, 255]; END_VAR END_PROGRAM")
        self.assertEqual(len(m), 1, m)  # 重複的同一值只報一次
        self.assertIn("256", m[0])

    def test_struct_field_default_reported_once(self):
        src = ("TYPE S : STRUCT k : BYTE := 999; END_STRUCT END_TYPE\n"
               "PROGRAM P VAR s1 : S; s2 : S; END_VAR END_PROGRAM")
        m = errors(src)
        self.assertEqual(len(m), 1, m)
        self.assertIn("S.k", m[0])

    def test_typed_and_hex_literals(self):
        self.assertEqual(errors("PROGRAM P VAR w : WORD := 16#FFFF; d : DINT := DINT#-5; END_VAR END_PROGRAM"), [])
        self.assertTrue(errors("PROGRAM P VAR w : WORD := 16#10000; END_VAR END_PROGRAM"))

    def test_inside_function(self):
        src = "FUNCTION F : INT VAR k : SINT := 200; END_VAR F := k; END_FUNCTION\nPROGRAM P END_PROGRAM"
        self.assertTrue(any("200 of k" in m for m in errors(src)), errors(src))


class Export(unittest.TestCase):
    def test_l5x_cop(self):
        src = ("PROGRAM P VAR a : ARRAY[0..1, 0..2] OF INT; b : ARRAY[0..1, 0..2] OF INT; x : INT; END_VAR\n"
               "b := a; IF x > 0 THEN a := b; END_IF;\n(* c := a; *)\nEND_PROGRAM")
        out = export(src, "l5x")
        self.assertIn("COP(a[0,0], b[0,0], 6);", out)
        self.assertIn("THEN COP(b[0,0], a[0,0], 6);", out)
        self.assertNotIn("b := a;", out)

    def test_l5x_cop_scalar_untouched(self):
        out = export("PROGRAM P VAR a : ARRAY[0..1] OF INT; x : INT; y : INT; END_VAR x := y; END_PROGRAM", "l5x")
        self.assertIn("x := y;", out)

    def test_l5x_cop_mismatch(self):
        with self.assertRaises(STError):
            export("PROGRAM P VAR a : ARRAY[0..1] OF INT; b : ARRAY[0..1] OF DINT; END_VAR b := a; END_PROGRAM",
                   "l5x")

    def test_l5x_aoi_array_inout(self):
        src = EX.split("FUNCTION MaxOf")[0].split("END_FUNCTION\n", 1)[1] + (
            "PROGRAM Main VAR_INPUT sample : INT; END_VAR VAR hist : ARRAY[0..4] OF INT; "
            "snap : ARRAY[0..4] OF INT; sh : ShiftReg; END_VAR\n"
            "sh(nv := sample, buf := hist);\nsnap := hist;\nEND_PROGRAM\n")
        out = export(src, "l5x")
        self.assertIn('Name="buf" TagType="Base" DataType="INT" Dimensions="5" Usage="InOut"', out)
        self.assertIn("ShiftReg(sh, hist);", out)
        self.assertIn("COP(hist[0], snap[0], 5);", out)

    def test_plcopen_and_scl(self):
        from plc_st.export import validate_plcopen
        try:
            import lxml  # noqa: F401
        except ImportError:
            self.skipTest("lxml not installed")
        validate_plcopen(export(EX, "plcopen"))
        scl = export(EX, "scl")
        self.assertIn("data : ARRAY[1..5] OF INT;", scl)
        self.assertIn("snap := hist;", scl)


if __name__ == "__main__":
    unittest.main()
