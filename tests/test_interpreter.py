import unittest
from pathlib import Path
from plc_st import VirtualPLC, STError

ROOT = Path(__file__).resolve().parent.parent


def prog(vars_, body):
    return f"PROGRAM T\nVAR {vars_} END_VAR\n{body}\nEND_PROGRAM"


class TestCore(unittest.TestCase):
    def test_motor_example(self):
        plc = VirtualPLC((ROOT / "examples/motor.st").read_text(), scan_ms=100)
        plc.set_input("start", True)
        plc.scan(1)
        self.assertTrue(plc.get("motor"))
        plc.set_input("start", False)
        plc.scan(10)
        self.assertTrue(plc.get("t.Q"))
        self.assertGreater(plc.get("cnt"), 0)
        plc.set_input("stop", True)
        plc.scan(1)
        self.assertFalse(plc.get("motor"))

    def test_arith_precedence(self):
        p = VirtualPLC(prog("x : INT; y : REAL;", "x := 2 + 3 * 4 - 10 / 3; y := 2.0 ** 3;"))
        p.scan()
        self.assertEqual(p.get("x"), 11)
        self.assertEqual(p.get("y"), 8.0)

    def test_int_overflow_wraps(self):
        p = VirtualPLC(prog("x : INT := 32767;", "x := x + 1;"))
        p.scan()
        self.assertEqual(p.get("x"), -32768)

    def test_loops_and_case(self):
        p = VirtualPLC(prog("i : INT; s : INT; c : INT := 7; r : INT;", """
FOR i := 1 TO 10 BY 1 DO s := s + i; END_FOR;
CASE c OF
  1, 2: r := 10;
  5..9: r := 20;
  ELSE r := 30;
END_CASE;
WHILE c > 0 DO c := c - 3; END_WHILE;
"""))
        p.scan()
        self.assertEqual(p.get("s"), 55)
        self.assertEqual(p.get("r"), 20)
        self.assertEqual(p.get("c"), -2)

    def test_repeat_exit(self):
        p = VirtualPLC(prog("n : INT;", "REPEAT n := n + 1; IF n = 5 THEN EXIT; END_IF; UNTIL FALSE END_REPEAT;"))
        p.scan()
        self.assertEqual(p.get("n"), 5)

    def test_timers_counters_edges(self):
        p = VirtualPLC(prog("t : TON; c : CTU; r : R_TRIG; pulse : BOOL; hits : INT;", """
t(IN := TRUE, PT := T#50ms);
c(CU := pulse, PV := 2);
r(CLK := pulse);
IF r.Q THEN hits := hits + 1; END_IF;
"""), )
        p.scan(4)
        self.assertFalse(p.get("t.Q"))
        p.scan(1)
        self.assertTrue(p.get("t.Q"))
        for v in (True, False, True):
            p.set_input("pulse", v)
            p.scan()
        self.assertEqual(p.get("hits"), 2)
        self.assertTrue(p.get("c.Q"))

    def test_tof(self):
        p = VirtualPLC(prog("t : TOF; i : BOOL;", "t(IN := i, PT := T#30ms);"))
        p.set_input("i", True)
        p.scan()
        p.set_input("i", False)
        p.scan(2)
        self.assertTrue(p.get("t.Q"))
        p.scan(2)
        self.assertFalse(p.get("t.Q"))

    def test_errors(self):
        with self.assertRaises(STError):
            VirtualPLC(prog("x : INT;", "x := ;"))
        with self.assertRaises(STError):
            VirtualPLC(prog("x : INT;", "y := 1;")).scan()
        with self.assertRaises(STError):
            VirtualPLC(prog("x : INT;", "x := 1 / 0;")).scan()
        with self.assertRaises(STError):
            VirtualPLC(prog("x : FOO;", ""))

    def test_comments_case_insensitive(self):
        p = VirtualPLC("program a var X : bool; end_var (* c *) x := true; // d\nend_program")
        p.scan()
        self.assertTrue(p.get("X"))


if __name__ == "__main__":
    unittest.main()
