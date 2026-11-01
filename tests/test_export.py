import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from plc_st.export import export, split_program, to_plcopen
from plc_st import STError

SRC = (Path(__file__).resolve().parent.parent / "examples/motor.st").read_text(encoding="utf-8")
NS = {"p": "http://www.plcopen.org/xml/tc6_0201"}


class TestExport(unittest.TestCase):
    def test_split(self):
        name, blocks, decl, body = split_program(SRC)
        self.assertEqual(name, "Motor")
        self.assertEqual([b[0] for b in blocks], ["VAR_INPUT", "VAR_OUTPUT", "VAR"])
        self.assertIn(("t", "TON", None), blocks[2][1])
        self.assertTrue(body.startswith("IF start"))

    def test_plcopen_wellformed(self):
        root = ET.fromstring(to_plcopen(SRC))
        pou = root.find(".//p:pou", NS)
        self.assertEqual(pou.get("name"), "Motor")
        self.assertEqual(len(root.findall(".//p:inputVars/p:variable", NS)), 2)
        self.assertIsNotNone(root.find(".//p:variable[@name='t']/p:type/p:derived[@name='TON']", NS))
        self.assertIn("t.Q", "".join(root.find(".//{http://www.w3.org/1999/xhtml}xhtml").itertext()))

    def test_xml_escaping(self):
        src = "PROGRAM P\nVAR a : INT := 1; END_VAR\nIF a < 2 AND a > 0 THEN a := 3; END_IF;\nEND_PROGRAM"
        ET.fromstring(to_plcopen(src))

    def test_scl_and_errors(self):
        scl = export(SRC, "scl")
        self.assertTrue(scl.startswith('ORGANIZATION_BLOCK "Motor"'))
        self.assertIn("BEGIN", scl)
        with self.assertRaises(STError):
            export(SRC, "nope")
        with self.assertRaises(STError):
            export("no program", "plcopen")


class TestL5X(unittest.TestCase):
    def test_l5x(self):
        from plc_st.export import to_l5x
        root = ET.fromstring(to_l5x(SRC))
        self.assertEqual(root.get("TargetName"), "Motor")
        tags = {t.get("Name"): t for t in root.iter("Tag")}
        self.assertEqual(tags["t"].get("DataType"), "TIMER")
        self.assertEqual(tags["start"].get("Usage"), "Input")
        lines = [l.text for l in root.iter("Line")]
        self.assertTrue(lines[0].startswith("IF start"))
        self.assertEqual(root.find(".//Routine").get("Type"), "ST")

    def test_cdata_terminator(self):
        from plc_st.export import to_l5x
        src = "PROGRAM P\nVAR a : INT; END_VAR\n(* ]]> *) a := 1;\nEND_PROGRAM"
        ET.fromstring(to_l5x(src))
