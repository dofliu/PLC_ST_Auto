"""M41:ARRAY OF STRUCT 且 STRUCT 含 ARRAY 欄位(解譯/檢查/外部存取/整體複製/VAR_IN_OUT)。"""
import unittest

from plc_st.checker import check
from plc_st.export import export
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError
from plc_st.scenario import run_scenario_detail

EX = open("examples/recipe_slots.st", encoding="utf-8").read()

T = """TYPE Axis : STRUCT
  pos : ARRAY[1..3] OF INT := [1, 2, 3];
  on : BOOL;
END_STRUCT
END_TYPE
TYPE Cell : STRUCT
  ax : Axis;
  grid : ARRAY[0..1, 0..1] OF REAL;
END_STRUCT
END_TYPE
"""


def prog(decl, body):
    return T + f"PROGRAM Main\nVAR\n{decl}\nEND_VAR\n{body}\nEND_PROGRAM\n"


def errors(src):
    return [str(i) for i in check(src) if i.severity == "error"]


class Runtime(unittest.TestCase):
    def test_default_and_element_init(self):
        p = VirtualPLC(prog("a : ARRAY[1..3] OF Axis := [(pos := [7, 8]), (on := TRUE)];", ""))
        self.assertEqual([p.get(f"a[1].pos[{i}]") for i in (1, 2, 3)], [7, 8, 0])
        self.assertEqual([p.get(f"a[2].pos[{i}]") for i in (1, 2, 3)], [1, 2, 3])
        self.assertEqual([p.get(f"a[3].pos[{i}]") for i in (1, 2, 3)], [1, 2, 3])
        self.assertTrue(p.get("a[2].on"))

    def test_element_read_write_and_for(self):
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; s, i : INT;",
                            "a[1].pos[2] := 10; a[2].pos[3] := a[1].pos[2] + 5;\n"
                            "s := 0; FOR i := 1 TO 3 DO s := s + a[2].pos[i]; END_FOR;"))
        p.scan()
        self.assertEqual(p.get("a[1].pos[2]"), 10)
        self.assertEqual(p.get("a[2].pos[3]"), 15)
        self.assertEqual(p.get("a[1].pos[3]"), 3)  # 其他元素不受影響
        self.assertEqual(p.get("s"), 18)

    def test_multidim_outer_and_inner(self):
        p = VirtualPLC(prog("m : ARRAY[0..1, 1..2] OF Cell;",
                            "m[1,2].grid[1,0] := 2.5; m[0,1].ax.pos[3] := 9;"))
        p.scan()
        self.assertEqual(p.get("m[1,2].grid[1,0]"), 2.5)
        self.assertEqual(p.get("m[0,1].grid[1,0]"), 0.0)
        self.assertEqual(p.get("m[0,1].ax.pos[3]"), 9)
        self.assertEqual(p.get("m[1,1].ax.pos[3]"), 3)

    def test_struct_copy_element_both_ways(self):
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; w : Axis;",
                            "a[2].pos[1] := 42; w := a[2]; w.pos[2] := 5; a[1] := w; a[2].pos[1] := 0;"))
        p.scan()
        self.assertEqual([p.get(f"a[1].pos[{i}]") for i in (1, 2, 3)], [42, 5, 3])
        self.assertEqual(p.get("w.pos[1]"), 42)
        self.assertEqual(p.get("a[2].pos[1]"), 0)  # 深拷貝:改原件不影響副本

    def test_nested_struct_element_copy(self):
        p = VirtualPLC(prog("c : ARRAY[1..2] OF Cell; x : Axis;",
                            "c[1].ax.pos[1] := 11; x := c[1].ax; c[2].ax := x; c[2].grid[0,1] := 1.5;"))
        p.scan()
        self.assertEqual(p.get("c[2].ax.pos[1]"), 11)
        self.assertEqual(p.get("x.pos[1]"), 11)
        self.assertEqual(p.get("c[2].grid[0,1]"), 1.5)

    def test_whole_array_field_assign(self):
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; b : ARRAY[1..3] OF INT := [4, 5, 6];",
                            "a[2].pos := b; b := a[1].pos; a[1].pos := a[2].pos;"))
        p.scan()
        self.assertEqual([p.get(f"b[{i}]") for i in (1, 2, 3)], [1, 2, 3])
        self.assertEqual([p.get(f"a[1].pos[{i}]") for i in (1, 2, 3)], [4, 5, 6])

    def test_whole_array_shape_mismatch(self):
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; b : ARRAY[1..4] OF INT;", "a[1].pos := b;"))
        with self.assertRaisesRegex(STError, "same shape"):
            p.scan()

    def test_errors(self):
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; v : INT; i : INT := 4;", "v := a[1].pos[i];"))
        with self.assertRaisesRegex(STError, "out of range"):
            p.scan()
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; v : INT; i : INT := 3;", "v := a[i].pos[1];"))
        with self.assertRaisesRegex(STError, "out of range"):
            p.scan()
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; v : INT;", "v := a[1].pos;"))
        with self.assertRaisesRegex(STError, "without index"):
            p.scan()
        with self.assertRaisesRegex(STError, "too many"):
            VirtualPLC(prog("a : ARRAY[1..2] OF Axis := [(pos := [1, 2, 3, 4])];", ""))

    def test_external_set_get_snapshot(self):
        p = VirtualPLC(prog("a : ARRAY[1..2] OF Axis; m : ARRAY[0..1, 1..2] OF Cell;", ""))
        p.set_input("a[2].pos[3]", 77)
        p.set_input("m[1,2].grid[0,1]", 3.0)
        self.assertEqual(p.get("a[2].pos[3]"), 77)
        snap = p.snapshot()
        self.assertEqual(snap["a[2].pos[3]"], 77)
        self.assertEqual(snap["m[1,2].grid[0,1]"], 3.0)
        self.assertIn("m[0,1].ax.pos[2]", snap)
        self.assertIn("a[1].on", snap)
        with self.assertRaises(STError):
            p.set_input("a[3].pos[1]", 1)

    def test_retain_warm_restart(self):
        src = T + ("PROGRAM Main\nVAR RETAIN\n r : ARRAY[1..2] OF Axis;\nEND_VAR\nVAR\n t : ARRAY[1..2] OF Axis;\n"
                   "END_VAR\nr[2].pos[1] := 50; t[2].pos[1] := 50;\nEND_PROGRAM\n")
        p = VirtualPLC(src)
        p.scan()
        p.restart(warm=True)
        self.assertEqual(p.get("r[2].pos[1]"), 50)
        self.assertEqual(p.get("t[2].pos[1]"), 1)
        p.restart(warm=False)
        self.assertEqual(p.get("r[2].pos[1]"), 1)

    def test_inside_function_block_and_temp(self):
        src = T + """FUNCTION_BLOCK Hold
VAR_OUTPUT y : INT; END_VAR
VAR a : ARRAY[1..2] OF Axis; END_VAR
VAR_TEMP t : ARRAY[1..2] OF Axis; END_VAR
a[1].pos[1] := a[1].pos[1] + 1; t[1].pos[1] := t[1].pos[1] + 1;
y := a[1].pos[1] * 10 + t[1].pos[1];
END_FUNCTION_BLOCK
PROGRAM Main
VAR h : Hold; o : INT; END_VAR
h(y => o);
END_PROGRAM
"""
        p = VirtualPLC(src)
        p.scan(3)
        self.assertEqual(p.get("o"), 42)  # a 累加到 4,VAR_TEMP 每次重新初始化為 1+1

    def test_example_recipe_slots(self):
        p = VirtualPLC(EX)
        p.set_input("slot", 2)
        p.set_input("bump", True)
        p.scan()
        self.assertEqual([p.get(f"active[{i}]") for i in (1, 2, 3)], [10, 20, 30])
        self.assertEqual(p.get("sum"), 63)
        self.assertEqual(p.get("slots[2].setp[1]"), 11)  # VAR_IN_OUT 寫回元素的陣列欄位
        self.assertEqual(p.get("work.name"), "B")
        p.set_input("save", True)
        p.scan()
        self.assertEqual([p.get(f"slots[3].setp[{i}]") for i in (1, 2, 3)], [24, 44, 64])
        self.assertEqual(p.get("slots[3].name"), "copy")
        self.assertEqual(p.get("slots[1].setp[3]"), 300)

    def test_example_scenario(self):
        spec = {"steps": [
            {"set": {"slot": 2, "bump": True}, "cycles": 1, "expect": {"sum": 63, "slots[2].setp[1]": 11}},
            {"set": {"save": True}, "cycles": 1, "expect": {"slots[3].setp[2]": 44, "active[1]": 11}},
        ]}
        res = run_scenario_detail(EX, spec)
        self.assertTrue(all(st["passed"] for st in res), res)


