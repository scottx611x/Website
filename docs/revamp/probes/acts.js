const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 100)));
  await p.goto('http://127.0.0.1:5055/birds/stats', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  // park the pointer away from the sticky nav: it sits at 0,0 by default,
  // which is ON the nav, so :hover expanded every act and the collapse
  // looked broken when it was not.
  await p.mouse.move(720, 620);
  const read = () => p.evaluate(() => {
    const nav = document.getElementById('stat-jump');
    const visibleLinks = [...nav.querySelectorAll('a')].filter(a => a.getBoundingClientRect().width > 1);
    return {
      navW: Math.round(nav.getBoundingClientRect().width),
      overflows: nav.scrollWidth > nav.clientWidth + 1,
      actOn: [...nav.querySelectorAll('.sj-act')].findIndex(s => s.classList.contains('on')) + 1,
      linkOn: (nav.querySelector('a.on') || {}).textContent || null,
      shown: [...nav.querySelectorAll('a')].filter(a => a.getBoundingClientRect().width > 6).length,
      navTop: Math.round(nav.getBoundingClientRect().top),
      hiddenBehindNav: (() => { const r = nav.getBoundingClientRect();
        const e = document.elementFromPoint(r.left + 40, r.top + r.height / 2);
        return !(e && e.closest && e.closest('#stat-jump')); })(),
      collapsedMaxW: getComputedStyle(nav.querySelector('.sj-act:not(.on) a') || nav.querySelector('a')).maxWidth,
    };
  });
  for (const y of [0, 900, 2200, 3600, 5000, 6200]) {
    await p.evaluate(v => scrollTo(0, v), y);
    await p.waitForTimeout(800);
    console.log('  scrollY ' + String(y).padStart(4) + ' -> ' + JSON.stringify(await read()));
  }
  await p.evaluate(() => scrollTo(0, 2200)); await p.waitForTimeout(700);
  await p.screenshot({ path: process.env.OUT || '/tmp/acts.png', clip: { x: 0, y: 0, width: 1440, height: 120 } });
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
