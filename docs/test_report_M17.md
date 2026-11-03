# M17 測試報告(ARRAY 一維陣列)
日期:2026-11-03

## 單元測試
`python -m unittest discover -s tests` → 99 項全部 OK(新增 `tests/test_array.py` 7 項)。
- 宣告/初始值/FOR 迴圈累加、元素寫入、`snapshot` 展開 `buf[i]`、`set_input("buf[0]")`。
- 執行期越界、上下界顛倒報錯;靜態檢查:常數索引越界、陣列未加索引、非陣列被索引。
- PLCopen XML 匯出可被 XML 解析,含 `<dimension lower upper>` 與逐元素初始值。
- 順手修正:新增 `..` 詞法記號,CASE 範圍標籤改用之(原有 CASE 測試仍通過)。

## CLI 實測
`python -m plc_st run a.st --cycles 1` → 欄位 `buf[0],buf[1],buf[2]`,值 2,4,0(第三格預設 0)。

## UI 功能測試
環境無法安裝 Python playwright(pip 逾時),改以預裝 Node Playwright + Chromium 對 `serve` 實測(`tests/ui_smoke.py` 本次未重跑,M16 為 13/13 PASS,本次未改動 UI):
- 貼入含 `ARRAY[0..4] OF INT` 的程式 → 靜態檢查「✔ 無問題」。
- 執行 3 週期 → 狀態「3 週期」,波形畫布有繪製,頁面無 JS 錯誤。
- 截圖:`docs/screenshots/web_ui_array_M17.png`

## 已知限制
- 僅一維;多維與 STRUCT 列入下一步。非 PLCopen 的廠牌匯出不轉換陣列語法。
