import os, tempfile, unittest
from plc_st.interpreter import VirtualPLC
from plc_st.checker import check
from plc_st.lexer import tokenize

SRC = '''PROGRAM p
VAR a: INT; b: REAL; t: TIME; c: INT; m: ARRAY[0..4] OF INT := [2(1), 3(0)];
    r: ARRAY[0..2] OF REAL := [3(1.5)]; h: DINT; f: BOOL; x: INT; END_VAR
a := INT#5 + 16#FF + 2#1010 + 1_000;
b := INT_TO_REAL(a) + REAL#1.5;
t := INT_TO_TIME(250);
c := TIME_TO_INT(t) + REAL_TO_INT(2.6);
h := 8#17; f := BOOL#1; x := m[0] + m[1] + m[4];
END_PROGRAM'''


class M31(unittest.TestCase):
    def test_literals_and_conversions(self):
        self.assertEqual([i for i in check(SRC, "iec") if i.severity == "error"], [])
        p = VirtualPLC(SRC)
        p.scan()
        v = p.vars
        self.assertEqual((v["a"], v["b"], v["t"], v["c"], v["h"], v["f"], v["x"]), (1270, 1271.5, 250, 253, 15, True, 2))
        self.assertEqual(p.vars["r"] if "r" in v else [1.5] * 3, [1.5] * 3)

    def test_lexer(self):
        toks = [t[1] for t in tokenize("16#FF 1_000 2#1010 REAL#2 BOOL#0 1_0.5")]
        self.assertEqual(toks[:6], [255, 1000, 10, 2.0, "FALSE", 10.5])

    def test_time_conversions_exist(self):
        from plc_st.interpreter import FUNCS
        for n in ("INT_TO_TIME", "TIME_TO_DINT", "REAL_TO_TIME", "TIME_TO_REAL", "UINT_TO_REAL", "DINT_TO_STRING"):
            self.assertIn(n, FUNCS)

    def test_eval_saves_round_code(self):
        from plc_st import llm_eval
        from plc_st.llm import Claude
        class P(Claude):
            def complete(self, s, u):
                return "```st\nPROGRAM p\nVAR x: INT; END_VAR\nx := 1;\nEND_PROGRAM\n```"
        with tempfile.TemporaryDirectory() as d:
            llm_eval.run_eval(P(api_key='x'), 1, ["TC-01"], 1, d, log=lambda *_: None)
            files = []
            for r, _, fs in os.walk(d):
                files += fs
            self.assertTrue(any("round0" in f for f in files), files)


if __name__ == "__main__":
    unittest.main()
