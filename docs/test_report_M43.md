# M43 測試報告(VAR_GLOBAL / VAR_EXTERNAL)
日期:2026-11-27

## 變更
- `plc_st/lexer.py`、`plc_st/parser.py`:新增 `VAR_GLOBAL`、`VAR_EXTERNAL` 關鍵字與區段。頂層(TYPE / FUNCTION / FUNCTION_BLOCK 之間任意順序)與 PROGRAM 內的 `VAR_GLOBAL` 併入程式宣告最前面,標記 `glob`;FB/函式內寫 `VAR_GLOBAL`、`VAR_EXTERNAL` 帶初值或 AT 位址皆為語法錯誤並說明正確寫法。
- `plc_st/interpreter.py`:新增 `_Linked` 變數表。FB / 函式 scope 中本地未宣告、但屬於全域的名稱(VAR_EXTERNAL 或 CODESYS 式直接存取)讀寫都轉到程式 scope;以 `plc.gscope` 動態查找,斷電重啟後(含被保留的 RETAIN FB 實例)仍指向新 scope。全域 `AT` 位址仍走 M37 共用記憶體、CONSTANT 仍受寫入保護。
- `plc_st/checker.py`:FB/函式可見全域變數;VAR_EXTERNAL 找不到 VAR_GLOBAL、型別或陣列範圍不符 → error;CONSTANT 全域未以 `VAR_EXTERNAL CONSTANT` 宣告 → warning;PROGRAM 變數與全域同名 → error;FB 區域變數遮蔽全域 → warning。
- `plc_st/dialect.py`:Siemens(全域 DB)、Rockwell(controller-scoped 標籤)、Mitsubishi(Global Label)、Omron(Global Variable table)提示。
- `plc_st/export.py`:`global_blocks()`;PLCopen 頂層全域 → `<resource><globalVars [constant|retain]>`,POU 內 `VAR_EXTERNAL` → `<externalVars>`、PROGRAM 內 `VAR_GLOBAL` → `<globalVars>`;全域常數可作為 POU 陣列邊界。SCL / L5X / GX Works3 / Sysmac 含全域時拒絕並說明各平台作法。
- `plc_st/web.py`、`index.html`:模擬 meta 新增 `global`,I/O 面板顯示 `GLOBAL` 標記。
- 範例 `examples/global_vars.st`(兩個 FB 實例共用全域計數、常數上限、全域停止旗標、全域陣列,函式讀全域)。

## 單元測試
`python -m unittest discover -s tests` → **532 項全部通過**(本次環境安裝 lxml,PLCopen XSD 驗證實際執行)。新增 `tests/test_m43.py` 22 項:
解析(合併順序/旗標、PROGRAM 內與 POU 之間的全域、3 種語法錯誤)、模擬(FB 與函式共用、兩實例共用計數與上限、執行期常數保護、區域遮蔽、全域常數作為 FB 陣列邊界、RETAIN 暖/冷重啟、AT 共用記憶體、缺少全域)、
檢查器(無誤範例、型別/範圍/缺少、常數規則、衝突與遮蔽、經 EXTERNAL 的型別檢查、四廠牌方言)、匯出(global_blocks、PLCopen + XSD、PROGRAM 內全域、其他格式拒絕原因、st 原樣)、`/api/run` meta。

## UI 實測(Node Playwright + Chromium,`tests/ui_m43.js`)
| # | 項目 | 結果 |
|---|---|---|
| M43-01 | global_vars.st 靜態檢查無錯誤 | PASS |
| M43-02 | VAR_EXTERNAL 型別不符、缺少 VAR_GLOBAL 帶行號報錯 | PASS |
| M43-03 | I/O 面板標示 GLOBAL / GLOBAL+CONST | PASS |
| M43-04 | 非全域變數無標記 | PASS |
| M43-05 | cA 兩次 + cB 一次上升緣 → g_count=3、remain=2 | PASS |
| M43-06 | 達 G_LIMIT=5 → full=TRUE 且不再累加 | PASS |
| M43-07 | PLCopen 卡片可匯出 | PASS |
| M43-08 | SCL / L5X 卡片顯示不支援與原因 | PASS |
| M43-09 | PLCopen 預覽含 globalVars / externalVars | PASS |
| M43-10 | Siemens profile 顯示 VAR_GLOBAL 方言提示 | PASS |
| M43-11 | 全程無 JS 錯誤 | PASS |

回歸:`ui_e2e.js` 130/130、`ui_m34` 18/18、`ui_m35` 9/9、`ui_m36` 9/9、`ui_m37` 7/7、`ui_m38` 10/10、`ui_m39` 14/14、`ui_m40` 19/19、`ui_m41` 8/8、`ui_m42` 9/9、`ui_ui8` 22/22。

## 截圖(`docs/screenshots/m43/`)
- `01_editor_check.png` 靜態檢查通過
- `02_check_external_errors.png` VAR_EXTERNAL 錯誤
- `03_sim_globals.png` 模擬:GLOBAL 標記與共用計數波形
- `04_export_cards.png` 匯出卡片(PLCopen 可匯出、SCL/L5X 原因)
- `05_export_plcopen_preview.png` PLCopen 預覽
- `06_dialect_siemens.png` Siemens 方言提示

## 限制 / 待後續
- VAR_GLOBAL 尚未轉換到 SCL 全域 DB、L5X controller 標籤、GX Works3 / Sysmac 全域表。
- 從外部讀取 FB 陣列成員元素 `f.buf[i]` 仍不支援(M43 之前即存在,已列入 todo)。
- **待實機**:CODESYS / TwinCAT 匯入 PLCopen `<resource><globalVars>` 是否建立 GVL。
