// M39 UI 測試:點位表匯出依廠牌換算位址(IEC word 編號 ⇄ S7 位元組)+ Studio 5000 ALIAS 槽號。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m39.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m39') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const pg = await ctx.newPage();
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const shot = async (f, p = pg) => { await p.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await p.screenshot({ path: S + f }); };
  const csv = fs.readFileSync(R + 'examples/points_addr.csv', 'utf8') + 'level,INT,IN,,液位,%IW1\nflag,BOOL,VAR,,,%MX0.0\n';
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
  await pg.reload();
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.fill('#tags', csv);
  await pg.waitForSelector('#tagpv table');
  const opts = await pg.$$eval('#tagaddr option', o => o.map(x => x.value));
  ok('M39-01 位址定址選單 auto/iec/s7', JSON.stringify(opts) === '["auto","iec","s7"]', opts.join(','));
  ok('M39-02 非 logix 時隱藏 Alias 槽號', await pg.isHidden('#tagslotsw'));

  const get = async (fmt) => {
    await pg.selectOption('#tagfmt', fmt);
    const [dl] = await Promise.all([pg.waitForEvent('download'), pg.click('#tagexpbtn')]);
    const p = S + '_' + dl.suggestedFilename(); await dl.saveAs(p);
    await pg.waitForFunction(f => (document.getElementById('tagexpst') || {}).textContent?.includes(f), dl.suggestedFilename());
    return { buf: fs.readFileSync(p), st: await pg.innerText('#tagexpout') };
  };
  // 預設 profile(非 siemens)→ iec:TIA 換算成位元組位址
  await pg.selectOption('#profile', 'iec');
  const tia = await get('tia');
  ok('M39-03 TIA 換算提醒 %QW2 → %QW4、%IW1 → %IW2', /speed: %QW2 .*→ %QW4/.test(tia.st) && /level: %IW1 .*→ %IW2/.test(tia.st), tia.st.split('\n')[0]);
  ok('M39-04 TIA 下載為 xlsx(zip 檔頭 PK)', tia.buf.slice(0, 2).toString() === 'PK');
  await shot('01_tia_iec_conversion.png');

  // Siemens profile → auto 視為 s7:GVL 換成 CODESYS word 編號
  const sp = await pg.$$eval('#profile option', o => o.map(x => x.value).find(v => /siemens/.test(v)));
  await pg.selectOption('#profile', sp);
  const gv = await get('codesys');
  const gt = gv.buf.toString();
  ok('M39-05 Siemens profile 自動以 S7 定址:GVL %QW2 → %QW1', gt.includes('speed AT %QW1 : INT;') && /S7 位元組位址 %QW2 → CODESYS %QW1/.test(gv.st), gv.st.split('\n')[1] || '');
  ok('M39-06 S7 %IW1 未對齊:保留原樣並提醒', gt.includes('level AT %IW1 : INT;') && /level: %IW1 起始位元組不是型別大小的倍數/.test(gv.st));
  await shot('02_gvl_s7_conversion.png');
  // 手動指定 iec 覆蓋 profile
  await pg.selectOption('#tagaddr', 'iec');
  const gv2 = await get('codesys');
  ok('M39-07 手動選 IEC:GVL 位址不變、無換算提醒', gv2.buf.toString().includes('speed AT %QW2 : INT;') && !/S7 位元組位址/.test(gv2.st));

  // Logix:顯示槽號欄,建立 ALIAS
  await pg.selectOption('#tagfmt', 'logix');
  ok('M39-08 選 logix 顯示 Alias 槽號', await pg.isVisible('#tagslots'));
  await pg.fill('#tagslots', 'I=1,Q=2');
  const lx = await get('logix');
  const lt = lx.buf.toString('utf8');
  ok('M39-09 Studio 5000 ALIAS 列', lt.includes('ALIAS,,start,"啟動按鈕 [IEC %IX0.0]","","Local:1:I.Data.0"') && lt.includes('"Local:2:O.Data.0"'), lt.split('\r\n').find(l => l.startsWith('ALIAS')) || '');
  ok('M39-10 非位元 / %M 位址提醒', /level: 只為 BOOL 位元位址建立 Alias/.test(lx.st) && /flag: Logix 沒有 %M 記憶區/.test(lx.st));
  await shot('03_logix_alias.png');
  // 錯誤槽號
  await pg.fill('#tagslots', 'M=1'); await pg.click('#tagexpbtn');
  await pg.waitForSelector('#tagexpst.er');
  ok('M39-11 錯誤槽號顯示錯誤', /logix slot area must be I or Q/.test(await pg.innerText('#tagexpst')));
  await pg.fill('#tagslots', 'I=1,Q=2');
  // 設定記憶:重新載入後保留 logix / iec / 槽號
  await pg.evaluate(() => document.getElementById('tagslots').dispatchEvent(new Event('change', { bubbles: true })));
  await pg.reload();
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  const kept = await pg.evaluate(() => [$('tagfmt').value, $('tagaddr').value, $('tagslots').value, !document.getElementById('tagslotsw').hidden]);
  ok('M39-12 重新載入保留格式/定址/槽號', JSON.stringify(kept) === '["logix","iec","I=1,Q=2",true]', JSON.stringify(kept));

  // 手機:無水平捲動
  const m = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await m.goto(URL0); await m.fill('#tags', csv); await m.selectOption('#tagfmt', 'logix');
  const ov = await m.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok('M39-13 手機寬度無水平捲動', ov <= 0, 'overflow=' + ov);
  await m.locator('#tagaddr').scrollIntoViewIfNeeded();
  await shot('04_mobile_addressing.png', m);
  ok('M39-14 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  for (const f of fs.readdirSync(S)) if (f.startsWith('_')) fs.unlinkSync(S + f);
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
