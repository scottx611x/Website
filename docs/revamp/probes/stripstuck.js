// The detail view's strip must fill however a bird is opened, including after
// a gallery tile (sequence mode) was opened and closed first. It used to stay
// on its nine placeholder boxes: seqMode was never reset.
//   docs/revamp/probes/run.sh stripstuck
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const strip = p => p.evaluate(() => ({
  imgs: document.querySelectorAll('#bf-ostrip img').length,
  skeletons: document.querySelectorAll('#bf-ostrip .bf-sk').length,
  title: document.getElementById('bf-otitle').textContent,
  ctx: document.getElementById('bf-octx').hidden ? null : document.getElementById('bf-octxlab').textContent,
}));
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const out = {};
  await p.goto(BASE + '/birds#bird/eastern-towhee', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2000);
  out.direct = await strip(p);
  await p.click('#bf-octxnext'); await p.waitForTimeout(2000);
  out.stepNext = await strip(p);
  await p.keyboard.press('Escape'); await p.waitForTimeout(800);
  // open a grid tile: sequence mode
  await p.goto(BASE + '/birds?view=grid', { waitUntil: 'networkidle' }); await p.waitForTimeout(1500);
  await p.evaluate(() => document.querySelector('.masonry [data-images]').click());
  await p.waitForTimeout(2000);
  out.tile = await strip(p);
  await p.keyboard.press('Escape'); await p.waitForTimeout(800);
  await p.evaluate(() => { location.hash = '#bird/eastern-towhee'; });
  await p.waitForTimeout(2500);
  out.afterTile_hash = await strip(p);
  if (out.afterTile_hash.ctx) { await p.click('#bf-octxnext'); await p.waitForTimeout(2000); out.afterTile_step = await strip(p); }
  out.errors = errs;
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
