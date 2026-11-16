// M34 UI 測試:CONSTANT / RETAIN / VAR_TEMP 與直接位址(點位表、檢查、模擬、斷電重啟、情境、匯出)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m34.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m34') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const shot = async f => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.screenshot({ path: S + f }); };
  const src = fs.readFileSync(R + 'examples/qualifiers_m34.st', 'utf8');
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // 1. 點位表含位址 / CONST / RETAIN
  await pg.fill('#tags', fs.readFileSync(R + 'examples/points_addr.csv', 'utf8'));
  await pg.waitForFunction("document.querySelectorAll('#tagpv tbody tr').length==7");
  const pv = await pg.innerText('#tagpv');
  ok('M34-01 點位表預覽顯示位址欄與常數/保持', pv.includes('%IX0.0') && pv.includes('%QW2') && pv.includes('常數 1') && pv.includes('保持 1') && pv.includes('輸入 2') && pv.includes('輸出 2'), pv.split('\n')[0].slice(0, 80));
  await pg.click('text=點位表 → VAR 宣告'); await pg.waitForTimeout(600);
  const gen = await pg.inputValue('#code');
  ok('M34-02 點位表 → VAR 宣告帶 AT 位址與修飾詞', gen.includes('start AT %IX0.0 : BOOL;') && gen.includes('VAR CONSTANT') && gen.includes('VAR RETAIN'));
  await shot('01_tags_address.png');
  await pg.fill('#tags', 'name,type,direction,address\na,BOOL,IN,%QX0.0\nb,BOOL,OUT,X0\n');
  await pg.waitForFunction("document.querySelectorAll('#tagpv tr.bad').length==2");
  ok('M34-03 位址與方向不一致 / 格式錯誤逐列標示', (await pg.innerText('#tagpv')).includes('不一致') && (await pg.innerText('#tagpv')).includes('不是合法'));
  await pg.fill('#tags', '');

  // 2. 檢查:範例無問題;寫入常數、位址大小不符 → 錯誤並帶行號
  await pg.fill('#code', src);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.includes('無問題')");
  ok('M34-04 範例 qualifiers_m34.st 靜態檢查無問題', true);
  await pg.fill('#code', src.replace('speed := sum * 10;', 'speed := sum * 10;\nN := 5;').replace('speed AT %QW2 : INT;', 'speed AT %QX2.0 : INT;'));
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.includes('CONSTANT')");
  const chk = await pg.innerText('#chkout');
  ok('M34-05 寫入 CONSTANT、型別與位址大小不符報錯', chk.includes('write to CONSTANT N') && chk.includes('INT (16 bit) does not fit address %QX2.0 (1 bit)'), chk.replace(/\n/g, ' | ').slice(0, 160));
  await shot('02_check_errors.png');
  // 廠牌方言
  await pg.fill('#code', src);
  await pg.selectOption('#profile', 'siemens-s7-1500');
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.includes('TIA')");
  ok('M34-06 Siemens profile 提示 %IX0.0 → %I0.0 與 PLC 變數表', (await pg.innerText('#chkout')).includes('(%I0.0)') && (await pg.innerText('#chkout')).includes('PLC tag table'));
  await shot('03_dialect_siemens.png');
  await pg.selectOption('#profile', 'iec');

  // 3. 模擬:%I → 開關、%Q → 燈號、位址 / CONST / RETAIN 標籤、斷電重啟
  await T('sim');
  await pg.click('#sim_step'); await pg.waitForSelector('#io .sw[aria-label=start]');
  const io = await pg.evaluate(() => ({
    inSw: !!document.querySelector('#io .iog[data-g=input] .sw[aria-label=sensor]'),
    outLamp: !!document.querySelector('#io .iog[data-g=output] .lamp[aria-label=motor]'),
    ads: [...document.querySelectorAll('#io .ad')].map(e => e.textContent).join(' ') }));
  ok('M34-07 %I 變數為輸入開關、%Q 為輸出燈號,並顯示位址 / CONST / RETAIN', io.inSw && io.outLamp && io.ads.includes('%IX0.0') && io.ads.includes('%QW2') && io.ads.includes('CONST') && io.ads.includes('RETAIN'), io.ads);
  const val = async n => pg.evaluate(n => { const r = [...document.querySelectorAll('#io .ior')].find(e => e.querySelector('.nm').textContent == n); return r.querySelector('.val').textContent; }, n);
  const stepOnce = async () => { const c = await pg.innerText('#simclk'); await pg.click('#sim_step'); await pg.waitForFunction(c => document.getElementById('simclk').textContent != c, c); };
  await pg.click('#io .sw[aria-label=start]'); await stepOnce();
  for (let k = 0; k < 6; k++) { await pg.click('#io .sw[aria-label=sensor]'); await stepOnce(); }
  ok('M34-08 感測器 3 次上升緣:total=3、batch=3、speed=100(VAR_TEMP 每週期歸零)', await val('total') === '3' && await val('batch') === '3' && await val('speed') === '100', `total=${await val('total')} batch=${await val('batch')} speed=${await val('speed')}`);
  await shot('04_sim_before_power_cycle.png');
  await pg.click('#sim_power'); await pg.waitForFunction("document.getElementById('toasts').textContent.includes('斷電重啟')");
  await pg.waitForTimeout(300);
  ok('M34-09 斷電重啟(暖):RETAIN total 保留 3、batch 回 0', await val('total') === '3' && await val('batch') === '0', `total=${await val('total')} batch=${await val('batch')}`);
  await shot('05_sim_after_power_cycle.png');
  await pg.click('#sim_reset'); await pg.waitForTimeout(500);
  ok('M34-10 重設(冷):total 回 0', await val('total') === '0');

  // 4. 情境:restart 步驟
  await T('test');
  if (await pg.isVisible('#scnview_t')) await pg.click('#scnmode_j');
  await pg.fill('#scn', fs.readFileSync(R + 'examples/qualifiers_m34_scenario.json', 'utf8'));
  await pg.click('#scnmode_t');
  ok('M34-11 情境表格標示斷電重啟步驟(暖 / 冷)', (await pg.locator('#scnbody .pwr').count()) === 2 && (await pg.innerText('#scnbody')).includes('⏻暖'));
  await pg.click('#tstbtn'); await pg.waitForFunction("document.getElementById('tstout').textContent.startsWith('PASS')");
  ok('M34-12 含 restart 的情境 7/7 通過(表格模式保留 restart)', (await pg.innerText('#tstout')).includes('7/7'), await pg.innerText('#tstout'));
  await shot('06_scenario_restart.png');

  // 5. 匯出:六種格式皆可匯出,預覽內容正確
  await T('exp');
  await pg.waitForSelector('#expcards .xcard[data-fmt=st]');
  await pg.waitForTimeout(500);
  const cards = await pg.evaluate(() => [...document.querySelectorAll('#expcards .xcard')].map(c => c.dataset.fmt + ':' + (c.classList.contains('ok') ? 'ok' : 'no')));
  ok('M34-13 六種匯出格式皆可匯出', cards.length === 6 && cards.every(c => c.endsWith(':ok')), cards.join(' '));
  const ex = async fmt => (await (await pg.request.post(URL0 + 'api/export', { data: { code: src, format: fmt } })).json()).text;
  const scl = await ex('scl'), xml = await ex('plcopen'), l5x = await ex('l5x'), gx = await ex('gxworks');
  ok('M34-14 SCL:位址變數移到 PLC 變數表、本體加引號、常數邊界展開', scl.includes('// start\tBool\t%I0.0') && scl.includes('"motor" := "start" AND NOT "full";') && scl.includes('ARRAY[0..3] OF INT') && !scl.includes(' AT '));
  ok('M34-15 PLCopen:constant / retain / tempVars / address', xml.includes('<localVars constant="true">') && xml.includes('<localVars retain="true">') && xml.includes('<tempVars>') && xml.includes('address="%QW2"'));
  ok('M34-16 L5X:Constant="true" 並帶值;GX Works3:VAR_CONSTANT / VAR_RETAIN', l5x.includes('Constant="true"') && l5x.includes('Value="1000"') && gx.includes('VAR_CONSTANT\tN') && gx.includes('VAR_RETAIN\ttotal'));
  const pvBtn = pg.locator('#expcards .xcard[data-fmt=scl] button', { hasText: '預覽' });
  if (await pvBtn.count()) { await pvBtn.first().click(); await pg.waitForSelector('#exppvbox:not([hidden])'); }
  ok('M34-17 匯出頁 SCL 預覽顯示 PLC 變數表', (await pvBtn.count()) > 0 && (await pg.innerText('#exppv')).includes('PLC 變數表'));
  await shot('07_export_scl_preview.png');
  ok('M34-18 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
