# M34 測試報告:VAR CONSTANT / RETAIN / VAR_TEMP 與直接位址 AT %I/%Q/%M

日期:2026-11-16(排程執行)

## 為什麼做
M33 報告列出的既有問題:`VAR CONSTANT` / `VAR RETAIN` 匯出時修飾詞被併入第一個變數名稱(例 `name="CONSTANT n"`)。
追查後發現範圍更大:
- 解譯器把 `CONSTANT` / `RETAIN` 直接略過(常數可以被寫入,檢查器也不報錯)。
- `VAR_TEMP` 與 `x AT %IX0.0 : BOOL` 會直接語法錯誤,而這是實機程式與 LLM 產生程式最常見的寫法。
- 點位表沒有位址欄,產生的程式無法對應實體 I/O。

## 本次內容
| 範圍 | 變更 |
|---|---|
| 語法 | `VAR CONSTANT`、`VAR RETAIN`、`PERSISTENT`、`NON_RETAIN`、`VAR_TEMP`;`name AT %IX0.0 : BOOL`(%I/%Q/%M,X/B/W/D/L,省略大小字首視為位元)。本體直接寫 `%IX0.0` 會提示改用宣告 |
| 虛擬 PLC | 寫入 CONSTANT(含陣列元素)執行期報錯,也不能強制;`VAR_TEMP` 每個掃描週期(FB 為每次呼叫)重新初始化;`%I` 變數視為輸入、`%Q` 視為輸出;`restart(warm)` 模擬斷電再上電,RETAIN(含 STRUCT、FB 實例)保留 |
| 靜態檢查 | 寫入 CONSTANT(指派、FOR 迴圈變數、`=>` 輸出)為 error;CONSTANT 無初值 warning;型別與位址大小不符 error;位址重疊 warning(Siemens 以 byte 定址、IEC/CODESYS 以大小定址,結果不同);FB/FUNCTION 內或 VAR_TEMP 帶位址提示 |
| 廠牌方言 | Siemens:`%IX0.0` → `%I0.0`、位址屬於 PLC 變數表;Rockwell / Mitsubishi / Omron:無 IEC 直接位址與 `VAR_TEMP` 的對應做法;`PERSISTENT` 為 CODESYS 擴充 |
| 匯出 | 修飾詞不再併入變數名稱。PLCopen:`constant` / `retain` / `persistent` 屬性、`<tempVars>`、`address`(TC6 XSD 通過)。SCL:位址變數移出區塊、檔頭列出 PLC 變數表、本體引用加雙引號(FB 具名參數不動),`PERSISTENT`→`RETAIN`,VAR_TEMP 初值移到本體開頭。L5X:`Constant="true"`、純量字面量初值寫入 `<Data>`、位址寫入 Description。GX Works3:`VAR_CONSTANT` / `VAR_RETAIN` 類別、IEC 位址欄。Sysmac:Retain / Constant / 位址欄。所有格式:引用 `VAR CONSTANT` 的陣列邊界展開為數字 |
| 點位表 | 新欄位 `address`(選用),direction 新增 `CONST` / `RETAIN`;方向與位址不一致、位址格式錯誤逐列報錯 |
| 情境 | 步驟可加 `"restart": "warm" \| "cold"` |
| Web UI | 模擬頁顯示位址 / CONST / RETAIN 標籤、「斷電重啟」按鈕;點位預覽多位址欄;情境表格標示重啟步驟 |
| LLM prompt | 要求實體 I/O 以 `AT` 宣告、固定值用 `VAR CONSTANT`、需保持的值用 `VAR RETAIN` |

範例:`examples/qualifiers_m34.st`、`examples/qualifiers_m34_scenario.json`、`examples/points_addr.csv`。

## 測試結果
| 項目 | 結果 |
|---|---|
| 單元測試 `python -m unittest discover -s tests` | **340 項 OK、0 略過**(原 295;新增 `tests/test_m34.py` 45 項;本次安裝 lxml,XSD 測試全部實際執行) |
| PLCopen TC6 v2.01 XSD | 範例與 `RETAIN PERSISTENT` / `NON_RETAIN` 程式皆通過 |
| 情境 `python -m plc_st test examples/qualifiers_m34.st examples/qualifiers_m34_scenario.json` | PASS(7 步、含暖/冷啟動) |
| 既有 Web UI E2E `tests/ui_e2e.js` | **130/130 PASS**(無回歸) |
| M34 Web UI `tests/ui_m34.js` | **18/18 PASS** |
| 全部 `examples/*.st` 靜態檢查 | 無 error |

M34 UI 項目:01–03 點位表位址預覽 / 轉 VAR / 錯誤標示;04–06 檢查(範例無問題、寫常數與位址大小不符、Siemens 方言);
07–10 模擬(%I 開關、%Q 燈號、標籤、3 次上升緣計數、斷電重啟保留 total=3 且 batch 歸 0、重設歸 0);
11–12 情境含 restart 7/7;13–17 六種格式可匯出與內容;18 無 JS 錯誤。

測試過程備註:M34-08/09 第一次執行失敗,原因是測試腳本切換開關後沒有按「單步」(暫停狀態下開關只會排入待送出值),屬腳本錯誤,修正腳本後通過;產品行為未改。

## 截圖(`docs/screenshots/m34/`)
- `01_tags_address.png`:點位表含位址 / 常數 / 保持的預覽與產生的宣告
- `02_check_errors.png`:寫入 CONSTANT、位址大小不符
- `03_dialect_siemens.png`:Siemens 方言提示
- `04_sim_before_power_cycle.png`、`05_sim_after_power_cycle.png`:斷電重啟前後(total 保留、batch 歸零)
- `06_scenario_restart.png`:含暖/冷啟動的情境 7/7
- `07_export_scl_preview.png`:SCL 預覽的 PLC 變數表

