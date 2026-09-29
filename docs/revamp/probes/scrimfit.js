const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  for (const q of ['', '?family=Old+World+Sparrows', '?family=Old+World+Sparrows&sort=oldest', '?media=video&area=elsewhere']) {
    const p = await c.newPage();
    await p.goto('http://127.0.0.1:5055/birds' + q, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2200);
    const r = await p.evaluate(() => {
      const hdr = document.querySelector('.gallery-header').getBoundingClientRect();
      const scrim = getComputedStyle(document.body, '::before');
      return { barBottom: +hdr.bottom.toFixed(1), scrimH: scrim.height,
               gap: +(hdr.bottom - parseFloat(scrim.height)).toFixed(1),
               label: (document.getElementById('vmLabel') || {}).textContent };
    });
    console.log('  ' + (q || '(none)').padEnd(38) + ' ' + JSON.stringify(r));
    await p.close();
  }
  await b.close();
})();
