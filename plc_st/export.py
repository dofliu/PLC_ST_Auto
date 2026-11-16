"""匯出:PLCopen XML(TC6 v2.01,CODESYS/Beckhoff/多數工具可匯入)、Siemens SCL(.scl)、純文字 ST。

以文字層級切分 PROGRAM(宣告區 / 本體),不改動使用者程式邏輯。"""
import os
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape, quoteattr

from .lexer import STError, parse_time
from .parser import Parser

_PROG = re.compile(r"PROGRAM\s+(\w+)(.*?)END_PROGRAM", re.S | re.I)
_BLOCK = re.compile(r"\b(VAR(?:_INPUT|_OUTPUT|_IN_OUT|_TEMP)?)\b((?:\s+(?:CONSTANT|RETAIN|NON_RETAIN|PERSISTENT)\b)*)(.*?)\bEND_VAR\b",
                    re.S | re.I)
_AT = re.compile(r"(\w+)\s+AT\s+(%[\w.]+)$", re.I)


class _Kind(str):
    """VAR 區段名稱(字串,與舊介面相容),另帶 mods(CONSTANT/RETAIN/PERSISTENT…)與 addrs {變數: 位址}。"""
    mods = frozenset()
    addrs = {}


def _blocks(nocom, masked, i0, i1):
    """[i0, i1) 內的 VAR 區段 → ([( _Kind, [(name, type, init)] )], 最後一個 END_VAR 之後的位置)。"""
    blocks, last = [], i0
    for b in _BLOCK.finditer(masked, i0, i1):
        kind = _Kind(b.group(1).upper())
        kind.mods = frozenset(b.group(2).upper().split())
        kind.addrs = {}
        decls = []
        for names, typ, init in _decls(nocom, masked, *b.span(3)):
            for n in names:
                m = _AT.match(n)
                if m:
                    n = m.group(1)
                    kind.addrs[n] = m.group(2).upper()
                decls.append((n, typ, init))
        blocks.append((kind, decls))
        last = b.end()
    return blocks, last
_BASE = {"BOOL", "SINT", "INT", "DINT", "LINT", "USINT", "UINT", "UDINT", "ULINT",
         "BYTE", "WORD", "DWORD", "REAL", "LREAL", "TIME", "STRING"}
_SECTION = {"VAR": "localVars", "VAR_INPUT": "inputVars", "VAR_OUTPUT": "outputVars", "VAR_IN_OUT": "inOutVars",
            "VAR_TEMP": "tempVars"}


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
    blocks, last = _blocks(nocom, masked, i0, i1)
    return name, blocks, src[i0:last].strip(), src[last:i1].strip()


_POU = re.compile(r"\b(FUNCTION_BLOCK|FUNCTION|PROGRAM)\s+(\w+)(.*?)\bEND_\1\b", re.S | re.I)
_KIND = {"FUNCTION": "function", "FUNCTION_BLOCK": "fb", "PROGRAM": "program"}


def split_pous(src):
    """依原始順序切出所有 POU:[{kind: function|fb|program, name, rtype, blocks, decl, body}]。
    blocks = [(VAR 區段, [(name, type, init)])];decl / body 為原文(保留註解)。"""
    nocom, masked = _views(src)
    out = []
    for m in _POU.finditer(masked):
        kind, (i0, i1) = _KIND[m.group(1).upper()], m.span(3)
        rtype = None
        if kind == "function":
            r = re.match(r"\s*:\s*(\w+)", masked[i0:i1])
            if not r:
                raise STError(f"export: FUNCTION {m.group(2)} 缺少回傳型別")
            rtype, i0 = r.group(1), i0 + r.end()
        blocks, last = _blocks(nocom, masked, i0, i1)
        out.append({"kind": kind, "name": m.group(2), "rtype": rtype, "blocks": blocks,
                    "decl": src[i0:last].strip(), "body": src[last:i1].strip()})
    if sum(p["kind"] == "program" for p in out) != 1:
        raise STError("export: 找不到 PROGRAM ... END_PROGRAM" if not any(p["kind"] == "program" for p in out)
                      else "export: 僅支援單一 PROGRAM")
    return out


def _consts(blocks, where=""):
    """VAR CONSTANT 區段中可算出整數值的常數 {小寫名稱: 值}(可引用先前宣告的常數)。"""
    out = {}
    for kind, decls in blocks:
        if "CONSTANT" not in kind.mods:
            continue
        for n, t, init in decls:
            if init and not re.match(r"(?i)ARRAY\b", t):
                try:
                    out[n.lower()] = _const_int(init, where, out)
                except STError:
                    pass
    return out


