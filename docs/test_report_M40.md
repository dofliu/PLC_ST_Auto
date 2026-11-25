# M40 測試報告:產生流程串流顯示

日期:2026-11-25 · 分支 `claude/lucid-fermat-2yorto`

## 變更
| 檔案 | 內容 |
|---|---|
| `plc_st/web.py` | `_generate(p, state, emit)` 於開始/每輪完成時送出事件;`generate_stream()` 轉成 NDJSON;HTTP `POST /api/generate/stream`(無 Content-Length、逐行 flush、結束關閉連線);寫入失敗(用戶端斷線)→ `Cancelled`,不再進行下一輪 LLM 呼叫 |
| `plc_st/llm.py` | mock provider 的 model 以 `-slow` 結尾時每次呼叫延遲 0.8 s(示範/測試串流用) |
| `plc_st/web/index.html` | `gen()` 讀取串流:進行中列(初稿產生中 / 第 n 輪修正中,旋轉圓點)、每輪即更新編輯器/錯誤標記/問題抽屜、狀態列「LLM 產生中 k/N」、「■ 停止」按鈕(AbortController,保留已完成輪次、標示「已停止」)、時間軸自動捲到進行中列、串流端點 404 時退回 `/api/generate` |
| `tests/ui_e2e.js` | 測試 70 的等待條件改為只算完成的輪次(進行中列也是 `li`) |

## 事件格式(每行一個 JSON)
```
{"type":"start","provider":"mock","model":"demo","max_rounds":3,"rag_passages":0}
{"type":"round","round":0,"code":"…","issues":[…],"errors":1,"warnings":0,"ms":801,"more":true}
{"type":"round","round":1,…,"errors":0,"more":false}
{"type":"done","code":"…","issues":[],"rounds":1,"timeline":[…不含 code…],"provider":"mock","model":"demo"}
{"type":"error","status":400,"error":"STError: …"}   ← 失敗時取代 done
```
`more=true` 表示還有錯誤且未用完修正輪數,UI 據此顯示「第 n 輪修正中」。

## 測試結果
| 項目 | 結果 |
|---|---|
| 單元測試全部(`python -m unittest discover -s tests`) | 478 項 OK(10 skipped,缺 lxml 等選用套件) |
| `tests/test_m40.py` | 10/10:事件順序、`more` 旗標、每行一個 JSON、錯誤事件、與非串流結果一致、斷線後不再呼叫 LLM、慢速 mock、**真實 HTTP 下初稿事件比 done 早 ≥0.5 s 到達**、非串流 API 不受影響、錯誤 JSON 400 |
| `tests/ui_m40.js`(Playwright) | 19/19 |
| `tests/ui_e2e.js` | 130/130(4 次執行中有 1 次 128/130,當次只保留了總數,其後 3 次重跑皆全過,判斷為時序不穩;下次排程若重現再追查) |
| `tests/ui_ui8.js` / `ui_m39.js` / `ui_m38.js` | 22/22、14/14、10/10 |

### E2E 明細(`docs/screenshots/m40/results.json`)
M40-01 停止鈕預設隱藏 · 02 送出後立即顯示「初稿產生中」· 03 狀態列顯示產生中 · 04 初稿完成即顯示 ✘1 錯並接著「第 1 輪修正中」· 05 編輯器已是初稿 · 06 進度文字 · 07 完成 2 輪且無進行中列 · 08 按鈕恢復、編輯器為修正版 · 09 差異面板 · 10 狀態列恢復 · 11 停止後保留初稿並標示已停止 · 12b 停止後問題抽屜顯示最後一輪錯誤 · 12c 時間軸最後一列在可視範圍 · 12 按鈕恢復 · 13 停止後無遲到事件 · 14 LLM 連線錯誤顯示 · 15 串流端點 404 退回一次性 API · 16 手機寬度無水平捲動 · 17 無 JS 錯誤

## 截圖(`docs/screenshots/m40/`)
| 檔案 | 畫面 |
|---|---|
| `01_pending_draft.png` | 送出後「初稿產生中…」 |
| `02_streaming_round1.png` | 初稿已顯示(✘ 1 錯,編輯器標記第 14 行),「第 1 輪修正中…」 |
| `03_stream_done.png` | 完成:經 1 輪修正後通過 + 差異 |
| `04_stopped.png` | 按下停止:保留初稿、標示已停止 |
| `05_error_event.png` | Ollama 無法連線的錯誤 |
| `06_dark_streaming.png` | 暗色主題串流中 |
| `07_mobile_streaming.png` | 手機寬度串流中 |

## 已知限制 / 後續
- 串流單位是「一輪」;LLM 回應本身(token 級)尚未串流 → 已列入 todo 候選。
- 停止只能在兩次 LLM 呼叫之間生效:正在進行中的那次 HTTP 呼叫會跑完(結果丟棄)。
