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
    ufn, ufb = prog["functions"], prog["fbs"]
    structs = prog.get("types", {})

    class _UFB:  # adapter so user FBs look like built-in FB classes
        def __init__(self, d):
            self.inputs_t = {x["name"]: x["type"] for x in d["decls"] if x["section"] in ("input", "inout")}
            self.outputs_t = {x["name"]: x["type"] for x in d["decls"] if x["section"] == "output"}

    def fb_of(t):
        if t in FB_TYPES:
            return FB_TYPES[t]
        if t.lower() in ufb:
            return _UFB(ufb[t.lower()])
        return None

    def load_scope(decls):
        env.clear()
        for d in decls:
            if d["name"].lower() in env:
                issues.append(Issue("error", 0, f"duplicate declaration {d['name']}"))
            env[d["name"].lower()] = d
            t = d["type"]
            if t.lower() in structs:
                struct_types(t, d["name"], ())
            elif fb_of(t) is None and t not in prof.types:
                issues.append(Issue("error", 0, f"type {t} of {d['name']} not supported by profile {prof.name}"))

    def struct_types(t, owner, stack):
        sd = structs[t.lower()]
        if t.lower() in stack:
            issues.append(Issue("error", 0, f"recursive STRUCT {sd['name']}"))
            return
        for f in sd["fields"]:
            ft = f["type"]
            if ft.lower() in structs:
                struct_types(ft, owner, stack + (t.lower(),))
            elif ft not in INT_RANGES and ft not in ("BOOL", "REAL", "LREAL", "TIME", "STRING"):
                issues.append(Issue("error", 0, f"unknown type {ft} in STRUCT {sd['name']}"))
            elif ft not in prof.types:
                issues.append(Issue("error", 0, f"type {ft} of {owner}.{f['name']} not supported by profile {prof.name}"))

    load_scope(prog["decls"])

    def err(ln, msg, sev="error"):
        if not any(i.line == ln and i.msg == msg and i.severity == sev for i in issues):
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
            if d.get("array"):
                err(ln, f"array {e[1]} used without index")
                return None
            if d["type"].lower() in structs:
                err(ln, f"STRUCT {e[1]} used without member")
                return None
            return d["type"]
        if k == "index":
            chain, b = [], e
            while b[0] == "index":
                chain.append(b[2])
                b = b[1]
            chain.reverse()
            for ie in chain:
                it = ty(ie, ln)
                if it is not None and it not in INT_RANGES:
                    err(ln, f"array index must be an integer, got {it}")
            d = env.get(b[1].lower()) if b[0] == "var" else None
            if d is None:
                if b[0] == "var":
                    err(ln, f"undeclared variable {b[1]}")
                return None
            if not d.get("array"):
                err(ln, f"{b[1]} is not an array")
                return None
            dims = d.get("dims") or [d["array"]]
            if len(chain) != len(dims):
                err(ln, f"{b[1]} needs {len(dims)} index(es), got {len(chain)}")
                return None
            for (lo, hi), ie in zip(dims, chain):
                if ie[0] == "num" and lo[0] == hi[0] == "num" and not lo[1] <= ie[1] <= hi[1]:
                    err(ln, f"array index {ie[1]} out of range [{lo[1]}..{hi[1]}] for {b[1]}")
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
            uf = ufn.get(e[1].lower())
            if uf:
                ins = [x["name"].lower() for x in uf["decls"] if x["section"] in ("input", "inout")]
                pos = 0
                for nm, op, v in e[2]:
                    ty(v, ln)
                    if op == "=>":
                        continue
                    if nm is None:
                        pos += 1
                    elif nm.lower() not in ins:
                        err(ln, f"function {uf['name']} has no input {nm}")
                if pos > len(ins):
                    err(ln, f"too many arguments for function {uf['name']}")
                return uf["type"]
            if e[1].upper() not in FUNCS:
                err(ln, f"unknown function {e[1]}")
            for _, _, v in e[2]:
                ty(v, ln)
            return None
        return None

    def struct_field(t, name, ln, _owner):
        sd = structs.get(t.lower())
        if sd is None:
            err(ln, f"{t} has no member {name}")
            return None
        for f in sd["fields"]:
            if f["name"].lower() == name.lower():
                return f["type"]
        err(ln, f"STRUCT {sd['name']} has no field {name}")
        return None

    def member(e, ln):
        base = e[1]
        if base[0] == "index":
            bt = ty(base, ln)
            if bt and bt.lower() in structs:
                return struct_field(bt, e[2], ln, "")
            if bt:
                err(ln, f"{bt} element has no member {e[2]}")
            return None
        if base[0] == "member":
            bt = member(base, ln)
            return struct_field(bt, e[2], ln, "") if bt else None
        if base[0] != "var":
            return None
        d = env.get(base[1].lower())
        if d is None:
            err(ln, f"undeclared variable {base[1]}")
            return None
        if d["type"].lower() in structs:
            return struct_field(d["type"], e[2], ln, base[1])
        fb = fb_of(d["type"])
        if fb is None:
            err(ln, f"{base[1]} is {d['type']}, has no member {e[2]}")
            return None
        outs = {**fb.inputs_t, **fb.outputs_t}
        m = {k.upper(): t for k, t in outs.items()}.get(e[2].upper())
        if m is None:
            err(ln, f"{d['type']} has no member {e[2]}")
        return m

    def stype(x, ln):
        if x[0] == "var":
            d = env.get(x[1].lower())
            if d and not d.get("array") and d["type"].lower() in structs:
                return d["type"].lower()
        elif x[0] in ("member", "index"):
            t = member(x, ln) if x[0] == "member" else ty(x, ln)
            if t and t.lower() in structs:
                return t.lower()
        return None

    def assign(target, e, ln):
        st = stype(target, ln)
        if st:
            if stype(e, ln) != st:
                err(ln, f"STRUCT {structs[st]['name']} can only be assigned a STRUCT of the same type")
            return
        tt = ty(target, ln)
        if target[0] == "var":
            d = env.get(target[1].lower())
            if d and d["section"] == "input":
                err(ln, f"write to input variable {target[1]}", "warning")
            if d and d.get("array"):
                err(ln, f"cannot assign whole array {target[1]}; use {target[1]}[i]")
                return
            if d and fb_of(d["type"]) is not None:
                err(ln, f"cannot assign to function block instance {target[1]}")
                return
            if d and d["type"].lower() in structs:
                err(ln, f"cannot assign whole STRUCT {target[1]}; assign its fields")
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
        fb = fb_of(d["type"]) if d else None
        if fb is None and d is None and tgt[0] == "var" and tgt[1].lower() in ufn:
            ty(("func", tgt[1], s[2]), ln)  # user function called as a statement
            return
        if fb is None:
            err(ln, f"call target {tgt[1] if tgt[0] == 'var' else '?'} is not a declared function block")
            return
        ins = {k.upper() for k in fb.inputs_t}
        outs = {k.upper() for k in fb.outputs_t}
        for name, op, v in s[2]:
            ty(v, ln)
            if name and name.upper() not in (outs if op == "=>" else ins):
                err(ln, f"{d['type']} has no {'output' if op == '=>' else 'input'} {name}")

    stmts(prog["body"])
    for fn in list(ufn.values()) + list(ufb.values()):
        decls = list(fn["decls"])
        if fn["kind"] == "function":
            if fn["type"] not in prof.types:
                err(0, f"return type {fn['type']} of {fn['name']} not supported by profile {prof.name}")
            decls.append({"name": fn["name"], "type": fn["type"], "section": "local", "init": None, "array": None})
        load_scope(decls)
        stmts(fn["body"])
    issues += [Issue("warning", ln, f"dialect: {m}") for ln, m in dialect_issues(src, prof.name)]
    return issues
