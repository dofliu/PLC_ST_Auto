# TODO
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
## 下一步候選(≤2h)
- [ ] 其他格式 STRUCT 匯出(SCL TYPE、L5X UDT)
- [ ] 自訂 POU 的 PLCopen/SCL 匯出
