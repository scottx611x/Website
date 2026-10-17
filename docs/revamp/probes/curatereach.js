/* Curate actions must be reachable from the stage, not three sections down.
 *
 * The full "Curate this frame" panel sits after By-the-numbers, the year chart
 * and the map, so on a phone the frame being curated has scrolled off before
 * you reach it. Two stage-side buttons mirror the panel's actions.
 *
 * Checks they exist in curate mode, sit above the fold on a phone, and are
 * absent for a normal visitor.
 */
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const look = () => {
  const q = id => document.getElementById(id);
  const panel = q('bf-chide');
  const stage = q('bf-ohide2');
  const box = e => e ? e.getBoundingClientRect() : null;
  const sb = box(stage), pb = box(panel);
  return {
    stageButtons: !!(q('bf-oaway2') && q('bf-ohide2')),
    panelButtons: !!(q('bf-caway') && q('bf-chide')),
    stageTop: sb ? Math.round(sb.top) : null,
    panelTop: pb ? Math.round(pb.top) : null,
    viewportH: innerHeight,
    stageAboveFold: sb ? sb.top < innerHeight : null,
    panelAboveFold: pb ? pb.top < innerHeight : null,
  };
};

(async () => {
  const b = await chromium.launch({executablePath: EXE});
  for (const [label, curate] of [['curate', '1'], ['visitor', '0']]) {
    const c = await b.newContext({viewport: {width: 390, height: 780},
                                  isMobile: true, hasTouch: true,
                                  reducedMotion: 'reduce'});
    await c.addCookies([{name: 'curate', value: curate, url: BASE}]);
    const p = await c.newPage();
    await p.goto(BASE + '/birds#bird/peregrine-falcon', {waitUntil: 'domcontentloaded'});
    await p.waitForTimeout(3200);
    const r = await p.evaluate(look);
    const ok = curate === '1'
      ? (r.stageButtons && r.stageAboveFold)
      : (!r.stageButtons && !r.panelButtons);
    console.log('  %-8s %s %s', label, JSON.stringify(r), ok ? 'OK' : 'FAIL');
    await c.close();
  }
  await b.close();
})();
