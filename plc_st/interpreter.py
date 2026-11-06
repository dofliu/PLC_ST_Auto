"""Tree-walking ST interpreter with scan-cycle semantics and standard FBs."""
import math
import re
from .lexer import STError
from .parser import parse
from .profiles import get_profile

INT_RANGES = {
    "SINT": (-2**7, 2**7 - 1), "INT": (-2**15, 2**15 - 1), "DINT": (-2**31, 2**31 - 1),
    "LINT": (-2**63, 2**63 - 1), "USINT": (0, 2**8 - 1), "UINT": (0, 2**16 - 1),
    "UDINT": (0, 2**32 - 1), "ULINT": (0, 2**64 - 1), "BYTE": (0, 255),
    "WORD": (0, 65535), "DWORD": (0, 2**32 - 1),
}
MAX_LOOP = 100000


class _Exit(Exception):
    pass


class _Return(Exception):
    pass


MAX_DEPTH = 32


def wrap(tname, v, overflow="wrap"):
    """Coerce value to declared type; overflow: wrap | saturate | fault."""
    if tname == "BOOL":
        return bool(v)
    if tname in INT_RANGES:
        lo, hi = INT_RANGES[tname]
        if overflow != "wrap" and not lo <= int(v) <= hi:
            if overflow == "fault":
                raise STError(f"integer overflow: {int(v)} does not fit {tname}")
            return lo if int(v) < lo else hi
        bits = (hi - lo).bit_length()
        v = int(v) & ((1 << bits) - 1)
        if lo < 0 and v > hi:
            v -= 1 << bits
        return v
    if tname in ("REAL", "LREAL"):
        return float(v)
    if tname == "TIME":
        return int(v)
    if tname == "STRING":
        return str(v)
    return v


def default(tname):
    return {"BOOL": False, "REAL": 0.0, "LREAL": 0.0, "STRING": ""}.get(tname, 0)


class _View:
    """Case-insensitive dict-like view over a user FB instance's variables."""

    def __init__(self, fb):
        self.fb = fb

    def __getitem__(self, k):
        sc = self.fb.sc
        n = k.lower()
        if n not in sc["vars"]:
            raise STError(f"{self.fb.d['name']} has no member {k}")
        return sc["vars"][n]

    def __setitem__(self, k, val):
        sc = self.fb.sc
        n = k.lower()
        if n not in sc["vars"]:
            raise STError(f"{self.fb.d['name']} has no member {k}")
        sc["vars"][n] = self.fb.plc.wrap(sc["types"][n], val)


class UserFB:
    """Instance of a user-defined FUNCTION_BLOCK; locals persist between calls."""

    def __init__(self, plc, d):
        self.plc, self.d = plc, d
        self.sc = plc._build(d["decls"])
        self.v = _View(self)

    def call(self, dt):
        self.plc._exec_in(self.sc, self.d["body"])


class FB:
    inputs, outputs = (), ()

    def __init__(self):
        self.v = {n: default_of(t) for n, t in {**self.inputs_t, **self.outputs_t}.items()}

    def call(self, dt):
        raise NotImplementedError


def default_of(t):
    return default(t)


class TON(FB):
    inputs_t = {"IN": "BOOL", "PT": "TIME"}
    outputs_t = {"Q": "BOOL", "ET": "TIME"}

    def __init__(self):
        super().__init__()
        self.el = 0

    def call(self, dt):
        v = self.v
        if v["IN"]:
            self.el = min(self.el + dt, v["PT"]) if self.el < v["PT"] else self.el
            v["Q"] = self.el >= v["PT"]
        else:
            self.el, v["Q"] = 0, False
        v["ET"] = self.el


class TOF(FB):
    inputs_t = {"IN": "BOOL", "PT": "TIME"}
    outputs_t = {"Q": "BOOL", "ET": "TIME"}

    def __init__(self):
        super().__init__()
        self.el = 0

    def call(self, dt):
        v = self.v
        if v["IN"]:
            self.el, v["Q"] = 0, True
        elif v["Q"]:
            self.el += dt
            if self.el >= v["PT"]:
                v["Q"] = False
                self.el = v["PT"]
        v["ET"] = self.el


