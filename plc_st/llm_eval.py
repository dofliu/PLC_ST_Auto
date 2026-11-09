"""LLM 產生 ST 的評測套件(由使用者 2026-11-09 的 run_claude_eval.py 整合而來)。

    python -m plc_st eval --provider claude --model claude-haiku-5-5 --model claude-sonnet-5-5 --repeat 3

每個案例:LLM 產生(含 check / 情境自動修正)→ 虛擬 PLC 行為驗證 → 結果與每輪錯誤寫入 results.json,
多模型時另產生對照報告 report.md。案例的判定條件在看到產生的程式之前就寫死在這裡,不依產出調整。

相對原腳本的修正:
- TC-09 原本忽略 validate_plcopen() 的回傳值(它回傳錯誤清單、不會丟例外),XSD 結果被寫死為 True。
- TC-10 原本不看靜態檢查錯誤。
- TC-02 原本只在兩個時間點檢查互鎖,改為每個掃描週期都檢查;並檢查切換時間。
- TC-04 原本只看初始綠燈與緊急全紅,改為驗證綠 5s → 黃 2s → 紅 5s → 綠 的時序。
- TC-06 原本只檢查輸出 > 0,改為驗證 5 點平均值。
- TC-08 增加計數與停止的驗證;TC-12 增加 clear 歸零;TC-05 增加「未寫入輸入點」。
- 每一輪的錯誤都會記錄(原本只知道修正了幾輪,不知道修了什麼)。
"""
import json
import math
import os
import time
import traceback

from . import web
from .export import export, validate_plcopen
from .interpreter import VirtualPLC
from .lexer import STError
from .llm import generate_checked
from .rag import VectorStore
from .scenario import run_scenario
from .tags import tags_to_var_blocks


class Case:
    def __init__(self, cid, title, fn):
        self.id, self.title, self.fn = cid, title, fn


CASES = []


def case(cid, title):
    def deco(fn):
        CASES.append(Case(cid, title, fn))
        return fn
    return deco


def _errors(issues):
    return [i for i in issues if i.severity == "error"]


# ---------------------------------------------------------------- cases
# 每個案例收到 gen(requirement, **kw) -> (code, issues, rounds),回傳 (code, issues, rounds, checks, info)
# checks: {名稱: bool};全部為 True 且最終無 error 才算 PASS。

@case("TC-01", "馬達啟停自保持與停止優先")
def tc01(gen):
    code, issues, rounds = gen("經典馬達自保持啟停控制：輸入 start 為啟動按鈕，stop 為停止按鈕，輸出 motor 為接觸器。"
                               "要求自保持電路，且停止按鈕絕對優先（同時按下時馬達必須保持關閉）。")
    plc = VirtualPLC(code, scan_ms=100)
    seq = [(False, False, False), (True, False, True), (False, False, True), (False, True, False), (True, True, False)]
    got = []
    for start, stop, _ in seq:
        plc.set_input("start", start)
        plc.set_input("stop", stop)
        plc.scan(1)
        got.append(plc.get("motor"))
    names = ["idle_off", "start_on", "self_hold", "stop_off", "stop_priority"]
    return code, issues, rounds, {n: g is e for n, g, (_, _, e) in zip(names, got, seq)}, {}


@case("TC-02", "星三角降壓啟動與互鎖")
def tc02(gen):
    code, issues, rounds = gen("星三角降壓啟動：輸入 start 啟動，stop 停止。按下 start 後主接觸器 km_main 與星形接觸器 km_star "
                               "同時吸合；TON 計時器延時 5 秒 (5000ms) 後，km_star 斷開並投入三角形接觸器 km_delta。"
                               "km_star 與 km_delta 必須有邏輯互鎖防止短路。stop 優先。")
    plc = VirtualPLC(code, scan_ms=100)
    plc.set_input("stop", False)
    plc.set_input("start", True)
    trace = []
    for i in range(80):  # 8 s
        plc.scan(1)
        if i == 0:
            plc.set_input("start", False)
        trace.append((plc.time_ms, plc.get("km_main"), plc.get("km_star"), plc.get("km_delta")))
    star_off = next((t for t, _, s, _ in trace if not s), None)
    delta_on = next((t for t, _, _, d in trace if d), None)
    plc.set_input("stop", True)
    plc.scan(1)
    stopped = not (plc.get("km_main") or plc.get("km_star") or plc.get("km_delta"))
    checks = {
        "interlock_every_scan": all(not (s and d) for _, _, s, d in trace),
        "main_on_whole_run": all(m for _, m, _, _ in trace),
        "star_first": trace[0][2] is True and trace[0][3] is False,
        "star_off_at_5s": star_off is not None and 4900 <= star_off <= 5300,
        "delta_on_after_star_off": delta_on is not None and star_off is not None and delta_on >= star_off,
        "delta_on_by_6s": delta_on is not None and delta_on <= 6000,
        "stop_drops_all": stopped,
    }
    return code, issues, rounds, checks, {"star_off_ms": star_off, "delta_on_ms": delta_on}


