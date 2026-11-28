# M37b 測試報告:M37 審查回歸修正(REAL 精度、陣列重疊)

日期:2026-11-22 · 分支 `claude/lucid-fermat-b8cjhm`

## 審查指出的問題(已重現)
| # | 問題 | 重現 | 修正前 |
|---|---|---|---|
| 1 | 同位址的 REAL 讀出不同精度 | `r1 AT %MD0 : REAL; r2 AT %MD0 : REAL; r1 := 0.1;` | `r1 = 0.1`(64 位元)、`r2 = 0.10000000149011612`(32 位元),`r1 = r2` 為 FALSE |
| 2 | 未同步的陣列漏報位址重疊 | `arr AT %MW0 : ARRAY[0..3] OF WORD; x AT %MW2 : WORD;` | 檢查器只算第一個元素,**無警告**;模擬時 `arr[2] := 16#1234` 後 `x` 仍為 0 |

## 修正
1. `plc_st/memory.py`:寫入共用記憶體後,寫入者自己也從記憶體讀回 → REAL 依 32 位元捨入、整數依位元寬截斷,同位址變數讀到相同的值。沒有位址重疊的變數行為不變。
2. `plc_st/checker.py`:陣列的位址範圍改為「元素數 × 元素位元」(邊界可用 `VAR CONSTANT`,依廠牌定址:IEC 依大小、S7 依位元組);只要重疊的一方是陣列就警告 `array … is NOT kept in sync by the virtual PLC, simulation results may differ from the real PLC`。純量之間的完整別名維持不警告。陣列元素同步模擬**未實作**,改由警告明確告知。

## 測試結果
| 項目 | 結果 |
|---|---|
| 新回歸測試 `tests/test_m37_review.py` | 修正前 10/14 失敗,修正後 14/14 PASS |
| 全部單元測試 | 461 項 OK(10 skipped) |
| UI `tests/ui_m37.js` / `tests/ui_m38.js`(回歸) | 7/7、10/10 PASS |

## 驗收說明
- 純量重疊位址(含 REAL/DWORD 別名、位元/位元組/字、Siemens big-endian)的模擬結果可作為驗收依據。
- 陣列與其他位址重疊時,模擬結果**不能**作為驗收依據;靜態檢查會發出警告。
