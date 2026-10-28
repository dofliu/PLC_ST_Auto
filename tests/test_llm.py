import unittest

from plc_st.llm import (Claude, Gemini, Ollama, OpenAI, build_prompt, extract_st,
                        generate, get_provider)
from plc_st import STError

ST = "PROGRAM P\nVAR x : BOOL; END_VAR\nx := TRUE;\nEND_PROGRAM"


def fake(resp):
    calls = []

    def t(url, headers, payload):
        calls.append((url, headers, payload))
        return resp
    t.calls = calls
    return t


class TestLLM(unittest.TestCase):
    def test_extract(self):
        self.assertIn("END_PROGRAM", extract_st(f"hi\n```st\n{ST}\n```\nbye"))
        self.assertIn("END_PROGRAM", extract_st(f"text {ST} text"))
        with self.assertRaises(STError):
            extract_st("nothing")

    def test_providers_request_and_parse(self):
        cases = [
            (OpenAI, {"choices": [{"message": {"content": "A"}}]}, "chat/completions"),
            (Claude, {"content": [{"type": "text", "text": "A"}]}, "/v1/messages"),
            (Gemini, {"candidates": [{"content": {"parts": [{"text": "A"}]}}]}, ":generateContent"),
            (Ollama, {"message": {"content": "A"}}, "/api/chat"),
        ]
        for cls, resp, frag in cases:
            t = fake(resp)
            self.assertEqual(cls(transport=t).complete("s", "u"), "A")
            self.assertIn(frag, t.calls[0][0])

    def test_bad_response(self):
        with self.assertRaises(STError):
            OpenAI(transport=fake({})).complete("s", "u")

    def test_generate_with_context_and_tags(self):
        t = fake({"message": {"content": f"```st\n{ST}\n```"}})
        code = generate(Ollama(transport=t), "turn on x", "VAR_INPUT a : BOOL; END_VAR", "siemens",
                        context=["DOC SNIPPET"])
        self.assertIn("PROGRAM", code)
        user = t.calls[0][2]["messages"][1]["content"]
        self.assertIn("DOC SNIPPET", user)
        self.assertIn("VAR_INPUT", user)
        self.assertIn("siemens", build_prompt("r", vendor="siemens")[0])

    def test_factory_and_missing_key(self):
        self.assertIsInstance(get_provider("gpt", api_key="k"), OpenAI)
        with self.assertRaises(STError):
            get_provider("nope")
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with self.assertRaises(STError):
            get_provider("claude")


if __name__ == "__main__":
    unittest.main()


class TestGenerateCLI(unittest.TestCase):
    def test_cli_generate(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        from plc_st import llm
        from plc_st.cli import main
        resp = {"message": {"content": f"```st\n{ST}\n```"}}
        with mock.patch.object(llm, "http_post_json", lambda *a, **k: resp):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["generate", "turn on x", "--provider", "ollama"])
        self.assertEqual(rc, 0)
        self.assertIn("END_PROGRAM", buf.getvalue())


class TestRepairLoop(unittest.TestCase):
    BAD = "PROGRAM P\nVAR x : BOOL; END_VAR\ny := TRUE;\nEND_PROGRAM"

    class Seq:
        def __init__(self, replies):
            self.replies, self.users = list(replies), []

        def complete(self, system, user):
            self.users.append(user)
            return self.replies.pop(0)

    def test_repairs_then_stops(self):
        from plc_st.llm import generate_checked
        p = self.Seq([f"```st\n{self.BAD}\n```", f"```st\n{ST}\n```"])
        code, issues, rounds = generate_checked(p, "req")
        self.assertEqual(rounds, 1)
        self.assertFalse([i for i in issues if i.severity == "error"])
        self.assertIn("x := TRUE", code)
        self.assertIn("static checker", p.users[1])
        self.assertIn("y", p.users[1])

    def test_gives_up_after_max_rounds(self):
        from plc_st.llm import generate_checked
        p = self.Seq([f"```st\n{self.BAD}\n```"] * 3)
        _, issues, rounds = generate_checked(p, "req", max_rounds=2)
        self.assertEqual(rounds, 2)
        self.assertTrue(any(i.severity == "error" for i in issues))
        self.assertEqual(len(p.users), 3)

    def test_no_repair_when_clean_or_disabled(self):
        from plc_st.llm import generate_checked
        p = self.Seq([f"```st\n{ST}\n```"])
        self.assertEqual(generate_checked(p, "req")[2], 0)
        p = self.Seq([f"```st\n{self.BAD}\n```"])
        self.assertEqual(generate_checked(p, "req", max_rounds=0)[2], 0)


class TestScenarioLoop(unittest.TestCase):
    SPEC = '{"steps": [{"set": {"go": true}, "expect": {"m": true}}]}'
    WRONG = "PROGRAM P\nVAR_INPUT go : BOOL; END_VAR\nVAR_OUTPUT m : BOOL; END_VAR\nm := NOT go;\nEND_PROGRAM"
    RIGHT = "PROGRAM P\nVAR_INPUT go : BOOL; END_VAR\nVAR_OUTPUT m : BOOL; END_VAR\nm := go;\nEND_PROGRAM"
    Seq = TestRepairLoop.Seq

    def test_scenario_failure_triggers_repair(self):
        from plc_st.llm import generate_checked
        p = self.Seq([f"```st\n{self.WRONG}\n```", f"```st\n{self.RIGHT}\n```"])
        code, issues, rounds = generate_checked(p, "req", scenario=self.SPEC)
        self.assertEqual(rounds, 1)
        self.assertFalse([i for i in issues if i.severity == "error"])
        self.assertIn("m := go", code)
        self.assertIn("expected True but program produced False", p.users[1])

    def test_scenario_failure_remains_after_max_rounds(self):
        from plc_st.llm import generate_checked
        p = self.Seq([f"```st\n{self.WRONG}\n```"] * 2)
        _, issues, rounds = generate_checked(p, "req", max_rounds=1, scenario=self.SPEC)
        self.assertEqual(rounds, 1)
        self.assertTrue(any("scenario" in i.msg for i in issues))

    def test_bad_scenario_reported_not_raised(self):
        from plc_st.llm import generate_checked
        p = self.Seq([f"```st\n{self.RIGHT}\n```"])
        _, issues, _ = generate_checked(p, "req", max_rounds=0, scenario='{"steps": [{"expect": {"zz": 1}}]}')
        self.assertTrue(any("could not run" in i.msg for i in issues))

    def test_cli_scenario_flag(self):
        import io, os, tempfile
        from contextlib import redirect_stdout
        from unittest import mock
        from plc_st import llm
        from plc_st.cli import main
        with tempfile.TemporaryDirectory() as d:
            sp = os.path.join(d, "s.json")
            open(sp, "w").write(self.SPEC)
            resp = {"message": {"content": f"```st\n{self.WRONG}\n```"}}
            with mock.patch.object(llm, "http_post_json", lambda *a, **k: resp):
                with redirect_stdout(io.StringIO()):
                    rc = main(["generate", "r", "--max-rounds", "0", "--scenario", sp])
        self.assertEqual(rc, 1)
