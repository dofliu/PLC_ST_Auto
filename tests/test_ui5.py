"""UI5:mock provider、/api/generate 時間軸、/api/tags/preview。"""
import json
import unittest

from plc_st.llm import Mock, generate_checked, get_provider
from plc_st.tags import preview_tags, tags_to_var_blocks
from plc_st.web import State, handle

POINTS = open("examples/points.csv", encoding="utf-8").read()


class MockProviderTests(unittest.TestCase):
    def test_no_key_needed_and_repairs_in_one_round(self):
        log = []
        code, issues, rounds = generate_checked(get_provider("mock"), "馬達", on_round=lambda n, c, i: log.append((n, i)))
        self.assertEqual(rounds, 1)
        self.assertEqual(issues, [])
        self.assertIn("undeclared variable alarm_lamp", str(log[0][1][0]))
        self.assertIn("alarm_lamp : BOOL", code)

    def test_uses_tag_table(self):
        code, issues, _ = generate_checked(Mock(), "x", tags_to_var_blocks(POINTS))
        self.assertIn("cnt : INT;", code)
        self.assertIn("motor := (start OR motor) AND NOT stop;", code)
        self.assertEqual(issues, [])

    def test_max_rounds_zero_keeps_error(self):
        _, issues, rounds = generate_checked(Mock(), "x", max_rounds=0)
        self.assertEqual(rounds, 0)
        self.assertTrue(any(i.severity == "error" for i in issues))

    def test_single_input_and_no_bool_output(self):
        tags = tags_to_var_blocks("name,type,direction\nsw,BOOL,IN\nlevel,INT,OUT\n")
        code, issues, _ = generate_checked(Mock(), "x", tags)
        self.assertIn("motor := sw;", code)
        self.assertEqual(issues, [])


class GenerateTimelineTests(unittest.TestCase):
    def post(self, path, **p):
        return handle("POST", path, p, State())

    def test_timeline_rounds(self):
        c, b = self.post("/api/generate", requirement="r", provider="mock", tags_csv=POINTS)
        self.assertEqual(c, 200)
        tl = b["timeline"]
        self.assertEqual([t["round"] for t in tl], [0, 1])
        self.assertEqual([t["errors"] for t in tl], [1, 0])
        self.assertEqual(tl[-1]["code"], b["code"])
        self.assertEqual(tl[0]["issues"][0]["severity"], "error")
        self.assertTrue(all(isinstance(t["ms"], int) and t["ms"] >= 0 for t in tl))
        self.assertEqual((b["provider"], b["model"], b["rounds"]), ("mock", "demo", 1))

    def test_timeline_with_scenario(self):
        scn = {"steps": [{"set": {"start": True}, "cycles": 1, "expect": {"motor": True, "alarm_lamp": False}}]}
        c, b = self.post("/api/generate", requirement="r", provider="mock", scenario=json.dumps(scn))
        self.assertEqual(c, 200)
        self.assertEqual(b["timeline"][-1]["errors"], 0)

    def test_unknown_provider_400(self):
        c, b = self.post("/api/generate", requirement="r", provider="nope")
        self.assertEqual(c, 400)
        self.assertIn("mock", b["error"])


class TagPreviewTests(unittest.TestCase):
    def test_good_table(self):
        j = preview_tags(POINTS)
        self.assertEqual(j["errors"], 0)
        self.assertEqual([r["section"] for r in j["rows"]], ["VAR_INPUT", "VAR_INPUT", "VAR_OUTPUT", "VAR"])
        self.assertEqual(j["rows"][3]["init"], "0")
        self.assertEqual(j["rows"][0]["line"], 2)

    def test_row_errors_do_not_stop_preview(self):
        j = preview_tags("name,type,direction\na,bool,in\nA,INT,OUT\n1x,INT,VAR\nq,,IN\nz,BOOL,SIDE\n\nok,REAL,\n")
        errs = [r["error"] for r in j["rows"]]
        self.assertIsNone(errs[0])
        self.assertIn("重複", errs[1])
        self.assertIn("識別字", errs[2])
        self.assertIn("type", errs[3])
        self.assertIn("direction", errs[4])
        self.assertEqual(j["rows"][5]["section"], "VAR")  # 空 direction 預設 VAR
        self.assertEqual(j["rows"][0]["type"], "BOOL")
        self.assertEqual(j["errors"], 4)

    def test_api_and_empty(self):
        c, b = handle("POST", "/api/tags/preview", {"csv": ""}, State())
        self.assertEqual((c, b["rows"], b["errors"]), (200, [], 0))
        c, b = handle("POST", "/api/tags/preview", {"csv": POINTS}, State())
        self.assertEqual(len(b["rows"]), 4)

    def test_preview_agrees_with_parser_on_valid_rows(self):
        from plc_st.tags import parse_tags
        self.assertEqual([r["name"] for r in parse_tags(POINTS)], [r["name"] for r in preview_tags(POINTS)["rows"]])


if __name__ == "__main__":
    unittest.main()
