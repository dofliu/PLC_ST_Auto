# M41 測試報告(ARRAY OF STRUCT 且 STRUCT 含 ARRAY 欄位)
日期:2026-11-26

## 變更
- `plc_st/interpreter.py`:移除「ARRAY OF STRUCT whose STRUCT has ARRAY fields is not supported」限制。
  陣列欄位 `slots.setp` 以「外層維度 + 欄位維度」列優先存成一個平面陣列,每個元素佔一段連續區塊。
  - `a[i].f[j]` 讀寫、多維外層 `m[1,2].grid[1,0]`、巢狀 `c[i].ax.pos[k]`
  - 元素初值 `[(setp := [10, 20, 30]), (name := 'B')]`(未指定沿用 STRUCT 預設)
  - `w := a[i]` / `a[i] := w` / `a[1] := a[2]` 整體複製(陣列欄位深拷貝)
  - `b := a[i].f`、`a[i].f := b`、傳入 `VAR_IN_OUT` / `VAR_INPUT` 陣列參數(呼叫後寫回該元素)
  - 外部名稱 `a[i].f[j]`:`set_input` / `get` / 快照 / 情境 / 波形
  - RETAIN 暖/冷重啟、FB 內宣告、VAR_TEMP 每次重新初始化
- `plc_st/web/index.html`:I/O 面板長名稱只省略名稱部分,外層索引 `[i]` 與最後的 `.f[j]` 永遠可見(原本 `slots[1].setp…` 與 `slots[2].setp…` 看起來一樣)。
- `tests/ui_e2e.js`:64/65 改為等待整個產生流程完成再讀時間軸(M40 改串流後在主線上就已失敗,與本次變更無關)。
- 範例 `examples/recipe_slots.st`(配方槽)。

## 單元測試
`python -m unittest discover -s tests` → **494 項通過**(10 項因缺 lxml/PDF 環境略過)。新增 `tests/test_m41.py` 16 項:
預設/元素初值、讀寫與 FOR、多維外層 + 多維欄位、元素 ⇄ STRUCT 複製(深拷貝)、巢狀 STRUCT 元素複製、陣列欄位整體賦值與形狀不符、
執行期越界(內/外層)/未加索引/初值過多、外部強制/讀值/快照名稱、RETAIN 暖/冷重啟、FB 內與 VAR_TEMP、範例程式、情境、檢查器(無誤報 + 4 種錯誤)、PLCopen/SCL 匯出。
`test_struct_arrfield.py` 原「明確拒絕」測試改為驗證已支援。

## UI 實測(Node Playwright + Chromium,`tests/ui_m41.js`)
| # | 項目 | 結果 |
|---|---|---|
| M41-01 | recipe_slots.st 靜態檢查無錯誤 | PASS |
| M41-02 | `slots[1].setp[4]` 越界、`slots[2].setp` 未加索引報錯 | PASS |
| M41-03 | 波形軌道以 `slots[i].setp[j]` 命名 | PASS |
| M41-04 | 6 週期後 `slots[2].setp[1]=16`、`slots[3].setp[2]=52`、`slots[3].name=copy` | PASS |
| M41-04b | I/O 面板長名稱外層 `[2]` 與 `.setp[j]` 都可見 | PASS |
| M41-05 | 情境:陣列欄位期望值 PASS | PASS |
| M41-06 | 情境:錯誤期望值偵測為 FAIL | PASS |
| M41-07 | 全程無 JS 錯誤 | PASS |

回歸:`ui_e2e.js` 130/130、`ui_m40.js` 19/19、`ui_m37.js` 7/7、`ui_m36.js` 9/9、`ui_m35.js` 9/9、`ui_m34.js` 18/18。

截圖(`docs/screenshots/m41/`):`01_check_ok.png`、`02_check_errors.png`、`03_sim_wave.png`、`04_scenario_pass.png`、`05_scenario_fail.png`。

## 匯出
PLCopen XML(`<derived name="Recipe"/>` 陣列 + dataType 陣列欄位)與 Siemens SCL(`ARRAY[1..3] OF "Recipe"` + UDT)照常產生;
L5X 仍要求陣列下界為 0(Logix 限制);GX Works3 / Sysmac 仍不支援 STRUCT(既有限制)。

## 已知限制
- STRUCT 欄位本身為 `ARRAY OF STRUCT`、ARRAY OF STRUCT 整體傳遞/賦值尚不支援(明確報錯)。