class TP(FB):
    inputs_t = {"IN": "BOOL", "PT": "TIME"}
    outputs_t = {"Q": "BOOL", "ET": "TIME"}

    def __init__(self):
        super().__init__()
        self.el, self.prev, self.run = 0, False, False

    def call(self, dt):
        v = self.v
        if v["IN"] and not self.prev and not self.run:
            self.run, self.el = True, 0
        if self.run:
            self.el += dt
            if self.el >= v["PT"]:
                self.el, self.run = v["PT"], False
        v["Q"] = self.run
        if not self.run and not v["IN"]:
            self.el = 0
        v["ET"] = self.el
        self.prev = v["IN"]


class CTU(FB):
    inputs_t = {"CU": "BOOL", "R": "BOOL", "PV": "INT"}
    outputs_t = {"Q": "BOOL", "CV": "INT"}

    def __init__(self):
        super().__init__()
        self.prev = False

    def call(self, dt):
        v = self.v
        if v["R"]:
            v["CV"] = 0
        elif v["CU"] and not self.prev and v["CV"] < 32767:
            v["CV"] += 1
        self.prev = v["CU"]
        v["Q"] = v["CV"] >= v["PV"]


class CTD(FB):
    inputs_t = {"CD": "BOOL", "LD": "BOOL", "PV": "INT"}
    outputs_t = {"Q": "BOOL", "CV": "INT"}

    def __init__(self):
        super().__init__()
        self.prev = False

    def call(self, dt):
        v = self.v
        if v["LD"]:
            v["CV"] = v["PV"]
        elif v["CD"] and not self.prev and v["CV"] > -32768:
            v["CV"] -= 1
        self.prev = v["CD"]
        v["Q"] = v["CV"] <= 0


class CTUD(FB):
    inputs_t = {"CU": "BOOL", "CD": "BOOL", "R": "BOOL", "LD": "BOOL", "PV": "INT"}
    outputs_t = {"QU": "BOOL", "QD": "BOOL", "CV": "INT"}

    def __init__(self):
        super().__init__()
        self.pu = self.pd = False

    def call(self, dt):
        v = self.v
        if v["R"]:
            v["CV"] = 0
        elif v["LD"]:
            v["CV"] = v["PV"]
        else:
            if v["CU"] and not self.pu and v["CV"] < 32767:
                v["CV"] += 1
            elif v["CD"] and not self.pd and v["CV"] > -32768:
                v["CV"] -= 1
        self.pu, self.pd = v["CU"], v["CD"]
        v["QU"] = v["CV"] >= v["PV"]
        v["QD"] = v["CV"] <= 0


class R_TRIG(FB):
    inputs_t = {"CLK": "BOOL"}
    outputs_t = {"Q": "BOOL"}

    def __init__(self):
        super().__init__()
        self.prev = False

    def call(self, dt):
        self.v["Q"] = self.v["CLK"] and not self.prev
        self.prev = self.v["CLK"]


class F_TRIG(R_TRIG):
    def call(self, dt):
        self.v["Q"] = (not self.v["CLK"]) and self.prev
        self.prev = self.v["CLK"]


class RS(FB):
    inputs_t = {"SET": "BOOL", "RESET1": "BOOL"}
    outputs_t = {"Q1": "BOOL"}

    def call(self, dt):
        v = self.v
        v["Q1"] = (v["SET"] or v["Q1"]) and not v["RESET1"]


class SR(FB):
    inputs_t = {"SET1": "BOOL", "RESET": "BOOL"}
    outputs_t = {"Q1": "BOOL"}

    def call(self, dt):
        v = self.v
        v["Q1"] = v["SET1"] or (v["Q1"] and not v["RESET"])


FB_TYPES = {c.__name__: c for c in (TON, TOF, TP, CTU, CTD, CTUD, R_TRIG, F_TRIG, RS, SR)}

