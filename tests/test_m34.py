"""M34:VAR CONSTANT / RETAIN / VAR_TEMP 修飾詞與直接位址 AT %I/%Q/%M(解譯、檢查、方言、匯出、點位表、情境)。"""
import json
import unittest

from plc_st.checker import check
from plc_st.export import export, split_program, to_gxworks, to_l5x, to_plcopen, to_scl, to_sysmac, validate_plcopen
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError
from plc_st.parser import parse, parse_addr
from plc_st.scenario import run_scenario, run_scenario_detail
from plc_st.tags import preview_tags, tags_to_var_blocks
from plc_st.web import State as AppState, handle

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


SRC = read("examples/qualifiers_m34.st")


def prog(decl, body=""):
    return f"PROGRAM P\n{decl}\n{body}\nEND_PROGRAM\n"


def msgs(src, profile="iec", sev=None):
    return [i.msg for i in check(src, profile) if sev is None or i.severity == sev]


class ParseTest(unittest.TestCase):
    def test_qualifiers_and_address_recorded(self):
        d = {x["name"]: x for x in parse(SRC)["decls"]}
        self.assertTrue(d["N"]["const"] and not d["N"]["retain"])
        self.assertTrue(d["total"]["retain"] and not d["total"]["const"])
        self.assertEqual(d["i"]["section"], "temp")
        self.assertEqual((d["start"]["addr"], d["start"]["section"]), ("%IX0.0", "input"))
        self.assertEqual((d["motor"]["addr"], d["motor"]["section"]), ("%QX0.0", "output"))
        self.assertEqual((d["full"]["addr"], d["full"]["section"]), ("%MX1.0", "local"))

    def test_parse_addr(self):
        self.assertEqual(parse_addr("%ix0.3")["bits"], 1)
        self.assertEqual(parse_addr("%I0.3")["size"], "X")
        self.assertEqual(parse_addr("%QW2")["bits"], 16)
        self.assertEqual(parse_addr("%MD10")["bits"], 32)
        for bad in ("%IX0.8", "%QW2.1", "%ZX0.0", "IX0.0", "%I"):
            self.assertIsNone(parse_addr(bad), bad)

    def test_bad_at_reports_line(self):
        for decl in ("VAR\n x AT 5 : BOOL;\nEND_VAR", "VAR\n x AT %ZZ9 : BOOL;\nEND_VAR", "VAR\n a, b AT %IX0.0 : BOOL;\nEND_VAR"):
            with self.assertRaises(STError) as c:
                parse(prog(decl))
            self.assertIn("line 3", str(c.exception))

    def test_address_in_body_has_helpful_error(self):
        with self.assertRaises(STError) as c:
            parse(prog("VAR x : BOOL; END_VAR", "x := %IX0.0;"))
        self.assertIn("declare a variable", str(c.exception))

    def test_variable_named_at_still_works(self):
        plc = VirtualPLC(prog("VAR at : INT; END_VAR", "at := at + 1;"))
        plc.scan(3)
        self.assertEqual(plc.get("at"), 3)


