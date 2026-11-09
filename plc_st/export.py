"""匯出:PLCopen XML(TC6 v2.01,CODESYS/Beckhoff/多數工具可匯入)、Siemens SCL(.scl)、純文字 ST。

以文字層級切分 PROGRAM(宣告區 / 本體),不改動使用者程式邏輯。"""
import os
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr

from .lexer import STError
from .parser import Parser

_PROG = re.compile(r"PROGRAM\s+(\w+)(.*?)END_PROGRAM", re.S | re.I)
_BLOCK = re.compile(r"(VAR(?:_INPUT|_OUTPUT|_IN_OUT)?)\b(.*?)END_VAR", re.S | re.I)
_BASE = {"BOOL", "SINT", "INT", "DINT", "LINT", "USINT", "UINT", "UDINT", "ULINT",
         "BYTE", "WORD", "DWORD", "REAL", "LREAL", "TIME", "STRING"}
_SECTION = {"VAR": "localVars", "VAR_INPUT": "inputVars", "VAR_OUTPUT": "outputVars", "VAR_IN_OUT": "inOutVars"}


_LIT = re.compile(r"'[^']*'|\(\*.*?\*\)|//[^\n]*", re.S)


def _views(src):
    """同長度的兩份文字:nocom = 註解換成空白(字串保留);masked = 再把字串內容換成 '_'。
    結構判斷(找 TYPE/VAR 區塊、切 ';'、找 ':'/':=')一律在 masked 上做,取值時切 nocom 同位置,
    因此字串內的 ';'、'(*'、'//'、':=' 不會被誤判。"""
    nocom, masked = list(src), list(src)
    for m in _LIT.finditer(src):
        a, b = m.span()
        if m.group().startswith("'"):
            for i in range(a + 1, b - 1):
                masked[i] = "\n" if src[i] == "\n" else "_"
        else:
            for i in range(a, b):
                nocom[i] = masked[i] = "\n" if src[i] == "\n" else " "
    return "".join(nocom), "".join(masked)


def _decls(nocom, masked, a, b, what="宣告"):
    """把 [a, b) 區間依頂層 ';' 切成 [(names, type, init|None)]。"""
    out, start = [], a
    for i in range(a, b + 1):
        if i < b and masked[i] != ";":
            continue
        ms, ns, start = masked[start:i], nocom[start:i], i + 1
        if not ms.strip():
            continue
        c = ms.find(":")
        if c < 0 or ms.startswith(":=", c):
            raise STError(f"export: 無法解析{what} {ns.strip()!r}")
        ce = ms.find(":=", c + 1)
        typ = ns[c + 1:ce] if ce >= 0 else ns[c + 1:]
        init = ns[ce + 2:].strip() if ce >= 0 else ""
        names = [n.strip() for n in ns[:c].split(",")]
        out.append((names, " ".join(typ.split()), init or None))
    return out


def split_program(src):
    """回傳 (name, [(kind, [(name,type,init)])], decl_text, body_text)。"""
    nocom, masked = _views(src)
    m = _PROG.search(masked)
    if not m:
        raise STError("export: 找不到 PROGRAM ... END_PROGRAM")
    name, (i0, i1) = m.group(1), m.span(2)
    blocks, last = [], i0
    for b in _BLOCK.finditer(masked, i0, i1):
        decls = []
        for names, typ, init in _decls(nocom, masked, *b.span(2)):
            decls += [(n, typ, init) for n in names]
        blocks.append((b.group(1).upper(), decls))
        last = b.end()
    return name, blocks, src[i0:last].strip(), src[last:i1].strip()


def _const_int(text, where):
    """陣列邊界:完整解析並計算整數常數運算式(+ - * / MOD、括號、負號)。
    無法完整解析或含變數/實數時明確報錯,不做部分比對。"""
    try:
        p = Parser(text)
        e = p.expr()
        p.expect("eof")
    except STError:
        raise STError(f"export: {where} 陣列邊界 {text.strip()!r} 無法解析") from None

    def ev(e):
        if e[0] == "num" and isinstance(e[1], int):
            return e[1]
        if e[0] == "neg":
            return -ev(e[1])
        if e[0] == "bin" and e[1] in ("+", "-", "*", "/", "MOD"):
            a, b = ev(e[2]), ev(e[3])
            if e[1] in ("/", "MOD") and b == 0:
                raise STError(f"export: {where} 陣列邊界 {text.strip()!r} 除以 0")
            if e[1] == "/":
                return int(a / b)
            if e[1] == "MOD":
                return a - b * int(a / b)
            return {"+": a + b, "-": a - b, "*": a * b}[e[1]]
        raise STError(f"export: {where} 陣列邊界 {text.strip()!r} 須為整數常數運算式"
                      "(不支援變數/常數名稱/實數)")
    return ev(e)


