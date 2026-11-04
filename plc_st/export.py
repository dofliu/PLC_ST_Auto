"""匯出:PLCopen XML(TC6 v2.01,CODESYS/Beckhoff/多數工具可匯入)、Siemens SCL(.scl)、純文字 ST。

以文字層級切分 PROGRAM(宣告區 / 本體),不改動使用者程式邏輯。"""
import os
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr

from .lexer import STError

_PROG = re.compile(r"PROGRAM\s+(\w+)(.*?)END_PROGRAM", re.S | re.I)
_BLOCK = re.compile(r"(VAR(?:_INPUT|_OUTPUT|_IN_OUT)?)\b(.*?)END_VAR", re.S | re.I)
_BASE = {"BOOL", "SINT", "INT", "DINT", "LINT", "USINT", "UINT", "UDINT", "ULINT",
         "BYTE", "WORD", "DWORD", "REAL", "LREAL", "TIME", "STRING"}
_SECTION = {"VAR": "localVars", "VAR_INPUT": "inputVars", "VAR_OUTPUT": "outputVars", "VAR_IN_OUT": "inOutVars"}


def split_program(src):
    """回傳 (name, [(kind, [(name,type,init)])], decl_text, body_text)。"""
    src = re.sub(r"\(\*.*?\*\)", lambda m: m.group(0), src, flags=re.S)
    m = _PROG.search(src)
    if not m:
        raise STError("export: 找不到 PROGRAM ... END_PROGRAM")
    name, inner = m.group(1), m.group(2)
    blocks, last = [], 0
    for b in _BLOCK.finditer(inner):
        decls = []
        for stmt in b.group(2).split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            lhs, _, rest = stmt.partition(":")
            if not _:
                raise STError(f"export: 無法解析宣告 {stmt!r}")
            typ, _, init = rest.partition(":=")
            for n in lhs.split(","):
                decls.append((n.strip(), typ.strip(), init.strip() or None))
        blocks.append((b.group(1).upper(), decls))
        last = b.end()
    decl_text = inner[:last].strip()
    return name, blocks, decl_text, inner[last:].strip()


def _tc6_type(t):
    """IEC 型別 → TC6 型別元素;TC6 的 string/wstring 為小寫,其餘基本型別大寫。"""
    u = t.upper()
    if u in ("STRING", "WSTRING"):
        return f"<{u.lower()}/>"
    return f"<{u}/>" if u in _BASE else f"<derived name={quoteattr(t)}/>"


def to_plcopen(src, project="PLC_ST_Auto"):
    name, blocks, _, body = split_program(src)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    o = ['<?xml version="1.0" encoding="utf-8"?>',
         '<project xmlns="http://www.plcopen.org/xml/tc6_0201">',
         f'  <fileHeader companyName="" productName="PLC_ST_Auto" productVersion="1.0" creationDateTime="{now}"/>',
         f'  <contentHeader name={quoteattr(project)}><coordinateInfo>'
         '<fbd><scaling x="1" y="1"/></fbd><ld><scaling x="1" y="1"/></ld><sfc><scaling x="1" y="1"/></sfc>'
         '</coordinateInfo></contentHeader>',
         '  <types><dataTypes/><pous>',
         f'    <pou name={quoteattr(name)} pouType="program"><interface>']
    for kind, decls in blocks:
        if not decls:
            continue
        o.append(f"      <{_SECTION[kind]}>")
        for n, t, init in decls:
            am = re.match(r"(?is)ARRAY\s*\[\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*\]\s*OF\s+(\w+)$", t)
            if am:
                base = _tc6_type(am.group(3))
                typ = (f'<array><dimension lower="{am.group(1)}" upper="{am.group(2)}"/>'
                       f"<baseType>{base}</baseType></array>")
                vals = [v.strip() for v in init.strip("[] ").split(",")] if init else []
                # TC6: initialValue holds ONE value; arrays wrap elements in <arrayValue>
                iv = ("<initialValue><arrayValue>"
                      + "".join(f'<value><simpleValue value={quoteattr(v)}/></value>' for v in vals)
                      + "</arrayValue></initialValue>") if vals else ""
            else:
                typ = _tc6_type(t)
                iv = f'<initialValue><simpleValue value={quoteattr(init)}/></initialValue>' if init else ""
            o.append(f"        <variable name={quoteattr(n)}><type>{typ}</type>{iv}</variable>")
        o.append(f"      </{_SECTION[kind]}>")
    o += ["    </interface><body><ST>",
          f'      <xhtml xmlns="http://www.w3.org/1999/xhtml">{escape(body)}</xhtml>',
          "    </ST></body></pou>", "  </pous></types>",
          '  <instances><configurations><configuration name="Config"><resource name="Res">'
          f'<task name="MainTask" interval="T#10ms" priority="1"><pouInstance name="{name}_inst" typeName={quoteattr(name)}/></task>'
          "</resource></configuration></configurations></instances>",
          "</project>", ""]
    return "\n".join(o)


