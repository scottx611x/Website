const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
// Live stage: is the hero photo cropped around the bird? Prints the aim and
// whether the focus point lands inside the stage, for each reel bird tapped.
const S = process.env.PROBE_SERVER || SRV;
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const W = +(process.env.W || 412), H = +(process.env.H || 915);
  const ctx = await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 2, isMobile: W < 900, hasTouch: W < 900 });
  const p = await ctx.newPage();
  await p.goto(S + '/birds/live', { waitUntil: 'load' }); await p.waitForTimeout(3000);
  console.log('focus entries', await p.evaluate(() => Object.keys((window.LIVE_DEBUG || {}).focus || {}).length || document.getElementById('lv-data').textContent.match(/"focus":\{[^}]*/)?.[0].split('],').length));
  const n = Math.min(+(process.env.N || 6), await p.locator('.lv-reel .lv-chip').count());
  for (let i = 0; i < n; i++) {
    if (i) { await p.locator('.lv-reel .lv-chip').nth(i).click({ force: true }).catch(() => {}); await p.waitForTimeout(1600); }
    const r = await p.evaluate(() => {
      const els = document.querySelectorAll('#lv-hero .lv-ph'); const el = els[els.length - 1]; if (!el) return null;
      const nm = document.querySelector('#lv-hero .lv-nm:last-of-type')?.textContent.trim();
      if (!el.dataset.fx) return { nm, aimed: false };
      const fx = +el.dataset.fx, fy = +el.dataset.fy, ar = +el.dataset.ar, cw = el.offsetWidth, ch = el.offsetHeight;
      const ih = Math.max(ch, cw / ar), iw = ih * ar;
      const [ox, oy] = el.style.backgroundPosition.split(' ').map(parseFloat);
      const bx = fx * iw + ox, by = fy * ih + oy, cx = (iw - cw) / 2;
      return { nm, aimed: true, pos: el.style.backgroundPosition, birdAt: [Math.round(bx / cw * 100), Math.round(by / ch * 100)],
               middleCropBirdAt: Math.round((fx * iw - cx) / cw * 100) };
    });
    console.log(JSON.stringify(r));
    if (process.env.OUT && i < 3) await p.screenshot({ path: process.env.OUT + '/livefocus' + i + '.png' });
  }
  await b.close();
})();
