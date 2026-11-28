# Roadmap(每個里程碑 ≤ 2 小時)

## 📌 v1.0 衝刺計畫(2026-11-28 起;每次排程先讀這裡,選下一個未完成項目,完成後打勾)
**凍結規則**:v1.0 前不做新的冷門語法特性(STRUCT 欄位為 ARRAY OF STRUCT、`ARRAY[*]`、外部讀取 `fb.arr[i]`、新匯出格式細節等),
一律放「v1.1 backlog」;只有題庫或交叉驗證實際需要時才做。發現的既有缺陷可當作當次項目修正。階段提早完成就直接進入下一階段。
**結案條件**:階段 D 完成並打 tag v1.0.0 → 寫 `docs/status_report_final.md`、標記「🏁 v1.0 結案」;或到 2026-12-12(台北時間)不論進度只做收尾並標記「🏁 結案」;
或連續 3 次排程因外部阻擋沒有可合併進展 → 寫明原因並標記「⏸ 暫停」。

### 階段 A 標準函式庫與正確性稽核(預計 11/28–11/30)
- [x] A1 `docs/stdlib_coverage.md`:對照 IEC 61131-3 第 3 版標準函式/標準 FB 表逐項標示(2026-11-28;`tools/stdlib_probe.py` 自動探測 112 項:OK 60 / 結果錯誤 7 / 未支援 45 = 53%)
- [ ] A2 補齊缺口(拆兩次):
  - [ ] A2a 依型別寬度的 SHL/SHR/ROL/ROR 與 AND/OR/XOR/NOT(含中間值)、`BOOL_TO_STRING`、MUX、MOVE、EXPT、MID/FIND/INSERT/DELETE/REPLACE、多引數 CONCAT、`STRING(n)`、`STRING_TO_*`、BCD、`TRUNC_xxx`、CODESYS `TO_xxx`、函式形式 ADD/GT/AND…
  - [ ] A2b TIME/TOD/DATE/DT/LTIME 常數、型別與運算函式、型別化計數器 `CTU_DINT` 等
  - 每個函式至少一個邊界值測試,檢查器與方言警告同步更新;`tests/test_stdlib_probe.py` 的 `BASELINE_OK` 隨之調高
- [ ] A3 GitHub Actions CI(unittest + PLCopen XSD 驗證;無法啟動就略過、改自我審查);README「目前狀態」改為實際狀態
- 完成目標:常用標準函式與 FB 覆蓋率 ≥ 95%,ROL/ROR 等寬度錯誤修正並有回歸測試

### 階段 B 獨立參考實作交叉驗證(預計 12/1–12/3,替代目前無法進行的實機驗證)
- [ ] B1 嘗試在雲端建置 matiec(iec2c → C → gcc)或 rusty;一次排程內建不起來就記錄原因,改用手算期望值對照表
- [ ] B2 `tests/differential/`:同一支 ST + 同一組輸入序列,逐掃描週期比對虛擬 PLC 與參考實作輸出
- [ ] B3 ≥ 40 支程式(四則運算、溢位、型別轉換、計時器、計數器、邊緣偵測、字串、陣列、STRUCT、自訂 FB)結果一致;不一致逐一判定並寫入 `docs/differential_report.md`

### 階段 C 實務工控題庫(預計 12/4–12/8)
- [ ] C1 `tests/benchmark/` 架構 + 前 10 題(需求文字、點位表 CSV、情境 JSON 含互鎖/安全逐週期檢查、參考解 .st)
- [ ] C2 第 11–20 題
- [ ] C3 第 21–30 題(馬達啟停、正逆轉互鎖、星三角、交通號誌、水塔液位、輸送帶分揀、批次配料、混合槽、停車場計數、三層電梯、警報確認與閃爍、手動/自動切換、溫控回差/PI、SFC 風格步進、緊急停止與復歸……)
- [ ] C4 30 題全部通過 check + 情境 + ≥3 種廠牌匯出(PLCopen TC6 XSD 通過);併入 `eval`(14 → 44 題)。有 LLM 金鑰才跑真實評測,沒有就跳過(不用 mock 充數)

### 階段 D v1.0 發布收尾(預計 12/9–12/11)
- [ ] D1 `pyproject.toml`(`pip install .` → `plc-st` 指令)、Dockerfile(serve)
- [ ] D2 `docs/user_manual.md`:需求 → 產生 → 模擬 → 情境測試 → 匯出 完整操作手冊(附截圖)
- [ ] D3 `docs/hardware_validation_checklist.md`:彙整 todo.md 所有「待實機」項目為可勾選清單(廠牌/版本、匯入步驟、預期結果、範例檔)
- [ ] D4 全專案回歸(單元 + 全部 UI E2E + 題庫 + 交叉驗證)→ `docs/test_report_v1.0.md`,tag `v1.0.0` + GitHub Release

**下一步**:A2a(依型別寬度的位元運算修正 + 常用缺漏函式)。

