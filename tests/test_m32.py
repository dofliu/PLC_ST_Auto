import unittest
from plc_st.interpreter import VirtualPLC, rnd
from plc_st.checker import check
from plc_st.lexer import STError, tokenize
from plc_st import web


def run(body, decl="x:INT;"):
    p = VirtualPLC(f"PROGRAM p VAR {decl} END_VAR {body} END_PROGRAM")
    p.scan(1)
    return p


class Exit(unittest.TestCase):
    def test_checker_error_outside_loop(self):
        iss = check("PROGRAM p VAR x:INT; END_VAR EXIT; END_PROGRAM")
        self.assertTrue(any(i.severity == "error" and "EXIT" in i.msg for i in iss))

    def test_checker_ok_in_loops_and_if(self):
        for body in ("WHILE x<3 DO IF x=1 THEN EXIT; END_IF x:=x+1; END_WHILE",
                     "FOR x:=0 TO 3 DO EXIT; END_FOR",
                     "REPEAT EXIT; UNTIL TRUE END_REPEAT"):
            iss = check(f"PROGRAM p VAR x:INT; END_VAR {body} END_PROGRAM")
            self.assertFalse([i for i in iss if "EXIT" in i.msg], body)

    def test_interpreter_raises(self):
        with self.assertRaises(STError):
            run("EXIT;")


class Escapes(unittest.TestCase):
    def test_tokens(self):
        t = [x for x in tokenize("'a$'b$$c$Nd$T$41'") if x[0] == "str"][0][1]
        self.assertEqual(t, "a'b$c\nd\tA")

    def test_bad_escape(self):
        with self.assertRaises(STError):
            tokenize("'$Z'")

    def test_len(self):
        p = run("x:=LEN(s);", "x:INT; s:STRING:='it$'s';")
        self.assertEqual(p.vars["x"], 4)


class Rounding(unittest.TestCase):
    def test_half_away_from_zero(self):
        self.assertEqual([rnd(v) for v in (0.5, 1.5, 2.5, -0.5, -2.5, 2.4)], [1, 2, 3, -1, -3, 2])

    def test_implicit_equals_explicit(self):
        p = run("x:=r; y:=REAL_TO_INT(r);", "x:INT; y:INT; r:REAL:=2.5;")
        self.assertEqual((p.vars["x"], p.vars["y"]), (3, 3))

    def test_cycles_message(self):
        with self.assertRaises(STError) as c:
            web._run({"code": "PROGRAM p END_PROGRAM", "cycles": "abc"})
        self.assertIn("integer", str(c.exception))


if __name__ == "__main__":
    unittest.main()
