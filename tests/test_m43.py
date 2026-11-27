"""M43:VAR_GLOBAL / VAR_EXTERNAL(多 POU 共用變數)— 語法、虛擬 PLC、檢查器、方言、匯出。"""
import json
import os
import threading
import unittest
import urllib.request

from plc_st.checker import check
from plc_st.export import export, global_blocks, validate_plcopen
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError
from plc_st.parser import parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def errs(src, profile="iec"):
    return [str(i) for i in check(src, profile) if i.severity == "error"]


def warns(src, profile="iec"):
    return [str(i) for i in check(src, profile) if i.severity == "warning"]


BASIC = """VAR_GLOBAL CONSTANT K : INT := 3; END_VAR
VAR_GLOBAL
  g : INT := 10;
  arr : ARRAY[0..2] OF INT;
  flag : BOOL;
END_VAR
FUNCTION_BLOCK Adder
VAR_EXTERNAL g : INT; arr : ARRAY[0..2] OF INT; END_VAR
VAR_EXTERNAL CONSTANT K : INT; END_VAR
VAR_INPUT i : INT; END_VAR
g := g + K;
arr[i] := g;
END_FUNCTION_BLOCK
FUNCTION GetG : INT
VAR_EXTERNAL g : INT; END_VAR
GetG := g * 2;
END_FUNCTION
FUNCTION_BLOCK Direct
flag := NOT flag;
END_FUNCTION_BLOCK
PROGRAM Main
VAR a : Adder; d : Direct; out : INT; END_VAR
a(i := 1);
d();
out := GetG();
END_PROGRAM
"""


class Parse(unittest.TestCase):
    def test_globals_merged_first_with_flag(self):
        ast = parse(BASIC)
        names = [(d["name"], d["section"], d["glob"]) for d in ast["decls"]][:4]
        self.assertEqual(names, [("K", "global", True), ("g", "global", True), ("arr", "global", True), ("flag", "global", True)])
        self.assertTrue(ast["decls"][0]["const"])
        ext = [d for d in ast["fbs"]["adder"]["decls"] if d["section"] == "external"]
        self.assertEqual([d["name"] for d in ext], ["g", "arr", "K"])

    def test_global_inside_program_and_between_pous(self):
        src = """FUNCTION_BLOCK F VAR_EXTERNAL x : INT; END_VAR x := x + 1; END_FUNCTION_BLOCK
VAR_GLOBAL x : INT; END_VAR
PROGRAM P VAR_GLOBAL y : BOOL; END_VAR VAR f : F; END_VAR f(); y := x > 1; END_PROGRAM"""
        ast = parse(src)
        self.assertEqual([(d["name"], d["glob"]) for d in ast["decls"]], [("x", True), ("y", True), ("f", False)])

    def test_syntax_errors(self):
        with self.assertRaisesRegex(STError, "VAR_GLOBAL is not allowed inside F"):
            parse("FUNCTION_BLOCK F VAR_GLOBAL x : INT; END_VAR END_FUNCTION_BLOCK PROGRAM P END_PROGRAM")
        with self.assertRaisesRegex(STError, "cannot have an initial value"):
            parse("VAR_GLOBAL x : INT; END_VAR FUNCTION_BLOCK F VAR_EXTERNAL x : INT := 1; END_VAR END_FUNCTION_BLOCK PROGRAM P END_PROGRAM")
        with self.assertRaisesRegex(STError, "AT address is not allowed in VAR_EXTERNAL"):
            parse("VAR_GLOBAL x : INT; END_VAR FUNCTION_BLOCK F VAR_EXTERNAL x AT %MW0 : INT; END_VAR END_FUNCTION_BLOCK PROGRAM P END_PROGRAM")


