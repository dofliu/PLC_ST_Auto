"""python -m plc_st serve [--port 8765]:stdlib http.server Web UI + JSON API(僅綁 127.0.0.1)。

POST /api/{check,run,test,export,export/status,tags,tags/preview,generate,rag/add,rag/search,rag/clear,sim/start,sim/step,sim/stop};GET /api/profiles、/。
handle() 與 HTTP 分離,方便單元測試。"""
import base64
import json
import os
import re
import secrets
import tempfile
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .checker import check
from .interpreter import VirtualPLC, STError
from .llm import get_provider, generate_checked
from .profiles import PROFILES
from .rag import VectorStore
from .scenario import run_scenario_detail
from .tags import tags_to_var_blocks, preview_tags

MAX_CYCLES = 5000
MAX_SIMS = 16  # 互動模擬 session 上限(超過時淘汰最久未用的)
INDEX_HTML = os.path.join(os.path.dirname(__file__), "web", "index.html")


class State:
    def __init__(self):
        self.store = VectorStore()
        self.sims = OrderedDict()


def _issues(items):
    return [{"severity": i.severity, "line": i.line, "msg": i.msg} for i in items]


def _need(p, key):
    v = p.get(key)
    if not isinstance(v, str) or not v.strip():
        raise STError(f"missing field: {key}")
    return v


def _meta(plc, cols):
    """每個 snapshot 欄位的型別與區段(input/output/inout/local),供 UI 畫開關/燈號。"""
    out = []
    for c in cols:
        key = re.sub(r"\[[^\]]*\]", "", c.lower())
        out.append({"name": c, "type": plc.types.get(key, ""), "section": plc.section.get(key, "local")})
    return out


def _cycles(p, default=50):
    try:
        cycles = int(p.get("cycles", default))
    except (TypeError, ValueError):
        raise STError(f"cycles must be an integer 1..{MAX_CYCLES}, got {p.get('cycles')!r}")
    if not 0 < cycles <= MAX_CYCLES:
        raise STError(f"cycles must be 1..{MAX_CYCLES}")
    return cycles


def _row(plc, cols):
    snap = plc.snapshot()
    return [plc.cycles, plc.time_ms] + [snap[k] for k in cols]


def _sim_start(p, state):
    plc = VirtualPLC(_need(p, "code"), scan_ms=int(p.get("scan_ms", 10)), profile=p.get("profile", "iec"))
    cols = list(plc.snapshot())
    sid = secrets.token_hex(8)
    state.sims[sid] = (plc, cols)
    while len(state.sims) > MAX_SIMS:
        state.sims.popitem(last=False)
    return {"id": sid, "columns": ["cycle", "time_ms"] + cols, "meta": _meta(plc, cols), "row": _row(plc, cols)}


def _sim_get(p, state):
    sid = p.get("id")
    if sid not in state.sims:
        raise STError("simulation session not found (expired or stopped); press reset")
    state.sims.move_to_end(sid)
    return state.sims[sid]


def _sim_step(p, state):
    plc, cols = _sim_get(p, state)
    sets = p.get("set") or {}
    if not isinstance(sets, dict):
        raise STError("set must be an object {name: value}")
    for n, v in sets.items():
        if plc.section.get(re.sub(r"\[[^\]]*\]", "", n.lower())) == "output":
            raise STError(f"{n} is an output; only inputs/locals can be forced")
        plc.set_input(n, v)
    rows = []
    for _ in range(_cycles(p, 1)):
        plc.scan(1)
        rows.append(_row(plc, cols))
    return {"rows": rows}


def _run(p):
    plc = VirtualPLC(_need(p, "code"), scan_ms=int(p.get("scan_ms", 10)), profile=p.get("profile", "iec"))
    cycles = _cycles(p)
    events = [(int(e.get("cycle", 0)), e["name"], e["value"]) for e in p.get("events", [])]
    cols = list(plc.snapshot())
    rows = []
    for cyc in range(cycles):
        for c, n, v in events:
            if c == cyc:
                plc.set_input(n, v)
        plc.scan(1)
        rows.append(_row(plc, cols))
    return {"columns": ["cycle", "time_ms"] + cols, "rows": rows, "meta": _meta(plc, cols)}


