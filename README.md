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

## CLI (M2)
```
python -m plc_st run examples/motor.st --cycles 10 --scan-ms 100 --set stop=false --at 1:start=true --trace out.csv
python -m plc_st tags examples/points.csv   # CSV 點位表 → VAR 宣告
```
點位表欄位: `name,type,direction(IN/OUT/INOUT/VAR),init,comment`。

## 靜態檢查 (M4)
```
python -m plc_st check examples/motor.st --profile siemens-s7-1200
```

## LLM 產生 (M5)
```
export ANTHROPIC_API_KEY=...   # 或 OPENAI_API_KEY / GEMINI_API_KEY;ollama 不需金鑰
python -m plc_st generate "馬達啟停,停止優先" --provider claude --tags examples/points.csv -o out.st
```
產生後自動執行 `check`;LLM 輸出仍須經虛擬 PLC 與廠牌官方工具驗證。

## RAG (M6)
```
python -m plc_st index examples/docs -o docs.idx.json      # 文件/資料夾 → 索引
python -m plc_st search docs.idx.json "TON 計時器"
python -m plc_st generate "..." --index docs.idx.json --top-k 4
```

## 情境測試 (M8)
```
python -m plc_st test examples/motor.st examples/motor_scenario.json
```
JSON:`steps` 每步 `set` 輸入 → 掃描 `cycles`/`ms` → 比對 `expect`(支援 `t.Q` 這類 FB 成員);不符 exit 1。

## 產生時情境驗證 (M9)
```
python -m plc_st generate @req.txt --scenario examples/motor_scenario.json --provider claude -o out.st
```
靜態檢查通過後在虛擬 PLC 跑情境,不符的步驟會回饋 LLM 修正(受 `--max-rounds` 限制)。

## 注意:「無警告」不等於相容
`check` 的廠牌方言檢查(`plc_st/dialect.py`)是保守的啟發式規則,只涵蓋少數已知差異。
未出現警告不能視為通過該廠牌 IDE/PLC 的編譯或相容性驗證,上傳實機前請以廠牌官方工具再驗證。
