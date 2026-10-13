/* The view menu must stay fully on screen.
 *
 * It anchored to the button's right edge, which was fine while the button sat
 * at the right of the bar. The one-row header moved it left on narrow screens
 * and the panel ran off the side — most of the menu unreachable.
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  for (const [w, h] of [[390, 780], [430, 930], [560, 900], [720, 900], [1440, 860]]) {
    const c = await b.newContext({viewport: {width: w, height: h}, isMobile: w < 700, hasTouch: w < 700});
    await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
    const p = await c.newPage();
    await p.goto(BASE + '/birds?bird=Northern+Flicker', {waitUntil: 'domcontentloaded'});
    await p.waitForTimeout(2500);
    await p.click('#vmBtn');
    await p.waitForTimeout(500);
    const r = await p.evaluate(() => {
      const pop = document.getElementById('vmPop');
      const b = pop.getBoundingClientRect();
      const items = [...pop.querySelectorAll('.vm-opt')].map(e => e.getBoundingClientRect());
      return {
        left: Math.round(b.left), right: Math.round(b.right),
        width: Math.round(b.width), vw: innerWidth,
        offLeft: b.left < -0.5, offRight: b.right > innerWidth + 0.5,
        optsClipped: items.filter(i => i.left < -0.5 || i.right > innerWidth + 0.5).length,
      };
    });
    const ok = !r.offLeft && !r.offRight && r.optsClipped === 0;
    console.log('  %s %s %s', (w + 'x' + h).padEnd(10), JSON.stringify(r), ok ? 'OK' : 'CLIPPED');
    await c.close();
  }
  await b.close();
})();
