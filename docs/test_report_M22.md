# M22 測試報告(STRUCT 整體賦值)
日期:2026-11-05

## 單元測試
`python -m unittest discover -s tests` → 132 項 OK(新增 `tests/test_struct_copy.py` 4 項,5 項因無 Python playwright 略過)。
- `b := a`、巢狀 `l.m := b`:欄位逐一複製,複製後互相獨立(非別名)。
- 檢查器:型別不同 / 非 STRUCT 賦值報「same type」錯誤;執行期型別不符丟 STError。
- 檢查器訊息去重(同行同訊息只報一次);`test_struct` 舊「whole STRUCT」訊息改為新訊息。

## CLI / UI 實測
- `check examples/struct_copy.st` 無問題;`run --cycles 2`:b.speed 50→51、l.count 1→2。
- Web UI(Node Playwright + Chromium):載入 struct_copy.st → 檢查、執行,無 JS 錯誤。截圖:`docs/screenshots/web_ui_structcopy_M22.png`

## 已知限制
- STRUCT 陣列、STRUCT 的 PLCopen dataType 匯出、自訂 POU 匯出仍未支援。
