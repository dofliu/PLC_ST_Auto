import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError
from plc_st.export import export

SRC = """PROGRAM P
VAR
  buf : ARRAY[0..4] OF INT := [10, 20];
  flags : ARRAY[1..3] OF BOOL;
  i : INT;
  sum : INT;
END_VAR
sum := 0;
FOR i := 0 TO 4 DO
  sum := sum + buf[i];
END_FOR;
buf[2] := sum;
flags[1] := buf[0] = 10;
END_PROGRAM
"""


class ArrayTests(unittest.TestCase):
    def test_run(self):
        p = VirtualPLC(SRC)
        p.scan(1)
        self.assertEqual(p.get("sum"), 30)
        self.assertEqual(p.get("buf[2]"), 30)
        self.assertEqual(p.get("buf[4]"), 0)
        self.assertTrue(p.get("flags[1]"))
        self.assertIn("buf[0]", p.snapshot())
        self.assertIn("flags[3]", p.snapshot())

    def test_set_input_element(self):
        p = VirtualPLC(SRC)
        p.set_input("buf[0]", 5)
        p.scan(1)
        self.assertEqual(p.get("sum"), 25)

    def test_out_of_range_runtime(self):
        p = VirtualPLC("PROGRAM P\nVAR a : ARRAY[0..1] OF INT; i : INT; END_VAR\ni := 5;\na[i] := 1;\nEND_PROGRAM")
        with self.assertRaises(STError):
            p.scan(1)

    def test_checker(self):
        self.assertEqual([i for i in check(SRC) if i.severity == "error"], [])
        bad = "PROGRAM P\nVAR a : ARRAY[0..1] OF INT; x : INT; END_VAR\na[7] := 1;\nx := a;\nx[0] := 1;\nEND_PROGRAM"
        msgs = " ".join(str(i) for i in check(bad))
        self.assertIn("out of range", msgs)
        self.assertIn("without index", msgs)
        self.assertIn("not an array", msgs)

    def test_bad_bounds(self):
        with self.assertRaises(STError):
            VirtualPLC("PROGRAM P\nVAR a : ARRAY[3..1] OF INT; END_VAR\nEND_PROGRAM")

    def test_export_keeps_array(self):
        out = export(SRC, "scl")
        self.assertIn("ARRAY", out.upper())

    def test_plcopen_array_element(self):
        import xml.dom.minidom
        out = export(SRC, "plcopen")
        xml.dom.minidom.parseString(out)
        self.assertIn('<dimension lower="0" upper="4"/>', out)
        self.assertIn('<value><simpleValue value="20"/></value>', out)


if __name__ == "__main__":
    unittest.main()
