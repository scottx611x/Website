const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [w, h] of [[390, 780], [820, 900], [1440, 860]]) {
    const c = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: w < 700, hasTouch: w < 700 });
    await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto('http://127.0.0.1:5055/birds?view=field', { waitUntil: 'networkidle' });
    await p.waitForTimeout(1800);
    const r = await p.evaluate(() => {
      const hd = document.querySelector('.gallery-header').getBoundingClientRect();
      const rows = new Set([...document.querySelectorAll('.gallery-header > *, .gallery-header .bird-filter')]
        .filter(e => e.getBoundingClientRect().height > 0)
        .map(e => Math.round(e.getBoundingClientRect().top)));
      return { chromeH: Math.round(hd.bottom), fieldPct: Math.round(100 * (innerHeight - hd.bottom) / innerHeight),
               barRows: rows.size, label: (document.getElementById('vmLabel') || {}).textContent };
    });
    console.log('  ' + (w+'x'+h).padEnd(9) + ' ' + JSON.stringify(r) + ' errors=' + errs.length);
    if (w === 1440) {
      await p.click('#vmBtn'); await p.waitForTimeout(400);
      await p.screenshot({ path: process.env.SP + '/menu_open.png', clip: { x: 0, y: 0, width: 1440, height: 520 } });
      console.log('    menu opens:', await p.evaluate(() => !document.getElementById('vmPop').hidden));
      await p.click('.vm-opt:nth-of-type(1)'); await p.waitForTimeout(2000);
      console.log('    picked order ->', new URL(p.url()).search.slice(0, 60));
    }
    errs.forEach(e => console.log('     ! ' + e));
    await c.close();
  }
  await b.close();
})();
