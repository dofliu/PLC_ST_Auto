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
## M4b (下一個)
- [ ] 廠牌方言警告(Siemens SCL / Rockwell / Mitsubishi 語法差異,如保留字、轉換函式命名)
## M5
- [ ] LLM provider 抽象(Gemini/GPT/Claude/Ollama)+ prompt 模板
