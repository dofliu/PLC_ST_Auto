"""UI4:互動模擬 API(/api/sim/*)、變數 meta、執行期錯誤行號。"""
import unittest

from plc_st.interpreter import VirtualPLC, STError
from plc_st.web import MAX_SIMS, State, handle

MOTOR = open("examples/motor.st", encoding="utf-8").read()


class SimApiTests(unittest.TestCase):
    def setUp(self):
        self.s = State()

    def post(self, path, **p):
        return handle("POST", path, p, self.s)

    def start(self, code=MOTOR, **kw):
        c, b = self.post("/api/sim/start", code=code, **kw)
        self.assertEqual(c, 200, b)
        return b

    def test_start_returns_meta_and_initial_row(self):
        b = self.start()
        self.assertEqual(b["columns"][:2], ["cycle", "time_ms"])
        self.assertEqual(b["row"], [0, 0, False, False, False, 0])
        sec = {m["name"]: (m["section"], m["type"]) for m in b["meta"]}
        self.assertEqual(sec, {"start": ("input", "BOOL"), "stop": ("input", "BOOL"),
                               "motor": ("output", "BOOL"), "cnt": ("local", "INT")})

    def test_step_applies_inputs_and_keeps_state(self):
        sid = self.start()["id"]
        c, r = self.post("/api/sim/step", id=sid, set={"start": True})
        self.assertEqual(c, 200)
        self.assertEqual(r["rows"], [[1, 10, True, False, True, 0]])
        c, r = self.post("/api/sim/step", id=sid, cycles=60, set={"start": False})
        self.assertEqual(len(r["rows"]), 60)
        last = r["rows"][-1]
        self.assertEqual(last[:2], [61, 610])
        self.assertTrue(last[4])        # motor 自保持
        self.assertGreater(last[5], 0)  # TON 500ms 後 cnt 增加

    def test_outputs_cannot_be_forced(self):
        sid = self.start()["id"]
        c, b = self.post("/api/sim/step", id=sid, set={"motor": True})
        self.assertEqual(c, 400)
        self.assertIn("output", b["error"])

    def test_bad_requests(self):
        sid = self.start()["id"]
        self.assertEqual(self.post("/api/sim/step", id="nope")[0], 400)
        self.assertEqual(self.post("/api/sim/step", id=sid, cycles=0)[0], 400)
        self.assertEqual(self.post("/api/sim/step", id=sid, cycles="x")[0], 400)
        self.assertEqual(self.post("/api/sim/step", id=sid, set=[1])[0], 400)
        self.assertEqual(self.post("/api/sim/step", id=sid, set={"zz": 1})[0], 400)
        self.assertEqual(self.post("/api/sim/start", code="PROGRAM")[0], 400)

    def test_stop_and_session_limit(self):
        sid = self.start()["id"]
        self.assertEqual(self.post("/api/sim/stop", id=sid), (200, {"stopped": True}))
        self.assertEqual(self.post("/api/sim/step", id=sid)[0], 400)
        ids = [self.start()["id"] for _ in range(MAX_SIMS + 3)]
        self.assertEqual(len(self.s.sims), MAX_SIMS)
        self.assertEqual(self.post("/api/sim/step", id=ids[0])[0], 400)   # 最舊的被淘汰
        self.assertEqual(self.post("/api/sim/step", id=ids[-1])[0], 200)

    def test_profile_and_scan(self):
        code = "PROGRAM P\nVAR x : INT := 32767; END_VAR\nx := x + 1;\nEND_PROGRAM"
        sid = self.start(code, profile="strict", scan_ms=100)["id"]
        c, b = self.post("/api/sim/step", id=sid)
        self.assertEqual(c, 400)
        self.assertIn("overflow", b["error"])
        sid = self.start(code, profile="saturate", scan_ms=100)["id"]
        self.assertEqual(self.post("/api/sim/step", id=sid)[1]["rows"], [[1, 100, 32767]])

    def test_run_meta_for_arrays_and_structs(self):
        code = ("TYPE Pt : STRUCT x : INT; ok : BOOL; END_STRUCT END_TYPE\nPROGRAM M\n"
                "VAR_INPUT a : ARRAY[1..2] OF BOOL; END_VAR\nVAR_OUTPUT p : Pt; msg : STRING; END_VAR\n"
                "p.ok := a[1];\nEND_PROGRAM")
        c, b = self.post("/api/run", code=code, cycles=1)
        self.assertEqual(c, 200, b)
        meta = {m["name"]: (m["section"], m["type"]) for m in b["meta"]}
        self.assertEqual(meta["a[1]"], ("input", "BOOL"))
        self.assertEqual(meta["p.ok"], ("output", "BOOL"))
        self.assertEqual(meta["p.x"], ("output", "INT"))
        self.assertEqual(meta["msg"], ("output", "STRING"))


class RuntimeLineTests(unittest.TestCase):
    def test_runtime_error_has_line(self):
        plc = VirtualPLC("PROGRAM E\nVAR a : ARRAY[1..3] OF INT; i : INT; END_VAR\ni := i + 1;\na[i] := i;\nEND_PROGRAM")
        plc.scan(3)
        with self.assertRaisesRegex(STError, r"^line 4: array index 4 out of range"):
            plc.scan(1)

    def test_innermost_line_kept_in_function(self):
        src = ("FUNCTION F : INT\nVAR_INPUT k : INT; END_VAR\nVAR b : ARRAY[0..1] OF INT; END_VAR\n"
               "b[k] := 1;\nF := 0;\nEND_FUNCTION\nPROGRAM P\nVAR r : INT; END_VAR\nr := F(k := 5);\nEND_PROGRAM")
        with self.assertRaisesRegex(STError, r"^line 4: "):
            VirtualPLC(src).scan(1)

    def test_fb_call_error_has_line(self):
        src = "PROGRAM P\nVAR t : TON; a : ARRAY[1..2] OF TIME; END_VAR\n\nt(IN := TRUE, PT := a[5]);\nEND_PROGRAM"
        with self.assertRaisesRegex(STError, r"^line 4: "):
            VirtualPLC(src).scan(1)


if __name__ == "__main__":
    unittest.main()