def _array_type(t, where):
    """'ARRAY[lo..hi, ...] OF T' → ([(lo, hi), ...], 'T');非陣列回傳 None。"""
    t = t.strip()
    if not re.match(r"(?i)ARRAY\b", t):
        return None
    m = re.fullmatch(r"(?is)ARRAY\s*\[(.*)\]\s*OF\s+(\w+)", t)
    if not m:
        raise STError(f"export: {where} 陣列型別 {t!r} 無法解析")
    dims = []
    for part in _split_top(m.group(1)):
        lo, sep, hi = part.partition("..")
        if not sep:
            raise STError(f"export: {where} 陣列範圍 {part!r} 須為 lo..hi")
        a, b = _const_int(lo, where), _const_int(hi, where)
        if b < a:
            raise STError(f"export: {where} 陣列上界 {b} < 下界 {a}")
        dims.append((a, b))
    return dims, m.group(2)


def _tc6_type(t):
    """IEC 型別 → TC6 型別元素;TC6 的 string/wstring 為小寫,其餘基本型別大寫。"""
    u = t.upper()
    if u in ("STRING", "WSTRING"):
        return f"<{u.lower()}/>"
    return f"<{u}/>" if u in _BASE else f"<derived name={quoteattr(t)}/>"


_TYPEDEF = re.compile(r"TYPE\s+(\w+)\s*:\s*STRUCT(.*?)END_STRUCT\s*;?\s*END_TYPE", re.S | re.I)


def _split_top(text):
    """依最外層逗號切分(括號/中括號/字串內不切)。"""
    parts, depth, cur, q = [], 0, [], False
    for ch in text:
        if ch == "'":
            q = not q
        if not q:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(cur).strip())
                cur = []
                continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def _tc6_value(v):
    """ST 初始值文字 → TC6 value 元素(simpleValue / arrayValue / structValue)。"""
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return "<arrayValue>" + "".join(f"<value>{_tc6_value(x)}</value>" for x in _split_top(v[1:-1])) + "</arrayValue>"
    if v.startswith("(") and v.endswith(")"):
        out = []
        for item in _split_top(v[1:-1]):
            k, _, val = item.partition(":=")
            if not _:
                raise STError(f"export: 無法解析 STRUCT 初始值 {item!r}")
            out.append(f"<value member={quoteattr(k.strip())}>{_tc6_value(val)}</value>")
        return "<structValue>" + "".join(out) + "</structValue>"
    return f"<simpleValue value={quoteattr(v)}/>"


def _tc6_vartype(t, where=""):
    arr = _array_type(t, where)
    if arr:
        dims = "".join(f'<dimension lower="{a}" upper="{b}"/>' for a, b in arr[0])
        return f"<array>{dims}<baseType>{_tc6_type(arr[1])}</baseType></array>"
    return _tc6_type(t.strip())


def _datatypes(src):
    """TYPE ... STRUCT → TC6 <dataType>(欄位型別含 ARRAY / 巢狀 STRUCT / 初始值)。"""
    nocom, masked = _views(src)
    out = []
    for m in _TYPEDEF.finditer(masked):
        fields = []
        for names, typ, init in _decls(nocom, masked, *m.span(2), what=" STRUCT 欄位"):
            iv = f"<initialValue>{_tc6_value(init)}</initialValue>" if init else ""
            for n in names:
                fields.append(f"<variable name={quoteattr(n)}><type>{_tc6_vartype(typ, f'{m.group(1)}.{n}')}</type>{iv}</variable>")
        out.append(f"<dataType name={quoteattr(m.group(1))}><baseType><struct>{''.join(fields)}</struct></baseType></dataType>")
    return out


