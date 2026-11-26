// M41 UI 測試:ARRAY OF STRUCT 且 STRUCT 含 ARRAY 欄位(examples/recipe_slots.st)。
// 先啟動 `python -m plc_st serve --port 8765`,再執行:NODE_PATH=$(npm root -g) node tests/ui_m41.js [截圖資料夾]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/m41') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push(!!c); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const shot = async f => { await pg.evaluate(() => { document.getElementById('toasts').innerHTML = ''; }); await pg.screenshot({ path: S + f }); };
  const src = fs.readFileSync(R + 'examples/recipe_slots.st', 'utf8');
  await pg.goto(URL0);
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  await pg.evaluate(() => { try { localStorage.clear(); } catch (e) {} });

  // 1. 靜態檢查
  await pg.fill('#code', src);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.length>0");
  const chk = await pg.innerText('#chkout');
  ok('M41-01 recipe_slots.st 靜態檢查無錯誤', !/error/i.test(chk), chk.replace(/\n/g, ' | ').slice(0, 120));
  await shot('01_check_ok.png');

  // 2. 靜態檢查抓到陣列欄位越界/未加索引
  await pg.fill('#code', src.replace('slots[3].name := \'copy\';', "slots[3].name := 'copy';\n  slots[1].setp[4] := 1;\n  sum := slots[2].setp;"));
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.includes('out of range')");
  const chk2 = await pg.innerText('#chkout');
  ok('M41-02 slots[1].setp[4] 越界、slots[2].setp 未加索引皆報錯', chk2.includes('out of range [1..3] for setp') && chk2.includes('used without index'), chk2.replace(/\n/g, ' | ').slice(0, 160));
  await shot('02_check_errors.png');
  await pg.fill('#code', src);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("!document.getElementById('chkout').textContent.includes('out of range')");

  // 3. 批次模擬 + 波形
  await T('sim');
  await pg.evaluate(() => { document.getElementById('batchbox').open = true; });
  await pg.fill('#cycles', '6');
  await pg.fill('#events', '0:slot=2\n0:bump=true\n3:save=true');
  await pg.click('text=執行並繪製波形');
  await pg.waitForFunction("document.getElementById('runst').textContent.includes('週期')");
  const lanes = await pg.evaluate(() => wv.lanes.map(l => l.nm));
  ok('M41-03 波形軌道以 slots[i].setp[j] 命名', lanes.includes('slots[2].setp[1]') && lanes.includes('slots[3].setp[2]'), lanes.slice(0, 12).join(' '));
  const v = await pg.evaluate(() => { const w = lastWave, last = w.rows[w.rows.length - 1]; const hdr = w.columns || Object.keys(last);
    const col = n => Array.isArray(last) ? last[hdr.indexOf(n)] : last[n];
    return { s21: col('slots[2].setp[1]'), s32: col('slots[3].setp[2]'), name3: col('slots[3].name'), a1: col('active[1]') }; });
  ok('M41-04 6 週期後 slots[2].setp[1]=16、slots[3].setp[2]=52、slots[3].name=copy', String(v.s21) === '16' && String(v.s32) === '52' && String(v.name3).includes('copy'), JSON.stringify(v));
  const tails = await pg.evaluate(() => [...document.querySelectorAll('#io .ior .nm')].filter(e => e.textContent.startsWith('slots[2].setp')).map(e => { const t = [...e.querySelectorAll('.t')]; return t.map(x => x.textContent + (x.getBoundingClientRect().width > 0 ? '' : '(hidden)')).join(''); }));
  ok('M41-04b I/O 面板長名稱只縮名稱,外層 [i] 與 .setp[j] 索引都可見', tails.length === 3 && tails.every((t, i) => t === `[2].setp[${i + 1}]`), tails.join(' '));
  await shot('03_sim_wave.png');

  // 4. 情境測試(陣列欄位的期望值)
  await T('test');
  await pg.click('#scnmode_j');
  await pg.fill('#scn', JSON.stringify({ steps: [
    { name: 'pick B', set: { slot: 2, bump: true }, cycles: 1, expect: { sum: 63, 'slots[2].setp[1]': 11, 'work.name': 'B' } },
    { name: 'save', set: { save: true }, cycles: 1, expect: { 'slots[3].setp[2]': 44, 'slots[3].name': 'copy', 'slots[1].setp[3]': 300 } }] }));
  await pg.click('text=執行情境'); await pg.waitForSelector('#tstout:not([hidden])');
  const t1 = await pg.innerText('#tstout');
  ok('M41-05 情境:陣列欄位期望值 PASS', t1.trim().startsWith('PASS'), t1.slice(0, 100));
  await pg.click('#scnmode_t');
  await shot('04_scenario_pass.png');
  await pg.click('#scnmode_j');
  await pg.fill('#scn', JSON.stringify({ steps: [{ set: { slot: 1 }, cycles: 1, expect: { 'slots[1].setp[1]': 999 } }] }));
  await pg.click('text=執行情境'); await pg.waitForTimeout(800);
  const t2 = await pg.innerText('#tstout');
  ok('M41-06 情境:錯誤期望值偵測為 FAIL', t2.includes('FAIL'), t2.slice(0, 100));
  await pg.click('#scnmode_t');
  await shot('05_scenario_fail.png');

  ok('M41-07 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  const n = res.filter(Boolean).length;
  console.log(`${n}/${res.length} PASS`);
  await b.close();
  process.exit(n === res.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
