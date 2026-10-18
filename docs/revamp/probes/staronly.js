/* The detail viewer's "starred only" toggle.
 *
 * Four promises:
 *   1. opening a bird from /birds?star=1 arrives already narrowed
 *   2. the toggle widens to every frame of that species, and back
 *   3. the rebuilt filmstrip is still CLICKABLE — every item keeps data-i
 *      (omitting it was the original dead-strip bug)
 *   4. a bird with NO starred frame shows whole rather than an empty modal
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const SLUG = process.env.SLUG || 'barred-owl';

const strip = () => {
  const items = Array.from(document.querySelectorAll('#bf-ostrip img'));
  const btn = document.getElementById('bf-ostaronly');
  return {
    n: items.length,
    // data-i may sit on the img or its wrapper -- either is clickable
    missingDataI: items.filter(e =>
      e.getAttribute('data-i') === null &&
      !(e.parentElement && e.parentElement.getAttribute('data-i') !== null)).length,
    pressed: btn ? btn.getAttribute('aria-pressed') : null,
    // The strip is lazy (first 24), so its DOM count cannot tell a narrowed
    // scope from a wide one. The "n / total" counter reports the real scope.
    scope: ((document.getElementById('bf-ocount') || {}).textContent || '').trim(),
    hidden: btn ? (btn.hidden || btn.disabled) : true,
  };
};

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  const c = await b.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
  const p = await c.newPage();
  p.on('pageerror', e => console.log('  JS ERROR: ' + e.message));

  // Deep link: a synthetic click on a drifting tile does not open the overlay.
  // ?star=1 is what seeds CTX.star, so the view opens already narrowed.
  await p.goto(BASE + '/birds?star=1#bird/' + SLUG, {waitUntil: 'domcontentloaded'});
  // Wait for the strip to actually populate -- the species JSON is an S3 round
  // trip, and a fixed 3.5s sampled an empty overlay and read it as "0 frames".
  await p.waitForFunction(
    () => document.querySelectorAll('#bf-ostrip img').length > 0,
    null, {timeout: 25000}).catch(() => console.log('  !! strip never populated'));
  await p.waitForTimeout(600);
  const a = await p.evaluate(strip);
  console.log('  1. arrives narrowed   %s', JSON.stringify(a));
  if (a.hidden) {
    // A species with no starred frame: the whole set shows and the control is
    // gone. Nothing left to round-trip, so the remaining checks do not apply.
    console.log('  no starred frames for %s -- toggle hidden, full set shown  %s',
                SLUG, a.n > 0 ? 'OK' : 'FAIL (empty modal)');
    await b.close(); return;
  }

  await p.evaluate(() => document.getElementById('bf-ostaronly').click());
  await p.waitForTimeout(1200);
  const wide = await p.evaluate(strip);
  console.log('  2. widened            %s  %s', JSON.stringify(wide),
              wide.pressed === 'false' ? 'OK' : 'FAIL (toggle did not release)');
  console.log('  3. strip clickable    %s',
              wide.missingDataI === 0 ? 'OK (all items keep data-i)'
                                      : 'FAIL (' + wide.missingDataI + ' dead items)');

  await p.evaluate(() => document.getElementById('bf-ostaronly').click());
  await p.waitForTimeout(1200);
  const back = await p.evaluate(strip);
  console.log('  4. back to starred    %s  %s', JSON.stringify(back),
              (back.pressed === 'true' && back.scope === a.scope) ? 'OK (round-trips)' : 'FAIL');

  // clicking a rebuilt item must actually change the stage
  const moved = await p.evaluate(async () => {
    const cap = () => (document.getElementById('bf-ocount') || {}).textContent || '';
    const before = cap();
    const items = document.querySelectorAll('#bf-ostrip img');
    if (items.length < 2) return 'skipped (only ' + items.length + ' frame)';
    items[items.length - 1].click();
    await new Promise(r => setTimeout(r, 900));
    return before !== cap() ? 'OK (stage followed the click)'
                            : 'FAIL (stage did not move: ' + JSON.stringify(before) + ')';
  });
  console.log('  5. click moves stage  %s', moved);
  await b.close();
})();
