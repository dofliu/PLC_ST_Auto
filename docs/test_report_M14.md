# M14 測試報告(Mitsubishi GX Works3 匯出 + Web UI embedder 選項)
日期:2026-11-01

## 單元測試
`python -m unittest discover -s tests` → 89 項全部 OK(新增 3 項)。
- `gxworks` 匯出:標籤表(Class/Label Name/Data Type/Initial Value,Tab 分隔)與 ST 本體;BOOL→Bit、INT→Word [Signed] 等對映。
- `/api/export format=gxworks`、`/api/rag/add` 的 `embedder`(hash 可用;與現有索引不同或未知 embedder → 400;清空後可重選)。

## UI 功能測試(Playwright + Chromium)
12 項全部 PASS(新增:匯出 GX Works3 下載、RAG embedder 選擇 hash)。截圖:`docs/screenshots/web_ui.png`

## 已知限制
- GX Works3 輸出為標籤表 + ST 本體文字,未在真實 GX Works3 匯入驗證;Timer/Counter FB 實例型別需人工確認。
- 遠端 embedding 仍僅以 mock transport 測試。

## M14 修補(合併後回報的問題)
- GX Works3 匯出:原本把 LINT 對映為 32 位元 Double Word,可能改變數值 → 現在 LINT/ULINT 直接拒絕匯出(STError),不再靜默降位元。
- RAG embedder:規格相同但更換 API Key 時未生效 → 現在更新現有 embedder 的金鑰。
- 空索引切換 embedder(含切回 TF-IDF)未重設 → 現在空索引時直接重建 store。
- 新增 3 項測試,共 91 項 OK。
- 仍存在(未處理):L5X 匯出的 UDINT→DINT、DWORD→DINT、LREAL→REAL 亦為有損對映,列入 M15。
