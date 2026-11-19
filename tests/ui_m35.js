// M35 UI 測試:自訂 FUNCTION_BLOCK → Rockwell L5X Add-On Instruction(檢查、模擬、匯出卡片、預覽)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m35.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m35') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const shot = async f => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.screenshot({ path: S + f }); };
  const src = fs.readFileSync(R + 'examples/aoi_l5x.st', 'utf8');
  const fnsrc = fs.readFileSync(R + 'examples/userpou_export.st', 'utf8');
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // 1. 檢查(Rockwell profile):無錯誤,只有 R_TRIG → OSRI 方言提示
  await pg.fill('#code', src);
  const rw = await pg.evaluate(() => [...document.querySelectorAll('#profile option')].map(o => o.value).find(v => v.startsWith('rockwell')));
  await pg.selectOption('#profile', rw);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.length>0");
  const chk = await pg.innerText('#chkout');
  ok('M35-01 範例 aoi_l5x.st 在 Rockwell profile 無錯誤(僅方言提示)', !/error/i.test(chk) && chk.includes('OSRI'), chk.replace(/\n/g, ' | ').slice(0, 140));
  await shot('01_check_rockwell.png');
  await pg.selectOption('#profile', 'iec');

  // 2. 模擬:FB 實例(含巢狀 FB 與 VAR_IN_OUT)在虛擬 PLC 執行
  await T('sim');
  await pg.click('#sim_step'); await pg.waitForSelector('#io .sw[aria-label=start]');
  const val = async n => pg.evaluate(n => { const r = [...document.querySelectorAll('#io .ior')].find(e => e.querySelector('.nm').textContent == n); return r ? r.querySelector('.val').textContent : null; }, n);
  const stepOnce = async () => { const c = await pg.innerText('#simclk'); await pg.click('#sim_step'); await pg.waitForFunction(c => document.getElementById('simclk').textContent != c, c); };
  await pg.click('#io .sw[aria-label=start]'); await stepOnce(); await stepOnce();
  const s1 = await val('sum'), p1 = await val('pool'), st = await val('starts');
  ok('M35-02 start 兩個週期:sum=90、pool=140(VAR_IN_OUT 累加)、starts=1', s1 === '90' && p1 === '140' && st === '1', `sum=${s1} pool=${p1} starts=${st}`);
  await shot('02_sim_fb_instances.png');

  // 3. 匯出卡片:l5x 可匯出;預覽含 AOI 定義與轉換後的呼叫
  await T('exp');
  await pg.waitForSelector('#expcards .xcard[data-fmt=l5x]'); await pg.waitForTimeout(600);
  const card = async f => pg.evaluate(f => { const c = document.querySelector(`#expcards .xcard[data-fmt=${f}]`); return { ok: c.classList.contains('ok'), text: c.innerText }; }, f);
  ok('M35-03 Rockwell L5X 卡片顯示可匯出(含 FUNCTION_BLOCK)', (await card('l5x')).ok, (await card('l5x')).text.replace(/\n/g, ' ').slice(0, 100));
  const pvBtn = pg.locator('#expcards .xcard[data-fmt=l5x] button', { hasText: '預覽' });
  if (await pvBtn.count()) { await pvBtn.first().click(); await pg.waitForSelector('#exppvbox:not([hidden])'); }
  const pv = await pg.innerText('#exppv');
  ok('M35-04 預覽含 AddOnInstructionDefinition Latch / Accum 與 EnableIn', pv.includes('AddOnInstructionDefinition Name="Latch"') && pv.includes('AddOnInstructionDefinition Name="Accum"') && pv.includes('EnableIn'));
  await shot('03_export_l5x_preview.png');
  const l5x = (await (await pg.request.post(URL0 + 'api/export', { data: { code: src, format: 'l5x' } })).json()).text;
  ok('M35-05 程式呼叫改為 Logix AOI 語法', l5x.includes('l1.set := start;') && l5x.includes('Latch(l1);') && l5x.includes('Accum(acc, pool);') && l5x.includes('sum := acc.total;'));
  ok('M35-06 VAR_IN_OUT 為必要參數、巢狀實例為 LocalTag', l5x.includes('Name="shared" TagType="Base" DataType="DINT" Usage="InOut" Radix="Decimal" Required="true"') && l5x.includes('<LocalTag Name="inner" DataType="Latch"'));
  const pvs = await pg.request.post(URL0 + 'api/export', { data: { code: src, format: 'plcopen' } });
  ok('M35-07 同一程式 PLCopen / SCL 匯出仍可用', pvs.ok() && (await (await pg.request.post(URL0 + 'api/export', { data: { code: src, format: 'scl' } })).json()).text.includes('FUNCTION_BLOCK "Accum"'));

  // 4. 含 FUNCTION 的程式:L5X 卡片仍顯示不支援,原因指向改寫為 FUNCTION_BLOCK
  await pg.fill('#code', fnsrc); await pg.waitForTimeout(1200);
  const c2 = await card('l5x');
  ok('M35-08 含 FUNCTION:L5X 卡片顯示不支援與原因', !c2.ok && c2.text.includes('FUNCTION_BLOCK'), c2.text.replace(/\n/g, ' ').slice(0, 140));
  await shot('04_export_function_reason.png');
  ok('M35-09 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