@case("TC-03", "工件計數 CTU + 上升緣")
def tc03(gen):
    code, issues, rounds = gen("工件包裝計數器：光電感測器 sensor 輸入，每當工件經過（上升緣觸發），使用 IEC CTU 計數器累計。"
                               "預設打包數量 PV := 10。當累計值達 10 個時，輸出 package_ready := TRUE；"
                               "按下 reset_btn 復歸按鈕時計數器歸零且 package_ready 熄滅。")
    plc = VirtualPLC(code, scan_ms=10)
    plc.set_input("reset_btn", False)
    plc.set_input("sensor", False)
    plc.scan(1)
    at9 = None
    for i in range(1, 11):
        plc.set_input("sensor", True)
        plc.scan(3)  # 感測器持續 3 個週期:上升緣只能算 1 次
        plc.set_input("sensor", False)
        plc.scan(1)
        if i == 9:
            at9 = plc.get("package_ready")
    at10 = plc.get("package_ready")
    plc.set_input("reset_btn", True)
    plc.scan(1)
    plc.set_input("reset_btn", False)
    plc.scan(1)
    checks = {"not_ready_at_9": at9 is False, "ready_at_10": at10 is True,
              "reset_clears": plc.get("package_ready") is False}
    return code, issues, rounds, checks, {}


@case("TC-04", "交通號誌狀態機時序")
def tc04(gen):
    code, issues, rounds = gen("交通號誌狀態機控制：使用 CASE 語法或狀態變數實作三態循環。State 0: 綠燈 green 亮 5 秒；"
                               "State 1: 黃燈 yellow 亮 2 秒；State 2: 紅燈 red 亮 5 秒，隨後回到 State 0。"
                               "若 emergency 信號為 TRUE，立即強制進入全紅燈模式（僅 red 為 TRUE，green 與 yellow 強制為 FALSE）。")
    plc = VirtualPLC(code, scan_ms=100)
    plc.set_input("emergency", False)
    lamps = []
    for _ in range(150):  # 15 s
        plc.scan(1)
        lamps.append((plc.get("green"), plc.get("yellow"), plc.get("red")))
    one_on = all(sum(bool(x) for x in l) == 1 for l in lamps)
    phases = []  # [(lamp, scans)]
    for l in lamps:
        name = "gyr"[l.index(True)] if True in l else "-"
        if phases and phases[-1][0] == name:
            phases[-1][1] += 1
        else:
            phases.append([name, 1])
    seq = "".join(p[0] for p in phases)
    dur = {p[0]: p[1] * 100 for p in phases[1:-1]}  # 完整的中間相位
    first_green = phases[0][1] * 100 if phases and phases[0][0] == "g" else 0
    plc.set_input("emergency", True)
    plc.scan(1)
    checks = {
        "exactly_one_lamp": one_on,
        "order_g_y_r_g": seq.startswith("gyrg"),
        "green_about_5s": 4800 <= first_green <= 5300,
        "yellow_about_2s": 1800 <= dur.get("y", 0) <= 2300,
        "red_about_5s": 4800 <= dur.get("r", 0) <= 5300,
        "emergency_all_red": (plc.get("red"), plc.get("green"), plc.get("yellow")) == (True, False, False),
    }
    return code, issues, rounds, checks, {"phases": [(p, n * 100) for p, n in phases]}


