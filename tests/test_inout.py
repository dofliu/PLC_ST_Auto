import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

SRC = """FUNCTION Bump : INT
VAR_INPUT step : INT; END_VAR
VAR_IN_OUT v : INT; END_VAR
v := v + step;
Bump := v;
END_FUNCTION

FUNCTION_BLOCK Acc
VAR_INPUT d : INT; END_VAR
VAR_IN_OUT total : INT; END_VAR
total := total + d;
END_FUNCTION_BLOCK

PROGRAM P
VAR
  x : INT := 1; r : INT; y : INT := 10;
  arr : ARRAY[0..2] OF INT := [0,0,0];
  a1 : Acc;
END_VAR
r := Bump(step := 2, v := x);
Bump(3, arr[1]);
a1(d := 5, total := y);
END_PROGRAM
"""


class InOut(unittest.TestCase):
    def test_writeback(self):
        p = VirtualPLC(SRC)
        p.scan(2)
        self.assertEqual(p.get("x"), 5)       # +2 per scan
        self.assertEqual(p.get("r"), 5)
        self.assertEqual(p.get("arr[1]"), 6)  # +3 per scan, positional
        self.assertEqual(p.get("y"), 20)      # FB in/out, +5 per scan

    def test_literal_rejected(self):
        src = SRC.replace("v := x)", "v := 3)")
        with self.assertRaises(STError):
            VirtualPLC(src).scan()

    def test_checker_ok(self):
        errs = [d for d in check(SRC) if getattr(d, "level", "error") == "error"]
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