def _const_int(text, where, consts=None):
    """陣列邊界:完整解析並計算整數常數運算式(+ - * / MOD、括號、負號、VAR CONSTANT 整數常數)。
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
        if e[0] == "var" and consts and e[1].lower() in consts:
            return consts[e[1].lower()]
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
                      "(僅支援整數與 VAR CONSTANT 整數常數,不支援變數/實數)")
    return ev(e)


def _array_type(t, where, consts=None):
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
        a, b = _const_int(lo, where, consts), _const_int(hi, where, consts)
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


def _expand(t, where, consts):
    """型別文字中的陣列邊界改寫為數字(`ARRAY[1..N] OF INT` → `ARRAY[1..4] OF INT`);非陣列原樣回傳。"""
    arr = _array_type(t, where, consts)
    if not arr:
        return t
    return "ARRAY[" + ", ".join(f"{a}..{b}" for a, b in arr[0]) + f"] OF {arr[1]}"


def _expand_text(text, where, consts):
    """宣告原文中引用常數名稱的陣列邊界改寫為數字(註解與字串不動)。"""
    masked = _views(text)[1]
    for m in reversed(list(re.finditer(r"(?i)\bARRAY\s*\[[^\]]*\]\s*OF\s+\w+", masked))):
        if re.search(r"[A-Za-z_]", m.group().split("]")[0][5:]):
            text = text[:m.start()] + _expand(text[m.start():m.end()], where, consts) + text[m.end():]
    return text


def _temp_init(blocks, where, note):
    """VAR_TEMP 在 IEC / 虛擬 PLC 每次執行都重新初始化;目標平台的暫存或區域變數不保證,
    因此回傳要補在本體開頭的指派敘述(純量)或提醒註解(陣列/結構)。"""
    pre = []
    for kind, decls in blocks:
        if kind != "VAR_TEMP":
            continue
        for n, t, init in decls:
            if re.match(r"(?i)ARRAY\b", t) or t.upper() not in _BASE:
                if init:
                    raise STError(f"export: {where} 的 VAR_TEMP {n} 為陣列/結構且有初始值,目標平台無法帶初值,請改在本體內指派")
                pre.append(f"// 注意:{n} 為暫存變數,{note},使用前請先指派")
            else:
                pre.append(f"{n} := {init or _SCL_ZERO.get(t.upper(), '0')};")
    return pre


def _tc6_vartype(t, where="", consts=None):
    arr = _array_type(t, where, consts)
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


_POUTYPE = {"function": "function", "fb": "functionBlock", "program": "program"}


def to_plcopen(src, project="PLC_ST_Auto"):
    """PROGRAM + 自訂 FUNCTION / FUNCTION_BLOCK → TC6 <pou>(function 帶 returnType);只有 PROGRAM 掛到 task。"""
    pous = split_pous(src)
    name = next(p["name"] for p in pous if p["kind"] == "program")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    o = ['<?xml version="1.0" encoding="utf-8"?>',
         '<project xmlns="http://www.plcopen.org/xml/tc6_0201">',
         f'  <fileHeader companyName="" productName="PLC_ST_Auto" productVersion="1.0" creationDateTime="{now}"/>',
         f'  <contentHeader name={quoteattr(project)}><coordinateInfo>'
         '<fbd><scaling x="1" y="1"/></fbd><ld><scaling x="1" y="1"/></ld><sfc><scaling x="1" y="1"/></sfc>'
         '</coordinateInfo></contentHeader>',
         '  <types><dataTypes>' + "".join(_datatypes(src)) + '</dataTypes><pous>']
    for p in pous:
        o.append(f'    <pou name={quoteattr(p["name"])} pouType="{_POUTYPE[p["kind"]]}"><interface>')
        if p["rtype"]:
            o.append(f'      <returnType>{_tc6_type(p["rtype"])}</returnType>')
        consts = _consts(p["blocks"], p["name"])
        for kind, decls in p["blocks"]:
            if not decls:
                continue
            attrs = "".join(f' {a}="true"' for a, k in (("constant", "CONSTANT"), ("retain", "RETAIN"),
                                                         ("nonretain", "NON_RETAIN"), ("persistent", "PERSISTENT"))
                            if k in kind.mods)
            o.append(f"      <{_SECTION[kind]}{attrs}>")
            for n, t, init in decls:
                typ = _tc6_vartype(t, n, consts)
                iv = f"<initialValue>{_tc6_value(init)}</initialValue>" if init else ""
                at = f" address={quoteattr(kind.addrs[n])}" if n in kind.addrs else ""
                o.append(f"        <variable name={quoteattr(n)}{at}><type>{typ}</type>{iv}</variable>")
            o.append(f"      </{_SECTION[kind]}>")
        o += ["    </interface><body><ST>",
              f'      <xhtml xmlns="http://www.w3.org/1999/xhtml">{escape(p["body"])}</xhtml>',
              "    </ST></body></pou>"]
    o += ["  </pous></types>",
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


_SCL_ZERO = {"BOOL": "FALSE", "REAL": "0.0", "LREAL": "0.0", "TIME": "T#0s", "STRING": "''"}


def _scl_calls(text, funcs):
    """自訂 FUNCTION 呼叫改寫為 TIA 語法:名稱加雙引號、位置引數補成具名(`F(a, 1)` → `"F"(x := a, y := 1)`)。
    funcs = {小寫名稱: (名稱, [參數名…])};字串與註解內不改寫(引數內的註解會被移除)。"""
    if not funcs:
        return text
    nocom, masked = _views(text)
    out, pos = [], 0
    for m in re.finditer(r"(?<![\w.\"])(\w+)\s*\(", masked):
        f = funcs.get(m.group(1).lower())
        if m.start() < pos or not f:
            continue
        depth, j = 1, m.end()
        while j < len(masked) and depth:
            depth += (masked[j] == "(") - (masked[j] == ")")
            j += 1
        if depth:
            raise STError(f"export scl: {f[0]}( 呼叫括號不成對")
        args = _split_top(nocom[m.end():j - 1])
        if len(args) > len(f[1]):
            raise STError(f"export scl: {f[0]} 呼叫引數 {len(args)} 個,超過參數 {len(f[1])} 個")
        named = []
        for k, a in enumerate(args):
            a = _scl_calls(a, funcs)
            top = re.sub(r"\([^()]*\)", "", _views(a)[1])
            while re.search(r"\([^()]*\)", top):
                top = re.sub(r"\([^()]*\)", "", top)
            named.append(a if ":=" in top or "=>" in top else f"{f[1][k]} := {a}")
        out.append(text[pos:m.start()] + f'"{f[0]}"(' + ", ".join(named) + ")")
        pos = j
    return "".join(out) + text[pos:]


def _scl_function(p, names, funcs):
    """FUNCTION → TIA FC:區域 VAR 改為 VAR_TEMP(FC 無靜態區),並在本體開頭補上初值指派,
    使行為與 IEC(每次呼叫重新初始化)及虛擬 PLC 一致。"""
    decl, pre = [], []
    consts = _consts(p["blocks"], p["name"])
    for kind, decls in p["blocks"]:
        if not decls:
            continue
        if kind.addrs:
            raise STError(f'export scl: FUNCTION {p["name"]} 內不可宣告直接位址(AT),請移到 PROGRAM')
        const = "CONSTANT" in kind.mods
        local = kind in ("VAR", "VAR_TEMP") and not const
        decl.append("   " + ("VAR_TEMP" if local else "VAR CONSTANT" if const else kind))
        for n, t, init in decls:
            t = _expand(t, f'{p["name"]}.{n}', consts)
            if local:
                if _array_type(t, f'{p["name"]}.{n}', consts) or t.upper() not in _BASE:
                    if init:
                        raise STError(f'export scl: FUNCTION {p["name"]} 的區域變數 {n} 為陣列/結構且有初始值,'
                                      "TIA FC 的 Temp 無法帶初值,請改在本體內指派")
                    pre.append(f"   // 注意:{n} 為 Temp,TIA 不會自動清零,使用前請先指派")
                else:
                    pre.append(f"   {n} := {init or _SCL_ZERO.get(t.upper(), '0')};")
                init = None
            decl.append(f"      {n} : {t}" + (f" := {init}" if init else "") + ";")
        decl.append("   END_VAR")
    body = "\n".join(pre + [_scl_calls(p["body"], funcs)])
    return (f'FUNCTION "{p["name"]}" : {_scl_quote(": " + p["rtype"], names)[2:]}\n'
            f"{{ S7_Optimized_Access := 'TRUE' }}\nVERSION : 0.1\n"
            f'{_scl_quote(chr(10).join(decl), names)}\nBEGIN\n{body}\nEND_FUNCTION\n')


def _scl_addr(a):
    """IEC 位址 → TIA 寫法:位元位址不寫 X(%IX0.0 → %I0.0),其餘相同。"""
    return re.sub(r"^(%[IQM])X", r"\1", a.upper())


_SCL_TAGTYPE = {"BOOL": "Bool", "SINT": "SInt", "USINT": "USInt", "BYTE": "Byte", "INT": "Int", "UINT": "UInt",
                "WORD": "Word", "DINT": "DInt", "UDINT": "UDInt", "DWORD": "DWord", "REAL": "Real", "TIME": "Time",
                "LINT": "LInt", "ULINT": "ULInt", "LREAL": "LReal"}


def _cut_stmt(text, pattern):
    """在遮罩文字上找到 pattern,從原文刪除同一區間(註解/字串內不比對)。"""
    m = re.search(pattern, _views(text)[1], re.I | re.S)
    return (text[:m.start()] + text[m.end():]) if m else text


def _scl_block(p, names):
    """FB / OB 的宣告原文與本體前置敘述:直接位址變數移出(改為 PLC 變數表)、VAR_TEMP 初值移到本體開頭、
    PERSISTENT → RETAIN、引用常數的陣列邊界展開為數字。回傳 (decl, pre, tags=[(name, type, addr, init)])。"""
    text, tags, where = p["decl"], [], p["name"]
    for kind, decls in p["blocks"]:
        for n, t, init in decls:
            if n in kind.addrs:
                if p["kind"] != "program":
                    raise STError(f"export scl: FUNCTION_BLOCK {where} 內不可宣告直接位址(AT),請移到 PROGRAM")
                tags.append((n, t, kind.addrs[n], init))
                text = _cut_stmt(text, rf"[ \t]*\b{re.escape(n)}\s+AT\s+%[\w.]+\s*:[^;]*;[ \t]*\n?")
    pre = _temp_init(p["blocks"], where, "TIA 不保證清零")
    masked = _views(text)[1]
    for b in reversed(list(_BLOCK.finditer(masked))):  # VAR_TEMP 不能帶初值:移除 `:= 值`
        if b.group(1).upper() != "VAR_TEMP":
            continue
        a, e = b.span(3)
        for m in reversed(list(re.finditer(r":=[^;]*(?=;)", masked[a:e]))):
            text = text[:a + m.start()].rstrip() + text[a + m.end():]
    def header(m):
        mods = []
        for w in m.group(2).upper().split():
            w = "RETAIN" if w == "PERSISTENT" else w
            if w not in mods:
                mods.append(w)
        return m.group(1) + "".join(" " + w for w in mods)
    masked = _views(text)[1]
    for m in reversed(list(re.finditer(r"\b(VAR\w*)((?:\s+(?:CONSTANT|RETAIN|NON_RETAIN|PERSISTENT)\b)+)", masked, re.I))):
        text = text[:m.start()] + header(m) + text[m.end():]
    text = re.sub(r"\bVAR\w*(?:[ \t]+\w+)*\s*END_VAR[ \t]*\n?", "", text, flags=re.I)  # 清掉變空的區段
    text = _expand_text(text, where, _consts(p["blocks"], where))
    return _scl_quote(text.strip(), names), pre, tags


def _scl_tagrefs(body, tags):
    """本體中引用 PLC 變數表變數處加雙引號(`start` → `"start"`);FB 呼叫的具名參數(`IN := …`)不動。"""
    if not tags:
        return body
    masked = _views(body)[1]
    pat = re.compile(r'(?<![\w.#"])(' + "|".join(re.escape(t[0]) for t in tags) + r')(?![\w"])', re.I)
    out, pos = [], 0
    for m in pat.finditer(masked):
        before, after = masked[:m.start()].rstrip(), masked[m.end():].lstrip()
        if before[-1:] in ("(", ",") and (after.startswith(":=") or after.startswith("=>")):
            continue
        out.append(body[pos:m.start()] + f'"{body[m.start():m.end()]}"')
        pos = m.end()
    return "".join(out) + body[pos:]


def to_scl(src):
    """Siemens TIA(SCL 外部來源檔 .scl):TYPE STRUCT → UDT、FUNCTION → FC、FUNCTION_BLOCK → FB、
    PROGRAM → ORGANIZATION_BLOCK;依原始順序輸出(被呼叫者在前)。"""
    pous = split_pous(src)
    names, types = _scl_types(src)
    names = names + [p["name"] for p in pous if p["kind"] == "fb"]
    funcs = {p["name"].lower(): (p["name"], [n for k, d in p["blocks"] if k in ("VAR_INPUT", "VAR_IN_OUT") for n, _, _ in d])
             for p in pous if p["kind"] == "function"}
    out = [types] if types else []
    for p in pous:
        if p["kind"] == "function":
            out.append(_scl_function(p, names, funcs))
            continue
        block = "FUNCTION_BLOCK" if p["kind"] == "fb" else "ORGANIZATION_BLOCK"
        decl, pre, tags = _scl_block(p, names)
        body = "\n".join(pre + [_scl_tagrefs(_scl_calls(p["body"], funcs), tags)])
        if tags:
            head = ["// === PLC 變數表(PLC tags):匯入本檔前,請先在 TIA Portal 建立下列變數 ===",
                    "// Name\tData Type\tLogical Address"]
            for n, t, a, init in tags:
                head.append(f'// {n}\t{_SCL_TAGTYPE.get(t.upper(), t)}\t{_scl_addr(a)}'
                            + (f"\t(初始值 {init} 未匯出:PLC 變數無初值)" if init else ""))
            out.insert(0, "\n".join(head) + "\n")
        out.append(f'{block} "{p["name"]}"\n{{ S7_Optimized_Access := \'TRUE\' }}\nVERSION : 0.1\n'
                   f'{decl}\nBEGIN\n{body}\nEND_{block}\n')
    return "\n".join(out)


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


def _l5x_data(dt, src_type, init):
    """純量字面量初值 → L5X <Data Format="Decorated">;無法表示(運算式/字串等)回傳 None。"""
    v = (init or "").strip()
    if not v:
        return None
    v = re.sub(r"(?i)^[A-Z]+#(?=[\d\-+TF]|16#|8#|2#)", "", v) if not re.match(r"(?i)T(IME)?#", v) else v
    try:
        if dt == "BOOL":
            val = {"TRUE": "1", "FALSE": "0", "1": "1", "0": "0"}[v.upper()]
        elif src_type.upper() == "TIME":
            if not re.fullmatch(r"(?i)T(IME)?#[\w.\-]+", v):
                return None
            val = str(parse_time(v))
        elif dt == "REAL":
            val = repr(float(v.replace("_", "")))
        elif dt in ("SINT", "INT", "DINT", "LINT"):
            m = re.fullmatch(r"(-?)\s*(?:(2|8|16)#)?([0-9A-Fa-f_]+)", v)
            if not m or (not m.group(2) and not m.group(3).replace("_", "").isdigit()):
                return None
            val = str(int(m.group(3).replace("_", ""), int(m.group(2) or 10)) * (-1 if m.group(1) else 1))
        else:
            return None
    except (KeyError, ValueError):
        return None
    radix = "Float" if dt == "REAL" else "Decimal"
    return f'<Data Format="Decorated"><DataValue DataType="{dt}" Radix="{radix}" Value="{val}"/></Data>'


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
    consts = _consts(blocks, name)
    pre = _temp_init(blocks, name, "Logix 區域標籤會保留上一次掃描的值")
    for kind, decls in blocks:
        usage = {"VAR_INPUT": "Input", "VAR_OUTPUT": "Output", "VAR_IN_OUT": "InOut"}.get(kind, "Local")
        const = "CONSTANT" in kind.mods
        for n, t, init in decls:
            dimattr = ""
            src_type = t
            arr = _array_type(t, n, consts)
            if arr:
                rs, t = arr
                if len(rs) > 3 or any(lo != 0 for lo, _ in rs):
                    raise STError(f"export l5x: 標籤 {n} 陣列須 ≤3 維且下界為 0(Logix 陣列從 0 起算)")
                # Tag 的 Dimensions 以空白分隔(例 "2 3");尚未以 Studio 5000 實機匯入確認,見 docs/test_report_M29.md
                dimattr = ' Dimensions="' + " ".join(str(hi + 1) for _, hi in rs) + '"'
            dt = _L5X_TYPE.get(t.upper(), t.upper() if t.upper() in _BASE else t)
            # 純量字面量初值寫入 <Data>(VAR_TEMP 的初值改由本體開頭指派);尚未以 Studio 5000 實機匯入確認
            data = None if arr or kind == "VAR_TEMP" else _l5x_data(dt, src_type, init)
            if const and data is None:
                raise STError(f"export l5x: 常數 {n} 的值 {init!r} 無法寫入標籤(僅支援純量字面量),"
                              "匯出後常數會變成 0,請改為字面量或改用 plcopen / st")
            desc = (f"<Description><![CDATA[IEC address {kind.addrs[n]}: alias this tag to the module point]]></Description>"
                    if n in kind.addrs else "")
            head = (f'<Tag Name={quoteattr(n)} TagType="Base" DataType={quoteattr(dt)}{dimattr} '
                    f'Usage={quoteattr(usage)} Constant="{"true" if const else "false"}" ExternalAccess="Read/Write"')
            o.append(head + (f">{desc}{data or ''}</Tag>" if desc or data else "/>"))
    o += ["</Tags><Routines>", '<Routine Name="MainRoutine" Type="ST"><STContent>']
    for i, line in enumerate(pre + body.splitlines()):
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
    consts = _consts(blocks, name)
    located = any(kind.addrs for kind, _ in blocks)
    if located:  # MELSEC 裝置編號(X/Y 為 16 或 8 進位)無法由 IEC 位址可靠換算,列出原位址由使用者指定裝置
        o[-1] += "\tIEC Address (assign a device: X / Y / M / D)"
    for kind, decls in blocks:
        cls = _MELSEC_CLASS.get(kind, "VAR")
        if "CONSTANT" in kind.mods:
            cls += "_CONSTANT"
        elif kind.mods & {"RETAIN", "PERSISTENT"}:
            cls += "_RETAIN"
        for n, t, init in decls:
            dt = _MELSEC_TYPE.get(t.upper(), _expand(t, n, consts))
            o.append(f"{cls}\t{n}\t{dt}\t{'' if kind == 'VAR_TEMP' else init or ''}"
                     + (f"\t{kind.addrs.get(n, '')}" if located else ""))
    o += ["(* === ST Program Body === *)", *_temp_init(blocks, name, "GX Works3 的 VAR 會保留上一次掃描的值"), body, ""]
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
    consts = _consts(blocks, name)
    extra = any(kind.addrs or kind.mods for kind, _ in blocks)
    if extra:  # Sysmac 的 I/O 由 I/O Map 指定,IEC 位址僅供對照
        o[-1] += "\tRetain\tConstant\tIEC Address (assign in I/O Map)"
    for kind, decls in blocks:
        for n, t, init in decls:
            t = _expand(t, n, consts)
            o.append(f"{n}\t{_OMRON_TYPE.get(t.upper(), t.upper() if t.upper() in _BASE else t)}"
                     f"\t{'' if kind == 'VAR_TEMP' else init or ''}\t{_OMRON_CLASS.get(kind, 'Internal')}"
                     + (f"\t{'TRUE' if kind.mods & {'RETAIN', 'PERSISTENT'} else 'FALSE'}"
                        f"\t{'TRUE' if 'CONSTANT' in kind.mods else 'FALSE'}\t{kind.addrs.get(n, '')}" if extra else ""))
    o += ["(* === ST Program Body === *)", *_temp_init(blocks, name, "Sysmac 的內部變數會保留上一次掃描的值"), body, ""]
    return "\n".join(o)


FORMATS = {"plcopen": ("xml", to_plcopen), "scl": ("scl", to_scl), "l5x": ("L5X", to_l5x),
           "gxworks": ("txt", to_gxworks),
           "sysmac": ("txt", to_sysmac), "st": ("st", lambda s: s)}


_USERPOU = re.compile(r"^\s*(?:FUNCTION(?:_BLOCK)?\s+\w+|TYPE\s+\w+\s*:)", re.M | re.I)

_FUNCPOU = re.compile(r"^\s*FUNCTION(?:_BLOCK)?\s+\w+", re.M | re.I)


def export(src, fmt):
    masked = _views(src)[1]
    if fmt in ("gxworks", "sysmac") and _USERPOU.search(masked):
        raise STError(f"export {fmt}: 含自訂 FUNCTION/FUNCTION_BLOCK/TYPE(STRUCT),此格式尚未支援(僅 st 格式可完整匯出)")
    if fmt == "l5x" and _FUNCPOU.search(masked):
        raise STError("export l5x: 含自訂 FUNCTION/FUNCTION_BLOCK;Logix 須以 Add-On Instruction 實作,尚未支援"
                      "(可改用 plcopen / scl / st 匯出)")
    try:
        return FORMATS[fmt][1](src)
    except KeyError:
        raise STError(f"unknown export format {fmt!r}; available: {', '.join(FORMATS)}") from None