class Simulate(unittest.TestCase):
    def test_fb_and_function_share_globals(self):
        plc = VirtualPLC(BASIC)
        plc.scan()
        self.assertEqual(plc.get("g"), 13)
        self.assertEqual(plc.get("arr[1]"), 13)
        self.assertEqual(plc.get("out"), 26)
        self.assertTrue(plc.get("flag"))  # 直接存取(CODESYS 式,無 VAR_EXTERNAL)
        plc.scan()
        self.assertEqual(plc.get("g"), 16)
        self.assertFalse(plc.get("flag"))

    def test_two_instances_one_global(self):
        plc = VirtualPLC(read("examples/global_vars.st"))
        for c in range(4):
            plc.set_input("sensorA", c % 2 == 0)
            plc.set_input("sensorB", c % 2 == 0)
            plc.scan()
        self.assertEqual(plc.get("g_count"), 4)  # 兩個實例各 2 個上升緣,共用同一計數
        self.assertEqual(plc.get("remain"), 1)
        plc.set_input("sensorA", True)
        plc.scan()
        self.assertTrue(plc.get("full"))
        plc.set_input("sensorA", False); plc.scan()
        plc.set_input("sensorA", True); plc.scan()
        self.assertEqual(plc.get("g_count"), 5)  # g_stop 之後不再累加

    def test_constant_global_write_blocked_at_runtime(self):
        src = """VAR_GLOBAL CONSTANT K : INT := 1; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL CONSTANT K : INT; END_VAR K := 2; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""
        with self.assertRaisesRegex(STError, "CONSTANT K"):
            VirtualPLC(src).scan()

    def test_local_shadows_global(self):
        src = """VAR_GLOBAL x : INT := 5; END_VAR
FUNCTION_BLOCK F VAR x : INT; END_VAR x := 99; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""
        plc = VirtualPLC(src)
        plc.scan()
        self.assertEqual(plc.get("x"), 5)

    def test_global_constant_bound_in_fb_array(self):
        src = """VAR_GLOBAL CONSTANT N : INT := 3; END_VAR
FUNCTION_BLOCK F VAR buf : ARRAY[0..N] OF INT; END_VAR VAR_OUTPUT last : INT; END_VAR
buf[N] := 7; last := buf[3]; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; v : INT; END_VAR f(); v := f.last; END_PROGRAM"""
        plc = VirtualPLC(src)
        plc.scan()
        self.assertEqual(plc.get("v"), 7)

    def test_retain_global_and_restart(self):
        src = """VAR_GLOBAL RETAIN total : INT; END_VAR
VAR_GLOBAL plain : INT; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL total : INT; plain : INT; END_VAR total := total + 1; plain := plain + 1; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""
        plc = VirtualPLC(src)
        plc.scan(); plc.scan()
        plc.restart(warm=True)
        plc.scan()
        self.assertEqual((plc.get("total"), plc.get("plain")), (3, 1))  # FB 重建後仍連到新的全域 scope
        plc.restart(warm=False)
        self.assertEqual(plc.get("total"), 0)

    def test_located_global_shared_memory(self):
        src = """VAR_GLOBAL w AT %MW0 : WORD; b AT %MX0.0 : BOOL; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL w : WORD; END_VAR w := 1; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""
        plc = VirtualPLC(src)
        plc.scan()
        self.assertTrue(plc.get("b"))  # FB 經 VAR_EXTERNAL 寫入,共用記憶體同步

    def test_missing_global_runtime_error(self):
        with self.assertRaisesRegex(STError, "no matching VAR_GLOBAL"):
            VirtualPLC("FUNCTION_BLOCK F VAR_EXTERNAL z : INT; END_VAR END_FUNCTION_BLOCK PROGRAM P VAR f : F; END_VAR END_PROGRAM")