class RuntimeTest(unittest.TestCase):
    def test_example_runs(self):
        plc = VirtualPLC(SRC)
        plc.set_input("start", True)
        for v in (True, False, True, False):
            plc.set_input("sensor", v)
            plc.scan(1)
        self.assertEqual((plc.get("total"), plc.get("batch")), (2, 2))
        self.assertEqual(plc.get("speed"), 100)  # VAR_TEMP sum 每週期歸零:1+2+3+4 = 10
        self.assertTrue(plc.get("motor"))

    def test_temp_reinitialised_every_scan(self):
        plc = VirtualPLC(prog("VAR_TEMP t : INT := 5; END_VAR\nVAR keep, seen : INT; END_VAR",
                              "seen := t; t := t + 1; keep := keep + 1;"))
        plc.scan(3)
        self.assertEqual((plc.get("seen"), plc.get("keep")), (5, 3))

    def test_temp_in_function_block_reinitialised_each_call(self):
        src = ("FUNCTION_BLOCK Acc\nVAR_INPUT x : INT; END_VAR\nVAR_OUTPUT y, n : INT; END_VAR\nVAR_TEMP t : INT; END_VAR\n"
               "t := t + x; y := t; n := n + 1;\nEND_FUNCTION_BLOCK\n"
               + prog("VAR a : Acc; r, n : INT; END_VAR", "a(x := 7); r := a.y; n := a.n;"))
        plc = VirtualPLC(src)
        plc.scan(4)
        self.assertEqual((plc.get("r"), plc.get("n")), (7, 4))

    def test_constant_write_rejected_at_runtime(self):
        for body in ("K := 2;", "A[1] := 2;"):
            plc = VirtualPLC(prog("VAR CONSTANT K : INT := 1; A : ARRAY[0..1] OF INT := [1, 2]; END_VAR", body))
            with self.assertRaises(STError) as c:
                plc.scan(1)
            self.assertIn("CONSTANT", str(c.exception))

    def test_constant_cannot_be_forced(self):
        plc = VirtualPLC(SRC)
        with self.assertRaises(STError):
            plc.set_input("N", 9)

    def test_constant_as_array_bound(self):
        plc = VirtualPLC(SRC)
        self.assertEqual([plc.get(f"slots[{k}]") for k in range(4)], [1, 2, 3, 4])
        with self.assertRaises(STError):
            plc.get("slots[4]")

    def test_warm_and_cold_restart(self):
        plc = VirtualPLC(SRC)
        for v in (True, False, True, False):
            plc.set_input("sensor", v)
            plc.scan(1)
        plc.restart(warm=True)
        self.assertEqual((plc.get("total"), plc.get("batch")), (2, 0))
        plc.scan(1)
        self.assertEqual(plc.get("total"), 2)
        plc.restart(warm=False)
        self.assertEqual(plc.get("total"), 0)

    def test_retain_struct_and_fb_kept_on_warm_restart(self):
        src = ("TYPE R : STRUCT a : INT; b : INT; END_STRUCT END_TYPE\n"
               + prog("VAR RETAIN r : R; c : CTU; END_VAR\nVAR x : INT; END_VAR",
                      "r.a := r.a + 1; x := x + 1; c(CU := (x MOD 2) = 1, PV := 100);"))
        plc = VirtualPLC(src)
        plc.scan(4)
        plc.restart()
        self.assertEqual((plc.get("r.a"), plc.get("x"), plc.get("c.CV")), (4, 0, 2))


class CheckerTest(unittest.TestCase):
    def test_example_is_clean(self):
        self.assertEqual(msgs(SRC), [])

    def test_constant_writes_are_errors(self):
        decl = "VAR CONSTANT K : INT := 1; A : ARRAY[0..1] OF INT := [1, 2]; END_VAR\nVAR c : CTU; j : INT; END_VAR"
        for body in ("K := 2;", "A[0] := 2;", "FOR K := 0 TO 1 DO j := j + 1; END_FOR;", "c(CU := TRUE, CV => K);"):
            self.assertIn("write to CONSTANT", " ".join(msgs(prog(decl, body), sev="error")), body)

    def test_reading_constant_is_fine(self):
        self.assertEqual(msgs(prog("VAR CONSTANT K : INT := 1; END_VAR\nVAR j : INT; END_VAR", "j := K + 1;")), [])

    def test_constant_without_init_warns(self):
        self.assertIn("CONSTANT K has no initial value", msgs(prog("VAR CONSTANT K : INT; END_VAR"), sev="warning"))

    def test_address_size_mismatch(self):
        m = msgs(prog("VAR\n a AT %QW0 : BOOL;\n b AT %IX0.0 : INT;\n c AT %MD4 : REAL;\n t AT %MW8 : TON;\nEND_VAR"), sev="error")
        self.assertEqual(len(m), 3)
        self.assertIn("BOOL (1 bit) does not fit address %QW0 (16 bit)", m[0])
        self.assertIn("TON cannot be placed", m[2])

    def test_overlap_depends_on_vendor_addressing(self):
        src = prog("VAR\n a AT %MW0 : INT;\n b AT %MW1 : INT;\n x AT %MX0.3 : BOOL;\nEND_VAR")
        iec = [m for m in msgs(src) if "overlaps" in m]
        s7 = [m for m in msgs(src, "siemens-s7-1500") if "overlaps" in m]
        self.assertEqual(len(iec), 1)  # IEC:%MW1 是第 1 個 word(byte 2..3),只有 %MX0.3 與 %MW0 重疊
        self.assertEqual(len(s7), 2)   # S7:%MW1 = byte 1..2,與 %MW0(byte 0..1)重疊
        self.assertIn("b at %MW1 overlaps a at %MW0", s7[0])

    def test_write_to_input_address_warns(self):
        self.assertIn("write to input variable s", msgs(prog("VAR s AT %IX0.0 : BOOL; END_VAR", "s := TRUE;"), sev="warning"))

    def test_located_var_in_fb_and_temp(self):
        src = ("FUNCTION_BLOCK F\nVAR q AT %QX0.0 : BOOL; END_VAR\nq := TRUE;\nEND_FUNCTION_BLOCK\n"
               + prog("VAR_TEMP t AT %MX0.0 : BOOL; END_VAR\nVAR f : F; END_VAR", "f();"))
        m = " | ".join(msgs(src))
        self.assertIn("inside FUNCTION_BLOCK F", m)
        self.assertIn("VAR_TEMP t cannot have a direct address", m)

    def test_issue_lines(self):
        i = [x for x in check(prog("VAR\n a AT %QW0 : BOOL;\nEND_VAR")) if x.severity == "error"][0]
        self.assertEqual(i.line, 3)


