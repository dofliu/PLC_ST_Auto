# M26 測試報告(STRUCT → Siemens SCL UDT 匯出)
日期:2026-11-07

## 單元測試
`python -m unittest discover -s tests` → 154 項通過(6 項因缺 lxml/PDF 環境略過,與前次相同)。新增 `tests/test_scl_struct.py` 5 項:
- `TYPE ... STRUCT` → SCL `TYPE "Name" ... STRUCT ... END_STRUCT; END_TYPE`,置於 `ORGANIZATION_BLOCK` 之前
- 變數宣告 / ARRAY OF / 巢狀欄位中的 STRUCT 型別名稱加雙引號(`"Motor"`)
- 無 TYPE 的程式輸出不變;自訂 FUNCTION/FUNCTION_BLOCK 匯出 SCL 仍明確報錯
- 更新 `test_struct.py`、`test_struct_export.py`:scl 不再拒絕 STRUCT,l5x/gxworks/sysmac 仍拒絕

## UI 實測
Web UI(Node Playwright + Chromium):載入 `examples/struct_export.st`,選 Siemens SCL 匯出,下載 `program.scl` 含 `TYPE "Motor"` 與 `OF "Motor"`,無 JS 錯誤。截圖:`docs/screenshots/web_ui_sclstruct_M26.png`

## 已知限制
- L5X UDT、GX Works3、Sysmac 的 STRUCT 匯出,以及自訂 POU 的 PLCopen/SCL 匯出尚未支援。
- SCL 內 TIA 的資料型別大小寫(`Int`)與區域變數 `#` 前綴未轉換,需於 TIA 匯入時人工確認。
