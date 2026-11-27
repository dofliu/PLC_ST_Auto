# M42 測試報告(TYPE STRUCT 匯出 GX Works3 / Sysmac Studio)
日期:2026-11-27

## 變更
- `plc_st/export.py`
  - `_struct_defs()`:解析 `TYPE ... STRUCT`(註解/字串內不誤判);列舉、別名等非 STRUCT 的 TYPE 明確報錯。
  - `to_gxworks()`:開頭新增「Structured Data Types」表(Structure / Label Name / Data Type / Initial Value),成員型別換成 MELSEC 型別(INT→Word [Signed]、BOOL→Bit…)。
    結構體或 ARRAY OF STRUCT 標籤的初值以 `_flat_init()` 展開為逐一成員,列於「Structured Label Initial Values」
    (巢狀 `ax.home.x`、多維 `g[0, 2].x`、`2((y := 20))` 重複初值、未列出的成員沿用型別預設)。
  - `to_sysmac()`:開頭新增「Data Types / Structures」表(Structure / Member / Base Type / Initial Value);變數初值保留 IEC 寫法。
  - 匯出閘門:GX Works3 / Sysmac 只再拒絕 `FUNCTION` / `FUNCTION_BLOCK`,原因說明 TYPE STRUCT 已支援。
- 範例 `examples/struct_gx_sysmac.st`。
- 舊測試(`test_struct.py`、`test_struct_export.py`、`test_ui6.py`、`ui_e2e.js` #51)原本驗證「GX/Sysmac 拒絕 STRUCT」,改為驗證已支援,或改用 FUNCTION_BLOCK 範例驗證仍會拒絕。

## 單元測試
`python -m unittest discover -s tests` → **510 項通過**(10 項因缺 lxml/PDF 環境略過)。新增 `tests/test_m42.py` 16 項:
GX 結構體定義/成員型別/定義順序、巢狀與字串含逗號的初值展開、多維 + 常數邊界 + 重複初值、基本型別陣列初值保留、VAR_TEMP 結構體提醒、
無 TYPE 時輸出不變、Sysmac 定義表與初值、7 個 STRUCT 範例皆可匯出、FUNCTION_BLOCK 仍拒絕、列舉 TYPE 拒絕、
3 種錯誤初值、註解/字串中的 TYPE 不誤判、同一原始碼可在虛擬 PLC 執行、`/api/export` 與 `/api/export/status`。

## UI 實測(Node Playwright + Chromium,`tests/ui_m42.js`)
| # | 項目 | 結果 |
|---|---|---|
| M42-01 | struct_gx_sysmac.st 靜態檢查無錯誤 | PASS |
| M42-02 | 模擬初值 sum = 41(巢狀/重複初值生效) | PASS |
| M42-03 | start 3 週期後 sum = 44 | PASS |
| M42-04 | GX Works3、Sysmac 卡片顯示可匯出 | PASS |
| M42-05 | GX 預覽含結構體定義(MELSEC 型別) | PASS |
| M42-06 | GX 預覽結構體標籤初值逐一成員 | PASS |
| M42-07 | Sysmac 預覽含結構體表與 IEC 初值 | PASS |
| M42-08 | 含 FUNCTION:GX 卡片顯示不支援與原因 | PASS |
| M42-09 | 全程無 JS 錯誤 | PASS |

回歸:`ui_e2e.js` 130/130、`ui_m34` 18/18、`ui_m35` 9/9、`ui_m36` 9/9、`ui_m37` 7/7、`ui_m38` 10/10、`ui_m39` 14/14、`ui_m40` 19/19、`ui_m41` 8/8、`ui_ui8` 22/22。

## 截圖(`docs/screenshots/m42/`)
- `01_sim_struct.png` 模擬執行結構體程式
- `02_export_gxworks_preview.png` GX Works3 預覽(結構體定義表)
- `03_export_sysmac_preview.png` Sysmac 預覽
- `04_export_function_reason.png` 含 FUNCTION 時的不支援原因

## 限制 / 待實機確認
- GX Works3:結構體成員表貼上的欄位順序;標籤陣列型別目前沿用 `ARRAY[0..3] OF INT` 寫法(GX 原生寫法可能為 `Word [Signed](0..3)`),結構體整體賦值是否可編譯。
- Sysmac:結構體成員初值欄位、變數初值 `(a := 1)` / `[..]` 寫法是否可直接貼上。
- STRUCT 欄位為 ARRAY OF STRUCT 仍未支援虛擬 PLC 執行(匯出端已可展開)。
