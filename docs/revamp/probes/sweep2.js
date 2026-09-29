const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [w, h] of [[390, 780], [820, 900], [1440, 860], [1920, 1080]]) {
    const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: w < 700, hasTouch: w < 700 });
    await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto('http://127.0.0.1:5055/birds?view=field', { waitUntil: 'networkidle' });
    await p.waitForTimeout(2200);
    const r = await p.evaluate(() => {
      const nav = document.querySelector('.site-nav').getBoundingClientRect();
      const hdr = document.querySelector('.gallery-header').getBoundingClientRect();
      const vis = s => { const e = document.querySelector(s); if (!e) return false;
        const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
      const over = (a, bb) => { const x = document.querySelector(a), y = document.querySelector(bb);
        if (!x || !y) return null; const p = x.getBoundingClientRect(), q = y.getBoundingClientRect();
        if (!p.width || !q.width) return null;
        return !(p.right <= q.left || q.right <= p.left || p.bottom <= q.top || q.bottom <= p.top); };
      return { seam: +(hdr.top - nav.bottom).toFixed(2),
               chromeH: Math.round(hdr.bottom), fieldPct: Math.round(100 * (innerHeight - hdr.bottom) / innerHeight),
               title: vis('.gallery-header h1'), search: vis('#speciesSearch'),
               order: document.querySelectorAll('.media-stat .media-link').length,
               hintOverTilt: over('.bf-hint', '.bf-tilt'),
               xScroll: document.documentElement.scrollWidth > innerWidth + 1 };
    });
    console.log('  %s %s errors=%d', (w+'x'+h).padEnd(10), JSON.stringify(r), errs.length);
    errs.forEach(e => console.log('     ! ' + e));
    await c.close();
  }
  await b.close();
})();
