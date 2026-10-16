/* The detail view's filmstrip must stay clickable after a reshuffle.
 *
 * The click handler reads `data-i` off the thumbnail. Shuffling the frames
 * (and hiding one in curate) used to rebuild the strip with a bare <img>, so
 * `+undefined` became NaN, showFrame(NaN) did nothing, and every thumbnail
 * went dead until the modal was reopened. Reported as "clicking on the image
 * squares in gallery does nothing sometimes".
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const strip = () => {
  const imgs = [...document.querySelectorAll('#bf-ostrip img')];
  return {
    n: imgs.length,
    withIndex: imgs.filter(i => i.dataset.i !== undefined).length,
    shown: (document.getElementById('bf-ocount') || {}).textContent || '',
  };
};

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  // reducedMotion stops the field's ambient drift; without it the tile is
  // never 'stable' and Playwright refuses to click.
  const c = await b.newContext({viewport: {width: 1440, height: 900},
                                reducedMotion: 'reduce'});
  await c.addCookies([{name: 'curate', value: '0', url: BASE}]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 100)));

  // Deep link straight into the detail view: a synthetic click on a drifting
  // tile does not open it, and the hash route is supported anyway.
  await p.goto(BASE + '/birds#bird/barred-owl', {waitUntil: 'domcontentloaded'});
  await p.waitForTimeout(3500);

  const before = await p.evaluate(strip);
  console.log('  on open          %s', JSON.stringify(before));

  // click a thumbnail: the stage caption must change
  const capA = await p.evaluate(() => document.getElementById('bf-ocount').textContent);
  await p.evaluate(() => { const i = document.querySelectorAll('#bf-ostrip img')[3]; i && i.click(); });
  await p.waitForTimeout(700);
  const capB = await p.evaluate(() => document.getElementById('bf-ocount').textContent);
  console.log('  click thumb #3   %s  (changed: %s)', JSON.stringify(capB.slice(0, 28)), capA !== capB);

  // now reshuffle, then click again — this is where it used to die
  const sh = await p.$('#bf-oshuffle');
  if (sh) {
    await p.evaluate(() => document.getElementById('bf-oshuffle').click());
    await p.waitForTimeout(1500);
    const after = await p.evaluate(strip);
    const capC = await p.evaluate(() => document.getElementById('bf-ocount').textContent);
    await p.evaluate(() => { const i = document.querySelectorAll('#bf-ostrip img')[2]; i && i.click(); });
    await p.waitForTimeout(700);
    const capD = await p.evaluate(() => document.getElementById('bf-ocount').textContent);
    console.log('  after shuffle    %s', JSON.stringify(after));
    console.log('  click thumb #2   changed: %s  %s',
                capC !== capD, (after.withIndex === after.n && capC !== capD) ? 'OK' : 'DEAD');
  } else {
    console.log('  ! no shuffle control found');
  }
  errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
