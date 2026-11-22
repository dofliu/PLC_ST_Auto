"""Static checker: undeclared names, type mismatches, writes to inputs, profile limits."""
import re
from dataclasses import dataclass

from .dialect import dialect_issues
from .interpreter import FB_TYPES, FUNCS, INT_RANGES
from .lexer import STError
from .parser import parse, parse_addr
from .profiles import get_profile

_NUM = set(INT_RANGES) | {"REAL", "LREAL"}
_BITS = {"BOOL": 1, "SINT": 8, "USINT": 8, "BYTE": 8, "INT": 16, "UINT": 16, "WORD": 16,
         "DINT": 32, "UDINT": 32, "DWORD": 32, "REAL": 32, "TIME": 32,
         "LINT": 64, "ULINT": 64, "LWORD": 64, "LREAL": 64}


def _addr_issues(decls, prof, in_pou=None):
    """直接位址(AT %I/%Q/%M)檢查:大小與型別相符、位址重疊;CONSTANT 需有初值。"""
    out, used = [], []
    byte_addr = prof.name.split("-")[0] == "siemens"  # S7:%IW1 = byte 1..2;IEC/CODESYS:%IW1 = word 1
    consts = {d["name"].lower(): d for d in decls if d.get("const") and d.get("init") is not None and not d.get("array")}

    def cval(x):
        if x[0] == "var" and x[1].lower() in consts:
            return cval(consts[x[1].lower()]["init"])
        if x[0] == "neg":
            v = cval(x[1])
            return None if v is None else -v
        return _lit(x)

    def count(d):
        """陣列元素總數(邊界無法靜態求值時回傳 None)。"""
        n = 1
        for lo, hi in d.get("dims") or [d["array"]]:
            a, b = cval(lo), cval(hi)
            if a is None or b is None:
                return None
            n *= max(b - a + 1, 0)
        return n

    for d in decls:
        ln = d.get("line", 0)
        if d.get("const") and d.get("init") is None:
            out.append(Issue("warning", ln, f"CONSTANT {d['name']} has no initial value"))
        if d.get("const") and d.get("addr"):
            out.append(Issue("error", ln, f"CONSTANT {d['name']} cannot have a direct address"))
        if not d.get("addr"):
            continue
        a = parse_addr(d["addr"])
        if in_pou:
            out.append(Issue("warning", ln, f"direct address {d['addr']} inside {in_pou}: located variables "
                                            "belong in PROGRAM (or global) declarations"))
        if d["section"] == "temp":
            out.append(Issue("error", ln, f"VAR_TEMP {d['name']} cannot have a direct address"))
        tb = _BITS.get(d["type"])
        if tb is None:
            out.append(Issue("error", ln, f"{d['name']}: type {d['type']} cannot be placed at {d['addr']}"))
        elif tb != a["bits"]:
            out.append(Issue("error", ln, f"{d['name']}: {d['type']} ({tb} bit) does not fit address "
                                          f"{d['addr']} ({a['bits']} bit)"))
        if a["size"] == "X":
            start = a["index"] * 8 + (a["bit"] or 0)
        else:
            start = a["index"] * (8 if byte_addr else a["bits"])
        is_arr = bool(d.get("array"))
        # 陣列從起始位址連續佔用「元素數 × 元素位元」;邊界無法求值時至少算一個元素
        width = a["bits"] * ((count(d) or 1) if is_arr else 1)
        for area, s0, s1, other, oaddr, oarr in used:
            if area == a["area"] and start < s1 and s0 < start + width:
                if is_arr or oarr:
                    # 虛擬 PLC 只同步純量的重疊位址,陣列元素不會同步:模擬結果與實機可能不同,一律警告
                    arr = d["name"] if is_arr else other
                    out.append(Issue("warning", ln, f"{d['name']} at {d['addr']} overlaps {other} at {oaddr}; "
                                                    f"array {arr} is NOT kept in sync by the virtual PLC, "
                                                    "simulation results may differ from the real PLC"))
                    continue
                # 一個完全包含另一個(位元在位元組/字內、REAL 與 DWORD 同位址)是常見的刻意別名,虛擬 PLC 會同步模擬;
                # 只有部分重疊(例:S7 的 %MW0 與 %MW1 共用 byte 1)才多半是定址錯誤
                inside = (s0 <= start and start + width <= s1) or (start <= s0 and s1 <= start + width)
                if not inside:
                    out.append(Issue("warning", ln, f"{d['name']} at {d['addr']} partially overlaps {other} at {oaddr}; "
                                                    "they share bytes (the virtual PLC keeps them in sync)"))
        used.append((a["area"], start, start + width, d["name"], d["addr"], is_arr))
    return out


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warning"
    line: int  # 0 when unknown
    msg: str

    def __str__(self):
        loc = f"line {self.line}: " if self.line else ""
        return f"{self.severity}: {loc}{self.msg}"


