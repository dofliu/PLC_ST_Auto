# M20 測試報告(VAR_IN_OUT 寫回)
日期:2026-11-04

## 單元測試
`python -m unittest discover -s tests` → 124 項 OK(新增 `tests/test_inout.py` 3 項,5 項因無 Python playwright 略過)。
- FUNCTION 具名/位置 `VAR_IN_OUT` 寫回變數與陣列元素;FUNCTION_BLOCK inout 寫回;常數引數報錯;檢查器無誤報。
- 函式可作為陳述式呼叫(`Bump(3, arr[1]);`),執行與靜態檢查皆支援。

## CLI / UI 實測
- `check examples/inout.st` 無問題;`run --cycles 3`:x 3→5→7、y 15→20→25。
- Web UI(Node Playwright + Chromium):載入 inout.st → 靜態檢查「無問題」、執行 80 週期,無 JS 錯誤。截圖:`docs/screenshots/web_ui_inout_M20.png`
- `tests/ui_smoke.py` 未重跑(無 Python playwright)。

## 已知限制
- inout 引數必須是變數/陣列元素/欄位;自訂 POU 仍僅 st 格式匯出。