TANK_TAGS = """name,type,direction,init,comment
emergency_stop,BOOL,IN,false,現場急停開關
high_level_sw,BOOL,IN,false,水槽高水位浮球
low_level_sw,BOOL,IN,false,水槽低水位浮球
inlet_valve,BOOL,OUT,false,進水電磁閥
drain_pump,BOOL,OUT,false,排水泵浦
alarm_lamp,BOOL,OUT,false,水位警報燈
fill_time,TIME,VAR,T#0s,進水累計時間"""


@case("TC-05", "點位表 CSV 嚴格綁定")
def tc05(gen):
    code, issues, rounds = gen("水槽自動給排水控制：嚴格遵照點位表。低水位 low_level_sw 觸發且未高水位時打開進水閥 inlet_valve 補水；"
                               "當高水位 high_level_sw 觸發時關閉進水閥並啟動排水泵 drain_pump；若 emergency_stop 為 TRUE，"
                               "則關閉進水閥與排水泵，並點亮 alarm_lamp。", tags_text=tags_to_var_blocks(TANK_TAGS))
    plc = VirtualPLC(code, scan_ms=100)
    declared = {n.lower() for n in plc.names}
    tags = [l.split(",")[0] for l in TANK_TAGS.splitlines()[1:]]
    plc.set_input("emergency_stop", False)
    plc.set_input("low_level_sw", True)
    plc.set_input("high_level_sw", False)
    plc.scan(1)
    fill = plc.get("inlet_valve")
    plc.set_input("low_level_sw", False)
    plc.set_input("high_level_sw", True)
    plc.scan(1)
    drain = plc.get("drain_pump") is True and plc.get("inlet_valve") is False
    plc.set_input("emergency_stop", True)
    plc.scan(1)
    checks = {
        "all_tags_declared": all(t in declared for t in tags),
        "no_write_to_inputs": not any("write to input" in i.msg for i in issues),
        "fill_on_low": fill is True,
        "drain_on_high": drain,
        "emergency_safe": (plc.get("alarm_lamp"), plc.get("inlet_valve"), plc.get("drain_pump")) == (True, False, False),
    }
    return code, issues, rounds, checks, {}


FILTER_SPEC = """# 企業自訂標準: 5點滑動平均濾波規範
在類比量處理中，為避免雜訊干擾，一律使用 ARRAY[0..4] OF REAL 儲存最近 5 次取樣值。
變數規範：
- raw_in : REAL 輸入原始值
- filter_out : REAL 濾波後輸出
- buf : ARRAY[0..4] OF REAL 緩衝區
- idx : INT 索引 (0..4)
演算法：每次掃描將 raw_in 寫入 buf[idx]，計算 5 點總和除以 5.0，並更新 idx := (idx + 1) MOD 5。"""


@case("TC-06", "RAG 規範:5 點滑動平均")
def tc06(gen):
    store = VectorStore()
    store.add_text("custom_filter_spec.md", FILTER_SPEC)
    req = "依據企業標準實作類比輸入的 5 點滑動平均濾波程式。"
    ctx = store.context(req, k=2)
    code, issues, rounds = gen(req, context=ctx)
    plc = VirtualPLC(code, scan_ms=50)
    plc.set_input("raw_in", 10.0)
    plc.scan(5)
    a = plc.get("filter_out")
    plc.set_input("raw_in", 20.0)
    plc.scan(2)
    b = plc.get("filter_out")  # (3*10 + 2*20) / 5 = 14
    plc.scan(3)
    c = plc.get("filter_out")
    checks = {
        "rag_context_used": bool(ctx),
        "uses_buf_array": "buf" in plc.arrays and len(plc.vars["buf"]) == 5,
        "steady_10": math.isclose(a, 10.0, abs_tol=1e-4),
        "window_mix_14": math.isclose(b, 14.0, abs_tol=1e-4),
        "steady_20": math.isclose(c, 20.0, abs_tol=1e-4),
    }
    return code, issues, rounds, checks, {"outputs": [a, b, c]}


