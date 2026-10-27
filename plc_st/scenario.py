"""測試情境腳本(JSON):輸入時序 + 預期輸出,於虛擬 PLC 上自動驗證。

{"scan_ms": 100, "profile": "iec",
 "steps": [{"name": "start", "set": {"start": true}, "ms": 600, "expect": {"motor": true, "t.Q": true}}]}
每個 step:先 set → 掃描 cycles 次(或 ms 毫秒,向上取整,預設 1 週期)→ 比對 expect。"""
import json
import math

from .interpreter import VirtualPLC, STError


def _load(spec):
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except json.JSONDecodeError as e:
            raise STError(f"bad scenario JSON: {e}")
    if not isinstance(spec, dict) or not isinstance(spec.get("steps"), list):
        raise STError("scenario must be an object with a 'steps' list")
    return spec


def _same(a, b):
    if isinstance(a, float) or isinstance(b, float):
        if isinstance(a, bool) or isinstance(b, bool):
            return a is b
        return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)
    return a == b and isinstance(a, bool) == isinstance(b, bool)


def run_scenario(source, spec, profile=None, scan_ms=None):
    """回傳失敗清單(空=全部通過)。每筆: dict(step, var, expected, actual)。"""
    spec = _load(spec)
    scan_ms = scan_ms or spec.get("scan_ms", 10)
    if not isinstance(scan_ms, int) or scan_ms <= 0:
        raise STError("scan_ms must be a positive integer")
    plc = VirtualPLC(source, scan_ms=scan_ms, profile=profile or spec.get("profile", "iec"))
    fails = []
    for i, st in enumerate(spec["steps"]):
        label = st.get("name", f"#{i + 1}")
        for n, v in (st.get("set") or {}).items():
            plc.set_input(n, v)
        if "ms" in st:
            cycles = math.ceil(st["ms"] / scan_ms)
        else:
            cycles = st.get("cycles", 1)
        if not isinstance(cycles, int) or cycles < 0:
            raise STError(f"step {label}: invalid cycles/ms")
        plc.scan(cycles)
        for n, want in (st.get("expect") or {}).items():
            try:
                got = plc.get(n)
            except (STError, KeyError):
                raise STError(f"step {label}: unknown variable {n}")
            if not _same(got, want):
                fails.append({"step": label, "var": n, "expected": want, "actual": got})
    return fails
