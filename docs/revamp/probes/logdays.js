// Recordings by day: the strip of recent days, ?day= deep links, and the
// arrows stepping past the days the page carries.
//   docs/revamp/probes/run.sh logdays [outdir]
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
  const state = () => p.evaluate(() => ({
    url: location.pathname + location.search,
    title: document.getElementById('dl-daytitle').textContent,
    chips: [...document.querySelectorAll('#dl-days button')].map(x => (x.classList.contains('on') ? '*' : '') + x.firstChild.textContent),
    prevDisabled: document.getElementById('dl-prev').disabled,
    nextDisabled: document.getElementById('dl-next').disabled,
  }));
  const r = {};
  await p.goto(BASE + '/birds/live/log', { waitUntil: 'networkidle' });
  r.landing = await state();
  await p.screenshot({ path: OUT + '/logdays-landing.png' });
  await p.click('#dl-days button:nth-child(3)');
  r.clickedThirdChip = await state();
  await p.click('#dl-next');
  r.afterNext = await state();
  const all = await p.evaluate(() => ALL_DAYS);
  const deep = all[Math.min(20, all.length - 1)];
  await p.goto(BASE + '/birds/live/log?day=' + deep, { waitUntil: 'networkidle' });
  r.deepLink = await state();
  // walk older until the page has to load a new window
  for (let i = 0; i < 12; i++) {
    const before = await p.evaluate(() => location.href);
    await Promise.all([p.waitForLoadState('networkidle'), p.click('#dl-prev')]);
    await p.waitForTimeout(150);
    if ((await p.evaluate(() => location.href)) === before) break;
  }
  r.afterWalkingOlder = await state();
  r.errs = errs;
  console.log(JSON.stringify(r, null, 1));
  await b.close();
})();
