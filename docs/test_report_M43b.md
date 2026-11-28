# M43b 測試報告(PR #60 審查意見修正)
日期:2026-11-28

PR #60(M43 VAR_GLOBAL / VAR_EXTERNAL)合併後收到 5 則程式碼審查意見,本次全部修正。以下皆為模擬與靜態檢查層級的驗證,**尚未實機驗證**。

| # | 審查意見 | 修正 |
|---|---|---|
| 1 | 陣列界限:常數未求值就比對,`[0..N]`(N=3)與 `[0..3]` 被誤拒;`[0..N]` 與 `[0..M]` 都變成 `(0, None)` 被誤放 | `checker._cint()` 編譯期求值(字面值、負號、`+ - * / MOD`、CONSTANT,含循環保護);全域界限以全域常數求值、外部宣告以 POU 內環境求值(本地常數全部載入後才比對)。算不出來時給 warning「cannot verify」,不再默默通過。陣列/純量不一致也報錯。`cval()` 共用同一求值器 |
| 2 | `VAR_EXTERNAL CONSTANT g` 綁到可寫 `VAR_GLOBAL g` 時,CONSTANT 被丟掉,FB 可寫入 | 檢查器:error「refers to a writable VAR_GLOBAL」,且本 POU 內仍視為常數(寫入另報 `write to CONSTANT`);虛擬 PLC 建立時拒絕此綁定 |
| 3 | PLCopen 匯出:本地常數 `N := G + 1` 引用全域常數 G 時算不出來,匯出報陣列界限錯誤,與模擬不一致 | `export._consts(blocks, where, seed)` 以全域常數為初始環境求本地常數(同名時本地優先) |
| 4 | FB 內整份複製全域 STRUCT(`h := g`)模擬時 `unknown variable g` | `_prefixed()`:列舉 STRUCT 欄位時 `_Linked` 變數表也列出全域 scope 的鍵;用於 STRUCT 複製、ARRAY OF STRUCT 元素複製與「STRUCT used without member」訊息 |
| 5 | PROGRAM 中 FB 實例宣告在帶 `%I/%Q` 位址的 VAR_GLOBAL 之前時,全域沒有被提前,FB 初值讀不到 | parser 改依 `glob` 旗標(不是 section,%I/%Q 已改成 input/output)把全域提前 |

## 單元測試
`python -m unittest discover -s tests` → **547 項全部通過**。新增 `tests/test_m43_review.py` 15 項;在修正前的程式碼上其中 **11 項失敗**(7 fail + 4 error),修正後全過。

## UI 回歸(Node Playwright + Chromium)
`ui_m43` 11/11、`ui_e2e` 130/130、`ui_m34` 18/18、`ui_m36` 9/9、`ui_m37` 7/7、`ui_m41` 8/8、`ui_m42` 9/9。

## 截圖(`docs/screenshots/m43b/`)
- `01_check_bounds_and_constant.png`:`[0..N]` vs `[0..M]` 界限不符、EXTERNAL CONSTANT 綁可寫全域、寫入常數,三個錯誤帶行號
- `02_check_constant_bound_ok.png`:`[0..N]`(N=3)與 `[0..3]` 相符,檢查無問題

## 限制
- 界限求值只支援整數 `+ - * / MOD` 與 CONSTANT;其他運算式(例如函式呼叫)給 warning 而非 error。
- 尚未實機驗證(CODESYS / TwinCAT 匯入 PLCopen 全域常數界限)。
