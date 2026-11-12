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

## LLM 評測 (M30)
```
python -m plc_st eval --provider claude --model claude-haiku-5-5 --model claude-sonnet-5-5 --repeat 3
```
14 個案例(工控原語、點位表、RAG、方言、TC6 XSD、多廠牌匯出、情境修正、防溢位、安全假設、Web API),
判定條件固定寫在 `plc_st/llm_eval.py`。輸出 `eval_out/<時間>/report.md`(通過率、一次正確率、修正輪數、
耗時、token;加 `--price 模型=輸入,輸出` 可估算費用)與每次產生的 `.st`。`--cases TC-01,TC-04` 可只跑部分案例。

## 注意:「無警告」不等於相容
`check` 的廠牌方言檢查(`plc_st/dialect.py`)是保守的啟發式規則,只涵蓋少數已知差異。
未出現警告不能視為通過該廠牌 IDE/PLC 的編譯或相容性驗證,上傳實機前請以廠牌官方工具再驗證。

## Web UI
`python -m plc_st serve --port 8765` 後開啟 http://127.0.0.1:8765 (僅本機)。UI 功能測試:`PYTHONPATH=. CHROMIUM_PATH=<chromium> python tests/ui_smoke.py`(需 playwright)。報告見 `docs/test_report_M11.md`。

程式碼編輯器(UI3):行號、ST 語法色彩、輸入後自動檢查並在行號/程式行標記錯誤與警告、點擊問題清單或行號跳到該行、游標行/欄顯示。
模擬儀表板(UI4):執行/暫停/單步/重設與速度(×0.2/×1/×10)、I/O 面板(BOOL 輸入開關、輸出燈號、數值即時顯示;暫停時切換的輸入於下一掃描生效)、波形每變數一軌(STRING 以文字帶顯示、長名稱截斷)、滾輪縮放/拖曳平移/游標讀值/雙擊全覽;批次執行(事件腳本)後游標移動時 I/O 面板回放該週期值。快捷鍵 `Alt+R` 執行/暫停、`Alt+S` 單步。API:`/api/sim/start|step|stop`。執行期錯誤訊息帶行號並標記於編輯器。

情境測試與匯出(UI6):情境可用表格編輯(步驟名稱/設定輸入 `變數=值; …`/等待 ms 或週期/預期輸出),與 JSON 雙向切換,變數晶片一鍵插入;執行後逐步顯示 ✔/✘ 與實際值。匯出頁以 6 張廠牌卡片顯示可否匯出、不支援原因、方言警告(點擊跳行)與預覽。API:`/api/test`(回傳 `steps`)、`/api/export/status`。
快捷鍵:`Ctrl+Enter` 執行模擬、`Ctrl+Shift+Enter` 靜態檢查、`Ctrl+/` 註解切換、`Tab`/`Shift+Tab` 縮排(先按 `Esc` 再按 Tab 可離開編輯器)、`THEN`/`DO` 等之後 Enter 自動縮排。
E2E:`python -m plc_st serve --port 8765` 後 `NODE_PATH=$(npm root -g) node tests/ui_e2e.js [截圖資料夾]`(`UI3_SHOTS=`/`UI4_SHOTS=`/`UI6_SHOTS=` 指定編輯器/模擬儀表板/測試與匯出截圖資料夾)。

## 陣列 (M17)
支援一維 `ARRAY[lo..hi] OF T`(可帶初始值 `:= [1,2,3]`),以 `a[i]` 讀寫;越界於靜態檢查(常數索引)與執行期皆報錯。
`--set buf[2]=5`、情境與 trace 以 `buf[0]`、`buf[1]`… 欄位呈現。尚不支援多維陣列、STRUCT;PLCopen 匯出為 `<array>`,其他廠牌匯出保留原 ST 宣告文字。

## 匯出
`python -m plc_st export examples/motor.st --format plcopen|scl|l5x|gxworks|sysmac|st -o out`(Web UI 亦有「匯出」按鈕)。PLCopen XML 可匯入 CODESYS 等;scl=Siemens TIA、l5x=Rockwell Studio 5000、gxworks=Mitsubishi GX Works3(標籤表+ST)、sysmac=Omron Sysmac Studio(變數表+ST);匯出後請在目標 IDE 編譯確認。
PLCopen 可加 `--validate` 以官方 TC6 v2.01 XSD(`plc_st/schemas/`)驗證結構,失敗時 exit 1(需 `pip install lxml`)。
