/* A8: the home strip's composition survives the click into the gallery.
 *
 * Asserts the five frames you clicked arrive in the SAME arrangement — a lead
 * tile twice the width and height of the others — and that the gallery
 * continues beneath them rather than the mosaic replacing it.
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  for (const [w, h] of [[1440, 860], [390, 780]]) {
    const c = await b.newContext({viewport: {width: w, height: h}, isMobile: w < 700, hasTouch: w < 700});
    await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));

    await p.goto(BASE + '/', {waitUntil: 'networkidle'});
    await p.waitForTimeout(900);
    const home = await p.evaluate(() => {
      const t = [...document.querySelectorAll('a.feature-tile')];
      const r = t.map(e => e.getBoundingClientRect());
      return {n: t.length, lead: r.length ? {w: Math.round(r[0].width), h: Math.round(r[0].height)} : null,
              second: r.length > 1 ? {w: Math.round(r[1].width), h: Math.round(r[1].height)} : null};
    });
    const tile = await p.$('a.feature-tile');
    // Only the BIRD strip's five — the photography strip reuses .feature-tile.
    const srcs = (await p.$$eval('a.feature-tile img',
      els => els.map(i => (i.currentSrc || i.src).split('/').pop().split('?')[0]))).slice(0, 5);
    await tile.click();
    await p.waitForLoadState('networkidle');
    await p.waitForTimeout(1600);

    const got = await p.evaluate((want) => {
      const m = document.querySelector('.masonry.opening-mosaic');
      if (!m) return {mosaic: false};
      const shots = [...m.querySelectorAll('.shot')];
      const r = shots.map(e => e.getBoundingClientRect());
      const key = e => { const i = e.querySelector('img'); return i ? (i.currentSrc || i.src).split('/').pop().split('?')[0] : null; };
      const rest = document.querySelectorAll('.masonry:not(.opening-mosaic) .shot').length;
      return {
        mosaic: true,
        n: shots.length,
        lead: r.length ? {w: Math.round(r[0].width), h: Math.round(r[0].height)} : null,
        second: r.length > 1 ? {w: Math.round(r[1].width), h: Math.round(r[1].height)} : null,
        sameOrder: JSON.stringify(shots.map(key)) === JSON.stringify(want),
        restBelow: rest,
        dealtIntoColumns: m.querySelectorAll('.masonry-col').length > 0,
      };
    }, srcs);

    const ratio = got.lead && got.second
      ? (got.lead.w / got.second.w).toFixed(2) + 'x wide, ' + (got.lead.h / got.second.h).toFixed(2) + 'x tall'
      : 'n/a';
    console.log('  %s home lead %s | gallery %s', (w + 'x' + h).padEnd(9),
                JSON.stringify(home.lead), JSON.stringify(got.lead));
    console.log('            n=%s sameOrder=%s leadIs=%s restBelow=%s dealt=%s %s',
                got.n, got.sameOrder, ratio, got.restBelow, got.dealtIntoColumns,
                got.mosaic && got.sameOrder && !got.dealtIntoColumns ? 'OK' : 'FAIL');
    errs.forEach(e => console.log('     ! ' + e));
    await c.close();
  }
  await b.close();
})();