def _generate(p, state):
    req = _need(p, "requirement")
    tags = tags_to_var_blocks(p["tags_csv"]) if p.get("tags_csv", "").strip() else ""
    kw = {k: p[k] for k in ("model", "api_key", "base_url") if p.get(k)}
    prov = get_provider(p.get("provider", "ollama"), **kw)
    ctx = state.store.context(req, int(p.get("top_k", 4))) if p.get("use_rag") and state.store.docs else None
    scenario = p.get("scenario") or None
    timeline, t0 = [], [time.monotonic()]

    def on_round(n, code, issues):  # 每輪(含初稿)的程式碼、問題與耗時,供 UI 時間軸/差異比較
        now = time.monotonic()
        ne = sum(i.severity == "error" for i in issues)
        timeline.append({"round": n, "code": code, "issues": _issues(issues), "errors": ne,
                         "warnings": len(issues) - ne, "ms": round((now - t0[0]) * 1000)})
        t0[0] = now

    code, issues, rounds = generate_checked(prov, req, tags, p.get("profile", "iec"), ctx,
                                            int(p.get("max_rounds", 3)), scenario, on_round)
    return {"code": code, "issues": _issues(issues), "rounds": rounds, "rag_passages": len(ctx or []),
            "timeline": timeline, "provider": prov.name, "model": prov.model}


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


def _test(p):
    """情境測試:回傳 passed、failures(相容舊版)與逐步結果 steps;執行期錯誤回 400 並附 step(0 起算)。"""
    try:
        steps = run_scenario_detail(_need(p, "code"), _need(p, "scenario"), profile=p.get("profile") or None)
    except STError as e:
        return 400, {"error": f"STError: {e}", "step": getattr(e, "step_index", None)}
    fails = [{"step": s["step"], "var": c["var"], "expected": c["expected"], "actual": c["actual"]}
             for s in steps for c in s["checks"] if not c["pass"]]
    return 200, {"passed": not fails, "failures": fails, "steps": steps}


# 匯出卡片:格式 → (顯示名稱, 廠牌/軟體, 方言警告所用 profile)
EXPORT_CARDS = (
    ("plcopen", "PLCopen XML", "CODESYS / TwinCAT / 通用 TC6", "codesys"),
    ("scl", "Siemens SCL", "TIA Portal(S7-1200/1500)", "siemens-s7-1500"),
    ("l5x", "Rockwell L5X", "Studio 5000 Logix Designer", "rockwell"),
    ("gxworks", "Mitsubishi GX Works3", "MELSEC iQ-R / iQ-F", "mitsubishi"),
    ("sysmac", "Omron Sysmac Studio", "NJ / NX 系列", "omron"),
    ("st", "純 ST", "任何 IEC 61131-3 編輯器", None),
)


def export_status(code):
    """每個匯出格式是否可匯出(不可時附原因)、輸出大小與該廠牌的方言警告。"""
    from .dialect import dialect_issues
    from .export import export, FORMATS
    from .parser import parse
    try:
        parse(code)
        syntax = None
    except STError as e:
        syntax = str(e)
    out = []
    for fmt, label, vendor, prof in EXPORT_CARDS:
        item = {"format": fmt, "label": label, "vendor": vendor, "profile": prof, "ext": FORMATS[fmt][0],
                "ok": False, "size": 0, "error": None, "warnings": []}
        if syntax:
            item["error"] = f"語法錯誤:{syntax}"
        else:
            try:
                item["size"] = len(export(code, fmt))
                item["ok"] = True
            except STError as e:
                item["error"] = str(e)
            if prof:
                try:
                    item["warnings"] = [{"line": ln, "msg": m} for ln, m in dialect_issues(code, prof)]
                except STError:
                    pass
        out.append(item)
    return out


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
        if path == "/api/sim/start":
            return 200, _sim_start(payload, state)
        if path == "/api/sim/step":
            return 200, _sim_step(payload, state)
        if path == "/api/sim/stop":
            state.sims.pop(payload.get("id"), None)
            return 200, {"stopped": True}
        if path == "/api/test":
            return _test(payload)
        if path == "/api/export":
            from .export import export, FORMATS
            fmt = payload.get("format", "plcopen")
            return 200, {"text": export(_need(payload, "code"), fmt), "ext": FORMATS[fmt][0]}
        if path == "/api/export/status":
            return 200, {"formats": export_status(_need(payload, "code"))}
        if path == "/api/tags":
            return 200, {"code": tags_to_var_blocks(_need(payload, "csv"))}
        if path == "/api/tags/preview":
            return 200, preview_tags(payload.get("csv") or "")
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
