"""PLCopen XML 匯出以官方 TC6 v2.01 XSD 驗證(需 lxml;缺少時略過)。"""
import glob
import os
import subprocess
import sys
import unittest

from plc_st.export import to_plcopen, validate_plcopen

try:
    import lxml  # noqa: F401
    HAVE_LXML = True
except ImportError:
    HAVE_LXML = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALL_KINDS = """PROGRAM Kinds
VAR_INPUT start : BOOL; sp : REAL := 1.5; END_VAR
VAR_OUTPUT motor : BOOL; cv : INT; END_VAR
VAR_IN_OUT shared : DINT; END_VAR
VAR
  t1 : TON; c1 : CTU;
  buf : ARRAY[0..4] OF INT := [10, 20, 30];
  neg : ARRAY[-2..2] OF REAL := [0.5, -1.0];
  flags : ARRAY[1..3] OF BOOL;
  msg : STRING := 'a<b&c';
  dt : TIME := T#500ms;
END_VAR
t1(IN := start, PT := dt);
motor := t1.Q AND buf[0] < 20;
END_PROGRAM
"""


@unittest.skipUnless(HAVE_LXML, "lxml not installed")
class PlcopenSchema(unittest.TestCase):
    def assertValid(self, src):
        errs = validate_plcopen(to_plcopen(src))
        self.assertEqual(errs, [], "\n".join(errs))

    def test_all_variable_kinds(self):
        self.assertValid(ALL_KINDS)

    def test_array_initial_value_wrapped(self):
        xml = to_plcopen(ALL_KINDS)
        self.assertIn("<initialValue><arrayValue><value><simpleValue value=\"10\"/></value>", xml)
        self.assertNotIn("<initialValue><value>", xml)

    def test_examples(self):
        files = glob.glob(os.path.join(ROOT, "examples", "*.st"))
        self.assertTrue(files)
        for f in files:
            with self.subTest(f=f), open(f, encoding="utf-8") as fh:
                self.assertValid(fh.read())

    def test_invalid_detected(self):
        bad = to_plcopen(ALL_KINDS).replace("<arrayValue>", "").replace("</arrayValue>", "")
        self.assertTrue(validate_plcopen(bad))

    def test_cli_validate(self):
        r = subprocess.run([sys.executable, "-m", "plc_st", "export",
                            os.path.join(ROOT, "examples", "motor.st"), "--validate", "-o", os.devnull],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("schema: OK", r.stderr)


if __name__ == "__main__":
    unittest.main()
