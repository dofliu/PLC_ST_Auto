# M28 測試報告(STRUCT 內含 ARRAY 欄位)
日期:2026-11-08

## 單元測試
`python -m unittest discover -s tests` → 173 項通過(6 項因缺 lxml/PDF 環境略過,與前次相同)。新增 `tests/test_struct_arrfield.py` 12 項:
- 解析:`f : ARRAY[lo..hi(, lo..hi)] OF T := [..]` 欄位(一維/多維、初始值)
- 解譯:預設值與部分初始值、FOR 迴圈讀寫 `r.buf[i]`、多維 `r.m[2,1]`、巢狀 `o.r.buf[2]`
- STRUCT 整體賦值深拷貝陣列欄位(複製後改原件不影響副本)
- 執行期越界、未加索引、初始值過多皆明確報錯;`ARRAY OF STRUCT`(STRUCT 含陣列欄位)明確拒絕
- 快照/CSV 欄名 `a.buf[2]`;檢查器:越界、索引數不符、非陣列加索引、型別不符、未加索引
- PLCopen XML 與 L5X 匯出仍可產生(匯出器原已支援陣列欄位)

## UI 實測
Web UI(Node Playwright + Chromium):載入 `examples/struct_arrfield.st`,靜態檢查「無問題」,虛擬 PLC 執行 80 週期並繪圖,無 JS 錯誤。截圖:`docs/screenshots/web_ui_structarrfield_M28.png`

## 已知限制
- `ARRAY OF STRUCT` 且 STRUCT 含 ARRAY 欄位、以及 STRUCT 欄位為 `ARRAY OF STRUCT` 尚不支援(明確報錯)。
- Logix L5X 多維陣列欄位仍不可匯出(Logix UDT 限制)。
