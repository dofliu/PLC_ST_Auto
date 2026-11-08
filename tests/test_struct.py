import unittest

from plc_st.checker import check
from plc_st.export import export
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError

SRC = open("examples/struct.st").read()


def errs(src, profile="iec"):
    return [str(i) for i in check(src, profile) if i.severity == "error"]


class StructTests(unittest.TestCase):
    def test_run_nested_and_init(self):
        p = VirtualPLC(SRC)
        self.assertEqual(p.get("a.speed"), 50)
        self.assertEqual(p.get("l.m.speed"), 7)
        self.assertEqual(p.get("l.m.run"), False)
        p.scan(2)
        self.assertEqual(p.get("l.m.speed"), 9)
        self.assertEqual(p.get("l.count"), 103)
        self.assertTrue(p.get("a.run"))
        self.assertIn("l.m.speed", p.snapshot())

    def test_default_field_init_and_instances_independent(self):
        p = VirtualPLC(SRC.replace("a : Motor := (speed := 50);", "a : Motor;"))
        self.assertEqual(p.get("a.speed"), 10)
        self.assertEqual(p.get("l.m.speed"), 7)

    def test_set_input_field(self):
        p = VirtualPLC(SRC)
        p.set_input("a.speed", 5)
        p.scan(1)
        self.assertFalse(p.get("a.run"))

    def test_clean_check(self):
        self.assertEqual(errs(SRC), [])

    def test_checker_errors(self):
        bad = SRC.replace("a.run := a.speed > 20;", "a.nope := 1; a.speed := TRUE; a := 1;")
        e = "\n".join(errs(bad))
        self.assertIn("no field nope", e)
        self.assertIn("type mismatch", e)
        self.assertIn("same type", e)

    def test_bad_init_field(self):
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("(speed := 50)", "(bogus := 1)"))

    def test_struct_without_member(self):
        with self.assertRaises(STError):
            VirtualPLC(SRC.replace("a.run := a.speed > 20;", "a.speed := a;")).scan(1)

    def test_profile_type_limit(self):
        src = SRC.replace("count : DINT", "count : LINT")
        self.assertEqual(errs(src), [])
        self.assertTrue(any("LINT" in e for e in errs(src, "mitsubishi")))

    def test_non_st_export_rejected(self):
        with self.assertRaises(STError):
            export(SRC, "gxworks")
        self.assertIn("TYPE", export(SRC, "scl"))
        self.assertIn("<struct>", export(SRC, "plcopen"))
        self.assertIn("STRUCT", export(SRC, "st"))


if __name__ == "__main__":
    unittest.main()
