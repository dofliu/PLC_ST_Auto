# M37 測試報告:虛擬 PLC 直接位址共用記憶體

日期:2026-11-21(排程自動執行)

## 範圍
- 新模組 `plc_st/memory.py`:`ProcessImage`(I/Q/M 三個區域的位元組陣列)與 `LocatedVars`(變數表 dict 子類別)。
  只追蹤**真的與其他變數重疊**的直接位址變數;沒有重疊時變數表仍是一般 dict,行為與效能不變。
- 定址與位元組順序依 profile:
  - IEC / CODESYS(預設):`%MW1` = 第 1 個 word(位元組 2..3)、little-endian,`%MX0.0` = `%MW0` bit 0
  - Siemens S7-1200/1500:`%MW1` = 位元組 1..2、big-endian,`%M0.0` = `%MW0` bit 8
- 同步涵蓋所有寫入路徑:指派、UI/情境強制(`set_input`)、FB 輸出 `=>`、FOR 迴圈變數、宣告初值(後宣告者覆蓋)、暖/冷重啟與 RETAIN。
- 支援型別別名:`REAL` ⇄ `DWORD`(IEEE 754 位元)、`INT` ⇄ `UINT`(二補數)、BYTE/WORD/DWORD/LWORD/TIME。
- 檢查器:完全包含的別名(位元在位元組/字內、相同位址不同型別)不再警告;**部分重疊**(例 S7 `%MW0` 與 `%MW1` 共用 byte 1)
  仍警告,訊息改為 `partially overlaps … they share bytes`。
- Web:`/api/sim/start`、`/api/run` 的 meta 加 `shared`;I/O 面板以 ⇄ 標記共用的變數(tooltip 列出對象)。
  順帶修正:有位址標記時名稱被擠成「s…」,改為名稱至少 6 字元、型別移到 tooltip。
- 範例 `examples/shared_memory.st`:`%IB0` 輸入位元組 + 起停位元、`%MW0` 狀態字 + `%MX` 旗標、`%QB0` 輸出位元組。

## 測試結果
| 項目 | 結果 |
|---|---|
| `tests/test_m37.py`(位元組順序 3、同步 10、檢查 2、Web 1、情境 1) | 17/17 PASS |
| 全部單元測試 `python3 -m unittest discover -s tests`(無 lxml) | 431 PASS(10 skipped) |
| 全部單元測試 `python3.13 -m unittest discover -s tests`(有 lxml) | 431 PASS |
| UI `tests/ui_m37.js` | 7/7 PASS |
| UI 回歸 `tests/ui_e2e.js` / `ui_m34.js` / `ui_m35.js` / `ui_m36.js` | 130/130、18/18、9/9、9/9 PASS |
| `examples/*.st` 靜態檢查 | 無錯誤 |

調整既有測試:`test_m34.test_overlap_depends_on_vendor_addressing` 依新規則改為 IEC 0 個、S7 1 個(部分重疊)警告。

## 截圖(`docs/screenshots/m37/`)
- `01_sim_iec_shared.png`:IEC,強制 `inByte = 1` → start、running、motor 亮,status = 1、outByte = 1
- `02_sim_siemens_shared.png`:Siemens S7-1500,同一程式 status = 256(`%M0.0` 為 `%MW0` 高位元組的 bit 0)
- `03_check_partial_overlap.png`:S7 `%MW0` / `%MW1` 部分重疊警告

## 限制 / 待辦
- 陣列、STRUCT、STRING 放在直接位址上不參與共用記憶體(檢查器原本就會對不支援的型別報錯)。
- FUNCTION_BLOCK 內的直接位址變數各自獨立(檢查器已提示應放在 PROGRAM)。
- 待實機:CODESYS / TIA Portal 確認位元對應與位元組順序。