class Checker(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(errs(BASIC), [])
        self.assertEqual(check(read("examples/global_vars.st")), [])

    def test_external_mismatch_and_missing(self):
        src = """VAR_GLOBAL g : INT; a : ARRAY[0..2] OF INT; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL g : DINT; a : ARRAY[0..3] OF INT; z : BOOL; END_VAR END_FUNCTION_BLOCK
PROGRAM P END_PROGRAM"""
        e = errs(src)
        self.assertTrue(any("VAR_EXTERNAL g type does not match VAR_GLOBAL (INT)" in x for x in e), e)
        self.assertTrue(any("VAR_EXTERNAL a type does not match" in x for x in e), e)
        self.assertTrue(any("VAR_EXTERNAL z has no matching VAR_GLOBAL" in x for x in e), e)

    def test_constant_rules(self):
        src = """VAR_GLOBAL CONSTANT K : INT := 1; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL K : INT; END_VAR K := 2; END_FUNCTION_BLOCK
PROGRAM P K := 3; END_PROGRAM"""
        self.assertTrue(any("declare it in VAR_EXTERNAL CONSTANT" in w for w in warns(src)))
        self.assertEqual(sum("write to CONSTANT K" in x for x in errs(src)), 2)

    def test_conflict_and_shadow(self):
        src = """VAR_GLOBAL g : INT; END_VAR
FUNCTION_BLOCK F VAR g : BOOL; END_VAR g := TRUE; END_FUNCTION_BLOCK
PROGRAM P VAR g : BOOL; END_VAR END_PROGRAM"""
        self.assertTrue(any("g conflicts with VAR_GLOBAL g" in x for x in errs(src)))
        self.assertTrue(any("g in F hides VAR_GLOBAL g" in w for w in warns(src)))

    def test_type_checks_through_external(self):
        src = """VAR_GLOBAL g : BOOL; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL g : BOOL; END_VAR g := 5; END_FUNCTION_BLOCK
PROGRAM P END_PROGRAM"""
        self.assertTrue(errs(src))

    def test_dialect_hints(self):
        src = read("examples/global_vars.st")
        for prof, word in (("siemens-s7-1500", "global DB"), ("rockwell", "controller-scoped"),
                           ("mitsubishi", "Global Label"), ("omron", "Global Variable table")):
            w = [x for x in warns(src, prof) if "VAR_GLOBAL" in x]
            self.assertEqual(len(w), 1, (prof, w))
            self.assertIn(word, w[0])
        self.assertFalse([x for x in warns(src, "codesys") if "VAR_GLOBAL" in x])


class Export(unittest.TestCase):
    def test_global_blocks(self):
        gb = global_blocks(read("examples/global_vars.st"))
        self.assertEqual([(str(k), sorted(k.mods), [n for n, _, _ in d]) for k, d in gb],
                         [("VAR_GLOBAL", ["CONSTANT"], ["G_LIMIT"]), ("VAR_GLOBAL", [], ["g_count", "g_stop", "g_log"])])

    def test_plcopen_globals_and_externals(self):
        x = export(read("examples/global_vars.st"), "plcopen")
        self.assertIn('<globalVars constant="true">', x)
        self.assertIn('<variable name="g_count"><type><INT/></type><initialValue><simpleValue value="0"/>', x)
        self.assertIn("<externalVars>", x)
        self.assertIn('<externalVars constant="true">', x)
        self.assertLess(x.index("</task>"), x.index("<globalVars"))
        try:
            self.assertEqual(validate_plcopen(x), [])
        except STError:
            self.skipTest("lxml not installed")

    def test_plcopen_global_inside_program(self):
        src = "PROGRAM P VAR_GLOBAL y : BOOL; END_VAR VAR z : INT; END_VAR z := 1; END_PROGRAM"
        x = export(src, "plcopen")
        self.assertIn("<globalVars>", x)
        self.assertNotIn("VAR_GLOBAL", x.split("<xhtml")[1])  # 宣告不殘留在本體

    def test_other_formats_rejected_with_reason(self):
        src = read("examples/global_vars.st")
        for fmt, word in (("scl", "全域 DB"), ("l5x", "controller-scope"), ("gxworks", "全域標籤"), ("sysmac", "全域變數表")):
            with self.assertRaisesRegex(STError, f"VAR_GLOBAL.*{word}"):
                export(src, fmt)
        self.assertEqual(export(src, "st"), src)


class Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from plc_st.web import make_server
        cls.srv = make_server("127.0.0.1", 0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, path, body):
        req = urllib.request.Request(self.url + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def test_simulate_meta_marks_globals(self):
        j = self.post("/api/run", {"code": read("examples/global_vars.st"), "cycles": 2})
        meta = {m["name"]: m for m in j["meta"]}
        self.assertTrue(meta["g_count"]["global"])
        self.assertTrue(meta["G_LIMIT"]["const"] and meta["G_LIMIT"]["global"])
        self.assertFalse(meta["sensorA"]["global"])
