"""M43b:PR #60 審查意見修正(陣列界限常數求值、EXTERNAL CONSTANT 綁可寫全域、PLCopen 本地常數引用全域常數、
FB 內整份複製全域 STRUCT、帶 %I/%Q 位址全域變數的初始化順序)。"""
import unittest

from plc_st.checker import check
from plc_st.export import export, validate_plcopen
from plc_st.interpreter import VirtualPLC
from plc_st.lexer import STError
from plc_st.parser import parse


def errs(src):
    return [str(i) for i in check(src) if i.severity == "error"]


def warns(src):
    return [str(i) for i in check(src) if i.severity == "warning"]


class ArrayBounds(unittest.TestCase):
    """審查 1:界限先求常數值再比對。"""

    def src(self, gdim, edim, extra=""):
        return f"""VAR_GLOBAL CONSTANT N : INT := 3; M : INT := 5; END_VAR
VAR_GLOBAL a : ARRAY[0..{gdim}] OF INT; END_VAR
FUNCTION_BLOCK F {extra}VAR_EXTERNAL a : ARRAY[0..{edim}] OF INT; END_VAR a[1] := 1; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""

    def test_constant_equals_literal_accepted(self):
        self.assertEqual(errs(self.src("N", "3")), [])
        self.assertEqual(errs(self.src("3", "N")), [])
        self.assertEqual(errs(self.src("N + 1", "4")), [])
        VirtualPLC(self.src("N", "3")).scan()

    def test_local_constant_bound(self):
        src = self.src("N", "K", "VAR CONSTANT K : INT := 3; END_VAR ")
        self.assertEqual(errs(src), [])

    def test_different_constants_rejected(self):
        e = errs(self.src("N", "M"))
        self.assertTrue(any("VAR_EXTERNAL a type does not match VAR_GLOBAL (ARRAY[0..3] OF INT)" in x for x in e), e)
        e = errs(self.src("N", "4"))
        self.assertTrue(any("VAR_EXTERNAL a type does not match" in x for x in e), e)

    def test_array_vs_scalar_rejected(self):
        src = """VAR_GLOBAL a : ARRAY[0..2] OF INT; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL a : INT; END_VAR END_FUNCTION_BLOCK PROGRAM P END_PROGRAM"""
        self.assertTrue(any("type does not match" in x for x in errs(src)))

    def test_unresolvable_bound_warns(self):
        src = """VAR_GLOBAL n : INT := 3; a : ARRAY[0..2] OF INT; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL a : ARRAY[0..n] OF INT; END_VAR END_FUNCTION_BLOCK PROGRAM P END_PROGRAM"""
        self.assertTrue(any("cannot verify" in w for w in warns(src)), warns(src))


class ExternalConstant(unittest.TestCase):
    """審查 2:VAR_EXTERNAL CONSTANT 不可綁到可寫的全域變數。"""
    SRC = """VAR_GLOBAL g : INT; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL CONSTANT g : INT; END_VAR g := 99; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""

    def test_checker_rejects_binding_and_write(self):
        e = errs(self.SRC)
        self.assertTrue(any("VAR_EXTERNAL CONSTANT g refers to a writable VAR_GLOBAL" in x for x in e), e)
        self.assertTrue(any("write to CONSTANT g" in x for x in e), e)

    def test_simulator_rejects_binding(self):
        with self.assertRaisesRegex(STError, "refers to a writable VAR_GLOBAL"):
            VirtualPLC(self.SRC)

    def test_constant_global_still_fine(self):
        src = self.SRC.replace("VAR_GLOBAL g", "VAR_GLOBAL CONSTANT g").replace("g : INT; END_VAR\nFUNCTION", "g : INT := 1; END_VAR\nFUNCTION").replace("g := 99; ", "")
        self.assertEqual(errs(src), [])
        VirtualPLC(src).scan()


