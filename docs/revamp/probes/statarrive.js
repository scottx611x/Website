// Stats first sight: charts below the fold start undrawn, draw themselves
// once when scrolled to, end fully drawn; reduced motion draws them at once.
//   docs/revamp/probes/run.sh statarrive [outdir]
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.argv[2] || '/tmp';
const state = p => p.evaluate(() => {
  const tf = s => { const e = document.querySelector(s); return e ? getComputedStyle(e).transform : null; };
  const cp = s => { const e = document.querySelector(s); return e ? getComputedStyle(e).clipPath : null; };
  return {
    arriveClass: document.documentElement.classList.contains('stats-arrive'),
    arrived: [...document.querySelectorAll('.stat-block.arrived')].map(b => b.id),
    boardBar: tf('#board-rows .bar-row:nth-child(1) .bar-fill'),
    calDot: tf('#cal-chart circle.cal-day'),
    ridge: tf('.rhythm-row:not(.axis) .rhythm-spark'),
    river: cp('#river-chart svg'),
  };
});
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const out = {};
  for (const reduced of [false, true]) {
    const c = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: reduced ? 'reduce' : 'no-preference' });
    const p = await c.newPage(); const errs = [];
    p.on('pageerror', e => errs.push(e.message));
    await p.goto(BASE + '/birds/stats', { waitUntil: 'networkidle' });
    await p.waitForTimeout(1000);
    const atTop = await state(p);
    for (const id of ['days', 'board', 'rhythm-block', 's-river']) {
      await p.evaluate(i => document.getElementById(i).scrollIntoView({ block: 'center' }), id);
      if (!reduced && id === 'days') { await p.waitForTimeout(260); await p.screenshot({ path: OUT + '/arrive-days.png' }); }
      await p.waitForTimeout(1400);
    }
    out[reduced ? 'reduced' : 'motion'] = { atTop, afterScroll: await state(p), errs };
    await c.close();
  }
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