@case("TC-07", "Siemens S7-1200 溫控回差")
def tc07(gen):
    code, issues, rounds = gen("西門子 S7-1200 溫控系統：類比輸入 temp_pv (REAL)，設定值 temp_sp (REAL)。"
                               "若 temp_pv < temp_sp - 2.0 則開啟加熱器 heater (BOOL)；若 temp_pv > temp_sp + 2.0 "
                               "則關閉 heater 並啟動冷卻器 cooler (BOOL)。", vendor="siemens-s7-1200")
    plc = VirtualPLC(code, scan_ms=100, profile="siemens-s7-1200")
    plc.set_input("temp_sp", 50.0)
    plc.set_input("temp_pv", 40.0)
    plc.scan(1)
    heat = plc.get("heater") is True and plc.get("cooler") is not True
    plc.set_input("temp_pv", 60.0)
    plc.scan(1)
    cool = plc.get("cooler") is True and plc.get("heater") is False
    checks = {"no_64bit_types": not any("64-bit" in i.msg or "not supported" in i.msg for i in issues),
              "heater_when_cold": heat, "cooler_when_hot": cool}
    return code, issues, rounds, checks, {}


@case("TC-08", "Rockwell 輸送帶與計數")
def tc08(gen):
    code, issues, rounds = gen("Rockwell ControlLogix 輸送帶控制：按 start 啟動輸送帶 conveyor，按 stop 停止。"
                               "具備光電開關 item_trigger 累計產量 item_count (DINT)。", vendor="rockwell")
    plc = VirtualPLC(code, scan_ms=50, profile="rockwell")
    plc.set_input("stop", False)
    plc.set_input("start", True)
    plc.scan(1)
    plc.set_input("start", False)
    plc.scan(1)
    running = plc.get("conveyor")
    for _ in range(3):
        plc.set_input("item_trigger", True)
        plc.scan(2)
        plc.set_input("item_trigger", False)
        plc.scan(1)
    count = plc.get("item_count")
    plc.set_input("stop", True)
    plc.scan(1)
    checks = {"runs_and_holds": running is True, "counts_3_items": count == 3,
              "stop_stops": plc.get("conveyor") is False}
    warns = [i.msg for i in issues if "dialect" in i.msg]
    return code, issues, rounds, checks, {"dialect_warnings": warns}


@case("TC-09", "PLCopen TC6 XSD 驗證")
def tc09(gen):
    code, issues, rounds = gen("雙馬達順序啟動：按下 start 後馬達 motor1 先啟動，延遲 3 秒後馬達 motor2 啟動。"
                               "按下 stop 時兩台馬達立即停止。")
    xml = export(code, "plcopen")
    try:
        xsd = validate_plcopen(xml)
        checks = {"tc6_xsd_valid": xsd == []}
        info = {"xsd_errors": xsd[:5]}
    except STError as e:  # 未安裝 lxml
        checks, info = {"tc6_xsd_valid": False}, {"xsd_errors": [str(e)]}
    plc = VirtualPLC(code, scan_ms=100)
    plc.set_input("stop", False)
    plc.set_input("start", True)
    plc.scan(1)
    plc.set_input("start", False)
    plc.scan(1)
    m1, m2_early = plc.get("motor1"), plc.get("motor2")
    plc.scan(35)
    m2 = plc.get("motor2")
    plc.set_input("stop", True)
    plc.scan(1)
    checks.update({"motor1_first": m1 is True and m2_early is False, "motor2_after_3s": m2 is True,
                   "stop_both": (plc.get("motor1"), plc.get("motor2")) == (False, False)})
    return code, issues, rounds, checks, info


@case("TC-10", "多廠牌匯出")
def tc10(gen):
    code, issues, rounds = gen("經典水泵啟停：start, stop, pump, run_hours (INT)。")
    checks, info = {}, {}
    for fmt in ("plcopen", "scl", "l5x", "gxworks", "sysmac", "st"):
        try:
            checks[f"export_{fmt}"] = len(export(code, fmt)) > 0
        except STError as e:
            checks[f"export_{fmt}"] = False
            info[fmt] = str(e)
    return code, issues, rounds, checks, info


FIRE_SCENARIO = {"scan_ms": 100, "steps": [
    {"name": "initial_idle", "cycles": 2, "expect": {"alarm": False, "siren": False}},
    {"name": "fire_detected", "set": {"fire_sensor": True}, "cycles": 1, "expect": {"alarm": True}},
    {"name": "siren_delay", "ms": 500, "expect": {"siren": True}},
    {"name": "reset_alarm", "set": {"fire_sensor": False, "ack_btn": True}, "cycles": 1,
     "expect": {"alarm": False, "siren": False}}]}


