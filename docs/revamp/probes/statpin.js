// Stats pin: clicking a bird pins it and every section answers for it.
//   docs/revamp/probes/run.sh statpin
// Checks, for a bird pinned from "Most photographed" and one from "Heard":
// all eight sections mark the same bird, scrollY does not move, Escape
// clears every mark, #bird=<slug> pins on load, and a phone tap pins too.
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';

const marks = (p) => p.evaluate(() => {
  const t = s => (document.querySelector(s) || {}).textContent;
  const rv = document.getElementById('river-readout');
  return {
    chip: document.getElementById('pin-chip').hidden ? null : t('#pin-chip .pin-name'),
    life: t('#ll-name'),
    year: (t('.pheno-row.pin .pheno-name') || null),
    days: document.querySelectorAll('#cal-chart circle.cal-match').length,
    daysDimmed: [...document.querySelectorAll('#cal-chart circle.cal-day')].some(c => c.style.opacity === '0.35'),
    board: (document.querySelector('#board-rows .stat-focus') || {}).dataset?.slug || null,
    heard: (document.querySelector('#ear-bars .stat-focus') || {}).dataset?.slug || (t('#ear-bars .pin-note') ? 'note' : null),
    rhythm: (document.querySelector('.rhythm-row.pin') || {}).dataset?.slug ||
            (document.querySelector('.rhythm-chart.pin-miss') ? 'miss' : null),
    places: t('#places-block .places-top-h'),
    river: rv && !rv.hidden ? (rv.querySelector('b') || {}).textContent : null,
    hash: location.hash,
    scrollY: Math.round(scrollY),
  };
});

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const out = {};
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto(BASE + '/birds/stats', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);

  // Pin from Most photographed: click the BAR (the name is a link).
  const row = '#board-rows .bar-row:nth-child(2)';
  await p.locator(row).scrollIntoViewIfNeeded();
  await p.waitForTimeout(300);
  const want = await p.$eval(row, r => r.dataset.slug);
  const y0 = await p.evaluate(() => Math.round(scrollY));
  await p.click(row + ' .bar-track');
  await p.waitForTimeout(700);
  out.fromBoard = Object.assign({ want, scrollBefore: y0 }, await marks(p));
  out.fromBoard.url = p.url();

  // Hover elsewhere must not move the other sections.
  await p.locator('.rhythm-row:nth-child(4)').hover();
  await p.waitForTimeout(200);
  out.hoverKeepsPin = (await marks(p)).board === want;

  await p.keyboard.press('Escape');
  await p.waitForTimeout(500);
  out.afterEscape = await marks(p);

  // Pin from Heard, then click it again to clear.
  const erow = '#ear-bars .bar-row:nth-child(3)';
  await p.locator(erow).scrollIntoViewIfNeeded();
  const ewant = await p.$eval(erow, r => r.dataset.slug);
  await p.click(erow + ' .bar-track');
  await p.waitForTimeout(600);
  out.fromHeard = Object.assign({ want: ewant }, await marks(p));
  await p.click('#ear-bars .bar-row.stat-focus .bar-track');
  await p.waitForTimeout(400);
  out.secondClickClears = (await marks(p)).chip === null;

  // The name still navigates.
  await p.click('#board-rows .bar-row:nth-child(1) .bar-label');
  await p.waitForLoadState('domcontentloaded');
  out.nameNavigates = /\/birds\/species\//.test(p.url());

  // #bird= on load.
  await p.goto(BASE + '/birds/stats#bird=carolina-wren', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);
  out.hashOnLoad = await marks(p);
  out.desktopErrors = errs;
  await c.close();

  // Phone: tap a row (its name included: on touch the whole row pins).
  const m = await b.newContext({ viewport: { width: 412, height: 860 }, isMobile: true, hasTouch: true });
  const mp = await m.newPage();
  const merrs = [];
  mp.on('pageerror', e => merrs.push(e.message));
  await mp.goto(BASE + '/birds/stats', { waitUntil: 'networkidle' });
  await mp.waitForTimeout(1500);
  await mp.locator('#board-rows .bar-row:nth-child(3)').scrollIntoViewIfNeeded();
  await mp.waitForTimeout(300);
  const mwant = await mp.$eval('#board-rows .bar-row:nth-child(3)', r => r.dataset.slug);
  await mp.tap('#board-rows .bar-row:nth-child(3) .bar-label');   // the whole row pins on touch
  await mp.waitForTimeout(700);
  out.phoneTap = Object.assign({ want: mwant }, await marks(mp));
  out.phoneChipVisible = await mp.evaluate(() => {
    const r = document.getElementById('pin-chip').getBoundingClientRect();
    return r.width > 0 && r.right <= innerWidth + 1 && r.left >= 0;
  });
  out.phoneErrors = merrs;
  await m.close();

  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
