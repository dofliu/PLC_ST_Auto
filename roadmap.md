# Roadmap(每個里程碑 ≤ 2 小時)
- M1 ST 解譯核心:lexer/parser/interpreter、掃描週期、TON/TOF/CTU/R_TRIG/F_TRIG ✅
- M2 虛擬 PLC CLI + 點位表格(CSV)匯入/強制值/trace
- M3 廠牌 profile:型別範圍/溢位、方言檢查(Siemens SCL、Rockwell、Mitsubishi、CODESYS、Omron)
- M4 靜態檢查/驗證器(未宣告變數、型別、廠牌方言警告)
- M5 LLM provider 抽象(Gemini/GPT/Claude/Ollama,HTTP,stdlib)+ prompt 模板
- M6 RAG:文件切塊、TF-IDF/可替換 embedding 向量庫、檢索注入 prompt
- M7 產生→驗證→自動修正迴圈
- M8 Web UI(輸入方式、設定、虛擬 PLC 面板、波形)
- M9 匯出:PLCopen XML、各廠牌檔案格式
