import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from plc_st.cli import main
from plc_st.tags import tags_to_var_blocks
from plc_st import VirtualPLC, STError

ROOT = Path(__file__).resolve().parent.parent


class TestCLI(unittest.TestCase):
    def test_run_trace(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["run", str(ROOT / "examples/motor.st"), "--cycles", "3",
                       "--at", "1:start=true"])
        self.assertEqual(rc, 0)
        lines = buf.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 4)
        hdr = lines[0].split(",")
        m = hdr.index("motor")
        self.assertEqual(lines[1].split(",")[m], "False")
        self.assertEqual(lines[2].split(",")[m], "True")

    def test_trace_file_and_bad_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "t.csv"
            self.assertEqual(main(["run", str(ROOT / "examples/motor.st"), "--cycles", "2",
                                   "--trace", str(out)]), 0)
            self.assertTrue(out.read_text().startswith("cycle,time_ms"))
        self.assertEqual(main(["run", "/nonexistent.st"]), 1)

    def test_tags_generate_valid_st(self):
        decl = tags_to_var_blocks((ROOT / "examples/points.csv").read_text(encoding="utf-8"))
        self.assertIn("VAR_INPUT", decl)
        self.assertIn("cnt : INT := 0;", decl)
        plc = VirtualPLC(f"PROGRAM P\n{decl}\nIF start THEN motor := TRUE; END_IF;\nEND_PROGRAM")
        plc.set_input("start", True)
        plc.scan()
        self.assertTrue(plc.get("motor"))

    def test_bad_direction(self):
        with self.assertRaises(STError):
            tags_to_var_blocks("name,type,direction\nx,BOOL,SIDEWAYS\n")
