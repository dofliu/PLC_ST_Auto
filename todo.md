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
## M11 (下一個)
- [ ] 可替換 embedding
- [ ] Web UI(stdlib http.server:輸入、設定、虛擬 PLC 面板)
## M6 修補 ✅
- [x] 切塊參數檢查(size>0、0<=overlap<size)、`index` 排除輸出檔、`add_path` 批次只重建一次索引
