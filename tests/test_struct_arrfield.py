"""STRUCT 內含 ARRAY 欄位(一維 / 多維、初始值、整體賦值、檢查、匯出)。"""
import unittest
import xml.etree.ElementTree as ET

from plc_st.checker import check
from plc_st.export import export
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

HEAD = """TYPE R : STRUCT id : INT := 5; buf : ARRAY[0..3] OF INT := [1,2]; m : ARRAY[1..2,1..2] OF REAL; END_STRUCT END_TYPE
TYPE O : STRUCT r : R; END_STRUCT END_TYPE
"""


def run(body, decl="VAR a, b : R; i, s : INT; o : O; END_VAR", n=1):
    p = VirtualPLC(HEAD + f"PROGRAM P {decl} {body} END_PROGRAM")
    p.scan(n)
    return p


class ArrField(unittest.TestCase):
    def test_init_and_default(self):
        p = run("")
        self.assertEqual(p.vars["a.buf"], [1, 2, 0, 0])
        self.assertEqual(p.vars["a.m"], [0.0] * 4)

    def test_read_write_loop(self):
        p = run("FOR i := 0 TO 3 DO a.buf[i] := a.buf[i] + i; END_FOR s := a.buf[3];")
        self.assertEqual(p.get("s"), 3)
        self.assertEqual(p.get("a.buf[1]"), 3)

    def test_multidim_and_nested(self):
        p = run("a.m[2,1] := 2.5; o.r.buf[2] := 7; s := o.r.buf[2];")
        self.assertEqual(p.get("a.m[2,1]"), 2.5)
        self.assertEqual(p.get("s"), 7)

    def test_struct_copy_is_deep(self):
        p = run("b := a; a.buf[0] := 99; s := b.buf[0];")
        self.assertEqual(p.get("s"), 1)
        self.assertEqual(p.get("a.buf[0]"), 99)

    def test_out_of_range_runtime(self):
        with self.assertRaises(STError):
            run("i := 9; a.buf[i] := 1;")

    def test_without_index_errors(self):
        with self.assertRaises(STError):
            run("s := a.buf;")

    def test_snapshot_names(self):
        self.assertIn("a.buf[2]", run("").snapshot())

    def test_array_of_struct_with_array_field_rejected(self):
        with self.assertRaises(STError):
            VirtualPLC(HEAD + "PROGRAM P VAR x : ARRAY[0..1] OF R; END_VAR END_PROGRAM")

    def test_too_many_inits(self):
        with self.assertRaises(STError):
            VirtualPLC("TYPE T : STRUCT b : ARRAY[0..1] OF INT := [1,2,3]; END_STRUCT END_TYPE PROGRAM P VAR t : T; END_VAR END_PROGRAM")


class Checker(unittest.TestCase):
    def msgs(self, body):
        return [str(i) for i in check(HEAD + f"PROGRAM P VAR a : R; x : INT; f : BOOL; END_VAR {body} END_PROGRAM")]

    def test_clean(self):
        self.assertEqual(self.msgs("a.buf[1] := 3; x := a.buf[2]; a.m[1,2] := 1.5;"), [])

    def test_errors(self):
        m = "\n".join(self.msgs("x := a.buf; a.buf[7] := 1; a.buf[0,1] := 1; a.id[0] := 1; f := a.buf[1];"))
        for frag in ("used without index", "out of range", "needs 1 index", "not an array", "type mismatch"):
            self.assertIn(frag, m)


class Export(unittest.TestCase):
    SRC = HEAD.replace("[1,2,3]", "") + "PROGRAM P VAR a : R; END_VAR a.buf[0] := 1; END_PROGRAM"

    def test_plcopen_and_l5x(self):
        ET.fromstring(export(self.SRC.replace(",1..2", ""), "plcopen"))
        self.assertIn("buf", export(self.SRC.replace("m : ARRAY[1..2,1..2] OF REAL;", ""), "l5x"))


if __name__ == "__main__":
    unittest.main()
