"""M39:點位表匯出依廠牌換算位址(IEC word 編號 ⇄ S7 位元組)+ Studio 5000 ALIAS 列。"""
import csv
import os
import subprocess
import sys
import unittest

from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError
from plc_st.tagexport import convert_addr, export_tags, parse_slots, tag_rows, tia_rows
from plc_st.web import State as AppState, handle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "name,type,direction,init,comment,address\n"


def logix_rows(text):
    lines = text.splitlines()
    i = lines.index("TYPE,SCOPE,NAME,DESCRIPTION,DATATYPE,SPECIFIER,ATTRIBUTES")
    return {r[2]: r for r in csv.reader(lines[i + 1:])}


class ConvertAddrTest(unittest.TestCase):
    def test_iec_to_s7(self):
        self.assertEqual(convert_addr("%QW2", "iec", "s7"), "%QW4")
        self.assertEqual(convert_addr("%MD1", "iec", "s7"), "%MD4")
        self.assertEqual(convert_addr("%ML1", "iec", "s7"), "%ML8")
        self.assertEqual(convert_addr("%IB3", "iec", "s7"), "%IB3")
        self.assertEqual(convert_addr("%IX1.3", "iec", "s7"), "%I1.3")
        self.assertEqual(convert_addr("%qw0", "iec", "s7"), "%QW0")

    def test_s7_to_iec(self):
        self.assertEqual(convert_addr("%QW4", "s7", "iec"), "%QW2")
        self.assertEqual(convert_addr("%MD8", "s7", "iec"), "%MD2")
        self.assertEqual(convert_addr("%I1.3", "s7", "iec"), "%IX1.3")
        self.assertIsNone(convert_addr("%MW1", "s7", "iec"))  # 未對齊
        self.assertIsNone(convert_addr("%MD2", "s7", "iec"))

    def test_identity_and_roundtrip(self):
        for a in ("%QW0", "%QW7", "%MD3", "%IB9", "%IX2.7"):
            self.assertEqual(convert_addr(convert_addr(a, "iec", "s7"), "s7", "iec"), a)
        self.assertEqual(convert_addr("%QW2", "s7", "s7"), "%QW2")

    def test_same_bytes_as_simulator(self):
        """換算結果必須與虛擬 PLC 的共用記憶體一致:IEC %MW1 的低位元組 = %MX2.x(=TIA 的 %MW2)。"""
        src = ("PROGRAM p VAR w AT %MW1 : WORD; b AT %MX2.0 : BOOL; END_VAR w := 1; END_PROGRAM")
        plc = VirtualPLC(src, profile="codesys")
        plc.scan()
        self.assertTrue(plc.get("b"))
        self.assertEqual(convert_addr("%MW1", "iec", "s7"), "%MW2")

    def test_errors(self):
        with self.assertRaises(STError):
            convert_addr("%QW2", "iec", "abc")
        with self.assertRaises(STError):
            convert_addr("QW2", "iec", "s7")


class TiaAddressingTest(unittest.TestCase):
    CSV = H + "a,INT,OUT,,,%QW1\nb,DINT,VAR,,,%MD1\nc,BOOL,IN,,,%IX0.0\nd,INT,OUT,,,\ne,INT,VAR,,,\n"

    def test_iec_default_converts_and_warns(self):
        tags, _, warn = tia_rows(tag_rows(self.CSV))
        got = {r[0]: r[3] for r in tags}
        self.assertEqual(got["a"], "%QW2")
        self.assertEqual(got["b"], "%MD4")
        self.assertEqual(got["c"], "%I0.0")
        w = "\n".join(warn)
        self.assertIn("a: %QW1", w)
        self.assertIn("→ %QW2", w)
        self.assertNotIn("c: %IX0.0", w)  # 位元位址兩者相同,不提醒

    def test_alloc_uses_converted_bytes(self):
        """IEC %QW1 佔位元組 2..3;自動配置不可再用到 2..3(M38 會誤配 %QW2)。"""
        tags, _, _ = tia_rows(tag_rows(self.CSV))
        got = {r[0]: r[3] for r in tags}
        self.assertEqual(got["d"], "%QW0")
        self.assertEqual(got["e"], "%MW0")  # %MD1(IEC)= 位元組 4..7,0..1 仍空

    def test_s7_source_kept(self):
        tags, _, warn = tia_rows(tag_rows(self.CSV), addressing="s7")
        got = {r[0]: r[3] for r in tags}
        self.assertEqual(got["a"], "%QW1")
        self.assertEqual(got["b"], "%MD1")
        self.assertFalse(any("依 IEC 定址" in w for w in warn))
        self.assertEqual(got["d"], "%QW4")  # S7 %QW1 = 位元組 1..2 → 下一個偶數 4
        self.assertEqual(got["e"], "%MW6")  # %MD1 = 位元組 1..4 → 6


