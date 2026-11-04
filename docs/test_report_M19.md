# M19 測試報告(STRUCT / TYPE)
日期:2026-11-04

## 單元測試
`python -m unittest discover -s tests` → 121 項全部 OK(新增 `tests/test_struct.py` 9 項)。
- `TYPE x : STRUCT ... END_STRUCT END_TYPE` 解析、欄位預設值、巢狀 STRUCT、初始化 `(a := 1, m := (speed := 7))`。
- 欄位讀寫、`set_input("a.speed")`、snapshot/trace 輸出 `l.m.speed` 形式。
- 檢查器:未知欄位、型別不符、整個 STRUCT 賦值/未帶成員使用皆報錯;profile 型別限制(mitsubishi 無 LINT)。
- 非 st 匯出遇 TYPE 明確拒絕(僅 `--format st`)。

## CLI / UI 實測
- `check examples/struct.st` 無問題;`run --cycles 2` 輸出 a.speed=50、a.run=True、l.m.speed 8→9、l.count 53→103。
- Web UI(Node Playwright + Chromium):載入 `examples/struct.st` → 靜態檢查、執行 80 週期,頁面無 JS 錯誤。截圖:`docs/screenshots/web_ui_struct_M19.png`
- `tests/ui_smoke.py` 本次未重跑(環境無 Python playwright)。

## 已知限制
- STRUCT 內不可含 ARRAY、無 STRUCT 陣列、無整個 STRUCT 賦值(需逐欄位);PLCopen/SCL 等匯出尚未輸出 dataType。
