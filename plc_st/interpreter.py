"""Tree-walking ST interpreter with scan-cycle semantics and standard FBs."""
import math
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


FB_TYPES = {c.__name__: c for c in (TON, TOF, TP, CTU, CTD, R_TRIG, F_TRIG, RS, SR)}

FUNCS = {
    "ABS": abs, "SQRT": math.sqrt, "SIN": math.sin, "COS": math.cos, "TAN": math.tan,
    "LN": math.log, "LOG": math.log10, "EXP": math.exp,
    "MIN": min, "MAX": max,
    "TRUNC": lambda x: int(x), "REAL_TO_INT": lambda x: int(round(x)),
    "INT_TO_REAL": float, "DINT_TO_REAL": float, "INT_TO_DINT": int, "DINT_TO_INT": int,
    "BOOL_TO_INT": int, "INT_TO_BOOL": bool,
    "LIMIT": lambda mn, x, mx: max(mn, min(x, mx)),
    "SEL": lambda g, a, b: b if g else a,
}


class VirtualPLC:
    def __init__(self, source, scan_ms=10, profile="iec"):
        self.profile = get_profile(profile)
        self.ast = parse(source)
        self.scan_ms = scan_ms
        self.vars, self.types, self.section, self.fbs = {}, {}, {}, {}
        self.cycles = 0
        self.time_ms = 0
        for d in self.ast["decls"]:
            n = d["name"].lower()
            self.section[n] = d["section"]
            t = d["type"]
            if t in FB_TYPES:
                self.fbs[n] = FB_TYPES[t]()
                self.types[n] = t
                continue
            if t not in INT_RANGES and t not in ("BOOL", "REAL", "LREAL", "TIME", "STRING"):
                raise STError(f"unknown type {t} for {d['name']}")
            if t not in self.profile.types:
                raise STError(f"type {t} of {d['name']} not supported on profile {self.profile.name}")
            self.types[n] = t
            self.vars[n] = self.wrap(t, self.eval(d["init"])) if d["init"] else default(t)
        self.names = {d["name"].lower(): d["name"] for d in self.ast["decls"]}

    def wrap(self, t, v):
        return wrap(t, v, self.profile.overflow)

    # -- external interface
    def set_input(self, name, value):
        n = name.lower()
        if n not in self.vars:
            raise STError(f"unknown variable {name}")
        self.vars[n] = self.wrap(self.types[n], value)

    def get(self, name):
        n = name.lower()
        if "." in n:
            fb, field = n.split(".", 1)
            return self.fbs[fb].v[field.upper()]
        if n not in self.vars:
            raise STError(f"unknown variable {name}")
        return self.vars[n]

    def snapshot(self):
        return {self.names[n]: v for n, v in self.vars.items()}

    def scan(self, cycles=1):
        for _ in range(cycles):
            try:
                self.run(self.ast["body"])
            except _Exit:
                pass
            self.cycles += 1
            self.time_ms += self.scan_ms

    # -- execution
    def run(self, stmts):
        for s in stmts:
            op = s[0]
            if op == "assign":
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

    def assign(self, target, value):
        if target[0] == "var":
            n = target[1].lower()
            if n not in self.vars:
                raise STError(f"assignment to unknown variable {target[1]}")
            if self.section[n] == "input":
                pass  # allowed for testing; real PLCs forbid it (see validator, M4)
            self.vars[n] = self.wrap(self.types[n], value)
        else:
            fb = self.fbs[target[1][1].lower()]
            fb.v[target[2].upper()] = value

    def call_fb(self, target, args):
        fb = self.fbs.get(target[1].lower()) if target[0] == "var" else None
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

    def eval(self, e):
        k = e[0]
        if k in ("num", "time", "bool", "str"):
            return e[1]
        if k == "var":
            n = e[1].lower()
            if n in self.vars:
                return self.vars[n]
            raise STError(f"unknown variable {e[1]}")
        if k == "member":
            return self.fbs[e[1][1].lower()].v[e[2].upper()]
        if k == "not":
            v = self.eval(e[1])
            return (not v) if isinstance(v, bool) else ~v
        if k == "neg":
            return -self.eval(e[1])
        if k == "func":
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
