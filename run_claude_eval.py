"""Claude PLC ST 代碼生成與全方位驗證自動化測試套件
涵蓋 14 項測試案例 (TC-01 至 TC-14)
"""
import os
import sys
import time
import json
import traceback

from plc_st.llm import get_provider, generate_checked
from plc_st.checker import check
from plc_st.interpreter import VirtualPLC, STError
from plc_st.export import export, validate_plcopen
from plc_st.scenario import run_scenario
from plc_st.tags import tags_to_var_blocks
from plc_st.rag import VectorStore
from plc_st.web import handle, State

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

class ClaudeTestRunner:
    def __init__(self):
        self.provider = get_provider("claude")
        self.results = []
        os.makedirs("docs/claude_eval_artifacts", exist_ok=True)

    def run_all(self):
        tests = [
            ("TC-01", "基本馬達啟停自保持與停止優先", self.test_tc01_motor_start_stop),
            ("TC-02", "星三角延遲降壓啟動與互鎖控制", self.test_tc02_star_delta),
            ("TC-03", "工件計數與批量打包 (CTU & R_TRIG)", self.test_tc03_batch_counter),
            ("TC-04", "交通號誌循環狀態機 (CASE Statement)", self.test_tc04_traffic_lights),
            ("TC-05", "嚴格點位表 (CSV) 綁定與一致性", self.test_tc05_tag_binding),
            ("TC-06", "RAG 專用規範檢索增強生成", self.test_tc06_rag_generation),
            ("TC-07", "Siemens S7-1200 Profile 方言相容性", self.test_tc07_siemens_profile),
            ("TC-08", "Rockwell ControlLogix Profile 規範檢查", self.test_tc08_rockwell_profile),
            ("TC-09", "PLCopen TC6 XML 匯出與官方 XSD 嚴格校驗", self.test_tc09_plcopen_xsd),
            ("TC-10", "多廠牌格式匯出驗證 (SCL/L5X/GXWorks/Sysmac/ST)", self.test_tc10_multivendor_export),
            ("TC-11", "情境時序驅動驗證與自動修復閉環", self.test_tc11_scenario_auto_repair),
            ("TC-12", "數值邊界防溢位與運算安全防護", self.test_tc12_overflow_guard),
            ("TC-13", "模糊/衝突需求之安全假設與優先原則", self.test_tc13_ambiguity_safety),
            ("TC-14", "Web API 端到端整合驗證 (/api/generate)", self.test_tc14_web_api),
        ]

        log(f"=== 開始執行 Claude ST 代碼生成評測 (共 {len(tests)} 項) ===")
        start_all = time.time()

        for tid, name, fn in tests:
            log(f"\n--- 執行 [{tid}] {name} ---")
            t0 = time.time()
            try:
                res = fn()
                res["id"] = tid
                res["name"] = name
                res["duration_sec"] = round(time.time() - t0, 2)
                res["status"] = "PASS" if res.get("passed", False) else "FAIL"
            except Exception as e:
                log(f"EXCEPTION in {tid}: {e}")
                traceback.print_exc()
                res = {
                    "id": tid,
                    "name": name,
                    "status": "ERROR",
                    "error": str(e),
                    "duration_sec": round(time.time() - t0, 2),
                    "passed": False
                }
            self.results.append(res)
            log(f"[{tid}] 結果: {res['status']} (耗時: {res['duration_sec']}s)")

        total_time = round(time.time() - start_all, 2)
        passed_count = sum(1 for r in self.results if r["status"] == "PASS")
        log(f"\n=== 評測完成: {passed_count}/{len(tests)} 通過，總耗時: {total_time}s ===")

        # 保存詳細 JSON 結果
        out_path = "docs/claude_eval_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "model": self.provider.model,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_tests": len(tests),
                "passed": passed_count,
                "total_time_sec": total_time,
                "results": self.results
            }, f, ensure_ascii=False, indent=2)
        log(f"詳細評測數據已存入 {out_path}")
        return self.results

    def test_tc01_motor_start_stop(self):
        req = "經典馬達自保持啟停控制：輸入 start 為啟動按鈕，stop 為停止按鈕，輸出 motor 為接觸器。要求自保持電路，且停止按鈕絕對優先（同時按下時馬達必須保持關閉）。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        
        # 1. 靜態檢查
        has_error = any(i.severity == "error" for i in issues)
        
        # 2. 虛擬 PLC 模擬 (5 週期)
        plc = VirtualPLC(code, scan_ms=100)
        # Cycle 0: idle
        plc.set_input("start", False)
        plc.set_input("stop", False)
        plc.scan(1)
        c0 = plc.get("motor")
        
        # Cycle 1: start
        plc.set_input("start", True)
        plc.scan(1)
        c1 = plc.get("motor")
        
        # Cycle 2: release start (self holding)
        plc.set_input("start", False)
        plc.scan(1)
        c2 = plc.get("motor")
        
        # Cycle 3: stop
        plc.set_input("stop", True)
        plc.scan(1)
        c3 = plc.get("motor")
        
        # Cycle 4: start and stop together (stop priority!)
        plc.set_input("start", True)
        plc.set_input("stop", True)
        plc.scan(1)
        c4 = plc.get("motor")

        sim_ok = (c0 is False) and (c1 is True) and (c2 is True) and (c3 is False) and (c4 is False)

        with open("docs/claude_eval_artifacts/tc01_motor.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and sim_ok,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "sim_results": {
                "idle_is_false": c0 is False,
                "start_is_true": c1 is True,
                "holding_is_true": c2 is True,
                "stop_is_false": c3 is False,
                "stop_priority_is_false": c4 is False
            },
            "code_snippet": code[:400]
        }

    def test_tc02_star_delta(self):
        req = "星三角降壓啟動：輸入 start 啟動，stop 停止。按下 start 後主接觸器 km_main 與星形接觸器 km_star 同時吸合；TON 計時器延時 5 秒 (5000ms) 後，km_star 斷開並投入三角形接觸器 km_delta。km_star 與 km_delta 必須有邏輯互鎖防止短路。stop 優先。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        plc = VirtualPLC(code, scan_ms=500)
        plc.set_input("start", True)
        plc.set_input("stop", False)
        plc.scan(1)
        plc.set_input("start", False)
        
        # 初始階段 (1000ms): main=True, star=True, delta=False
        plc.scan(1)
        s_main1 = plc.get("km_main")
        s_star1 = plc.get("km_star")
        s_delta1 = plc.get("km_delta")
        
        # 推進至 6000ms (> 5000ms 切換): main=True, star=False, delta=True
        plc.scan(10)
        s_main2 = plc.get("km_main")
        s_star2 = plc.get("km_star")
        s_delta2 = plc.get("km_delta")
        
        # 互鎖驗證
        interlock_ok = not (s_star1 and s_delta1) and not (s_star2 and s_delta2)
        phase1_ok = (s_main1 is True) and (s_star1 is True) and (s_delta1 is False)
        phase2_ok = (s_main2 is True) and (s_star2 is False) and (s_delta2 is True)

        with open("docs/claude_eval_artifacts/tc02_star_delta.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and interlock_ok and phase1_ok and phase2_ok,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "sim_results": {
                "phase1_star_active": phase1_ok,
                "phase2_delta_active": phase2_ok,
                "interlock_safe": interlock_ok
            },
            "code_snippet": code[:400]
        }

    def test_tc03_batch_counter(self):
        req = "工件包裝計數器：光電感測器 sensor 輸入，每當工件經過（上升緣觸發），使用 IEC CTU 計數器累計。預設打包數量 PV := 10。當累計值達 10 個時，輸出 package_ready := TRUE；按下 reset_btn 復歸按鈕時計數器歸零且 package_ready 熄滅。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        plc = VirtualPLC(code, scan_ms=10)
        plc.set_input("reset_btn", False)
        plc.set_input("sensor", False)
        plc.scan(1)

        # 模擬 10 次工件通過脈衝
        ready_at_9 = None
        for i in range(1, 11):
            plc.set_input("sensor", True)
            plc.scan(1)
            plc.set_input("sensor", False)
            plc.scan(1)
            if i == 9:
                ready_at_9 = plc.get("package_ready")

        ready_at_10 = plc.get("package_ready")

        # 測試 reset
        plc.set_input("reset_btn", True)
        plc.scan(1)
        plc.set_input("reset_btn", False)
        plc.scan(1)
        ready_after_reset = plc.get("package_ready")

        count_ok = (ready_at_9 is False) and (ready_at_10 is True) and (ready_after_reset is False)

        with open("docs/claude_eval_artifacts/tc03_counter.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and count_ok,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "sim_results": {
                "ready_at_9_is_false": ready_at_9 is False,
                "ready_at_10_is_true": ready_at_10 is True,
                "reset_clears_ready": ready_after_reset is False
            },
            "code_snippet": code[:400]
        }

    def test_tc04_traffic_lights(self):
        req = "交通號誌狀態機控制：使用 CASE 語法或狀態變數實作三態循環。State 0: 綠燈 green 亮 5 秒；State 1: 黃燈 yellow 亮 2 秒；State 2: 紅燈 red 亮 5 秒，隨後回到 State 0。若 emergency 信號為 TRUE，立即強制進入全紅燈模式（僅 red 為 TRUE，green 與 yellow 強制為 FALSE）。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        plc = VirtualPLC(code, scan_ms=1000)
        plc.set_input("emergency", False)
        plc.scan(1) # State 0 綠燈
        g0 = plc.get("green")
        
        # 測試緊急停止優先性
        plc.set_input("emergency", True)
        plc.scan(1)
        em_red = plc.get("red")
        em_green = plc.get("green")
        em_yellow = plc.get("yellow")
        emergency_ok = (em_red is True) and (em_green is False) and (em_yellow is False)

        with open("docs/claude_eval_artifacts/tc04_traffic.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and (g0 is True) and emergency_ok,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "sim_results": {
                "initial_green": g0 is True,
                "emergency_all_red_override": emergency_ok
            },
            "code_snippet": code[:400]
        }

    def test_tc05_tag_binding(self):
        csv_tags = """name,type,direction,init,comment
emergency_stop,BOOL,IN,false,現場急停開關
high_level_sw,BOOL,IN,false,水槽高水位浮球
low_level_sw,BOOL,IN,false,水槽低水位浮球
inlet_valve,BOOL,OUT,false,進水電磁閥
drain_pump,BOOL,OUT,false,排水泵浦
alarm_lamp,BOOL,OUT,false,水位警報燈
fill_time,TIME,VAR,T#0s,進水累計時間"""
        
        req = "水槽自動給排水控制：嚴格遵照點位表。低水位 low_level_sw 觸發且未高水位時打開進水閥 inlet_valve 補水；當高水位 high_level_sw 觸發時關閉進水閥並啟動排水泵 drain_pump；若 emergency_stop 為 TRUE，則關閉進水閥與排水泵，並點亮 alarm_lamp。"
        var_text = tags_to_var_blocks(csv_tags)
        code, issues, rounds = generate_checked(self.provider, req, tags_text=var_text, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        # 檢驗宣告是否包含點位表所有名稱
        all_tags = ["emergency_stop", "high_level_sw", "low_level_sw", "inlet_valve", "drain_pump", "alarm_lamp", "fill_time"]
        tags_declared = all(t in code for t in all_tags)

        # 虛擬 PLC 測試
        plc = VirtualPLC(code, scan_ms=100)
        plc.set_input("emergency_stop", False)
        plc.set_input("low_level_sw", True)
        plc.set_input("high_level_sw", False)
        plc.scan(1)
        valve_on = plc.get("inlet_valve")
        
        plc.set_input("emergency_stop", True)
        plc.scan(1)
        em_alarm = plc.get("alarm_lamp")
        em_valve = plc.get("inlet_valve")
        em_ok = (em_alarm is True) and (em_valve is False)

        with open("docs/claude_eval_artifacts/tc05_tank.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and tags_declared and (valve_on is True) and em_ok,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "all_tags_declared": tags_declared,
            "sim_results": {
                "inlet_valve_on_low_level": valve_on is True,
                "emergency_safe_shutdown": em_ok
            },
            "code_snippet": code[:400]
        }

    def test_tc06_rag_generation(self):
        # 建立專用知識庫片段
        spec_text = """# 企業自訂標準: 5點滑動平均濾波規範
在類比量處理中，為避免雜訊干擾，一律使用 ARRAY[0..4] OF REAL 儲存最近 5 次取樣值。
變數規範：
- raw_in : REAL 輸入原始值
- filter_out : REAL 濾波後輸出
- buf : ARRAY[0..4] OF REAL 緩衝區
- idx : INT 索引 (0..4)
演算法：每次掃描將 raw_in 寫入 buf[idx]，計算 5 點總和除以 5.0，並更新 idx := (idx + 1) MOD 5。"""
        
        store = VectorStore()
        store.add_text("custom_filter_spec.md", spec_text)
        req = "依據企業標準實作類比輸入的 5 點滑動平均濾波程式。"
        ctx = store.context(req, k=2)
        
        code, issues, rounds = generate_checked(self.provider, req, context=ctx, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        # 檢驗是否採納 RAG 中的 ARRAY 與 MOD 5 或 5.0
        used_array = "ARRAY" in code and "5" in code
        used_filter = "filter_out" in code or "buf" in code

        plc = VirtualPLC(code, scan_ms=50)
        plc.set_input("raw_in", 10.0)
        plc.scan(5)
        out_val = plc.get("filter_out")
        filter_ok = (out_val is not None) and (out_val > 0)

        with open("docs/claude_eval_artifacts/tc06_rag_filter.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and used_array and filter_ok,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "rag_context_injected": len(ctx) > 0,
            "used_rag_spec": used_array and used_filter,
            "sim_output": out_val,
            "code_snippet": code[:400]
        }

    def test_tc07_siemens_profile(self):
        req = "西門子 S7-1200 溫控系統：類比輸入 temp_pv (REAL)，設定值 temp_sp (REAL)。若 temp_pv < temp_sp - 2.0 則開啟加熱器 heater (BOOL)；若 temp_pv > temp_sp + 2.0 則關閉 heater 並啟動冷卻器 cooler (BOOL)。"
        code, issues, rounds = generate_checked(self.provider, req, vendor="siemens-s7-1200", max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)
        has_lint_warn = any("64-bit" in i.msg for i in issues)

        plc = VirtualPLC(code, scan_ms=100, profile="siemens-s7-1200")
        plc.set_input("temp_sp", 50.0)
        plc.set_input("temp_pv", 40.0) # < 48 -> heater on
        plc.scan(1)
        h_on = plc.get("heater")

        plc.set_input("temp_pv", 60.0) # > 52 -> cooler on, heater off
        plc.scan(1)
        c_on = plc.get("cooler")
        h_off = not plc.get("heater")

        with open("docs/claude_eval_artifacts/tc07_siemens.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and (not has_lint_warn) and h_on and c_on and h_off,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "sim_results": {
                "heater_on_when_cold": h_on,
                "cooler_on_when_hot": c_on,
                "heater_off_when_hot": h_off
            },
            "code_snippet": code[:400]
        }

    def test_tc08_rockwell_profile(self):
        req = "Rockwell ControlLogix 輸送帶控制：按 start 啟動輸送帶 conveyor，按 stop 停止。具備光電開關 item_trigger 累計產量 item_count (DINT)。"
        code, issues, rounds = generate_checked(self.provider, req, vendor="rockwell", max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        plc = VirtualPLC(code, scan_ms=50, profile="rockwell")
        plc.set_input("start", True)
        plc.set_input("stop", False)
        plc.scan(1)
        conv_on = plc.get("conveyor")

        with open("docs/claude_eval_artifacts/tc08_rockwell.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and conv_on,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "code_snippet": code[:400]
        }

    def test_tc09_plcopen_xsd(self):
        # 針對典型 ST 代碼匯出 PLCopen XML 並進行 TC6 XML v2.01 官方 Schema 驗證
        req = "雙馬達順序啟動：按下 start 後馬達 motor1 先啟動，延遲 3 秒後馬達 motor2 啟動。按下 stop 時兩台馬達立即停止。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        xml_content = export(code, "plcopen")
        validate_plcopen(xml_content) # 若不符合 XSD 會拋出 STError

        with open("docs/claude_eval_artifacts/tc09_export.xml", "w", encoding="utf-8") as f:
            f.write(xml_content)

        return {
            "passed": (not has_error) and (len(xml_content) > 200),
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "xml_length": len(xml_content),
            "tc6_xsd_validated": True,
            "code_snippet": code[:300]
        }

    def test_tc10_multivendor_export(self):
        # 測試將生成的程式碼匯出至 5 大平台格式
        req = "經典水泵啟停：start, stop, pump, run_hours (INT)。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        formats = ["plcopen", "scl", "l5x", "gxworks", "sysmac", "st"]
        exports = {}
        for fmt in formats:
            out = export(code, fmt)
            exports[fmt] = len(out) > 0
            with open(f"docs/claude_eval_artifacts/tc10_export.{fmt}", "w", encoding="utf-8") as f:
                f.write(out)

        all_ok = all(exports.values())
        return {
            "passed": all_ok,
            "formats_exported": exports,
            "rounds": rounds,
            "code_snippet": code[:300]
        }

    def test_tc11_scenario_auto_repair(self):
        # 使用情境腳本驅動閉環驗證與自動修復
        scenario = {
            "scan_ms": 100,
            "steps": [
                {"name": "initial_idle", "cycles": 2, "expect": {"alarm": False, "siren": False}},
                {"name": "fire_detected", "set": {"fire_sensor": True}, "cycles": 1, "expect": {"alarm": True}},
                {"name": "siren_delay", "ms": 500, "expect": {"siren": True}},
                {"name": "reset_alarm", "set": {"fire_sensor": False, "ack_btn": True}, "cycles": 1, "expect": {"alarm": False, "siren": False}}
            ]
        }
        scenario_json = json.dumps(scenario)
        req = "火警警報系統：當火警感測器 fire_sensor 觸發時，立即輸出 alarm := TRUE；若火警持續超過 400ms，啟動蜂鳴器 siren := TRUE；當火警解除且按下確認按鈕 ack_btn 時，alarm 與 siren 皆復歸為 FALSE。"
        code, issues, rounds = generate_checked(self.provider, req, scenario=scenario_json, max_rounds=3)
        has_error = any(i.severity == "error" for i in issues)

        fails = run_scenario(code, scenario_json)
        scenario_pass = len(fails) == 0

        with open("docs/claude_eval_artifacts/tc11_scenario.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and scenario_pass,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "scenario_failures": fails,
            "code_snippet": code[:400]
        }

    def test_tc12_overflow_guard(self):
        req = "高速產量計數器：感測器 pulse (BOOL) 上升緣時，累加總產量 total_count (INT)。要求具備防溢位保護（避免 INT 超過 32767 產生負數），當到達 32767 時保持在上限不再累加；按下 clear 時歸零。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        plc = VirtualPLC(code, scan_ms=10)
        # 測試設為 32767 後再觸發 pulse
        plc.vars["total_count"] = 32767
        plc.set_input("pulse", True)
        plc.scan(1)
        val = plc.get("total_count")
        overflow_safe = (val == 32767)

        with open("docs/claude_eval_artifacts/tc12_overflow.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and overflow_safe,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "overflow_safe_val": val,
            "code_snippet": code[:400]
        }

    def test_tc13_ambiguity_safety(self):
        # 需求刻意含糊：未定義 stop 優先性與預設時間
        req = "風機啟停：按鈕 run_cmd 與 stop_cmd 同時控制 fan_out。若兩個按鈕同時被按下，必須優先保護設備安全。"
        code, issues, rounds = generate_checked(self.provider, req, max_rounds=2)
        has_error = any(i.severity == "error" for i in issues)

        has_comment = "(*" in code or "//" in code
        
        plc = VirtualPLC(code, scan_ms=50)
        plc.set_input("run_cmd", True)
        plc.set_input("stop_cmd", True)
        plc.scan(1)
        fan_state = plc.get("fan_out")
        safety_stop_priority = (fan_state is False)

        with open("docs/claude_eval_artifacts/tc13_safety.st", "w", encoding="utf-8") as f:
            f.write(code)

        return {
            "passed": (not has_error) and safety_stop_priority and has_comment,
            "rounds": rounds,
            "issues": [str(i) for i in issues],
            "safety_stop_priority": safety_stop_priority,
            "has_engineering_assumptions": has_comment,
            "code_snippet": code[:400]
        }

    def test_tc14_web_api(self):
        state = State()
        payload = {
            "provider": "claude",
            "requirement": "冷卻水塔啟停：start 啟動 pump，stop 停止。",
            "tags_csv": "",
            "profile": "iec",
            "max_rounds": 2
        }
        status, resp = handle("POST", "/api/generate", payload, state)
        api_ok = (status == 200) and ("code" in resp) and ("issues" in resp)
        code = resp.get("code", "")
        has_program = "PROGRAM" in code and "END_PROGRAM" in code

        return {
            "passed": api_ok and has_program,
            "http_status": status,
            "issues": resp.get("issues", []),
            "rounds": resp.get("rounds", 0),
            "code_length": len(code)
        }

if __name__ == "__main__":
    runner = ClaudeTestRunner()
    results = runner.run_all()

