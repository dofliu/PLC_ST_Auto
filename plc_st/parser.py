"""Recursive-descent ST parser producing tuple ASTs."""
import re
from .lexer import tokenize, STError

SECTIONS = {"VAR": "local", "VAR_INPUT": "input", "VAR_OUTPUT": "output", "VAR_IN_OUT": "inout", "VAR_TEMP": "temp",
            "VAR_GLOBAL": "global", "VAR_EXTERNAL": "external"}
_QUALS = ("RETAIN", "CONSTANT", "NON_RETAIN", "PERSISTENT")
_ADDR = re.compile(r"%([IQM])([XBWDL]?)(\d+)(?:\.(\d+))?$")
_ADDR_BITS = {"X": 1, "B": 8, "W": 16, "D": 32, "L": 64}


def parse_addr(text):
    """'%IX0.3' → {area: I|Q|M, size: X|B|W|D|L, bits, index, bit};格式不符回傳 None。
    省略大小字首(%I0.3)視為位元。"""
    m = _ADDR.match(text.upper())
    if not m:
        return None
    area, size, idx, bit = m.group(1), m.group(2) or "X", int(m.group(3)), m.group(4)
    if bit is not None and (size != "X" or int(bit) > 7):
        return None
    return {"area": area, "size": size, "bits": _ADDR_BITS[size], "index": idx,
            "bit": int(bit) if bit is not None else None}


