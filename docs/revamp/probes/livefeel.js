// Live page: layout budget, and arrivals released one at a time.
//   docs/revamp/probes/run.sh livefeel [outdir]
// Layout: hero top edge and page height at 1440 and 412, no x-scroll, no errors.
// Arrivals: one poll carrying three new detections must produce three hero
// changes at least 2s apart, in the order heard; with reduced motion the same
// birds arrive with no animation running.
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = 'http://127.0.0.1:5055';
const OUT = process.argv[2] || '/tmp';

async function layout(b, w, h, mobile) {
  const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: mobile, hasTouch: mobile });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto(BASE + '/birds/live', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);
  const m = await p.evaluate(() => ({
    heroTop: Math.round(document.getElementById('lv-hero').getBoundingClientRect().top + scrollY),
    height: document.documentElement.scrollHeight,
    xScroll: document.documentElement.scrollWidth > innerWidth,
    tally: document.getElementById('lv-tally').textContent.replace(/\s+/g, ' ').trim(),
    status: document.getElementById('lv-upd').textContent,
    wallKick: (document.getElementById('lv-wallkick') || {}).textContent || null,   // the stage has a reel instead
    fact: (document.querySelector('#lv-hero .lv-fact') || {}).textContent || null,
    stamp: (document.querySelector('#lv-hero .lv-stamp') || {}).textContent || null,
    trackRows: document.querySelectorAll('#lv-trackrows .lv-trow').length,
    trackPlays: document.querySelectorAll('#lv-trackrows .lv-rowplay').length,
  }));
  await p.screenshot({ path: `${OUT}/livefeel-${w}.png`, fullPage: true });
  await c.close();
  return Object.assign({ width: w, errors: errs }, m);
}

async function arrivals(b, reduced) {
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  let inject = false, injected = [];
  await p.route('**/birds/live.json', async route => {
    const res = await route.fetch();
    const d = await res.json();
    if (inject) {
      // Three new birds, heard 30s, 20s and 10s ago, cloned from real ones so
      // their photos and families are real.
      // skip the bird already on stage (the newest playable clip over the bar),
      // or its 'arrival' changes nothing visible
      const seen = new Set([d.recent[0].display, (d.recent.find(r => r.audio && r.conf >= 0.75) || {}).display]);
      const src = d.recent.filter(r => r.audio && r.conf >= 0.8 && !seen.has(r.display) && seen.add(r.display)).slice(0, 3);
      const now = Date.now();
      injected = src.map((r, i) => Object.assign({}, r, {
        t: new Date(now - (30 - 10 * i) * 1000).toISOString(),
        audio: `probe_${i}.m4a`, node: r.node,
      }));
      d.recent = injected.slice().reverse().concat(d.recent);
      d.dayrecs = injected.slice().reverse().concat(d.dayrecs);
      d.generated = new Date().toISOString();
    }
    await route.fulfill({ response: res, json: d });
  });
  await p.goto(BASE + '/birds/live', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  const name = () => p.evaluate(() => {
    const els = document.querySelectorAll('#lv-hero .lv-nm');
    return els.length ? els[els.length - 1].textContent.trim() : '';
  });
  const before = await name();
  inject = true;
  await p.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  const t0 = Date.now(), changes = [];
  let last = before, animSeen = false, frames = 0;
  while (Date.now() - t0 < 16000) {
    const n = await name();
    if (n !== last) {
      // on the stage: the reel's head and the tab title follow the arrival
      const extra = await p.evaluate(() => ({
        reelHead: ((document.querySelector('#lv-wall.lv-reel .lv-chip') || {}).querySelector || (() => null)).call(document.querySelector('#lv-wall.lv-reel .lv-chip'), '.cl')?.textContent || null,
        title: document.title }));
      changes.push(Object.assign({ at: Date.now() - t0, name: n }, extra));
      last = n;
      if (!reduced && frames < 3) {
        await p.waitForTimeout(350);
        await p.screenshot({ path: `${OUT}/arrive-${frames++}.png`, clip: { x: 0, y: 0, width: 1440, height: 900 } });
      }
    }
    if (!animSeen) animSeen = await p.evaluate(() => document.getAnimations().some(a =>
      /lvHeroIn|lvWipe|lvWord|lvDrop|lvLand|lvSettle/.test(a.animationName || '')));
    await p.waitForTimeout(150);
  }
  const gaps = changes.slice(1).map((c, i) => c.at - changes[i].at);
  await c.close();
  return {
    reduced, before, expected: injected.map(r => r.display), changes, gaps,
    inOrder: JSON.stringify(changes.map(c => c.name)) === JSON.stringify(injected.map(r => r.display)),
    minGapOk: gaps.every(g => g >= 2000), arrivalAnimations: animSeen, errors: errs,
    reelFollows: changes.every(c => c.reelHead == null || c.reelHead === c.name),
    titleFollows: changes.every(c => !c.reelHead || c.title.indexOf(c.name) > 0),
  };
}

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const out = {
    desktop: await layout(b, 1440, 900, false),
    phone: await layout(b, 412, 860, true),
    arrivals: await arrivals(b, false),
    reducedMotion: await arrivals(b, true),
  };
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
