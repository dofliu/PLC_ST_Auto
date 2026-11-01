# M13 測試報告(可替換 embedding + Rockwell L5X)
日期:2026-11-01

## 單元測試
`python -m unittest discover -s tests` → 全數 OK(新增 `test_embed.py` 5 項、`test_export.py` L5X 2 項)。
- embedding:hash 離線向量檢索、OpenAI/Ollama/Gemini 回應格式解析(transport 注入)、錯誤處理、cosine、索引持久化(含 embedder 規格)與 CLI `index --embedder hash`。
- L5X:XML 可解析、TIMER 型別對映、Usage(Input/Local)、ST Routine 行內容、CDATA 終止符跳脫。

## UI 功能測試(Playwright + Chromium)
全部 PASS,新增「匯出 Rockwell L5X 下載」。截圖:`docs/screenshots/web_ui.png`

## 已知限制
- L5X 未在真實 Studio 5000 匯入驗證;FB 呼叫語法(TON 等)需於 Logix 端人工調整。
- 遠端 embedding 未以真實 API 測試(僅 mock transport);Web UI 尚未提供 embedder 選項。
- Mitsubishi GX Works 匯出尚未支援(列入 M14)。
