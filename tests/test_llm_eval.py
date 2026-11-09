"""plc_st.llm_eval 評測工具本身的測試(不呼叫真實 LLM)。"""
import json
import os
import tempfile
import unittest
from unittest import mock

from plc_st import llm_eval
from plc_st.cli import main
from plc_st.llm import get_provider
from plc_st.llm_eval import CASES, main_eval, report_md, run_case, run_eval

GOLD = os.path.join(os.path.dirname(__file__), "llm_eval_golden")


def golden(cid):
    with open(os.path.join(GOLD, f"{cid}.st"), encoding="utf-8") as f:
        return f.read()


class Fixed:
    """每次都回傳同一段程式的假 provider。"""
    name = "claude"

    def __init__(self, code, model="fake"):
        self.code, self.model, self.calls = code, model, 0

    def complete(self, system, user):
        self.calls += 1
        return f"```st\n{self.code}\n```"


class Sequence(Fixed):
    """依序回傳多段程式(測自動修正)。"""

    def __init__(self, codes):
        super().__init__(codes[0])
        self.codes = list(codes)

    def complete(self, system, user):
        self.calls += 1
        return f"```st\n{self.codes.pop(0) if len(self.codes) > 1 else self.codes[0]}\n```"


class Golden(Fixed):
    """依目前執行的案例回傳參考解。"""

    def __init__(self):
        super().__init__("", "golden")
        self.current = None

    def complete(self, system, user):
        self.calls += 1
        return f"```st\n{golden(self.current)}\n```"


def by_id(cid):
    return next(c for c in CASES if c.id == cid)


class CasesAreSatisfiable(unittest.TestCase):
    def test_all_14_cases_pass_with_reference_solutions(self):
        self.assertEqual([c.id for c in CASES], [f"TC-{i:02d}" for i in range(1, 15)])
        for c in CASES:
            with self.subTest(case=c.id):
                p = Golden()
                p.current = c.id
                with mock.patch.object(llm_eval.web, "get_provider", side_effect=AssertionError):
                    r = run_case(c, p)
                bad = [k for k, v in (r.get("checks") or {}).items() if not v]
                self.assertEqual(r["status"], "PASS", (bad, r.get("error"), r.get("final_errors")))
                self.assertTrue(r["first_try"])


class CasesCatchBadPrograms(unittest.TestCase):
    def check_fails(self, cid, code, failing_check):
        r = run_case(by_id(cid), Fixed(code), max_rounds=0)
        self.assertEqual(r["status"], "FAIL")
        self.assertIn(failing_check, [k for k, v in r["checks"].items() if not v])

    def test_tc02_overlap_detected_every_scan(self):
        # 星形永遠不斷開:只在兩個時間點檢查的舊版抓得到,但這裡確認每個週期都檢查
        bad = golden("TC-02").replace("km_star := running AND NOT tmr_star.Q AND NOT km_delta;", "km_star := running;") \
                             .replace("km_delta := running AND tmr_dead.Q AND NOT km_star;", "km_delta := running AND tmr_dead.Q;")
        self.check_fails("TC-02", bad, "interlock_every_scan")

    def test_tc04_wrong_timing(self):
        self.check_fails("TC-04", golden("TC-04").replace("T#2s", "T#4s").replace("T#2000ms", "T#4000ms"), "yellow_about_2s")

    def test_tc06_wrong_divisor(self):
        self.check_fails("TC-06", golden("TC-06").replace("sum / 5.0", "sum / 4.0"), "steady_10")

    def test_tc09_xsd_failure_is_not_ignored(self):
        with mock.patch.object(llm_eval, "validate_plcopen", return_value=["line 1: bad"]):
            r = run_case(by_id("TC-09"), Fixed(golden("TC-09")))
        self.assertEqual(r["status"], "FAIL")
        self.assertFalse(r["checks"]["tc6_xsd_valid"])

    def test_tc10_checker_errors_fail(self):
        r = run_case(by_id("TC-10"), Fixed(golden("TC-10").replace("END_PROGRAM", "ghost := 1;\nEND_PROGRAM")),
                     max_rounds=0)
        self.assertEqual(r["status"], "FAIL")
        self.assertTrue(r["final_errors"])

    def test_tc12_wraps_detected(self):
        bad = "PROGRAM P VAR_INPUT pulse, clear : BOOL; END_VAR VAR_OUTPUT total_count : INT; END_VAR " \
              "VAR e : R_TRIG; END_VAR e(CLK := pulse); IF clear THEN total_count := 0; " \
              "ELSIF e.Q THEN total_count := total_count + 1; END_IF; END_PROGRAM"
        r = run_case(by_id("TC-12"), Fixed(bad), max_rounds=0)
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("overflow", r.get("error", ""))

    def test_missing_io_is_fail_not_crash(self):
        r = run_case(by_id("TC-01"), Fixed("PROGRAM P VAR x : INT; END_VAR x := 1; END_PROGRAM"))
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("STError", r["error"])


