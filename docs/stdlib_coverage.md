# IEC 61131-3 標準函式 / 標準 FB 覆蓋率(A1,2026-11-28)

對照 IEC 61131-3 第 3 版(2013)表 22–37(型別轉換、數值、算術、位移、位元邏輯、選擇、比較、字串、時間日期函式)
與表 43–46(雙穩態、邊緣偵測、計數器、計時器標準 FB),逐項在虛擬 PLC 執行一次並跑靜態檢查器。
本表由 `python tools/stdlib_probe.py` 自動產生(每項:宣告 + 一行陳述式 + 期望值),A2 修正後重跑即可更新。

狀態定義:
- **OK** 已支援:執行結果等於期望值,檢查器無錯誤
- **WRONG** 部分支援:可以執行但結果錯誤(最危險:LLM 產生的程式在模擬中「看起來正常」,上實機才出錯)
- **CHECKER** 執行正確但檢查器誤報
- **MISSING** 未支援:語法或執行期錯誤

## 摘要

| 類別 | 項目數 | OK | WRONG | MISSING |
|---|---|---|---|---|
| 型別轉換 | 18 | 11 | 1 | 6 |
| 數值 | 12 | 11 | 0 | 1 |
| 算術 | 10 | 3 | 0 | 7 |
| 位移 | 9 | 3 | 5 | 1 |
| 位元邏輯 | 6 | 4 | 1 | 1 |
| 選擇 | 5 | 4 | 0 | 1 |
| 比較 | 5 | 2 | 0 | 3 |
| 字串 | 11 | 4 | 0 | 7 |
| 時間日期 | 17 | 4 | 0 | 13 |
| 基本型別 | 6 | 3 | 0 | 3 |
| 標準 FB | 13 | 11 | 0 | 2 |
| **合計** | **112** | **60** | **7** | **45** |

目前覆蓋率:**60/112 = 53%**(v1.0 目標 ≥ 95%)。

## 結果判讀

### 結果錯誤(WRONG,需優先修正)
1. **ROL / ROR 寫死 16 位元**:BYTE `ROL(16#81,1)` 得 2(應 3)、DWORD `ROL(16#80000001,1)` 得 2(應 3)、`ROR` DWORD 只剩低 16 位元;
   `n ≥ 16` 時 Python 拋出 `negative shift count`。需依運算元宣告型別(BYTE/WORD/DWORD/LWORD)決定寬度並取 `n MOD 寬度`。
