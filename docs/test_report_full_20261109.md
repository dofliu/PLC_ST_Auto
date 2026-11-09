# 全專案測試報告
日期:2026-11-09 基準:main `01761b7`(M29 合併後) 環境:Python 3、lxml 6.1.3、Chromium + Node Playwright

## 總結

| 層級 | 範圍 | 結果 |
|---|---|---|
| 單元測試 | 26 個測試檔,`python -m unittest discover -s tests` | **204 / 204 通過**,0 略過(含本次新增 2 項) |
| CLI 矩陣 | 11 個範例 × check / run / 6 種匯出 / TC6 XSD 驗證 | 全部可執行;無任何未處理例外(⛔ 皆為設計上明確拒絕) |
| 廠牌 profile | 9 個 profile × motor.st check + run | 9/9 正常 |
| 情境測試 / 點位表 | `test motor.st motor_scenario.json`、`tags points.csv` | PASS / 正確產生 VAR 宣告 |
| 邊界探索 | 26 個執行期案例(溢位、除 0、無窮迴圈、型別、FB…) | 22 符合預期,**4 個發現**(F1–F4) |
| Web API | 13 個異常輸入(壞 JSON、缺欄位、超大週期、路徑穿越…) | 全部回 4xx JSON 錯誤,無 500、無路徑穿越 |
| Web UI 端到端 | `tests/ui_e2e.js`,24 項 | **24 / 24 通過**(修正前 20/22,見「本次已修正」) |

整體而言，產生 → 檢查 → 虛擬 PLC → 情境驗證 → 匯出整條流程穩定。本次修正 2 個 UI 問題。另有 4 個執行期/語法問題與 2 項尚未驗證的部分（見下），建議排入後續里程碑。

## 1. 單元測試(204 項)

| 模組 | 測試檔(項數) |
|---|---|
| 解譯器核心 | interpreter 10、array 7、multidim 4、userpou 8、inout 3 |
| STRUCT | struct 9、struct_copy 4、struct_array 6、struct_elem 5、struct_arrfield 12 |
| 靜態檢查 / 方言 | checker 8、dialect 12、profiles 3 |
| 匯出 | export 8、plcopen_schema 5、struct_export 6、scl_struct 5、l5x_struct 7、review_m29 29 |
| LLM / RAG | llm 13(transport 注入,未連真實 API)、rag 8、embed 5、docreader 4 |
| 其他 | scenario 5、cli 4、web 14 |

lxml 已安裝,過去因缺 lxml 略過的 6 項 PLCopen TC6 XSD 測試本次全部執行並通過。

## 2. CLI 矩陣

| 範例 | check | run 20 週期 | plcopen | scl | l5x | gxworks | sysmac | st | TC6 XSD |
|---|---|---|---|---|---|---|---|---|---|
| inout.st | ✅ | ✅ | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | ✅ | — |
| matrix.st | ✅ | ✅ | ✅ | ✅ | ⛔ | ✅ | ✅ | ✅ | ✅ |
| motor.st | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| review_m29.st | ✅ | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ✅ | ✅ |
| struct.st | ✅ | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ✅ | ✅ |
| struct_array.st | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ⛔ | ✅ | ✅ |
| struct_arrfield.st | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ⛔ | ✅ | ✅ |
| struct_copy.st | ✅ | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ✅ | ✅ |
| struct_elem.st | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ⛔ | ✅ | ✅ |
| struct_export.st | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ⛔ | ✅ | ✅ |
| struct_l5x.st | ✅ | ✅ | ✅ | ✅ | ✅ | ⛔ | ⛔ | ✅ | ✅ |

⛔ 皆為明確錯誤訊息,依原因分三類:
- **自訂 FUNCTION/FB(inout.st)**:僅 `st` 格式可匯出。
- **GX Works3 / Sysmac 遇 STRUCT**:尚未支援(9 個範例中有 8 個因此無法匯出到這兩個廠牌)。
- **L5X**:陣列下界非 0(`ARRAY[1..n]`,5 例)或 UDT 多維陣列成員(1 例),Logix 本身限制。

**profile**:iec / codesys / siemens-s7-1200 / siemens-s7-1500 / rockwell(2 個方言警告) / mitsubishi / omron / strict / saturate 全部 check rc=0、run rc=0。

## 3. 邊界探索(執行期)

符合預期:INT 溢位(wrap → -32768、saturate → 32767、strict → 報錯)、SINT -128/-1、整數與實數除以 0 報錯、`-7 MOD 3 = -1`、WHILE 無窮迴圈與 FOR 步長 0 有保護、FOR 到 INT 上限不會繞回、TIME 運算、UINT 0-1 → 65535、LINT 在 S7-1200 / TIME 在 Rockwell 被拒、TON / R_TRIG 行為、未知函式、語法錯誤附行號、非法字元。

**發現(尚未修正)**

