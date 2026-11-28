# 測試報告 A1:標準函式庫覆蓋率盤點(2026-11-28)

## 範圍
- 新增 `tools/stdlib_probe.py`:對照 IEC 61131-3 第 3 版標準函式/標準 FB,112 個探測案例(宣告 + 陳述式 + 期望值),
  在虛擬 PLC 執行並跑靜態檢查器,自動分類 OK / WRONG / CHECKER / MISSING。
- 新增 `docs/stdlib_coverage.md`(覆蓋率表、結果判讀、A2 拆分建議)。
- 新增 `tests/test_stdlib_probe.py`(4 項):OK 數不得低於基準 60、核心 FB/函式必須 OK、文件與探測項目一致。
- 本次同時合併遺留 PR #54(M37b:同位址 REAL 精度、陣列位址重疊警告),與目前 main 合併無衝突。

## 結果
| 項目 | 結果 |
|---|---|
| 探測 112 項 | OK 60、WRONG 7、MISSING 45(覆蓋率 53%) |
| 單元測試(含 PR #54 的 14 項、本次 4 項) | 565 項 OK(12 skipped) |
| UI | 無介面變動,未跑 E2E |

## 主要發現(A2 待修)
- ROL/ROR 寫死 16 位元:BYTE、DWORD 結果錯誤;`n ≥ 16` 會拋例外。
- SHL / NOT 在運算式中間未依型別截斷(只在指派時截斷)。
- `BOOL_TO_STRING` 輸出 `True` 而非 `TRUE`。
- 缺 MUX、MOVE、EXPT、MID/FIND/INSERT/DELETE/REPLACE、`STRING(n)`、TOD/DATE/DT 常數與運算、BCD、CODESYS `TO_xxx`、函式形式 ADD/GT/AND 等。
