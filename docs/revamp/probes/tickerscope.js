// Home ticker: sticks to the top while you scroll through Birds, then scrolls
// away with that section so it is gone by Photography and Projects.
//   docs/revamp/probes/run.sh tickerscope [outdir]
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.argv[2] || '/tmp';

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const vp of [{ width: 412, height: 915, isMobile: true }, { width: 1440, height: 900 }]) {
    const p = await (await b.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile })).newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    await p.goto(BASE + '/', { waitUntil: 'networkidle' });
    const names = await p.$$eval('.ticker-bird:not([aria-hidden])', a => a.map(x => x.textContent));
    const at = async (sel, off) => {
      await p.evaluate(([s, o]) => { const el = document.querySelectorAll('.strip')[s];
        const r = el.getBoundingClientRect(); window.scrollTo({ top: (o < 0 ? r.bottom : r.top) + scrollY + o, behavior: 'instant' }); }, [sel, off]);
      await p.waitForTimeout(400);
      return p.evaluate(() => { const r = document.querySelector('.ticker').getBoundingClientRect(); return Math.round(r.top) + '..' + Math.round(r.bottom); });
    };
    const res = { vp: vp.width, weir: names.filter(n => /weir/i.test(n)), n: names.length,
      inBirds: await at(0, -400), atPhoto: await at(1, 0), atProjects: await at(2, 0), errs };
    console.log(JSON.stringify(res));
    await p.evaluate(() => window.scrollTo({ top: document.querySelectorAll('.strip')[1].getBoundingClientRect().top + scrollY - 300, behavior: 'instant' }));
    await p.screenshot({ path: `${OUT}/ticker-${vp.width}.png` });
  }
  await b.close();
})();
