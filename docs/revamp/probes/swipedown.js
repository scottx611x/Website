const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
// Detail view on a phone: a hard swipe down must not close it; a sideways one still pages.
const S = process.env.PROBE_SERVER || SRV;
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const ctx = await b.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  await p.goto(S + '/birds#bird/blue-jay', { waitUntil: 'load' }); await p.waitForTimeout(3500);
  const st = () => p.evaluate(() => { const o = document.getElementById('bf-over'); return { open: !!o && !o.hidden && getComputedStyle(o).display !== 'none' && o.classList.length ? o.className : 'closed', hash: location.hash, count: (document.querySelector('.bf-count') || {}).textContent }; });
  console.log('before', JSON.stringify(await st()));
  const swipe = (x0, y0, x1, y1) => p.evaluate(([x0, y0, x1, y1]) => {
    const t = document.querySelector('.bf-oimg') || document.getElementById('bf-over');
    const mk = (x, y) => new Touch({ identifier: 1, target: t, clientX: x, clientY: y });
    t.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, touches: [mk(x0, y0)], changedTouches: [mk(x0, y0)] }));
    t.dispatchEvent(new TouchEvent('touchend', { bubbles: true, touches: [], changedTouches: [mk(x1, y1)] }));
  }, [x0, y0, x1, y1]);
  await swipe(200, 200, 205, 600); await p.waitForTimeout(800);
  console.log('after down', JSON.stringify(await st()));
  await swipe(300, 300, 100, 310); await p.waitForTimeout(800);
  console.log('after left', JSON.stringify(await st()));
  await b.close();
})();
