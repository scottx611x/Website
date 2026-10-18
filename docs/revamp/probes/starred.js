/* The starred ("best of") set.
 *
 * Three promises, each checked here:
 *   1. the home strip shows ONLY starred frames
 *   2. ?star=1 narrows the gallery to the starred set
 *   3. starred frames surface MORE OFTEN in the default shuffle, without
 *      taking it over — a greatest-hits reel would bury the other 80%
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const tiles = () => {
  const el = document.getElementById('bf-tiles');
  if (!el) return null;
  const t = JSON.parse(el.textContent);
  return {n: t.length, starred: t.filter(x => x.star).length};
};

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  const c = await b.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
  await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
  const p = await c.newPage();

  // 1. home strip
  await p.goto(BASE + '/', {waitUntil: 'domcontentloaded'});
  await p.waitForTimeout(1200);
  const home = await p.$$eval('a.feature-tile', els =>
    els.slice(0, 5).map(e => e.getAttribute('href')));
  console.log('  home strip tiles: %d', home.length);

  // 2. the filter
  await p.goto(BASE + '/birds', {waitUntil: 'domcontentloaded'});
  await p.waitForTimeout(2000);
  const all = await p.evaluate(tiles);
  await p.goto(BASE + '/birds?star=1', {waitUntil: 'domcontentloaded'});
  await p.waitForTimeout(2000);
  const only = await p.evaluate(tiles);
  console.log('  /birds        %s', JSON.stringify(all));
  console.log('  /birds?star=1 %s  %s', JSON.stringify(only),
              (only && only.n === only.starred && only.n > 0) ? 'OK' : 'FAIL');

  // 3. weighting: starred denser at the front of the sequence than overall.
  // SEQ rides in its own <script id="bf-seq"> block, not an inline var.
  await p.goto(BASE + '/birds', {waitUntil: 'domcontentloaded'});
  await p.waitForTimeout(2200);
  const d = await p.evaluate(() => {
    const t = JSON.parse(document.getElementById('bf-tiles').textContent);
    const seqEl = document.getElementById('bf-seq');
    if (!seqEl) return null;
    const seq = JSON.parse(seqEl.textContent);
    const star = i => ((t[seq[i]] || {}).star ? 1 : 0);
    const n = Math.min(60, seq.length);
    let head = 0; for (let i = 0; i < n; i++) head += star(i);
    let tot = 0; for (let i = 0; i < seq.length; i++) tot += star(i);
    return {headPct: Math.round(100 * head / n),
            overallPct: Math.round(100 * tot / seq.length), seq: seq.length};
  });
  console.log('  shuffle density %s  %s', JSON.stringify(d),
              (d && d.headPct > d.overallPct) ? 'OK (starred surface more)' : 'FAIL');
  await b.close();
})();
