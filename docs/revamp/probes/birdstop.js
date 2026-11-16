const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// /birds top on a phone: what the control panel over the field looks like.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const ctx = await b.newContext({ viewport: { width: +(process.env.W || 412), height: 915 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  if (process.env.CURATE) await ctx.addCookies([{ name: 'curate', value: '1', url: S }]);
  const p = await ctx.newPage();
  await p.goto(S + '/birds', { waitUntil: 'load' }); await p.waitForTimeout(2500);
  if (process.env.SCROLL) { await p.mouse.wheel(0, +process.env.SCROLL); await p.waitForTimeout(800); }
  if (process.env.RESIZE) { await p.setViewportSize({ width: +(process.env.W || 412), height: 860 }); await p.waitForTimeout(600); }
  console.log('stuck', await p.evaluate(() => document.querySelector('.gallery-header').classList.contains('is-stuck')));
  await p.screenshot({ path: process.env.OUT + '/birdstop.png' });
  console.log(JSON.stringify(await p.evaluate(() => {
    const n = document.querySelector('.gallery-header'); return [...n.querySelectorAll(':scope > *, :scope > * > *')].map(e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return [e.tagName, e.className.toString().slice(0,40), Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height), cs.backgroundColor, cs.position]; });
    let el = n, out = [];
    while (el && el !== document.body) { const cs = getComputedStyle(el), r = el.getBoundingClientRect();
      out.push([el.tagName, el.id, el.className.toString().slice(0, 50), Math.round(r.left), Math.round(r.width), cs.position, cs.backgroundColor, cs.zIndex]); el = el.parentElement; }
    return out; })));
  await b.close();
})();
