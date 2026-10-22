import os
import tempfile
import unittest

from plc_st.checker import check
from plc_st.cli import main

HEAD = "PROGRAM p\nVAR_INPUT i : BOOL; END_VAR\nVAR x : INT; b : BOOL; t : TON; END_VAR\n"


def msgs(body, profile="iec", head=HEAD):
    return [str(i) for i in check(head + body + "\nEND_PROGRAM", profile)]


class TestChecker(unittest.TestCase):
    def test_clean(self):
        with open("examples/motor.st", encoding="utf-8") as f:
            self.assertEqual(check(f.read()), [])

    def test_undeclared(self):
        self.assertTrue(any("undeclared variable y" in m for m in msgs("y := 1;")))
        self.assertTrue(any("undeclared variable z" in m for m in msgs("x := z;")))

    def test_type_mismatch(self):
        self.assertTrue(any("type mismatch" in m for m in msgs("x := TRUE;")))
        self.assertTrue(any("type mismatch" in m for m in msgs("b := 5;")))
        self.assertEqual(msgs("x := x + 1; b := x > 2;"), [])

    def test_input_write(self):
        m = msgs("i := TRUE;")
        self.assertTrue(m and m[0].startswith("warning") and "input" in m[0])

    def test_fb_members_and_calls(self):
        self.assertEqual(msgs("t(IN := i, PT := T#1s); b := t.Q;"), [])
        self.assertTrue(any("no member Foo" in m for m in msgs("b := t.Foo;")))
        self.assertTrue(any("no input XX" in m for m in msgs("t(XX := i);")))
        self.assertTrue(any("not a declared function block" in m for m in msgs("x(IN := i);")))

    def test_profile_types(self):
        head = "PROGRAM p\nVAR a : LINT; END_VAR\n"
        self.assertEqual(check(head + "END_PROGRAM", "iec"), [])
        self.assertTrue(any("not supported" in str(i) for i in check(head + "END_PROGRAM", "siemens-s7-1200")))

    def test_syntax_error(self):
        r = check("PROGRAM p\nIF THEN\nEND_PROGRAM")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].severity, "error")

    def test_cli_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "a.st")
            open(f, "w").write("PROGRAM p\nVAR x:INT; END_VAR\ny := 1;\nEND_PROGRAM")
            self.assertEqual(main(["check", f]), 1)
            self.assertEqual(main(["check", "examples/motor.st"]), 0)


if __name__ == "__main__":
    unittest.main()
