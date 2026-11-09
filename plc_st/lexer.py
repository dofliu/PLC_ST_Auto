"""ST lexer. Identifiers/keywords are case-insensitive; times are ms ints."""
import re

class STError(Exception):
    pass

KEYWORDS = {
    "PROGRAM", "END_PROGRAM", "VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT",
    "END_VAR", "IF", "THEN", "ELSIF", "ELSE", "END_IF", "CASE", "OF", "END_CASE",
    "FOR", "TO", "BY", "DO", "END_FOR", "WHILE", "END_WHILE", "REPEAT", "UNTIL",
    "END_REPEAT", "EXIT", "AND", "OR", "XOR", "NOT", "MOD", "TRUE", "FALSE",
    "RETAIN", "CONSTANT", "ARRAY", "FUNCTION", "END_FUNCTION",
    "FUNCTION_BLOCK", "END_FUNCTION_BLOCK", "RETURN", "TYPE", "END_TYPE", "STRUCT", "END_STRUCT",
}

_TIME_UNITS = {"d": 86400000, "h": 3600000, "m": 60000, "s": 1000, "ms": 1}
_TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<bcomment>\(\*.*?\*\))
  | (?P<lcomment>//[^\n]*)
  | (?P<time>[Tt](?:[Ii][Mm][Ee])?\#(?:-?\d+(?:\.\d+)?(?:ms|d|h|m|s))+)
  | (?P<typed>(?:SINT|USINT|UINT|UDINT|ULINT|DINT|LINT|INT|LREAL|REAL|BOOL|BYTE|WORD|DWORD|LWORD)\#
      (?:TRUE|FALSE|(?:2|8|16)\#[0-9A-Fa-f_]+|-?\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?)(?![A-Za-z_0-9]))
  | (?P<based>(?:2|8|16)\#[0-9A-Fa-f][0-9A-Fa-f_]*)
  | (?P<real>\d[\d_]*\.\d[\d_]*(?:[eE][+-]?\d+)?)
  | (?P<int>\d[\d_]*)
  | (?P<str>'(?:\$.|[^'$])*')
  | (?P<id>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<op>:=|=>|<>|<=|>=|\*\*|\.\.|[-+*/=<>():;,.\[\]])
""", re.X | re.S)


def parse_time(text):
    body = text.split("#", 1)[1]
    total = 0.0
    for num, unit in re.findall(r"(-?\d+(?:\.\d+)?)(ms|d|h|m|s)", body):
        total += float(num) * _TIME_UNITS[unit]
    return int(round(total))


def _based(text):
    base, digits = text.split("#", 1)
    return int(digits.replace("_", ""), int(base))


def _num(text, real=False):
    """數值字面量文字(整數/實數/進位 16#FF)轉成 int 或 float。"""
    t = text.replace("_", "")
    if "#" in t:
        v = _based(t)
        return float(v) if real else v
    if real or "." in t or "e" in t.lower():
        return float(t)
    return int(t)


_ESC = {"$": "$", "'": "'", "L": "\n", "N": "\n", "P": "\f", "R": "\r", "T": "\t"}


def _unescape(body, line=0):
    """IEC 字串跳脫:$$ $' $L $N $P $R $T 與 $HH(十六進位字元)。"""
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "$":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1:i + 2]
        if nxt.upper() in _ESC:
            out.append(_ESC[nxt.upper()])
            i += 2
        elif re.fullmatch(r"[0-9A-Fa-f]{2}", body[i + 1:i + 3]):
            out.append(chr(int(body[i + 1:i + 3], 16)))
            i += 3
        else:
            raise STError(f"line {line}: invalid string escape ${nxt}")
    return "".join(out)


def tokenize(src):
    toks, pos, line = [], 0, 1
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m:
            raise STError(f"line {line}: unexpected character {src[pos]!r}")
        kind, text = m.lastgroup, m.group()
        if kind == "id":
            up = text.upper()
            if up in KEYWORDS:
                toks.append(("kw", up, line))
            else:
                toks.append(("id", text, line))
        elif kind == "int":
            toks.append(("num", _num(text), line))
        elif kind == "based":
            toks.append(("num", _based(text), line))
        elif kind == "real":
            toks.append(("num", _num(text), line))
        elif kind == "typed":
            prefix, val = text.split("#", 1)
            if prefix.upper() == "BOOL" and val in ("0", "1"):
                toks.append(("kw", "TRUE" if val == "1" else "FALSE", line))
            elif val.upper() in ("TRUE", "FALSE"):
                toks.append(("kw", val.upper(), line))
            else:
                toks.append(("num", _num(val, real=prefix.upper() in ("REAL", "LREAL")), line))
        elif kind == "time":
            toks.append(("time", parse_time(text), line))
        elif kind == "str":
            toks.append(("str", _unescape(text[1:-1], line), line))
        elif kind == "op":
            toks.append(("op", text, line))
        line += text.count("\n")
        pos = m.end()
    toks.append(("eof", None, line))
    return toks
