// M42 UI 測試:TYPE STRUCT 匯出至 Mitsubishi GX Works3 / Omron Sysmac Studio(examples/struct_gx_sysmac.st)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m42.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m42') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const shot = async f => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.screenshot({ path: S + f }); };
  const src = fs.readFileSync(R + 'examples/struct_gx_sysmac.st', 'utf8');
  const fnsrc = fs.readFileSync(R + 'examples/userpou_export.st', 'utf8');
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // 1. 靜態檢查
  await pg.fill('#code', src);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.length>0");
  const chk = await pg.innerText('#chkout');
  ok('M42-01 struct_gx_sysmac.st 靜態檢查無錯誤', !/error/i.test(chk), chk.replace(/\n/g, ' | ').slice(0, 120));

  // 2. 模擬:巢狀 STRUCT 初值與 ARRAY OF STRUCT 重複初值在虛擬 PLC 生效
  await T('sim');
  await pg.click('#sim_step'); await pg.waitForSelector('#io .sw[aria-label=start]');
  const val = async n => pg.evaluate(n => { const r = [...document.querySelectorAll('#io .ior')].find(e => e.querySelector('.nm').textContent == n); return r ? r.querySelector('.val').textContent : null; }, n);
  const stepOnce = async () => { const c = await pg.innerText('#simclk'); await pg.click('#sim_step'); await pg.waitForFunction(c => document.getElementById('simclk').textContent != c, c); };
  const s0 = await val('sum');
  ok('M42-02 初值:sum = 5+6+10+20+0 = 41', s0 === '41', `sum=${s0}`);
  await pg.click('#io .sw[aria-label=start]'); await stepOnce(); await stepOnce(); await stepOnce();
  const s1 = await val('sum');
  ok('M42-03 start 三個週期後 sum=44(ax.pos[1] 累加)', s1 === '44', `sum=${s1}`);
  await shot('01_sim_struct.png');

  // 3. 匯出卡片:GX Works3 / Sysmac 可匯出
  await T('exp');
  await pg.waitForSelector('#expcards .xcard[data-fmt=gxworks]'); await pg.waitForTimeout(800);
  const card = async f => pg.evaluate(f => { const c = document.querySelector(`#expcards .xcard[data-fmt=${f}]`); return { ok: c.classList.contains('ok'), text: c.innerText }; }, f);
  const cg = await card('gxworks'), cs = await card('sysmac');
  ok('M42-04 GX Works3 與 Sysmac 卡片皆顯示可匯出(含 TYPE STRUCT)', cg.ok && cs.ok, (cg.text + ' / ' + cs.text).replace(/\n/g, ' ').slice(0, 160));
  const preview = async f => { const btn = pg.locator(`#expcards .xcard[data-fmt=${f}] button`, { hasText: '預覽' }); await btn.first().click(); await pg.waitForSelector('#exppvbox:not([hidden])'); await pg.waitForTimeout(300); return pg.innerText('#exppv'); };
  const pvg = await preview('gxworks');
  ok('M42-05 GX 預覽含結構體定義(Pt / Axis 成員,MELSEC 型別)', pvg.includes('Structured Data Types') && /Pt\s+x\s+Word \[Signed\]\s+1/.test(pvg) && /Axis\s+home\s+Pt/.test(pvg));
  ok('M42-06 GX 預覽把結構體標籤初值展開為逐一成員', /ax\.home\.x\s+5/.test(pvg) && /ax\.name\s+'X, main'/.test(pvg) && /marks\[3\]\.y\s+20/.test(pvg));
  await shot('02_export_gxworks_preview.png');
  const pvs = await preview('sysmac');
  ok('M42-07 Sysmac 預覽含 Data Types / Structures 與結構體初值', pvs.includes('Data Types / Structures') && /Axis\s+pos\s+ARRAY\[0\.\.1\] OF INT/.test(pvs) && pvs.includes("(home := (x := 5, y := 6), name := 'X, main')"));
  await shot('03_export_sysmac_preview.png');

  // 4. 含 FUNCTION / FUNCTION_BLOCK:GX 卡片仍顯示不支援與原因
  await pg.fill('#code', fnsrc); await pg.waitForTimeout(1200);
  const c2 = await card('gxworks');
  ok('M42-08 含 FUNCTION:GX 卡片顯示不支援、原因提到 FUNCTION 與 TYPE STRUCT 已支援', !c2.ok && c2.text.includes('FUNCTION') && c2.text.includes('STRUCT'), c2.text.replace(/\n/g, ' ').slice(0, 160));
  await shot('04_export_function_reason.png');
  ok('M42-09 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
