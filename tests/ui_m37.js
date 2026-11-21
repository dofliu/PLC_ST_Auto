// M37 UI 測試:直接位址共用記憶體(%IB0 與 %IX0.x、%MW0 與 %MX 旗標同步;IEC 與 Siemens 位元組順序)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m37.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m37') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const shot = async f => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.screenshot({ path: S + f }); };
  const src = fs.readFileSync(R + 'examples/shared_memory.st', 'utf8');
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // 1. 靜態檢查:刻意的位元/位元組別名不產生警告
  await pg.fill('#code', src);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.length>0");
  const chk = await pg.innerText('#chkout');
  ok('M37-01 shared_memory.st 靜態檢查無錯誤、無重疊警告', !/error|overlap/i.test(chk), chk.replace(/\n/g, ' | ').slice(0, 120));

  // 2. 模擬:I/O 面板顯示共用記憶體標記
  await T('sim');
  await pg.click('#sim_step'); await pg.waitForSelector('#io input[aria-label=inByte]');
  const badge = await pg.evaluate(() => [...document.querySelectorAll('#io .ior')].filter(r => r.querySelector('.sh')).map(r => r.querySelector('.nm').textContent + ':' + r.querySelector('.sh').title));
  ok('M37-02 I/O 面板顯示 ⇄ 共用記憶體標記', badge.some(x => x.startsWith('inByte:') && x.includes('start')) && badge.some(x => x.startsWith('status:') && x.includes('running')), badge.join(' / '));
  const val = async n => pg.evaluate(n => { const r = [...document.querySelectorAll('#io .ior')].find(e => e.querySelector('.nm').textContent == n); if (!r) return null; const v = r.querySelector('.val'); const l = r.querySelector('.lamp'); return v ? v.textContent : l ? String(l.classList.contains('on')) : r.querySelector('[aria-checked]') ? r.querySelector('[aria-checked]').getAttribute('aria-checked') : r.innerText; }, n);
  const stepOnce = async () => { const c = await pg.innerText('#simclk'); await pg.click('#sim_step'); await pg.waitForFunction(c => document.getElementById('simclk').textContent != c, c); };
  await pg.fill('#io input[aria-label=inByte]', '1'); await pg.press('#io input[aria-label=inByte]', 'Enter');
  await stepOnce();
  const v1 = { start: await val('start'), running: await val('running'), motor: await val('motor'), status: await val('status'), outByte: await val('outByte') };
  ok('M37-03 強制 inByte=1 → start、running、motor 為 TRUE,status=1、outByte=1(IEC little-endian)',
    /true|TRUE|1/.test(v1.start) && /true|TRUE|1/.test(v1.motor) && v1.status === '1' && v1.outByte === '1', JSON.stringify(v1));
  await shot('01_sim_iec_shared.png');
  await pg.fill('#io input[aria-label=inByte]', '3'); await pg.press('#io input[aria-label=inByte]', 'Enter');
  await stepOnce();
  const st2 = await val('status');
  ok('M37-04 inByte=3(start+stop)→ alarm %MX1.7 = status bit 15 = 32768', st2 === '32768', 'status=' + st2);

  // 3. Siemens profile:同一程式 %M0.0 是 %MW0 的 bit 8
  await pg.selectOption('#profile', 'siemens-s7-1500'); await pg.waitForTimeout(300);
  await pg.click('#sim_reset').catch(() => {});
  await pg.click('#sim_step'); await pg.waitForSelector('#io input[aria-label=inByte]');
  await pg.fill('#io input[aria-label=inByte]', '1'); await pg.press('#io input[aria-label=inByte]', 'Enter');
  await stepOnce();
  const st3 = await val('status');
  ok('M37-05 Siemens S7-1500:running(%M0.0)→ status = 256(big-endian)', st3 === '256', 'status=' + st3);
  await shot('02_sim_siemens_shared.png');

  // 4. 部分重疊仍警告(S7 的 %MW0 / %MW1)
  await T('gen').catch(() => {});
  await pg.fill('#code', 'PROGRAM P\nVAR\n a AT %MW0 : WORD;\n b AT %MW1 : WORD;\nEND_VAR\na := 1;\nEND_PROGRAM\n');
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.includes('overlap')");
  const c2 = await pg.innerText('#chkout');
  ok('M37-06 S7 部分重疊 %MW0/%MW1 → partially overlaps 警告', c2.includes('b at %MW1 partially overlaps a at %MW0'), c2.replace(/\n/g, ' | ').slice(0, 160));
  await shot('03_check_partial_overlap.png');
  ok('M37-07 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
