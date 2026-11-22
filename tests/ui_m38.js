// M38 UI 測試:點位表 → 各廠牌標籤表匯出(TIA xlsx / Studio 5000 CSV / GX Works3 / Sysmac / CODESYS GVL)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m38.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m38') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const shot = async (f, p = pg) => { await p.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await p.screenshot({ path: S + f }); };
  const csv = fs.readFileSync(R + 'examples/points_addr.csv', 'utf8') + 'stop,BOOL,IN,,停止按鈕,\nt1,TON,VAR,,延時,\n';
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
  await pg.fill('#tags', csv);
  await pg.waitForSelector('#tagpv table');
  const opts = await pg.$$eval('#tagfmt option', o => o.map(x => x.value));
  ok('M38-01 標籤表格式選單含 5 種廠牌', JSON.stringify(opts) === JSON.stringify(['tia', 'logix', 'gxworks', 'sysmac', 'codesys']), opts.join(','));

  const get = async fmt => {
    await pg.selectOption('#tagfmt', fmt);
    const [dl] = await Promise.all([pg.waitForEvent('download'), pg.click('#tagexpbtn')]);
    const p = S + '_' + dl.suggestedFilename(); await dl.saveAs(p);
    await pg.waitForFunction(f => (document.getElementById('tagexpst') || {}).textContent?.includes(f), dl.suggestedFilename());
    return { name: dl.suggestedFilename(), buf: fs.readFileSync(p), st: await pg.innerText('#tagexpout') };
  };
  const tia = await get('tia');
  ok('M38-02 TIA 下載 tags_tia.xlsx(zip 檔頭 PK)', tia.name === 'tags_tia.xlsx' && tia.buf.slice(0, 2).toString() === 'PK', tia.name + ' ' + tia.buf.length + 'B');
  ok('M38-03 TIA 提醒:自動配置位址與 TON 略過', /stop: 點位表未指定位址,自動配置 %I0\.2/.test(tia.st) && /t1: 型別 TON/.test(tia.st), tia.st.split('\n')[0]);
  await shot('01_tia_export_warnings.png');
  const lx = await get('logix');
  const lt = lx.buf.toString('utf8');
  ok('M38-04 Studio 5000 CSV:表頭與 TIMER 標籤', lt.startsWith('remark,"CSV-Import-Export"') && /TAG,,t1,"延時","TIMER"/.test(lt), lx.name);
  const gx = await get('gxworks');
  ok('M38-05 GX Works3:VAR_GLOBAL_CONSTANT / RETAIN 類別', /MAX_COUNT\tDouble Word \[Signed\]\tVAR_GLOBAL_CONSTANT/.test(gx.buf.toString()) && /VAR_GLOBAL_RETAIN/.test(gx.buf.toString()), gx.name);
  const sy = await get('sysmac');
  ok('M38-06 Sysmac:Retain/Constant 欄', /total\tDINT\t\t\tTRUE\tFALSE/.test(sy.buf.toString()), sy.name);
  const gv = await get('codesys');
  const gt = gv.buf.toString();
  ok('M38-07 CODESYS GVL:保留 AT 位址,無提醒', gv.name === 'tags_codesys.gvl.st' && gt.includes('start AT %IX0.0 : BOOL;') && /VAR_GLOBAL RETAIN/.test(gt) && !/提醒/.test(gv.st), gv.st);
  await shot('02_gvl_export_ok.png');

  // 錯誤點位表:明確錯誤訊息、不下載
  await pg.fill('#tags', 'name,type,direction\n9x,BOOL,IN\n');
  await pg.selectOption('#tagfmt', 'tia'); await pg.click('#tagexpbtn');
  await pg.waitForSelector('#tagexpst.er');
  const er = await pg.innerText('#tagexpst');
  ok('M38-08 錯誤點位表顯示行號錯誤', /line 2/.test(er) && /不是合法識別字/.test(er), er);
  await shot('03_tag_export_error.png');

  // 手機版:匯出列不造成水平捲動
  const m = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await m.goto(URL0); await m.fill('#tags', csv); await m.click('#tagexpbtn').catch(() => {});
  await m.waitForSelector('#tagexpst');
  const ov = await m.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok('M38-09 手機寬度無水平捲動', ov <= 0, 'overflow=' + ov);
  await m.locator('.tagexp').scrollIntoViewIfNeeded();
  await shot('04_mobile_tag_export.png', m);
  ok('M38-10 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  for (const f of fs.readdirSync(S)) if (f.startsWith('_')) fs.unlinkSync(S + f);
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
