// Stats tally count-up must not reflow the page: the sentence's height and
// the top of what follows stay put while the numbers count.
//   docs/revamp/probes/run.sh tallysteady
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const out = {};
  for (const [w, h, mob] of [[1440, 900, false], [412, 860, true], [360, 760, true]]) {
    const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: mob, hasTouch: mob });
    const p = await c.newPage();
    await p.addInitScript(() => {
      window.__tl = [];
      const rec = () => {
        const t = document.querySelector('.stat-tally');
        if (t) {
          const r = t.getBoundingClientRect();
          const xs = [...t.querySelectorAll('b')].map(e => Math.round(e.getBoundingClientRect().left));
          window.__tl.push(Math.round(r.height) + '|' + xs.join(','));
        }
        if (window.__tl.length < 120) requestAnimationFrame(rec);
      };
      requestAnimationFrame(rec);
    });
    await p.goto(BASE + '/birds/stats', { waitUntil: 'load' });
    await p.waitForTimeout(2500);
    const tl = await p.evaluate(() => window.__tl);
    out[w] = { frames: tl.length, distinct: [...new Set(tl)].length, sample: [...new Set(tl)].slice(0, 6) };
    await c.close();
  }
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
