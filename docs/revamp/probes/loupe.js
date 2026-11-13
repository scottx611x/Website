// Touch loupe in the detail view: hold to raise it, drag to move it, and a
// held drag must not page frames; a quick swipe still must.
//   docs/revamp/probes/run.sh loupe [slug]
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const slug = process.argv[2] || 'northern-flicker';
const OUT = process.env.OUT || '/tmp';

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 412, height: 860 }, isMobile: true,
                                 hasTouch: true, deviceScaleFactor: 2 });
  const p = await c.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://127.0.0.1:5055/birds#bird/' + slug, { waitUntil: 'networkidle' });
  await p.waitForFunction(() => {
    const i = document.getElementById('bf-oimg');
    return i && i.complete && i.naturalWidth > 500;
  }, null, { timeout: 20000 });
  await p.waitForTimeout(400);
  const cdp = await c.newCDPSession(p);
  const box = await p.evaluate(() => {
    const r = document.getElementById('bf-oimg').getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  const state = () => p.evaluate(() => ({
    loupe: !!document.querySelector('.bf-loupe.on'),
    count: document.getElementById('bf-ocount').textContent.split('·')[0].trim(),
    scrollY: document.getElementById('bf-over').scrollTop,
  }));
  const touch = (type, x, y) => cdp.send('Input.dispatchTouchEvent',
    { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] });

  const before = await state();
  // Hold, then drag 140px sideways and up: a loupe, not a swipe.
  await touch('touchStart', box.x, box.y);
  await p.waitForTimeout(450);
  const menuBlocked = await p.evaluate(() => {
    const e = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });
    document.getElementById('bf-oimg').dispatchEvent(e);
    return e.defaultPrevented;
  });
  for (let k = 1; k <= 10; k++) {
    await touch('touchMove', box.x - 14 * k, box.y - 6 * k);
    await p.waitForTimeout(25);
  }
  const held = await state();
  // Keep holding: the full-size original should arrive and take over.
  let hdSwap = false;
  for (let k = 0; k < 40 && !hdSwap; k++) {
    await p.waitForTimeout(250);
    hdSwap = await p.evaluate(() => {
      const d = document.querySelector('.bf-loupe > i');
      return !!d && /originals\//.test(d.style.backgroundImage);
    });
  }
  await touch('touchMove', box.x - 150, box.y - 70);
  await p.waitForTimeout(600);
  const loupeSize = await p.evaluate(() => document.querySelector('.bf-loupe').getBoundingClientRect().width);
  await p.screenshot({ path: OUT + '/loupe.png' });
  await touch('touchEnd');
  await p.waitForTimeout(300);
  const after = await state();

  // A quick swipe (no hold) still pages.
  await touch('touchStart', box.x + 80, box.y);
  for (let k = 1; k <= 6; k++) { await touch('touchMove', box.x + 80 - 30 * k, box.y); await p.waitForTimeout(16); }
  await touch('touchEnd');
  await p.waitForTimeout(300);
  const swiped = await state();

  console.log(JSON.stringify({
    loupeWhileHeld: held.loupe,
    loupeDiameter: loupeSize,
    swappedToOriginal: hdSwap,
    androidMenuBlocked: menuBlocked,
    heldDragPagedFrame: held.count !== before.count || after.count !== before.count,
    overlayScrolledDuringHold: held.scrollY !== before.scrollY,
    loupeGoneAfterLift: !after.loupe,
    quickSwipeStillPages: swiped.count !== after.count,
    frames: [before.count, after.count, swiped.count],
    errors: errs,
    screenshot: OUT + '/loupe.png',
  }, null, 1));
  await b.close();
})();
