"""M38:點位表 → 各廠牌標籤表匯出(TIA xlsx / Studio 5000 CSV / GX Works3 / Sysmac / CODESYS GVL)。"""
import base64
import csv
import io
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from plc_st.lexer import STError
from plc_st.parser import parse
from plc_st.tagexport import export_tags, tia_rows, tag_rows
from plc_st.web import State as AppState, handle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = """name,type,direction,init,comment,address
start,BOOL,IN,,啟動按鈕,%IX0.0
stop,BOOL,IN,,"停止, 常閉",
motor,BOOL,OUT,,馬達,%QX0.0
speed,INT,OUT,,速度,%QW2
cnt,INT,VAR,0,計數,
total,DINT,RETAIN,,累計,
MAXN,INT,CONST,100,上限,
t1,TON,VAR,,計時,
buf,"ARRAY[1..5] OF INT",VAR,,,
big,LREAL,VAR,,,
"""
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def xlsx_sheets(data):
    """以 stdlib 讀回 xlsx:{工作表名: [[cell...]]}。"""
    z = zipfile.ZipFile(io.BytesIO(data))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    out = {}
    for i, sh in enumerate(wb.find("m:sheets", NS), 1):
        root = ET.fromstring(z.read(f"xl/worksheets/sheet{i}.xml"))
        rows = []
        for r in root.iter(f"{{{NS['m']}}}row"):
            cells = {}
            for c in r:
                col = "".join(ch for ch in c.get("r") if ch.isalpha())
                cells[ord(col) - 65] = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
            rows.append([cells.get(k, "") for k in range(max(cells) + 1)] if cells else [])
        out[sh.get("name")] = rows
    return out


class TiaTest(unittest.TestCase):
    def setUp(self):
        self.data, self.ext, self.warn = export_tags(CSV, "tia")
        self.sh = xlsx_sheets(self.data)

    def test_valid_xlsx_with_two_sheets(self):
        self.assertEqual(self.ext, "xlsx")
        self.assertEqual(list(self.sh), ["PLC Tags", "User Constants"])
        self.assertEqual(self.sh["PLC Tags"][0][:4], ["Name", "Path", "Data Type", "Logical Address"])

    def test_addresses_and_types(self):
        rows = {r[0]: r for r in self.sh["PLC Tags"][1:]}
        self.assertEqual(rows["start"][2:4], ["Bool", "%I0.0"])
        self.assertEqual(rows["motor"][3], "%Q0.0")
        self.assertEqual(rows["speed"][2:4], ["Int", "%QW2"])
        self.assertEqual(rows["stop"][3], "%I0.1")  # 自動配置:同位元組下一個位元
        self.assertEqual(rows["stop"][4], "停止, 常閉")

    def test_retain_first_then_memory(self):
        rows = {r[0]: r for r in self.sh["PLC Tags"][1:]}
        self.assertEqual(rows["total"][3], "%MD0")  # RETAIN 先配置,從 MB0 起
        self.assertEqual(rows["cnt"][3], "%MW4")

    def test_constants_sheet(self):
        self.assertEqual(self.sh["User Constants"][1], ["MAXN", "Default tag table", "Int", "100", "上限"])

    def test_skips_non_elementary_with_warnings(self):
        names = [r[0] for r in self.sh["PLC Tags"][1:]]
        for n in ("t1", "buf", "big", "MAXN"):
            self.assertNotIn(n, names)
        w = "\n".join(self.warn)
        self.assertIn("t1: 型別 TON", w)
        self.assertIn("buf: 型別 ARRAY", w)
        self.assertIn("big: LREAL 需 8 位元組", w)
        self.assertIn("自動配置 %I0.1", w)
        self.assertIn("初值 0 未匯出", w)

    def test_alloc_avoids_used_bytes(self):
        csv_ = "name,type,direction,init,comment,address\na,WORD,VAR,,,%MW0\nb,BOOL,VAR,,,%MX2.0\nc,INT,VAR,,,\nd,BOOL,VAR,,,\n"
        tags, _, _ = tia_rows(tag_rows(csv_))
        got = {r[0]: r[3] for r in tags}
        self.assertEqual(got["c"], "%MW4")  # 0-1 被 a、2 被位元使用 → 下一個偶數位元組 4
        self.assertEqual(got["d"], "%M2.1")


class LogixTest(unittest.TestCase):
    def setUp(self):
        self.text, self.ext, self.warn = export_tags(CSV, "logix")
        lines = self.text.splitlines()
        i = lines.index("TYPE,SCOPE,NAME,DESCRIPTION,DATATYPE,SPECIFIER,ATTRIBUTES")
        self.head = lines[:i]
        self.rows = {r[2]: r for r in csv.reader(lines[i + 1:])}

    def test_header(self):
        self.assertEqual(self.head[0], 'remark,"CSV-Import-Export"')
        self.assertIn("0.3", self.head)
        self.assertIn("\r\n", self.text)

    def test_types_and_attrs(self):
        self.assertEqual(self.rows["start"][:5], ["TAG", "", "start", "啟動按鈕 [IEC %IX0.0: alias to module I/O]", "BOOL"])
        self.assertEqual(self.rows["t1"][4], "TIMER")
        self.assertEqual(self.rows["buf"][4], "INT[5]")
        self.assertIn("Constant := true", self.rows["MAXN"][6])
        self.assertIn("RADIX := Float", self.rows["big"][6])
        self.assertNotIn("RADIX", self.rows["t1"][6])
        self.assertEqual(self.rows["stop"][3], "停止, 常閉")  # 含逗號的說明正確加引號

    def test_warnings(self):
        w = "\n".join(self.warn)
        self.assertIn("buf: Logix 陣列從 0 起算", w)
        self.assertIn("MAXN: 標籤 CSV 不含初值", w)
        self.assertIn("big: LREAL 僅 v32", w)

    def test_substitutions(self):
        text, _, warn = export_tags("name,type,direction\nw,WORD,VAR\nt,TIME,VAR\ns,MyUdt,VAR\n", "logix")
        self.assertIn('TAG,,w,"","INT"', text)
        self.assertIn('TAG,,t,"","DINT"', text)
        self.assertNotIn(",s,", text)
        self.assertTrue(any("s: 型別 MYUDT 無 Logix 對應" in x for x in warn))


