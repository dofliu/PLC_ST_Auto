import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

SRC = open("examples/struct_array.st").read()


def errs(src):
    return [str(i) for i in check(src, "iec") if i.severity == "error"]


class StructArrayTests(unittest.TestCase):
    def test_run(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        self.assertEqual(p.get("ms[1].speed"), 11)
        self.assertEqual(p.get("ms[3].speed"), 13)
        self.assertFalse(p.get("ms[1].run"))
        self.assertTrue(p.get("ms[2].run"))
        self.assertEqual(p.get("total"), 36)
        p.scan(1)
        self.assertEqual(p.get("ms[2].speed"), 14)
        self.assertEqual(p.get("ms[1].speed"), 12)  # elements independent

    def test_snapshot_names(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        self.assertEqual(p.snapshot()["ms[2].speed"], 12)

    def test_set_input(self):
        p = VirtualPLC(SRC)
        p.set_input("ms[2].speed", 100)
        self.assertEqual(p.get("ms[2].speed"), 100)

    def test_out_of_range(self):
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("TO 3", "TO 4")).scan(1)

    def test_checker(self):
        self.assertEqual(errs(SRC), [])
        self.assertIn("no field", "\n".join(errs(SRC.replace("ms[i].run :=", "ms[i].bogus :="))))

    def test_init_unsupported(self):
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("OF Motor;", "OF Motor := (speed := 1);"))


if __name__ == "__main__":
    unittest.main()
