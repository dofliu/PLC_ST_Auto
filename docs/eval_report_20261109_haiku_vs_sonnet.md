# Haiku vs Sonnet 對照評測(使用者本機執行)
日期:2026-11-09 14:50 執行者:使用者本機 指令:`python -m plc_st eval --provider claude --model claude-haiku-5-5 --model claude-sonnet-5-5 --repeat 3`
工具版本:M30(main `154a831`) 每案重複 3 次 自動修正上限 2 輪

## 原始結果

| 模型 | 通過 | 通過率 | 一次正確 | 平均修正輪數 | 平均秒數 | API 呼叫 | 輸入 token | 輸出 token |
|---|---|---|---|---|---|---|---|---|
| `claude-haiku-5-5` | 38/42 | 90% | 30/42 | 0.21 | 10.6 | 55 | 30,888 | 88,654 |
| `claude-sonnet-5-5` | 42/42 | 100% | 38/42 | 0.10 | 6.6 | 46 | 18,949 | 33,937 |

各案例:兩個模型在 TC-01..07、10..14 皆 3/3;Haiku 的 TC-08、TC-09 各 1/3,Sonnet 全部 3/3。

## 第 0 輪錯誤歸類(Claude 分析)

逐一驗證錯誤訊息中的語法後,多數「第 0 輪錯誤」是**本專案檢查器不支援合法 IEC 語法**,不是模型寫錯:

| 錯誤訊息 | 推定寫法 | IEC 合法? | 次數(Haiku / Sonnet) |
|---|---|---|---|
| `unexpected character '#'` | `INT#5`、`16#FF` 等型別前綴/進位常數 | ✅ | 8 / 0 |
| `expected ], got '('` | 陣列重複初值 `[5(0.0)]` | ✅ | 1 / 1 |
| `unknown function DINT_TO_TIME` / `INT_TO_TIME` | 標準轉換函式(第 1 輪,被迫改寫後出現) | ✅ | 2 / 0 |
| `CTU has no input RESET` | CTU 輸入應為 `R` | ❌ 模型錯誤 | 2 / 0 |
| `expected :, got 'VAR_OUTPUT'` / `'END_PROGRAM'` | 未知(第 0 輪程式碼未保存) | 待查 | 0 / 3 |

→ 排除誤判後,Haiku 的「一次正確」可能接近 Sonnet;需修正檢查器(M31)後重跑才能確認。

## 真正失敗:Haiku `unknown variable stop` ×4
TC-08 run1/run2、TC-09 run1/run2:最終程式沒有名為 `stop` 的變數(推測改名為 `stop_btn` 等)。其中 3 次第 0 輪先被誤判 `'#'`,可能是被迫改寫時一併改名。需要使用者本機 `eval_out/<時間>/claude-haiku-5-5/run{1,2}/tc0{8,9}.st` 才能確認(目前使用者暫時無法本機執行)。

## 其他觀察
- Haiku 輸出 token 為 Sonnet 的 2.6 倍,平均耗時也較長;總費用需以 `--price` 填入官方單價比較。
- 評測工具只保存最終程式碼,無法回查第 0 輪原始輸出 → M31 改為保存每一輪程式碼。
