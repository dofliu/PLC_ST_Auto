# UI6 測試報告:情境表格編輯器 + 匯出卡片(2026-11-12)

## 變更
- `plc_st/scenario.py`
  - 新增 `run_scenario_detail()`:逐步回傳 `{index, step, cycles, t_ms, set, checks:[{var, expected, actual, pass}], passed}`;執行期錯誤拋出 `STError` 並帶 `step_index`(出錯步驟,0 起算)。
  - `run_scenario()` 改為以 detail 結果彙整失敗清單(輸出格式不變,CLI / LLM 修正迴圈 / eval 不受影響)。
  - 更嚴格的步驟驗證:`ms` 須為非負數字、`cycles` 須為非負整數(拒絕 `true`、`1.5`、`"5"`),步驟須為物件。
- `plc_st/web.py`
  - `POST /api/test` 新增 `steps`(逐步結果),保留 `passed` / `failures`;錯誤時 400 並附 `step`。
  - 新增 `POST /api/export/status`:6 種格式(PLCopen / SCL / L5X / GX Works3 / Sysmac / 純 ST)各自是否可匯出、不支援原因、輸出字元數、對應廠牌 profile 的方言警告(含行號);語法錯誤時所有格式標示「語法錯誤」。
- `plc_st/web/index.html`
  - **測試頁**:情境「表格 / JSON」切換。表格欄位:步驟名稱、設定輸入(`變數=值; …`)、等待(ms 或週期)、預期輸出;上移/下移/刪除、新增步驟;掃描週期欄位。表格每次編輯即時同步成 JSON(`#scn` 仍是唯一來源,LLM 產生的情境閉環也讀它),JSON 切回表格時解析並帶入(格式錯誤則留在 JSON 模式並提示)。
  - 值格式:`TRUE`/`FALSE`、數字、`'文字'`;格式錯誤欄位紅框 + 說明,且不送出執行。
  - 變數晶片:從程式 `VAR_INPUT`(藍)/`VAR_OUTPUT`(綠)/內部變數擷取,點一下插入到目前欄位(輸入預設 `=TRUE`)。
  - 執行後每步驟下方顯示 ✔/✘、累計時間 `@t ms`、每個預期變數的實際值與預期值;執行期錯誤標在出錯的那一步。狀態列顯示 `情境 PASS n/n`。
  - **匯出頁**:改為 6 張廠牌卡片(取代下拉選單),顯示「✔ 可匯出 / ⚠ n 警告 / ✘ 不支援」、目標軟體、副檔名、大小;不支援時列出原因並停用下載;方言警告可展開,點擊跳到程式對應行;「預覽」顯示前 80 行。開啟頁籤時與程式變更後(700ms 防抖)自動更新。
  - 程式化設定程式碼(產生、載入、點位表)會觸發 `codeset` 事件,讓變數晶片與匯出卡片同步更新。

## 測試
- 單元測試:`python -m unittest discover -s tests` → **258 項 OK(7 略過)**;新增 `tests/test_ui6.py` 9 項(逐步結果與累計時間、與舊 API 相容、錯誤步驟索引、非法等待值、`/api/test` steps 與錯誤 step、匯出狀態:全部可匯出 / L5X 方言警告行號 / STRUCT 不支援原因 / 語法錯誤 / 缺參數 400)。
- E2E `tests/ui_e2e.js`:**94/94 PASS**(原 76 項 + UI6 18 項;07 匯出改用卡片下載按鈕、10 改為以 PASS 開頭、11 先切到 JSON 模式):
  - 41 變數晶片分色;42 不寫 JSON:新增步驟、點晶片、填表 → JSON 即時同步
  - 43 逐步結果(步驟 1 通過、步驟 2 cnt 失敗並顯示預期值);43b 狀態列 FAIL;44 修正後 2/2 通過
  - 45 格式錯誤紅框與說明;45b 有錯誤不執行;46 上移;46b 刪除
  - 47 JSON → 表格帶入步驟/掃描週期/單位;47b JSON 錯誤時留在 JSON 模式;48 執行期錯誤標在第 2 步
  - 49 6 張卡片皆可匯出;49b L5X 顯示警告數;49c 點警告跳到第 4 行;50 SCL 預覽
  - 51 程式改為 STRUCT 範例後卡片自動更新:GX Works3 不支援並顯示原因、下載停用,L5X 仍可匯出
  - 52 測試/匯出頁整頁無垂直捲動;既有 14 手機 390px 無水平捲動、15 全程無 JS 錯誤
- 截圖 `docs/screenshots/ui6/`:`scenario_table_fail.png`、`scenario_table_pass.png`、`export_cards.png`、`export_unsupported.png`、`dark_scenario.png`、`dark_export.png`。

## 已知/後續
- `tests/ui_smoke.py` 是 UI1 之前的舊版腳本(需要 Python Playwright,本環境未安裝,且使用已移除的 `#expfmt`),已由 `tests/ui_e2e.js` 取代。
- 變數晶片以前端正規表示式擷取宣告,FB 實例成員(如 `t.Q`)需手動輸入。
- 下一步 UI5:產生流程時間軸、各輪修正 diff、點位表表格預覽。