class Checker(unittest.TestCase):
    def test_valid_program_no_errors(self):
        self.assertEqual(errors(EX), [])
        self.assertEqual(errors(prog("m : ARRAY[0..1, 1..2] OF Cell; a : ARRAY[1..2] OF Axis; b : ARRAY[1..3] OF INT;",
                                     "m[1,2].grid[1,0] := 2.5; m[0,1].ax.pos[3] := 9; a[1].pos := b; b := a[2].pos;")), [])

    def test_static_errors(self):
        e = errors(prog("a : ARRAY[1..2] OF Axis; x : INT;",
                        "a[1].pos[4] := 1;\nx := a[1].pos;\na[1].pos[1] := TRUE;\na[1].pos[1, 2] := 1;"))
        self.assertTrue(any("out of range" in m for m in e), e)
        self.assertTrue(any("without index" in m for m in e), e)
        self.assertTrue(any("BOOL assigned to INT" in m for m in e), e)
        self.assertTrue(any("needs 1 index" in m for m in e), e)


class Export(unittest.TestCase):
    def test_plcopen_and_scl_still_export(self):
        x = export(EX, "plcopen")
        self.assertIn('<derived name="Recipe"/>', x)
        self.assertIn('name="setp"', x)
        s = export(EX, "scl")
        self.assertIn('ARRAY[1..3] OF "Recipe"', s)


if __name__ == "__main__":
    unittest.main()
