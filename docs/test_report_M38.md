# M38 測試報告:點位表 → 各廠牌標籤表匯出

日期:2026-11-22 · 分支 `claude/lucid-fermat-b8cjhm`

## 目標
讓點位表(CSV)可以直接匯入實體 PLC 的工程軟體,而不只是轉成 ST 的 VAR 宣告。

| 格式 | 輸出 | 匯入方式 | 主要處理 |
|---|---|---|---|
| `tia` | `.xlsx` | TIA Portal → PLC tags → Import | PLC Tags / User Constants 工作表;未指定位址者自動配置 %I/%Q/%M(位元組定址、word 偶數對齊、RETAIN 先配置);非基本型別略過 |
| `logix` | `.CSV` | Studio 5000 → Tools → Import → Tags | `TAG` 列、RADIX/Constant;陣列 0 起算、TON→TIMER、CTU→COUNTER、WORD→INT、TIME→DINT |
| `gxworks` | `.txt`(Tab) | 貼入 Global Label Setting | Class `VAR_GLOBAL[_CONSTANT/_RETAIN]`、MELSEC 型別、陣列 `(lo..hi)` |
| `sysmac` | `.txt`(Tab) | 貼入 Global Variables | Retain / Constant / Network Publish 欄 |
| `codesys` | `.gvl.st` | CODESYS / TwinCAT GVL | `VAR_GLOBAL` / `CONSTANT` / `RETAIN`,保留 `AT` 位址 |

每個格式都回傳提醒清單(自動配置的位址、未匯出的初值、型別替代、需人工指定的裝置)。

## 測試結果
| 項目 | 結果 |
|---|---|
| 單元測試 `tests/test_m38.py` | 16/16 PASS(xlsx 以 stdlib 讀回驗證;另以 openpyxl 3.1.5 開啟確認) |
| 全部單元測試 `python -m unittest discover -s tests` | 447 項 OK(10 skipped) |
| UI 測試 `tests/ui_m38.js` | 10/10 PASS |
| 既有 UI E2E `tests/ui_e2e.js`(回歸) | 130/130 PASS |

UI 測試項目:格式選單 5 種、TIA 下載為 zip(xlsx)、提醒列出自動配置位址與略過 TON、Studio 5000 表頭與 TIMER、GX Works3 類別、Sysmac Retain 欄、GVL 無提醒、錯誤點位表顯示行號、手機寬度無水平捲動、無 JS 錯誤。

## 截圖(`docs/screenshots/m38/`)
- `01_tia_export_warnings.png`:匯出 TIA xlsx 後的 6 項提醒
- `02_gvl_export_ok.png`:CODESYS GVL 匯出成功
- `03_tag_export_error.png`:不合法識別字的錯誤訊息(含行號)
- `04_mobile_tag_export.png`:手機版匯出列與提醒

## 限制 / 待實機
- 位址照點位表原樣輸出(TIA 僅 `%IX0.0` → `%I0.0`),不依廠牌換算 word 編號(IEC `%QW2` 為位元組 4,TIA `%QW2` 為位元組 2)— 列入下一步候選。
- 欄位格式依公開文件與匯出範例整理,尚未在 TIA Portal、Studio 5000、GX Works3、Sysmac Studio 實機匯入確認。
- Logix 標籤 CSV 不含初值與 Alias;需要初值請用 L5X 程式匯出。