def to_plcopen(src, project="PLC_ST_Auto"):
    name, blocks, _, body = split_program(src)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    o = ['<?xml version="1.0" encoding="utf-8"?>',
         '<project xmlns="http://www.plcopen.org/xml/tc6_0201">',
         f'  <fileHeader companyName="" productName="PLC_ST_Auto" productVersion="1.0" creationDateTime="{now}"/>',
         f'  <contentHeader name={quoteattr(project)}><coordinateInfo>'
         '<fbd><scaling x="1" y="1"/></fbd><ld><scaling x="1" y="1"/></ld><sfc><scaling x="1" y="1"/></sfc>'
         '</coordinateInfo></contentHeader>',
         '  <types><dataTypes>' + "".join(_datatypes(src)) + '</dataTypes><pous>',
         f'    <pou name={quoteattr(name)} pouType="program"><interface>']
    for kind, decls in blocks:
        if not decls:
            continue
        o.append(f"      <{_SECTION[kind]}>")
        for n, t, init in decls:
            typ = _tc6_vartype(t, n)
            iv = f"<initialValue>{_tc6_value(init)}</initialValue>" if init else ""
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


def _scl_quote(text, names):
    """把已定義的 STRUCT 型別名稱在型別位置加上雙引號(SCL UDT 引用語法)。"""
    for n in names:
        text = re.sub(rf'(:\s*|\bOF\s+){re.escape(n)}\b(?!")', lambda m: f'{m.group(1)}"{n}"', text, flags=re.I)
    return text


def _scl_types(src):
    """TYPE ... STRUCT → SCL `TYPE "Name" ... END_TYPE`(UDT)。回傳 (名稱清單, 文字)。"""
    nocom, masked = _views(src)
    defs = list(_TYPEDEF.finditer(masked))
    names = [m.group(1) for m in defs]
    out = []
    for m in defs:
        fields = []
        for fnames, typ, init in _decls(nocom, masked, *m.span(2), what=" STRUCT 欄位"):
            stmt = f"{', '.join(fnames)} : {_scl_quote(': ' + typ, names)[2:]}" + (f" := {init}" if init else "")
            fields.append("      " + stmt + ";")
        out.append(f'TYPE "{m.group(1)}"\nVERSION : 0.1\n   STRUCT\n' + "\n".join(fields)
                   + "\n   END_STRUCT;\nEND_TYPE\n")
    return names, "\n".join(out)


def to_scl(src):
    """Siemens TIA:PROGRAM → ORGANIZATION_BLOCK(SCL 外部來源檔 .scl);TYPE STRUCT → UDT(置於 OB 之前)。"""
    name, _, decl, body = split_program(src)
    names, types = _scl_types(src)
    decl = _scl_quote(decl, names)
    if types:
        types += "\n"
    return (f'{types}ORGANIZATION_BLOCK "{name}"\n{{ S7_Optimized_Access := \'TRUE\' }}\nVERSION : 0.1\n'
            f"{decl}\nBEGIN\n{body}\nEND_ORGANIZATION_BLOCK\n")


_L5X_TYPE = {"TON": "TIMER", "TOF": "TIMER", "TP": "TIMER", "CTU": "COUNTER", "CTD": "COUNTER",
             "CTUD": "COUNTER", "TIME": "DINT", "UINT": "INT", "UDINT": "DINT", "USINT": "SINT",
             "BYTE": "SINT", "WORD": "INT", "DWORD": "DINT", "LREAL": "REAL"}


