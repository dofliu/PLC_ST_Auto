# UI5 測試報告:產生流程時間軸 + 修正輪差異 + 點位表預覽(2026-11-12)

## 變更
- `plc_st/llm.py`:新增 **`mock` provider(離線示範)**——不連網、不需金鑰。依 prompt 中的點位表宣告變數,產生自保持程式;初稿故意引用未宣告的 `alarm_lamp`,修正輪補上宣告,用來在沒有 API 金鑰時展示/測試「產生 → 檢查 → 修正」流程。CLI `generate --provider mock` 也可用。
- `plc_st/web.py`
  - `POST /api/generate` 新增 `timeline`:每輪(含初稿)的 `round`、`code`、`issues`、`errors`、`warnings`、`ms`,以及 `provider`、`model`。
  - 新增 `POST /api/tags/preview`:不中斷的點位表預覽,逐列回傳 `line / name / type / direction / section / init / comment / error`;檢查缺 name、非法識別字、名稱重複(不分大小寫)、direction 錯誤、缺 type。
- `plc_st/tags.py`:`preview_tags()`。
- `plc_st/web/index.html`(產生頁)
  - **點位預覽**:貼上或上傳 CSV 後 250ms 內顯示表格,依方向統計(輸入/輸出/輸入輸出/內部),錯誤列標紅並寫出原因。
  - **產生流程卡片**:垂直時間軸,每輪顯示 ✘ n 錯 / ✔ 通過、耗時、行數、前 3 個錯誤訊息;總結徽章(「經 n 輪修正後通過」或「仍有 n 個錯誤」)。
  - **修正輪差異**:LCS 行差異,雙欄行號、+/− 上色、未變更行收合為「⋯ n 行未變更」;產生後自動顯示最後一輪差異,每輪可點「差異」或「套用」(把該輪程式碼放回編輯器並標出錯誤行)。
  - 新增勾選「以『測試』頁情境驗證並修正」(預設勾選,行為與之前相同):先前產生時一律送出測試頁情境,使用者看不出來;現在可以關閉。
  - 設定頁 Provider 多一個「mock(離線示範)」選項。

## 測試
- 單元測試:`python -m unittest discover -s tests` → **269 項 OK(7 略過)**;新增 `tests/test_ui5.py` 11 項(mock 一輪修正、使用點位表、max_rounds=0、單一輸入/無 BOOL 輸出;API 時間軸、搭配情境、未知 provider 400;點位預覽正常/逐列錯誤/空輸入/與 parse_tags 一致)。
- E2E `tests/ui_e2e.js`:**108/108 PASS**(原 94 項 + UI5 14 項):
  - 60 點位表即時預覽 4 列與分組;61 重複/非法名稱/缺型別逐列標紅;62 上傳檔案也更新預覽
  - 63 狀態列 LLM:mock;64 時間軸 初稿 ✘ 1 錯 → 第 1 輪 ✔;65 列出錯誤訊息與行號
  - 66 自動顯示差異 +1 −0、新增行標綠;67 編輯器為最終程式碼;68 套用初稿並標錯誤行;69 差異選取該輪
  - 69b 取消情境驗證時不送情境;69c 勾選時情境錯誤顯示在每一輪;70 修正輪數 0 只有初稿且不顯示差異
  - 71 產生頁整頁無垂直捲動;既有 14 手機無水平捲動、15 全程無 JS 錯誤
- 過程中發現:E2E 第一次跑時 mock 修正 3 輪都失敗——原因是產生時一律帶入測試頁的 motor 情境(要求 `t.Q`),時間軸正確顯示了這個原因;據此加入情境驗證勾選框,讓這個耦合看得見、可關閉。
- 截圖 `docs/screenshots/ui5/`:`timeline_diff.png`、`dark_timeline.png`、`tag_preview_errors.png`、`mobile_timeline.png`。

## 限制
- 時間軸在整個產生完成後才顯示(非串流);真實 LLM 每輪耗時仍會正確記錄。
- 雲端環境仍無 LLM 金鑰,真實 provider 的時間軸未實測(mock 走同一條程式路徑)。