| # | 嚴重度 | 現象 | 說明 / 建議 |
|---|---|---|---|
| F1 | 中 | `EXIT;` 寫在迴圈外:檢查器不報錯,執行時靜默跳過本週期後續所有陳述式 | IEC 規定 EXIT 只能在迴圈內;建議檢查器報 error,解譯器拋 STError |
| F2 | 中 | 字串跳脫字元 `$'`、`$$`、`$N`、`$T` 不支援,`'it$'s'` 直接語法錯誤 | 合法 IEC 程式會被拒,LLM 產生的程式也常用 `$N`;需擴充 lexer 並轉換 |
| F3 | 低-中 | `REAL_TO_INT(2.5)=2`(銀行家捨入)、`REAL_TO_INT(2.7)=3`,但隱式 `x := 2.7` 得 2(截斷) | 兩種轉換結果不一致;捨入方式各廠牌不同,建議依 profile 定義並在文件說明。檢查器對隱式轉換已有 warning |
| F4 | 低 | 巢狀註解 `(* a (* b *) c *)` 不支援 | IEC 不要求;CODESYS 可選支援。可列為 profile 選項 |

## 4. Web API 健全性
13 個異常請求全部得到 4xx 與 JSON 錯誤:非 JSON / JSON 陣列 → 400;缺 `code` / `requirement` → 400;`cycles` = 1e9 或 -5 → 400(上限 5000);未知匯出格式 → 400 並列出可用格式;`GET /../../etc/passwd` → 404;未知端點 → 404。
小瑕疵:`cycles: "abc"` 的錯誤訊息直接露出 Python `ValueError: invalid literal for int()…`,建議改成友善訊息。

## 5. Web UI 端到端(24/24)
腳本:`tests/ui_e2e.js`(Node Playwright;啟動 `python -m plc_st serve` 後執行)。截圖:`docs/screenshots/full_test_20261109/`。

| # | 項目 | 結果 |
|---|---|---|
| 01 | 頁面載入、9 個 profile | ✅ |
| 02 | 點位表 CSV → VAR 宣告 | ✅ |
| 03 | LLM 產生(無本機 Ollama / 無 key)顯示錯誤而非當機 | ✅ |
| 04 | RAG 上傳文件並檢索 | ✅ |
| 05–06 | 靜態檢查:抓到未宣告變數 / motor.st 無問題 | ✅ |
| 07 | 匯出 PLCopen、SCL、L5X、GX Works3、Sysmac 下載內容正確 | ✅ ×5 |
| 08–09 | 虛擬 PLC 80 週期、波形繪製 | ✅ |
| 10–11 | 情境測試 PASS,以及故意寫錯的預期能判 FAIL | ✅ |
| 12 | 切換 profile:iec 繞回、strict 報溢位、saturate 截頂;錯誤後再成功狀態顏色恢復 | ✅ ×4 |
| 13 | 進階範例 struct_arrfield / review_m29 / matrix 在 UI 執行 | ✅ ×3 |
| 14 | 手機寬度 390px 無水平捲動 | ✅(修正後) |
| 15 | 全程無 JS 錯誤 | ✅ |

截圖:`00_full_page.png`(全頁)、`01_input.png`、`02_llm.png`、`03_rag.png`、`04_check_error.png`、`05_vplc.png`(motor 波形)、`06_scenario_fail.png`、`07_mobile.png`。

### 本次已修正(皆附回歸測試 `tests/test_web.py::UiLayout`)
1. **手機版水平捲動 42px**:`main` 的格線寫死 `minmax(420px,1fr)`,窄於 420px 的螢幕會被撐開。改為 `minmax(min(420px,100%),1fr)`。
2. **執行狀態顏色殘留**:虛擬 PLC 執行出錯後狀態變紅,下一次成功仍維持紅色(只改了文字沒清 class)。成功時改為重設 class。

## 6. 未涵蓋 / 待驗證
- **LLM 真實呼叫 (已於 2026-11-09 評測完成 ✅)**:使用 Claude API (`claude-sonnet-5-5`) 執行 14 項專屬測試案例(涵蓋基礎工控、點位表約束、RAG 增強、方言檢查、TC6 XSD 驗證、多廠牌匯出、情境閉環與防溢位),**14/14 通過 (100%)**,詳細報告見 `docs/test_report_claude_st_generation.md`。Gemini / OpenAI / Ollama 仍以注入 transport 的單元測試為主。
- **實機匯入**:PLCopen 已通過 TC6 XSD;L5X、SCL、GX Works3、Sysmac 匯出都**未**在 Studio 5000 / TIA Portal / GX Works3 / Sysmac Studio 實機匯入。L5X 多維 `Dimensions` 分隔符(空白或逗號)仍待確認(見 M29)。
- **RAG**:只測 TF-IDF 與 hash embedder;OpenAI / Ollama / Gemini embedder 只有 mock 測試。
- **已知 UI 問題**:訊號很多時波形左側標籤重疊,STRING 訊號顯示 NaN。

## 建議後續工作(各 ≤ 2 小時)
1. F1 EXIT 位置檢查 + F2 字串 `$` 跳脫字元(影響 LLM 產生程式的相容性,優先)
2. F3 依 profile 定義 REAL→INT 捨入規則並統一隱式/顯式轉換
3. GX Works3 / Sysmac 的 STRUCT 匯出(目前 9 個範例中有 8 個無法匯出到這兩個廠牌)
4. 波形圖標籤重疊與 STRING 顯示
5. API `cycles` 型別錯誤訊息友善化
