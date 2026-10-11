/* A7: clicking "See all photos" on the home page lands on /birds with the
 * field drifted off to the top-left, out of view.
 *
 * Measures, for a direct load and for the click-through, how many tiles
 * actually intersect the viewport and where the canvas transform sits. A
 * healthy field has tiles on screen; the bug shows as 0.
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const probe = () => {
  const cv = document.querySelector('.bf-canvas') || document.querySelector('[class*=canvas]');
  const tiles = [...document.querySelectorAll('.bf-tile, .bf-cell, figure')];
  const onScreen = tiles.filter(t => {
    const b = t.getBoundingClientRect();
    return b.width > 0 && b.right > 0 && b.left < innerWidth &&
           b.bottom > 0 && b.top < innerHeight;
  });
  const first = tiles.length ? tiles[0].getBoundingClientRect() : null;
  return {
    url: location.pathname + location.search,
    tiles: tiles.length,
    onScreen: onScreen.length,
    transform: cv ? getComputedStyle(cv).transform.replace(/matrix\(|\)/g, '') : null,
    firstTile: first ? {x: Math.round(first.left), y: Math.round(first.top)} : null,
  };
};

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  const c = await b.newContext({viewport: {width: 1440, height: 860}});
  await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
  const p = await c.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e).slice(0, 120)));

  await p.goto(BASE + '/birds', {waitUntil: 'networkidle'});
  await p.waitForTimeout(2600);
  console.log('  direct /birds   ', JSON.stringify(await p.evaluate(probe)));

  await p.goto(BASE + '/', {waitUntil: 'networkidle'});
  await p.waitForTimeout(1200);
  const link = await p.$('a.more[href="/birds"]');
  if (!link) { console.log('  ! "See all photos" link not found'); await b.close(); return; }
  await link.click();
  await p.waitForLoadState('networkidle');
  for (const t of [600, 1500, 3000]) {
    await p.waitForTimeout(t === 600 ? 600 : 900);
    console.log('  after click +%-5s', t + 'ms', JSON.stringify(await p.evaluate(probe)));
  }
  // The preview photos link to /birds?start=<ids>, a different path from the
  // "See all photos" link — this is the one Scott pointed at.
  await p.goto(BASE + '/', {waitUntil: 'networkidle'});
  await p.waitForTimeout(1200);
  const tile = await p.$('a.feature-tile');
  if (!tile) { console.log('  ! no feature tile'); await b.close(); return; }
  console.log('  tile href       ', await tile.getAttribute('href'));
  await tile.click();
  await p.waitForLoadState('networkidle');
  for (let i = 0; i < 3; i++) {
    await p.waitForTimeout(1000);
    console.log('  after tile +%ds  %s', i + 1, JSON.stringify(await p.evaluate(probe)));
  }
  errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
