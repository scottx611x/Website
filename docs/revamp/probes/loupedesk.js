// Mouse loupe in the detail view: click raises it centred on the pointer,
// it follows the mouse, the wheel zooms, the original takes over, and
// Escape / a second click / leaving the photo drop it. Escape with no lens
// still closes the viewer.
//   docs/revamp/probes/run.sh loupedesk [slug]
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const slug = process.argv[2] || 'northern-flicker';
const OUT = process.env.OUT || '/tmp';

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://127.0.0.1:5055/birds#bird/' + slug, { waitUntil: 'networkidle' });
  await p.waitForFunction(() => {
    const i = document.getElementById('bf-oimg');
    return i && i.complete && i.naturalWidth > 500;
  }, null, { timeout: 20000 });
  await p.waitForTimeout(400);
  const box = await p.evaluate(() => {
    const r = document.getElementById('bf-oimg').getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  const st = () => p.evaluate(() => {
    const l = document.querySelector('.bf-loupe'), i = document.querySelector('.bf-loupe > i');
    const img = document.getElementById('bf-oimg');
    const r = l && l.getBoundingClientRect();
    return { on: !!(l && l.classList.contains('on')), cx: r && Math.round(r.left + r.width / 2),
             cy: r && Math.round(r.top + r.height / 2), d: r && Math.round(r.width),
             size: i && i.style.backgroundSize, hd: !!i && /originals\//.test(i.style.backgroundImage),
             cursor: getComputedStyle(img).cursor, open: document.getElementById('bf-over').classList.contains('open'),
             count: document.getElementById('bf-ocount').textContent.split('·')[0].trim() };
  });
  const hover = await st();
  await p.mouse.move(box.x, box.y);
  await p.mouse.down(); await p.mouse.up();
  await p.waitForTimeout(300);
  const raised = await st();
  await p.mouse.move(box.x - 120, box.y + 60, { steps: 6 });
  await p.waitForTimeout(200);
  const moved = await st();
  let hd = false;
  for (let k = 0; k < 40 && !hd; k++) { await p.waitForTimeout(250); hd = (await st()).hd; }
  const beforeWheel = (await st()).size;
  await p.mouse.wheel(0, -300); await p.waitForTimeout(700);
  const zoomed = (await st()).size;
  await p.screenshot({ path: OUT + '/loupedesk.png' });
  await p.keyboard.press('Escape'); await p.waitForTimeout(250);
  const afterEsc = await st();
  await p.mouse.down(); await p.mouse.up(); await p.waitForTimeout(250);
  const again = (await st()).on;
  await p.mouse.down(); await p.mouse.up(); await p.waitForTimeout(250);
  const secondClick = await st();
  await p.mouse.down(); await p.mouse.up(); await p.waitForTimeout(250);
  await p.mouse.move(5, 5, { steps: 4 }); await p.waitForTimeout(250);
  const left = await st();
  await p.keyboard.press('Escape'); await p.waitForTimeout(400);
  const closed = await st();
  console.log(JSON.stringify({
    zoomCursor: hover.cursor, raisedOnClick: raised.on, hiddenCursorWhileOn: raised.cursor,
    centredOnPointer: Math.abs(moved.cx - (box.x - 120)) <= 2 && Math.abs(moved.cy - (box.y + 60)) <= 2,
    diameter: raised.d, swappedToOriginal: hd, wheelZoomed: beforeWheel !== zoomed, sizes: [beforeWheel, zoomed],
    escapeDropsLens: !afterEsc.on && afterEsc.open, clickRaisesAgain: again,
    secondClickDrops: !secondClick.on, leavingDrops: !left.on,
    frameUnchanged: [hover.count, secondClick.count], escapeStillClosesViewer: !closed.open,
    errors: errs, screenshot: OUT + '/loupedesk.png',
  }, null, 1));
  await b.close();
})();
