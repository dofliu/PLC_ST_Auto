"""UI6:情境逐步結果(/api/test steps)、匯出狀態(/api/export/status)。"""
import json
import unittest

from plc_st.interpreter import STError
from plc_st.scenario import run_scenario, run_scenario_detail
from plc_st.web import State, handle

MOTOR = open("examples/motor.st", encoding="utf-8").read()
SCN = {"scan_ms": 100, "steps": [
    {"name": "start", "set": {"start": True}, "ms": 600, "expect": {"motor": True, "t.Q": True}},
    {"name": "stop", "set": {"start": False, "stop": True}, "cycles": 1, "expect": {"motor": False}},
]}


class ScenarioDetailTests(unittest.TestCase):
    def test_steps_have_actuals_and_time(self):
        st = run_scenario_detail(MOTOR, SCN)
        self.assertEqual([s["step"] for s in st], ["start", "stop"])
        self.assertEqual([s["cycles"] for s in st], [6, 1])
        self.assertEqual([s["t_ms"] for s in st], [600, 700])
        self.assertEqual(st[0]["checks"][0], {"var": "motor", "expected": True, "actual": True, "pass": True})
        self.assertTrue(all(s["passed"] for s in st))

    def test_failures_match_legacy_api(self):
        bad = {"steps": [{"name": "a", "set": {"start": True}, "expect": {"motor": False, "cnt": 0}}]}
        st = run_scenario_detail(MOTOR, bad)
        self.assertFalse(st[0]["passed"])
        self.assertEqual([c["pass"] for c in st[0]["checks"]], [False, True])
        self.assertEqual(run_scenario(MOTOR, bad), [{"step": "a", "var": "motor", "expected": False, "actual": True}])

    def test_error_carries_step_index(self):
        spec = {"steps": [{"cycles": 1}, {"name": "x", "expect": {"nope": 1}}]}
        with self.assertRaises(STError) as cm:
            run_scenario_detail(MOTOR, spec)
        self.assertEqual(cm.exception.step_index, 1)
        self.assertIn("unknown variable nope", str(cm.exception))

    def test_invalid_wait_rejected(self):
        for st in ({"ms": -1}, {"ms": "5"}, {"cycles": True}, {"cycles": 1.5}):
            with self.assertRaises(STError) as cm:
                run_scenario_detail(MOTOR, {"steps": [st]})
            self.assertEqual(cm.exception.step_index, 0)
        with self.assertRaises(STError):
            run_scenario_detail(MOTOR, {"steps": ["oops"]})


class WebTests(unittest.TestCase):
    def setUp(self):
        self.s = State()

    def post(self, path, **p):
        return handle("POST", path, p, self.s)

    def test_api_test_returns_steps(self):
        c, b = self.post("/api/test", code=MOTOR, scenario=json.dumps(SCN))
        self.assertEqual((c, b["passed"], b["failures"]), (200, True, []))
        self.assertEqual(len(b["steps"]), 2)
        self.assertEqual(b["steps"][1]["checks"][0]["actual"], False)

    def test_api_test_error_has_step(self):
        spec = json.dumps({"steps": [{"cycles": 1}, {"expect": {"zz": True}}]})
        c, b = self.post("/api/test", code=MOTOR, scenario=spec)
        self.assertEqual((c, b["step"]), (400, 1))
        c, b = self.post("/api/test", code=MOTOR, scenario="{")
        self.assertEqual((c, b["step"]), (400, None))

    def test_export_status_motor(self):
        c, b = self.post("/api/export/status", code=MOTOR)
        self.assertEqual(c, 200)
        f = {x["format"]: x for x in b["formats"]}
        self.assertEqual(list(f), ["plcopen", "scl", "l5x", "gxworks", "sysmac", "st"])
        self.assertTrue(all(x["ok"] and x["size"] > 0 for x in f.values()))
        self.assertTrue(any("TONR" in w["msg"] for w in f["l5x"]["warnings"]))
        self.assertEqual(f["l5x"]["warnings"][0]["line"], 4)
        self.assertEqual(f["st"]["warnings"], [])

    def test_export_status_unsupported_reason(self):
        src = open("examples/struct_l5x.st", encoding="utf-8").read()
        f = {x["format"]: x for x in self.post("/api/export/status", code=src)[1]["formats"]}
        self.assertTrue(f["l5x"]["ok"])
        self.assertFalse(f["gxworks"]["ok"])
        self.assertIn("STRUCT", f["gxworks"]["error"])

    def test_export_status_syntax_error(self):
        f = self.post("/api/export/status", code="PROGRAM X\nIF THEN\nEND_PROGRAM")[1]["formats"]
        self.assertTrue(all(not x["ok"] and x["error"].startswith("語法錯誤") for x in f))
        self.assertEqual(self.post("/api/export/status")[0], 400)


if __name__ == "__main__":
    unittest.main()
