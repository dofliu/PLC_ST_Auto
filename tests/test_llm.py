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
