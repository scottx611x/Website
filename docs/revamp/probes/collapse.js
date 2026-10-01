const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  for (const url of ['/birds/stats', '/birds/live', '/birds?view=grid', '/photography']) {
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto('http://127.0.0.1:5055' + url, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2000);
    const at = async y => { await p.evaluate(v => scrollTo(0, v), y); await p.waitForTimeout(600);
      return p.evaluate(() => { const h = document.querySelector('.gallery-header');
        const r = h.getBoundingClientRect();
        return { stuck: h.classList.contains('is-stuck'), h: Math.round(r.height),
                 bottom: Math.round(r.bottom), optedIn: !!h.dataset.collapse }; }); };
    const top = await at(0), down = await at(1400);
    console.log('  ' + url.padEnd(18) + ' rest ' + JSON.stringify(top) + '  scrolled ' + JSON.stringify(down) + ' errors=' + errs.length);
    errs.forEach(e => console.log('     ! ' + e));
    await p.close();
  }
  await b.close();
})();
