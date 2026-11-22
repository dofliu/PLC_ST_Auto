"""M38:點位表(CSV)→ 各廠牌工程軟體可匯入的標籤/變數表。

每個格式回傳 (內容, 警告清單);內容為 str,TIA 為 xlsx 的 bytes。
- tia     Siemens TIA Portal「PLC 變數」表 xlsx(PLC tags → Import):PLC Tags + User Constants 工作表;
          PLC 變數必須有位址,沒有位址的點位依方向自動配置(IN→%I、OUT→%Q、其餘→%M),並列出警告
- logix   Rockwell Studio 5000 標籤 CSV(Tools → Import → Tags and Logic Comments):控制器範圍 TAG 列
- gxworks Mitsubishi GX Works3 全域標籤(Tab 分隔,可貼入 Global Label Setting)
- sysmac  Omron Sysmac Studio 全域變數表(Tab 分隔,可貼入 Global Variables)
- codesys CODESYS / TwinCAT GVL(VAR_GLOBAL / CONSTANT / RETAIN,保留 AT 位址)

位址照點位表原樣輸出(TIA 僅把 %IX0.0 寫成 %I0.0),不依廠牌換算 word 編號;
自動配置的位址使用該廠牌的定址(TIA 依位元組)。
"""
import io
import re
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from .interpreter import STError
from .parser import parse_addr
from .tags import preview_tags

_ARR = re.compile(r"^ARRAY\s*\[\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*\]\s*OF\s+(\w+)$", re.I)
_BYTES = {"BOOL": 0, "SINT": 1, "USINT": 1, "BYTE": 1, "CHAR": 1, "INT": 2, "UINT": 2, "WORD": 2,
          "DINT": 4, "UDINT": 4, "DWORD": 4, "REAL": 4, "TIME": 4, "LINT": 8, "ULINT": 8, "LWORD": 8, "LREAL": 8}


def tag_rows(csv_text):
    """讀點位表;有任何錯誤列即報錯(帶行號)。回傳列:name/type/direction/init/comment/address。"""
    pv = preview_tags(csv_text)
    if pv.get("fatal"):
        raise STError(pv["fatal"])
    bad = [r for r in pv["rows"] if r["error"]]
    if bad:
        raise STError("; ".join(f"tag table line {r['line']}: {r['error']}" for r in bad[:5]))
    if not pv["rows"]:
        raise STError("點位表沒有任何點位")
    for r in pv["rows"]:
        r["direction"] = {"CONSTANT": "CONST"}.get(r["direction"], r["direction"])
    return pv["rows"]


def _arr(t):
    m = _ARR.match(t.strip())
    return (int(m.group(1)), int(m.group(2)), m.group(3).upper()) if m else None


# ---------------------------------------------------------------- Siemens TIA Portal
_TIA_TYPE = {"BOOL": "Bool", "SINT": "SInt", "USINT": "USInt", "BYTE": "Byte", "CHAR": "Char", "INT": "Int",
             "UINT": "UInt", "WORD": "Word", "DINT": "DInt", "UDINT": "UDInt", "DWORD": "DWord", "REAL": "Real",
             "TIME": "Time", "LINT": "LInt", "ULINT": "ULInt", "LWORD": "LWord", "LREAL": "LReal"}
_TIA_SIZE = {1: "B", 2: "W", 4: "D"}  # 8 位元組型別不自動配置(改放 DB)


def _tia_addr(a):
    return re.sub(r"^(%[IQM])X", r"\1", a.upper())


