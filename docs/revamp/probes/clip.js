const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [w, h] of [[360, 740], [390, 780], [1440, 860]]) {
    const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: w < 700, hasTouch: w < 700 });
    await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
    const p = await c.newPage();
    await p.goto('http://127.0.0.1:5055/birds?view=field', { waitUntil: 'networkidle' });
    await p.waitForTimeout(1500);
    if (w < 700) await p.tap('#vmBtn'); else await p.click('#vmBtn');
    await p.waitForTimeout(400);
    console.log('  ' + (w+'x'+h).padEnd(9) + ' ' + JSON.stringify(await p.evaluate(() => {
      const pop = document.getElementById('vmPop').getBoundingClientRect();
      let clipped = 0;
      document.querySelectorAll('.vm-opt, .vm-count, .vm-head').forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width && (r.right > pop.right + 1 || e.scrollWidth > e.clientWidth + 1)) clipped++;
      });
      return { clippedRows: clipped, popInViewport: pop.left >= -1 && pop.right <= innerWidth + 1,
               subsShown: [...document.querySelectorAll('.vm-sub')].filter(e => e.offsetParent).length,
               countsShown: [...document.querySelectorAll('.vm-num')].filter(e => e.offsetParent).length };
    })));
    await c.close();
  }
  await b.close();
})();
