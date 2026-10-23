"""Vendor dialect hints: warnings for ST that is valid IEC but risky on a target platform.

Rules are conservative approximations; they never produce errors.
"""
import re

from .interpreter import FB_TYPES, FUNCS
from .lexer import tokenize

_IEC_NAMES = set(FUNCS) | {n.upper() for n in FB_TYPES} | {
    "INT", "DINT", "REAL", "BOOL", "TIME", "STRING", "BYTE", "WORD", "DWORD",
}
# identifiers a given platform rejects or treats specially (extra to _IEC_NAMES)
_RESERVED = {
    "codesys": {"THIS", "SUPER", "POINTER", "REFERENCE", "METHOD", "PROPERTY", "INTERFACE", "ADR", "SIZEOF"},
    "siemens": {"DB", "FC", "FB", "OB", "DATE", "TOD", "DT", "ANY", "VARIANT", "REGION"},
    "rockwell": {"TIMER", "COUNTER", "CONTROL", "MESSAGE", "AXIS"},
}
_DEVICE = re.compile(r"^[XYMDLFVBSTCRZW][0-9A-F]+$", re.I)  # MELSEC device labels like X0, D100


def _family(profile):
    return profile.split("-")[0]


def dialect_issues(src, profile):
    """Return (line, message) warnings for `profile`; empty for generic profiles."""
    fam = _family(profile)
    toks = tokenize(src)
    out = []
    seen = set()

    def warn(ln, msg):
        if (ln, msg) not in seen:
            seen.add((ln, msg))
            out.append((ln, msg))

    reserved = _RESERVED.get(fam, set())
    in_var = False
    for i, (k, v, ln) in enumerate(toks):
        if k == "kw" and v.startswith("VAR"):
            in_var = True
        elif k == "kw" and v == "END_VAR":
            in_var = False
        if k == "id" and in_var and i + 1 < len(toks) and toks[i + 1][1] == ":":
            up = v.upper()
            if up in _IEC_NAMES:
                warn(ln, f"variable {v} shadows a standard function/type name; rename it for portability")
            elif up in reserved:
                warn(ln, f"variable {v} is reserved on {fam}")
            elif fam == "mitsubishi" and _DEVICE.match(v):
                warn(ln, f"label {v} looks like a MELSEC device address; GX Works rejects it")
        if fam == "rockwell":
            if k == "time":
                warn(ln, "Logix has no T# literal; use DINT milliseconds")
            elif k == "op" and v == "**":
                warn(ln, "Logix uses XPY(a, b) instead of **")
            elif k == "id" and v in FB_TYPES and in_var:
                warn(ln, f"Logix has no IEC {v} block; use TIMER/COUNTER tags with TONR/CTU instructions")
    return out
