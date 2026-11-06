import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

SRC = open("examples/struct_elem.st").read()


def errs(src):
    return [str(i) for i in check(src, "iec") if i.severity == "error"]


class StructElemTests(unittest.TestCase):
    def test_initialiser(self):
        p = VirtualPLC(SRC.replace("tmp := ms[1];", "").replace("ms[3] := ms[2];", "").replace("ms[2] := tmp;", ""))
        p.scan(1)
        self.assertEqual(p.get("ms[1].speed"), 100)
        self.assertTrue(p.get("ms[1].run"))
        self.assertEqual(p.get("ms[2].speed"), 200)
        self.assertFalse(p.get("ms[2].run"))
        self.assertEqual(p.get("ms[3].speed"), 10)  # default

    def test_element_assign(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        self.assertEqual(p.get("ms[3].speed"), 200)  # copy of old ms[2]
        self.assertEqual(p.get("ms[2].speed"), 100)  # from tmp
        self.assertTrue(p.get("ms[2].run"))
        self.assertEqual(p.get("best"), 200)
        p.set_input("ms[1].speed", 5)  # copies are independent
        p.scan(1)
        self.assertEqual(p.get("ms[2].speed"), 5)  # re-copied from ms[1]

    def test_independent_after_copy(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        p.vars["ms.speed"][2] = 7
        self.assertEqual(p.get("ms[3].speed"), 7)
        self.assertEqual(p.get("ms[2].speed"), 100)

    def test_errors(self):
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("(speed := 200)", "(bogus := 1)"))
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("[(speed := 100, run := TRUE), (speed := 200)]", "[(speed := 1),(speed := 2),(speed := 3),(speed := 4)]"))
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("(speed := 200)", "5"))
        p = VirtualPLC(SRC.replace("ms[3] := ms[2];", "ms[4] := ms[2];"))
        with self.assertRaises(STError):
            p.scan(1)

    def test_checker(self):
        self.assertEqual(errs(SRC), [])
        bad = SRC.replace("tmp := ms[1];", "tmp := best;")
        self.assertTrue(any("STRUCT" in e for e in errs(bad)))
        bad2 = SRC.replace("best := ms[3].speed;", "ms[1] := 3;")
        self.assertTrue(any("STRUCT" in e for e in errs(bad2)))


if __name__ == "__main__":
    unittest.main()
