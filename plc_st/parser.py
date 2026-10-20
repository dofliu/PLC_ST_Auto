"""Recursive-descent ST parser producing tuple ASTs."""
from .lexer import tokenize, STError

SECTIONS = {"VAR": "local", "VAR_INPUT": "input", "VAR_OUTPUT": "output", "VAR_IN_OUT": "inout"}


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
    def parse(self):
        name = "Main"
        if self.accept("kw", "PROGRAM"):
            name = self.expect("id")[1]
        decls = []
        while self.peek()[0] == "kw" and self.peek()[1] in SECTIONS:
            decls += self.var_block()
        body = self.statements({"END_PROGRAM"})
        self.accept("kw", "END_PROGRAM")
        self.expect("eof")
        return {"name": name, "decls": decls, "body": body}

    def var_block(self):
        section = SECTIONS[self.next()[1]]
        while self.accept("kw", "RETAIN") or self.accept("kw", "CONSTANT"):
            pass
        out = []
        while not self.accept("kw", "END_VAR"):
            names = [self.expect("id")[1]]
            while self.accept("op", ","):
                names.append(self.expect("id")[1])
            self.expect("op", ":")
            tname = self.expect("id")[1].upper()
            size = None
            if tname == "ARRAY":
                raise STError("ARRAY not supported yet")
            init = None
            if self.accept("op", ":="):
                init = self.expr()
            self.expect("op", ";")
            for n in names:
                out.append({"name": n, "type": tname, "section": section, "init": init})
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
        node = ("var", name)
        while self.accept("op", "."):
            node = ("member", node, self.expect("id")[1])
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
                if self.is_("op", ".") and self.t[self.i + 1][1] == ".":
                    self.next()
                    self.next()
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
            node = ("var", v)
            while self.accept("op", "."):
                node = ("member", node, self.expect("id")[1])
            return node
        raise STError(f"line {ln}: unexpected token {v!r}")


def parse(src):
    return Parser(src).parse()
