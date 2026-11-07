"""STRUCT → Siemens SCL UDT 匯出。"""
import os
import unittest

from plc_st.export import export
from plc_st.lexer import STError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SclStruct(unittest.TestCase):
    def setUp(self):
        self.scl = export(open(os.path.join(ROOT, "examples", "struct_export.st")).read(), "scl")

    def test_udt_emitted_before_ob(self):
        self.assertIn('TYPE "Motor"', self.scl)
        self.assertLess(self.scl.index("END_TYPE"), self.scl.index("ORGANIZATION_BLOCK"))
        self.assertIn("speed : INT := 10;", self.scl)

    def test_type_references_quoted(self):
        self.assertIn('tmp : "Motor";', self.scl)
        self.assertIn('ARRAY[1..3] OF "Motor"', self.scl)

    def test_nested_struct_reference(self):
        src = ("TYPE A : STRUCT x : INT; END_STRUCT END_TYPE\n"
               "TYPE B : STRUCT a : A; END_STRUCT END_TYPE\n"
               "PROGRAM P VAR b : B; END_VAR b.a.x := 1; END_PROGRAM")
        out = export(src, "scl")
        self.assertIn('a : "A";', out)
        self.assertEqual(out.count("END_TYPE"), 2)

    def test_no_type_unchanged(self):
        out = export("PROGRAM P VAR x : INT; END_VAR x := 1; END_PROGRAM", "scl")
        self.assertTrue(out.startswith("ORGANIZATION_BLOCK"))

    def test_function_pou_still_rejected(self):
        with self.assertRaises(STError):
            export("FUNCTION F : INT END_FUNCTION PROGRAM P END_PROGRAM", "scl")


if __name__ == "__main__":
    unittest.main()