class Parser:
    def __init__(self, src):
        self.t = tokenize(src)
        self.i = 0

    # -- helpers
    def peek(self):
        return self.t[self.i]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def is_(self, kind, val=None):
        k, v, _ = self.peek()
        return k == kind and (val is None or v == val)

    def accept(self, kind, val=None):
        if self.is_(kind, val):
            return self.next()
        return None

    def expect(self, kind, val=None):
        if not self.is_(kind, val):
            k, v, ln = self.peek()
            raise STError(f"line {ln}: expected {val or kind}, got {v!r}")
        return self.next()

    # -- program
    def pou_def(self):
        """FUNCTION name : TYPE ... END_FUNCTION  |  FUNCTION_BLOCK name ... END_FUNCTION_BLOCK."""
        kind = "function" if self.next()[1] == "FUNCTION" else "fb"
        name = self.expect("id")[1]
        rtype = None
        if kind == "function":
            self.expect("op", ":")
            rtype = self.expect("id")[1].upper()
        decls = []
        while self.peek()[0] == "kw" and self.peek()[1] in SECTIONS:
            ln = self.peek()[2]
            if self.peek()[1] == "VAR_GLOBAL":
                raise STError(f"line {ln}: VAR_GLOBAL is not allowed inside {name}; "
                              "declare it at top level (or in the PROGRAM) and use VAR_EXTERNAL here")
            decls += self.var_block()
        end = "END_FUNCTION" if kind == "function" else "END_FUNCTION_BLOCK"
        body = self.statements({end})
        self.expect("kw", end)
        return {"kind": kind, "name": name, "type": rtype, "decls": decls, "body": body}

    def type_def(self):
        """TYPE name : STRUCT f : T [:= init]; ... END_STRUCT END_TYPE"""
        self.expect("kw", "TYPE")
        name = self.expect("id")[1]
        self.expect("op", ":")
        self.expect("kw", "STRUCT")
        fields = []
        while not self.accept("kw", "END_STRUCT"):
            names = [self.expect("id")[1]]
            while self.accept("op", ","):
                names.append(self.expect("id")[1])
            self.expect("op", ":")
            arr, dims = None, None
            if self.accept("kw", "ARRAY"):
                self.expect("op", "[")
                dims = []
                while True:
                    lo = self.expr()
                    self.expect("op", "..")
                    hi = self.expr()
                    dims.append((lo, hi))
                    if not self.accept("op", ","):
                        break
                self.expect("op", "]")
                self.expect("kw", "OF")
                arr = dims[0]
            tname = self.expect("id")[1].upper()
            init = self.init_value() if self.accept("op", ":=") else None
            self.expect("op", ";")
            for n in names:
                fields.append({"name": n, "type": tname, "init": init, "array": arr, "dims": dims})
        self.accept("op", ";")
        self.expect("kw", "END_TYPE")
        self.accept("op", ";")
        return {"name": name, "fields": fields}

    def init_value(self):
        """expression, array initialiser [1, 2, 3], or struct initialiser (a := 1, b := 2);
        nests freely, e.g. (buf := [1, 2], m := (x := 3))."""
        if self.accept("op", "["):
            items = []
            while True:
                v = self.init_value()
                if self.is_("op", "(") and v[0] == "num" and isinstance(v[1], int):
                    self.next()  # 重複初值 n(v)
                    items.extend([self.init_value()] * v[1])
                    self.expect("op", ")")
                else:
                    items.append(v)
                if not self.accept("op", ","):
                    break
            self.expect("op", "]")
            return ("arrinit", items)
        if self.is_("op", "(") and self.t[self.i + 1][0] == "id" and self.t[self.i + 2][1] == ":=":
            self.next()
            items = []
            while True:
                fname = self.expect("id")[1]
                self.expect("op", ":=")
                items.append((fname, self.init_value()))
                if self.accept("op", ")"):
                    return ("structinit", items)
                self.expect("op", ",")
        return self.expr()

    def parse(self):
        """[TYPE | FUNCTION | FUNCTION_BLOCK | VAR_GLOBAL]* PROGRAM ... END_PROGRAM
        頂層 VAR_GLOBAL(CODESYS GVL 寫法)與 PROGRAM 內的 VAR_GLOBAL 都併入程式宣告(section=global,放最前面)。"""
        functions, fbdefs, types, gdecls = {}, {}, {}, []
        while self.peek()[0] == "kw" and self.peek()[1] in ("TYPE", "FUNCTION", "FUNCTION_BLOCK", "VAR_GLOBAL"):
            k = self.peek()[1]
            if k == "TYPE":
                td = self.type_def()
                if td["name"].lower() in types:
                    raise STError(f"duplicate definition of {td['name']}")
                types[td["name"].lower()] = td
            elif k == "VAR_GLOBAL":
                gdecls += self.var_block()
            else:
                d = self.pou_def()
                tbl = functions if d["kind"] == "function" else fbdefs
                if d["name"].lower() in functions or d["name"].lower() in fbdefs:
                    raise STError(f"duplicate definition of {d['name']}")
                tbl[d["name"].lower()] = d
        name = "Main"
        if self.accept("kw", "PROGRAM"):
            name = self.expect("id")[1]
        decls = []
        while self.peek()[0] == "kw" and self.peek()[1] in SECTIONS:
            decls += self.var_block()
        body = self.statements({"END_PROGRAM"})
        self.accept("kw", "END_PROGRAM")
        self.expect("eof")
        # 依 glob 旗標(而非 section)提前:帶 %I/%Q 位址的全域變數 section 已改成 input/output
        gdecls += [d for d in decls if d.get("glob")]
        decls = gdecls + [d for d in decls if not d.get("glob")]
        return {"name": name, "decls": decls, "body": body, "functions": functions, "fbs": fbdefs, "types": types}

    def var_block(self):
        section = SECTIONS[self.next()[1]]
        quals = set()
        while self.peek()[0] == "kw" and self.peek()[1] in _QUALS:
            quals.add(self.next()[1])
        const, retain = "CONSTANT" in quals, bool(quals & {"RETAIN", "PERSISTENT"})
        out = []
        while not self.accept("kw", "END_VAR"):
            ln = self.peek()[2]
            names = [self.expect("id")[1]]
            while self.accept("op", ","):
                names.append(self.expect("id")[1])
            addr = None
            if self.peek()[0] == "id" and self.peek()[1].upper() == "AT":
                self.next()
                k, v, aln = self.next()
                if k != "addr" or parse_addr(v) is None:
                    raise STError(f"line {aln}: AT needs a direct address like %IX0.0 / %QW2 / %MD10")
                if len(names) > 1:
                    raise STError(f"line {aln}: AT address can only be given to a single variable")
                addr = v
            self.expect("op", ":")
            arr = None
            if self.accept("kw", "ARRAY"):
                self.expect("op", "[")
                dims = []
                while True:
                    lo = self.expr()
                    self.expect("op", "..")
                    hi = self.expr()
                    dims.append((lo, hi))
                    if not self.accept("op", ","):
                        break
                self.expect("op", "]")
                self.expect("kw", "OF")
                arr = dims[0]
            tname = self.expect("id")[1].upper()
            init = self.init_value() if self.accept("op", ":=") else None
            self.expect("op", ";")
            # 直接位址決定模擬時的 I/O 角色:%I 視為輸入、%Q 視為輸出(%M 維持原區段)
            if section == "external" and addr:
                raise STError(f"line {ln}: AT address is not allowed in VAR_EXTERNAL (give it in VAR_GLOBAL)")
            if section == "external" and init is not None:
                raise STError(f"line {ln}: VAR_EXTERNAL {names[0]} cannot have an initial value (set it in VAR_GLOBAL)")
            eff = section
            if addr and section in ("local", "global"):
                eff = {"I": "input", "Q": "output"}.get(addr[1], section)
            for n in names:
                out.append({"name": n, "type": tname, "section": eff, "init": init, "array": arr,
                            "dims": dims if arr else None, "const": const, "retain": retain,
                            "addr": addr, "line": ln, "glob": section == "global"})
        return out

    def statements(self, stops):
        out = []
        while True:
            k, v, ln = self.peek()
            if k == "eof" or (k == "kw" and v in stops):
                return out
            s = self.statement()
            if s:
                out.append(s)

    def statement(self):
        k, v, ln = self.peek()
        if self.accept("op", ";"):
            return None
        if k == "kw":
            if v == "IF":
                return self.if_stmt()
            if v == "CASE":
                return self.case_stmt()
            if v == "FOR":
                self.next()
                var = self.expect("id")[1]
                self.expect("op", ":=")
                a = self.expr()
                self.expect("kw", "TO")
                b = self.expr()
                step = self.expr() if self.accept("kw", "BY") else ("num", 1)
                self.expect("kw", "DO")
                body = self.statements({"END_FOR"})
                self.expect("kw", "END_FOR")
                self.accept("op", ";")
                return ("for", var, a, b, step, body)
            if v == "WHILE":
                self.next()
                c = self.expr()
                self.expect("kw", "DO")
                body = self.statements({"END_WHILE"})
                self.expect("kw", "END_WHILE")
                self.accept("op", ";")
                return ("while", c, body)
            if v == "REPEAT":
                self.next()
                body = self.statements({"UNTIL"})
                self.expect("kw", "UNTIL")
                c = self.expr()
                self.expect("kw", "END_REPEAT")
                self.accept("op", ";")
                return ("repeat", body, c)
            if v == "RETURN":
                self.next()
                self.accept("op", ";")
                return ("return",)
            if v == "EXIT":
                self.next()
                self.accept("op", ";")
                return ("exit",)
            raise STError(f"line {ln}: unexpected keyword {v}")
        target = self.designator()
        if self.accept("op", ":="):
            e = self.expr()
            self.expect("op", ";")
            return ("assign", target, e, ln)
        if self.accept("op", "("):
            args = self.call_args()
            self.expect("op", ";")
            return ("call", target, args, ln)
        raise STError(f"line {ln}: expected := or ( after {target}")

    def designator(self):
        name = self.expect("id")[1]
        return self.selectors(("var", name))

    def selectors(self, node):
        while True:
            if self.accept("op", "."):
                node = ("member", node, self.expect("id")[1])
            elif self.accept("op", "["):
                node = ("index", node, self.expr())
                while self.accept("op", ","):  # a[i,j] == a[i][j] (row-major)
                    node = ("index", node, self.expr())
                self.expect("op", "]")
            else:
                return node

    def call_args(self):
        args = []
        if self.accept("op", ")"):
            return args
        while True:
            if self.peek()[0] == "id" and self.t[self.i + 1][1] in (":=", "=>"):
                name = self.next()[1]
                op = self.next()[1]
                args.append((name, op, self.expr()))
            else:
                args.append((None, ":=", self.expr()))
            if self.accept("op", ")"):
                return args
            self.expect("op", ",")

    def if_stmt(self):
        self.expect("kw", "IF")
        branches = []
        c = self.expr()
        self.expect("kw", "THEN")
        branches.append((c, self.statements({"ELSIF", "ELSE", "END_IF"})))
        els = []
        while True:
            if self.accept("kw", "ELSIF"):
                c = self.expr()
                self.expect("kw", "THEN")
                branches.append((c, self.statements({"ELSIF", "ELSE", "END_IF"})))
            elif self.accept("kw", "ELSE"):
                els = self.statements({"END_IF"})
            else:
                break
        self.expect("kw", "END_IF")
        self.accept("op", ";")
        return ("if", branches, els)

    def case_stmt(self):
        self.expect("kw", "CASE")
        sel = self.expr()
        self.expect("kw", "OF")
        arms, els = [], []
        while not self.is_("kw", "END_CASE"):
            if self.accept("kw", "ELSE"):
                els = self.statements({"END_CASE"})
                break
            labels = []
            while True:
                lo = self.expr()
                if self.accept("op", ".."):
                    labels.append((lo, self.expr()))
                else:
                    labels.append((lo, None))
                if not self.accept("op", ","):
                    break
            self.expect("op", ":")
            body = []
            while not (self.is_("kw", "END_CASE") or self.is_("kw", "ELSE") or self._label_ahead()):
                s = self.statement()
                if s:
                    body.append(s)
            arms.append((labels, body))
        self.expect("kw", "END_CASE")
        self.accept("op", ";")
        return ("case", sel, arms, els)

    def _label_ahead(self):
        k, v, _ = self.peek()
        if k == "num" or (k == "kw" and v in ("TRUE", "FALSE")) or (k == "op" and v == "-"):
            return True
        return k == "id" and self.t[self.i + 1][1] in (":", ",")

    # -- expressions
    def expr(self):
        return self.binary(0)

    LEVELS = [("OR",), ("XOR",), ("AND",), ("=", "<>"), ("<", ">", "<=", ">="),
              ("+", "-"), ("*", "/", "MOD")]

    def binary(self, lvl):
        if lvl == len(self.LEVELS):
            return self.power()
        left = self.binary(lvl + 1)
        while True:
            k, v, _ = self.peek()
            if (k in ("kw", "op")) and v in self.LEVELS[lvl]:
                self.next()
                left = ("bin", v, left, self.binary(lvl + 1))
            else:
                return left

    def power(self):
        left = self.unary()
        if self.accept("op", "**"):
            return ("bin", "**", left, self.power())
        return left

    def unary(self):
        if self.accept("kw", "NOT"):
            return ("not", self.unary())
        if self.accept("op", "-"):
            return ("neg", self.unary())
        if self.accept("op", "+"):
            return self.unary()
        return self.primary()

    def primary(self):
        k, v, ln = self.next()
        if k == "num":
            return ("num", v)
        if k == "time":
            return ("time", v)
        if k == "str":
            return ("str", v)
        if k == "kw" and v in ("TRUE", "FALSE"):
            return ("bool", v == "TRUE")
        if k == "op" and v == "(":
            e = self.expr()
            self.expect("op", ")")
            return e
        if k == "id":
            if self.is_("op", "("):
                self.next()
                return ("func", v, self.call_args())
            return self.selectors(("var", v))
        if k == "addr":
            raise STError(f"line {ln}: direct address {v} cannot be used in code; "
                          f"declare a variable for it, e.g. `name AT {v} : BOOL;`")
        raise STError(f"line {ln}: unexpected token {v!r}")


def parse(src):
    return Parser(src).parse()
