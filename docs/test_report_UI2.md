# UI2 測試報告:視覺系統(設計 token、亮/暗主題、元件、SVG 圖示、toast)(2026-11-10)

## 變更(`plc_st/web/index.html`)
- **設計 token**:字型、字級、間距、圓角、陰影、色彩(bg/surface/surface-2/fg/fg-muted/bd/ac/ok/er/wn 與各自淡底色)統一定義於 `:root`。
- **亮/暗主題**:跟隨系統(`prefers-color-scheme`),並可用頂列按鈕循環「自動 → 亮色 → 暗色」;`data-theme` 在繪製前套用避免閃爍。
  `localStorage` 只存 `plcst.theme`(不含任何 API key,E2E 驗證)。切換主題時波形圖依 token 重繪。
- **元件**:主要/次要/ghost 按鈕(hover、focus-visible 焦點框、**執行中 spinner + disabled**)、輸入框 focus ring、檔案選擇器樣式、核取方塊、卡片(各頁籤內容改成卡片)、狀態 pill 淡底色、空狀態(波形尚未執行)。
- **內嵌 SVG 圖示**(sprite,離線、無 CDN):頁籤、標題、按鈕、主題、toast。
- **Toast**:檢查/模擬/情境/匯出/產生/RAG/載入檔案完成或失敗時右下角提示(`aria-live`,錯誤用 `role=alert`),最多 4 則。
- 尊重 `prefers-reduced-motion`;補上 `[hidden]{display:none!important}` 修正 `display` 覆蓋 `hidden` 的問題。
- 元素 ID、後端 API、CLI 不變。

## 測試
- 單元測試:`python -m unittest discover -s tests` → **239 項 OK(7 略過)**。
- E2E `tests/ui_e2e.js` 新增 UI2 檢查,**37/37 PASS**:
  - 16 亮色主題 18 組文字/背景對比 **最低 5.42:1**、暗色 **最低 6.06:1**(WCAG AA 4.5:1)
  - 17 主題套用到 body 背景(亮/暗)
  - 18 操作完成顯示 toast
  - 19 主題按鈕 auto→light→dark 且重新整理後保留
  - 20 localStorage 只存主題
  - 21 執行中按鈕顯示載入狀態、完成後恢復
  - 22 波形繪製後空狀態提示隱藏
  - 既有 01–15(含 1280×800 / 1920×1080 無捲動、390px 無水平捲動、全程無 JS 錯誤)全過
- 截圖:`docs/screenshots/ui2/`(`light_*.png`、`dark_*.png` 各 6 頁籤,其餘沿用 E2E 流程截圖)。

## 已知/後續
- 波形標籤字小、訊號多時擁擠、STRING 顯示 → UI4。
- 錯誤行標記、問題列表跳行 → UI3(下一個)。