class DialectTest(unittest.TestCase):
    def d(self, profile):
        return [m for m in msgs(SRC, profile, "warning") if m.startswith("dialect")]

    def test_generic_profiles_silent(self):
        self.assertEqual(self.d("iec") + self.d("codesys"), [])

    def test_siemens(self):
        m = self.d("siemens-s7-1500")
        self.assertTrue(any("%IX0.0: TIA Portal writes bit addresses without X (%I0.0)" in x for x in m))
        self.assertEqual(sum("PLC tag table" in x for x in m), 1)
        self.assertFalse(any("%QW2:" in x for x in m))

    def test_tag_based_platforms(self):
        for prof, word in (("rockwell", "alias"), ("mitsubishi", "devices"), ("omron", "I/O Map")):
            m = self.d(prof)
            self.assertEqual(sum("direct address" in x for x in m), 1, prof)
            self.assertTrue(any(word in x for x in m), prof)
            self.assertTrue(any("VAR_TEMP" in x for x in m), prof)

    def test_persistent(self):
        src = prog("VAR RETAIN PERSISTENT k : INT; END_VAR", "k := k + 1;")
        self.assertEqual(msgs(src, "codesys"), [])
        self.assertTrue(any("PERSISTENT is a CODESYS extension" in x for x in msgs(src, "omron")))


