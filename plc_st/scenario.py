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


def run_scenario_detail(source, spec, profile=None, scan_ms=None):
    """逐步結果(UI 用)。回傳 list:每步 {index, step, cycles, t_ms, set, checks:[{var, expected, actual, pass}], passed}。

    執行期錯誤時拋出 STError,其 `step_index` 屬性為出錯步驟(0 起算;建立 PLC 階段為 None)。"""
    spec = _load(spec)
    scan_ms = scan_ms or spec.get("scan_ms", 10)
    if not isinstance(scan_ms, int) or isinstance(scan_ms, bool) or scan_ms <= 0:
        raise STError("scan_ms must be a positive integer")
    plc = VirtualPLC(source, scan_ms=scan_ms, profile=profile or spec.get("profile", "iec"))
    out, total = [], 0
    for i, st in enumerate(spec["steps"]):
        if not isinstance(st, dict):
            raise _at(STError(f"step #{i + 1}: must be an object"), i)
        label = st.get("name", f"#{i + 1}")
        try:
            for n, v in (st.get("set") or {}).items():
                plc.set_input(n, v)
            if "ms" in st:
                if not isinstance(st["ms"], (int, float)) or isinstance(st["ms"], bool) or st["ms"] < 0:
                    raise STError(f"step {label}: invalid cycles/ms")
                cycles = math.ceil(st["ms"] / scan_ms)
            else:
                cycles = st.get("cycles", 1)
            if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 0:
                raise STError(f"step {label}: invalid cycles/ms")
            plc.scan(cycles)
            total += cycles
            checks = []
            for n, want in (st.get("expect") or {}).items():
                try:
                    got = plc.get(n)
                except (STError, KeyError):
                    raise STError(f"step {label}: unknown variable {n}")
                checks.append({"var": n, "expected": want, "actual": got, "pass": _same(got, want)})
        except STError as e:
            raise _at(e, i)
        out.append({"index": i, "step": label, "cycles": cycles, "t_ms": total * scan_ms,
                    "set": dict(st.get("set") or {}), "checks": checks,
                    "passed": all(c["pass"] for c in checks)})
    return out


def _at(err, i):
    err.step_index = i
    return err


def run_scenario(source, spec, profile=None, scan_ms=None):
    """回傳失敗清單(空=全部通過)。每筆: dict(step, var, expected, actual)。"""
    return [{"step": s["step"], "var": c["var"], "expected": c["expected"], "actual": c["actual"]}
            for s in run_scenario_detail(source, spec, profile, scan_ms) for c in s["checks"] if not c["pass"]]
