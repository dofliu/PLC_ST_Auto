import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

SRC = open("examples/struct_copy.st").read()


def errs(src):
    return [str(i) for i in check(src, "iec") if i.severity == "error"]


class StructCopyTests(unittest.TestCase):
    def test_copy_and_independence(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        self.assertEqual(p.get("b.speed"), 50)
        self.assertTrue(p.get("b.run"))
        self.assertEqual(p.get("l.m.speed"), 50)
        self.assertEqual(p.get("a.speed"), 51)  # copy, not alias
        p.scan(1)
        self.assertEqual(p.get("b.speed"), 51)
        self.assertEqual(p.get("l.count"), 2)

    def test_clean_check(self):
        self.assertEqual(errs(SRC), [])

    def test_type_mismatch(self):
        self.assertIn("same type", "\n".join(errs(SRC.replace("b := a;", "b := l;"))))
        self.assertIn("same type", "\n".join(errs(SRC.replace("b := a;", "b := 1;"))))

    def test_runtime_mismatch(self):
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("b := a;", "b := l;")).scan(1)


if __name__ == "__main__":
    unittest.main()
