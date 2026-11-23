# M39 測試報告:點位表匯出依廠牌換算位址 + Studio 5000 ALIAS

日期:2026-11-23(排程自動執行)

## 目標
M38 匯出標籤表時位址「照原樣」輸出,但 IEC / CODESYS 的 `%QW2` 是**第 2 個 word(位元組 4..5)**,
TIA Portal 的 `%QW2` 是**位元組 2..3**,直接沿用會讓實機 I/O 錯位。M39 依點位表的定址方式換算成目標廠牌的定址,
並讓 Studio 5000 可直接產生指向本機 I/O 模組的 ALIAS 標籤。

## 功能
| 項目 | 說明 |
|---|---|
| `convert_addr(addr, src, dst)` | `iec` ⇄ `s7`;位元位址 `%IX1.3` 兩者相同;S7 → IEC 未對齊(例 `%MW1`)回傳 None |
| 點位表定址 `addressing` | `iec`(預設,與虛擬 PLC 的 iec/codesys profile 一致)或 `s7`(與 siemens profile 一致) |
| TIA xlsx | 一律輸出位元組定址(IEC `%QW2` → `%QW4`,並提醒);**自動配置改用換算後的位元組**,修正 M38 會把新變數配到 IEC `%QW1`(位元組 2..3)上的問題 |
| CODESYS GVL | 一律輸出 word 編號(S7 `%QW4` → `%QW2`);未對齊保留原樣並提醒 |
| Studio 5000 ALIAS | `logix_slots`(例 `I=1,Q=2`):BOOL 位元位址 → `ALIAS,,name,…,"",Local:1:I.Data.n`(n = 位元組×8+位元);非 BOOL、%M、常數、超過第 31 點者保留一般 TAG 並提醒 |
| CLI | `tags pts.csv --format tia --addressing s7 -o x.xlsx`、`--format logix --logix-slots I=1,Q=2` |
| API | `/api/tags/export` 新增 `addressing`、`logix_slots`;錯誤值回 400 |
| Web UI | 「位址定址」選單(依廠牌 Profile / IEC / S7;Siemens profile 自動視為 S7)、選 logix 才顯示「Alias 槽號」,三者記入設定記憶 |

## 測試結果
- 單元測試:`python -m unittest discover -s tests` → **463 項通過**(10 skipped,環境缺 lxml 等選用套件),新增 `tests/test_m39.py` 16 項:
  換算雙向/往返/未對齊、與虛擬 PLC 共用記憶體一致(CODESYS `%MW1` 與 `%MX2.0` 重疊 ⇒ TIA `%MW2`)、TIA 換算與自動配置避讓、
  S7 來源不換算、GVL 換算與未對齊提醒、Logix ALIAS(Data 位元、O 區、超過 31 點、%M、類比、初值)、槽號解析錯誤、API、CLI。
- M38 既有測試調整 1 項:`speed %QW2` 匯出到 TIA 由 `%QW2` 改為 `%QW4`(刻意的行為修正)。
- UI:`tests/ui_m39.js` **14/14 PASS**;回歸 `tests/ui_m38.js` 10/10(修正 `.tagexp` 定位器因新增一列而不唯一)、`tests/ui_e2e.js` 130/130。

## 截圖(`docs/screenshots/m39/`)
| 檔案 | 內容 |
|---|---|
| `01_tia_iec_conversion.png` | IEC 點位表匯出 TIA:`%QW2 → %QW4`、`%IW1 → %IW2` 提醒 |
| `02_gvl_s7_conversion.png` | Siemens profile:GVL `%QW2 → %QW1`、`%IW1` 未對齊提醒 |
| `03_logix_alias.png` | Studio 5000 槽號 `I=1,Q=2`,ALIAS 與非位元/%M 提醒 |
| `04_mobile_addressing.png` | 390px 手機版定址列與槽號(無水平捲動) |

## 限制 / 待實機
- Studio 5000 ALIAS 只支援 1756 數位模組 `Local:槽:I.Data.n`(DINT 0..31);5069 CompactLogix(`Local:1:I.Pt00.Data`)與類比通道需手動建立。
- 待實機:Studio 5000 Import Tags 讀入 ALIAS 列(SPECIFIER 欄)、TIA Portal 匯入換算後的位元組位址。
- GX Works3 / Sysmac 仍只把 IEC 位址寫入註解(MELSEC X/Y 進位制依機種不同)。
