const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const state = p => p.evaluate(() => {
  const t = [...document.querySelectorAll('.bf-tile')];
  const names = t.map(x => x._t && x._t.name).filter(Boolean);
  return {
    overview: document.querySelector('.bf-canvas').classList.contains('overview'),
    tiles: t.length,
    distinctSpecies: new Set(names).size,
    dupes: names.length - new Set(names).size,
    tileW: t[0] ? Math.round(t[0].getBoundingClientRect().width) : 0,
    heights: t.slice(0, 4).map(x => Math.round(x.getBoundingClientRect().height)),
    counts: t.slice(0, 4).map(x => { const c = x.querySelector('.bf-tally'); return c ? +c.textContent : null; }),
  };
});
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 110)));
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  console.log('  photos   ', JSON.stringify(await state(p)));

  await p.evaluate(() => window.bfScale(120));            // zoom out past the threshold
  await p.waitForTimeout(1400);
  const ov = await state(p);
  console.log('  survey   ', JSON.stringify(ov));
  await p.screenshot({ path: process.env.SP + '/survey.png' });

  await p.evaluate(() => window.bfScale(260));            // and back
  await p.waitForTimeout(1400);
  console.log('  photos   ', JSON.stringify(await state(p)));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
