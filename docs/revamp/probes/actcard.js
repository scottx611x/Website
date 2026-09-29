const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 100)));
  await p.goto('http://127.0.0.1:5055/birds/stats', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  const cards = await p.evaluate(() => [...document.querySelectorAll('.act-card')].map(e => {
    const r = e.getBoundingClientRect();
    return { id: e.id, top: Math.round(r.top + scrollY), w: Math.round(r.width),
             title: e.querySelector('.act-title').textContent,
             spans: Math.round(r.width) > 900 };
  }));
  console.log('  act cards:'); cards.forEach(x => console.log('    ' + JSON.stringify(x)));
  for (const x of cards) {
    await p.evaluate(t => scrollTo(0, t - 120), x.top);
    await p.waitForTimeout(700);
    await p.screenshot({ path: process.env.SP + '/card-' + x.id + '.png', clip: { x: 0, y: 90, width: 1440, height: 330 } });
  }
  console.log('  doc height:', await p.evaluate(() => document.documentElement.scrollHeight));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
