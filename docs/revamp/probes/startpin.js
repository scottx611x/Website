/* A7, narrowed: are the ?start= photos actually ON SCREEN when you arrive?
 *
 * The home previews link to /birds?start=<post.idx,...>, which pins those
 * frames to the head of the sequence. The complaint is that they "fly to the
 * top left out of view" — so measure where those specific tiles land, not
 * just how many tiles are visible overall.
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  const c = await b.newContext({viewport: {width: 1440, height: 860}});
  await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
  const p = await c.newPage();

  await p.goto(BASE + '/', {waitUntil: 'networkidle'});
  await p.waitForTimeout(1000);
  const tile = await p.$('a.feature-tile');
  const href = await tile.getAttribute('href');
  const wanted = await tile.$eval('img', i => i.currentSrc || i.src);
  const cap = await tile.$eval('.tile-cap', e => e.textContent.trim()).catch(() => '');
  console.log('  clicked  : %s', cap);
  console.log('  href     : %s', href);

  await tile.click();
  await p.waitForLoadState('networkidle');
  await p.waitForTimeout(2500);

  const r = await p.evaluate((wantedSrc) => {
    const key = s => (s || '').split('/').pop().split('?')[0];
    const want = key(wantedSrc);
    const tiles = [...document.querySelectorAll('.bf-tile, .bf-cell, figure')];
    const vis = b => b.right > 0 && b.left < innerWidth && b.bottom > 0 && b.top < innerHeight;
    const hits = [];
    tiles.forEach((t, i) => {
      const img = t.querySelector('img');
      if (!img) return;
      if (key(img.currentSrc || img.src) !== want) return;
      const b = t.getBoundingClientRect();
      hits.push({i, x: Math.round(b.left), y: Math.round(b.top), onScreen: vis(b)});
    });
    const all = tiles.map(t => t.getBoundingClientRect());
    return {
      total: tiles.length,
      onScreen: all.filter(vis).length,
      matches: hits,
      firstFive: all.slice(0, 5).map(b => ({x: Math.round(b.left), y: Math.round(b.top), on: vis(b)})),
      viewport: {w: innerWidth, h: innerHeight},
    };
  }, wanted);
  console.log('  %s', JSON.stringify(r, null, 1).replace(/\n/g, '\n  '));
  await b.close();
})();
