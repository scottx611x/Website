/* A1 + A7.
 *
 * A1: an ORDER (posted / recent / oldest) makes the field a bounded block,
 *     anchored top-left, travelling down and right only — never up or left
 *     past the first frame, and never wrapping.
 * A7: arriving from the home page, the frame you clicked is fully visible
 *     and clear of the floating header — not clipped into the corner.
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const state = () => {
  const hdr = document.querySelector('.gallery-header');
  const hb = hdr ? hdr.getBoundingClientRect().bottom : 0;
  const tiles = [...document.querySelectorAll('.bf-tile')];
  const rects = tiles.map(t => t.getBoundingClientRect());
  const on = rects.filter(b => b.right > 0 && b.left < innerWidth &&
                               b.bottom > 0 && b.top < innerHeight);
  return {
    onScreen: on.length,
    headerBottom: Math.round(hb),
    minTop: rects.length ? Math.round(Math.min(...rects.map(b => b.top))) : null,
    minLeft: rects.length ? Math.round(Math.min(...rects.map(b => b.left))) : null,
    underHeader: on.filter(b => b.top < hb - 1).length,
  };
};

const pan = ({dx, dy}) => {
  const cv = document.querySelector('.bf-canvas') || document.querySelector('.bf-wrap') || document.body;
  const r = cv.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  cv.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, clientX: x, clientY: y, pointerId: 1}));
  for (let s = 1; s <= 8; s++) {
    cv.dispatchEvent(new PointerEvent('pointermove', {bubbles: true, pointerId: 1,
      clientX: x + dx * s / 8, clientY: y + dy * s / 8}));
  }
  cv.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, pointerId: 1, clientX: x + dx, clientY: y + dy}));
};

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  const c = await b.newContext({viewport: {width: 1440, height: 860}});
  await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));

  for (const sort of ['posted', 'recent', 'oldest']) {
    await p.goto(`${BASE}/birds?sort=${sort}`, {waitUntil: 'networkidle'});
    await p.waitForTimeout(2200);
    const at0 = await p.evaluate(state);
    // try to drag DOWN-RIGHT, i.e. reveal content up-left of the anchor: must not move
    await p.evaluate(pan, {dx: 600, dy: 600}); await p.waitForTimeout(700);
    const back = await p.evaluate(state);
    // now drag UP-LEFT: should travel into older frames
    await p.evaluate(pan, {dx: -600, dy: -600}); await p.waitForTimeout(700);
    const fwd = await p.evaluate(state);
    console.log('  sort=%-7s start=%s', sort, JSON.stringify(at0));
    console.log('            pastStart=%s  (minTop/minLeft must not grow)', JSON.stringify({minTop: back.minTop, minLeft: back.minLeft}));
    console.log('            travelled=%s', JSON.stringify({minTop: fwd.minTop, minLeft: fwd.minLeft, onScreen: fwd.onScreen}));
  }

  // A7: arrive from home
  await p.goto(BASE + '/', {waitUntil: 'networkidle'});
  await p.waitForTimeout(1000);
  const tile = await p.$('a.feature-tile');
  const wanted = await tile.$eval('img', i => (i.currentSrc || i.src).split('/').pop().split('?')[0]);
  await tile.click();
  await p.waitForLoadState('networkidle');
  await p.waitForTimeout(2600);
  const r = await p.evaluate((want) => {
    const hdr = document.querySelector('.gallery-header');
    const hb = hdr ? hdr.getBoundingClientRect().bottom : 0;
    const hit = [...document.querySelectorAll('.bf-tile')].find(t => {
      const i = t.querySelector('img');
      return i && (i.currentSrc || i.src).split('/').pop().split('?')[0] === want;
    });
    if (!hit) return {found: false};
    const b = hit.getBoundingClientRect();
    return {found: true, x: Math.round(b.left), y: Math.round(b.top),
            clearOfHeader: b.top >= hb - 1, fullyVisible: b.left >= 0 && b.top >= 0};
  }, wanted);
  console.log('  home→gallery clicked tile: %s', JSON.stringify(r));
  errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
