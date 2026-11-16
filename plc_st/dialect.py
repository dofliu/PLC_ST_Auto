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
# Logix 5000 Structured Text equivalents of IEC function blocks (used in rockwell warnings)
_LOGIX_EQUIV = {
    "TON": "use a TIMER tag with the TONR instruction",
    "TOF": "use a TIMER tag with the TOFR instruction",
    "TP": "no pulse-timer instruction; build it from TONR plus a one-shot (OSRI)",
    "CTU": "use a COUNTER tag with the CTUD instruction (CUEnable)",
    "CTD": "use a COUNTER tag with the CTUD instruction (CDEnable)",
    "CTUD": "use a COUNTER tag with the CTUD instruction",
    "R_TRIG": "use the OSRI (one shot rising with input) instruction with a FBD_ONESHOT tag",
    "F_TRIG": "use the OSFI (one shot falling with input) instruction with a FBD_ONESHOT tag",
    "RS": "write the latch as boolean logic, e.g. q := NOT reset1 AND (set OR q)",
    "SR": "write the latch as boolean logic, e.g. q := set1 OR (NOT reset AND q)",
}
# how each platform handles IEC direct addresses (AT %I/%Q/%M) and VAR_TEMP
_ADDR_HINT = {
    "rockwell": "Logix has no direct addresses; make the tag an alias of the module point (e.g. Local:1:I.Data.0)",
    "mitsubishi": "GX Works3 assigns devices (X0 / Y0 / M0 / D0) in the label table instead of %I/%Q/%M addresses",
    "omron": "Sysmac NJ/NX maps I/O through the I/O Map (device variables), not %I/%Q addresses",
}
_NO_TEMP = {
    "rockwell": "Logix has no VAR_TEMP; use a local tag and initialise it at the start of the routine",
    "mitsubishi": "GX Works3 has no VAR_TEMP label class; use VAR and initialise it every scan",
    "omron": "Sysmac Studio has no VAR_TEMP; use an internal variable and initialise it every scan",
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
    in_var = addr_seen = False
    names = []  # declared names awaiting their ':' (handles `a, b : INT`)
    after_colon = False
    for k, v, ln in toks:
        if k == "addr":
            if names and names[-1][0].upper() == "AT":
                names.pop()
            if fam in _ADDR_HINT and not addr_seen:
                warn(ln, f"direct address {v}: {_ADDR_HINT[fam]}")
            elif fam == "siemens":
                if re.match(r"%[IQM]X", v):
                    warn(ln, f"{v}: TIA Portal writes bit addresses without X ({v[:2]}{v[3:]})")
                if not addr_seen:
                    warn(ln, "in TIA Portal absolute addresses belong in the PLC tag table; "
                             "the SCL export moves located variables there")
            addr_seen = True
        elif k == "kw" and v == "PERSISTENT" and fam not in ("codesys", "iec"):
            warn(ln, "PERSISTENT is a CODESYS extension; use RETAIN or the platform's retentive setting")
        elif k == "kw" and v == "VAR_TEMP" and fam in _NO_TEMP:
            warn(ln, _NO_TEMP[fam])
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
                warn(ln, f"Logix has no IEC {v.upper()} block; {_LOGIX_EQUIV[v.upper()]}")
        if fam == "rockwell":
            if k == "time":
                warn(ln, "Logix has no T# literal; use DINT milliseconds")
            elif k == "op" and v == "**":
                warn(ln, "Logix uses XPY(a, b) instead of **")
    return out