FUNCS = {
    "ABS": abs, "SQRT": math.sqrt, "SIN": math.sin, "COS": math.cos, "TAN": math.tan,
    "LN": math.log, "LOG": math.log10, "EXP": math.exp,
    "MIN": min, "MAX": max,
    "TRUNC": lambda x: int(x), "REAL_TO_INT": lambda x: int(round(x)),
    "INT_TO_REAL": float, "DINT_TO_REAL": float, "INT_TO_DINT": int, "DINT_TO_INT": int,
    "BOOL_TO_INT": int, "INT_TO_BOOL": bool,
    "LIMIT": lambda mn, x, mx: max(mn, min(x, mx)),
    "SEL": lambda g, a, b: b if g else a,
    "ASIN": math.asin, "ACOS": math.acos, "ATAN": math.atan,
    "FLOOR": lambda x: int(math.floor(x)), "CEIL": lambda x: int(math.ceil(x)),
    "REAL_TO_DINT": lambda x: int(round(x)), "DINT_TO_BOOL": bool, "BOOL_TO_DINT": int,
    "WORD_TO_INT": int, "INT_TO_WORD": lambda x: x & 0xFFFF,
    "SHL": lambda x, n: x << n, "SHR": lambda x, n: x >> n,
    "ROL": lambda x, n: ((x << n) | (x >> (16 - n))) & 0xFFFF,
    "ROR": lambda x, n: ((x >> n) | (x << (16 - n))) & 0xFFFF,
    "LEN": len, "CONCAT": lambda a, b: a + b,
    "LEFT": lambda s, n: s[:n], "RIGHT": lambda s, n: s[len(s) - n:] if n else "",
}


