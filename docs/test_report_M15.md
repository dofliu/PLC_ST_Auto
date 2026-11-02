# M15 測試報告(Omron Sysmac Studio 匯出 + README 匯出說明)
日期:2026-11-02

## 單元測試
`python -m unittest discover -s tests` → 91 項全部 OK(新增 2 項)。
- `sysmac` 匯出:變數表(Name/Data Type/Initial Value/Class,Tab 分隔)與 ST 本體;Input/Internal 類別對映。
- `/api/export format=sysmac`。

## UI 功能測試(Playwright + Chromium)
13 項全部 PASS(新增:匯出 Sysmac 下載)。截圖:`docs/screenshots/web_ui.png`

## 已知限制
- Sysmac 輸出為變數表 + ST 本體文字,未在真實 Sysmac Studio 匯入驗證;FB 實例型別需人工確認。
- 遠端 embedding 仍僅以 mock transport 測試。