class ExportTest(unittest.TestCase):
    def test_modifier_not_merged_into_name(self):
        _, blocks, _, _ = split_program(SRC)
        self.assertEqual([(str(k), sorted(k.mods)) for k, _ in blocks],
                         [("VAR", ["CONSTANT"]), ("VAR", ["RETAIN"]), ("VAR_TEMP", []), ("VAR", [])])
        self.assertEqual([n for n, _, _ in blocks[0][1]], ["N", "MAX_COUNT"])
        self.assertEqual(blocks[3][0].addrs["speed"], "%QW2")
        self.assertEqual([n for n, _, _ in blocks[3][1]][:2], ["start", "sensor"])

    def test_plcopen(self):
        x = to_plcopen(SRC)
        for frag in ('<localVars constant="true">', '<localVars retain="true">', "<tempVars>",
                     '<variable name="start" address="%IX0.0">', '<variable name="speed" address="%QW2">',
                     '<dimension lower="0" upper="3"/>'):
            self.assertIn(frag, x)
        self.assertNotIn("CONSTANT", x)

    def test_plcopen_schema(self):
        try:
            errs = validate_plcopen(to_plcopen(SRC))
        except STError as e:
            self.skipTest(str(e))
        self.assertEqual(errs, [])
        self.assertEqual(validate_plcopen(to_plcopen(prog("VAR RETAIN PERSISTENT k : INT; END_VAR\nVAR NON_RETAIN j : INT; END_VAR", "k := j;"))), [])

    def test_scl(self):
        s = to_scl(SRC)
        self.assertIn("// start\tBool\t%I0.0", s)
        self.assertIn("// speed\tInt\t%QW2", s)
        self.assertIn("// full\tBool\t%M1.0", s)
        self.assertNotIn(" AT ", s)
        self.assertIn("VAR CONSTANT", s)
        self.assertIn("VAR RETAIN", s)
        self.assertIn("slots : ARRAY[0..3] OF INT := [1, 2, 3, 4];", s)
        self.assertIn("  sum : INT;", s)                     # VAR_TEMP 初值移到本體
        self.assertIn("BEGIN\ni := 0;\nsum := 0;\nedge(CLK := \"sensor\");", s)
        self.assertIn('"motor" := "start" AND NOT "full";', s)
        self.assertIn("// 'start' in a string or (* start *) comment stays untouched", s)

    def test_scl_named_parameter_not_quoted(self):
        src = prog("VAR\n IN AT %IX0.0 : BOOL;\n q AT %QX0.0 : BOOL;\n t : TON;\nEND_VAR", "t(IN := IN, PT := T#1s);\nq := t.Q AND IN;")
        s = to_scl(src)
        self.assertIn('t(IN := "IN", PT := T#1s);', s)
        self.assertIn('"q" := t.Q AND "IN";', s)

    def test_scl_persistent_and_fb_address(self):
        s = to_scl(prog("VAR RETAIN PERSISTENT k : INT; END_VAR", "k := k + 1;"))
        self.assertIn("VAR RETAIN\n", s.replace("VAR RETAIN k", "VAR RETAIN\nk"))
        self.assertNotIn("PERSISTENT", s)
        src = "FUNCTION_BLOCK F\nVAR q AT %QX0.0 : BOOL; END_VAR\nq := TRUE;\nEND_FUNCTION_BLOCK\n" + prog("VAR f : F; END_VAR", "f();")
        with self.assertRaises(STError):
            to_scl(src)

    def test_scl_function_constant_and_bounds(self):
        src = ("FUNCTION Sum : INT\nVAR CONSTANT M : INT := 2; END_VAR\nVAR_INPUT a : INT; END_VAR\n"
               "VAR buf : ARRAY[0..M] OF INT; END_VAR\nSum := a + M;\nEND_FUNCTION\n" + prog("VAR r : INT; END_VAR", "r := Sum(1);"))
        s = to_scl(src)
        self.assertIn("VAR CONSTANT\n      M : INT := 2;", s)
        self.assertIn("buf : ARRAY[0..2] OF INT;", s)

    def test_l5x(self):
        x = to_l5x(SRC)
        self.assertIn('<Tag Name="N" TagType="Base" DataType="INT" Usage="Local" Constant="true" ExternalAccess="Read/Write">'
                      '<Data Format="Decorated"><DataValue DataType="INT" Radix="Decimal" Value="4"/></Data></Tag>', x)
        self.assertIn('Name="slots" TagType="Base" DataType="INT" Dimensions="4"', x)
        self.assertIn("IEC address %IX0.0", x)
        self.assertIn('<Line Number="1"><![CDATA[sum := 0;]]></Line>', x)
        self.assertNotIn('Name="CONSTANT"', x)

    def test_l5x_literal_initial_values(self):
        x = to_l5x(prog("VAR b : BOOL := TRUE; r : REAL := 2.5; t : TIME := T#1s500ms; h : INT := 16#1F; n : DINT := -7; e : INT := 2 + 3; END_VAR", "n := n;"))
        for v in ('DataType="BOOL" Radix="Decimal" Value="1"', 'DataType="REAL" Radix="Float" Value="2.5"',
                  'DataType="DINT" Radix="Decimal" Value="1500"', 'Value="31"', 'Value="-7"'):
            self.assertIn(v, x)
        self.assertIn('<Tag Name="e" TagType="Base" DataType="INT" Usage="Local" Constant="false" ExternalAccess="Read/Write"/>', x)

    def test_l5x_constant_needs_literal(self):
        with self.assertRaises(STError) as c:
            to_l5x(prog("VAR CONSTANT K : INT := 2 + 3; END_VAR\nVAR j : INT; END_VAR", "j := K;"))
        self.assertIn("常數 K", str(c.exception))

    def test_gxworks_and_sysmac(self):
        g = to_gxworks(SRC).splitlines()
        self.assertIn("VAR_CONSTANT\tN\tWord [Signed]\t4\t", g)
        self.assertIn("VAR_RETAIN\ttotal\tDouble Word [Signed]\t\t", g)
        self.assertIn("VAR\tstart\tBit\t\t%IX0.0", g)
        self.assertIn("VAR\tslots\tARRAY[0..3] OF INT\t[1, 2, 3, 4]\t", g)
        self.assertEqual(g[g.index("(* === ST Program Body === *)") + 1:][:2], ["i := 0;", "sum := 0;"])
        o = to_sysmac(SRC).splitlines()
        self.assertIn("N\tINT\t4\tInternal\tFALSE\tTRUE\t", o)
        self.assertIn("total\tDINT\t\tInternal\tTRUE\tFALSE\t", o)
        self.assertIn("motor\tBOOL\t\tInternal\tFALSE\tFALSE\t%QX0.0", o)

    def test_plain_program_output_unchanged(self):
        motor = read("examples/motor.st")
        self.assertTrue(to_gxworks(motor).splitlines()[2] == "Class\tLabel Name\tData Type\tInitial Value")
        self.assertTrue(to_sysmac(motor).splitlines()[2] == "Name\tData Type\tInitial Value\tClass")
        self.assertNotIn("PLC 變數表", to_scl(motor))

    def test_all_formats_export(self):
        for fmt in ("plcopen", "scl", "l5x", "gxworks", "sysmac", "st"):
            self.assertTrue(export(SRC, fmt), fmt)


