"""M40:串流產生 /api/generate/stream(NDJSON 事件、逐輪即時送出、用戶端斷線中止)。"""
import http.client
import json
import threading
import time
import unittest

from plc_st.llm import get_provider
from plc_st.web import State, generate_stream, make_server

POINTS = open("examples/points.csv", encoding="utf-8").read()


def events(payload, state=None):
    out = []
    ok = generate_stream(payload, state or State(), out.append)
    return ok, [json.loads(b) for b in out]


class StreamEventTests(unittest.TestCase):
    def test_event_sequence_mock(self):
        ok, ev = events({"requirement": "r", "provider": "mock", "tags_csv": POINTS})
        self.assertTrue(ok)
        self.assertEqual([e["type"] for e in ev], ["start", "round", "round", "done"])
        self.assertEqual((ev[0]["provider"], ev[0]["model"], ev[0]["max_rounds"], ev[0]["rag_passages"]),
                         ("mock", "demo", 3, 0))
        r0, r1, done = ev[1], ev[2], ev[3]
        self.assertEqual((r0["round"], r0["errors"], r0["more"]), (0, 1, True))
        self.assertEqual((r1["round"], r1["errors"], r1["more"]), (1, 0, False))
        self.assertIn("alarm_lamp : BOOL", r1["code"])
        self.assertEqual(done["code"], r1["code"])
        self.assertEqual(done["rounds"], 1)
        self.assertEqual([t["round"] for t in done["timeline"]], [0, 1])
        self.assertNotIn("code", done["timeline"][0])  # 程式碼不重送

    def test_more_false_when_rounds_exhausted(self):
        _, ev = events({"requirement": "r", "provider": "mock", "max_rounds": 0})
        rounds = [e for e in ev if e["type"] == "round"]
        self.assertEqual(len(rounds), 1)
        self.assertEqual((rounds[0]["errors"], rounds[0]["more"]), (1, False))
        self.assertEqual(ev[-1]["type"], "done")

    def test_each_line_is_one_json(self):
        out = []
        generate_stream({"requirement": "r", "provider": "mock"}, State(), out.append)
        for b in out:
            self.assertTrue(b.endswith(b"\n"))
            self.assertEqual(b.count(b"\n"), 1)

    def test_errors_become_events(self):
        _, ev = events({"requirement": "r", "provider": "nope"})
        self.assertEqual(ev[-1]["type"], "error")
        self.assertEqual(ev[-1]["status"], 400)
        _, ev = events({"provider": "mock"})
        self.assertIn("missing field: requirement", ev[-1]["error"])

    def test_scenario_and_matches_non_stream(self):
        from plc_st.web import handle
        scn = json.dumps({"steps": [{"set": {"start": True}, "cycles": 1, "expect": {"motor": True}}]})
        p = {"requirement": "r", "provider": "mock", "scenario": scn}
        _, ev = events(p)
        _, b = handle("POST", "/api/generate", p, State())
        self.assertEqual(ev[-1]["code"], b["code"])
        self.assertEqual(ev[-1]["issues"], b["issues"])

    def test_client_disconnect_stops_further_llm_calls(self):
        calls = []
        prov_cls = type(get_provider("mock"))
        orig = prov_cls.complete

        def spy(self, system, user):
            calls.append(1)
            return orig(self, system, user)
        prov_cls.complete = spy
        try:
            sent = []

            def write(b):
                sent.append(b)
                if b'"type": "round"' in b:
                    raise BrokenPipeError("client gone")
            ok = generate_stream({"requirement": "r", "provider": "mock"}, State(), write)
        finally:
            prov_cls.complete = orig
        self.assertFalse(ok)
        self.assertEqual(len(calls), 1)  # 初稿後斷線,不再呼叫修正輪

    def test_slow_mock_model(self):
        t = time.monotonic()
        get_provider("mock", model="demo-slow").complete("s", "u")
        self.assertGreaterEqual(time.monotonic() - t, 0.7)


class StreamHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = make_server(port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def post(self, path, body):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
        return c, c.getresponse()

    def test_http_events_arrive_incrementally(self):
        t0 = time.monotonic()
        c, r = self.post("/api/generate/stream", {"requirement": "r", "provider": "mock", "model": "demo-slow"})
        self.assertEqual(r.status, 200)
        self.assertIn("application/x-ndjson", r.getheader("Content-Type"))
        self.assertIsNone(r.getheader("Content-Length"))
        stamps = []
        while True:
            line = r.readline()
            if not line:
                break
            stamps.append((json.loads(line)["type"], time.monotonic() - t0))
        c.close()
        types = [s[0] for s in stamps]
        self.assertEqual(types, ["start", "round", "round", "done"])
        first_round, done = stamps[1][1], stamps[3][1]
        # 初稿事件在第二次 LLM 呼叫(0.8 s)完成前就已送達
        self.assertLess(first_round + 0.5, done, stamps)

    def test_http_non_stream_still_works(self):
        c, r = self.post("/api/generate", {"requirement": "r", "provider": "mock"})
        self.assertEqual(r.status, 200)
        self.assertEqual(json.loads(r.read())["rounds"], 1)
        c.close()

    def test_http_bad_json(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/api/generate/stream", "[1]", {"Content-Type": "application/json"})
        r = c.getresponse()
        self.assertEqual(r.status, 400)
        c.close()


if __name__ == "__main__":
    unittest.main()
