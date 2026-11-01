"""python -m plc_st serve [--port 8765]:stdlib http.server Web UI + JSON API(僅綁 127.0.0.1)。

POST /api/{check,run,test,tags,generate,rag/add,rag/search,rag/clear};GET /api/profiles、/。
handle() 與 HTTP 分離,方便單元測試。"""
import base64
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .checker import check
from .interpreter import VirtualPLC, STError
from .llm import get_provider, generate_checked
from .profiles import PROFILES
from .rag import VectorStore
from .scenario import run_scenario
from .tags import tags_to_var_blocks

MAX_CYCLES = 5000
INDEX_HTML = os.path.join(os.path.dirname(__file__), "web", "index.html")


class State:
    def __init__(self):
        self.store = VectorStore()


def _issues(items):
    return [{"severity": i.severity, "line": i.line, "msg": i.msg} for i in items]


def _need(p, key):
    v = p.get(key)
    if not isinstance(v, str) or not v.strip():
        raise STError(f"missing field: {key}")
    return v


def _run(p):
    plc = VirtualPLC(_need(p, "code"), scan_ms=int(p.get("scan_ms", 10)), profile=p.get("profile", "iec"))
    cycles = int(p.get("cycles", 50))
    if not 0 < cycles <= MAX_CYCLES:
        raise STError(f"cycles must be 1..{MAX_CYCLES}")
    events = [(int(e.get("cycle", 0)), e["name"], e["value"]) for e in p.get("events", [])]
    cols = list(plc.snapshot())
    rows = []
    for cyc in range(cycles):
        for c, n, v in events:
            if c == cyc:
                plc.set_input(n, v)
        plc.scan(1)
        snap = plc.snapshot()
        rows.append([plc.cycles, plc.time_ms] + [snap[k] for k in cols])
    return {"columns": ["cycle", "time_ms"] + cols, "rows": rows}


def _generate(p, state):
    req = _need(p, "requirement")
    tags = tags_to_var_blocks(p["tags_csv"]) if p.get("tags_csv", "").strip() else ""
    kw = {k: p[k] for k in ("model", "api_key", "base_url") if p.get(k)}
    prov = get_provider(p.get("provider", "ollama"), **kw)
    ctx = state.store.context(req, int(p.get("top_k", 4))) if p.get("use_rag") and state.store.docs else None
    scenario = p.get("scenario") or None
    code, issues, rounds = generate_checked(prov, req, tags, p.get("profile", "iec"), ctx,
                                            int(p.get("max_rounds", 3)), scenario)
    return {"code": code, "issues": _issues(issues), "rounds": rounds, "rag_passages": len(ctx or [])}


def _rag_add(p, state):
    if p.get("embedder", "tfidf") == "tfidf" and state.store.embedder and state.store.docs:
        raise STError("embedder 與現有索引不同,請先清空索引")
    if p.get("embedder") and p["embedder"] != "tfidf":
        from .embed import make_embedder
        spec = {k: p[k] for k in ("embed_model", "embed_api_key", "embed_base_url") if p.get(k)}
        kw = {{"embed_model": "model", "embed_api_key": "api_key", "embed_base_url": "base_url"}[k]: v for k, v in spec.items()}
        emb = make_embedder(p["embedder"], **kw)
        cur = state.store.embedder.spec() if state.store.embedder else None
        if not state.store.docs or cur != emb.spec():
            if state.store.docs:
                raise STError("embedder 與現有索引不同,請先清空索引")
            state.store = VectorStore(embedder=emb)
    name = os.path.basename(_need(p, "name"))
    ext = os.path.splitext(name)[1].lower()
    if p.get("base64"):
        data = base64.b64decode(p["base64"])
    else:
        data = _need(p, "text").encode("utf-8")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "doc" + ext)
        with open(path, "wb") as f:
            f.write(data)
        before = len(state.store.docs)
        state.store.add_file(path)
        for doc in state.store.docs[before:]:
            doc["source"] = name
    return {"chunks": len(state.store.docs) - before, "total": len(state.store.docs)}


def handle(method, path, payload, state):
    """回傳 (http_status, json_obj)。"""
    try:
        if method == "GET" and path == "/api/profiles":
            return 200, [{"name": p.name, "overflow": p.overflow, "note": p.note} for p in PROFILES.values()]
        if method != "POST":
            return 404, {"error": "not found"}
        if path == "/api/check":
            return 200, {"issues": _issues(check(_need(payload, "code"), payload.get("profile", "iec")))}
        if path == "/api/run":
            return 200, _run(payload)
        if path == "/api/test":
            fails = run_scenario(_need(payload, "code"), _need(payload, "scenario"), profile=payload.get("profile"))
            return 200, {"passed": not fails, "failures": fails}
        if path == "/api/export":
            from .export import export, FORMATS
            fmt = payload.get("format", "plcopen")
            return 200, {"text": export(_need(payload, "code"), fmt), "ext": FORMATS[fmt][0]}
        if path == "/api/tags":
            return 200, {"code": tags_to_var_blocks(_need(payload, "csv"))}
        if path == "/api/generate":
            return 200, _generate(payload, state)
        if path == "/api/rag/add":
            return 200, _rag_add(payload, state)
        if path == "/api/rag/search":
            hits = state.store.search(_need(payload, "query"), int(payload.get("top_k", 4)))
            return 200, {"hits": [{"score": round(s, 3), "source": src, "text": t} for s, src, t in hits]}
        if path == "/api/rag/clear":
            state.store = VectorStore()
            return 200, {"total": 0}
        return 404, {"error": "not found"}
    except (STError, ValueError, KeyError, TypeError, OSError) as e:
        return 400, {"error": f"{type(e).__name__}: {e}"}
    except Exception as e:  # LLM 網路錯誤等
        return 502, {"error": f"{type(e).__name__}: {e}"}


def make_server(host="127.0.0.1", port=8765):
    state = State()

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                with open(INDEX_HTML, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(*handle("GET", self.path, {}, state))

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 50_000_000:
                return self._send(413, {"error": "payload too large"})
            try:
                payload = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError
            except ValueError:
                return self._send(400, {"error": "body must be a JSON object"})
            self._send(*handle("POST", self.path, payload, state))

        def log_message(self, *a):
            pass

    return ThreadingHTTPServer((host, port), H)
