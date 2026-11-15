# M33 測試報告:自訂 FUNCTION / FUNCTION_BLOCK 匯出(2026-11-15)

原本含自訂 POU 的程式只能以純 ST 匯出。本次讓 PLCopen XML 與 Siemens SCL 也能匯出,範例 `examples/userpou_export.st`。

## 變更(`plc_st/export.py`)
- `split_pous()`:依原始順序切出 FUNCTION(含回傳型別)/ FUNCTION_BLOCK / PROGRAM;註解與字串內的關鍵字不誤判;必須恰有一個 PROGRAM。
- **PLCopen XML**:每個 POU 一個 `<pou>`,`pouType` 為 `function` / `functionBlock` / `program`;function 的 `<returnType>` 置於 interface 最前;FB 實例型別為 `<derived name="…"/>`;只有 PROGRAM 掛到 task。
- **Siemens SCL**:`FUNCTION "F" : T`(FC)、`FUNCTION_BLOCK "B"`、`ORGANIZATION_BLOCK "P"`,依原始順序輸出。
  - 自訂函式呼叫改為 TIA 語法:名稱加雙引號、位置引數補成具名(`Scale(a, 200.0)` → `"Scale"(raw := a, hi := 200.0)`),支援巢狀呼叫;字串、註解、`inst.F(…)` 成員呼叫不改寫;引數過多或括號不成對會報錯。
  - FC 沒有靜態區:區域 `VAR` 改為 `VAR_TEMP`,初值(未給則為零值)移到本體開頭指派,行為與虛擬 PLC 一致;陣列/結構 Temp 帶初值會報錯,未帶初值則加註解提醒。
  - FB 實例宣告型別加引號(`l1 : "Latch"`),標準 FB(`R_TRIG` 等)不加。
- **其他格式**:L5X 改為明確說明「Logix 須以 Add-On Instruction 實作,尚未支援」;GX Works3 / Sysmac 維持不支援。

## 測試結果
| 項目 | 結果 |
|---|---|
| 單元測試 `python -m unittest discover -s tests` | **295 項 OK**(原 274;新增 `tests/test_pou_export.py` 21 項;本次環境已裝 lxml,原本略過的 7 項 XSD 測試也實際執行) |
| PLCopen TC6 v2.01 XSD(`export --format plcopen --validate`) | `schema: OK` |
| 範例在虛擬 PLC 執行(start=1、level_raw=50,2 週期) | level=100.0、duty=50、pump=TRUE、starts=1,符合預期 |
| Web UI E2E `tests/ui_e2e.js` | **130/130 PASS**(原 124 + M33 6 項) |

新增 E2E 項目:84 卡片狀態(PLCopen/SCL/ST 可匯出,其餘三種不支援)、85 L5X 原因與下載停用、86 SCL 預覽內容、87 下載 PLCopen(4 個 pou、returnType)、88 下載 SCL、89 PLCopen 預覽。

既有測試調整:3 個原本斷言「plcopen / scl 拒絕自訂 FUNCTION」的測試改為斷言可匯出(`test_struct_export`、`test_scl_struct`、`test_userpou`)。

## 截圖(`docs/screenshots/m33/`)
- `export_cards_userpou.png`:匯出卡片與 SCL 預覽
- `scl_preview.png`、`plcopen_preview.png`:預覽內容
- `dark_export_userpou.png`:暗色主題

## 限制與未驗證
- **未在 TIA Portal / CODESYS 實機匯入**:XML 只通過 XSD 驗證;SCL 的 FC 區域變數未加 `#` 前綴(預期匯入時自動補上)、OB 內的 `VAR_INPUT` 區段為既有行為,都待實機確認。
- 型別名稱未轉成 TIA 慣用大小寫(`REAL` 而非 `Real`),TIA 不分大小寫。
- 函式呼叫引數內的註解在改寫時會被移除。
- 發現既有問題(未修,列入 todo):`VAR CONSTANT` / `VAR RETAIN` 區段匯出時修飾詞會併入第一個變數名稱(例 `name="CONSTANT n"`),所有格式都受影響。
- 雲端環境仍無 LLM 金鑰,真實 provider 未實測。
