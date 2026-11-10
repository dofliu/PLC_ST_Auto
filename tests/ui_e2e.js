const { chromium } = require('playwright');
const fs = require('fs');
// Web UI 端到端測試(Node Playwright)。先啟動 `python -m plc_st serve --port 8765`,再於 repo 根目錄執行:
//   NODE_PATH=$(npm root -g) node tests/ui_e2e.js [截圖資料夾]
// 環境變數 PLC_URL 可改伺服器位址。結果印到 stdout,全部通過時 exit 0。
const path = require('path');
const R = path.resolve(__dirname, '..') + '/';
const S = path.resolve(process.argv[2] || 'docs/screenshots/e2e') + '/';
const URL0 = process.env.PLC_URL || 'http://127.0.0.1:8765/';
fs.mkdirSync(S, { recursive: true });
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2, acceptDownloads: true });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  const res = []; const ok = (n, c, d = '') => { res.push({ n, pass: !!c, d }); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? '  [' + d + ']' : '')); };
  const T = async t => { await pg.click(`#nav button[data-t=${t}]`); };
  const card = async (h, file) => { await pg.screenshot({ path: S + file }); };
  const t0 = Date.now();
  await pg.goto(URL0);
  await pg.setViewportSize({ width: 1280, height: 800 });
  await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  const nprof = await pg.locator('#profile option').count();
  ok('01 頁面載入 + 廠牌 profile 清單', nprof === 9, nprof + ' profiles, ' + (Date.now() - t0) + 'ms');
  // 1. 點位表 -> VAR
  await pg.fill('#tags', fs.readFileSync(R + 'examples/points.csv', 'utf8')).catch(() => {});
  const hasCsv = await pg.locator('#tags').count();
  if (hasCsv) { await pg.click('text=點位表 → VAR 宣告'); await pg.waitForTimeout(800); }
  ok('02 點位表 CSV → VAR 宣告', hasCsv && (await pg.inputValue('#code')).includes('VAR_INPUT'));
  await card('1. 需求輸入', '01_input.png').catch(e => console.log('shot', e.message));
  // 2. LLM 無金鑰 -> 錯誤需顯示
  await T('set'); await card('', '02_llm.png'); await T('gen');
  await pg.click('text=產生 ST');
  await pg.waitForFunction("document.getElementById('genout').className=='er'", null, { timeout: 30000 });
  ok('03 LLM 產生(無 API key)顯示錯誤而非當機', true, (await pg.innerText('#genout')).slice(0, 80));
  await card('2. LLM 設定', '02_llm.png').catch(() => {});
  // 3. RAG
  await T('rag');
  await pg.setInputFiles('#ragfile', { name: 'ton.md', mimeType: 'text/markdown', buffer: Buffer.from('TON on-delay timer PT preset Q output 計時器') });
  await pg.click('text=加入索引');
  await pg.waitForFunction("document.getElementById('ragst').textContent.includes('片段')");
  await pg.fill('#ragq', 'TON timer'); await pg.click('text=搜尋');
  await pg.waitForSelector('#ragout:not([hidden])');
  ok('04 RAG 上傳文件 + 檢索', (await pg.innerText('#ragout')).includes('ton.md'));
  await card('3. RAG', '03_rag.png').catch(() => {});
  // 4. check: error then clean
  await T('gen');
  await pg.fill('#code', 'PROGRAM X\nVAR a:INT; END_VAR\nb := 1;\nEND_PROGRAM');
  await pg.click('text=靜態檢查');
  await pg.waitForFunction("document.getElementById('chkout').textContent.includes('error')");
  ok('05 靜態檢查抓到未宣告變數', (await pg.innerText('#chkout')).includes('b'));
  await card('4. ST 程式碼', '04_check_error.png').catch(() => {});
  const motor = fs.readFileSync(R + 'examples/motor.st', 'utf8');
  await pg.fill('#code', motor);
  await pg.click('text=靜態檢查'); await pg.waitForFunction("document.getElementById('chkout').textContent.includes('無問題')");
  ok('06 motor.st 靜態檢查無問題', true);
  // 5. exports
  await T('exp');
  const fmts = { plcopen: ['program.xml', '<pou'], scl: ['.scl', 'ORGANIZATION_BLOCK'], l5x: ['.L5X', '<Routine'], gxworks: ['.txt', 'Label Name'], sysmac: ['.txt', 'Data Type'] };
  for (const [f, [ext, needle]] of Object.entries(fmts)) {
    await pg.selectOption('#expfmt', f);
    const [d] = await Promise.all([pg.waitForEvent('download'), pg.click('#tab_exp button')]);
    const txt = fs.readFileSync(await d.path(), 'utf8');
    ok('07 匯出 ' + f, d.suggestedFilename().endsWith(ext) && txt.includes(needle), d.suggestedFilename() + ' ' + txt.length + ' chars');
  }
  // 6. virtual PLC
  await T('sim');
  await pg.fill('#events', '2:start=true\n40:start=false');
  const t1 = Date.now();
  await pg.click('text=執行並繪製波形');
  await pg.waitForFunction("document.getElementById('runst').textContent.includes('週期')");
  ok('08 虛擬 PLC 執行 80 週期', (await pg.innerText('#runst')).includes('80'), (Date.now() - t1) + 'ms');
  ok('09 波形圖有繪製', await pg.evaluate("[...document.getElementById('wave').getContext('2d').getImageData(0,0,900,380).data].some(v=>v>0)"));
  await card('5. 虛擬 PLC', '05_vplc.png').catch(() => {});
  // 7. scenario
  await T('test');
  await pg.click('text=執行情境'); await pg.waitForSelector('#tstout:not([hidden])');
  ok('10 情境測試 PASS', (await pg.innerText('#tstout')).trim() === 'PASS');
  await pg.fill('#scn', '{"scan_ms":100,"steps":[{"name":"wrong","set":{"start":true},"ms":600,"expect":{"motor":false}}]}').catch(() => {});
  if (await pg.locator('#scn').count()) {
    await pg.click('text=執行情境'); await pg.waitForTimeout(800);
    ok('11 情境測試能偵測錯誤預期(FAIL)', (await pg.innerText('#tstout')).includes('FAIL'), (await pg.innerText('#tstout')).slice(0, 80));
    await card('6. 情境測試', '06_scenario_fail.png').catch(() => {});
  }
  // 8. profiles: strict overflow
  await T('sim');
  await pg.fill('#code', 'PROGRAM P\nVAR x : INT := 32767; END_VAR\nx := x + 1;\nEND_PROGRAM');
  await pg.fill('#events', '');
  for (const [p, exp] of [['iec', '週期'], ['strict', 'overflow'], ['saturate', '週期']]) {
    await pg.selectOption('#profile', p);
    await pg.click('text=執行並繪製波形'); await pg.waitForTimeout(700);
    ok('12 profile ' + p + ' 溢位行為', (await pg.innerText('#runst')).includes(exp), (await pg.innerText('#runst')).slice(0, 70));
  }
  ok('12b 錯誤後再成功,狀態不再顯示紅色', (await pg.getAttribute('#runst', 'class')) !== 'er', 'class=' + await pg.getAttribute('#runst', 'class'));
  // 9. advanced ST in UI
  await pg.selectOption('#profile', 'iec');
  for (const ex of ['struct_arrfield.st', 'review_m29.st', 'matrix.st']) {
    await pg.fill('#code', fs.readFileSync(R + 'examples/' + ex, 'utf8'));
    await pg.click('text=執行並繪製波形');
    await pg.waitForFunction("document.getElementById('runst').textContent.includes('週期') || document.getElementById('runst').textContent.includes('Error')");
    ok('13 範例 ' + ex + ' 於 UI 執行', (await pg.innerText('#runst')).includes('週期'));
  }
  await pg.screenshot({ path: S + '00_full_page.png', fullPage: true });
  // 10. no-scroll layout + status bar
  const noscroll = await pg.evaluate('document.documentElement.scrollHeight <= window.innerHeight && document.body.scrollHeight <= window.innerHeight');
  ok('13b 1280x800 整頁無垂直捲動', noscroll);
  for (const [w, h] of [[1920, 1080], [1280, 800]]) { await pg.setViewportSize({ width: w, height: h }); ok('13c ' + w + 'x' + h + ' 無垂直捲動', await pg.evaluate('document.documentElement.scrollHeight <= window.innerHeight')); }
  ok('13d 狀態列顯示檢查/模擬/情境結果', /情境 (PASS|FAIL)/.test(await pg.innerText('#st_tst')) && /模擬/.test(await pg.innerText('#st_run')) && /檢查/.test(await pg.innerText('#st_chk')), (await pg.innerText('#statusbar')).replace(/\n/g, ' | '));
  for (const t of ['gen','sim','test','exp','rag','set']) { await T(t); await pg.waitForTimeout(250); await pg.screenshot({ path: S + 'tab_' + t + '.png' }); }
  // UI2: 視覺系統 — 主題切換、WCAG AA 對比、toast、亮/暗截圖
  const lum = h => { const c = h.replace('#', '').match(/../g).map(x => parseInt(x, 16) / 255).map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const PAIRS = [['--fg', '--bg'], ['--fg', '--surface'], ['--fg', '--surface-2'], ['--fg-muted', '--surface'], ['--fg-muted', '--surface-2'], ['--fg-muted', '--bg'],
    ['--ac', '--surface'], ['--ac', '--ac-bg'], ['--ac-fg', '--ac'], ['--ac-fg', '--ac-hover'], ['--ok', '--ok-bg'], ['--er', '--er-bg'], ['--wn', '--wn-bg'], ['--ok', '--surface'], ['--er', '--surface'], ['--wn', '--surface'], ['--ok', '--surface-2'], ['--er', '--surface-2']];
  await pg.setViewportSize({ width: 1280, height: 800 });
  for (const th of ['light', 'dark']) {
    await pg.evaluate(t => setTheme(t), th);
    const vals = await pg.evaluate(ps => { const cs = getComputedStyle(document.documentElement); const o = {}; ps.flat().forEach(n => o[n] = cs.getPropertyValue(n).trim()); return o; }, PAIRS);
    const bad = PAIRS.map(([f, bg]) => [f + '/' + bg, ratio(vals[f], vals[bg])]).filter(([, r]) => r < 4.5);
    const min = Math.min(...PAIRS.map(([f, bg]) => ratio(vals[f], vals[bg])));
    ok('16 ' + th + ' 主題文字對比 ≥ 4.5:1 (WCAG AA)', bad.length === 0, 'min ' + min.toFixed(2) + (bad.length ? ' bad: ' + bad.map(([n, r]) => n + '=' + r.toFixed(2)).join(',') : ''));
    const bodyBg = await pg.evaluate(() => getComputedStyle(document.body).backgroundColor);
    ok('17 ' + th + ' 主題套用到 body 背景', th === 'dark' ? bodyBg === 'rgb(14, 18, 24)' : bodyBg === 'rgb(243, 245, 248)', bodyBg);
    await T('sim'); await pg.click('text=執行並繪製波形'); await pg.waitForTimeout(500);
    await T('gen'); await pg.fill('#code', motor); await pg.click('text=靜態檢查');
    await pg.waitForSelector('.toast.ok');
    if (th === 'light') ok('18 操作完成顯示 toast', (await pg.innerText('#toasts')).includes('檢查通過'), await pg.innerText('#toasts'));
    for (const t of ['gen', 'sim', 'test', 'exp', 'rag', 'set']) { await T(t); await pg.waitForTimeout(250); await pg.screenshot({ path: S + th + '_' + t + '.png' }); }
  }
  // 主題按鈕循環 auto → light → dark 並記住
  await pg.evaluate(() => setTheme('auto'));
  await pg.click('#themebtn'); const t1th = await pg.evaluate(() => document.documentElement.dataset.theme);
  await pg.click('#themebtn'); const t2th = await pg.evaluate(() => document.documentElement.dataset.theme);
  await pg.reload(); await pg.waitForFunction("document.querySelectorAll('#profile option').length>3");
  const kept = await pg.evaluate(() => document.documentElement.dataset.theme);
  ok('19 主題按鈕 auto→light→dark 且重新整理後保留', t1th === 'light' && t2th === 'dark' && kept === 'dark', [t1th, t2th, kept].join('→'));
  ok('20 localStorage 只存主題,不含 API key', await pg.evaluate(() => Object.keys(localStorage).every(k => k === 'plcst.theme')));
  await pg.evaluate(() => setTheme('auto'));
  // 按鈕載入狀態:執行中顯示 busy 並 disabled
  await T('sim'); await pg.fill('#cycles', '3000');
  const busySeen = await pg.evaluate(() => { const b = [...document.querySelectorAll('#tab_sim button')][0]; b.click(); return b.classList.contains('busy') && b.disabled; });
  await pg.waitForFunction("!document.querySelector('#tab_sim button').disabled");
  ok('21 執行中按鈕顯示載入狀態,完成後恢復', busySeen);
  ok('22 波形繪製後空狀態提示隱藏', await pg.evaluate(() => getComputedStyle(document.getElementById('waveempty')).display === 'none'));
  await pg.fill('#cycles', '80');
  // 10. mobile width
  await pg.setViewportSize({ width: 390, height: 844 });
  const overflow = await pg.evaluate('document.documentElement.scrollWidth - window.innerWidth');
  ok('14 手機寬度 390px 無水平捲動', overflow <= 0, 'overflow ' + overflow + 'px');
  await pg.screenshot({ path: S + '07_mobile.png' });
  ok('15 全程無 JS 錯誤', errs.length === 0, errs.join(' | '));
  fs.writeFileSync(S + 'results.json', JSON.stringify(res, null, 1));
  console.log(res.filter(r => r.pass).length + '/' + res.length + ' PASS');
  await b.close();
  process.exit(res.every(r => r.pass) ? 0 : 1);
})().catch(e => { console.error('E2E CRASH', e.message); process.exit(2); });
