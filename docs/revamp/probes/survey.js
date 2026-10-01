const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const read = p => p.evaluate(() => {
  const sv = document.getElementById('vmSurvey');
  const t = [...document.querySelectorAll('.bf-tile')];
  const names = t.map(x => x._t && x._t.name).filter(Boolean);
  return {
    overview: document.querySelector('.bf-canvas').classList.contains('overview'),
    label: sv ? sv.querySelector('span').textContent : null,
    pressed: sv ? sv.getAttribute('aria-pressed') : null,
    tiles: t.length, dupes: names.length - new Set(names).size,
  };
});
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 100)));
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2300);
  console.log('  start        ', JSON.stringify(await read(p)));

  await p.click('#vmBtn'); await p.waitForTimeout(300);
  await p.click('#vmSurvey'); await p.waitForTimeout(1500);
  console.log('  via control  ', JSON.stringify(await read(p)));

  await p.click('#vmBtn'); await p.waitForTimeout(300);
  await p.click('#vmSurvey'); await p.waitForTimeout(1500);
  console.log('  toggled back ', JSON.stringify(await read(p)));

  // and the label must follow a PINCH, not just its own button
  await p.evaluate(() => window.bfScale(120)); await p.waitForTimeout(1400);
  console.log('  after a pinch', JSON.stringify(await read(p)));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
