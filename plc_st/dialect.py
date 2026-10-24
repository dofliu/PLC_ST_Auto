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
    fb_names = {n.upper() for n in FB_TYPES}
    in_var = False
    names = []  # declared names awaiting their ':' (handles `a, b : INT`)
    after_colon = False
    for k, v, ln in toks:
        if k == "kw" and v.startswith("VAR"):
            in_var, names, after_colon = True, [], False
        elif k == "kw" and v == "END_VAR":
            in_var = False
        elif in_var:
            if k == "op" and v == ":":
                after_colon = True
                for nm, nl in names:
                    up = nm.upper()
                    if up in _IEC_NAMES:
                        warn(nl, f"variable {nm} shadows a standard function/type name; rename it for portability")
                    elif up in reserved:
                        warn(nl, f"variable {nm} is reserved on {fam}")
                    elif fam == "mitsubishi" and _DEVICE.match(nm):
                        warn(nl, f"label {nm} looks like a MELSEC device address; GX Works rejects it")
            elif k == "op" and v == ";":
                names, after_colon = [], False
            elif k == "id" and not after_colon:
                names.append((v, ln))
            elif k == "id" and fam == "rockwell" and v.upper() in fb_names:
                warn(ln, f"Logix has no IEC {v.upper()} block; use TIMER/COUNTER tags with TONR/CTU instructions")
        if fam == "rockwell":
            if k == "time":
                warn(ln, "Logix has no T# literal; use DINT milliseconds")
            elif k == "op" and v == "**":
                warn(ln, "Logix uses XPY(a, b) instead of **")
    return out
