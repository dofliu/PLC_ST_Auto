# M23 測試報告(ARRAY OF STRUCT)
日期:2026-11-06

## 單元測試
`python -m unittest discover -s tests` → 138 項 OK(新增 `tests/test_struct_array.py` 6 項,5 項因無 Python playwright 略過)。
- `ms : ARRAY[1..3] OF Motor`,`ms[i].speed` 讀寫、FOR 迴圈、元素互相獨立、欄位預設值生效。
- 越界索引(執行期)報錯;檢查器對不存在欄位報錯;ARRAY OF STRUCT 初始值明確報不支援。
- 外部 `get/set_input("ms[2].speed")` 與 trace/snapshot 欄名 `ms[2].speed`。

## CLI / UI 實測
- `run examples/struct_array.st --cycles 2`:total 36 → 42,ms[2].speed 12 → 14。
- Web UI(Node Playwright + Chromium):載入範例 → 檢查「無問題」、執行 3 週期,無 JS 錯誤。截圖:`docs/screenshots/web_ui_structarray_M23.png`

## 實作
內部以「每個欄位一個陣列」(`ms.speed`)儲存,`a[i].f` 對應該陣列的第 i 元素(支援巢狀 STRUCT 欄位)。

## 已知限制
- 整個元素賦值 `ms[1] := x`、ARRAY OF STRUCT 初始值、STRUCT 內含 ARRAY、PLCopen dataType 匯出仍未支援。
