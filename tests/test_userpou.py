import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

SRC = """FUNCTION Scale : REAL
VAR_INPUT raw : INT; hi : REAL; END_VAR
Scale := INT_TO_REAL(raw) * hi / 100.0;
END_FUNCTION

FUNCTION Clamp : INT
VAR_INPUT x : INT; END_VAR
IF x > 10 THEN
  Clamp := 10;
  RETURN;
END_IF;
Clamp := x;
END_FUNCTION

FUNCTION_BLOCK Latch
VAR_INPUT set : BOOL; rst : BOOL; END_VAR
VAR_OUTPUT q : BOOL; n : INT; END_VAR
VAR rt : R_TRIG; END_VAR
rt(CLK := set);
IF rt.Q THEN n := n + 1; END_IF;
IF set THEN q := TRUE; END_IF;
IF rst THEN q := FALSE; END_IF;
END_FUNCTION_BLOCK

PROGRAM P
VAR
  a : INT := 50; b : INT; s : REAL;
  l1 : Latch; l2 : Latch;
  go : BOOL; r : BOOL; out1 : BOOL; cnt : INT;
END_VAR
s := Scale(a, 200.0);
b := Clamp(a);
l1(set := go, rst := r);
l2(set := FALSE, rst := FALSE);
out1 := l1.q;
cnt := l1.n;
END_PROGRAM
"""


class UserPouTests(unittest.TestCase):
    def test_function(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        self.assertEqual(p.get("s"), 100.0)
        self.assertEqual(p.get("b"), 10)  # RETURN path

    def test_fb_state_and_independent_instances(self):
        p = VirtualPLC(SRC)
        p.set_input("go", True); p.scan(1)
        self.assertTrue(p.get("out1")); self.assertEqual(p.get("cnt"), 1)
        p.scan(2)                      # no new rising edge
        self.assertEqual(p.get("cnt"), 1)
        p.set_input("go", False); p.scan(1)
        self.assertTrue(p.get("out1"))  # latched across scans
        p.set_input("r", True); p.scan(1)
        self.assertFalse(p.get("out1"))
        self.assertFalse(p.get("l2.q"))  # other instance untouched

    def test_checker_clean(self):
        errs = [i for i in check(SRC) if i.severity == "error"]
        self.assertEqual(errs, [])

    def test_checker_errors(self):
        bad = SRC.replace("Clamp(a)", "Clamp(a, 1)").replace("l1.q", "l1.zzz")
        msgs = " ".join(str(i) for i in check(bad))
        self.assertIn("too many arguments", msgs)
        self.assertIn("no member zzz", msgs)

    def test_checker_body_error_in_pou(self):
        bad = SRC.replace("Clamp := x;", "Clamp := undefined_v;")
        self.assertTrue(any("undeclared" in str(i) for i in check(bad)))

    def test_recursion_blocked(self):
        src = """FUNCTION F : INT
VAR_INPUT x : INT; END_VAR
F := F(x);
END_FUNCTION
PROGRAM P VAR y : INT; END_VAR y := F(1); END_PROGRAM"""
        p = VirtualPLC(src)
        with self.assertRaises(STError):
            p.scan(1)

    def test_named_args_and_dup(self):
        p = VirtualPLC(SRC.replace("Scale(a, 200.0)", "Scale(hi := 10.0, raw := a)"))
        p.scan(1)
        self.assertEqual(p.get("s"), 5.0)
        with self.assertRaises(STError):
            VirtualPLC("FUNCTION A : INT\nEND_FUNCTION\nFUNCTION a : INT\nEND_FUNCTION\nPROGRAM P END_PROGRAM")


if __name__ == "__main__":
    unittest.main()


class ExportGuard(unittest.TestCase):
    def test_export(self):
        from plc_st.export import export
        self.assertIn("FUNCTION Scale", export(SRC, "st"))
        with self.assertRaises(STError):
            export(SRC, "plcopen")
