"""M37:虛擬 PLC 直接位址共用記憶體(%MW0 與 %MX0.0 等重疊位址同步)。"""
import unittest

from plc_st.checker import check
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError
from plc_st.scenario import run_scenario
from plc_st.web import State as AppState, handle


def prog(decl, body=""):
    return f"PROGRAM P\nVAR\n{decl}\nEND_VAR\n{body}\nEND_PROGRAM\n"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class ByteOrderTest(unittest.TestCase):
    SRC = prog(" w AT %MW0 : WORD;\n b0 AT %MX0.0 : BOOL;\n b8 AT %MX1.0 : BOOL;\n lo AT %MB0 : BYTE;\n d AT %MD0 : DINT;",
               "w := 16#0102;")

    def test_iec_little_endian(self):
        p = VirtualPLC(self.SRC)
        p.scan()
        self.assertEqual((p.get("b0"), p.get("b8"), p.get("lo"), p.get("d")), (False, True, 2, 0x0102))

    def test_siemens_big_endian(self):
        p = VirtualPLC(self.SRC, profile="siemens-s7-1500")
        p.scan()
        self.assertEqual((p.get("b0"), p.get("b8"), p.get("lo"), p.get("d")), (True, False, 1, 0x01020000))

    def test_word_index_addressing(self):
        src = prog(" a AT %MW1 : WORD;\n x AT %MB2 : BYTE;\n y AT %MB1 : BYTE;", "a := 16#ABCD;")
        p = VirtualPLC(src)  # IEC:%MW1 = byte 2..3
        p.scan()
        self.assertEqual((p.get("x"), p.get("y")), (0xCD, 0))
        p = VirtualPLC(src, profile="siemens-s7-1200")  # S7:%MW1 = byte 1..2
        p.scan()
        self.assertEqual((p.get("x"), p.get("y")), (0xCD, 0xAB))


