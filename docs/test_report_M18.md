# M18 測試報告(使用者自訂 FUNCTION / FUNCTION_BLOCK)
日期:2026-11-03

## 單元測試
`python -m unittest discover -s tests` → 107 項全部 OK(新增 `tests/test_userpou.py` 8 項)。
- FUNCTION 回傳值、RETURN 提早離開、具名參數;FB 實例狀態跨掃描保存、多實例互不影響、內含 R_TRIG。
- 檢查器:乾淨程式無 error;多餘參數、不存在成員、POU 本體未宣告變數皆報錯。
- 遞迴超過深度 32 報錯;重複定義報錯;非 st 匯出遇自訂 POU 明確拒絕。

## CLI / UI 實測
- `check /tmp/u.st --profile siemens-s7-1500` 無錯誤;`run --cycles 2 --set go=1` 輸出 s=100.0、b=10(RETURN)、out1=True、cnt=1。
- Web UI(Node Playwright + Chromium):貼入含 FUNCTION/FUNCTION_BLOCK 程式 → 靜態檢查「✔ 無問題」,執行 80 週期,頁面無 JS 錯誤。截圖:`docs/screenshots/web_ui_userpou_M18.png`
- `tests/ui_smoke.py` 本次未重跑(環境無 Python playwright)。

## 已知限制
- VAR_IN_OUT 僅視為輸入(不回寫);PLCopen/SCL/L5X/GX/Sysmac 匯出尚不支援自訂 POU(僅 `--format st`)。
