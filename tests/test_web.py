import base64
import json
import threading
import unittest
import urllib.request

from plc_st.web import State, handle, make_server

MOTOR = open("examples/motor.st", encoding="utf-8").read()
SCN = open("examples/motor_scenario.json", encoding="utf-8").read()


class WebHandleTests(unittest.TestCase):
    def setUp(self):
        self.s = State()

    def post(self, path, **p):
        return handle("POST", path, p, self.s)

    def test_export(self):
        code, body = self.post("/api/export", code=MOTOR, format="scl")
        self.assertEqual((code, body["ext"]), (200, "scl"))
        self.assertEqual(self.post("/api/export", code=MOTOR, format="bad")[0], 400)

    def test_export_gxworks(self):
        code, body = self.post("/api/export", code=MOTOR, format="gxworks")
        self.assertEqual((code, body["ext"]), (200, "txt"))
        self.assertIn("Label Name", body["text"])

    def test_rag_embedder_option(self):
        code, _ = self.post("/api/rag/add", name="a.md", text="TON timer 計時器", embedder="hash")
        self.assertEqual(code, 200)
        self.assertEqual(self.s.store.embedder.name, "hash")
        code, body = self.post("/api/rag/search", query="TON timer")
        self.assertEqual(code, 200)
        self.assertTrue(body["hits"])
        self.assertEqual(self.post("/api/rag/add", name="b.md", text="x y z", embedder="ollama")[0], 400)
        self.assertEqual(self.post("/api/rag/add", name="b.md", text="x y z")[0], 400)
        self.post("/api/rag/clear")
        self.assertEqual(self.post("/api/rag/add", name="b.md", text="x y z")[0], 200)
        self.assertEqual(self.post("/api/rag/add", name="c.md", text="x", embedder="nope")[0], 400)

    def test_profiles(self):
        code, body = handle("GET", "/api/profiles", {}, self.s)
        self.assertEqual(code, 200)
        self.assertIn("iec", [p["name"] for p in body])

    def test_check_and_missing_field(self):
        code, body = self.post("/api/check", code=MOTOR)
        self.assertEqual((code, body["issues"]), (200, []))
        code, body = self.post("/api/check", code="PROGRAM X\nVAR a:INT; END_VAR\nb := 1;\nEND_PROGRAM")
        self.assertTrue(any(i["severity"] == "error" for i in body["issues"]))
        self.assertEqual(self.post("/api/check")[0], 400)

    def test_run_trace_and_limit(self):
        code, body = self.post("/api/run", code=MOTOR, cycles=5,
                               events=[{"cycle": 1, "name": "start", "value": True}])
        self.assertEqual(code, 200)
        self.assertEqual(len(body["rows"]), 5)
        i = body["columns"].index("motor")
        self.assertFalse(body["rows"][0][i])
        self.assertTrue(body["rows"][2][i])
        self.assertEqual(self.post("/api/run", code=MOTOR, cycles=10**6)[0], 400)

    def test_scenario(self):
        code, body = self.post("/api/test", code=MOTOR, scenario=SCN)
        self.assertEqual((code, body["passed"]), (200, True))
        bad = json.dumps({"steps": [{"set": {"start": True}, "expect": {"motor": False}}]})
        self.assertFalse(self.post("/api/test", code=MOTOR, scenario=bad)[1]["passed"])
        self.assertEqual(self.post("/api/test", code=MOTOR, scenario="{")[0], 400)

    def test_rag_add_search_clear(self):
        b = base64.b64encode("TON 計時器 On-delay timer: PT preset time, Q output".encode()).decode()
        code, body = self.post("/api/rag/add", name="ton.md", base64=b)
        self.assertEqual(code, 200)
        self.assertGreater(body["total"], 0)
        hits = self.post("/api/rag/search", query="TON timer preset")[1]["hits"]
        self.assertEqual(hits[0]["source"], "ton.md")
        self.assertEqual(self.post("/api/rag/clear")[1]["total"], 0)
        self.assertEqual(self.post("/api/rag/add", name="x.exe", text="a")[0], 400)

    def test_tags(self):
        code, body = self.post("/api/tags", csv="name,type,direction\nstart,BOOL,IN\n")
        self.assertEqual(code, 200)
        self.assertIn("start", body["code"])

    def test_unknown_provider_400_and_unknown_path_404(self):
        self.assertEqual(self.post("/api/generate", requirement="x", provider="nope")[0], 400)
        self.assertEqual(self.post("/api/nope")[0], 404)


class WebHttpTests(unittest.TestCase):
    def test_http_roundtrip(self):
        srv = make_server(port=0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        self.assertIn("PLC ST", urllib.request.urlopen(base + "/").read().decode())
        req = urllib.request.Request(base + "/api/check", json.dumps({"code": MOTOR}).encode(),
                                     {"Content-Type": "application/json"})
        self.assertEqual(json.load(urllib.request.urlopen(req))["issues"], [])


if __name__ == "__main__":
    unittest.main()
