# UI7 測試報告:響應式、可拖曳分欄、設定記憶、無障礙(2026-11-14)

UI 改版最後一個里程碑(見 `docs/ui_redesign_plan.md`)。只改前端 `plc_st/web/index.html`,後端 API 不變。

## 變更
- **可拖曳分欄**:程式碼欄與頁籤欄之間加入 `#split`(`role="separator"`、`aria-valuenow` 25–75%)。滑鼠/觸控拖曳、鍵盤 ←/→(Shift ×5 步距)、Home/End、雙擊或 Enter 還原 50%;拖曳時波形即時重繪。
- **手機/平板(≤820px)**:左側頁籤改為固定底部導覽列(7 鍵:程式碼 + 6 頁籤,每鍵 52px 高),程式碼與頁籤內容一次顯示一個,整頁不捲動;狀態列改單行橫向捲動;頂列隱藏副標與主題文字。點問題清單時自動切回編輯器並定位(修正:原本先 focus 再切換,隱藏中的 textarea 無法取得焦點)。
- **設定記憶**:`localStorage`(前綴 `plcst.`)記住 provider、model、base URL、修正輪數、RAG/情境勾選、embedder、掃描週期、批次週期、廠牌 profile、最後頁籤、分欄寬度、程式碼草稿。**`key`、`embkey` 列在 `MEM_NEVER`,永不儲存**。設定頁新增「介面記憶」卡片:可關閉「記住程式碼草稿」(立即刪除草稿)、「清除記憶」(保留主題)。
- **無障礙**:`跳到程式碼編輯器` skip link(第一個 Tab)、問題抽屜標題改為 `role="button"` + `aria-expanded` + Enter/空白鍵、頁籤按鈕加 `aria-keyshortcuts`。

## 測試
- 單元測試:`python -m unittest discover -s tests` → **274 項 OK(7 略過)**;新增 `tests/test_ui7.py` 5 項(金鑰不在記憶清單、記憶的 id 都存在、分欄 ARIA、手機導覽與 skip link、抽屜鍵盤屬性);`test_web.UiLayout` 改為檢查新的 `minmax(0,var(--lw,1fr))` 欄寬。
- E2E `tests/ui_e2e.js`:**124/124 PASS**(原 108 + UI7 16 項;第 20 項改為「只用 `plcst.` 前綴且不含 API key」):
  - 72 拖曳分欄 595→797px;73 鍵盤 ←=-2%、End=75%,範圍限制、無整頁捲動;74 雙擊還原 50%
  - 75 重新整理後還原 provider/model/輪數/base/profile/週期/分欄 56%/頁籤 模擬/程式碼草稿,狀態列顯示 `LLM:mock·mem-model`
  - 76 API Key 輸入後重新整理為空,localStorage 任何值都找不到該字串
  - 77 取消記住程式碼即刪草稿;清除記憶後回到預設
  - 78 無障礙稽核:所有 button/input/select/textarea/separator/switch/img/canvas 有可讀名稱,無重複 id,`lang="zh-Hant"`
  - 79 第一個 Tab 為 skip link、Enter 進入編輯器;抽屜 Enter/空白鍵開關且 `aria-expanded` 同步
  - 80 390px:導覽列貼齊底部、7 鍵 ≥44px、預設顯示頁籤內容、無分欄把手、無整頁捲動;81/81b 程式碼⇄頁籤切換與目前頁標示;82 點問題自動切到編輯器並定位
  - 83 390×844 / 768×1024 / 1280×800 / 1920×1080 皆無水平/垂直整頁捲動
- 截圖 `docs/screenshots/ui7/`:`mobile_390.png`、`mobile_390_gen.png`、`mobile_390_code.png`、`mobile_390_sim.png`、`mobile_390_jump.png`、`tablet_768.png`、`desktop_1280.png`、`desktop_1920.png`、`split_75.png`、`settings_memory.png`。README 加入桌機/手機截圖。

## 限制
- 寬螢幕同時顯示兩個頁籤(規劃中的選配)未做,列入下一步候選。
- 對比度沿用 UI2 的 WCAG AA 檢查;此次未引入 axe-core(離線、無 npm 相依原則),以自訂稽核取代。
- 雲端環境仍無 LLM 金鑰,真實 provider 未實測。