## 已完成里程碑
- M1 ST 解譯核心:lexer/parser/interpreter、掃描週期、TON/TOF/CTU/R_TRIG/F_TRIG ✅
- M2 虛擬 PLC CLI + 點位表格(CSV)匯入/強制值/trace ✅
- M3 廠牌 profile:型別支援/溢位行為(iec、codesys、siemens、rockwell、mitsubishi、omron、strict、saturate;為近似模擬)✅
- M4 靜態檢查/驗證器(未宣告變數、型別不符、輸入被寫入、FB 呼叫)✅;廠牌方言警告(M4b ✅)
- M5 LLM provider 抽象(Gemini/GPT/Claude/Ollama,HTTP,stdlib)+ prompt 模板 ✅
- M6 RAG:文件切塊、TF-IDF 向量庫(可替換 embedding 為後續)、檢索注入 prompt ✅
- M7 ✅ 產生→驗證→自動修正迴圈
- M8 ✅ 測試情境腳本(輸入時序+預期輸出)自動驗證(`test` 指令)
- M9 ✅ generate 整合情境驗證(`--scenario`)
- M10 ✅ PDF/docx 讀取
- M11 ✅ Web UI(`serve` 指令:輸入方式、設定、RAG、虛擬 PLC 面板、波形、情境測試)
- M12 ✅ 匯出:PLCopen XML、Siemens SCL(`export` 指令 + UI)
- M13 ✅ 可替換 embedding;Rockwell L5X 匯出
- M14 ✅ Mitsubishi GX Works3 匯出;Web UI embedder 選項
- M15 ✅ Omron 匯出;README 補完
- M16 ✅ CTUD 計數器、標準函式擴充(位移、取整、字串)
- M17 ✅ ARRAY 一維陣列(解譯/檢查/PLCopen 匯出)
- M18 ✅ 使用者自訂 FUNCTION / FUNCTION_BLOCK(解譯/檢查;僅 st 格式匯出)
- M18b ✅ PLCopen XML 以 TC6 XSD 驗證;修正陣列初值與 STRING 型別
- M19 ✅ STRUCT / TYPE(巢狀、初始化、欄位存取;僅 st 格式匯出)
- M20 ✅ VAR_IN_OUT 寫回、函式陳述式呼叫
- M21 ✅ 多維陣列(解譯/檢查/PLCopen 匯出)
- M22 ✅ STRUCT 整體賦值(解譯/檢查)
- M23 ✅ ARRAY OF STRUCT(解譯/檢查)
- M24 ✅ ARRAY OF STRUCT 初始值、元素整體賦值
- M25 ✅ STRUCT PLCopen dataType 匯出(TC6 XSD 驗證)
- M26 ✅ STRUCT → Siemens SCL UDT 匯出
- M27 ✅ STRUCT → Rockwell L5X UDT 匯出
- M28 ✅ STRUCT 內含 ARRAY 欄位(解譯/檢查)
- M29 ✅ PR #31/#32 審查意見修正(L5X 匯出健全性、陣列寫入/初值);Dimensions 分隔符待實機確認
- UI1–UI7 Web UI 改版(UI1–UI7 ✅):單一畫面 + 頁籤 + 常駐狀態列 + 視覺系統 + 程式碼編輯器,見 `docs/ui_redesign_plan.md`
- M30 ✅ LLM 評測工具(`eval`)、Logix 方言對應、計時器邊緣時序修正
- M31 ✅ 檢查器補合法 IEC 語法(型別前綴/進位常數、TIME 轉換、陣列重複初值)+ 評測保存每輪程式碼
- M32 ✅ EXIT 位置、字串 $ 跳脫、REAL→INT 捨入
- M33 ✅ 自訂 FUNCTION / FUNCTION_BLOCK 匯出 PLCopen XML(TC6 XSD 驗證)與 Siemens SCL(FC/FB/OB)
- M34 ✅ VAR CONSTANT / RETAIN / VAR_TEMP、直接位址 AT %I/%Q/%M(解譯/檢查/方言/六種匯出)、點位表位址欄、斷電重啟模擬
- M35 ✅ 自訂 FUNCTION_BLOCK → Rockwell L5X Add-On Instruction(參數/區域標籤/巢狀 AOI、IEC 呼叫改寫為 Logix AOI 呼叫)
- M36 ✅ 整個陣列傳入 VAR_IN_OUT / VAR_INPUT、陣列整體賦值(L5X 轉 COP)、初值超出型別範圍的靜態檢查
- M37 ✅ 虛擬 PLC 直接位址共用記憶體(重疊位址同步、依廠牌位元組順序)、部分重疊才警告、UI ⇄ 標記;M37b 修正同位址 REAL 精度、陣列重疊警告
- M38 ✅ 點位表 → 各廠牌標籤表(TIA PLC 變數 xlsx、Studio 5000 標籤 CSV、GX Works3 全域標籤、Sysmac 全域變數、CODESYS GVL)、TIA 自動配置位址
- M39 ✅ 點位表匯出依廠牌換算位址(IEC word 編號 ⇄ S7 位元組)、TIA 自動配置避讓修正、Studio 5000 ALIAS(本機 I/O 槽號)
- UI8 ✅ 寬螢幕(≥1600px)雙頁籤:右側同時顯示兩個頁籤(例:模擬 + 測試),右欄指定/對調/記憶
- M40 ✅ 產生流程串流顯示(NDJSON 逐輪事件、進行中列、可停止、舊 API 後援)
- M41 ✅ ARRAY OF STRUCT 且 STRUCT 含 ARRAY 欄位(`a[i].f[j]`、元素初值/整體複製、陣列欄位整體讀寫與 VAR_IN_OUT 寫回)
- M42 ✅ TYPE STRUCT 匯出 GX Works3 / Sysmac Studio(結構體定義表、GX 結構體標籤初值逐一成員展開)
- M43 ✅ `VAR_GLOBAL` / `VAR_EXTERNAL`(頂層 GVL / PROGRAM 內全域、FB/函式共用、檢查器與方言提示、PLCopen globalVars / externalVars 匯出)
- M43b ✅ PR #60 審查修正(常數界限求值、EXTERNAL CONSTANT 綁定、PLCopen 全域常數、FB 內全域 STRUCT 複製、位址全域初始化順序)