class TagsScenarioWebTest(unittest.TestCase):
    CSV = read("examples/points_addr.csv")

    def test_tags_with_address_and_qualifiers(self):
        t = tags_to_var_blocks(self.CSV)
        self.assertIn("VAR CONSTANT\n  MAX_COUNT : DINT := 1000;", t)
        self.assertIn("VAR RETAIN\n  total : DINT;", t)
        self.assertIn("  start AT %IX0.0 : BOOL;", t)
        self.assertNotIn("VAR_INPUT", t)
        self.assertEqual([i for i in check(f"PROGRAM P\n{t}motor := start;\nEND_PROGRAM") if i.severity == "error"], [])

    def test_tags_address_errors(self):
        p = preview_tags("name,type,direction,address\na,BOOL,IN,%QX0.0\nb,BOOL,OUT,X0\nc,BOOL,CONST,%MX0.0\nd,BOOL,IN,%ix0.1\n")
        errs = [r["error"] for r in p["rows"]]
        self.assertIn("不一致", errs[0])
        self.assertIn("不是合法", errs[1])
        self.assertIn("不可指定位址", errs[2])
        self.assertIsNone(errs[3])
        self.assertEqual(p["rows"][3]["address"], "%IX0.1")
        with self.assertRaises(STError):
            tags_to_var_blocks("name,type,direction,address\na,BOOL,IN,%QX0.0\n")

    def test_old_csv_unchanged(self):
        t = tags_to_var_blocks(read("examples/points.csv"))
        self.assertTrue(t.startswith("VAR_INPUT\n  start : BOOL;"))

    def test_scenario_restart(self):
        spec = json.loads(read("examples/qualifiers_m34_scenario.json"))
        self.assertEqual(run_scenario(SRC, spec), [])
        with self.assertRaises(STError):
            run_scenario_detail(SRC, {"steps": [{"restart": "hot"}]})

    def test_web_meta_and_restart(self):
        st = AppState()
        code, j = handle("POST", "/api/sim/start", {"code": SRC}, st)
        self.assertEqual(code, 200)
        meta = {m["name"]: m for m in j["meta"]}
        self.assertEqual(meta["start"]["addr"], "%IX0.0")
        self.assertTrue(meta["N"]["const"] and meta["total"]["retain"])
        col = j["columns"].index
        for v in (True, False, True, False):
            code, r = handle("POST", "/api/sim/step", {"id": j["id"], "set": {"sensor": v}}, st)
        self.assertEqual((r["rows"][-1][col("total")], r["rows"][-1][col("batch")]), (2, 2))
        code, r = handle("POST", "/api/sim/step", {"id": j["id"], "restart": "warm"}, st)
        self.assertEqual((code, r["rows"][-1][col("total")], r["rows"][-1][col("batch")]), (200, 2, 0))
        self.assertEqual(handle("POST", "/api/sim/step", {"id": j["id"], "set": {"N": 9}}, st)[0], 400)
        self.assertEqual(handle("POST", "/api/sim/step", {"id": j["id"], "restart": "x"}, st)[0], 400)

    def test_export_status_all_ok(self):
        code, j = handle("POST", "/api/export/status", {"code": SRC}, AppState())
        self.assertEqual([f["format"] for f in j["formats"] if not f["ok"]], [])


if __name__ == "__main__":
    unittest.main()