## 限制與未驗證
- **未在任何廠牌 IDE 實機匯入**。特別需要確認:
  - TIA Portal:OB 內的 `VAR CONSTANT` / `VAR RETAIN` 區段是否接受(OB 通常只有 Temp 與 Constant);SCL 檔頭的 PLC 變數表只是註解,需手動建立變數。
  - Studio 5000:`<Data Format="Decorated">` 初值與 `Constant="true"` 的匯入結果。這次起純量字面量初值會寫入標籤(以前一律不寫,匯入後為 0)。
- 虛擬 PLC **不模擬位址共用記憶體**:兩個變數位址重疊時只給警告,值各自獨立。
- 位址重疊檢查不計入陣列長度(只算單一元素大小)。
- 不支援 `VAR_GLOBAL` / `VAR_EXTERNAL`、本體內直接使用 `%IX0.0`、未完整指定位址 `AT %I*`。
- GX Works3 / Sysmac 不換算裝置編號(MELSEC 的 X/Y 為 8 或 16 進位,無法可靠換算),只列出 IEC 位址供人工指定。
- L5X 常數若不是純量字面量(例 `2 + 3`)會拒絕匯出並說明原因。
- 雲端環境仍無 LLM 金鑰,prompt 的新規則未以真實模型驗證。

---

# M34b:審查意見修正(2026-11-16)

五項審查意見全部重現後修正,回歸測試在 `tests/test_m34_review.py`(18 項)。

| # | 問題(修正前實測) | 修正 |
|---|---|---|
| 1 | **FB 內的 RETAIN 在暖重啟後遺失**:FB 內 `VAR RETAIN keep`,實例宣告在一般 `VAR`;掃描 3 次 → 暖重啟 → 再掃 1 次,得到 1(應為 4) | `restart()` 對非 RETAIN 的自訂 FB 實例往內遞迴(含巢狀 FB),只保留內部宣告為 RETAIN 的變數,其餘回初值;冷啟動仍全部清除 |
| 2 | **SCL 匯出靜默改變字串內容**,兩種情況:(a) `m2 : STRING := 'VAR END_VAR'` 被輸出成 `''`(清除空區段的規則直接套在原文);(b) `'it$'s start now'` 內的 `start` 被加上雙引號(遮罩不認得 `$'` 跳脫,字串提早結束) | 字串遮罩支援 IEC `$` 跳脫;新增 `_sub_code()`,改寫只在程式碼上比對,區間內有字串或註解就不動;UDT 型別加引號(`: Rec` → `: "Rec"`)原本也會改到字串 `'x: Rec'`,一併修正;初值逗號切分同樣認得 `$'` |
| 3 | **VAR_TEMP 陣列**:(a) `VAR_TEMP s : ARRAY[0..1] OF S`(STRUCT 陣列)第二個掃描週期起執行期當機 `TypeError`;(b) 匯出時暫存陣列無初值只加註解、有初值直接拒絕,匯出後行為與虛擬 PLC 不一致 | (a) 重新初始化前先清掉舊鍵;(b) 基本型別陣列(≤64 元素,含多維、`n(v)` 重複初值、常數邊界)在本體開頭逐元素指派,各格式一致;結構或更大的陣列維持「無初值加提醒、有初值報錯」;FC 區域陣列套用同一規則 |
| 4 | **L5X 初值範圍**:`INT := 70000`、`UINT := 60000`(對映 INT)、`USINT := 200`(對映 SINT)、`TIME := T#30d`(DINT 毫秒溢位)、`REAL := 1e39` 都原樣寫入 `<Data>` | 依 Logix 目標型別檢查範圍,超出時拒絕匯出並說明原型別與對映(例「原型別 UINT 對映為 INT」);REAL 檢查單精度範圍 |
| 5 | **常數回寫**:常數傳給 `VAR_IN_OUT`(函式或 FB)、函式 `=>` 輸出接到常數,檢查器不報錯,執行期才失敗;`FOR K := …`(K 為常數)執行期可以改到常數 | 檢查器對 VAR_IN_OUT 引數(具名與位置)、函式 `=>` 輸出報 `write to CONSTANT`;FOR 迴圈變數加執行期保護;常數當一般輸入不受影響 |

## 測試結果
| 項目 | 結果 |
|---|---|
| 單元測試 | **358 項 OK、0 略過**(340 + 新增 18) |
| `tests/ui_e2e.js` / `tests/ui_m34.js` | 130/130、18/18 |
| 全部 `examples/*.st` 的 SCL / L5X / GX Works3 / Sysmac 匯出,修正前後比對 | 完全相同(修正只影響上述邊界情況) |

既有測試調整 1 項:`test_pou_export` 原本斷言「FC 區域陣列帶初值一律拒絕」,改為斷言小陣列逐元素展開、大陣列才拒絕。

## 行為變更(需留意)
- L5X:過去能匯出但數值超出範圍的程式,現在會被拒絕並說明原因。
- 暫存陣列:匯出的本體開頭會多出逐元素指派(最多 64 行)。

## 仍未處理
- 遮罩不處理雙引號 WSTRING(`"..."`),lexer 本身也不支援。
- `_scl_calls` 改寫函式呼叫時,引數內的註解仍會被移除(M33 既有限制)。
- 靜態檢查不檢查初值是否超出 IEC 宣告型別範圍;L5X 的範圍檢查只在匯出時進行。
- 以上修正同樣未經實機 IDE 驗證。
