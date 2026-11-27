// M43 UI 測試:VAR_GLOBAL / VAR_EXTERNAL(examples/global_vars.st)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m43.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m43') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const shot = async f => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.screenshot({ path: S + f }); };
  const src = fs.readFileSync(R + 'examples/global_vars.st', 'utf8');
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // 1. 靜態檢查(iec 無錯誤、無警告)
  await pg.fill('#code', src);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.length>0");
  const chk = await pg.innerText('#chkout');
  ok('M43-01 global_vars.st 靜態檢查無錯誤', !/error/i.test(chk), chk.replace(/\n/g, ' | ').slice(0, 120));
  await shot('01_editor_check.png');

  // 2. 錯誤的 VAR_EXTERNAL:型別不符 + 找不到全域 → 帶行號的錯誤
  const bad = src.replace('VAR_EXTERNAL\n    g_count : INT;\n    g_stop : BOOL;', 'VAR_EXTERNAL\n    g_count : INT;\n    g_stop : INT;\n    g_missing : BOOL;');
  await pg.fill('#code', bad);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("/VAR_EXTERNAL/.test(document.getElementById('chkout').textContent)");
  const chk2 = await pg.innerText('#chkout');
  ok('M43-02 VAR_EXTERNAL 型別不符與缺少 VAR_GLOBAL 皆報錯', /g_stop type does not match VAR_GLOBAL \(BOOL\)/.test(chk2) && /g_missing has no matching VAR_GLOBAL/.test(chk2), chk2.replace(/\n/g, ' | ').slice(0, 200));
  await shot('02_check_external_errors.png');

  // 3. 模擬:兩個 FB 實例共用全域計數
  await pg.fill('#code', src);
  await T('sim');
  await pg.click('#sim_step'); await pg.waitForSelector('#io .sw[aria-label=sensorA]');
  const val = async n => pg.evaluate(n => { const r = [...document.querySelectorAll('#io .ior')].find(e => e.querySelector('.nm').textContent == n); if (!r) return null; const l = r.querySelector('.lamp'); return l ? (l.classList.contains('on') ? 'TRUE' : 'FALSE') : r.querySelector('.val').textContent; }, n);
  const badge = async n => pg.evaluate(n => { const r = [...document.querySelectorAll('#io .ior')].find(e => e.querySelector('.nm').textContent == n); return r ? [...r.querySelectorAll('.ad')].map(x => x.textContent).join(',') : null; }, n);
  const stepOnce = async () => { const c = await pg.innerText('#simclk'); await pg.click('#sim_step'); await pg.waitForFunction(c => document.getElementById('simclk').textContent != c, c); };
  ok('M43-03 I/O 面板標示 GLOBAL(g_count)與 GLOBAL+CONST(G_LIMIT)', (await badge('g_count')) === 'GLOBAL' && (await badge('G_LIMIT')) === 'GLOBAL,CONST', `${await badge('g_count')} / ${await badge('G_LIMIT')}`);
  ok('M43-04 sensorA 不是全域', (await badge('sensorA')) === '');
  const pulse = async n => { await pg.click(`#io .sw[aria-label=${n}]`); await stepOnce(); await pg.click(`#io .sw[aria-label=${n}]`); await stepOnce(); };
  await pulse('sensorA'); await pulse('sensorB'); await pulse('sensorA');
  ok('M43-05 cA 兩次 + cB 一次上升緣 → g_count = 3、remain = 2', (await val('g_count')) === '3' && (await val('remain')) === '2', `g_count=${await val('g_count')} remain=${await val('remain')}`);
  await pulse('sensorB'); await pulse('sensorB'); await pulse('sensorA');
  ok('M43-06 達上限 G_LIMIT=5 → full=TRUE 且不再累加', (await val('g_count')) === '5' && (await val('full')) === 'TRUE', `g_count=${await val('g_count')} full=${await val('full')}`);
  await shot('03_sim_globals.png');

  // 4. 匯出卡片:PLCopen 可匯出(含 globalVars / externalVars),SCL / L5X 顯示原因
  await T('exp');
  await pg.waitForSelector('#expcards .xcard[data-fmt=plcopen]'); await pg.waitForTimeout(900);
  const card = async f => pg.evaluate(f => { const c = document.querySelector(`#expcards .xcard[data-fmt=${f}]`); return { ok: c.classList.contains('ok'), text: c.innerText }; }, f);
  const cp = await card('plcopen'), cs = await card('scl'), cl = await card('l5x');
  ok('M43-07 PLCopen 卡片可匯出', cp.ok, cp.text.replace(/\n/g, ' ').slice(0, 120));
  ok('M43-08 SCL / L5X 卡片顯示不支援與原因(VAR_GLOBAL、全域 DB / controller-scope)', !cs.ok && !cl.ok && cs.text.includes('全域 DB') && cl.text.includes('controller-scope'), (cs.text + ' / ' + cl.text).replace(/\n/g, ' ').slice(0, 200));
  await shot('04_export_cards.png');
  const btn = pg.locator('#expcards .xcard[data-fmt=plcopen] button', { hasText: '預覽' }); await btn.first().click();
  await pg.waitForSelector('#exppvbox:not([hidden])'); await pg.waitForTimeout(300);
  const pv = await pg.innerText('#exppv');
  ok('M43-09 PLCopen 預覽含 resource globalVars 與 FB externalVars', pv.includes('<globalVars constant="true">') && pv.includes('<externalVars>') && pv.includes('name="g_count"'));
  await pg.evaluate(() => { const e = document.getElementById('exppv'); const i = e.textContent.indexOf('<instances>'); const r = document.createRange(); e.scrollTop = e.scrollHeight; });
  await shot('05_export_plcopen_preview.png');

  // 5. 方言:Siemens profile 顯示 VAR_GLOBAL 提示
  await pg.selectOption('#profile', 'siemens-s7-1500');
  await pg.click('#nav button[data-t=gen]').catch(() => {});
  await pg.click('text=靜態檢查'); await pg.waitForFunction("/global DB/.test(document.getElementById('chkout').textContent)", null, { timeout: 5000 }).catch(() => {});
  const chk3 = await pg.innerText('#chkout');
  ok('M43-10 Siemens profile:VAR_GLOBAL 方言提示(改用全域 DB)', /VAR_GLOBAL: TIA Portal/.test(chk3), chk3.replace(/\n/g, ' | ').slice(0, 200));
  await shot('06_dialect_siemens.png');
  ok('M43-11 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
