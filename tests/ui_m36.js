// M36 UI 測試:整個陣列傳入 VAR_IN_OUT / VAR_INPUT、陣列整體賦值(檢查、模擬、L5X COP、初值範圍檢查)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m36.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m36') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const shot = async f => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.screenshot({ path: S + f }); };
  const src = fs.readFileSync(R + 'examples/array_inout.st', 'utf8');
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // 1. 靜態檢查:範例無錯誤
  await pg.fill('#code', src);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.length>0");
  const chk = await pg.innerText('#chkout');
  ok('M36-01 array_inout.st 靜態檢查無錯誤', !/error/i.test(chk), chk.replace(/\n/g, ' | ').slice(0, 120));
  await shot('01_check_ok.png');

  // 2. 模擬:sample 依序 5、12、3,hist 為移位暫存器、snap 為整體複製、peak 為最大值
  await T('sim');
  await pg.click('#sim_step'); await pg.waitForSelector('#io input[aria-label=sample]');
  const val = async n => pg.evaluate(n => { const r = [...document.querySelectorAll('#io .ior')].find(e => e.querySelector('.nm').textContent == n); return r ? r.querySelector('.val').textContent : null; }, n);
  const stepOnce = async () => { const c = await pg.innerText('#simclk'); await pg.click('#sim_step'); await pg.waitForFunction(c => document.getElementById('simclk').textContent != c, c); };
  for (const v of ['5', '12', '3']) {
    await pg.fill('#io input[aria-label=sample]', v); await pg.press('#io input[aria-label=sample]', 'Enter');
    await stepOnce();
  }
  const h = []; for (let i = 0; i < 5; i++) h.push(await val(`hist[${i}]`));
  const sn = []; for (let i = 0; i < 5; i++) sn.push(await val(`snap[${i}]`));
  const pk = await val('peak');
  ok('M36-02 VAR_IN_OUT 陣列移位:hist 最新三筆為 3,12,5', h.slice(0, 3).join(',') === '3,12,5', 'hist=' + h.join(','));
  ok('M36-03 snap := hist 整體複製、MaxOf(snap) = 12', sn.slice(0, 3).join(',') === '3,12,5' && pk === '12', `snap=${sn.join(',')} peak=${pk}`);
  await shot('02_sim_array_inout.png');

  // 3. 匯出:SCL 保留陣列參數;L5X 卡片因 FUNCTION 不可匯出,但只含 FB 的版本把 snap := hist 改為 COP
  await T('exp');
  await pg.waitForSelector('#expcards .xcard[data-fmt=scl]'); await pg.waitForTimeout(600);
  const card = async f => pg.evaluate(f => { const c = document.querySelector(`#expcards .xcard[data-fmt=${f}]`); return { ok: c.classList.contains('ok'), text: c.innerText }; }, f);
  ok('M36-04 SCL / PLCopen 卡片可匯出', (await card('scl')).ok && (await card('plcopen')).ok);
  const fbOnly = src.split('FUNCTION MaxOf')[0].split('END_FUNCTION\n', 2)[1]
    + 'PROGRAM Main\nVAR_INPUT sample : INT; END_VAR\nVAR hist : ARRAY[0..4] OF INT; snap : ARRAY[0..4] OF INT; sh : ShiftReg; END_VAR\n'
    + 'sh(nv := sample, buf := hist);\nsnap := hist;\nEND_PROGRAM\n';
  await pg.fill('#code', fbOnly); await pg.waitForTimeout(1200);
  ok('M36-05 只含 FUNCTION_BLOCK:L5X 卡片可匯出', (await card('l5x')).ok, (await card('l5x')).text.replace(/\n/g, ' ').slice(0, 100));
  const pvBtn = pg.locator('#expcards .xcard[data-fmt=l5x] button', { hasText: '預覽' });
  if (await pvBtn.count()) { await pvBtn.first().click(); await pg.waitForSelector('#exppvbox:not([hidden])'); }
  const l5x = (await (await pg.request.post(URL0 + 'api/export', { data: { code: fbOnly, format: 'l5x' } })).json()).text;
  ok('M36-06 L5X:陣列 InOut 參數 + snap := hist → COP(hist[0], snap[0], 5)', l5x.includes('Dimensions="5" Usage="InOut"') && l5x.includes('COP(hist[0], snap[0], 5);') && l5x.includes('ShiftReg(sh, hist);'));
  await pg.evaluate(() => { const p = document.getElementById('exppv'); const i = p.textContent.indexOf('COP('); if (i > 0) p.scrollTop = p.scrollHeight; });
  await shot('03_export_l5x_cop.png');

  // 4. 檢查器:陣列大小不符、初值超出範圍
  const bad = src.replace('hist : ARRAY[0..4] OF INT;', 'hist : ARRAY[0..5] OF INT;').replace('peak : INT;', 'peak : INT; lim : SINT := 300;');
  await pg.fill('#code', bad);
  await T('gen').catch(() => {});
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.includes('error')");
  const c2 = await pg.innerText('#chkout');
  ok('M36-07 檢查器報告陣列大小不符(ShiftReg 的 buf)', c2.includes('argument buf of ShiftReg') && c2.includes('[6] does not match [5]'), c2.replace(/\n/g, ' | ').slice(0, 200));
  ok('M36-08 檢查器報告初值 300 超出 SINT 範圍', c2.includes('300 of lim out of range for SINT'));
  await shot('04_check_errors.png');
  ok('M36-09 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