@case("TC-11", "情境驅動自動修正")
def tc11(gen):
    sc = json.dumps(FIRE_SCENARIO)
    code, issues, rounds = gen("火警警報系統：當火警感測器 fire_sensor 觸發時，立即輸出 alarm := TRUE；若火警持續超過 400ms，"
                               "啟動蜂鳴器 siren := TRUE；當火警解除且按下確認按鈕 ack_btn 時，alarm 與 siren 皆復歸為 FALSE。",
                               scenario=sc, max_rounds=3)
    fails = run_scenario(code, sc)
    return code, issues, rounds, {"scenario_pass": not fails}, {"scenario_failures": fails}


@case("TC-12", "INT 防溢位與清除")
def tc12(gen):
    code, issues, rounds = gen("高速產量計數器：感測器 pulse (BOOL) 上升緣時，累加總產量 total_count (INT)。"
                               "要求具備防溢位保護（避免 INT 超過 32767 產生負數），當到達 32767 時保持在上限不再累加；"
                               "按下 clear 時歸零。")
    plc = VirtualPLC(code, scan_ms=10, profile="strict")  # strict:任何溢位都會直接報錯
    plc.set_input("clear", False)
    for _ in range(3):
        plc.set_input("pulse", True)
        plc.scan(1)
        plc.set_input("pulse", False)
        plc.scan(1)
    counts = plc.get("total_count")
    plc.vars["total_count"] = 32766
    for _ in range(3):
        plc.set_input("pulse", True)
        plc.scan(1)
        plc.set_input("pulse", False)
        plc.scan(1)
    capped = plc.get("total_count")
    plc.set_input("clear", True)
    plc.scan(1)
    checks = {"counts_edges": counts == 3, "caps_at_32767": capped == 32767, "clear_resets": plc.get("total_count") == 0}
    return code, issues, rounds, checks, {}


@case("TC-13", "模糊需求的安全假設")
def tc13(gen):
    code, issues, rounds = gen("風機啟停：按鈕 run_cmd 與 stop_cmd 同時控制 fan_out。若兩個按鈕同時被按下，必須優先保護設備安全。")
    plc = VirtualPLC(code, scan_ms=50)
    plc.set_input("run_cmd", True)
    plc.set_input("stop_cmd", True)
    plc.scan(1)
    checks = {"stop_priority": plc.get("fan_out") is False, "states_assumption": "(*" in code or "//" in code}
    return code, issues, rounds, checks, {}


@case("TC-14", "Web API /api/generate")
def tc14(gen):
    return gen.web("冷卻水塔啟停：start 啟動 pump，stop 停止。")


# ---------------------------------------------------------------- runner

class _Usage:
    """包住 provider.transport,記錄呼叫次數與 token(Claude / OpenAI / Gemini / Ollama 回應格式)。"""

    def __init__(self, provider):
        self.calls = self.tin = self.tout = 0
        inner = getattr(provider, "transport", None)
        if inner is None:
            return

        def wrapped(url, headers, payload):
            d = inner(url, headers, payload)
            self.calls += 1
            u = d.get("usage") or {} if isinstance(d, dict) else {}
            g = d.get("usageMetadata") or {} if isinstance(d, dict) else {}
            self.tin += u.get("input_tokens", u.get("prompt_tokens", 0)) or g.get("promptTokenCount", 0) \
                or (d.get("prompt_eval_count", 0) if isinstance(d, dict) else 0)
            self.tout += u.get("output_tokens", u.get("completion_tokens", 0)) or g.get("candidatesTokenCount", 0) \
                or (d.get("eval_count", 0) if isinstance(d, dict) else 0)
            return d
        provider.transport = wrapped

    def snap(self):
        return self.calls, self.tin, self.tout


