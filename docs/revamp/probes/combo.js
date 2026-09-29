const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const rows = p => p.evaluate(() => [...document.querySelectorAll('.bc-opt')].map(o => ({
  name: o.querySelector('.bc-name').textContent,
  fam: o.querySelector('.bc-name').classList.contains('is-fam'),
  meta: o.querySelector('.bc-meta').textContent })));
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 100)));
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);

  await p.click('#speciesSearch'); await p.waitForTimeout(400);
  const empty = await rows(p);
  console.log('  focus (empty): %d rows, first = %s [%s]', empty.length, empty[0].name, empty[0].meta);

  for (const q of ['wood', 'hawk', 'owl', 'xyzzy']) {
    await p.fill('#speciesSearch', q); await p.waitForTimeout(400);
    const r = await rows(p);
    console.log('  "%s" -> %s', q, r.length ? r.slice(0, 4).map(x => (x.fam ? '[' + x.name + ']' : x.name)).join(' | ') : 'no matches');
  }

  // keyboard: arrow to the second row, Enter
  await p.fill('#speciesSearch', 'wood'); await p.waitForTimeout(400);
  await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown');
  const onRow = await p.evaluate(() => (document.querySelector('.bc-opt.on') || {}).textContent);
  await p.keyboard.press('Enter'); await p.waitForTimeout(2200);
  console.log('  keyboard: highlighted "%s" -> %s', (onRow || '').trim(), new URL(p.url()).search);

  // mouse pick of a family
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1200);
  await p.click('#speciesSearch'); await p.fill('#speciesSearch', 'woodp'); await p.waitForTimeout(400);
  await p.screenshot({ path: process.env.SP + '/combo.png', clip: { x: 900, y: 60, width: 540, height: 460 } });
  await p.locator('.bc-opt').first().click(); await p.waitForTimeout(2200);
  console.log('  mouse: -> %s', new URL(p.url()).search);
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
