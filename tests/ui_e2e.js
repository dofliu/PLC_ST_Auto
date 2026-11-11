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
const SS3 = path.resolve(process.env.UI3_SHOTS || S) + '/'; fs.mkdirSync(SS3, { recursive: true });
const SS4 = path.resolve(process.env.UI4_SHOTS || S) + '/'; fs.mkdirSync(SS4, { recursive: true });
const wv_x = (bx, idx, n) => 132 + (idx + 0.5) * (bx.width - 142) / n;
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
  await pg.evaluate(() => { document.getElementById('batchbox').open = true; });
  await pg.fill('#events', '2:start=true\n40:start=false');
  const t1 = Date.now();
  await pg.click('text=執行並繪製波形');
  await pg.waitForFunction("document.getElementById('runst').textContent.includes('週期')");
  ok('08 虛擬 PLC 執行 80 週期', (await pg.innerText('#runst')).includes('80'), (Date.now() - t1) + 'ms');
  ok('09 波形圖有繪製', await pg.evaluate("[...document.getElementById('wave').getContext('2d').getImageData(0,0,document.getElementById('wave').width,document.getElementById('wave').height).data].some(v=>v>0)"));
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
  const busySeen = await pg.evaluate(() => { const b = document.getElementById('batchbtn'); b.click(); return b.classList.contains('busy') && b.disabled; });
  await pg.waitForFunction("!document.getElementById('batchbtn').disabled");
  ok('21 執行中按鈕顯示載入狀態,完成後恢復', busySeen);
  ok('22 波形繪製後空狀態提示隱藏', await pg.evaluate(() => getComputedStyle(document.getElementById('waveempty')).display === 'none'));
  await pg.fill('#cycles', '80');
  // UI4: 模擬儀表板 — 執行/暫停/單步/重設、I/O 開關與燈號、波形縮放/游標/STRING/標籤
  await T('gen'); await pg.fill('#code', motor); await T('sim');
  await pg.evaluate(() => { document.getElementById('batchbox').open = true; });
  await pg.click('#sim_reset'); await pg.waitForFunction("document.getElementById('simmode').textContent=='暫停'");
  const io0 = await pg.evaluate(() => [document.querySelectorAll('#io .sw').length, document.querySelectorAll('#io .lamp').length, document.querySelectorAll('#io .val').length, document.getElementById('simclk').textContent, document.getElementById('simmode').textContent]);
  ok('31 重設後建立 I/O 面板:2 個輸入開關、1 個輸出燈號、1 個數值', io0[0] === 2 && io0[1] === 1 && io0[2] === 1 && io0[3].includes('週期 0') && io0[4] === '暫停', JSON.stringify(io0));
  await pg.click('.sw[aria-label=start]');
  ok('32 暫停中切換輸入:標示為待套用(下一掃描才生效)', await pg.evaluate(() => document.querySelector('.sw[aria-label=start]').classList.contains('pend') && !document.querySelector('.lamp').classList.contains('on')));
  await pg.click('#sim_step'); await pg.waitForFunction("document.getElementById('simclk').textContent.includes('週期 1 ')");
  ok('32b 單步後輸出燈號亮、待套用標記清除', await pg.evaluate(() => document.querySelector('.lamp').classList.contains('on') && !document.querySelector('#io .pend')));
  await pg.screenshot({ path: SS4 + 'sim_step_lamp_on.png' });
  await pg.click('#sim_run'); await pg.waitForTimeout(1200);
  const runSt = await pg.evaluate(() => [document.getElementById('simmode').textContent, document.getElementById('sim_pause').disabled, document.getElementById('sim_step').disabled, +document.getElementById('simclk').textContent.match(/週期 (\d+)/)[1]]);
  ok('33 連續執行:狀態「執行中」、暫停可按、單步停用、週期持續增加', runSt[0] === '執行中' && !runSt[1] && runSt[2] && runSt[3] > 30, JSON.stringify(runSt));
  ok('33b 狀態列顯示模擬週期', /模擬 週期 \d+/.test(await pg.innerText('#st_run')), await pg.innerText('#st_run'));
  await pg.screenshot({ path: SS4 + 'sim_running.png' });
  await pg.click('#sim_pause'); await pg.waitForTimeout(150);
  const c1 = await pg.innerText('#simclk'); await pg.waitForTimeout(500);
  ok('34 暫停後週期不再增加', c1 === await pg.innerText('#simclk') && await pg.innerText('#simmode') === '暫停', c1);
  ok('34b 執行中波形跟隨最新週期', await pg.evaluate(() => { const n = lastWave.rows.length, [i0, sp] = wvRange(n); return i0 + sp === n; }));
  const cntBefore = await pg.evaluate(() => +document.querySelector('#io .val').textContent);
  ok('34c TON 計時後內部計數 cnt 增加', cntBefore > 0, 'cnt=' + cntBefore);
  await pg.click('.sw[aria-label=stop]'); await pg.keyboard.press('Alt+s'); await pg.waitForTimeout(400);
  ok('35 Alt+S 單步:stop 生效後燈號熄滅', await pg.evaluate(() => !document.querySelector('.lamp').classList.contains('on')));
  // 縮放 / 平移 / 游標
  const sp0 = await pg.evaluate(() => wv.span);
  await pg.click('[aria-label=放大]'); const sp1 = await pg.evaluate(() => wv.span);
  const box = await pg.locator('#wave').boundingBox();
  await pg.mouse.move(box.x + box.width * 0.6, box.y + 20); await pg.mouse.wheel(0, 200); await pg.waitForTimeout(100);
  const sp2 = await pg.evaluate(() => wv.span);
  ok('36 放大按鈕與滾輪縮放改變可視範圍', sp1 < sp0 && sp2 > sp1, [sp0, sp1, sp2].join('→'));
  await pg.mouse.move(box.x + box.width * 0.5, box.y + 20); await pg.waitForTimeout(100);
  ok('37 游標讀值顯示週期與時間', /游標 週期 \d+ · \d+ ms/.test(await pg.innerText('#wavecur')), await pg.innerText('#wavecur'));
  const i0a = await pg.evaluate(() => wv.i0);
  await pg.mouse.down(); await pg.mouse.move(box.x + box.width * 0.8, box.y + 20, { steps: 4 }); await pg.mouse.up();
  ok('37b 拖曳平移', await pg.evaluate(() => wv.i0) !== i0a || i0a === 0, i0a + '→' + await pg.evaluate(() => wv.i0));
  await pg.dblclick('#wave'); ok('37c 雙擊全覽', await pg.evaluate(() => wv.i0 === 0 && wv.span === lastWave.rows.length));
  await pg.screenshot({ path: SS4 + 'wave_cursor.png' });
  // STRING 與長名稱:文字帶、無 NaN、標籤不重疊
  const strProg = "PROGRAM S\nVAR_INPUT go : BOOL; END_VAR\nVAR_OUTPUT msg : STRING; very_long_variable_name_for_label_test : INT; ratio : REAL; END_VAR\nVAR n : INT; END_VAR\nn := n + 1;\nIF go THEN msg := 'RUNNING'; ELSE msg := 'IDLE'; END_IF;\nvery_long_variable_name_for_label_test := n MOD 7;\nratio := INT_TO_REAL(n) / 3.0;\nEND_PROGRAM";
  await pg.fill('#code', strProg);
  await pg.evaluate(() => { window.__txt = []; const f = CanvasRenderingContext2D.prototype.fillText; CanvasRenderingContext2D.prototype.fillText = function (t, ...a) { window.__txt.push(String(t)); return f.call(this, t, ...a); }; });
  await pg.fill('#events', '10:go=true\n30:go=false'); await pg.fill('#cycles', '40');
  await pg.click('#batchbtn'); await pg.waitForFunction("document.getElementById('simmode').textContent=='批次回放'");
  const lanes = await pg.evaluate(() => wv.lanes.map(l => ({ nm: l.nm, kind: l.kind, y: l.y, h: l.h })));
  ok('38 STRING 以文字帶顯示,內容可讀、沒有 NaN', lanes.find(l => l.nm === 'msg').kind === 'str' && await pg.evaluate(() => __txt.includes("'RUNNING'") && __txt.includes("'IDLE'") && !__txt.some(t => t.includes('NaN'))));
  ok('38b 每個變數一條不重疊的軌道', lanes.every((l, i) => i === 0 || l.y >= lanes[i - 1].y + lanes[i - 1].h), lanes.map(l => l.nm + ':' + l.y).join(' '));
  ok('38c 長變數名截斷不壓到波形區', await pg.evaluate(() => { const g = document.getElementById('wave').getContext('2d'); g.font = '600 12px ' + getComputedStyle(document.documentElement).getPropertyValue('--font-code'); return __txt.filter(t => t.startsWith('very_long')).every(t => t.endsWith('…') && g.measureText(t).width <= wv.LM - 12); }));
  ok('38d 數值軌顯示範圍', await pg.evaluate(() => __txt.some(t => /^0…6$/.test(t))));
  const bx2 = await pg.locator('#wave').boundingBox();
  await pg.mouse.move(bx2.x + wv_x(bx2, 20, 40), bx2.y + 20); await pg.waitForTimeout(150);
  ok('39 批次回放:游標移到週期 21,I/O 面板顯示該週期值', await pg.evaluate(() => document.querySelector('.sw[aria-label=go]').getAttribute('aria-checked') === 'true' && document.querySelector('.sw').disabled), await pg.innerText('#wavecur'));
  await pg.screenshot({ path: SS4 + 'wave_string_lanes.png' });
  await pg.evaluate(() => setTheme('dark')); await pg.waitForTimeout(150); await pg.screenshot({ path: SS4 + 'dark_sim.png' });
  await pg.evaluate(() => setTheme('auto'));
  // 互動模擬執行期錯誤:停止並標記行號
  await pg.fill('#code', 'PROGRAM E\nVAR a : ARRAY[1..3] OF INT; i : INT; END_VAR\ni := i + 1;\na[i] := i;\nEND_PROGRAM');
  await pg.click('#sim_run'); await pg.waitForFunction("document.getElementById('simmode').textContent=='錯誤'", null, { timeout: 5000 });
  ok('40 互動模擬執行期錯誤:停止、狀態「錯誤」、標記第 4 行', await pg.evaluate(() => !sim.run && document.querySelectorAll('#gutter div')[3].classList.contains('er')));
  await pg.screenshot({ path: SS4 + 'sim_runtime_error.png' });
  await pg.evaluate(() => { document.getElementById('chkout').hidden = true; });
  await pg.fill('#events', '2:start=true\n40:start=false\n60:stop=true'); await pg.fill('#cycles', '80');
  // UI3: 程式碼編輯器 — 行號、語法色彩、即時檢查標記、點問題跳行、快捷鍵、捲動同步
  await T('gen'); await pg.fill('#code', motor); await pg.waitForTimeout(300);
  const nl = motor.split('\n').length;
  ok('23 行號數量 = 程式行數', await pg.locator('#gutter div').count() - 1 === nl, nl + ' lines');
  ok('23b ST 語法色彩(關鍵字/型別/FB/時間常數/註解)', await pg.evaluate(() => ['kw', 'ty', 'fb', 'num'].every(c => document.querySelector('#hl .t-' + c))));
  ok('23c 上色層與輸入框字型/行高/內距一致(游標不會錯位)', await pg.evaluate(() => { const a = getComputedStyle(document.getElementById('hl')), b = getComputedStyle(document.getElementById('code'));
    return ['fontFamily', 'fontSize', 'lineHeight', 'paddingTop', 'paddingLeft', 'whiteSpace', 'letterSpacing'].every(k => a[k] === b[k]); }));
  const bad = 'PROGRAM X\nVAR a : INT; END_VAR\na := 1;\nb := a + 1;\nEND_PROGRAM';
  const nToast = await pg.locator('.toast').count();
  await pg.fill('#code', bad);
  await pg.waitForFunction("document.querySelector('#gutter div:nth-child(4)').classList.contains('er')", null, { timeout: 4000 });
  ok('24 輸入後自動檢查,錯誤行(第 4 行)標記在行號與程式行', await pg.evaluate(() => document.querySelectorAll('#hl .l')[3].classList.contains('er') && document.querySelectorAll('#gutter .er').length === 1));
  ok('24b 自動檢查不跳 toast、不自動展開問題抽屜', (await pg.locator('.toast').count()) <= nToast && await pg.evaluate(() => document.getElementById('chkout').hidden));
  ok('24c 狀態列與抽屜摘要同步更新', /1 錯/.test(await pg.innerText('#st_chk')) && /1 錯誤/.test(await pg.innerText('#drawerinfo')));
  await pg.screenshot({ path: SS3 + 'editor_error_marked.png' });
  await pg.click('#drawer>div'); await pg.click('#chkout .iss[data-line="4"]');
  const sel = await pg.evaluate(() => { const t = document.getElementById('code'); return [document.activeElement === t, t.value.slice(t.selectionStart, t.selectionEnd)]; });
  ok('25 點擊問題跳到該行並選取', sel[0] && sel[1] === 'b := a + 1;', JSON.stringify(sel));
  ok('25b 游標位置顯示行 4', (await pg.innerText('#curpos')).includes('行 4'), await pg.innerText('#curpos'));
  await pg.screenshot({ path: SS3 + 'editor_jump_to_issue.png' });
  await pg.fill('#code', 'PROGRAM X\nVAR a : INT; END_VAR\nIF a > 1 THEN\n  a := 0;\nEND_PROGRAM');
  await pg.waitForFunction("document.querySelector('#gutter div:nth-child(5)').classList.contains('er')", null, { timeout: 4000 });
  ok('26 語法錯誤也有行號並標記(第 5 行)', (await pg.innerText('#chkout')).includes('line 5'));
  // 快捷鍵:Tab 縮排、Enter 自動縮排、Ctrl+/ 註解、Ctrl+Enter 執行
  await pg.fill('#code', 'PROGRAM K\nVAR a : INT; END_VAR\nIF a = 0 THEN\nEND_PROGRAM');
  await pg.evaluate(() => { const t = document.getElementById('code'); const i = t.value.indexOf('THEN') + 4; t.focus(); t.setSelectionRange(i, i); });
  await pg.keyboard.press('Enter'); await pg.keyboard.type('a := 1;');
  ok('27 THEN 後 Enter 自動縮排 4 格', (await pg.inputValue('#code')).includes('THEN\n    a := 1;'), JSON.stringify((await pg.inputValue('#code')).split('\n')[3]));
  await pg.keyboard.press('Control+/');
  ok('27b Ctrl+/ 註解目前行', (await pg.inputValue('#code')).includes('    // a := 1;'));
  await pg.keyboard.press('Control+/');
  ok('27c 再按 Ctrl+/ 取消註解', (await pg.inputValue('#code')).includes('    a := 1;') && !(await pg.inputValue('#code')).includes('//'));
  await pg.keyboard.press('Tab');
  ok('27d Tab 縮排並保留焦點在編輯器', (await pg.inputValue('#code')).includes('        a := 1;') && await pg.evaluate(() => document.activeElement.id === 'code'));
  await pg.keyboard.press('Shift+Tab');
  ok('27e Shift+Tab 取消縮排', (await pg.inputValue('#code')).includes('\n    a := 1;'));
  await pg.keyboard.press('Control+z');
  ok('27f Ctrl+Z 可復原編輯器操作', (await pg.inputValue('#code')).includes('        a := 1;'));
  await pg.keyboard.press('Escape'); await pg.keyboard.press('Tab');
  ok('27g Esc 後 Tab 可離開編輯器(鍵盤不受困)', await pg.evaluate(() => document.activeElement.id !== 'code'));
  await pg.fill('#code', motor); await pg.focus('#code');
  await pg.evaluate(() => { document.getElementById('runst').textContent = ''; });
  await pg.keyboard.press('Control+Enter');
  await pg.waitForFunction("document.getElementById('runst').textContent.includes('週期')");
  ok('28 Ctrl+Enter 切到模擬頁並執行', await pg.evaluate(() => document.getElementById('tab_sim').classList.contains('on')));
  // 長程式:跳到第 180 行後,上色層與行號跟著捲動
  await T('gen');
  const long = 'PROGRAM L\nVAR i : INT; END_VAR\n' + Array.from({ length: 200 }, (_, k) => 'i := i + ' + k + '; (* line ' + (k + 3) + ' *)').join('\n') + '\nEND_PROGRAM';
  await pg.fill('#code', long); await pg.evaluate(() => jumpTo(180));
  const sc = await pg.evaluate(() => [document.getElementById('code').scrollTop, document.getElementById('hl').scrollTop, document.getElementById('gutter').scrollTop]);
  ok('29 長程式跳行後捲動同步(輸入框/上色層/行號)', sc[0] > 0 && sc[0] === sc[1] && sc[1] === sc[2], sc.join(','));
  const vis = await pg.evaluate(() => { const g = document.querySelectorAll('#gutter div')[179].getBoundingClientRect(), e = document.getElementById('editor').getBoundingClientRect(); return g.top >= e.top && g.bottom <= e.bottom; });
  ok('29b 第 180 行在可視範圍', vis);
  await pg.screenshot({ path: SS3 + 'editor_long_jump.png' });
  // 程式化載入(點位表 → VAR)也會重繪
  await pg.fill('#tags', fs.readFileSync(R + 'examples/points.csv', 'utf8'));
  await pg.click('text=點位表 → VAR 宣告'); await pg.waitForTimeout(600);
  ok('30 程式由點位表產生後行號/上色重繪', await pg.evaluate(() => document.querySelectorAll('#gutter div').length - 1 === document.getElementById('code').value.split('\n').length));
  await pg.fill('#code', bad); await pg.waitForFunction("document.querySelector('#gutter .er')", null, { timeout: 4000 });
  for (const th of ['light', 'dark']) { await pg.evaluate(t => setTheme(t), th); await pg.waitForTimeout(150); await pg.screenshot({ path: SS3 + th + '_editor.png' }); }
  await pg.evaluate(() => setTheme('auto')); await pg.fill('#code', motor);
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
