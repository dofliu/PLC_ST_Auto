"""M42:TYPE STRUCT 匯出至 Mitsubishi GX Works3 與 Omron Sysmac Studio。"""
import json
import os
import threading
import unittest
import urllib.request

from plc_st.export import export, to_gxworks, to_sysmac
from plc_st.lexer import STError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


NESTED = """TYPE Pt : STRUCT x : INT := 1; y : INT; END_STRUCT END_TYPE
TYPE Line : STRUCT a : Pt; b : Pt; tag : STRING := 'a, b := c'; pts : ARRAY[0..1] OF INT; END_STRUCT END_TYPE
PROGRAM P
VAR CONSTANT N : INT := 1; END_VAR
VAR
  l : Line := (a := (x := 5), tag := 'x, y := 1', pts := [7, 8]);
  g : ARRAY[0..N, 1..2] OF Pt := [2((x := 3)), (y := 4)];
  plain : ARRAY[0..2] OF INT := [1, 2, 3];
  r AT %MW10 : INT;
END_VAR
VAR_TEMP t : Pt; END_VAR
t.x := l.a.x; r := g[1, 1].y + plain[0];
END_PROGRAM
"""


def section(lines, title):
    i = next(k for k, s in enumerate(lines) if title in s)
    out = []
    for s in lines[i + 1:]:
        if s.startswith("(* ==="):
            break
        out.append(s)
    return out


class GxWorksStruct(unittest.TestCase):
    def setUp(self):
        self.lines = to_gxworks(NESTED).splitlines()

    def test_struct_definitions(self):
        sec = section(self.lines, "Structured Data Types")
        self.assertEqual(sec[0], "Structure\tLabel Name\tData Type\tInitial Value")
        self.assertIn("Pt\tx\tWord [Signed]\t1", sec)
        self.assertIn("Line\ta\tPt\t", sec)
        self.assertIn("Line\ttag\tString\t'a, b := c'", sec)
        self.assertIn("Line\tpts\tARRAY[0..1] OF INT\t", sec)
        self.assertLess(self.lines.index("Pt\tx\tWord [Signed]\t1"), self.lines.index("Line\ta\tPt\t"))

    def test_struct_label_init_flattened(self):
        self.assertIn("VAR\tl\tLine\t\t", self.lines)
        sec = section(self.lines, "Structured Label Initial Values")
        self.assertEqual(sec[:4], ["l.a.x\t5", "l.tag\t'x, y := 1'", "l.pts[0]\t7", "l.pts[1]\t8"])

    def test_multidim_repeat_and_const_bounds(self):
        self.assertIn("VAR\tg\tARRAY[0..1, 1..2] OF Pt\t\t", self.lines)
        sec = section(self.lines, "Structured Label Initial Values")
        self.assertEqual(sec[4:], ["g[0, 1].x\t3", "g[0, 2].x\t3", "g[1, 1].y\t4"])

    def test_base_array_init_kept_inline(self):
        self.assertIn("VAR\tplain\tARRAY[0..2] OF INT\t[1, 2, 3]\t", self.lines)

    def test_temp_struct_note(self):
        body = self.lines[self.lines.index("(* === ST Program Body === *)") + 1:]
        self.assertTrue(body[0].startswith("// 注意:t 為暫存變數"))
        self.assertIn("VAR\tt\tPt\t\t", self.lines)

    def test_no_struct_section_without_types(self):
        out = to_gxworks(read("examples/motor.st"))
        self.assertNotIn("Structured", out)
        self.assertEqual(out.splitlines()[2], "Class\tLabel Name\tData Type\tInitial Value")


class SysmacStruct(unittest.TestCase):
    def setUp(self):
        self.lines = to_sysmac(NESTED).splitlines()

    def test_struct_definitions(self):
        sec = section(self.lines, "Data Types / Structures")
        self.assertEqual(sec[0], "Structure\tMember\tBase Type\tInitial Value")
        self.assertIn("Pt\tx\tINT\t1", sec)
        self.assertIn("Line\ttag\tSTRING\t'a, b := c'", sec)
        self.assertIn("Line\tpts\tARRAY[0..1] OF INT\t", sec)

    def test_struct_init_inline(self):
        row = next(s for s in self.lines if s.startswith("l\t"))
        self.assertIn("(a := (x := 5), tag := 'x, y := 1'", row)
        self.assertIn("g\tARRAY[0..1, 1..2] OF Pt\t[2((x := 3)), (y := 4)]", "\n".join(self.lines))


class Runs(unittest.TestCase):
    def test_nested_source_runs_in_virtual_plc(self):
        from plc_st.interpreter import VirtualPLC
        p = VirtualPLC(NESTED)
        p.scan(1)
        self.assertEqual((p.get("l.a.x"), p.get("l.pts[1]"), p.get("g[0, 2].x"), p.get("r")), (5, 8, 3, 5))


class Gate(unittest.TestCase):
    def test_examples_export(self):
        for ex in ("struct.st", "struct_array.st", "struct_export.st", "struct_arrfield.st", "struct_elem.st",
                   "struct_copy.st", "struct_l5x.st"):
            for fmt in ("gxworks", "sysmac"):
                self.assertIn("Structure\t", export(read("examples/" + ex), fmt), ex)

    def test_function_block_still_rejected(self):
        for fmt in ("gxworks", "sysmac"):
            with self.assertRaises(STError) as c:
                export(read("examples/userpou_export.st"), fmt)
            self.assertIn("FUNCTION", str(c.exception))

    def test_non_struct_type_rejected(self):
        src = "TYPE Color : (Red, Green); END_TYPE\nPROGRAM P\nVAR a : INT; END_VAR\na := 1;\nEND_PROGRAM"
        with self.assertRaises(STError) as c:
            to_gxworks(src)
        self.assertIn("列舉", str(c.exception))

    def test_bad_init(self):
        types = "TYPE Pt : STRUCT x : INT; END_STRUCT END_TYPE\n"
        for decl, msg in (("p : Pt := (z := 1);", "無法解析"), ("p : Pt := 5;", "須為"),
                          ("p : ARRAY[0..1] OF Pt := [(x:=1), (x:=2), (x:=3)];", "超過陣列大小")):
            with self.assertRaises(STError) as c:
                to_gxworks(types + f"PROGRAM P\nVAR {decl} END_VAR\np.x := 1;\nEND_PROGRAM")
            self.assertIn(msg, str(c.exception))

    def test_struct_in_comment_or_string_not_misread(self):
        src = "PROGRAM P\nVAR s : STRING := 'TYPE X : STRUCT'; END_VAR\n(* TYPE Y : STRUCT a:INT; END_STRUCT END_TYPE *)\ns := s;\nEND_PROGRAM"
        self.assertNotIn("Structure", to_gxworks(src))
        self.assertNotIn("Structure", to_sysmac(src))


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from plc_st.web import make_server
        cls.srv = make_server("127.0.0.1", 0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def post(self, path, **body):
        req = urllib.request.Request(self.url + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def test_export_status_all_ok_for_struct(self):
        f = {x["format"]: x for x in self.post("/api/export/status", code=read("examples/struct_export.st"))["formats"]}
        self.assertTrue(f["gxworks"]["ok"] and f["sysmac"]["ok"])

    def test_export_gxworks_struct(self):
        b = self.post("/api/export", code=read("examples/struct_export.st"), format="gxworks")
        self.assertIn("ms[1].speed\t100", json.dumps(b, ensure_ascii=False).replace("\\t", "\t"))


if __name__ == "__main__":
    unittest.main()