TC6_XSD = os.path.join(os.path.dirname(__file__), "schemas", "tc6_xml_v201.xsd")


def validate_plcopen(xml_text, xsd=TC6_XSD):
    """以 PLCopen TC6 v2.01 XSD 驗證;回傳錯誤訊息清單(空 = 通過)。需要 lxml。"""
    try:
        from lxml import etree
    except ImportError:
        raise STError("PLCopen schema 驗證需要 lxml(pip install lxml)") from None
    schema = etree.XMLSchema(etree.parse(xsd))
    doc = etree.fromstring(xml_text.encode("utf-8"))
    if schema.validate(doc):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


def to_scl(src):
    """Siemens TIA:PROGRAM → ORGANIZATION_BLOCK(SCL 外部來源檔 .scl)。"""
    name, _, decl, body = split_program(src)
    return (f'ORGANIZATION_BLOCK "{name}"\n{{ S7_Optimized_Access := \'TRUE\' }}\nVERSION : 0.1\n'
            f"{decl}\nBEGIN\n{body}\nEND_ORGANIZATION_BLOCK\n")


_L5X_TYPE = {"TON": "TIMER", "TOF": "TIMER", "TP": "TIMER", "CTU": "COUNTER", "CTD": "COUNTER",
             "CTUD": "COUNTER", "TIME": "DINT", "UINT": "INT", "UDINT": "DINT", "USINT": "SINT",
             "BYTE": "SINT", "WORD": "INT", "DWORD": "DINT", "LREAL": "REAL"}


def to_l5x(src, project="PLC_ST_Auto"):
    """Rockwell Studio 5000:Program(Tags + ST Routine)L5X 匯入檔。
    型別對映:TON/TOF→TIMER、CTU/CTD→COUNTER、TIME→DINT 等;函式塊呼叫語法需在 Logix 端人工調整(見 dialect 警告)。"""
    name, blocks, _, body = split_program(src)
    now = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
    o = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
         f'<RSLogix5000Content SchemaRevision="1.0" SoftwareRevision="32.00" TargetName={quoteattr(name)} '
         f'TargetType="Program" ContainsContext="false" ExportDate={quoteattr(now)}>',
         f'<Controller Use="Context" Name={quoteattr(project)}><Programs>',
         f'<Program Use="Target" Name={quoteattr(name)} MainRoutineName="MainRoutine"><Tags>']
    for kind, decls in blocks:
        usage = {"VAR_INPUT": "Input", "VAR_OUTPUT": "Output", "VAR_IN_OUT": "InOut"}.get(kind, "Local")
        for n, t, init in decls:
            dt = _L5X_TYPE.get(t.upper(), t.upper() if t.upper() in _BASE else t)
            o.append(f'<Tag Name={quoteattr(n)} TagType="Base" DataType={quoteattr(dt)} '
                     f'Usage={quoteattr(usage)} Constant="false" ExternalAccess="Read/Write"/>')
    o += ["</Tags><Routines>", '<Routine Name="MainRoutine" Type="ST"><STContent>']
    for i, line in enumerate(body.splitlines()):
        o.append(f'<Line Number="{i}"><![CDATA[{line.replace("]]>", "]]]]><![CDATA[>")}]]></Line>')
    o += ["</STContent></Routine></Routines></Program></Programs></Controller></RSLogix5000Content>", ""]
    return "\n".join(o)