class RepairLoopIsRecorded(unittest.TestCase):
    def test_round_errors_logged(self):
        broken = golden("TC-01").replace("END_PROGRAM", "ghost := TRUE;\nEND_PROGRAM")
        p = Sequence([broken, golden("TC-01")])
        r = run_case(by_id("TC-01"), p, max_rounds=2)
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(r["rounds"], 1)
        self.assertFalse(r["first_try"])
        self.assertIn("ghost", r["rounds_log"][0]["errors"][0])
        self.assertEqual(r["rounds_log"][1]["errors"], [])
        self.assertEqual(p.calls, 2)


class UsageAndReport(unittest.TestCase):
    def claude_with_fake_api(self, model):
        def transport(url, headers, payload):
            self.assertEqual(payload["model"], model)
            return {"content": [{"type": "text", "text": f"```st\n{golden('TC-01')}\n```"}],
                    "usage": {"input_tokens": 100, "output_tokens": 40}}
        return get_provider("claude", model=model, transport=transport)

    def test_tokens_counted_and_report(self):
        res = [run_eval(self.claude_with_fake_api(m), repeat=2, case_ids=["TC-01"], log=lambda s: None)
               for m in ("claude-haiku-5-5", "claude-sonnet-5-5")]
        s = llm_eval.summarize(res[0])
        self.assertEqual((s["runs"], s["pass"], s["api_calls"], s["input_tokens"], s["output_tokens"]),
                         (2, 2, 2, 200, 80))
        md = report_md(res, {"claude-haiku-5-5": (1.0, 5.0)})
        self.assertIn("`claude-haiku-5-5` | 2/2 | 100%", md)
        self.assertIn("$0.0006", md)  # (200*1 + 80*5)/1e6
        self.assertIn("| TC-01 馬達啟停自保持與停止優先 | ✅ 2/2 | ✅ 2/2 |", md)

    def test_main_eval_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            results, path = main_eval("claude", ["m1"], 1, ["TC-01", "TC-13"], 2, d, log=lambda s: None,
                                      provider_factory=lambda m: Fixed(golden("TC-01"), m))
            self.assertTrue(os.path.exists(path))
            out = os.path.dirname(path)
            with open(os.path.join(out, "results_m1.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual([r["id"] for r in data["runs"]], ["TC-01", "TC-13"])
            self.assertTrue(os.path.exists(os.path.join(out, "m1", "run1", "tc01.st")))

    def test_cli_validates_arguments(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(main(["eval", "--cases", "TC-99"]), 1)
            self.assertEqual(main(["eval", "--repeat", "0"]), 1)
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
                self.assertEqual(main(["eval", "--provider", "claude", "--cases", "TC-01",
                                       "--out", tempfile.mkdtemp()]), 1)  # 無金鑰:明確錯誤


if __name__ == "__main__":
    unittest.main()
