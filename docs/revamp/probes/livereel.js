// /birds/live?stage=1 — the reel (LIVE_STAGE_PLAN.md phase 2).
//   docs/revamp/probes/run.sh livereel
// Picking a frame puts that bird on stage without moving the page; Escape
// returns to the latest; a poll that brings a new bird does not take the
// stage from a picked one (the chip counts it); the reel scrolls by
// horizontal wheel and mouse drag while a vertical wheel still scrolls the
// page; arrow keys step it; a phone tap picks too.
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const stageName = p => p.evaluate(() => {
  const els = document.querySelectorAll('#lv-hero .lv-nm');
  return els.length ? els[els.length - 1].textContent.trim().replace(/\s+/g, ' ') : '';
});
const state = p => p.evaluate(() => ({
  back: document.getElementById('lv-back').hidden ? null : document.getElementById('lv-back').textContent,
  on: (document.querySelector('#lv-wall .lv-chip.on .cl') || {}).textContent || null,
  scrollY: Math.round(scrollY), reelLeft: Math.round(document.getElementById('lv-wall').scrollLeft),
  player: !document.getElementById('lv-player').hidden,
}));
const chipName = (p, i) => p.$eval(`#lv-wall .lv-chip:nth-child(${i}) .cl`, e => e.textContent.trim());

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const out = {};
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  let inject = false;
  await p.route(u => u.pathname === '/birds/live.json', async route => {
    const res = await route.fetch(); const d = await res.json();
    if (inject) {
      const src = d.recent.find(r => r.audio && r.conf >= 0.8 && r.photo);
      const n = Object.assign({}, src, { t: new Date(Date.now() - 5000).toISOString(), audio: 'probe_new.m4a' });
      d.recent = [n].concat(d.recent); d.dayrecs = [n].concat(d.dayrecs); d.generated = new Date().toISOString();
    }
    await route.fulfill({ response: res, json: d });
  });
  await p.goto(BASE + '/birds/live?stage=1', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2000);
  const live = await stageName(p);
  out.live = live;

  // pick the 5th frame by its picture (not its name)
  const want = await chipName(p, 5);
  const box = await p.$eval('#lv-wall .lv-chip:nth-child(5)', e => { const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + 12 }; });
  const y0 = await p.evaluate(() => Math.round(scrollY));
  await p.mouse.click(box.x, box.y);
  await p.waitForTimeout(1300);
  out.pick = Object.assign({ want, got: await stageName(p), scrollBefore: y0 }, await state(p));

  // a poll brings a new bird: the pick keeps the stage
  inject = true;
  await p.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  // wait for the poll (a cold server can take seconds), then for the release
  await p.waitForFunction(() => /new/.test(document.getElementById('lv-back').textContent), null, { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(1500);
  out.newWhilePicked = Object.assign({ stage: await stageName(p) }, await state(p));
  inject = false;

  await p.keyboard.press('Escape');
  await p.waitForTimeout(1300);
  out.escape = Object.assign({ stage: await stageName(p) }, await state(p));

  // the name of a frame is still a link with a mouse
  out.nameIsLink = await p.$eval('#lv-wall a.lv-chip', a => a.getAttribute('href'));

  // wheel: horizontal moves the reel, vertical moves the page
  const reel = await p.$eval('#lv-wall', e => { const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
  await p.mouse.move(reel.x, reel.y);
  await p.mouse.wheel(400, 0); await p.waitForTimeout(500);
  out.hWheel = await state(p);
  await p.mouse.wheel(0, 300); await p.waitForTimeout(500);
  out.vWheel = await state(p);
  await p.evaluate(() => { scrollTo(0, 0); document.getElementById('lv-wall').scrollLeft = 0; });
  await p.waitForTimeout(300);

  // mouse drag scrolls without picking
  const before = await stageName(p);
  await p.mouse.move(reel.x + 300, reel.y); await p.mouse.down();
  for (let i = 1; i <= 10; i++) await p.mouse.move(reel.x + 300 - i * 30, reel.y);
  await p.mouse.up(); await p.waitForTimeout(400);
  out.drag = Object.assign({ stageUnchanged: (await stageName(p)) === before }, await state(p));
  await p.evaluate(() => { document.getElementById('lv-wall').scrollLeft = 0; });

  // keyboard: focus frame 2, arrow right picks frame 3
  const k3 = await chipName(p, 3);
  await p.focus('#lv-wall .lv-chip:nth-child(2)');
  await p.keyboard.press('ArrowRight'); await p.waitForTimeout(1200);
  out.keyboard = { want: k3, got: await stageName(p) };
  await p.keyboard.press('Escape'); await p.waitForTimeout(800);
  out.errors = errs;
  await c.close();

  // phone: tapping a frame (its name included) picks it
  const m = await b.newContext({ viewport: { width: 412, height: 860 }, isMobile: true, hasTouch: true });
  const mp = await m.newPage();
  const merrs = []; mp.on('pageerror', e => merrs.push(e.message));
  await mp.goto(BASE + '/birds/live?stage=1', { waitUntil: 'networkidle' });
  await mp.waitForTimeout(1800);
  const mw = await chipName(mp, 3);
  const my0 = await mp.evaluate(() => Math.round(scrollY));
  await mp.tap('#lv-wall .lv-chip:nth-child(3) .cl');
  await mp.waitForTimeout(1300);
  out.phone = Object.assign({ want: mw, got: await stageName(mp), url: mp.url(), scrollBefore: my0,
    reelScrollable: await mp.$eval('#lv-wall', e => e.scrollWidth > e.clientWidth && getComputedStyle(e).overflowX === 'auto') }, await state(mp));
  out.phoneErrors = merrs;
  await m.close();

  const ok = {
    pickShowsBird: out.pick.got === out.pick.want && out.pick.on === out.pick.want,
    pickNoScroll: out.pick.scrollY === out.pick.scrollBefore,
    pickBackChip: !!out.pick.back,
    pollKeepsPick: out.newWhilePicked.stage === want && /1 new/.test(out.newWhilePicked.back || ''),
    escapeReturns: out.escape.back === null && out.escape.stage !== want,
    hWheelScrollsReel: out.hWheel.reelLeft > 0 && out.hWheel.scrollY === 0,
    vWheelScrollsPage: out.vWheel.scrollY > 0,
    dragScrollsNotPicks: out.drag.reelLeft > 100 && out.drag.stageUnchanged,
    keyboardSteps: out.keyboard.got === out.keyboard.want,
    phoneTapPicks: out.phone.got === out.phone.want && /stage=1/.test(out.phone.url) && out.phone.scrollY === out.phone.scrollBefore,
    phoneReelScrollable: out.phone.reelScrollable,
    noErrors: !out.errors.length && !out.phoneErrors.length,
  };
  console.log(JSON.stringify({ ok, out }, null, 1));
  await b.close();
})();
