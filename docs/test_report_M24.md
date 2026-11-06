# M24 測試報告(ARRAY OF STRUCT 初始值、元素整體賦值)
日期:2026-11-06

## 單元測試
`python -m unittest discover -s tests` → 143 項 OK(新增 `tests/test_struct_elem.py` 5 項,5 項因無 Python playwright 略過)。
- `ms : ARRAY[1..3] OF Motor := [(speed := 100, run := TRUE), (speed := 200)]`:已給欄位生效、未給欄位用型別預設值、未給元素用預設。
- `tmp := ms[1]`、`ms[3] := ms[2]`、`ms[2] := tmp`(元素↔STRUCT 變數、元素↔元素);複製後互相獨立。
- 錯誤:未知欄位、初始值過多、元素初始值非 STRUCT 值、元素索引越界 → 明確報錯;檢查器對 `tmp := best`、`ms[1] := 3` 報 STRUCT 型別錯誤。

## CLI / UI 實測
- `run examples/struct_elem.st --cycles 1`:ms.speed = 100,100,200;best = 200;`check` 無問題。
- Web UI(Node Playwright + Chromium):載入範例 → 檢查「無問題」、執行 3 週期,無 JS 錯誤。截圖:`docs/screenshots/web_ui_structelem_M24.png`

## 已知限制
- STRUCT 內含 ARRAY、STRUCT/自訂 POU 的 PLCopen dataType 匯出仍未支援。
