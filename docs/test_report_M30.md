# M30 測試報告(LLM 評測工具整合、Logix 方言訊息、計時器邊緣時序)
日期:2026-11-09 基準:main `9bd2209`(含使用者上傳的 Claude 評測)

## 1. Rockwell 方言訊息修正
`dialect.py` 對所有 IEC FB 都建議「TONR/CTU」,對 R_TRIG / F_TRIG 是錯的。改為逐一對應 Logix ST 指令:
TON→TONR、TOF→TOFR、CTU/CTD/CTUD→CTUD、R_TRIG→OSRI、F_TRIG→OSFI、TP / RS / SR 給出替代寫法。
回歸測試:`tests/test_dialect.py::LogixEquivalents`(3 項,涵蓋全部 10 個 FB)。

## 2. 評測工具整合:`python -m plc_st eval`
`run_claude_eval.py` 整合為 `plc_st/llm_eval.py`(根目錄腳本保留為相容入口)。

**新增功能**
- `--model` 可重複 → 多模型對照;`--repeat N` → 每案重複;`--cases` 選案例;`--price` 估費用
- 每一輪的錯誤都記錄(`rounds_log`),可區分「一次正確」與「修正後正確」
- 計量 API 呼叫次數與輸入/輸出 token(Claude / OpenAI / Gemini / Ollama 回應格式)
- 輸出 `results_<model>.json`、各模型產出的 `.st`、對照報告 `report.md`(預設 `eval_out/`,已加入 .gitignore)
- 產生的程式在虛擬 PLC 無法執行(缺點位等)算 FAIL 並記錄原因,評測不中斷

**判定修正**(原腳本的漏洞)

| 案例 | 原判定 | 問題 | 新判定 |
|---|---|---|---|
| TC-09 | `tc6_xsd_validated: True` 寫死 | `validate_plcopen()` 回傳錯誤清單、不丟例外,結果被忽略 | 錯誤清單須為空;另驗證順序啟動行為 |
| TC-10 | 只看檔案非空 | 未看靜態檢查錯誤 | 加上最終無 error;匯出例外記錄原因 |
| TC-02 | 兩個時間點檢查互鎖 | 中間週期重疊抓不到 | 100ms 掃描、8 秒內每週期檢查互鎖;星形約 5 秒斷開;三角形不早於星形斷開;stop 全斷 |
| TC-04 | 初始綠燈 + 緊急全紅 | 未驗證時序 | 15 秒內每週期恰一燈;順序 綠→黃→紅→綠;綠/紅約 5 秒、黃約 2 秒 |
| TC-06 | 輸出 > 0 | 幾乎任何程式都過 | 穩態 10.0、混合窗 14.0、穩態 20.0 |
| TC-08 | 輸送帶有啟動 | 未驗證計數與停止 | 自保持、3 個工件計數 = 3、stop 停止 |
| TC-12 | 32767 再 +1 | 以 wrap profile 執行 | 改用 strict profile(任何溢位直接報錯);計數正確、上限、clear 歸零 |
| TC-05 | 名稱字串出現在程式中 | 註解中出現也算 | 以實際宣告比對;加上「未寫入輸入點」與高水位排水 |
| TC-03 | 感測器 1 週期脈衝 | 用電位觸發也會過 | 每次脈衝持續 3 週期,只有上升緣計數才會剛好 10 |

**工具本身的測試** `tests/test_llm_eval.py`(12 項,不需 API 金鑰):
- 14 個案例以參考解(其中 12 個是 2026-11-09 Sonnet 實際產出)全部 PASS:確認判定是「可被正確程式滿足」的
- 刻意改壞的程式會被對應檢查抓到(TC-02 互鎖、TC-04 黃燈時間、TC-06 除數、TC-09 XSD、TC-10 檢查錯誤、TC-12 溢位、缺點位)
- 自動修正:第 0 輪錯誤被記錄、第 1 輪通過 → `rounds=1`、`first_try=False`
- token 計量、費用估算、`report.md` 內容、輸出檔案、CLI 參數錯誤與無金鑰的錯誤訊息

## 3. 虛擬 PLC 計時器提早一個掃描週期觸發(重要)
**發現經過**:以新判定重跑 TC-02 存檔程式碼時,星形斷開與三角形吸合發生在同一週期,但程式碼明明有 100ms 死區計時器。

**原因**:TON / TOF / TP 在邊緣那次呼叫就先累加了一個掃描週期(`el += dt`),IEC 語意是邊緣那次 ET = 0。結果是所有計時器都提早一個掃描週期觸發;PT ≤ 掃描週期時延時完全消失。這讓模擬可能「看起來安全」但實際不是,例如死區、防彈跳、最小導通時間。

**修正**:三個計時器都在邊緣那次 ET = 0,之後每次呼叫才累加。
- 既有測試只有 1 項(`test_interpreter.test_timers_counters_edges`)寫死了舊行為(PT 50ms / 掃描 10ms 在第 5 次呼叫觸發),已更正為第 6 次並加註
- 新增 `tests/test_timer_edge.py` 7 項:短 PT 不再瞬間觸發、PT=0 立即、精確觸發時刻、重新啟動歸零、TOF 下降緣、TP 脈寬、星三角死區可見
- `examples/motor_scenario.json` 與所有範例仍正常;以存檔程式碼重跑 TC-02:星形 5100ms 斷開、三角形 5200ms 吸合(報表時間為掃描結束時刻)

## 測試結果
- `python -m unittest discover -s tests` → **226 項全部通過**(含新增 22 項)
- 以新判定重跑使用者 2026-11-09 Sonnet 存檔程式碼(固定回應):12 / 12 PASS

## 未完成:Haiku / Sonnet 實際對照
本雲端環境沒有 `ANTHROPIC_API_KEY`,無法實際呼叫 API。工具已完成並以模擬 API 驗證;請於本機執行:
```
python -m plc_st eval --provider claude --model claude-haiku-5-5 --model claude-sonnet-5-5 --repeat 3
```
或把金鑰設成雲端環境變數後由排程執行。產出 `eval_out/<時間>/report.md` 即為對照報告。
