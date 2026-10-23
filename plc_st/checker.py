"""Static checker: undeclared names, type mismatches, writes to inputs, profile limits."""
from dataclasses import dataclass

from .dialect import dialect_issues
from .interpreter import FB_TYPES, FUNCS, INT_RANGES
from .lexer import STError
from .parser import parse
from .profiles import get_profile

_NUM = set(INT_RANGES) | {"REAL", "LREAL"}


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warning"
    line: int  # 0 when unknown
    msg: str

    def __str__(self):
        loc = f"line {self.line}: " if self.line else ""
        return f"{self.severity}: {loc}{self.msg}"


def _kind(t):
    if t == "BOOL":
        return "bool"
    if t in _NUM:
        return "num"
    return t  # TIME / STRING / FB name / None (unknown)


def check(src, profile="iec"):
    """Return a list of Issue; a parse failure is reported as a single error."""
    prof = get_profile(profile)
    try:
        prog = parse(src)
    except STError as e:
        return [Issue("error", 0, f"syntax: {e}")]
    issues = []
    env = {}
    for d in prog["decls"]:
        if d["name"].lower() in env:
            issues.append(Issue("error", 0, f"duplicate declaration {d['name']}"))
        env[d["name"].lower()] = d
        t = d["type"]
        if t not in FB_TYPES and t not in prof.types:
            issues.append(Issue("error", 0, f"type {t} of {d['name']} not supported by profile {prof.name}"))

    def err(ln, msg, sev="error"):
        issues.append(Issue(sev, ln, msg))

    def ty(e, ln):
        """Infer the expression's type name (None if unknown)."""
        k = e[0]
        if k == "num":
            return "REAL" if isinstance(e[1], float) else "INT"
        if k == "bool":
            return "BOOL"
        if k == "time":
            return "TIME"
        if k == "str":
            return "STRING"
        if k == "var":
            d = env.get(e[1].lower())
            if d is None:
                err(ln, f"undeclared variable {e[1]}")
                return None
            return d["type"]
        if k == "member":
            return member(e, ln)
        if k == "not":
            return ty(e[1], ln)
        if k == "neg":
            return ty(e[1], ln)
        if k == "bin":
            a, b = ty(e[2], ln), ty(e[3], ln)
            op = e[1]
            if op in ("=", "<>", "<", ">", "<=", ">="):
                return "BOOL"
            if op in ("AND", "OR", "XOR"):
                for t in (a, b):
                    if t is not None and _kind(t) not in ("bool", "num"):
                        err(ln, f"operator {op} applied to {t}")
                return "BOOL" if a == b == "BOOL" else a
            if op in ("+", "-", "*", "/", "MOD", "**"):
                if "BOOL" in (a, b):
                    err(ln, f"arithmetic {op} on BOOL")
                return "REAL" if "REAL" in (a, b) or "LREAL" in (a, b) else (a or b)
            return None
        if k == "func":
            if e[1].upper() not in FUNCS:
                err(ln, f"unknown function {e[1]}")
            for _, _, v in e[2]:
                ty(v, ln)
            return None
        return None

    def member(e, ln):
        base = e[1]
        if base[0] != "var":
            return None
        d = env.get(base[1].lower())
        if d is None:
            err(ln, f"undeclared variable {base[1]}")
            return None
        fb = FB_TYPES.get(d["type"])
        if fb is None:
            err(ln, f"{base[1]} is {d['type']}, has no member {e[2]}")
            return None
        outs = {**fb.inputs_t, **fb.outputs_t}
        m = {k.upper(): t for k, t in outs.items()}.get(e[2].upper())
        if m is None:
            err(ln, f"{d['type']} has no member {e[2]}")
        return m

    def assign(target, e, ln):
        tt = ty(target, ln)
        if target[0] == "var":
            d = env.get(target[1].lower())
            if d and d["section"] == "input":
                err(ln, f"write to input variable {target[1]}", "warning")
            if d and d["type"] in FB_TYPES:
                err(ln, f"cannot assign to function block instance {target[1]}")
                return
        et = ty(e, ln)
        if tt is None or et is None:
            return
        kt, ke = _kind(tt), _kind(et)
        if kt != ke:
            err(ln, f"type mismatch: {et} assigned to {tt}")
        elif tt in INT_RANGES and et in ("REAL", "LREAL"):
            err(ln, f"REAL assigned to {tt} needs explicit conversion", "warning")

    def stmts(body):
        for s in body:
            k = s[0]
            if k == "assign":
                assign(s[1], s[2], s[3])
            elif k == "call":
                call(s)
            elif k == "if":
                for c, b in s[1]:
                    cond(c)
                    stmts(b)
                stmts(s[2])
            elif k == "case":
                ty(s[1], 0)
                for _, b in s[2]:
                    stmts(b)
                stmts(s[3])
            elif k == "for":
                ty(("var", s[1]), 0)
                for x in s[2:5]:
                    ty(x, 0)
                stmts(s[5])
            elif k == "while":
                cond(s[1])
                stmts(s[2])
            elif k == "repeat":
                stmts(s[1])
                cond(s[2])

    def cond(c):
        t = ty(c, 0)
        if t is not None and _kind(t) != "bool":
            err(0, f"condition is {t}, expected BOOL", "warning")

    def call(s):
        ln = s[3]
        tgt = s[1]
        d = env.get(tgt[1].lower()) if tgt[0] == "var" else None
        if d is None or d["type"] not in FB_TYPES:
            err(ln, f"call target {tgt[1] if tgt[0] == 'var' else '?'} is not a declared function block")
            return
        fb = FB_TYPES[d["type"]]
        ins = {k.upper() for k in fb.inputs_t}
        outs = {k.upper() for k in fb.outputs_t}
        for name, op, v in s[2]:
            ty(v, ln)
            if name and name.upper() not in (outs if op == "=>" else ins):
                err(ln, f"{d['type']} has no {'output' if op == '=>' else 'input'} {name}")

    stmts(prog["body"])
    issues += [Issue("warning", ln, f"dialect: {m}") for ln, m in dialect_issues(src, prof.name)]
    return issues
