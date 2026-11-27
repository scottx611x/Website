// Gallery field: a thumb whose first request fails is retried, not left blank.
// Aborts the first request for every thumb, then checks the tiles on screen.
//   docs/revamp/probes/run.sh thumbretry [outdir]
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.argv[2] || '/tmp';

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const p = await (await b.newContext({ viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const tried = {}; let aborted = 0;
  await p.route(/\/thumbs\//, route => {
    const key = route.request().url().replace(/[?&]r=\d+$/, '');
    if (!tried[key]) { tried[key] = 1; aborted++; return route.abort('connectionreset'); }
    return route.continue();
  });
  await p.goto(BASE + '/birds', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(5000);
  const r = await p.evaluate(() => {
    const vh = innerHeight, vw = innerWidth;
    const on = [...document.querySelectorAll('.bf-tile')].filter(t => {
      const b = t.getBoundingClientRect(); return b.bottom > 0 && b.top < vh && b.right > 0 && b.left < vw;
    });
    const imgs = on.map(t => t.querySelector('img')).filter(Boolean);
    return {
      onScreen: imgs.length,
      painted: imgs.filter(i => i.complete && i.naturalWidth > 0).length,
      blank: imgs.filter(i => !(i.complete && i.naturalWidth > 0)).map(i => i.getAttribute('src')).slice(0, 5),
    };
  });
  r.firstRequestsAborted = aborted;
  r.ok = r.onScreen > 0 && r.painted === r.onScreen && aborted > 0;
  r.errs = errs;
  await p.screenshot({ path: OUT + '/thumbretry.png' });
  console.log(JSON.stringify(r, null, 1));
  await b.close();
  process.exit(r.ok ? 0 : 1);
})();
