# M27 測試報告(STRUCT → Rockwell L5X UDT 匯出)
日期:2026-11-08

## 單元測試
`python -m unittest discover -s tests` → 161 項通過(6 項因缺 lxml/PDF 環境略過,與前次相同)。新增 `tests/test_l5x_struct.py` 7 項:
- `TYPE ... STRUCT` → `<Controller><DataTypes><DataType Class="User">`,置於 `<Programs>` 之前,XML 可解析
- BOOL 欄位依 Logix 慣例打包進隱藏 SINT 主機成員(`ZZZZZZZZZZ<Type>0`,`DataType="BIT"` + `Target`/`BitNumber`)
- 一維 ARRAY 成員 `Dimension="N"`、巢狀 STRUCT 以型別名引用;標籤陣列輸出 `Dimensions="N"`(原本誤寫成 `DataType="ARRAY[..] OF .."`)
- 下界非 0 或多維成員明確報錯;無 TYPE 時不輸出 `<DataTypes>`;自訂 FUNCTION 仍拒絕
- 更新 `test_struct.py`、`test_struct_export.py`:l5x 不再拒絕 STRUCT,gxworks/sysmac 仍拒絕

## UI 實測
Web UI(Node Playwright + Chromium):載入 `examples/struct_l5x.st`,執行虛擬 PLC,選 Rockwell L5X 匯出,下載 `program.L5X` 含 `<DataType Name="Motor"` 與 `Dimensions="3"`,無 JS 錯誤。截圖:`docs/screenshots/web_ui_l5xstruct_M27.png`

## 已知限制
- 未以 Studio 5000 實機匯入驗證;L5X 無官方公開 XSD 可驗證,僅檢查結構與慣例。
- STRUCT 欄位初始值在 UDT 無對應(Logix 預設值在 Tag 的 Data 區),目前省略;單一 UDT 的 BOOL 欄位上限 8。
- GX Works3、Sysmac 的 STRUCT 匯出與自訂 POU 的 PLCopen/SCL 匯出尚未支援。
- 解析器尚不支援 STRUCT 內含 ARRAY 欄位(匯出器已預備)。