class SyncTest(unittest.TestCase):
    def test_bit_write_updates_word_and_back(self):
        p = VirtualPLC(prog(" w AT %MW0 : WORD;\n f AT %MX0.3 : BOOL;\n g AT %MX0.4 : BOOL;", "f := TRUE;"))
        p.scan()
        self.assertEqual(p.get("w"), 8)
        self.assertFalse(p.get("g"))
        p.set_input("w", 16)
        self.assertEqual((p.get("f"), p.get("g")), (False, True))

    def test_forcing_input_byte_sets_bits(self):
        src = read("examples/shared_memory.st")
        p = VirtualPLC(src)
        p.set_input("inByte", 1)
        p.scan()
        self.assertTrue(p.get("start") and p.get("running") and p.get("motor"))
        self.assertEqual(p.get("status"), 1)       # IEC:running = bit 0
        self.assertEqual(p.get("outByte"), 1)
        p.set_input("inByte", 3)                   # start + stop → alarm, stop wins
        p.scan()
        self.assertFalse(p.get("running"))
        self.assertTrue(p.get("alarm"))
        self.assertEqual(p.get("status"), 0x8000)  # IEC:%MX1.7 = bit 15
        s7 = VirtualPLC(src, profile="siemens-s7-1500")
        s7.set_input("inByte", 1)
        s7.scan()
        self.assertEqual(s7.get("status"), 0x0100)  # S7:%M0.0 = bit 8

    def test_real_dword_alias(self):
        p = VirtualPLC(prog(" r AT %MD4 : REAL;\n raw AT %MD4 : DWORD;", "r := 1.0;"))
        p.scan()
        self.assertEqual(p.get("raw"), 0x3F800000)
        p.set_input("raw", 0x40000000)
        self.assertEqual(p.get("r"), 2.0)

    def test_signed_and_wrap(self):
        p = VirtualPLC(prog(" i AT %MW0 : INT;\n u AT %MW0 : UINT;\n hb AT %MB1 : BYTE;", "i := -1;"))
        p.scan()
        self.assertEqual((p.get("u"), p.get("hb")), (0xFFFF, 0xFF))
        p.set_input("u", 0x8000)
        self.assertEqual(p.get("i"), -32768)

    def test_init_values_later_declaration_wins(self):
        p = VirtualPLC(prog(" w AT %MW0 : WORD := 16#00FF;\n b AT %MB0 : BYTE := 16#0F;"))
        self.assertEqual((p.get("w"), p.get("b")), (0x000F, 0x0F))

    def test_fb_output_and_for_loop_target_sync(self):
        p = VirtualPLC(prog(" w AT %MW0 : WORD;\n q AT %MX0.0 : BOOL;\n c AT %MB1 : BYTE;\n t : TON;\n s : BOOL := TRUE;",
                            "t(IN := s, PT := T#20ms, Q => q);\nFOR c := 1 TO 3 DO END_FOR;"))
        p.scan(4)
        self.assertTrue(p.get("q"))
        self.assertEqual(p.get("w"), 1 | (4 << 8))  # FOR 結束時 c = 4

    def test_different_areas_independent(self):
        p = VirtualPLC(prog(" a AT %MX0.0 : BOOL;\n b AT %QX0.0 : BOOL;\n w AT %MB0 : BYTE;", "a := TRUE;"))
        p.scan()
        self.assertFalse(p.get("b"))
        self.assertEqual(p.get("w"), 1)

    def test_no_overlap_plain_dict(self):
        p = VirtualPLC(prog(" a AT %MW0 : WORD;\n b AT %MW1 : WORD;", "a := 5;"))
        self.assertFalse(p.image)
        self.assertIs(type(p.vars), dict)

    def test_restart_warm_and_cold(self):
        src = prog(" w AT %MW0 : WORD;\n f AT %MX0.0 : BOOL;", "") .replace(
            "VAR\n", "VAR RETAIN\n k AT %MB1 : BYTE;\nEND_VAR\nVAR\n", 1)
        p = VirtualPLC(src)
        p.set_input("w", 0x0201)
        p.restart(warm=True)
        self.assertEqual((p.get("k"), p.get("w"), p.get("f")), (2, 0x0200, False))  # 只有 RETAIN 的 k 保留
        p.restart(warm=False)
        self.assertEqual((p.get("k"), p.get("w")), (0, 0))

    def test_unknown_name_still_rejected(self):
        with self.assertRaises(STError):
            VirtualPLC(prog(" w AT %MW0 : WORD;\n b AT %MX0.0 : BOOL;", "")).set_input("nope", 1)

    def test_scenario_uses_shared_memory(self):
        sc = {"steps": [{"set": {"inByte": 1}, "cycles": 1, "expect": {"motor": True, "status": 1}},
                        {"set": {"inByte": 2}, "cycles": 1, "expect": {"motor": False, "status": 0}}]}
        self.assertEqual(run_scenario(read("examples/shared_memory.st"), sc), [])


class CheckerTest(unittest.TestCase):
    def msgs(self, decl, profile="iec"):
        return [i.msg for i in check(prog(decl), profile) if "overlaps" in i.msg]

    def test_contained_alias_no_warning(self):
        self.assertEqual(self.msgs(" w AT %MW0 : WORD;\n b AT %MX0.0 : BOOL;\n r AT %MD4 : REAL;\n d AT %MD4 : DWORD;"), [])
        self.assertEqual(check(read("examples/shared_memory.st")), [])

    def test_partial_overlap_warns(self):
        m = self.msgs(" a AT %MW0 : WORD;\n b AT %MW1 : WORD;", "siemens-s7-1500")
        self.assertEqual(len(m), 1)
        self.assertIn("partially overlaps", m[0])
        self.assertEqual(self.msgs(" a AT %MD0 : DWORD;\n b AT %MD2 : DWORD;", "siemens-s7-1500")[0][:5], "b at ")


class WebTest(unittest.TestCase):
    def test_meta_shared_and_sim(self):
        st = AppState()
        code, j = handle("POST", "/api/sim/start", {"code": read("examples/shared_memory.st")}, st)
        self.assertEqual(code, 200)
        meta = {m["name"]: m for m in j["meta"]}
        self.assertEqual(sorted(meta["inByte"]["shared"]), ["start", "stop"])
        self.assertEqual(meta["motor"]["shared"], ["outByte"])
        code, r = handle("POST", "/api/sim/step", {"id": j["id"], "set": {"inByte": 1}}, st)
        row = dict(zip(j["columns"], r["rows"][-1]))
        self.assertEqual((row["start"], row["motor"], row["status"]), (True, True, 1))


if __name__ == "__main__":
    unittest.main()
