"""STRUCT → Rockwell L5X UDT(DataType)匯出。"""
import unittest
import xml.etree.ElementTree as ET

from plc_st.export import export
from plc_st.lexer import STError

SRC = """TYPE Pt : STRUCT x : INT; ok : BOOL; flag : BOOL; v : ARRAY[0..3] OF REAL; END_STRUCT END_TYPE
TYPE Seg : STRUCT a : Pt; n : DINT; END_STRUCT END_TYPE
PROGRAM P VAR arr : ARRAY[0..2] OF Pt; s : Seg; END_VAR arr[0].x := 1; END_PROGRAM"""


class L5xStruct(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(export(SRC, "l5x"))

    def test_well_formed_and_datatypes_before_programs(self):
        ctrl = self.root.find("Controller")
        self.assertEqual([c.tag for c in ctrl], ["DataTypes", "Programs"])
        names = [d.get("Name") for d in ctrl.find("DataTypes")]
        self.assertEqual(names, ["Pt", "Seg"])

    def test_bool_packed_into_hidden_host(self):
        pt = self.root.find(".//DataType[@Name='Pt']")
        host = pt.find("Members/Member[@Hidden='true']")
        self.assertEqual(host.get("DataType"), "SINT")
        bits = {m.get("Name"): m for m in pt.findall("Members/Member[@DataType='BIT']")}
        self.assertEqual(bits["ok"].get("BitNumber"), "0")
        self.assertEqual(bits["flag"].get("BitNumber"), "1")
        self.assertEqual(bits["ok"].get("Target"), host.get("Name"))

    def test_array_member_and_nested_type(self):
        v = self.root.find(".//DataType[@Name='Pt']/Members/Member[@Name='v']")
        self.assertEqual((v.get("DataType"), v.get("Dimension")), ("REAL", "4"))
        a = self.root.find(".//DataType[@Name='Seg']/Members/Member[@Name='a']")
        self.assertEqual(a.get("DataType"), "Pt")

    def test_tag_array_dimensions(self):
        t = self.root.find(".//Tag[@Name='arr']")
        self.assertEqual((t.get("DataType"), t.get("Dimensions")), ("Pt", "3"))

    def test_nonzero_lower_bound_rejected(self):
        with self.assertRaises(STError):
            export("TYPE A : STRUCT v : ARRAY[1..3] OF INT; END_STRUCT END_TYPE PROGRAM P END_PROGRAM", "l5x")

    def test_multidim_member_rejected(self):
        with self.assertRaises(STError):
            export("TYPE A : STRUCT v : ARRAY[0..1, 0..1] OF INT; END_STRUCT END_TYPE PROGRAM P END_PROGRAM", "l5x")

    def test_no_type_has_no_datatypes_and_function_rejected(self):
        out = export("PROGRAM P VAR x : INT; END_VAR x := 1; END_PROGRAM", "l5x")
        self.assertNotIn("<DataTypes>", out)
        with self.assertRaises(STError):
            export("FUNCTION F : INT END_FUNCTION PROGRAM P END_PROGRAM", "l5x")


if __name__ == "__main__":
    unittest.main()
