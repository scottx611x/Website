/* Regression: a bounded (finite) field tucked its first row under the header.
 *
 * Worst case is a species view — few enough frames to take the finite path,
 * and the header grows a chip row when a bird is selected, so the chrome is
 * at its tallest exactly when the clamp was at its loosest. No tile may sit
 * under the header band on arrival.
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const look = () => {
  const hdr = document.querySelector('.gallery-header');
  const hb = hdr ? hdr.getBoundingClientRect().bottom : 0;
  const t = [...document.querySelectorAll('.bf-tile')].map(e => e.getBoundingClientRect());
  const on = t.filter(b => b.right > 0 && b.left < innerWidth && b.bottom > 0 && b.top < innerHeight);
  return {
    headerBottom: Math.round(hb),
    tiles: t.length,
    onScreen: on.length,
    clipped: on.filter(b => b.top < hb - 1).length,
    minTop: on.length ? Math.round(Math.min(...on.map(b => b.top))) : null,
  };
};

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  // Filtered FIELD views (the chip form) take the finite path — these are the
  // ones that must clear the chrome. Unfiltered shuffle is an endless plane and
  // legitimately extends under the floating header, so it is not tested here.
  const paths = ['/birds?bird=Common+Kestrel', '/birds?bird=Barred+Owl',
                 '/birds?family=Falcons', '/birds?bird=Northern+Cardinal'];
  for (const [w, h] of [[1440, 860], [390, 780]]) {
    const c = await b.newContext({viewport: {width: w, height: h}, isMobile: w < 700, hasTouch: w < 700});
    await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
    const p = await c.newPage();
    for (const path of paths) {
      await p.goto(BASE + path, {waitUntil: 'networkidle'});
      await p.waitForTimeout(2300);
      const r = await p.evaluate(look);
      console.log('  %s %-34s %s %s', (w + 'x' + h).padEnd(9), path,
                  JSON.stringify(r), r.clipped === 0 ? 'OK' : 'CLIPPED');
    }
    await c.close();
  }
  await b.close();
})();
