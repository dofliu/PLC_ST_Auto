# M11 測試報告(Web UI)
日期:2026-10-30

## 單元/整合測試
`python -m unittest discover -s tests` → 74 tests OK(新增 `tests/test_web.py` 8 項:API check/run/test/tags/RAG/錯誤處理/HTTP 往返)。

## UI 功能測試(Playwright + Chromium,`tests/ui_smoke.py`)
| 項目 | 結果 |
|---|---|
| 載入廠牌 profile 清單 | PASS |
| 靜態檢查通過(motor.st) | PASS |
| 虛擬 PLC 執行 80 週期 | PASS |
| 波形繪製 | PASS |
| 情境測試 PASS | PASS |
| RAG 上傳文件 + 搜尋 | PASS |
| 檢查回報錯誤(未宣告變數) | PASS |
| 無 LLM 時產生錯誤正確顯示 | PASS |
| 無 JS 例外 | PASS |

截圖:`docs/screenshots/web_ui.png`

## 已知限制
- 未以真實 LLM 金鑰測試(僅驗證錯誤路徑);provider 邏輯由 test_llm 以 mock 涵蓋。
- UI 僅綁定 127.0.0.1,無認證;勿對外開放。