2. **SHL / NOT 中間值未截斷**:`SHL(w,1) = 0`(WORD 16#8000)得 FALSE、`(NOT b) = 16#F0`(BYTE 16#0F)得 FALSE;
   只有在指派給變數時才依型別截斷,用在比較或運算式中間就會錯。
3. **BOOL_TO_STRING** 得到 Python 的 `'True'`,應為 `'TRUE'`。

### 未支援(MISSING),依 LLM 產生程式常用程度排序
| 優先 | 項目 | 備註 |
|---|---|---|
| 高 | `MUX`、`MOVE`、`EXPT` | 選擇/指派/次方,LLM 常用 |
| 高 | `MID`、`FIND`、`INSERT`、`DELETE`、`REPLACE`、多引數 `CONCAT` | 字串處理(條碼、通訊訊息組裝) |
| 高 | `STRING(n)` 長度宣告 | 很常見的宣告寫法,目前直接語法錯誤 |
| 高 | `TOD#` / `TIME_OF_DAY#` / `D#` / `DATE#` / `DT#` / `DATE_AND_TIME#` 常數與 `TOD`/`DATE`/`DT` 型別 | 排程、班別控制 |
| 高 | `ADD_TIME` `SUB_TIME` `MUL_TIME` `DIV_TIME` `ADD_TOD_TIME` `SUB_TOD_TOD` `SUB_DATE_DATE` `ADD_DT_TIME` `SUB_DT_DT` `CONCAT_DATE_TOD` `DT_TO_TOD` `DT_TO_DATE` | 時間日期運算 |
| 中 | `STRING_TO_*`、`TRUNC_INT` 等型別化 TRUNC、`*_TO_BCD` / `BCD_TO_*` | BCD 用於七段顯示器、指撥開關 |
| 中 | CODESYS 通用轉換 `TO_INT` `TO_REAL` `TO_DINT` …… | CODESYS / TwinCAT 程式常見 |
| 中 | 函式形式 `ADD` `SUB` `MUL` `DIV` `MOD` `GT` `GE` `EQ` `LE` `LT` `NE` `AND` `OR` `XOR` | IEC 允許;`MOD(`、`AND(` 目前在 parser 就失敗 |
| 中 | 型別化計數器 `CTU_DINT` / `CTD_UDINT` …… | 第 3 版加入 |
| 低 | `LWORD`、`CHAR`、`WSTRING`、`LTIME`、`LTON` / `TON_LTIME` | 64 位元與寬字元,較少見 |
| 延伸 | `ATAN2` | 非 IEC 標準(CODESYS/TwinCAT 有,西門子 SCL 無),只在方言提示中說明 |

### 已支援、已確認正確
`*_TO_*` 整數/實數/BOOL/TIME 互轉(含溢位繞回與捨入)、`TRUNC`、`*_TO_STRING`、全部數值函式(ABS…ATAN)、
`**` 與 `MOD` 運算子(負數取餘數依 IEC 截斷)、`SHL`/`SHR`(指派時)、`AND`/`OR`/`XOR`/`NOT` 運算子、
`SEL` / 多引數 `MAX`/`MIN` / `LIMIT`、比較運算子與字串比較、`LEN`/`LEFT`/`RIGHT`/兩引數 `CONCAT`、
`TIME` 加減乘除與比較、標準 FB `TON` `TOF` `TP`(含 `ET`)`CTU` `CTD` `CTUD` `R_TRIG` `F_TRIG` `SR` `RS`。

## A2 工作拆分建議(每次 ≤ 2 小時)
- **A2a 正確性**:ROL/ROR/SHL/SHR/NOT/AND/OR/XOR 依型別寬度(需要在 eval 時取得運算式型別;字面值依 IEC 視為最小可容納型別)、
  `BOOL_TO_STRING`、`MUX`、`MOVE`、`EXPT`、函式形式算術/比較/位元邏輯、多引數 `CONCAT`、字串函式 `MID/FIND/INSERT/DELETE/REPLACE`、
  `STRING(n)` 宣告與截斷、`STRING_TO_*`、BCD、`TRUNC_xxx`、`TO_xxx`;檢查器回傳型別與方言警告同步。
- **A2b 時間日期**:lexer `TOD#/D#/DT#/LTIME#`、型別 `TOD/DATE/DT/LTIME`、全部 `*_TIME` / `*_TOD_*` / `*_DT_*` 函式、`CTU_DINT` 等型別化 FB;
  各廠牌匯出(Logix 無 DATE 型別 → 方言警告)。

## 完整探測結果

| 類別 | 項目 | 狀態 | 說明 |
|---|---|---|---|
| 型別轉換 | INT_TO_REAL 等 *_TO_* | OK |  |
| 型別轉換 | REAL_TO_INT(2.5) 捨入 | OK | IEC:四捨五入(CODESYS 同) |
| 型別轉換 | DINT_TO_INT 截斷溢位 | OK |  |
| 型別轉換 | TRUNC | OK |  |
| 型別轉換 | TRUNC_INT(型別化) | MISSING | STError: line 5: unknown function TRUNC_INT |
| 型別轉換 | STRING_TO_INT | MISSING | STError: line 5: unknown function STRING_TO_INT |
| 型別轉換 | INT_TO_STRING | OK |  |
| 型別轉換 | REAL_TO_STRING | OK |  |
| 型別轉換 | BOOL_TO_STRING | WRONG | 得到 'True',應為 'TRUE' |
| 型別轉換 | INT_TO_BCD | MISSING | STError: line 5: unknown function INT_TO_BCD |
| 型別轉換 | BCD_TO_INT | MISSING | STError: line 5: unknown function BCD_TO_INT |
| 型別轉換 | TIME_TO_DINT | OK |  |
| 型別轉換 | DINT_TO_TIME | OK |  |
| 型別轉換 | TO_INT(通用,CODESYS) | MISSING | STError: line 5: unknown function TO_INT |
| 型別轉換 | TO_REAL(通用,CODESYS) | MISSING | STError: line 5: unknown function TO_REAL |
| 型別轉換 | BYTE_TO_WORD | OK |  |
| 型別轉換 | INT_TO_UINT(-1) | OK |  |
| 型別轉換 | LREAL_TO_REAL | OK |  |
| 數值 | ABS | OK |  |
| 數值 | SQRT | OK |  |
| 數值 | LN | OK |  |
| 數值 | LOG | OK |  |
| 數值 | EXP | OK |  |
| 數值 | SIN | OK |  |
| 數值 | COS | OK |  |
| 數值 | TAN | OK |  |
| 數值 | ASIN | OK |  |
| 數值 | ACOS | OK |  |
| 數值 | ATAN | OK |  |
| 數值 | ATAN2(第 3 版附加) | MISSING | STError: line 5: unknown function ATAN2 |
| 算術 | ADD(函式形式) | MISSING | STError: line 5: unknown function ADD |
| 算術 | SUB | MISSING | STError: line 5: unknown function SUB |
| 算術 | MUL | MISSING | STError: line 5: unknown function MUL |
| 算術 | DIV(整數截斷) | MISSING | STError: line 5: unknown function DIV |
| 算術 | MOD(函式形式) | MISSING | STError: line 5: unexpected token 'MOD' |
| 算術 | MOD 運算子(負數) | OK |  |
| 算術 | EXPT | MISSING | STError: line 5: unknown function EXPT |
| 算術 | ** 運算子 | OK |  |
| 算術 | MOVE | MISSING | STError: line 5: unknown function MOVE |
| 算術 | INT 溢位繞回 | OK |  |
| 位移 | SHL WORD | OK |  |
| 位移 | SHL 中間值依型別截斷 | WRONG | 得到 False,應為 True |
| 位移 | SHR WORD | OK |  |
| 位移 | ROL WORD | OK |  |
| 位移 | ROL BYTE | WRONG | 得到 2,應為 3 |
| 位移 | ROR BYTE | WRONG | 得到 64,應為 192 |
| 位移 | ROL DWORD | WRONG | 得到 2,應為 3 |
| 位移 | ROR DWORD | WRONG | 得到 32768,應為 2147483648 |
| 位移 | ROL n ≥ 寬度 | MISSING | ValueError: negative shift count |
| 位元邏輯 | AND WORD | OK |  |
| 位元邏輯 | OR / XOR WORD | OK |  |
| 位元邏輯 | NOT BYTE | OK |  |
| 位元邏輯 | NOT 中間值依型別截斷 | WRONG | 得到 False,應為 True |
| 位元邏輯 | AND(函式形式) | MISSING | STError: line 5: unexpected token 'AND' |
| 位元邏輯 | NOT(函式形式) | OK |  |
| 選擇 | SEL | OK |  |
| 選擇 | MAX(多引數) | OK |  |
| 選擇 | MIN(多引數) | OK |  |
| 選擇 | LIMIT | OK |  |
| 選擇 | MUX | MISSING | STError: line 5: unknown function MUX |
| 比較 | 運算子 > >= = <> <= < | OK |  |
| 比較 | GT(函式形式,可多引數) | MISSING | STError: line 5: unknown function GT |
| 比較 | EQ(函式形式) | MISSING | STError: line 5: unknown function EQ |
| 比較 | GE/LE/LT/NE(函式形式) | MISSING | STError: line 5: unknown function NE |
| 比較 | 字串比較 | OK |  |
| 字串 | LEN | OK |  |
| 字串 | LEFT | OK |  |
| 字串 | RIGHT | OK |  |
| 字串 | MID | MISSING | STError: line 5: unknown function MID |
| 字串 | CONCAT(2 引數) | OK |  |
| 字串 | CONCAT(多引數) | MISSING | TypeError: <lambda>() takes 2 positional arguments but 3 were given |
| 字串 | INSERT | MISSING | STError: line 5: unknown function INSERT |
| 字串 | DELETE | MISSING | STError: line 5: unknown function DELETE |
| 字串 | REPLACE | MISSING | STError: line 5: unknown function REPLACE |
| 字串 | FIND | MISSING | STError: line 5: unknown function FIND |
| 字串 | STRING 長度上限 STRING(n) | MISSING | STError: line 3: expected ;, got '(' |
| 時間日期 | TIME + TIME | OK |  |
| 時間日期 | TIME * INT | OK |  |
| 時間日期 | TIME / INT | OK |  |
| 時間日期 | ADD_TIME / SUB_TIME | MISSING | STError: line 5: unknown function SUB_TIME |
| 時間日期 | MUL_TIME / DIV_TIME | MISSING | STError: line 5: unknown function MUL_TIME |
| 時間日期 | TIME 比較 | OK |  |
| 時間日期 | TOD# 常數 | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | TIME_OF_DAY# 常數 | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | D# 常數 | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | DT# 常數 | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | ADD_TOD_TIME | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | SUB_TOD_TOD | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | SUB_DATE_DATE | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | ADD_DT_TIME | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | CONCAT_DATE_TOD | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | DT_TO_TOD / DT_TO_DATE | MISSING | STError: line 5: unexpected character '#' |
| 時間日期 | LTIME# 常數 | MISSING | STError: line 5: unexpected character '#' |
| 基本型別 | LREAL / LINT | OK |  |
| 基本型別 | USINT / UDINT / ULINT | OK |  |
| 基本型別 | LWORD | MISSING | STError: unknown type LWORD for w |
| 基本型別 | CHAR | MISSING | STError: unknown type CHAR for c |
| 基本型別 | WSTRING | MISSING | STError: line 5: unexpected character '"' |
| 基本型別 | REAL 32 位元精度 | OK | IEC REAL 為 32 位元;兩邊皆轉為 REAL 時相等 |
| 標準 FB | TON | OK |  |
| 標準 FB | TOF | OK |  |
| 標準 FB | TP | OK |  |
| 標準 FB | CTU | OK |  |
| 標準 FB | CTD | OK |  |
| 標準 FB | CTUD | OK |  |
| 標準 FB | CTU_DINT / CTU_UDINT(型別化) | MISSING | STError: unknown type CTU_DINT for c |
| 標準 FB | R_TRIG | OK |  |
| 標準 FB | F_TRIG | OK |  |
| 標準 FB | SR | OK |  |
| 標準 FB | RS | OK |  |
| 標準 FB | TON 經過時間 ET | OK |  |
| 標準 FB | LTON / TON_LTIME(第 3 版) | MISSING | STError: unknown type LTON for t |
