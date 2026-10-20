# PLC ST Auto

PLC Structured Text (IEC 61131-3 ST) 開發工具:輸入需求 → LLM(搭配 RAG)產生 ST → 虛擬 PLC 驗證 → 輸出可上傳實體 PLC 的程式碼。

## 目標功能
1. 多種輸入:文字、檔案上傳、點位表格(CSV)
2. RAG:外部文件向量庫,降低幻覺
3. LLM:Gemini / GPT / Claude / Ollama 可設定
4. 虛擬 PLC:載入 ST 後以掃描週期模擬執行
5. 多廠牌模擬 profile(Siemens / Rockwell / Mitsubishi / CODESYS / Omron …)
6. 排程開發:見 `roadmap.md`、`todo.md`

## 目前狀態
M1 完成:純標準庫 ST 解譯器(`plc_st/`)。無外部相依。

## 使用
```python
from plc_st import VirtualPLC
plc = VirtualPLC(open("examples/motor.st").read())
plc.set_input("start", True)
plc.scan(10)
print(plc.get("motor"))
```
測試:`python3 -m unittest discover -s tests -v`
