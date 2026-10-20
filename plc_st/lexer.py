"""ST lexer. Identifiers/keywords are case-insensitive; times are ms ints."""
import re

class STError(Exception):
    pass

KEYWORDS = {
    "PROGRAM", "END_PROGRAM", "VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT",
    "END_VAR", "IF", "THEN", "ELSIF", "ELSE", "END_IF", "CASE", "OF", "END_CASE",
    "FOR", "TO", "BY", "DO", "END_FOR", "WHILE", "END_WHILE", "REPEAT", "UNTIL",
    "END_REPEAT", "EXIT", "AND", "OR", "XOR", "NOT", "MOD", "TRUE", "FALSE",
    "RETAIN", "CONSTANT",
}

_TIME_UNITS = {"d": 86400000, "h": 3600000, "m": 60000, "s": 1000, "ms": 1}
_TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<bcomment>\(\*.*?\*\))
  | (?P<lcomment>//[^\n]*)
  | (?P<time>[Tt](?:[Ii][Mm][Ee])?\#(?:-?\d+(?:\.\d+)?(?:ms|d|h|m|s))+)
  | (?P<real>\d+\.\d+(?:[eE][+-]?\d+)?)
  | (?P<int>\d+)
  | (?P<str>'[^']*')
  | (?P<id>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<op>:=|=>|<>|<=|>=|\*\*|[-+*/=<>():;,.\[\]])
""", re.X | re.S)


def parse_time(text):
    body = text.split("#", 1)[1]
    total = 0.0
    for num, unit in re.findall(r"(-?\d+(?:\.\d+)?)(ms|d|h|m|s)", body):
        total += float(num) * _TIME_UNITS[unit]
    return int(round(total))


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
            toks.append(("num", int(text), line))
        elif kind == "real":
            toks.append(("num", float(text), line))
        elif kind == "time":
            toks.append(("time", parse_time(text), line))
        elif kind == "str":
            toks.append(("str", text[1:-1], line))
        elif kind == "op":
            toks.append(("op", text, line))
        line += text.count("\n")
        pos = m.end()
    toks.append(("eof", None, line))
    return toks
