# M12 測試報告(匯出)
日期:2026-10-31

## 單元測試
`python -m unittest discover -s tests` → 79 tests OK(新增 test_export 4 項、test_web 匯出 1 項:PLCopen XML 格式正確且可解析、XML 跳脫(`<` `>`)、SCL 外框、錯誤格式/無 PROGRAM 報錯)。

## UI 功能測試(Playwright + Chromium)
全部 PASS(含新增「匯出 PLCopen XML 下載」:檔名 program.xml 且含 `<pou`)。截圖:`docs/screenshots/web_ui.png`

## 已知限制
- 匯出為文字層級切分,僅支援單一 PROGRAM;未在真實 CODESYS/TIA 匯入驗證。
- Rockwell L5X、Mitsubishi 專有格式尚未支援(M13)。
