# M35 測試報告:自訂 FUNCTION_BLOCK → Rockwell L5X Add-On Instruction

日期:2026-11-19(排程自動執行)

## 範圍
- `plc_st/export.py`:`_l5x_fbinfo`、`_l5x_instances`、`_l5x_fbcalls`、`_l5x_aoi`;`to_l5x` 輸出 `<AddOnInstructionDefinitions>`(位於 `<DataTypes>` 之後、`<Programs>` 之前)。
- 匯出閘門:L5X 只拒絕含 `FUNCTION` 的程式(訊息建議改寫為 FUNCTION_BLOCK);只含 FUNCTION_BLOCK 可以匯出。
- 範例 `examples/aoi_l5x.st`(Latch、內含巢狀 Latch 與 VAR_IN_OUT 的 Accum、Main)。

## 對映規則
| IEC | Logix AOI |
|---|---|
| VAR_INPUT(基本型別純量) | `Parameter Usage="Input" Required="false"`,初值 → `DefaultData` |
| VAR_OUTPUT(基本型別純量) | `Parameter Usage="Output"`(Read Only) |
| VAR_IN_OUT | `Parameter Usage="InOut" Required="true"`(可為陣列/UDT/TIMER) |
| VAR / VAR CONSTANT / VAR_TEMP | `LocalTag`(常數附 Description;VAR_TEMP 在 Logic 開頭重新指派) |
| `inst(a := x, b, q => y);` | `inst.a := x; inst.<第2個輸入> := b; FB(inst, <InOut…>); y := inst.q;` |

明確報錯:Input/Output 為陣列/STRING/STRUCT/計時器、參數名 EnableIn/EnableOut、FB 實例陣列、FB 內 AT 位址、
缺 VAR_IN_OUT 引數、輸出用 `:=`、未知參數、呼叫出現在運算式中。

## 測試結果
| 項目 | 結果 |
|---|---|
| `tests/test_aoi_l5x.py`(定義/參數/LocalTags/巢狀呼叫/位置引數/IF·CASE/字串註解/錯誤 11 種) | 25/25 PASS |
| 全部單元測試 `python -m unittest discover -s tests` | 383 PASS(9 skipped:環境無 lxml,TC6 XSD 驗證略過) |
| UI `tests/ui_m35.js` | 9/9 PASS |
| UI 回歸 `tests/ui_e2e.js` / `tests/ui_m34.js` | 130/130、18/18 PASS |

## 截圖(`docs/screenshots/m35/`)
- `01_check_rockwell.png`:Rockwell profile 檢查,僅 R_TRIG → OSRI 方言提示
- `02_sim_fb_instances.png`:虛擬 PLC 執行 FB 實例(sum=90、pool=140)
- `03_export_l5x_preview.png`:L5X 卡片可匯出,預覽顯示 AddOnInstructionDefinition
- `04_export_function_reason.png`:含 FUNCTION 時 L5X 卡片顯示不支援原因

## 限制 / 待辦
- 尚未以 Studio 5000 實機匯入確認(DefaultData 格式、InOut Radix、AOI 版本屬性)。
- AOI 內的 IEC 標準 FB(R_TRIG/TON…)與程式本體相同,仍需依方言警告改為 OSRI/TONR 等。
- 虛擬 PLC 尚不支援把整個陣列傳給 VAR_IN_OUT(另列待辦)。
