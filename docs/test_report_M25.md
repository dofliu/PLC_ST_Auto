# M25 測試報告(STRUCT → PLCopen dataType 匯出)
日期:2026-11-07

## 單元測試
`python -m unittest discover -s tests` → 149 項(新增 `tests/test_struct_export.py` 6 項;修正 `tests/test_struct.py` 預期:plcopen 現已支援 STRUCT,scl/l5x/gxworks/sysmac 仍明確拒絕)。
使用裝有 lxml 的 `/usr/bin/python3`:`test_struct_export` + `test_plcopen_schema` 全數通過,STRUCT 輸出**通過 TC6 v2.01 XSD 驗證**。
- `TYPE ... STRUCT` → `<dataTypes><dataType><baseType><struct>`;欄位含巢狀 STRUCT(`<derived>`)、ARRAY(`<array>`)、欄位初始值(`<structValue>` / `<arrayValue>`)。
- 程式變數 `ARRAY OF STRUCT` 初始值 → `<arrayValue><value><structValue>`。
- 自訂 FUNCTION/FUNCTION_BLOCK 匯出 plcopen 仍明確報錯。

## UI / CLI 實測
- Web UI(Node Playwright + Chromium):載入 `examples/struct_export.st` → 匯出 PLCopen XML,下載內容含 `<struct>`、`<structValue>`,無 JS 錯誤。截圖:`docs/screenshots/web_ui_structexport_M25.png`
- CLI `export examples/struct_export.st --format plcopen --validate` 通過 schema 驗證。

## 已知限制 / 環境註記
- 其他格式(SCL/L5X/GX Works3/Sysmac)的 STRUCT 與自訂 POU 匯出、PLCopen 自訂 POU 匯出尚未支援。
- 預設 `python`(3.11)無 lxml,schema 測試略過;`test_docreader` 的 PDF 測試在系統 python 的 pypdf 下失敗(既有問題,與本次無關)。
