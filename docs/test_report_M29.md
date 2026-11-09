# M29 測試報告(PR #31 / #32 審查意見修正)
日期:2026-11-09 基準:main `fc5a6de`

每項先寫測試在修正前的程式上重現(`git stash` 原始碼後執行 `tests/test_review_m29.py`:17 failures、13 errors),修正後全數通過。

| # | 來源 | 問題 | 重現結果(修正前) | 修正 | 回歸測試 |
|---|---|---|---|---|---|
| 1 | #31 | 第 8 個 BOOL 被拒絕 | 8 個 BOOL → `STError 超過 8 個` | 改為「放入下一個 bit 前」檢查容量,第 9 個才拒絕 | `L5xBoolHost`(7 / 8 / 9 個) |
| 2 | #31 | 多維 Tag `Dimensions` 分隔符 | 輸出 `Dimensions="2 3"` | **未變更**,見下方說明 | `L5xDimensions`(鎖住現況) |
| 3 | #31 | 陣列邊界運算式被部分比對 | `ARRAY[0..2+1]` → `Dimensions="3"`(執行期為 4);PLCopen 變成 `<derived name="ARRAY…">` | 新增 `_const_int`:用專案 Parser 完整解析整數常數運算式(+ - * / MOD、括號、負號);含變數/實數/語法錯誤/除以 0/上界<下界一律明確報錯。L5X Tag、L5X UDT 成員、PLCopen 共用 `_array_type` | `ArrayBoundExpressions` |
| 4 | #31 | 字串內容被當註解或分號 | `'http://host'` 讓整個 UDT 消失;`'a;b'` → `STError` | 新增 `_views`:產生同長度的「去註解」與「遮蔽字串」兩份文字,結構判斷在遮蔽版上做、取值切原位置。套用於 `split_program`、PLCopen/SCL/L5X 的 STRUCT 解析及 `export()` 的 POU 偵測 | `StringLiterals`(L5X / PLCopen / SCL / 本體註解保留 / 虛擬 PLC) |
| 5 | #31 | 隱藏 BOOL host 撞名 | `ZZZZZZZZZZA0 : INT` 時輸出兩個同名成員 | 不分大小寫比對所有欄位名,遞增尾碼直到唯一 | `HiddenHostName` |
| 6 | #32 | 未加索引寫入陣列欄位 | `a.buf := 7` 把內部 list 換成整數(之後 snapshot 會崩) | `assign()` 對 STRUCT 陣列欄位**與一般陣列變數**(同樣問題,`x := 7`)皆拋 `STError`,狀態不變 | `UnindexedArrayWrite` |
| 7 | #32 | 實例的陣列初值無法解析 | `a : R := (buf := [3,4])` → `unexpected token '['` | `init_value()` 統一支援 `[...]`,可任意巢狀;不合形狀的初值(純量給陣列、陣列給純量、過多元素)明確報錯 | `InstanceArrayInit`(覆寫、部分覆寫、巢狀、多實例獨立、檢查器、PLCopen 匯出) |

## 第 2 項說明(待實機確認)
審查意見依 Rockwell 1756-RM014 第 128 頁,認為 Tag 的 `Dimensions` 應以逗號分隔。我印象中 Studio 5000 匯出的 L5X 是 Tag 屬性用空白(`Dimensions="2 3"`)、`<Data>` 內 `<Array Dimensions="2,3">` 用逗號,但這點**未能查證**:本次執行環境無法連到 `literature.rockwellautomation.com` 與 L5Sharp 文件站(不在網路允許清單)。為避免在未查證下改成另一種可能也錯的格式,維持現況並以測試鎖住,程式中加註。**需要有 Studio 5000 的人用 `examples/review_m29.st` 匯出的 L5X 實機匯入確認**,若應為逗號,只需改 `to_l5x` 中一行與 `L5xDimensions` 測試。

## 測試結果
- `python -m unittest discover -s tests` → 202 項全部通過。本次安裝 lxml 後,原先略過的 6 項 TC6 XSD 測試也全數通過。
- 新增 `tests/test_review_m29.py` 29 項(含 TC6 XSD 驗證新輸出)。
- UI 實測(Node Playwright + Chromium,`examples/review_m29.st`):靜態檢查無問題、虛擬 PLC 80 週期、L5X 下載含 `BitNumber="7"`、`url` 成員、`buf Dimension="4"`、`hist Dimensions="5"`;PLCopen 保留字串與實例陣列初值;在 UI 加入 `a.buf := 7;` 時執行被拒絕(whole array);無 JS 錯誤。10/10 PASS。截圖:`docs/screenshots/web_ui_review_M29.png`

## 已知限制 / 觀察
- 所有 L5X 項目皆未以 Studio 5000 實機匯入驗證(本環境無 Studio 5000)。
- 陣列邊界若用 `VAR CONSTANT` 常數名稱,虛擬 PLC 可執行,但匯出會明確拒絕(尚未做常數展開)。
- 波形圖訊號很多時左側標籤會重疊,STRING 訊號顯示為 NaN(既有問題,非本次範圍)。
