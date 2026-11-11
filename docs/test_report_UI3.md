# UI3 測試報告:程式碼編輯器(行號、ST 語法色彩、問題行標記、跳行、快捷鍵)(2026-11-11)

## 變更
- `plc_st/web/index.html`
  - **編輯器**:`<textarea id="code">` 疊在上色層 `#hl` 之上(透明文字、保留原生游標/選取/IME/復原),左側行號 `#gutter`;三者捲動同步。元素 ID 與 `.value` 用法不變,其他功能不需改。
  - **ST 語法色彩**:關鍵字、資料型別與 `*_TO_*`、標準 FB(TON/CTU/R_TRIG…)、數值/時間/型別前綴常數(`T#500ms`、`16#FF`、`INT#5`)、字串、`(* *)`/`//` 註解、運算子;亮/暗主題各一組 token。
  - **自動檢查與行標記**:輸入停止 700ms 後背景呼叫 `/api/check`(不跳 toast、不展開抽屜,舊請求結果會被丟棄),錯誤/警告行在行號顯示紅/黃點、程式行底色 + 波浪底線,滑鼠停在行號可看訊息;狀態列與抽屜摘要同步。切換 profile 也會重新檢查。
  - **跳行**:問題清單中有行號的項目改為按鈕,點擊後選取該行、捲動到可視範圍並閃爍提示;點行號亦可。模擬執行期錯誤訊息若含 `line N` 也會標記。
  - **快捷鍵**:`Ctrl+Enter` 執行模擬(切到模擬頁)、`Ctrl+Shift+Enter` 靜態檢查、`Ctrl+/` 註解切換、`Tab`/`Shift+Tab` 縮排/取消縮排、`THEN/DO/OF/ELSE/VAR…` 後 Enter 自動縮排;編輯走 `execCommand('insertText')`,`Ctrl+Z` 可復原。按 `Esc` 後 Tab 可離開編輯器(避免鍵盤受困)。
  - 程式化設定 `.value`(LLM 產生、點位表 → VAR、載入 .st)會重繪並清除舊標記後重新檢查。
  - 編輯器下方顯示游標「行/欄」與快捷鍵說明。
- `plc_st/checker.py`:語法錯誤原本 `line=0`(行號只在訊息文字裡),改為帶出行號,訊息改為 `syntax: <原因>`(`str()` 仍顯示 `line N:`,不重複)。

## 測試
- 單元測試:`python -m unittest discover -s tests` → **239 項 OK(7 略過)**;`test_syntax_error` 新增行號斷言。
- E2E `tests/ui_e2e.js` 新增 UI3 檢查 20 項,總計 **57/57 PASS**(含既有 01–22:無捲動版面、對比、主題、390px 手機、全程無 JS 錯誤):
  - 23 行號數 = 程式行數;23b 語法色彩類別齊全;23c 上色層與輸入框字型/行高/內距/white-space 完全一致(游標不錯位)
  - 24 輸入後自動檢查標記第 4 行;24b 不跳 toast、不展開抽屜;24c 狀態列/抽屜摘要更新
  - 25 點問題跳到第 4 行並選取整行;25b 游標顯示「行 4」
  - 26 語法錯誤(缺 END_IF)標記於第 5 行
  - 27 THEN 後自動縮排;27b/c Ctrl+/ 註解/取消;27d/e Tab/Shift+Tab;27f Ctrl+Z 復原;27g Esc 後 Tab 離開
  - 28 Ctrl+Enter 切到模擬並執行
  - 29 202 行程式跳到第 180 行,輸入框/上色層/行號 scrollTop 一致(3407px);29b 該行可見
  - 30 點位表產生程式後行號重繪
- 截圖 `docs/screenshots/ui3/`:`editor_error_marked.png`、`editor_jump_to_issue.png`、`editor_long_jump.png`、`light_editor.png`、`dark_editor.png`。

## 已知/後續
- 很長的單行(>畫面寬)仍可水平捲動,上色層同步;不做自動換行(與行號對齊較單純)。
- 程式很大時(數千行)每次輸入整份重新上色,目前範例皆 <300 行無感;如需要再改為只重繪可視範圍。
- 下一步 UI4:模擬儀表板(執行/暫停/單步、I/O 開關與燈號、波形標籤重疊與 STRING 顯示)。
