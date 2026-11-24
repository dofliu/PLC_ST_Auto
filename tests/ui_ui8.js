// UI8 UI 測試:寬螢幕(≥1600px)雙頁籤 —— 右側同時顯示兩個頁籤(例:模擬 + 測試)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_ui8.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const S = path.resolve(process.argv[2] || 'docs/screenshots/ui8') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
  const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push({ name: n, pass: !!c, detail: d }); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const shot = async (f) => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.waitForTimeout(250); await pg.screenshot({ path: S + f }); };
  const vis = sel => pg.isVisible(sel);
  const ready = () => pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.goto(URL0); await ready();
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
  await pg.reload(); await ready();

  ok('U8-01 ≥1600px 顯示雙頁籤按鈕,預設關閉', await vis('#dualbtn') && await pg.getAttribute('#dualbtn', 'aria-pressed') === 'false' && !await vis('#dualbar'));
  await pg.click('#nav button[data-t=sim]');
  await pg.click('#dualbtn');
  ok('U8-02 開啟後左欄=模擬、右欄=測試(預設)', await vis('#tab_sim') && await vis('#tab_test') && await pg.inputValue('#tab2sel') === 'test' && (await pg.innerText('#dual1n')) === '模擬');
  const box = async id => pg.$eval(id, e => { const r = e.getBoundingClientRect(); return { x: r.x, w: r.width, h: r.height }; });
  const a = await box('#tab_sim'), c = await box('#tab_test');
  ok('U8-03 兩欄並排(右欄在左欄右側、寬度相近)', c.x >= a.x + a.w - 2 && Math.abs(a.w - c.w) < 40, `${Math.round(a.x)}+${Math.round(a.w)} | ${Math.round(c.x)}+${Math.round(c.w)}`);
  ok('U8-04 雙頁籤時程式碼欄預設 34%', await pg.getAttribute('#split', 'aria-valuenow') === '34');
  ok('U8-05 右欄頁籤在導覽列以虛線標示', await pg.$eval('#nav button[data-t=test]', e => e.classList.contains('on2') && !e.classList.contains('on')));
  ok('U8-06 情境變數晶片於右欄顯示時已更新', (await pg.$$('#scnvars .chip, #scnvars button, #scnvars span')).length > 0);

  // 左:執行模擬;右:執行情境 —— 兩者同時可見
  await pg.click('#batchbox summary');
  await pg.click('#batchbtn');
  await pg.waitForFunction("(document.getElementById('runst')||{}).textContent.length>0", null, { timeout: 15000 });
  await pg.click('#tstbtn');
  await pg.waitForSelector('#tstout:not([hidden])', { timeout: 15000 });
  ok('U8-07 模擬波形與情境結果同時可見', await vis('#tab_sim canvas, #tab_sim svg') && await vis('#tstout'));
  await shot('01_dual_sim_test.png');

  // simRun 會呼叫 tab('sim'):右欄是 sim 時不應換掉左欄
  await pg.selectOption('#tab2sel', 'exp');
  await pg.waitForSelector('#tab_exp.on2');
  await pg.waitForFunction("!document.querySelector('#expcards .empty')||!/自動檢查/.test(document.querySelector('#expcards').textContent)", null, { timeout: 15000 });
  ok('U8-08 右欄改為匯出:匯出卡片自動檢查', await vis('#tab_exp') && await vis('#tab_sim') && (await pg.$$('.xcard')).length >= 3);
  await shot('02_dual_sim_export.png');

  await pg.click('#nav button[data-t=gen]', { modifiers: ['Shift'] });
  ok('U8-09 Shift+點頁籤 指定右欄', await pg.inputValue('#tab2sel') === 'gen' && await vis('#tab_gen') && await vis('#tab_sim'));
  await pg.keyboard.press('Alt+Shift+Digit3');
  ok('U8-10 Alt+Shift+3 指定右欄=測試', await pg.inputValue('#tab2sel') === 'test');
  await pg.keyboard.press('Alt+Digit3');
  ok('U8-11 Alt+3 切到右欄頁籤時不會重複顯示(左欄保持模擬)', (await pg.innerText('#dual1n')) === '模擬' && await vis('#tab_test'));

  await pg.click('#dualbar button[title=左右對調]');
  ok('U8-12 對調:左欄=測試、右欄=模擬', (await pg.innerText('#dual1n')) === '測試' && await pg.inputValue('#tab2sel') === 'sim');
  await pg.click('#nav button[data-t=sim]');
  ok('U8-13 點右欄頁籤:左欄不變(保持測試)', (await pg.innerText('#dual1n')) === '測試' && await pg.$eval('#tab_sim', e => e.classList.contains('on2')));
  await pg.click('#nav button[data-t=rag]');
  ok('U8-14 左欄切到文件,右欄仍為模擬', (await pg.innerText('#dual1n')) === '文件' && await vis('#tab_rag') && await vis('#tab_sim') && !await vis('#tab_test'));
  await pg.selectOption('#tab2sel', 'rag');
  ok('U8-15 右欄選成與左欄相同 → 自動對調', (await pg.innerText('#dual1n')) === '模擬' && await pg.inputValue('#tab2sel') === 'rag');

  // 記憶:重新整理後保留雙頁籤與右欄
  await pg.reload(); await ready();
  ok('U8-16 重新整理後保留雙頁籤/左欄/右欄', await pg.getAttribute('#dualbtn', 'aria-pressed') === 'true' && (await pg.innerText('#dual1n')) === '模擬' && await pg.inputValue('#tab2sel') === 'rag');
  const sp = await pg.evaluate(() => [localStorage.getItem('plcst.dual'), localStorage.getItem('plcst.tab2'), localStorage.getItem('plcst.split2')]);
  ok('U8-17 localStorage 記錄 dual/tab2', sp[0] === 'true' && sp[1] === '"rag"', sp.join(','));

  // 視窗縮小到 1440:自動退回單頁籤、分欄 50%;放大後恢復
  await pg.setViewportSize({ width: 1440, height: 900 });
  await pg.waitForTimeout(200);
  ok('U8-18 縮到 1440px:隱藏按鈕、單頁籤、分欄回到 50%', !await vis('#dualbtn') && !await vis('#tab_rag') && await vis('#tab_sim') && await pg.getAttribute('#split', 'aria-valuenow') === '50');
  await pg.setViewportSize({ width: 1920, height: 1080 });
  await pg.waitForTimeout(200);
  ok('U8-19 放大回 1920px:恢復雙頁籤', await vis('#tab_rag') && await vis('#tab_sim') && await pg.getAttribute('#split', 'aria-valuenow') === '34');
  const ov = await pg.evaluate(() => [document.documentElement.scrollWidth - innerWidth, document.documentElement.scrollHeight - innerHeight]);
  ok('U8-20 雙頁籤無整頁捲動', ov[0] <= 0 && ov[1] <= 0, ov.join(','));

  await pg.click('#dualbar button[aria-label=關閉雙頁籤]');
  ok('U8-21 ✕ 關閉雙頁籤', !await vis('#dualbar') && !await vis('#tab_rag') && await pg.getAttribute('#dualbtn', 'aria-pressed') === 'false');
  // 暗色主題截圖
  await pg.click('#dualbtn');
  await pg.evaluate(() => { if (typeof setTheme == 'function') setTheme('dark'); });
  await pg.click('#nav button[data-t=test]');
  await shot('03_dual_dark.png');
  ok('U8-22 無 JavaScript 錯誤', errs.length === 0, errs.join(' | '));

  fs.writeFileSync(S + 'results.json', JSON.stringify(res, null, 1));
  console.log(res.filter(r => r.pass).length + '/' + res.length + ' PASS');
  await b.close();
  process.exit(res.every(r => r.pass) ? 0 : 1);
})().catch(e => { console.error('E2E CRASH', e.message); process.exit(2); });