def _l5x_datatypes(src):
    """TYPE ... STRUCT → L5X <DataType>(UDT)。BOOL 欄位依 Logix 慣例打包進隱藏 SINT 主機成員。
    限制:Logix 成員陣列為一維且從 0 起算;STRUCT 欄位初始值無對應(UDT 不帶預設值)。"""
    nocom, masked = _views(src)
    out = []
    for m in _TYPEDEF.finditer(masked):
        tname = m.group(1)
        members = []  # (name, dtype, dim)
        for names, typ, _ in _decls(nocom, masked, *m.span(2), what=" STRUCT 欄位"):
            where = f"{tname}.{names[0]}"
            dim = 0
            arr = _array_type(typ, where)
            if arr:
                if len(arr[0]) != 1:
                    raise STError(f"export l5x: {where} 為多維陣列,Logix UDT 成員僅支援一維")
                lo, hi = arr[0][0]
                if lo != 0:
                    raise STError(f"export l5x: {where} 陣列下界須為 0(Logix 陣列從 0 起算)")
                dim, typ = hi + 1, arr[1]
            dt = _L5X_TYPE.get(typ.upper(), typ.upper() if typ.upper() in _BASE else typ)
            members += [(n, dt, dim) for n in names]
        # 隱藏主機名稱不可與任何欄位撞名(Logix 名稱不分大小寫)
        taken = {n.lower() for n, _, _ in members}
        k = 0
        while f"zzzzzzzzzz{tname.lower()}{k}" in taken:
            k += 1
        host = f"ZZZZZZZZZZ{tname}{k}"
        bools = [x for x in members if x[1] == "BOOL" and not x[2]]
        rows, hidden = [], bool(bools)
        if hidden:
            rows.append(f'<Member Name={quoteattr(host)} DataType="SINT" Dimension="0" Radix="Decimal" '
                        f'Hidden="true" ExternalAccess="Read/Write"/>')
        bit = 0
        for n, dt, dim in members:
            if dt == "BOOL" and not dim:
                if bit > 7:
                    raise STError(f"export l5x: {tname} 的 BOOL 欄位超過 8 個,尚未支援多個隱藏主機")
                rows.append(f'<Member Name={quoteattr(n)} DataType="BIT" Dimension="0" Radix="Decimal" '
                            f'Hidden="false" Target={quoteattr(host)} BitNumber="{bit}" ExternalAccess="Read/Write"/>')
                bit += 1
            else:
                rows.append(f'<Member Name={quoteattr(n)} DataType={quoteattr(dt)} Dimension="{dim}" '
                            f'Radix="{"Float" if dt == "REAL" else "Decimal"}" Hidden="false" ExternalAccess="Read/Write"/>')
        out.append(f'<DataType Name={quoteattr(tname)} Family="NoFamily" Class="User"><Members>'
                   + "".join(rows) + "</Members></DataType>")
    return out


def to_l5x(src, project="PLC_ST_Auto"):
    """Rockwell Studio 5000:Program(Tags + ST Routine)L5X 匯入檔。
    型別對映:TON/TOF→TIMER、CTU/CTD→COUNTER、TIME→DINT 等;函式塊呼叫語法需在 Logix 端人工調整(見 dialect 警告)。"""
    name, blocks, _, body = split_program(src)
    dts = _l5x_datatypes(src)
    now = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
    o = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
         f'<RSLogix5000Content SchemaRevision="1.0" SoftwareRevision="32.00" TargetName={quoteattr(name)} '
         f'TargetType="Program" ContainsContext="false" ExportDate={quoteattr(now)}>',
         f'<Controller Use="Context" Name={quoteattr(project)}>',
         *(["<DataTypes>" + "".join(dts) + "</DataTypes>"] if dts else []),
         "<Programs>",
         f'<Program Use="Target" Name={quoteattr(name)} MainRoutineName="MainRoutine"><Tags>']
    for kind, decls in blocks:
        usage = {"VAR_INPUT": "Input", "VAR_OUTPUT": "Output", "VAR_IN_OUT": "InOut"}.get(kind, "Local")
        for n, t, init in decls:
            dimattr = ""
            arr = _array_type(t, n)
            if arr:
                rs, t = arr
                if len(rs) > 3 or any(lo != 0 for lo, _ in rs):
                    raise STError(f"export l5x: 標籤 {n} 陣列須 ≤3 維且下界為 0(Logix 陣列從 0 起算)")
                # Tag 的 Dimensions 以空白分隔(例 "2 3");尚未以 Studio 5000 實機匯入確認,見 docs/test_report_M29.md
                dimattr = ' Dimensions="' + " ".join(str(hi + 1) for _, hi in rs) + '"'
            dt = _L5X_TYPE.get(t.upper(), t.upper() if t.upper() in _BASE else t)
            o.append(f'<Tag Name={quoteattr(n)} TagType="Base" DataType={quoteattr(dt)}{dimattr} '
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

_FUNCPOU = re.compile(r"^\s*FUNCTION(?:_BLOCK)?\s+\w+", re.M | re.I)


def export(src, fmt):
    pat = _FUNCPOU if fmt in ("plcopen", "scl", "l5x") else _USERPOU
    if fmt in FORMATS and fmt != "st" and pat.search(_views(src)[1]):
        raise STError(f"export {fmt}: 含自訂 FUNCTION/FUNCTION_BLOCK/TYPE(STRUCT),此格式尚未支援(僅 st 格式可完整匯出)")
    try:
        return FORMATS[fmt][1](src)
    except KeyError:
        raise STError(f"unknown export format {fmt!r}; available: {', '.join(FORMATS)}") from None
