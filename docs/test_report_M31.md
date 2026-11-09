# M31 測試報告:檢查器補合法 IEC 語法 + 評測保存每輪程式碼

日期:2026-11-09

## 變更
- lexer:型別前綴常數(`INT#5` `REAL#1.5` `BOOL#1` `BOOL#TRUE` `DINT#-3`)、進位常數(`16#FF` `8#17` `2#1010`)、底線分隔(`1_000`、`1_0.5`)。
- 標準轉換函式:自動產生所有整數型別、REAL/LREAL、BOOL、TIME 之間的 `*_TO_*`(含 `*_TO_TIME`、`TIME_TO_*`、`*_TO_STRING`);整數轉換依目標型別環繞(wrap)。TIME 以毫秒整數表示。
- 陣列重複初值:`[5(0.0)]`、`[2(1), 3(0)]`。
- `llm_eval`:`rounds_log` 每輪保存 `code`;輸出資料夾除最終 `.st` 外另存 `<case>_roundN.st`;案例以 STError 失敗時仍保存最後一輪程式碼。

## 測試
- 新增 `tests/test_m31.py`(4 項):字面量/轉換/重複初值執行結果、lexer token、轉換函式存在、評測保存各輪程式碼。
- 全專案:`PYTHONPATH=. python -m unittest discover -s tests` → 230 項,1 項失敗(`test_llm_eval` TC-09 `tc6_xsd_valid`,**M31 之前即存在**,與本次無關,待查 XSD 檢查),7 skip。
- UI e2e(`tests/ui_e2e.js`):24/24 PASS。
- 截圖:`docs/screenshots/web_ui_literals_M31.png`(範例 `examples/literals_m31.st` 於虛擬 PLC 執行 80 週期)。

## 未完成/觀察
- 以 2026-11-09 評測的原始錯誤訊息建立的回歸以 `test_m31` 的語法案例涵蓋;實際 LLM 重跑需 API 金鑰(環境無)。
- 既有失敗 `tc6_xsd_valid` 列入 M32 一併調查。