class _Alloc:
    """TIA 位元組定址的自動配置:先標記已用位址,再為每區找下一個空位(word 以上偶數對齊)。"""

    def __init__(self, rows):
        self.used = {"I": set(), "Q": set(), "M": set()}
        self.bits = {"I": set(), "Q": set(), "M": set()}
        for r in rows:
            if r["address"]:
                a = parse_addr(r["address"])
                if a["size"] == "X":
                    self.bits[a["area"]].add((a["index"], a["bit"] or 0))
                    self.used[a["area"]].add(("bit", a["index"]))
                else:
                    for b in range(a["index"], a["index"] + a["bits"] // 8):
                        self.used[a["area"]].add(b)

    def _free(self, area, b):
        return b not in self.used[area] and ("bit", b) not in self.used[area]

    def take(self, area, nbytes):
        if nbytes == 0:  # BOOL:先填已有位元的位元組,再開新位元組
            for byte in sorted({b for b, _ in self.bits[area]}):
                for bit in range(8):
                    if (byte, bit) not in self.bits[area] and byte not in self.used[area]:
                        self.bits[area].add((byte, bit))
                        return f"%{area}{byte}.{bit}"
            b = 0
            while not self._free(area, b):
                b += 1
            self.bits[area].add((b, 0))
            self.used[area].add(("bit", b))
            return f"%{area}{b}.0"
        step = 1 if nbytes == 1 else 2
        b = 0
        while not all(self._free(area, x) for x in range(b, b + nbytes)):
            b += step
        self.used[area].update(range(b, b + nbytes))
        return f"%{area}{_TIA_SIZE[nbytes]}{b}"


def _xlsx(sheets):
    """最小 xlsx(inline string,無共用字串表/樣式);sheets = [(名稱, [[cell, ...], ...])]。"""
    def col(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    def sheet(rows):
        o = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for ri, row in enumerate(rows, 1):
            cells = "".join(f'<c r="{col(ci)}{ri}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
                            for ci, v in enumerate(row) if v != "")
            o.append(f'<row r="{ri}">{cells}</row>')
        o.append("</sheetData></worksheet>")
        return "".join(o)

    buf = io.BytesIO()
    ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                      for i in range(1, len(sheets) + 1)) + "</Types>"))
        z.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{ns}/officeDocument" Target="xl/workbook.xml"/></Relationships>'))
        z.writestr("xl/workbook.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="{ns}"><sheets>'
            + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheets, 1))
            + "</sheets></workbook>"))
        z.writestr("xl/_rels/workbook.xml.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i}" Type="{ns}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                      for i in range(1, len(sheets) + 1)) + "</Relationships>"))
        for i, (_, rows) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet(rows))
    return buf.getvalue()


def tia_rows(rows, table="Default tag table"):
    """回傳 (PLC Tags 列, User Constants 列, 警告)。"""
    warn, tags, consts = [], [], []
    alloc, auto = _Alloc(rows), {}
    # 斷電保持的 %M 先配置(TIA 的 Retain 範圍從 MB0 起連續),其餘依序
    for r in sorted(rows, key=lambda r: r["direction"] != "RETAIN"):
        t = r["type"]
        if not r["address"] and r["direction"] != "CONST" and t in _TIA_TYPE and _BYTES[t] != 8:
            auto[r["name"]] = alloc.take({"IN": "I", "OUT": "Q"}.get(r["direction"], "M"), _BYTES[t])
    for r in rows:
        t, n = r["type"], r["name"]
        if r["direction"] == "CONST":
            if t not in _TIA_TYPE:
                warn.append(f"{n}: 型別 {t} 不能作為 TIA 使用者常數,已略過")
                continue
            consts.append([n, table, _TIA_TYPE[t], r["init"] or "0", r["comment"]])
            continue
        if t not in _TIA_TYPE:
            warn.append(f"{n}: 型別 {t} 不能放在 PLC 變數表(只接受基本型別),請改放全域 DB,已略過")
            continue
        addr = r["address"]
        if not addr:
            if n not in auto:
                warn.append(f"{n}: {t} 需 8 位元組,不自動配置 64 位元位址,請改放全域 DB 或在點位表指定位址,已略過")
                continue
            addr = auto[n]
            warn.append(f"{n}: 點位表未指定位址,自動配置 {addr}")
        if r["direction"] == "RETAIN":
            warn.append(f"{n}: TIA 的 %M 斷電保持由「Retain」範圍設定(從 MB0 起連續),請確認 {_tia_addr(addr)} 在範圍內")
        if r["init"]:
            warn.append(f"{n}: PLC 變數表沒有初值欄,初值 {r['init']} 未匯出(請在啟動 OB100 指派)")
        tags.append([n, table, _TIA_TYPE[t], _tia_addr(addr), r["comment"], "True", "True", "True", "", ""])
    return tags, consts, warn


def to_tia(csv_text):
    tags, consts, warn = tia_rows(tag_rows(csv_text))
    head = ["Name", "Path", "Data Type", "Logical Address", "Comment", "Hmi Visible", "Hmi Accessible",
            "Hmi Writeable", "Typeobject ID", "Version ID"]
    sheets = [("PLC Tags", [head] + tags)]
    if consts:
        sheets.append(("User Constants", [["Name", "Path", "Data Type", "Value", "Comment"]] + consts))
    return _xlsx(sheets), warn


