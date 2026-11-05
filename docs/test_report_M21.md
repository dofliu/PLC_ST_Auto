# M21 測試報告(多維陣列)
日期:2026-11-05

## 單元測試
`python -m unittest discover -s tests` → 128 項 OK(新增 `tests/test_multidim.py` 4 項,5 項因無 Python playwright 略過)。
- `ARRAY[1..2, 0..2] OF INT` 宣告、列優先(row-major)初始值、`m[i, j]` 讀寫(亦支援 `m[i][j]`)。
- 越界(執行期/靜態)、索引個數不符(靜態)、外部 `set_input("m[1,1]")`、snapshot 欄名 `m[1,2]`。
- PLCopen XML 匯出多個 `<dimension>`。

## CLI / UI 實測
- `check examples/matrix.st` 無問題;`run --cycles 2`:total 21,m[2,3] 7→8。
- Web UI(Node Playwright + Chromium):載入 matrix.st → 靜態檢查「無問題」、執行 80 週期,無 JS 錯誤。截圖:`docs/screenshots/web_ui_multidim_M21.png`
- `tests/ui_smoke.py` 未重跑(無 Python playwright);PLCopen XSD 驗證因無法安裝 lxml 未執行。

## 已知限制
- 陣列整體賦值、STRUCT 陣列、自訂 POU 的 PLCopen/SCL 匯出仍未支援。
