# TODO

## 📌 排程備忘(每次排程先讀這裡)
- **2026-11-09 起使用者暫時無法在本機執行**:排程自行往下推進,只做不需要使用者的工作。
- 雲端環境目前**沒有** LLM API 金鑰(`ANTHROPIC_API_KEY` 等),無法實際呼叫 LLM;若某次排程偵測到金鑰已設定,
  就在 M31 完成後重跑 `python -m plc_st eval --provider claude --model claude-haiku-5-5 --model claude-sonnet-5-5 --repeat 3`,
  並與 `docs/eval_report_20261109_haiku_vs_sonnet.md` 比較。
- **暫緩(需要使用者)**:Haiku `unknown variable stop` 的 4 個 .st 檔;Studio 5000 / TIA Portal 等實機匯入確認。
- 建議順序:(M31–M40、UI1–UI8 已完成)→ 下一步候選(由上而下)。每次一個 ≤2h 里程碑,做完測試、截圖、報告、PR、合併、雲端紀錄。

## M40 ✅ 產生流程串流顯示(`docs/test_report_M40.md`)
- [x] `POST /api/generate/stream`(NDJSON:start / round / done / error),每輪完成即送出;用戶端斷線即停止呼叫 LLM
- [x] UI:進行中列(初稿產生中 / 第 n 輪修正中)、即時更新編輯器/錯誤標記/問題抽屜、「停止」按鈕、狀態列進度、舊伺服器自動退回 `/api/generate`
- [x] mock `demo-slow` 慢速模式;單元 10 項(`tests/test_m40.py`,含真實 HTTP 逐行到達)、E2E 19 項(`tests/ui_m40.js`)、截圖 `docs/screenshots/m40/`
## UI8 ✅ 寬螢幕(≥1600px)雙頁籤(`docs/test_report_UI8.md`)
- [x] 頂列「雙頁籤」按鈕、右欄選單/對調/關閉、導覽列虛線標示右欄、Shift+點 / Alt+Shift+1~6 指定右欄
- [x] 內部切頁不會換掉已在右欄的頁籤;右欄匯出/測試自動初始化;雙頁籤分欄另存(預設 34%);<1600px 自動退回
- [x] 單元 5 項(`tests/test_ui8.py`)、E2E 22 項(`tests/ui_ui8.js`)、截圖 `docs/screenshots/ui8/`
## M39 ✅ 點位表匯出依廠牌換算位址 + Studio 5000 ALIAS(`docs/test_report_M39.md`)
- [x] `convert_addr` iec⇄s7、`addressing` 選項(CLI/API/UI,UI 依 profile 自動)
- [x] TIA 輸出位元組定址並以換算後位元組自動配置(修正 M38 自動配置與 IEC word 位址重疊);GVL 輸出 word 編號
- [x] Studio 5000 `--logix-slots I=1,Q=2` → ALIAS `Local:槽:I.Data.n`;單元 16 項、UI 14 項、截圖 `docs/screenshots/m39/`
- [ ] **待實機**:Studio 5000 匯入 ALIAS 列、TIA 匯入換算後位址
## M38 ✅ 點位表 → 各廠牌標籤表匯出(`docs/test_report_M38.md`)
- [x] `plc_st/tagexport.py`:TIA xlsx(stdlib zip,PLC Tags + User Constants)、Studio 5000 標籤 CSV、GX Works3 全域標籤、Sysmac 全域變數、CODESYS GVL
- [x] TIA 自動配置位址(位元組定址、word 偶數對齊、RETAIN 先配置、避開已用位址);各格式型別替代與提醒清單
- [x] CLI `tags --format X -o`、API `/api/tags/export`(xlsx 以 base64)、UI 下拉 + 下載 + 提醒;單元 16 項、UI 10 項、截圖 `docs/screenshots/m38/`
- [ ] **待實機**:TIA Portal 匯入 xlsx、Studio 5000 Import Tags CSV、GX Works3 / Sysmac 貼上欄位順序確認
## M37 ✅ 虛擬 PLC 直接位址共用記憶體(`docs/test_report_M37.md`)
- [x] `plc_st/memory.py` process image:重疊位址變數共用位元組;IEC/CODESYS little-endian + 依大小定址,Siemens big-endian + byte 定址
- [x] 所有寫入路徑同步(指派、強制、FB `=>` 輸出、FOR 變數、初值、暖/冷重啟、RETAIN);REAL⇄DWORD、INT⇄UINT 別名
- [x] 檢查器:完全包含的別名不再警告,只有部分重疊(例 S7 `%MW0`/`%MW1`)警告
- [x] Web UI ⇄ 共用標記(tooltip 列出共用對象)、I/O 列名稱不再被位址標記擠掉;單元 17 項、UI 7 項、截圖 `docs/screenshots/m37/`
- [ ] **待實機**:CODESYS / TIA Portal 確認 %MX 與 %MW 位元對應
## M35 ✅ 自訂 FUNCTION_BLOCK → Rockwell L5X Add-On Instruction(`docs/test_report_M35.md`)
- [x] AOI 定義:EnableIn/EnableOut、Input/Output(基本型別純量,含預設值)、InOut(Required)、LocalTags(陣列/巢狀 AOI/常數)、VAR_TEMP 重新初始化
- [x] 呼叫改寫(程式與 AOI 內):具名/位置引數、`=>` 輸出、IF/CASE 內、字串/註解不動;不合法情況明確報錯
- [x] 匯出閘門:只含 FUNCTION_BLOCK 可匯出 L5X,含 FUNCTION 仍拒絕並建議改寫;單元 25 項、UI 9 項、截圖 `docs/screenshots/m35/`
- [ ] **待實機**:Studio 5000 匯入 AOI 定義(DefaultData 格式、InOut 的 Radix、AOI 內 R_TRIG 需改 OSRI)
## M34 ✅ VAR CONSTANT / RETAIN / VAR_TEMP 與直接位址 AT %I/%Q/%M(`docs/test_report_M34.md`)
- [x] 語法 + 虛擬 PLC:常數寫入保護、VAR_TEMP 每週期重新初始化、%I/%Q 變數作為輸入/輸出、斷電重啟(暖/冷)
- [x] 檢查器:寫入 CONSTANT、位址大小不符、位址重疊(依廠牌定址);方言:Siemens/Rockwell/Mitsubishi/Omron 位址與 VAR_TEMP 提示
- [x] 匯出:修飾詞不再併入變數名稱;PLCopen 屬性/address、SCL PLC 變數表、L5X Constant+初值、GX/Sysmac 欄位;常數陣列邊界展開
- [x] 點位表 `address` 欄與 CONST/RETAIN、情境 `restart`、UI 標籤與「斷電重啟」;單元 45 項、UI 18 項、截圖 `docs/screenshots/m34/`
- [x] M34b 審查修正:FB 內 RETAIN 暖重啟、SCL 不改字串、VAR_TEMP 陣列(當機修正 + 匯出逐元素指派)、L5X 初值範圍、常數回寫檢查(`tests/test_m34_review.py` 18 項)
- [ ] **待實機**:TIA OB 內 VAR CONSTANT/RETAIN、Studio 5000 `<Data>` 初值匯入
## M33 ✅ 自訂 FUNCTION / FUNCTION_BLOCK 匯出 PLCopen XML 與 Siemens SCL(`docs/test_report_M33.md`)
- [x] `split_pous()`:依序切出 FUNCTION / FUNCTION_BLOCK / PROGRAM(註解、字串內關鍵字不誤判)
- [x] PLCopen:`pouType=function|functionBlock|program`、`returnType`,TC6 XSD 驗證通過
- [x] SCL:FC / FB / OB、呼叫加引號 + 位置引數改具名、FC 區域變數改 VAR_TEMP 並補初值
- [x] L5X 明確說明需 AOI;單元 21 項、E2E 6 項、截圖 `docs/screenshots/m33/`
- [ ] **待實機**:TIA Portal 匯入 .scl 確認(FC 內未加 `#` 的區域變數、OB 的 VAR_INPUT 區段)
## M31 ✅ 檢查器補合法 IEC 語法 + 評測保存每輪程式碼(`docs/test_report_M31.md`)
- [x] lexer:型別前綴常數 `INT#5` `REAL#1.5` `BOOL#1`、進位常數 `16#FF` `8#17` `2#1010`、底線分隔 `1_000`
- [x] 標準轉換函式:`*_TO_TIME`、`TIME_TO_*`、其餘缺少的 `*_TO_*`(依 profile 型別)
- [x] 陣列重複初值 `[5(0.0)]`、`[2(1), 3(0)]`
- [x] `llm_eval`:`rounds_log` 保存每輪程式碼,輸出各輪 .st
- [x] 以 2026-11-09 的錯誤訊息建立回歸測試;報告 `docs/test_report_M31.md`
## M32 ✅ EXIT/字串跳脫/REAL→INT 捨入(`docs/test_report_M32.md`)
- [x] F1 EXIT 迴圈外 · [x] F2 `$` 跳脫 · [x] F3 捨入一致 + cycles 友善錯誤 · [x] TC-09 lxml 缺件改略過
## UI1 ✅ 100vh 外框/頁籤/狀態列/問題抽屜(`docs/test_report_UI1.md`)
## UI2 ✅ 設計 token、亮/暗主題切換、按鈕/卡片/SVG 圖示/toast、WCAG AA 對比(`docs/test_report_UI2.md`)
## UI3 ✅ 編輯器:行號、ST 語法色彩、自動檢查行標記、點問題跳行、快捷鍵;語法錯誤帶行號(`docs/test_report_UI3.md`);下一個 UI4(模擬儀表板),見 `docs/ui_redesign_plan.md`
## UI4 ✅ 模擬儀表板:執行/暫停/單步/重設、I/O 開關與燈號、波形軌道/STRING/縮放/游標、執行期錯誤行號(`docs/test_report_UI4.md`)
## UI6 ✅ 情境表格編輯器(表格⇄JSON、變數晶片、逐步 ✔/✘ 與實際值)+ 匯出卡片(可匯出/不支援原因/方言警告/預覽)(`docs/test_report_UI6.md`);下一個 UI5
## UI5 ✅ 產生流程時間軸、修正輪 diff/套用、點位表即時預覽、mock 離線 provider、情境驗證勾選(`docs/test_report_UI5.md`);下一個 UI7
## UI7 ✅ 可拖曳分欄、手機底部導覽、設定記憶(不含金鑰)、無障礙稽核、README 截圖(`docs/test_report_UI7.md`);UI 改版全部完成
## M1 ✅
- [x] lexer / parser / interpreter / FB 標準庫 / 測試
## M2 ✅
- [x] CLI: `python -m plc_st run file.st --cycles N --set x=1 --at C:x=1`
- [x] CSV 點位表 → VAR 宣告產生器 (`python -m plc_st tags points.csv`)
- [x] 每週期 trace 輸出(CSV)
## M3 ✅
- [x] vendor profile 抽象(`plc_st/profiles.py`):型別支援 + 溢位行為(wrap/saturate/fault)
- [x] CLI `--profile`、`profiles` 指令
## M4 ✅
- [x] 靜態檢查器 `plc_st/checker.py`:未宣告變數、型別不符、輸入變數被寫入、FB 成員/呼叫參數、profile 型別限制
- [x] CLI `python -m plc_st check file.st --profile X`(有 error 則 exit 1)
## M4b ✅
- [x] 廠牌方言警告 `plc_st/dialect.py`(保留字/與標準函式同名、MELSEC 裝置位址標籤、Logix 無 T#/**/IEC FB;僅 warning,已整合進 check)
## M5 ✅
- [x] `plc_st/llm.py`:Gemini/OpenAI/Claude/Ollama provider(stdlib HTTP、transport 可注入)、prompt 模板、ST 擷取
- [x] CLI `generate`(`--provider --model --base-url --tags -o`),產生後自動 `check`
## M6 ✅
- [x] `plc_st/rag.py`:切塊、TF-IDF(含 CJK bigram)向量庫、JSON 持久化
- [x] CLI `index` / `search`,`generate --index --top-k` 注入檢索片段
## M7 ✅
- [x] 產生→check→把錯誤回饋 LLM 自動修正迴圈(`generate --max-rounds N`,預設 3)
## M8 ✅
- [x] `plc_st/scenario.py` + CLI `test file.st scenario.json`(輸入時序 + 預期輸出,不符 exit 1)
## M9 ✅
- [x] `generate --scenario`:check 通過後以情境驗證,失敗回饋 LLM 修正
## M10 ✅
- [x] `plc_st/docreader.py`:docx(stdlib)、PDF(pypdf 或 stdlib 簡易解析)納入 RAG `index`
## M11 ✅
- [x] Web UI:`python -m plc_st serve`(stdlib http.server;需求/CSV/檔案輸入、LLM 設定、RAG 上傳、檢查、虛擬 PLC 波形、情境測試)
- [x] UI 功能測試 `tests/ui_smoke.py` + 截圖 + `docs/test_report_M11.md`
## M12 ✅
- [x] `plc_st/export.py`:PLCopen XML、Siemens SCL(.scl)、純 ST;CLI `export`、Web UI 匯出按鈕
- [x] 測試 `tests/test_export.py`、UI 匯出下載 + `docs/test_report_M12.md`
## M13 ✅
- [x] `plc_st/embed.py`:可替換 embedding(hash/OpenAI/Ollama/Gemini),`index --embedder`,索引保存 embedder 規格
- [x] Rockwell L5X 匯出(CLI + Web UI)、`docs/test_report_M13.md`
## M14 ✅
- [x] Mitsubishi GX Works3 匯出(CLI `export --format gxworks` + Web UI)
- [x] Web UI 提供 embedder 選項
## M15 ✅
- [x] Omron Sysmac Studio 匯出(CLI `--format sysmac` + Web UI)
- [x] README 匯出格式說明
## M6 修補 ✅
- [x] 切塊參數檢查(size>0、0<=overlap<size)、`index` 排除輸出檔、`add_path` 批次只重建一次索引
## M16 ✅
- [x] CTUD FB、ASIN/ACOS/ATAN、FLOOR/CEIL、SHL/SHR/ROL/ROR、LEN/CONCAT/LEFT/RIGHT
- [x] 測試與 `docs/test_report_M16.md`
## M17 ✅
- [x] `ARRAY[lo..hi] OF T` 一維陣列:宣告/初始值 `[1,2,3]`、索引讀寫、越界檢查(執行期+靜態)、CASE 範圍 `..` 詞法修正
- [x] PLCopen XML 匯出 `<array>`;測試 `tests/test_array.py`、`docs/test_report_M17.md`
## M18 ✅
- [x] 使用者自訂 `FUNCTION`(回傳值、RETURN、具名/位置參數)與 `FUNCTION_BLOCK`(實例狀態保存、`inst.out` 存取)
- [x] 靜態檢查涵蓋 POU 本體/呼叫參數;遞迴深度保護;非 st 格式匯出遇自訂 POU 明確報錯
- [x] 測試 `tests/test_userpou.py`、`docs/test_report_M18.md`
## M18b ✅ PLCopen XML 結構修正
- [x] 陣列初值改為 `<initialValue><arrayValue><value>…</value></arrayValue></initialValue>`
- [x] STRING 型別改為 TC6 規定的 `<string/>`(schema 驗證時發現)
- [x] `validate_plcopen()` + CLI `export --validate`;`tests/test_plcopen_schema.py` 以 TC6 XSD 驗證
## M19 ✅
- [x] `TYPE ... STRUCT` 巢狀結構、初始化、欄位存取(解譯/檢查);測試 `tests/test_struct.py`、`docs/test_report_M19.md`
## M20 ✅
- [x] `VAR_IN_OUT` 寫回(自訂 FUNCTION / FUNCTION_BLOCK;非變數引數明確報錯)、函式可作為陳述式呼叫
- [x] 檢查器支援 inout 作為呼叫參數;`tests/test_inout.py`、`examples/inout.st`、`docs/test_report_M20.md`
## M21 ✅
- [x] 多維陣列 `ARRAY[a..b, c..d]`(列優先、`m[i,j]`、檢查、PLCopen 多 dimension);`tests/test_multidim.py`、`examples/matrix.st`、`docs/test_report_M21.md`
## M22 ✅
- [x] STRUCT 整體賦值(含巢狀)、檢查器同型別驗證;`tests/test_struct_copy.py`、`examples/struct_copy.st`、`docs/test_report_M22.md`
## M23 ✅
- [x] `ARRAY OF STRUCT`(`a[i].f` 讀寫、檢查、外部存取);`tests/test_struct_array.py`、`examples/struct_array.st`、`docs/test_report_M23.md`
## M24 ✅
- [x] 陣列元素整體賦值 `ms[1] := x`、ARRAY OF STRUCT 初始值;`tests/test_struct_elem.py`、`examples/struct_elem.st`、`docs/test_report_M24.md`
## M25 ✅
- [x] STRUCT → PLCopen `dataType`(巢狀/ARRAY/初始值,TC6 XSD 驗證通過);`tests/test_struct_export.py`、`examples/struct_export.st`、`docs/test_report_M25.md`
## M26 ✅
- [x] STRUCT → Siemens SCL UDT(`TYPE "X"`)匯出、型別引用加引號;`tests/test_scl_struct.py`、`docs/test_report_M26.md`
## M27 ✅
- [x] STRUCT → Rockwell L5X UDT(DataType)匯出、標籤陣列 Dimensions;`tests/test_l5x_struct.py`、`examples/struct_l5x.st`、`docs/test_report_M27.md`
## M28 ✅
- [x] STRUCT 內含 ARRAY 欄位(一/多維、初始值、整體賦值深拷貝、檢查);`tests/test_struct_arrfield.py`、`examples/struct_arrfield.st`、`docs/test_report_M28.md`
## M29 ✅ PR #31/#32 審查修正
- [x] L5X:8 個 BOOL、邊界運算式完整解析、字串感知解析、隱藏 host 不撞名;執行期拒絕未索引陣列寫入;實例陣列初值
- [ ] **待實機**:Studio 5000 匯入確認多維 Tag `Dimensions` 分隔符(空白 vs 逗號)
## 全專案測試 2026-11-09 ✅
- [x] 204 單元測試、CLI 矩陣、API 健全性、UI E2E 24/24(`tests/ui_e2e.js`)、報告 `docs/test_report_full_20261109.md`
- [x] 修正:手機版水平捲動、執行狀態顏色殘留
- [x] 修復環境干擾:read_pdf fallback 支援 pypdf 異常轉 stdlib、OpenAIEmbedder 隔離環境變數測試
## Claude LLM 真實產生與全功能評測 2026-11-09 ✅
- [x] 14 項專屬評測案例 (`run_claude_eval.py`):工控原語、CSV 點位約束、RAG、方言、TC6 XSD、多廠牌匯出、情境閉環、邊界安全、Web API
- [x] 通過率 14/14 (100%),詳細評測報告與數據: `docs/test_report_claude_st_generation.md`、`docs/claude_eval_results.json`、`docs/claude_eval_artifacts/`
## M30 ✅ LLM 評測整合
- [x] `python -m plc_st eval`(多模型、重複、token、對照報告);修補原腳本判定漏洞(TC-09 XSD 結果被忽略等)
- [x] Rockwell 方言訊息:R_TRIG→OSRI 等逐一對應
- [x] 修正虛擬 PLC 計時器提早一個掃描週期觸發(TON/TOF/TP)
- [x] Haiku / Sonnet 對照已由使用者本機執行,結果與分析:`docs/eval_report_20261109_haiku_vs_sonnet.md`
## M36 ✅
- [x] 整個陣列傳入 VAR_IN_OUT / VAR_INPUT(解譯/檢查,形狀與型別檢查)、`a := b` 陣列整體賦值、L5X `COP` 改寫、初值超出型別範圍檢查;`tests/test_m36.py`、`tests/ui_m36.js`、`examples/array_inout.st`、`docs/test_report_M36.md`
- [ ] **待實機**:Studio 5000 確認 COP 改寫與 AOI 陣列 InOut
## UI 改版(規劃中,詳見 `docs/ui_redesign_plan.md`)
目標:一個畫面看完不用捲動、頁籤切換、重要資訊(檢查/模擬/情境/LLM 狀態)常駐、更有質感
- [x] UI1 100vh 外框 + 常駐狀態列 + 左側頁籤 + 程式碼常駐 + 底部問題抽屜(功能不變)
- [x] UI2 視覺系統:設計 token、亮/暗主題切換、元件、SVG 圖示、toast
- [x] UI3 程式碼編輯器:行號、ST 語法色彩、錯誤行標記、點擊跳行、快捷鍵
- [x] UI4 模擬儀表板:執行/暫停/單步、I/O 開關與燈號、波形改進
- [x] UI6 測試與匯出:情境表格編輯器、匯出卡片
- [x] UI5 產生流程時間軸、修正輪 diff、點位表預覽
- [x] UI7 響應式(手機底部導覽)、可拖曳分欄、設定記憶、無障礙、README 截圖
## 下一步候選(≤2h)
- [x] 寬螢幕(≥1600px)右側同時顯示兩個頁籤(例:模擬+測試)(UI8)
- [x] 產生流程串流顯示(每輪完成即更新時間軸)(M40)
- [x] 匯出時展開 VAR CONSTANT 陣列邊界(M34)
- [ ] ARRAY OF STRUCT 且 STRUCT 含 ARRAY 欄位
- [ ] GX Works3 / Sysmac STRUCT 匯出
- [x] 自訂 POU 的 PLCopen/SCL 匯出(M33)
- [x] 自訂 FUNCTION_BLOCK → Rockwell L5X Add-On Instruction(M35)
- [x] VAR_IN_OUT / VAR_INPUT 傳入整個陣列、陣列整體賦值、L5X COP 改寫(M36)
- [ ] 自訂 FUNCTION → L5X(提升為 AOI 並把運算式內呼叫拆成暫存實例)
- [x] 匯出支援 `VAR CONSTANT` / `RETAIN` 區段修飾詞(M34)
- [x] 靜態檢查:初值超出宣告型別範圍(M36)
- [ ] `VAR_GLOBAL` / `VAR_EXTERNAL`(多 POU 共用變數、GVL 匯出)
- [x] 虛擬 PLC 模擬位址共用記憶體(%MW0 與 %MX0.0 重疊時同步)(M37)
- [x] 點位表匯出為各廠牌可匯入格式(M38)
- [x] 點位表匯出時依廠牌換算 IEC 位址 word 編號並可選 Logix Alias 列(M39)
- [ ] GX Works3 點位表 IEC 位元位址 → X/Y 裝置(依機種選 8/16 進位)
- [ ] ARRAY OF STRUCT 整體傳遞/賦值、`ARRAY[*]` 可變長度 VAR_IN_OUT
- [ ] FB VAR_OUTPUT 陣列整體讀出 `x := fb.arr`
- [ ] LLM 回應 token 級串流(各 provider 的 stream API,邊產生邊顯示程式碼)