class OtherFormatsTest(unittest.TestCase):
    def test_gxworks(self):
        text, _, warn = export_tags(CSV, "gxworks")
        rows = {r.split("\t")[0]: r.split("\t") for r in text.splitlines()[1:]}
        self.assertEqual(rows["start"][1:3], ["Bit", "VAR_GLOBAL"])
        self.assertEqual(rows["total"][2], "VAR_GLOBAL_RETAIN")
        self.assertEqual(rows["MAXN"][2:6], ["VAR_GLOBAL_CONSTANT", "", "", "100"])
        self.assertEqual(rows["buf"][1], "Word [Signed](1..5)")
        self.assertIn("[IEC %QW2]", rows["speed"][6])
        self.assertTrue(any("speed: 請在 Assign 欄指定裝置" in w for w in warn))

    def test_sysmac(self):
        text, _, _ = export_tags(CSV, "sysmac")
        rows = {r.split("\t")[0]: r.split("\t") for r in text.splitlines()[1:]}
        self.assertEqual(rows["total"][4], "TRUE")
        self.assertEqual(rows["MAXN"][2:6], ["100", "", "FALSE", "TRUE"])
        self.assertEqual(rows["buf"][1], "ARRAY[1..5] OF INT")

    def test_gvl_parses_as_st(self):
        text, ext, warn = export_tags(CSV, "codesys")
        self.assertEqual(ext, "gvl.st")
        self.assertIn("\tstart AT %IX0.0 : BOOL; // 啟動按鈕", text)
        self.assertIn("VAR_GLOBAL CONSTANT\n\tMAXN : INT := 100; // 上限\nEND_VAR", text)
        self.assertIn("VAR_GLOBAL RETAIN\n\ttotal : DINT;", text)
        self.assertEqual(warn, [])
        # 把 GVL 區段改成 VAR 包進 PROGRAM,確認宣告語法正確
        body = text.replace("VAR_GLOBAL CONSTANT", "VAR CONSTANT").replace("VAR_GLOBAL RETAIN", "VAR RETAIN") \
            .replace("VAR_GLOBAL", "VAR").replace("//", "(*").replace("\n", "\n")
        decl = "\n".join(l.split(" (*")[0] if "(*" in l else l for l in body.splitlines())
        parse(f"PROGRAM P\n{decl}\nEND_PROGRAM\n")


class ErrorsTest(unittest.TestCase):
    def test_bad_rows(self):
        with self.assertRaisesRegex(STError, "line 2"):
            export_tags("name,type,direction\n1bad,BOOL,IN\n", "tia")
        with self.assertRaisesRegex(STError, "沒有任何點位"):
            export_tags("name,type,direction\n", "logix")
        with self.assertRaisesRegex(STError, "unknown tag format"):
            export_tags(CSV, "s5")


class WebCliTest(unittest.TestCase):
    def test_api_binary_and_text(self):
        st = AppState()
        code, j = handle("POST", "/api/tags/export", {"csv": CSV, "format": "tia"}, st)
        self.assertEqual(code, 200)
        self.assertIn("PLC Tags", xlsx_sheets(base64.b64decode(j["b64"])))
        self.assertEqual(j["size"], len(base64.b64decode(j["b64"])))
        code, j = handle("POST", "/api/tags/export", {"csv": CSV, "format": "codesys"}, st)
        self.assertEqual((code, j["ext"]), (200, "gvl.st"))
        self.assertIn("VAR_GLOBAL", j["text"])
        code, j = handle("POST", "/api/tags/export", {"csv": "name,type\nx,BOOL\n", "format": "nope"}, st)
        self.assertEqual(code, 400)

    def test_cli(self):
        src = os.path.join(ROOT, "examples", "points_addr.csv")
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "t.xlsx")
            r = subprocess.run([sys.executable, "-m", "plc_st", "tags", src, "--format", "tia", "-o", out],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out, "rb") as f:
                self.assertIn("PLC Tags", xlsx_sheets(f.read()))
            r = subprocess.run([sys.executable, "-m", "plc_st", "tags", src, "--format", "tia"],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("-o", r.stderr)
            r = subprocess.run([sys.executable, "-m", "plc_st", "tags", src, "--format", "logix"],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn("TYPE,SCOPE,NAME", r.stdout)
            r = subprocess.run([sys.executable, "-m", "plc_st", "tags", src], cwd=ROOT, capture_output=True, text=True)
            self.assertIn("start AT %IX0.0 : BOOL;", r.stdout)  # 不給 --format 仍是 VAR 宣告


if __name__ == "__main__":
    unittest.main()
