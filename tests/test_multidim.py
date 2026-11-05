import unittest

from plc_st.checker import check
from plc_st.export import export
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

SRC = """PROGRAM P
VAR
  m : ARRAY[1..2, 0..2] OF INT := [1, 2, 3, 4, 5, 6];
  i : INT := 1; j : INT := 0; t : INT;
END_VAR
t := 0;
FOR i := 1 TO 2 DO FOR j := 0 TO 2 DO t := t + m[i, j]; END_FOR; END_FOR;
m[2, 2] := 60;
END_PROGRAM
"""


class MultiDim(unittest.TestCase):
    def test_run_row_major(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        self.assertEqual(p.get("t"), 21)
        self.assertEqual(p.get("m[2,2]"), 60)
        self.assertEqual(p.get("m[1,2]"), 3)
        self.assertIn("m[2,0]", p.snapshot())

    def test_set_input_and_oob(self):
        p = VirtualPLC(SRC)
        p.set_input("m[1,1]", 9)
        self.assertEqual(p.get("m[1,1]"), 9)
        with self.assertRaises(STError):
            p.set_input("m[3,0]", 1)

    def test_checker(self):
        self.assertFalse([x for x in check(SRC) if "needs" in str(x) or "range" in str(x)])
        bad = SRC.replace("m[2, 2] := 60;", "m[2] := 1; m[3, 0] := 1;")
        msgs = " ".join(str(x) for x in check(bad))
        self.assertIn("needs 2 index", msgs)
        self.assertIn("out of range", msgs)

    def test_export_dimensions(self):
        xml = export(SRC, "plcopen")
        self.assertIn('<dimension lower="1" upper="2"/><dimension lower="0" upper="2"/>', xml)


if __name__ == "__main__":
    unittest.main()
