import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from plc_st import STError
from plc_st.cli import main
from plc_st.scenario import run_scenario

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "examples/motor.st").read_text(encoding="utf-8")
SPEC = ROOT / "examples/motor_scenario.json"


class TestScenario(unittest.TestCase):
    def test_example_passes(self):
        self.assertEqual(run_scenario(SRC, SPEC.read_text(encoding="utf-8")), [])

    def test_failure_reported(self):
        spec = {"steps": [{"set": {"start": True}, "expect": {"motor": False}}]}
        f = run_scenario(SRC, spec)
        self.assertEqual(f, [{"step": "#1", "var": "motor", "expected": False, "actual": True}])

    def test_bool_not_equal_int(self):
        spec = {"steps": [{"set": {"start": True}, "expect": {"motor": 1}}]}
        self.assertEqual(len(run_scenario(SRC, spec)), 1)

    def test_bad_specs(self):
        for bad in ("{", "[]", {"steps": [{"expect": {"nope": 1}}]},
                    {"steps": [{"cycles": -1}]}, {"scan_ms": 0, "steps": []}):
            with self.assertRaises(STError):
                run_scenario(SRC, bad)

    def test_cli(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["test", str(ROOT / "examples/motor.st"), str(SPEC)])
        self.assertEqual((rc, buf.getvalue().strip()), (0, "PASS"))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text(json.dumps({"steps": [{"expect": {"motor": True}}]}))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["test", str(ROOT / "examples/motor.st"), str(p)])
            self.assertEqual(rc, 1)
            self.assertIn("FAIL", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
