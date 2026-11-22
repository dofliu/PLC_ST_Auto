"""M37 審查回歸測試:
1. 同位址的 REAL 必須讀出相同精度(寫入者自己也依 32 位元捨入)
2. 與陣列重疊的直接位址必須警告(陣列依元素數計算範圍;虛擬 PLC 不同步陣列元素)"""
import struct
import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.scenario import run_scenario

F32 = struct.unpack("<f", struct.pack("<f", 0.1))[0]  # 0.10000000149011612


def prog(decl, body=""):
    return f"PROGRAM P\nVAR\n{decl}\nEND_VAR\n{body}\nEND_PROGRAM\n"


def warns(src, profile="iec"):
    return [i.msg for i in check(src, profile) if i.severity == "warning" and "overlap" in i.msg]


class RealPrecisionTest(unittest.TestCase):
    def test_two_reals_same_address_identical(self):
        p = VirtualPLC(prog(" r1 AT %MD0 : REAL;\n r2 AT %MD0 : REAL;", "r1 := 0.1;"))
        p.scan(1)
        self.assertEqual(p.get("r1"), p.get("r2"))
        self.assertEqual(p.get("r1"), F32)

    def test_writer_rounded_for_either_side(self):
        p = VirtualPLC(prog(" r1 AT %MD0 : REAL;\n r2 AT %MD0 : REAL;", "r2 := 1.0 / 3.0;"))
        p.scan(1)
        self.assertEqual(p.get("r1"), p.get("r2"))

    def test_real_dword_alias_roundtrip(self):
        p = VirtualPLC(prog(" r AT %MD0 : REAL;\n d AT %MD0 : DWORD;", "r := 0.1;"))
        p.scan(1)
        self.assertEqual(p.get("d"), 0x3DCCCCCD)
        self.assertEqual(p.get("r"), F32)

    def test_siemens_big_endian_same_value(self):
        p = VirtualPLC(prog(" r1 AT %MD4 : REAL;\n r2 AT %MD4 : REAL;", "r1 := 0.1;"), profile="siemens-s7-1500")
        p.scan(1)
        self.assertEqual(p.get("r1"), p.get("r2"))

    def test_scenario_compares_equal(self):
        src = prog(" r1 AT %MD0 : REAL;\n r2 AT %MD0 : REAL;\n same : BOOL;", "r1 := 0.1;\nsame := r1 = r2;")
        self.assertEqual(run_scenario(src, {"steps": [{"cycles": 1, "expect": {"same": True}}]}), [])

    def test_unshared_real_unchanged(self):
        p = VirtualPLC(prog(" r AT %MD0 : REAL;\n x : REAL;", "r := 0.1; x := 0.1;"))
        p.scan(1)
        self.assertEqual(p.get("x"), 0.1)  # 沒有重疊的變數行為不變


class ArrayOverlapTest(unittest.TestCase):
    def test_scalar_inside_array_warns(self):
        w = warns(prog(" arr AT %MW0 : ARRAY[0..3] OF WORD;\n x AT %MW2 : WORD;"))
        self.assertEqual(len(w), 1, w)
        self.assertIn("x at %MW2 overlaps arr at %MW0", w[0])
        self.assertIn("NOT kept in sync", w[0])

    def test_array_declared_after_scalar_warns(self):
        w = warns(prog(" x AT %MX3.0 : BOOL;\n arr AT %MB0 : ARRAY[1..8] OF BYTE;"))
        self.assertEqual(len(w), 1, w)
        self.assertIn("array arr is NOT kept in sync", w[0])

    def test_two_arrays_overlap_warns(self):
        self.assertEqual(len(warns(prog(" a AT %MW0 : ARRAY[0..3] OF WORD;\n b AT %MW3 : ARRAY[0..1] OF WORD;"))), 1)

    def test_bounds_from_constant(self):
        src = "PROGRAM P\nVAR CONSTANT\n N : INT := 4;\nEND_VAR\nVAR\n arr AT %MW0 : ARRAY[1..N] OF WORD;\n x AT %MW3 : WORD;\nEND_VAR\nEND_PROGRAM\n"
        self.assertEqual(len(warns(src)), 1)

    def test_adjacent_no_warning(self):
        self.assertEqual(warns(prog(" arr AT %MW0 : ARRAY[0..3] OF WORD;\n x AT %MW4 : WORD;")), [])

    def test_siemens_byte_addressing(self):
        src = prog(" arr AT %MW0 : ARRAY[0..1] OF WORD;\n x AT %MW3 : WORD;\n y AT %MW6 : WORD;")
        self.assertEqual(warns(src), [])  # IEC:arr 佔 word 0..1,x=word 3
        w = warns(src, "siemens-s7-1500")  # S7:arr 佔 byte 0..3,x 佔 byte 3..4 重疊,y 佔 6..7 不重疊
        self.assertEqual(len(w), 1, w)
        self.assertIn("x at %MW3", w[0])

    def test_scalar_overlaps_still_ok(self):
        self.assertEqual(warns(prog(" w AT %MW0 : WORD;\n b AT %MX0.3 : BOOL;")), [])

    def test_simulator_does_not_sync_array(self):
        """警告所描述的行為:陣列元素與重疊純量在虛擬 PLC 中互不影響。"""
        p = VirtualPLC(prog(" arr AT %MW0 : ARRAY[0..3] OF WORD;\n x AT %MW2 : WORD;", "arr[2] := 16#1234;"))
        p.scan(1)
        self.assertEqual((p.get("arr[2]"), p.get("x")), (0x1234, 0))


if __name__ == "__main__":
    unittest.main()
