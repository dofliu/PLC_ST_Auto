"""匯出:PLCopen XML(TC6 v2.01,CODESYS/Beckhoff/多數工具可匯入)、Siemens SCL(.scl)、純文字 ST。

以文字層級切分 PROGRAM(宣告區 / 本體),不改動使用者程式邏輯。"""
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
            typ = f"<{t.upper()}/>" if t.upper() in _BASE else f"<derived name={quoteattr(t)}/>"
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


def to_scl(src):
    """Siemens TIA:PROGRAM → ORGANIZATION_BLOCK(SCL 外部來源檔 .scl)。"""
    name, _, decl, body = split_program(src)
    return (f'ORGANIZATION_BLOCK "{name}"\n{{ S7_Optimized_Access := \'TRUE\' }}\nVERSION : 0.1\n'
            f"{decl}\nBEGIN\n{body}\nEND_ORGANIZATION_BLOCK\n")


FORMATS = {"plcopen": ("xml", to_plcopen), "scl": ("scl", to_scl), "st": ("st", lambda s: s)}


def export(src, fmt):
    try:
        return FORMATS[fmt][1](src)
    except KeyError:
        raise STError(f"unknown export format {fmt!r}; available: {', '.join(FORMATS)}") from None
