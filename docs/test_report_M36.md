# M36 測試報告:整個陣列傳入 VAR_IN_OUT / VAR_INPUT、陣列整體賦值、初值範圍檢查

日期:2026-11-20(排程自動執行)

## 範圍
- `plc_st/interpreter.py`:`_whole_array`、`_copy_array_in`、`_array_copy`;`call_function` / `call_fb` 對陣列參數改為複製進入,
  VAR_IN_OUT 呼叫結束後整個陣列寫回(依目標型別 wrap、CONSTANT 保護)。`dst := src` 陣列整體賦值(深拷貝)。
- `plc_st/checker.py`:陣列參數須傳入整個陣列變數(或 STRUCT 的陣列欄位),元素型別相同、每一維長度相同
  (下界可不同;邊界可用 VAR CONSTANT);陣列整體賦值同規則;ARRAY OF STRUCT 整體傳遞/賦值明確報「尚未支援」。
- 新靜態檢查:整數型別初值超出範圍(`SINT := 300`、`USINT := -1`、陣列初值每個元素、STRUCT 欄位預設值),先前只有 L5X 匯出時才會發現。
- `plc_st/export.py`:L5X 匯出把 `dst := src;`(兩邊皆為陣列)改寫為 Logix `COP(src[0], dst[0], n);`(程式與 AOI 內皆適用,型別/大小不同時報錯)。
- 範例 `examples/array_inout.st`:FUNCTION(VAR_IN_OUT 陣列求和並加倍)、FUNCTION_BLOCK 移位暫存器、FUNCTION 以 VAR_INPUT 陣列取最大值。

## 測試結果
| 項目 | 結果 |
|---|---|
| `tests/test_m36.py`(執行 11、檢查 10、初值範圍 5、匯出 5) | 31/31 PASS(含 TC6 XSD 驗證) |
| 全部單元測試 `python3.13 -m unittest discover -s tests`(有 lxml) | 414 PASS |
| 全部單元測試 `python3 -m unittest discover -s tests`(無 lxml) | 414 PASS(10 skipped) |
| UI `tests/ui_m36.js` | 9/9 PASS |
| UI 回歸 `tests/ui_e2e.js` / `ui_m34.js` / `ui_m35.js` | 130/130、18/18、9/9 PASS |
| `examples/*.st` 靜態檢查 | 無新增錯誤(無誤報) |

調整既有測試:`test_review_m29.test_checker_flags_unindexed_write` 的訊息改為更精確的
「cannot assign whole array buf; use buf[i] (or assign an array of the same shape)」,斷言改為接受 `whole array`。

## 截圖(`docs/screenshots/m36/`)
- `01_check_ok.png`:範例靜態檢查無問題
- `02_sim_array_inout.png`:sample 輸入 5→12→3,hist = 3,12,5(FB 陣列 VAR_IN_OUT 移位)、snap 整體複製、peak = 12
- `03_export_l5x_cop.png`:L5X 預覽 `ShiftReg(sh, hist);`、`COP(hist[0], snap[0], 5);`
- `04_check_errors.png`:陣列大小不符(`[6] does not match [5]`)與初值 300 超出 SINT 的錯誤

## 限制 / 待辦
- ARRAY OF STRUCT 整體傳遞/賦值、`ARRAY[*]` 可變長度參數尚未支援。
- FB 的 VAR_OUTPUT 陣列以 `x := fb.arr` 整體讀出尚未支援(可用 `fb.arr[i]`)。
- 待實機:Studio 5000 確認 COP 改寫與 AOI 陣列 InOut。