# ---------------------------------------------------------------- Rockwell Studio 5000
_LOGIX_TYPE = {"BOOL": "BOOL", "SINT": "SINT", "INT": "INT", "DINT": "DINT", "LINT": "LINT", "REAL": "REAL",
               "LREAL": "LREAL", "USINT": "USINT", "UINT": "UINT", "UDINT": "UDINT", "ULINT": "ULINT",
               "STRING": "STRING", "TON": "TIMER", "TOF": "TIMER", "TP": "TIMER", "CTU": "COUNTER",
               "CTD": "COUNTER", "CTUD": "COUNTER"}
_LOGIX_SUB = {"BYTE": "SINT", "WORD": "INT", "DWORD": "DINT", "LWORD": "LINT", "TIME": "DINT", "CHAR": "SINT"}


def _csvq(s):
    return '"' + str(s).replace('"', '""') + '"'


def to_logix(csv_text):
    warn, o = [], []
    for r in tag_rows(csv_text):
        n, t = r["name"], r["type"]
        a = _arr(t)
        base = a[2] if a else t
        if base in _LOGIX_SUB:
            warn.append(f"{n}: Logix 沒有 {base},改用 {_LOGIX_SUB[base]}" + ("(TIME 以毫秒 DINT 表示)" if base == "TIME" else ""))
            dt = _LOGIX_SUB[base]
        elif base in _LOGIX_TYPE:
            dt = _LOGIX_TYPE[base]
            if dt in ("TIMER", "COUNTER"):
                warn.append(f"{n}: {base} 對應 Logix {dt}(TON/CTU 指令語意不同,請確認 .PRE/.ACC)")
            elif base in ("USINT", "UINT", "UDINT", "ULINT", "LREAL"):
                warn.append(f"{n}: {base} 僅 v32 以上 / 5380·5580 控制器支援")
        else:
            warn.append(f"{n}: 型別 {t} 無 Logix 對應,已略過(UDT/AOI 請用 L5X 匯出)")
            continue
        if a:
            lo, hi, _ = a
            if lo != 0:
                warn.append(f"{n}: Logix 陣列從 0 起算,ARRAY[{lo}..{hi}] 改為 [{hi - lo + 1}],程式索引需減 {lo}")
            dt = f"{dt}[{hi - lo + 1}]"
        desc = r["comment"]
        if r["address"]:
            desc = (desc + " " if desc else "") + f"[IEC {r['address']}: alias to module I/O]"
        if r["init"]:
            warn.append(f"{n}: 標籤 CSV 不含初值,初值 {r['init']} 未匯出(需要初值請用 L5X 匯出)")
        if r["direction"] == "RETAIN":
            warn.append(f"{n}: Logix 標籤本來就斷電保持,RETAIN 不需額外設定")
        radix = "" if dt.split("[")[0] in ("STRING", "TIMER", "COUNTER") else \
            ("RADIX := Float, " if dt.startswith(("REAL", "LREAL")) else "RADIX := Decimal, ")
        attrs = f"({radix}Constant := {'true' if r['direction'] == 'CONST' else 'false'}, ExternalAccess := Read/Write)"
        o.append(",".join(["TAG", "", n, _csvq(desc), _csvq(dt), _csvq(""), _csvq(attrs)]))
    date = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
    head = ['remark,"CSV-Import-Export"', f'remark,"Date = {date}"', 'remark,"Version = RSLogix 5000 v32.00"',
            'remark,"Owner = PLC_ST_Auto"', 'remark,"Company = "', "0.3",
            "TYPE,SCOPE,NAME,DESCRIPTION,DATATYPE,SPECIFIER,ATTRIBUTES"]
    return "\r\n".join(head + o) + "\r\n", warn