class PlcopenConstants(unittest.TestCase):
    """審查 3:本地常數引用全域常數時,匯出與模擬採用相同界限。"""
    SRC = """VAR_GLOBAL CONSTANT G : INT := 3; END_VAR
FUNCTION_BLOCK F
VAR CONSTANT N : INT := G + 1; END_VAR
VAR buf : ARRAY[0..N] OF INT; END_VAR
VAR_OUTPUT last : INT; END_VAR
buf[N] := 9; last := buf[4];
END_FUNCTION_BLOCK
PROGRAM P VAR f : F; v : INT; END_VAR f(); v := f.last; END_PROGRAM"""

    def test_simulation_and_export_agree(self):
        self.assertEqual(errs(self.SRC), [])
        plc = VirtualPLC(self.SRC)
        plc.scan()
        self.assertEqual(plc.get("v"), 9)
        x = export(self.SRC, "plcopen")
        self.assertIn('<dimension lower="0" upper="4"/>', x)
        try:
            self.assertEqual(validate_plcopen(x), [])
        except STError:
            self.skipTest("lxml not installed")

    def test_local_constant_overrides_global_name(self):
        src = self.SRC.replace("VAR CONSTANT N : INT := G + 1; END_VAR", "VAR CONSTANT G : INT := 1; N : INT := G + 1; END_VAR") \
                      .replace("last := buf[4]", "last := buf[2]")
        x = export(src, "plcopen")
        self.assertIn('<dimension lower="0" upper="2"/>', x)


class GlobalStructCopy(unittest.TestCase):
    """審查 4:FB 內整份複製全域 STRUCT。"""

    def test_struct_copy_in_fb(self):
        src = """TYPE S : STRUCT x : INT; y : BOOL; END_STRUCT END_TYPE
VAR_GLOBAL g : S := (x := 7, y := TRUE); h : S; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL g : S; h : S; END_VAR VAR l : S; END_VAR
h := g; l := g; l.x := l.x + 1; g := l;
END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""
        self.assertEqual(errs(src), [])
        plc = VirtualPLC(src)
        plc.scan()
        self.assertEqual((plc.get("h.x"), plc.get("h.y"), plc.get("g.x")), (7, True, 8))

    def test_array_of_struct_element_copy_in_fb(self):
        src = """TYPE S : STRUCT x : INT; END_STRUCT END_TYPE
VAR_GLOBAL arr : ARRAY[0..1] OF S := [(x := 4), (x := 5)]; END_VAR
FUNCTION_BLOCK F VAR_EXTERNAL arr : ARRAY[0..1] OF S; END_VAR VAR t : S; END_VAR
t := arr[1]; arr[0] := t;
END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""
        plc = VirtualPLC(src)
        plc.scan()
        self.assertEqual(plc.get("arr[0].x"), 5)

    def test_struct_without_member_message(self):
        src = """TYPE S : STRUCT x : INT; END_STRUCT END_TYPE
VAR_GLOBAL g : S; END_VAR
FUNCTION_BLOCK F VAR v : INT; END_VAR v := g; END_FUNCTION_BLOCK
PROGRAM P VAR f : F; END_VAR f(); END_PROGRAM"""
        with self.assertRaisesRegex(STError, "STRUCT g used without member"):
            VirtualPLC(src).scan()


class LocatedGlobalOrder(unittest.TestCase):
    """審查 5:帶 %I/%Q 位址的全域變數也要在 FB 實例之前初始化。"""
    SRC = """FUNCTION_BLOCK F VAR x : INT := g; END_VAR VAR_OUTPUT o : INT; END_VAR o := x; END_FUNCTION_BLOCK
PROGRAM P
VAR f : F; v : INT; END_VAR
VAR_GLOBAL g AT %IW0 : INT := 5; q AT %QX0.0 : BOOL; END_VAR
f(); v := f.o; q := v > 0;
END_PROGRAM"""

    def test_hoisted_by_glob_flag(self):
        names = [(d["name"], d["section"], d["glob"]) for d in parse(self.SRC)["decls"]]
        self.assertEqual(names[:2], [("g", "input", True), ("q", "output", True)])

    def test_fb_initialises_from_located_global(self):
        self.assertEqual(errs(self.SRC), [])
        plc = VirtualPLC(self.SRC)
        plc.scan()
        self.assertEqual(plc.get("v"), 5)
        self.assertTrue(plc.get("q"))


if __name__ == "__main__":
    unittest.main()
