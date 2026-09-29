const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055/birds?family=Old+World+Sparrows', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  console.log(JSON.stringify(await p.evaluate(() => {
    const out = [];
    document.querySelectorAll('.gallery-header h1, .gallery-header .birds-subnav, .gallery-header .subnav-focus, .gallery-header .bird-filter, .gallery-header .view-menu, .gallery-header .bird-active, .gallery-header .bird-active-meta, .gallery-header .filter-chips')
      .forEach(e => {
        const r = e.getBoundingClientRect();
        if (!r.width) return;
        out.push({ el: (e.className || e.tagName).toString().slice(0, 22),
                   left: Math.round(r.left), top: Math.round(r.top),
                   bottom: Math.round(r.bottom), midY: Math.round(r.top + r.height / 2) });
      });
    return out;
  }), null, 1));
  await p.screenshot({ path: process.env.SP + '/align.png', clip: { x: 0, y: 0, width: 1440, height: 230 } });
  await b.close();
})();