# ---------------------------------------------------------------- Mitsubishi GX Works3
def to_gxworks_labels(csv_text):
    from .export import _MELSEC_TYPE
    warn = []
    o = ["Label Name\tData Type\tClass\tAssign (Device/Label)\tInitial Value\tConstant\tComment"]
    for r in tag_rows(csv_text):
        n, t = r["name"], r["type"]
        a = _arr(t)
        base = a[2] if a else t
        if base not in _MELSEC_TYPE:
            if base in ("TON", "TOF", "TP", "CTU", "CTD", "CTUD"):
                dt = base  # FB 實例:GX Works3 以 FB 名稱為型別
                warn.append(f"{n}: FB {base} 實例請確認 GX Works3 標準 FB 名稱(例 TON_10)")
            else:
                warn.append(f"{n}: 型別 {t} 無 GX Works3 對應,已略過")
                continue
        else:
            dt = _MELSEC_TYPE[base]
        if a:
            dt = f"{dt}({a[0]}..{a[1]})"
        cls = {"CONST": "VAR_GLOBAL_CONSTANT", "RETAIN": "VAR_GLOBAL_RETAIN"}.get(r["direction"], "VAR_GLOBAL")
        cmt = r["comment"]
        if r["address"]:  # MELSEC 裝置編號無法由 IEC 位址可靠換算(X/Y 為 8 或 16 進位)
            cmt = (cmt + " " if cmt else "") + f"[IEC {r['address']}]"
            warn.append(f"{n}: 請在 Assign 欄指定裝置(X/Y/M/D),IEC 位址 {r['address']} 已寫入註解")
        const = r["init"] if r["direction"] == "CONST" else ""
        init = "" if r["direction"] == "CONST" else r["init"]
        o.append("\t".join([n, dt, cls, "", init, const, cmt.replace("\t", " ")]))
    return "\r\n".join(o) + "\r\n", warn


# ---------------------------------------------------------------- Omron Sysmac Studio
def to_sysmac_vars(csv_text):
    warn = []
    o = ["Name\tData Type\tInitial Value\tAT\tRetain\tConstant\tNetwork Publish\tComment"]
    for r in tag_rows(csv_text):
        n, t = r["name"], r["type"]
        cmt = r["comment"]
        if r["address"]:
            cmt = (cmt + " " if cmt else "") + f"[IEC {r['address']}]"
            warn.append(f"{n}: Sysmac 的 I/O 請在 I/O Map 指定,IEC 位址 {r['address']} 已寫入註解")
        o.append("\t".join([n, t, r["init"], "", "TRUE" if r["direction"] == "RETAIN" else "FALSE",
                            "TRUE" if r["direction"] == "CONST" else "FALSE", "Do not publish", cmt.replace("\t", " ")]))
    return "\r\n".join(o) + "\r\n", warn


# ---------------------------------------------------------------- CODESYS / TwinCAT GVL
def to_gvl(csv_text):
    rows = tag_rows(csv_text)
    o = ["(* GVL generated by PLC_ST_Auto from tag table *)"]
    for title, sel in (("VAR_GLOBAL", lambda r: r["direction"] not in ("CONST", "RETAIN")),
                       ("VAR_GLOBAL CONSTANT", lambda r: r["direction"] == "CONST"),
                       ("VAR_GLOBAL RETAIN", lambda r: r["direction"] == "RETAIN")):
        part = [r for r in rows if sel(r)]
        if not part:
            continue
        o.append(title)
        for r in part:
            line = f"\t{r['name']}{' AT ' + r['address'] if r['address'] else ''} : {r['type']}"
            line += (f" := {r['init']}" if r["init"] else "") + ";"
            if r["comment"]:
                line += f" // {r['comment']}"
            o.append(line)
        o.append("END_VAR")
    warn = [f"{r['name']}: direction INOUT 在 GVL 中視為一般全域變數" for r in rows if r["direction"] == "INOUT"]
    return "\n".join(o) + "\n", warn


TAG_FORMATS = {
    "tia": ("xlsx", "Siemens TIA Portal PLC 變數表", to_tia),
    "logix": ("CSV", "Rockwell Studio 5000 標籤 CSV", to_logix),
    "gxworks": ("txt", "Mitsubishi GX Works3 全域標籤", to_gxworks_labels),
    "sysmac": ("txt", "Omron Sysmac Studio 全域變數", to_sysmac_vars),
    "codesys": ("gvl.st", "CODESYS / TwinCAT GVL", to_gvl),
}


def export_tags(csv_text, fmt):
    """回傳 (內容 str|bytes, 副檔名, 警告清單)。"""
    if fmt not in TAG_FORMATS:
        raise STError(f"unknown tag format {fmt!r}; available: {', '.join(TAG_FORMATS)}")
    ext, _, fn = TAG_FORMATS[fmt]
    data, warn = fn(csv_text)
    return data, ext, warn
