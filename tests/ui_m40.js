// M40 UI 測試:串流產生 —— 每輪完成即更新時間軸、進行中列、停止按鈕、錯誤事件、舊 API 後援。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m40.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const S = path.resolve(process.argv[2] || 'docs/screenshots/m40') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push({ name: n, pass: !!c, detail: d }); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const shot = async (f) => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.waitForTimeout(150); await pg.screenshot({ path: S + f }); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const ready = () => pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.goto(URL0); await ready();
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
  await pg.reload(); await ready();

  await pg.fill('#req', '按下 start 馬達啟動並自保持,按下 stop 停止;停止時亮警示燈');
  await pg.fill('#tags', fs.readFileSync('examples/points.csv', 'utf8'));
  await T('set'); await pg.selectOption('#prov', 'mock'); await pg.fill('#model', 'demo-slow'); await pg.fill('#rounds', '3'); await T('gen');
  await pg.evaluate(() => { document.getElementById('usescn').checked = false; });  // 不做情境驗證(預設情境引用 t.Q)
  ok('M40-01 停止按鈕預設隱藏', await pg.isHidden('#genstop'));

  // ---- 1. 串流:初稿中 → 初稿完成 + 第 1 輪修正中 → 完成 ----
  await pg.click('#genbtn');
  await pg.waitForSelector('#gentl li.pend');
  ok('M40-02 送出後立即顯示「初稿產生中」進行中列', (await pg.innerText('#gentl li.pend')).includes('初稿產生中') && await pg.isVisible('#genstop') && await pg.isDisabled('#genbtn'));
  ok('M40-03 狀態列 LLM 顯示產生中', (await pg.innerText('#st_llm')).includes('產生中'));
  await shot('01_pending_draft.png');
  await pg.waitForFunction("document.querySelectorAll('#gentl li[data-k]').length===1");
  const mid = await pg.innerText('#gentl');
  ok('M40-04 初稿完成即顯示(✘ 1 錯),下一列為「第 1 輪修正中」', mid.includes('初稿') && mid.includes('✘ 1 錯') && (await pg.innerText('#gentl li.pend')).includes('第 1 輪修正中'), mid.replace(/\n/g, ' ').slice(0, 140));
  ok('M40-05 編輯器已放入初稿程式碼(尚未結束)', (await pg.inputValue('#code')).includes('alarm_lamp := NOT') && !(await pg.inputValue('#code')).includes('alarm_lamp : BOOL'));
  ok('M40-06 進度文字顯示已完成輪數', (await pg.innerText('#genst')).includes('第 1 輪修正中') && (await pg.innerText('#genst')).includes('已完成 1 輪'));
  await shot('02_streaming_round1.png');
  await pg.waitForFunction("document.getElementById('genst').textContent.includes('完成(')", null, { timeout: 15000 });
  const fin = await pg.innerText('#gentl');
  ok('M40-07 完成後 2 輪、無進行中列、標示經 1 輪修正後通過', (await pg.locator('#gentl li[data-k]').count()) === 2 && (await pg.locator('#gentl li.pend').count()) === 0 && fin.includes('經 1 輪修正後通過'));
  ok('M40-08 完成後停止鈕隱藏、產生鈕恢復、編輯器為修正版', await pg.isHidden('#genstop') && !(await pg.isDisabled('#genbtn')) && (await pg.inputValue('#code')).includes('alarm_lamp : BOOL'));
  ok('M40-09 差異面板自動顯示最後一輪', await pg.isVisible('#gendiff') && (await pg.innerText('#gendiffh')).includes('第 1 輪'));
  ok('M40-10 狀態列 LLM 恢復為 provider·model', (await pg.innerText('#st_llm')).includes('mock·demo-slow'));
  await shot('03_stream_done.png');

  // ---- 2. 停止:初稿完成後按停止,保留 1 輪 ----
  await pg.click('#genbtn');
  await pg.waitForFunction("document.querySelectorAll('#gentl li[data-k]').length===1 && !!document.querySelector('#gentl li.pend')");
  await pg.click('#genstop');
  await pg.waitForFunction("document.getElementById('genst').textContent.includes('已停止')");
  const st = await pg.innerText('#gentl');
  ok('M40-11 停止後保留已完成的初稿、標示已停止、無進行中列', (await pg.locator('#gentl li[data-k]').count()) === 1 && st.includes('已停止') && (await pg.locator('#gentl li.pend').count()) === 0, st.replace(/\n/g, ' ').slice(0, 120));
  ok('M40-12b 停止後問題抽屜顯示最後一輪的錯誤', (await pg.innerText('#drawer')).includes('alarm_lamp'));
  ok('M40-12c 時間軸最後一列在可視範圍內', await pg.$eval('#gentl li:last-child', e => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.top < window.innerHeight; }));
  ok('M40-12 停止後按鈕狀態恢復', await pg.isHidden('#genstop') && !(await pg.isDisabled('#genbtn')));
  await shot('04_stopped.png');
  await pg.waitForTimeout(1200);  // 伺服器端寫入失敗即中止,不應影響之後的請求
  ok('M40-13 停止後未被後到的事件覆蓋', (await pg.locator('#gentl li[data-k]').count()) === 1);

  // ---- 3. 錯誤事件:ollama 無法連線 → 顯示錯誤 ----
  await T('set'); await pg.selectOption('#prov', 'ollama'); await pg.fill('#model', ''); await pg.fill('#base', 'http://127.0.0.1:9'); await T('gen');
  await pg.click('#genbtn');
  await pg.waitForSelector('#genout.er', { timeout: 15000 });
  ok('M40-14 LLM 連線錯誤以錯誤訊息顯示', (await pg.innerText('#genout')).includes('LLM request failed') && await pg.isHidden('#genstop'));
  await shot('05_error_event.png');

  // ---- 4. 舊伺服器後援:/api/generate/stream 404 → 改用 /api/generate ----
  await T('set'); await pg.selectOption('#prov', 'mock'); await pg.fill('#model', ''); await pg.fill('#base', ''); await T('gen');
  await pg.route('**/api/generate/stream', r => r.fulfill({ status: 404, contentType: 'application/json', body: '{"error":"not found"}' }));
  await pg.click('#genbtn');
  await pg.waitForFunction("document.getElementById('genst').textContent.includes('完成(')", null, { timeout: 15000 });
  ok('M40-15 串流端點不存在時改用一次性 API,結果相同', (await pg.locator('#gentl li[data-k]').count()) === 2 && (await pg.innerText('#gentl')).includes('經 1 輪修正後通過'));
  await pg.unroute('**/api/generate/stream');

  // ---- 5. 暗色 + 手機版 ----
  await T('set'); await pg.fill('#model', 'demo-slow'); await T('gen');
  await pg.evaluate(() => setTheme('dark'));
  await pg.click('#genbtn');
  await pg.waitForFunction("document.querySelectorAll('#gentl li[data-k]').length===1");
  await shot('06_dark_streaming.png');
  await pg.waitForFunction("document.getElementById('genst').textContent.includes('完成(')", null, { timeout: 15000 });
  await pg.evaluate(() => setTheme('light'));
  await pg.setViewportSize({ width: 390, height: 844 });
  await pg.click('#genbtn');
  await pg.waitForSelector('#gentl li.pend');
  const sw = await pg.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  ok('M40-16 手機寬度串流中無水平捲動、停止鈕可見', sw && await pg.isVisible('#genstop'));
  await shot('07_mobile_streaming.png');
  await pg.waitForFunction("document.getElementById('genst').textContent.includes('完成(')", null, { timeout: 15000 });

  ok('M40-17 無 JS 錯誤', errs.length === 0, errs.join(' | '));
  fs.writeFileSync(S + 'results.json', JSON.stringify(res, null, 1));
  const np = res.filter(r => r.pass).length;
  console.log(`${np}/${res.length} passed`);
  await b.close();
  process.exit(np === res.length ? 0 : 1);
})();