def run_case(c, provider, max_rounds=2, vendor="iec"):
    """執行單一案例,回傳結果 dict(不丟例外)。"""
    rounds_log = []

    def on_round(n, code, issues):
        rounds_log.append({"round": n, "code": code, "errors": [str(i) for i in _errors(issues)]})

    def gen(req, tags_text="", vendor=vendor, context=None, scenario=None, max_rounds=max_rounds):
        return generate_checked(provider, req, tags_text, vendor, context, max_rounds, scenario, on_round)

    def via_web(req):
        # 讓 /api/generate 用同一個(已計量的)provider 物件,模型與 token 統計才一致
        orig = web.get_provider
        web.get_provider = lambda *a, **k: provider
        try:
            status, resp = web.handle("POST", "/api/generate",
                                      {"provider": "claude", "requirement": req, "max_rounds": max_rounds}, web.State())
        finally:
            web.get_provider = orig
        code = resp.get("code", "") if isinstance(resp, dict) else ""
        checks = {"http_200": status == 200, "has_program": "PROGRAM" in code and "END_PROGRAM" in code}
        issues = [_Issue(i["severity"], i["line"], i["msg"]) for i in resp.get("issues", [])] if status == 200 else []
        return code, issues, resp.get("rounds", 0) if status == 200 else 0, checks, {"http_status": status}

    gen.web = via_web
    t0 = time.time()
    res = {"id": c.id, "title": c.title}
    try:
        code, issues, rounds, checks, info = c.fn(gen)
        errs = [str(i) for i in _errors(issues)]
        res.update(code=code, rounds=rounds, final_errors=errs,
                   warnings=[str(i) for i in issues if i.severity != "error"], checks=checks, info=info,
                   status="PASS" if not errs and all(checks.values()) else "FAIL")
    except STError as e:  # 產生的程式在虛擬 PLC 上無法執行(缺點位、語法等)屬於 FAIL
        res.update(status="FAIL", error=f"STError: {e}")
    except Exception as e:  # noqa: BLE001 — 評測不中斷,記錄後續看
        res.update(status="ERROR", error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc()[-800:])
    res["rounds_log"] = rounds_log
    res["first_try"] = (not rounds_log[0]["errors"]) if rounds_log else (res["status"] == "PASS" and not res.get("rounds"))
    res["seconds"] = round(time.time() - t0, 2)
    return res


class _Issue:
    def __init__(self, severity, line, msg):
        self.severity, self.line, self.msg = severity, line, msg

    def __str__(self):
        return f"{self.severity}: line {self.line}: {self.msg}"


def run_eval(provider, repeat=1, case_ids=None, max_rounds=2, out_dir=None, log=print):
    """對單一 provider/model 執行所選案例 repeat 次。回傳 summary dict(含每次結果)。"""
    cases = [c for c in CASES if not case_ids or c.id in case_ids]
    usage = _Usage(provider)
    runs = []
    for r in range(1, repeat + 1):
        for c in cases:
            before = usage.snap()
            res = run_case(c, provider, max_rounds)
            after = usage.snap()
            res.update(run=r, api_calls=after[0] - before[0], input_tokens=after[1] - before[1],
                       output_tokens=after[2] - before[2])
            runs.append(res)
            log(f"[{provider.model}] run {r}/{repeat} {c.id} {res['status']} "
                f"rounds={res.get('rounds', '-')} {res['seconds']}s" + (f"  {res.get('error', '')}" if res.get("error") else ""))
            if out_dir and (res.get("code") or res.get("rounds_log")):
                d = os.path.join(out_dir, _safe(provider.model), f"run{r}")
                os.makedirs(d, exist_ok=True)
                base = c.id.lower().replace("-", "")
                final = res.get("code") or (res["rounds_log"][-1].get("code") if res.get("rounds_log") else "")
                with open(os.path.join(d, f"{base}.st"), "w", encoding="utf-8") as f:
                    f.write(final or "")
                for rl in res.get("rounds_log", []):  # 每輪(含被修正前的)程式碼,供事後檢視
                    if rl.get("code"):
                        with open(os.path.join(d, f"{base}_round{rl['round']}.st"), "w", encoding="utf-8") as f:
                            f.write(rl["code"])
    return {"provider": provider.name, "model": provider.model, "repeat": repeat, "max_rounds": max_rounds,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": runs}


def _safe(s):
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in s)


def summarize(result):
    runs = result["runs"]
    n = len(runs)
    ok = [r for r in runs if r["status"] == "PASS"]
    return {
        "model": result["model"], "runs": n, "pass": len(ok),
        "pass_rate": len(ok) / n if n else 0.0,
        "first_try_pass": sum(1 for r in ok if r.get("first_try")),
        "avg_rounds": sum(r.get("rounds", 0) or 0 for r in runs) / n if n else 0.0,
        "avg_seconds": sum(r["seconds"] for r in runs) / n if n else 0.0,
        "api_calls": sum(r.get("api_calls", 0) for r in runs),
        "input_tokens": sum(r.get("input_tokens", 0) for r in runs),
        "output_tokens": sum(r.get("output_tokens", 0) for r in runs),
    }