_MELSEC_TYPE = {"BOOL": "Bit", "SINT": "Word [Signed]", "INT": "Word [Signed]", "DINT": "Double Word [Signed]",
                "LINT": "Double Word [Signed]", "USINT": "Word [Unsigned]/Bit String [16-bit]",
                "UINT": "Word [Unsigned]/Bit String [16-bit]", "UDINT": "Double Word [Unsigned]/Bit String [32-bit]",
                "BYTE": "Word [Unsigned]/Bit String [16-bit]", "WORD": "Word [Unsigned]/Bit String [16-bit]",
                "DWORD": "Double Word [Unsigned]/Bit String [32-bit]", "REAL": "FLOAT (Single Precision)",
                "LREAL": "FLOAT (Double Precision)", "TIME": "Time", "STRING": "String"}
_MELSEC_CLASS = {"VAR_INPUT": "VAR_GLOBAL", "VAR_OUTPUT": "VAR_GLOBAL", "VAR_IN_OUT": "VAR_GLOBAL", "VAR": "VAR"}


def to_gxworks(src, project="PLC_ST_Auto"):
    """Mitsubishi GX Works3:標籤表(Tab 分隔,可貼入 Label Setting)+ ST 本體(貼入 ST 程式編輯器)。
    型別對映:INT→Word [Signed]、DINT→Double Word [Signed]、REAL→FLOAT (Single Precision) 等;
    FB(TON/CTU…)在 GX Works3 為 Timer/Counter 函式塊,需於標籤表手動確認實例型別。"""
    name, blocks, _, body = split_program(src)
    o = [f"(* GX Works3 export: {project} / {name} *)",
         "(* === Label Setting(Tab 分隔:Class / Label Name / Data Type / Initial Value)=== *)",
         "Class\tLabel Name\tData Type\tInitial Value"]
    for kind, decls in blocks:
        for n, t, init in decls:
            dt = _MELSEC_TYPE.get(t.upper(), t)
            o.append(f"{_MELSEC_CLASS[kind]}\t{n}\t{dt}\t{init or ''}")
    o += ["(* === ST Program Body === *)", body, ""]
    return "\n".join(o)


_OMRON_TYPE = {"SINT": "SINT", "USINT": "USINT", "BYTE": "BYTE", "WORD": "WORD", "DWORD": "DWORD",
               "LINT": "LINT", "ULINT": "ULINT", "TIME": "TIME", "STRING": "STRING"}
_OMRON_CLASS = {"VAR": "Internal", "VAR_INPUT": "Input", "VAR_OUTPUT": "Output", "VAR_IN_OUT": "In Out"}


def to_sysmac(src, project="PLC_ST_Auto"):
    """Omron Sysmac Studio:變數表(Tab 分隔,可貼入 Global/Local Variables)+ ST 本體。
    Sysmac 為 IEC 61131-3 型別;TON/TOF/CTU 等 FB 於變數表型別保持原名,需確認實例。"""
    name, blocks, _, body = split_program(src)
    o = [f"(* Sysmac Studio export: {project} / {name} *)",
         "(* === Variable Table(Tab 分隔:Name / Data Type / Initial Value / Class)=== *)",
         "Name\tData Type\tInitial Value\tClass"]
    for kind, decls in blocks:
        for n, t, init in decls:
            o.append(f"{n}\t{_OMRON_TYPE.get(t.upper(), t.upper() if t.upper() in _BASE else t)}\t{init or ''}\t{_OMRON_CLASS[kind]}")
    o += ["(* === ST Program Body === *)", body, ""]
    return "\n".join(o)


FORMATS = {"plcopen": ("xml", to_plcopen), "scl": ("scl", to_scl), "l5x": ("L5X", to_l5x),
           "gxworks": ("txt", to_gxworks),
           "sysmac": ("txt", to_sysmac), "st": ("st", lambda s: s)}


_USERPOU = re.compile(r"^\s*(?:FUNCTION(?:_BLOCK)?\s+\w+|TYPE\s+\w+\s*:)", re.M | re.I)


def export(src, fmt):
    if fmt in FORMATS and fmt != "st" and _USERPOU.search(re.sub(r"\(\*.*?\*\)|//[^\n]*", "", src, flags=re.S)):
        raise STError(f"export {fmt}: 含自訂 FUNCTION/FUNCTION_BLOCK/TYPE(STRUCT),此格式尚未支援(僅 st 格式可完整匯出)")
    try:
        return FORMATS[fmt][1](src)
    except KeyError:
        raise STError(f"unknown export format {fmt!r}; available: {', '.join(FORMATS)}") from None