class VirtualPLC:
    def __init__(self, source, scan_ms=10, profile="iec"):
        self.profile = get_profile(profile)
        self.ast = parse(source)
        self.scan_ms = scan_ms
        self.udefs = {**self.ast.get("fbs", {})}
        self.structs = dict(self.ast.get("types", {}))
        self.disp = {}
        self.ufuncs = dict(self.ast.get("functions", {}))
        self.depth = 0
        self.cycles = 0
        self.time_ms = 0
        self._set_scope(self._build(self.ast["decls"]))
        self.names = {d["name"].lower(): d["name"] for d in self.ast["decls"]}

    def wrap(self, t, v):
        return wrap(t, v, self.profile.overflow)

    # -- scopes (program / user FUNCTION / user FUNCTION_BLOCK instance)
    def _get_scope(self):
        return {"vars": self.vars, "types": self.types, "section": self.section,
                "fbs": self.fbs, "arrays": self.arrays, "sarr": self.sarr}

    def _set_scope(self, sc):
        self.vars, self.types, self.section = sc["vars"], sc["types"], sc["section"]
        self.fbs, self.arrays, self.sarr = sc["fbs"], sc["arrays"], sc["sarr"]

    def _build(self, decls):
        sc = {"vars": {}, "types": {}, "section": {}, "fbs": {}, "arrays": {}, "sarr": {}}
        saved = self._get_scope() if hasattr(self, "vars") else None
        self._set_scope(sc)
        try:
            for d in decls:
                n = d["name"].lower()
                self.section[n] = d["section"]
                t = d["type"]
                if t in FB_TYPES:
                    self.fbs[n] = FB_TYPES[t]()
                    self.types[n] = t
                    continue
                if t.lower() in self.udefs:
                    self.fbs[n] = UserFB(self, self.udefs[t.lower()])
                    self.types[n] = t
                    continue
                if t.lower() in self.structs and d.get("array"):
                    self._struct_array(d)
                    continue
                if t.lower() in self.structs:
                    self._flatten(d["name"], t, d["init"], d["section"])
                    continue
                if t not in INT_RANGES and t not in ("BOOL", "REAL", "LREAL", "TIME", "STRING"):
                    raise STError(f"unknown type {t} for {d['name']}")
                if t not in self.profile.types:
                    raise STError(f"type {t} of {d['name']} not supported on profile {self.profile.name}")
                self.types[n] = t
                if d.get("array"):
                    dims, size = [], 1
                    for dl, dh in d.get("dims") or [d["array"]]:
                        lo, hi = self.eval(dl), self.eval(dh)
                        if hi < lo:
                            raise STError(f"array {d['name']}: upper bound {hi} < lower bound {lo}")
                        dims.append((lo, hi))
                        size *= hi - lo + 1
                    init = d["init"][1] if d["init"] else []
                    if len(init) > size:
                        raise STError(f"array {d['name']}: too many initial values")
                    vals = [self.wrap(t, self.eval(x)) for x in init]
                    self.arrays[n] = dims
                    self.vars[n] = vals + [default(t)] * (size - len(vals))
                else:
                    self.vars[n] = self.wrap(t, self.eval(d["init"])) if d["init"] else default(t)
        finally:
            if saved is not None:
                self._set_scope(saved)
        return sc

    def _flatten(self, name, tname, init, section, stack=()):
        """STRUCT instance -> scalar variables 'name.field' (nested structs recurse)."""
        sd = self.structs[tname.lower()]
        if tname.lower() in stack:
            raise STError(f"recursive STRUCT {sd['name']}")
        given = {}
        if init is not None:
            if init[0] != "structinit":
                raise STError(f"{name}: STRUCT {sd['name']} needs an initialiser like (a := 1)")
            given = {k.lower(): v for k, v in init[1]}
        known = {f["name"].lower() for f in sd["fields"]}
        for k in given:
            if k not in known:
                raise STError(f"{name}: STRUCT {sd['name']} has no field {k}")
        for f in sd["fields"]:
            key = f"{name}.{f['name']}"
            fi = given.get(f["name"].lower(), f["init"])
            ft = f["type"]
            if ft.lower() in self.structs:
                self._flatten(key, ft, fi, section, stack + (tname.lower(),))
                continue
            if ft not in INT_RANGES and ft not in ("BOOL", "REAL", "LREAL", "TIME", "STRING"):
                raise STError(f"unknown type {ft} for field {key}")
            if ft not in self.profile.types:
                raise STError(f"type {ft} of {key} not supported on profile {self.profile.name}")
            n = key.lower()
            self.section[n] = section
            self.types[n] = ft
            self.disp[n] = key
            self.vars[n] = self.wrap(ft, self.eval(fi)) if fi is not None else default(ft)

    def _struct_array(self, d):
        """ARRAY OF STRUCT -> one array per (flattened) field, key 'arr.field'."""
        dims, size = [], 1
        for dl, dh in d.get("dims") or [d["array"]]:
            lo, hi = self.eval(dl), self.eval(dh)
            if hi < lo:
                raise STError(f"array {d['name']}: upper bound {hi} < lower bound {lo}")
            dims.append((lo, hi))
            size *= hi - lo + 1
        before = set(self.vars)
        self._flatten(d["name"], d["type"], None, d["section"])
        for k in set(self.vars) - before:
            self.vars[k] = [self.vars[k]] * size
            self.arrays[k] = dims
        self.sarr[d["name"].lower()] = dims
        items = d["init"][1] if d["init"] else []
        if d["init"] and d["init"][0] != "arrinit":
            raise STError(f"{d['name']}: ARRAY OF STRUCT needs an initialiser like [(a := 1), (a := 2)]")
        if len(items) > size:
            raise STError(f"array {d['name']}: too many initial values")
        tmp = "__init"
        for pos, it in enumerate(items):
            if it[0] != "structinit":
                raise STError(f"{d['name']}: element initialiser must be a STRUCT value like (a := 1)")
            self._flatten(tmp, d["type"], it, d["section"])
            for k in [k for k in self.vars if k.startswith(tmp + ".")]:
                self.vars[d["name"].lower() + k[len(tmp):]][pos] = self.vars.pop(k)
                for tbl in (self.section, self.types, self.disp):
                    tbl.pop(k, None)

    def _sa_resolve(self, e):
        """a[i].f / a[i].m.f on an ARRAY OF STRUCT -> (array key, [indexes]) or None."""
        fields = []
        while e[0] == "member":
            fields.insert(0, e[2].lower())
            e = e[1]
        if e[0] != "index" or not fields:
            return None
        idx = []
        while e[0] == "index":
            idx.append(self.eval(e[2]))
            e = e[1]
        if e[0] != "var" or e[1].lower() not in self.sarr:
            return None
        key = e[1].lower() + "." + ".".join(fields)
        if key not in self.arrays:
            raise STError(f"unknown member {key}")
        return key, idx[::-1]

    def _path(self, e):
        """var/member chain -> lowercase dotted name (None if not a plain chain)."""
        if e[0] == "var":
            return e[1].lower()
        if e[0] == "member":
            b = self._path(e[1])
            return None if b is None else f"{b}.{e[2].lower()}"
        return None

    def _exec_in(self, sc, body):
        """Run `body` with `sc` as the active variable scope (RETURN ends the body)."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            self.depth -= 1
            raise STError("call depth exceeded (recursion is not allowed in IEC 61131-3)")
        saved = self._get_scope()
        self._set_scope(sc)
        try:
            self.run(body)
        except _Return:
            pass
        finally:
            self._set_scope(saved)
            self.depth -= 1

    def call_function(self, fn, args):
        decls = fn["decls"] + [{"name": fn["name"], "type": fn["type"], "section": "local",
                                "init": None, "array": None}]
        sc = self._build(decls)
        ins = [d["name"].lower() for d in fn["decls"] if d["section"] in ("input", "inout")]
        outs, pos = [], 0
        for name, op, e in args:
            if op == "=>":
                outs.append((name, e))
                continue
            if name is None:
                if pos >= len(ins):
                    raise STError(f"too many arguments for function {fn['name']}")
                key, pos = ins[pos], pos + 1
            else:
                key = name.lower()
                if key not in ins:
                    raise STError(f"function {fn['name']} has no input {name}")
            sc["vars"][key] = self.wrap(sc["types"][key], self.eval(e))
        self._exec_in(sc, fn["body"])
        for name, e in outs:
            self.assign(e, sc["vars"][name.lower()])
        self._write_back(fn["decls"], args, lambda k: sc["vars"][k], ins, fn["name"])
        return sc["vars"][fn["name"].lower()]

    def _write_back(self, decls, args, getter, ins, owner):
        """Copy VAR_IN_OUT values back to the caller's variables."""
        io = {d["name"].lower() for d in decls if d["section"] == "inout"}
        if not io:
            return
        pos = 0
        for name, op, e in args:
            if op == "=>":
                continue
            if name is None:
                key, pos = (ins[pos] if pos < len(ins) else None), pos + 1
            else:
                key = name.lower()
            if key in io:
                if e[0] not in ("var", "index", "member"):
                    raise STError(f"VAR_IN_OUT {key} of {owner} needs a variable argument")
                self.assign(e, getter(key))

    # -- external interface
    def _split_index(self, name):
        """'arr[3]' -> ('arr', 3); plain names -> (name, None)."""
        n = re.sub(r"^(\w+)\[([^\]]*)\]\.(.+)$", r"\1.\3[\2]", name.lower())
        if n.endswith("]") and "[" in n:
            base, _, idx = n[:-1].partition("[")
            return base, [int(x) for x in idx.split(",")]
        return n, None

    def _elem(self, base, idxs):
        if base not in self.arrays:
            raise STError(f"{base} is not an array")
        if not isinstance(idxs, (list, tuple)):
            idxs = [idxs]
        dims = self.arrays[base]
        if len(idxs) != len(dims):
            raise STError(f"{base} needs {len(dims)} index(es), got {len(idxs)}")
        flat = 0
        for (lo, hi), ix in zip(dims, idxs):
            if not lo <= ix <= hi:
                raise STError(f"array index {ix} out of range [{lo}..{hi}] for {base}")
            flat = flat * (hi - lo + 1) + (ix - lo)
        return flat

    def _chain(self, e):
        """index chain a[i][j] / a[i,j] -> (array name, [index values])."""
        idx = []
        while e[0] == "index":
            idx.append(self.eval(e[2]))
            e = e[1]
        if e[0] != "var" or e[1].lower() not in self.arrays:
            raise STError("indexing a non-array expression")
        return e[1].lower(), idx[::-1]

    def set_input(self, name, value):
        n, idx = self._split_index(name)
        if n not in self.vars:
            raise STError(f"unknown variable {name}")
        if idx is not None:
            self.vars[n][self._elem(n, idx)] = self.wrap(self.types[n], value)
        elif n in self.arrays:
            raise STError(f"{name} is an array; use {name}[i]")
        else:
            self.vars[n] = self.wrap(self.types[n], value)

    def get(self, name):
        n = re.sub(r"^(\w+)\[([^\]]*)\]\.(.+)$", r"\1.\3[\2]", name.lower())
        if n.endswith("]"):
            base, idx = self._split_index(n)
            if base not in self.vars:
                raise STError(f"unknown variable {name}")
            return self.vars[base][self._elem(base, idx)]
        if "." in n and n not in self.vars:
            fb, field = n.split(".", 1)
            return self.fbs[fb].v[field.upper()]
        if n not in self.vars:
            raise STError(f"unknown variable {name}")
        return self.vars[n]

    def snapshot(self):
        out = {}
        for n, v in self.vars.items():
            if n in self.arrays:
                dims = self.arrays[n]
                for i, x in enumerate(v):
                    sub, r = [], i
                    for lo, hi in reversed(dims):
                        w = hi - lo + 1
                        sub.append(lo + r % w)
                        r //= w
                    ix = ",".join(map(str, sub[::-1]))
                    base, dot, rest = n.partition(".")
                    if dot and base in self.sarr:
                        out[f"{self.names.get(base, base)}[{ix}].{self.disp.get(n, n).partition('.')[2]}"] = x
                    else:
                        out[f"{self.names[n]}[{ix}]"] = x
            else:
                out[self.names.get(n) or self.disp.get(n, n)] = v
        return out

    def scan(self, cycles=1):
        for _ in range(cycles):
            try:
                self.run(self.ast["body"])
            except (_Exit, _Return):
                pass
            self.cycles += 1
            self.time_ms += self.scan_ms

    # -- execution
    def run(self, stmts):
        for s in stmts:
            op = s[0]
            if op == "assign":
                if not self._struct_copy(s[1], s[2]):
                    self.assign(s[1], self.eval(s[2]))
            elif op == "call":
                self.call_fb(s[1], s[2])
            elif op == "if":
                for cond, body in s[1]:
                    if self.eval(cond):
                        self.run(body)
                        break
                else:
                    self.run(s[2])
            elif op == "case":
                v = self.eval(s[1])
                for labels, body in s[2]:
                    if any((self.eval(lo) <= v <= self.eval(hi)) if hi else v == self.eval(lo)
                           for lo, hi in labels):
                        self.run(body)
                        break
                else:
                    self.run(s[3])
            elif op == "for":
                self.for_loop(s)
            elif op == "while":
                n = 0
                while self.eval(s[1]):
                    n += 1
                    if n > MAX_LOOP:
                        raise STError("WHILE exceeded iteration limit")
                    try:
                        self.run(s[2])
                    except _Exit:
                        break
            elif op == "repeat":
                n = 0
                while True:
                    n += 1
                    if n > MAX_LOOP:
                        raise STError("REPEAT exceeded iteration limit")
                    try:
                        self.run(s[1])
                    except _Exit:
                        break
                    if self.eval(s[2]):
                        break
            elif op == "exit":
                raise _Exit()
            elif op == "return":
                raise _Return()

    def for_loop(self, s):
        _, var, a, b, step, body = s
        n = var.lower()
        i, end, st = self.eval(a), self.eval(b), self.eval(step)
        if st == 0:
            raise STError("FOR step is 0")
        count = 0
        while (i <= end) if st > 0 else (i >= end):
            count += 1
            if count > MAX_LOOP:
                raise STError("FOR exceeded iteration limit")
            self.vars[n] = self.wrap(self.types[n], i)
            try:
                self.run(body)
            except _Exit:
                break
            i += st
        else:
            self.vars[n] = self.wrap(self.types[n], i)

    def _fields_of(self, e):
        """flattened {suffix: (key, flat index|None)} of a STRUCT value expression
        (plain instance, or element / nested member of an ARRAY OF STRUCT), or None."""
        p = self._path(e)
        if p is not None:
            if p in self.vars:
                return None
            pre = p + "."
            f = {k[len(pre):]: (k, None) for k in self.vars if k.startswith(pre)}
            return f or None
        fields, b = [], e
        while b[0] == "member":
            fields.insert(0, b[2].lower())
            b = b[1]
        base = b
        while base[0] == "index":
            base = base[1]
        if b[0] != "index" or base[0] != "var" or base[1].lower() not in self.sarr:
            return None
        idx = []
        while b[0] == "index":
            idx.append(self.eval(b[2]))
            b = b[1]
        name, idx = b[1].lower(), idx[::-1]
        pre = ".".join([name] + fields) + "."
        f = {k[len(pre):]: (k, self._elem(k, idx)) for k in self.arrays if k.startswith(pre)}
        return f or None

    def _struct_copy(self, target, src):
        """whole-STRUCT assignment `a := b` (same type); True if handled."""
        tf = self._fields_of(target)
        if tf is None:
            return False
        sf = self._fields_of(src)
        if sf is None or set(sf) != set(tf):
            raise STError("STRUCT assignment needs a STRUCT of the same type")
        def get(r):
            return self.vars[r[0]] if r[1] is None else self.vars[r[0]][r[1]]

        vals = {k: get(sf[k]) for k in tf}
        for k, (key, pos) in tf.items():
            if pos is None:
                self.vars[key] = vals[k]
            else:
                self.vars[key][pos] = vals[k]
        return True

    def assign(self, target, value):
        if target[0] == "var":
            n = target[1].lower()
            if n not in self.vars:
                raise STError(f"assignment to unknown variable {target[1]}")
            if self.section[n] == "input":
                pass  # allowed for testing; real PLCs forbid it (see validator, M4)
            self.vars[n] = self.wrap(self.types[n], value)
        elif target[0] == "index":
            n, ix = self._chain(target)
            self.vars[n][self._elem(n, ix)] = self.wrap(self.types[n], value)
        else:
            r = self._sa_resolve(target)
            if r:
                self.vars[r[0]][self._elem(*r)] = self.wrap(self.types[r[0]], value)
                return
            p = self._path(target)
            if p in self.vars:
                self.vars[p] = self.wrap(self.types[p], value)
                return
            if target[1][0] != "var" or target[1][1].lower() not in self.fbs:
                raise STError(f"assignment to unknown member {p}")
            fb = self.fbs[target[1][1].lower()]
            fb.v[target[2].upper()] = value

    def call_fb(self, target, args):
        fb = self.fbs.get(target[1].lower()) if target[0] == "var" else None
        if fb is None and target[0] == "var" and target[1].lower() in self.ufuncs:
            self.call_function(self.ufuncs[target[1].lower()], args)  # function as statement
            return
        if fb is None:
            raise STError(f"{target} is not a function block instance")
        outs = []
        for name, op, e in args:
            if op == "=>":
                outs.append((name, e))
            else:
                fb.v[name.upper()] = self.eval(e)
        fb.call(self.scan_ms)
        for name, e in outs:
            self.assign(e, fb.v[name.upper()])
        if isinstance(fb, UserFB):
            ins = [d["name"].lower() for d in fb.d["decls"] if d["section"] in ("input", "inout")]
            self._write_back(fb.d["decls"], args, lambda k: fb.v[k], ins, fb.d["name"])

    def eval(self, e):
        k = e[0]
        if k in ("num", "time", "bool", "str"):
            return e[1]
        if k == "var":
            n = e[1].lower()
            if n in self.arrays:
                raise STError(f"array {e[1]} used without index")
            if n in self.vars:
                return self.vars[n]
            if any(k.startswith(n + ".") for k in self.vars):
                raise STError(f"STRUCT {e[1]} used without member")
            raise STError(f"unknown variable {e[1]}")
        if k == "index":
            n, ix = self._chain(e)
            return self.vars[n][self._elem(n, ix)]
        if k == "member":
            r = self._sa_resolve(e)
            if r:
                return self.vars[r[0]][self._elem(*r)]
            p = self._path(e)
            if p in self.vars:
                return self.vars[p]
            if e[1][0] != "var" or e[1][1].lower() not in self.fbs:
                raise STError(f"unknown member {p}")
            return self.fbs[e[1][1].lower()].v[e[2].upper()]
        if k == "not":
            v = self.eval(e[1])
            return (not v) if isinstance(v, bool) else ~v
        if k == "neg":
            return -self.eval(e[1])
        if k == "func":
            uf = self.ufuncs.get(e[1].lower())
            if uf:
                return self.call_function(uf, e[2])
            f = FUNCS.get(e[1].upper())
            if not f:
                raise STError(f"unknown function {e[1]}")
            return f(*[self.eval(a[2]) for a in e[2]])
        if k == "bin":
            return self.binop(e[1], self.eval(e[2]), self.eval(e[3]))
        raise STError(f"bad expression {e}")

    @staticmethod
    def binop(op, a, b):
        if op == "AND":
            return (a and b) if isinstance(a, bool) else a & b
        if op == "OR":
            return (a or b) if isinstance(a, bool) else a | b
        if op == "XOR":
            return (a != b) if isinstance(a, bool) else a ^ b
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise STError("division by zero")
            if isinstance(a, int) and isinstance(b, int):
                return int(a / b)  # truncate toward zero like IEC
            return a / b
        if op == "MOD":
            if b == 0:
                raise STError("MOD by zero")
            return a - b * int(a / b)
        if op == "**":
            return float(a) ** b
        return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b,
                "<=": a <= b, ">=": a >= b}[op]
