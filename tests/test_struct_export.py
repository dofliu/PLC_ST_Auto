"""STRUCT → PLCopen dataType 匯出(含 ARRAY / 巢狀 / 初始值)。"""
import os
import unittest
import xml.etree.ElementTree as ET

from plc_st.export import export, to_plcopen, validate_plcopen
from plc_st.lexer import STError

NS = {"p": "http://www.plcopen.org/xml/tc6_0201"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC = """TYPE Pt : STRUCT x : INT := 1; y : INT; END_STRUCT END_TYPE
TYPE Line : STRUCT a : Pt := (x := 5, y := 6); b : Pt; tags : ARRAY[0..2] OF INT := [1,2,3]; END_STRUCT END_TYPE
PROGRAM P
VAR l : Line; ps : ARRAY[1..2] OF Pt := [(x := 9), (y := 8)]; END_VAR
l.a.x := 2;
END_PROGRAM
"""


class StructExport(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(to_plcopen(SRC))

    def test_datatypes_listed(self):
        names = [d.get("name") for d in self.root.findall(".//p:dataTypes/p:dataType", NS)]
        self.assertEqual(names, ["Pt", "Line"])

    def test_nested_and_array_fields(self):
        line = self.root.findall(".//p:dataType", NS)[1]
        fields = {v.get("name"): v for v in line.findall(".//p:struct/p:variable", NS)}
        self.assertEqual(fields["a"].find("p:type/p:derived", NS).get("name"), "Pt")
        self.assertIsNotNone(fields["tags"].find("p:type/p:array/p:dimension", NS))
        self.assertEqual(len(fields["tags"].findall(".//p:arrayValue/p:value", NS)), 3)
        sv = fields["a"].find("p:initialValue/p:structValue", NS)
        self.assertEqual([v.get("member") for v in sv.findall("p:value", NS)], ["x", "y"])

    def test_array_of_struct_init(self):
        ps = [v for v in self.root.findall(".//p:pou//p:variable", NS) if v.get("name") == "ps"][0]
        self.assertEqual(len(ps.findall("p:initialValue/p:arrayValue/p:value/p:structValue", NS)), 2)

    def test_other_formats_still_reject(self):
        for fmt in ("l5x", "gxworks", "sysmac"):
            with self.assertRaises(STError):
                export(SRC, fmt)

    def test_user_function_still_rejected_for_plcopen(self):
        with self.assertRaises(STError):
            export("FUNCTION F : INT END_FUNCTION\nPROGRAM P\nEND_PROGRAM", "plcopen")

    def test_schema_valid(self):
        try:
            import lxml  # noqa: F401
        except ImportError:
            self.skipTest("lxml not installed")
        self.assertEqual(validate_plcopen(to_plcopen(SRC)), [])


if __name__ == "__main__":
    unittest.main()