def report_md(results, prices=None):
    """多個 run_eval 結果 → Markdown 對照報告。prices: {model: (USD/百萬輸入 token, USD/百萬輸出 token)}。"""
    prices = prices or {}
    sums = [summarize(r) for r in results]
    rep = results[0]["repeat"] if results else 0
    o = ["# LLM 產生 ST 對照評測", "",
         f"日期:{time.strftime('%Y-%m-%d %H:%M')}　每案重複:{rep} 次　自動修正上限:{results[0]['max_rounds'] if results else '-'} 輪", "",
         "> 判定條件寫在 `plc_st/llm_eval.py`,在看到任何產出之前就固定;PASS = 最終無靜態檢查 error 且所有行為檢查通過。",
         "> 「一次正確」= 第 0 輪就沒有 error(未經修正)。LLM 每次輸出不同,通過率請以重複次數解讀。", "",
         "## 總覽", "",
         "| 模型 | 通過 | 通過率 | 一次正確 | 平均修正輪數 | 平均秒數 | API 呼叫 | 輸入 token | 輸出 token | 估計費用 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for s in sums:
        p = prices.get(s["model"])
        cost = f"${(s['input_tokens'] * p[0] + s['output_tokens'] * p[1]) / 1e6:.4f}" if p else "—"
        o.append(f"| `{s['model']}` | {s['pass']}/{s['runs']} | {s['pass_rate']:.0%} | {s['first_try_pass']}/{s['runs']} "
                 f"| {s['avg_rounds']:.2f} | {s['avg_seconds']:.1f} | {s['api_calls']} | {s['input_tokens']:,} "
                 f"| {s['output_tokens']:,} | {cost} |")
    o += ["", "## 各案例", "", "| 案例 | " + " | ".join(f"`{s['model']}`" for s in sums) + " |",
          "|---|" + "---|" * len(sums)]
    for c in CASES:
        cells = []
        for r in results:
            rs = [x for x in r["runs"] if x["id"] == c.id]
            if not rs:
                cells.append("—")
                continue
            p = sum(x["status"] == "PASS" for x in rs)
            cells.append(f"{'✅' if p == len(rs) else ('⚠️' if p else '❌')} {p}/{len(rs)}")
        if any(cell != "—" for cell in cells):
            o.append(f"| {c.id} {c.title} | " + " | ".join(cells) + " |")
    o += ["", "## 失敗與修正明細", ""]
    any_detail = False
    for r in results:
        for x in r["runs"]:
            fixed = [l for l in x.get("rounds_log", []) if l["errors"]]
            if x["status"] == "PASS" and not fixed:
                continue
            any_detail = True
            o.append(f"**`{r['model']}` run {x['run']} {x['id']} — {x['status']}**")
            if x.get("error"):
                o.append(f"- 例外:`{x['error']}`")
            bad = [k for k, v in (x.get("checks") or {}).items() if not v]
            if bad:
                o.append(f"- 未通過的行為檢查:{', '.join(bad)}")
            for e in x.get("final_errors", []):
                o.append(f"- 最終錯誤:`{e}`")
            for l in fixed:
                o.append(f"- 第 {l['round']} 輪錯誤(已回饋修正):" + "; ".join(f"`{e}`" for e in l["errors"][:3]))
            o.append("")
    if not any_detail:
        o.append("無。")
    return "\n".join(o) + "\n"


def main_eval(provider_name, models, repeat=1, case_ids=None, max_rounds=2, out="eval_out", prices=None, log=print,
              provider_factory=None):
    """CLI 進入點。provider_factory(model) 可注入(測試用)。回傳 (results, report_path)。"""
    from .llm import get_provider
    out_dir = os.path.join(out, time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for m in models or [None]:
        prov = provider_factory(m) if provider_factory else get_provider(provider_name, **({"model": m} if m else {}))
        res = run_eval(prov, repeat, case_ids, max_rounds, out_dir, log)
        results.append(res)
        with open(os.path.join(out_dir, f"results_{_safe(prov.model)}.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    path = os.path.join(out_dir, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_md(results, prices))
    return results, path