class GvlAddressingTest(unittest.TestCase):
    def test_iec_kept(self):
        text, _, warn = export_tags(H + "a,INT,OUT,,,%QW1\n", "codesys")
        self.assertIn("a AT %QW1 : INT;", text)
        self.assertEqual(warn, [])

    def test_s7_converted(self):
        text, _, warn = export_tags(H + "a,INT,OUT,,,%QW4\nb,BOOL,IN,,,%I0.3\nc,WORD,VAR,,,%MW3\n", "codesys", "s7")
        self.assertIn("a AT %QW2 : INT;", text)
        self.assertIn("b AT %IX0.3 : BOOL;", text)
        self.assertIn("c AT %MW3 : WORD;", text)  # 未對齊:保留原樣
        w = "\n".join(warn)
        self.assertIn("a: S7 位元組位址 %QW4 → CODESYS %QW2", w)
        self.assertIn("c: %MW3 起始位元組不是型別大小的倍數", w)


class LogixAliasTest(unittest.TestCase):
    CSV = (H + "start,BOOL,IN,,啟動,%IX0.0\nlim,BOOL,IN,1,,%IX1.2\nmotor,BOOL,OUT,,,%QX0.5\n"
           "far,BOOL,IN,,,%IX4.0\nspeed,INT,OUT,,,%QW2\nflag,BOOL,VAR,,,%MX0.0\nplain,INT,VAR,,,\n")

    def test_no_slots_unchanged(self):
        text, _, _ = export_tags(self.CSV, "logix")
        self.assertNotIn("ALIAS", text)
        self.assertEqual(logix_rows(text)["start"][0], "TAG")

    def test_alias_rows(self):
        text, _, warn = export_tags(self.CSV, "logix", logix_slots="I=1,Q=2")
        rows = logix_rows(text)
        self.assertEqual(rows["start"], ["ALIAS", "", "start", "啟動 [IEC %IX0.0]", "", "Local:1:I.Data.0",
                                         "(RADIX := Decimal, ExternalAccess := Read/Write)"])
        self.assertEqual(rows["lim"][5], "Local:1:I.Data.10")
        self.assertEqual(rows["motor"][5], "Local:2:O.Data.5")
        self.assertEqual(rows["far"][0], "TAG")  # 第 32 點超出單一模組
        self.assertEqual(rows["speed"][0], "TAG")
        self.assertEqual(rows["flag"][0], "TAG")
        self.assertEqual(rows["plain"][0], "TAG")
        w = "\n".join(warn)
        self.assertIn("far: %IX4.0 換算為第 32 點", w)
        self.assertIn("speed: 只為 BOOL 位元位址建立 Alias", w)
        self.assertIn("flag: Logix 沒有 %M 記憶區", w)
        self.assertIn("lim: Alias 標籤沒有初值", w)

    def test_only_input_slot(self):
        text, _, _ = export_tags(self.CSV, "logix", logix_slots={"I": 3})
        rows = logix_rows(text)
        self.assertEqual(rows["start"][5], "Local:3:I.Data.0")
        self.assertEqual(rows["motor"][0], "TAG")

    def test_parse_slots(self):
        self.assertEqual(parse_slots(" i = 1 , Q=2 "), {"I": 1, "Q": 2})
        self.assertEqual(parse_slots(""), {})
        for bad in ("M=1", "I=x", "I=-1"):
            with self.assertRaises(STError):
                parse_slots(bad)


class InterfaceTest(unittest.TestCase):
    def test_api(self):
        st = AppState()
        code, j = handle("POST", "/api/tags/export", {"csv": H + "a,INT,OUT,,,%QW4\n", "format": "codesys", "addressing": "s7"}, st)
        self.assertEqual(code, 200)
        self.assertIn("a AT %QW2", j["text"])
        code, j = handle("POST", "/api/tags/export", {"csv": H + "a,BOOL,IN,,,%IX0.1\n", "format": "logix", "logix_slots": "I=4"}, st)
        self.assertIn('"Local:4:I.Data.1"', j["text"])
        code, j = handle("POST", "/api/tags/export", {"csv": H + "a,BOOL,IN,,,\n", "format": "tia", "addressing": "x"}, st)
        self.assertEqual(code, 400)
        self.assertIn("unknown addressing", j["error"])

    def test_cli(self):
        p = os.path.join(ROOT, "examples", "points_addr.csv")
        r = subprocess.run([sys.executable, "-m", "plc_st", "tags", p, "--format", "logix", "--logix-slots", "I=1,Q=2"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('ALIAS,,motor,"馬達接觸器 [IEC %QX0.0]","","Local:2:O.Data.0"', r.stdout)
        r = subprocess.run([sys.executable, "-m", "plc_st", "tags", p, "--format", "codesys", "--addressing", "s7"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertIn("speed AT %QW1 : INT;", r.stdout)
        self.assertIn("S7 位元組位址 %QW2 → CODESYS %QW1", r.stderr)


if __name__ == "__main__":
    unittest.main()
