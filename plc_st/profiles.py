"""Vendor profiles: supported types and integer-overflow behaviour.

These are simplified approximations of each platform for pre-checking ST code,
not bit-exact emulation; see roadmap M3/M4 for dialect checks.
"""
from dataclasses import dataclass

from .lexer import STError

_SIGNED = {"SINT", "INT", "DINT", "LINT"}
_UNSIGNED = {"USINT", "UINT", "UDINT", "ULINT"}
_BITS = {"BYTE", "WORD", "DWORD"}
_BASE = {"BOOL", "REAL", "LREAL", "TIME", "STRING"}


@dataclass(frozen=True)
class Profile:
    name: str
    overflow: str  # "wrap" (two's complement) | "saturate" | "fault"
    types: frozenset
    note: str = ""


def _p(name, overflow, *groups, drop=(), note=""):
    ts = set().union(*groups) - set(drop)
    return Profile(name, overflow, frozenset(ts), note)


ALL = (_SIGNED, _UNSIGNED, _BITS, _BASE)
PROFILES = {p.name: p for p in (
    _p("iec", "wrap", *ALL, note="IEC 61131-3 generic (default)"),
    _p("codesys", "wrap", *ALL, note="CODESYS V3"),
    _p("siemens-s7-1200", "wrap", *ALL, drop=("LINT", "ULINT"), note="S7-1200: no 64-bit integers"),
    _p("siemens-s7-1500", "wrap", *ALL, note="S7-1500 SCL"),
    _p("rockwell", "wrap", _SIGNED, _BASE, drop=("TIME",), note="Logix: signed ints only, no TIME type"),
    _p("mitsubishi", "wrap", *ALL, drop=("LINT", "ULINT"), note="MELSEC iQ-F: no 64-bit integers"),
    _p("omron", "wrap", *ALL, note="Sysmac Studio"),
    _p("strict", "fault", *ALL, note="Faults on integer overflow; for catching latent bugs"),
    _p("saturate", "saturate", *ALL, note="Clamps on overflow (some drive/motion controllers)"),
)}


def get_profile(name):
    try:
        return PROFILES[name.lower()]
    except KeyError:
        raise STError(f"unknown profile {name!r}; available: {', '.join(PROFILES)}") from None