def _lit(x):
    """integer value of a literal initialiser (n / -n), else None."""
    if x[0] == "num" and isinstance(x[1], int) and not isinstance(x[1], bool):
        return x[1]
    if x[0] == "neg":
        v = _lit(x[1])
        return None if v is None else -v
    return None


def _init_range_issues(name, tname, init, ln):
    """初值超出宣告型別範圍(例:SINT := 300、USINT := -1),含陣列初值每個元素。"""
    if tname not in INT_RANGES or init is None:
        return []
    lo, hi = INT_RANGES[tname]
    items = init[1] if init[0] == "arrinit" else [init]
    out, seen = [], set()
    for x in items:
        v = _lit(x)
        if v is not None and not lo <= v <= hi and v not in seen:
            seen.add(v)
            out.append(Issue("error", ln, f"initial value {v} of {name} out of range for {tname} [{lo}..{hi}]"))
    return out


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
        m = re.match(r"line (\d+): (.*)", str(e), re.S)
        if m:  # carry the line so the UI can mark/jump to it
            return [Issue("error", int(m.group(1)), f"syntax: {m.group(2)}")]
        return [Issue("error", 0, f"syntax: {e}")]
    issues = []
    env = {}
    ufn, ufb = prog["functions"], prog["fbs"]
    structs = prog.get("types", {})

    class _UFB:  # adapter so user FBs look like built-in FB classes
        def __init__(self, d):
            self.inputs_t = {x["name"]: x["type"] for x in d["decls"] if x["section"] in ("input", "inout")}
            self.outputs_t = {x["name"]: x["type"] for x in d["decls"] if x["section"] == "output"}
            self.inouts = {x["name"].upper() for x in d["decls"] if x["section"] == "inout"}
            self.params = {x["name"].upper(): x for x in d["decls"] if x["section"] in ("input", "inout")}

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
            issues.extend(_init_range_issues(d["name"], t, d.get("init"), d.get("line", 0)))
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
            for i in _init_range_issues(f"{sd['name']}.{f['name']}", ft, f.get("init"), 0):
                if i not in issues:
                    issues.append(i)
            if ft.lower() in structs:
                struct_types(ft, owner, stack + (t.lower(),))
            elif ft not in INT_RANGES and ft not in ("BOOL", "REAL", "LREAL", "TIME", "STRING"):
                issues.append(Issue("error", 0, f"unknown type {ft} in STRUCT {sd['name']}"))
            elif ft not in prof.types:
                issues.append(Issue("error", 0, f"type {ft} of {owner}.{f['name']} not supported by profile {prof.name}"))

    load_scope(prog["decls"])
    issues += _addr_issues(prog["decls"], prof)

    def const_guard(target, ln):
        b = target
        while b[0] in ("index", "member"):
            b = b[1]
        d = env.get(b[1].lower()) if b[0] == "var" else None
        if d and d.get("const"):
            err(ln, f"write to CONSTANT {b[1]}")
            return True
        return False

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
            if b[0] == "member":
                f = field_of(b, ln)
                if f is None:
                    return None
                if not f.get("array"):
                    err(ln, f"{b[2]} is not an array")
                    return None
                dims = f.get("dims") or [f["array"]]
                if len(chain) != len(dims):
                    err(ln, f"{b[2]} needs {len(dims)} index(es), got {len(chain)}")
                    return None
                for (lo, hi), ie in zip(dims, chain):
                    if ie[0] == "num" and lo[0] == hi[0] == "num" and not lo[1] <= ie[1] <= hi[1]:
                        err(ln, f"array index {ie[1]} out of range [{lo[1]}..{hi[1]}] for {b[2]}")
                return f["type"]
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
            t = member(e, ln)
            f = field_of(e, ln, quiet=True)
            if f is not None and f.get("array"):
                err(ln, f"array {e[2]} used without index")
                return None
            return t
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
                io = {x["name"].lower() for x in uf["decls"] if x["section"] == "inout"}
                pdecl = {x["name"].lower(): x for x in uf["decls"] if x["section"] in ("input", "inout")}
                pos = 0
                for nm, op, v in e[2]:
                    if op == "=>":
                        ty(v, ln)
                        const_guard(v, ln)  # 輸出會寫回引數
                        continue
                    key = nm.lower() if nm else (ins[pos] if pos < len(ins) else None)
                    arg(pdecl.get(key), v, ln, uf["name"])
                    if key in io:
                        const_guard(v, ln)  # VAR_IN_OUT 會寫回引數
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

    def field_of(e, ln, quiet=False):
        """STRUCT field definition referenced by member expression `e` (None if unresolved)."""
        base, st = e[1], None
        if base[0] == "var":
            d = env.get(base[1].lower())
            if d and d["type"].lower() in structs:
                st = d["type"]
        elif base[0] == "member":
            bf = field_of(base, ln, quiet=True)
            if bf and not bf.get("array") and bf["type"].lower() in structs:
                st = bf["type"]
        elif base[0] == "index":
            bt = ty(base, ln) if not quiet else None
            if bt is None and quiet:
                b = base
                while b[0] == "index":
                    b = b[1]
                d = env.get(b[1].lower()) if b[0] == "var" else None
                bt = d["type"] if d else None
            st = bt if bt and bt.lower() in structs else None
        if st is None:
            return None
        for f in structs[st.lower()]["fields"]:
            if f["name"].lower() == e[2].lower():
                return f
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

    def cval(x):
        """compile-time integer value of an array bound (literal, -literal or VAR CONSTANT), else None."""
        if x[0] == "num" and isinstance(x[1], int):
            return x[1]
        if x[0] == "neg":
            v = cval(x[1])
            return None if v is None else -v
        if x[0] == "var":
            d = env.get(x[1].lower())
            if d and d.get("const") and d.get("init") is not None and not d.get("array"):
                return cval(d["init"])
        return None

    def shape(d):
        out = []
        for lo, hi in d.get("dims") or [d["array"]]:
            a, b = cval(lo), cval(hi)
            if a is None or b is None:
                return None
            out.append(b - a + 1)
        return out

    def whole_array(e, ln):
        """declaration of a bare (unindexed) array reference `a` / `s.f`, else None."""
        if e[0] == "var":
            d = env.get(e[1].lower())
            return d if d and d.get("array") else None
        if e[0] == "member":
            f = field_of(e, ln, quiet=True)
            return f if f and f.get("array") else None
        return None

    def array_match(dst, src, ln, what):
        """whole-array assignment / argument: same element type and same shape."""
        if dst["type"].lower() in structs or src["type"].lower() in structs:
            err(ln, f"{what}: ARRAY OF STRUCT cannot be passed or assigned as a whole yet")
            return
        if dst["type"] != src["type"]:
            err(ln, f"{what}: ARRAY OF {src['type']} given, ARRAY OF {dst['type']} expected")
            return
        a, b = shape(dst), shape(src)
        if a is not None and b is not None and a != b:
            err(ln, f"{what}: array shape {b} does not match {a}")

    def arg(param, v, ln, owner):
        """check one call argument; array parameters take a whole array variable."""
        if param is None or not param.get("array"):
            ty(v, ln)
            return
        src = whole_array(v, ln)
        if src is None:
            ty(v, ln)
            err(ln, f"parameter {param['name']} of {owner} is an ARRAY; pass a whole array variable")
            return
        array_match(param, src, ln, f"argument {param['name']} of {owner}")

    def assign(target, e, ln):
        if const_guard(target, ln):
            ty(e, ln)
            return
        dst = whole_array(target, ln)
        if dst is not None:
            src = whole_array(e, ln)
            if src is None:
                n = target[1] if target[0] == "var" else target[2]
                err(ln, f"cannot assign whole array {n}; use {n}[i] (or assign an array of the same shape)")
                return
            array_match(dst, src, ln, "array assignment")
            return
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

    def stmts(body, depth=0):
        for s in body:
            k = s[0]
            if k == "assign":
                assign(s[1], s[2], s[3])
            elif k == "call":
                call(s)
            elif k == "exit" and depth == 0:
                err(0, "EXIT used outside of a loop")
            elif k == "if":
                for c, b in s[1]:
                    cond(c)
                    stmts(b, depth)
                stmts(s[2], depth)
            elif k == "case":
                ty(s[1], 0)
                for _, b in s[2]:
                    stmts(b, depth)
                stmts(s[3], depth)
            elif k == "for":
                ty(("var", s[1]), 0)
                const_guard(("var", s[1]), 0)
                for x in s[2:5]:
                    ty(x, 0)
                stmts(s[5], depth + 1)
            elif k == "while":
                cond(s[1])
                stmts(s[2], depth + 1)
            elif k == "repeat":
                stmts(s[1], depth + 1)
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
        params = getattr(fb, "params", {})
        for name, op, v in s[2]:
            if op != "=>" and name:
                arg(params.get(name.upper()), v, ln, ufb.get(d["type"].lower(), {}).get("name", d["type"]))
            else:
                ty(v, ln)
            if op == "=>" or (name and name.upper() in getattr(fb, "inouts", ())):
                const_guard(v, ln)
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
        issues += _addr_issues(fn["decls"], prof, f"{'FUNCTION' if fn['kind'] == 'function' else 'FUNCTION_BLOCK'} {fn['name']}")
        stmts(fn["body"])
    issues += [Issue("warning", ln, f"dialect: {m}") for ln, m in dialect_issues(src, prof.name)]
    return issues
