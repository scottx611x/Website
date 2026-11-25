// Live, three regressions: the bird on stage is in the reel (and leads it);
// the soundtrack's ▶ opens the viewer (with its ✕), not invisible audio;
// stamps vary across birds picked from the reel.
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const p = await c.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));
  await p.goto(S + '/birds/live', { waitUntil: 'networkidle' }); await p.waitForTimeout(1500);
  const reel = await p.evaluate(() => {
    const hero = (document.querySelector('#lv-hero .lv-nm') || {}).textContent || '';
    const chips = [...document.querySelectorAll('#lv-wall .lv-chip')].map(c => c.title.split(' · ')[0]);
    const recs = (window.LIVE && LIVE.dayrecs) || [];
    return { hero: hero.trim(), chips: chips.slice(0, 6), heroInReel: chips.some(n => hero.includes(n)) };
  });
  console.log('reel', JSON.stringify(reel));
  const stamps = [];
  const n = await p.locator('#lv-wall .lv-chip').count();
  for (let i = 0; i < Math.min(n, 8); i++) {
    await p.evaluate(i => { const c = document.querySelectorAll('#lv-wall .lv-chip')[i]; c.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); }, i);
    await p.waitForTimeout(1400);
    stamps.push(await p.evaluate(() => { const q = sel => document.querySelector('#lv-hero > :not(.lv-leave) ' + sel); const s = q('.lv-stamp'); const f = q('.lv-fact');
      return ((q('.lv-nm') || {}).textContent || '').trim() + ' | ' + (s ? s.textContent : '-') + ' | ' + (f ? f.textContent : '-'); }));
  }
  stamps.forEach(s => console.log('  ' + s));
  // Labels: stamps are occasions from a fixed list; none of the retired
  // filler may appear anywhere on the stage (LIVE_LABELS_PLAN.md).
  const OK = /^(new to the yard|first since [a-z]{3} \d{1,2}|second visit|third visit|(early|late) for an? [a-z-]+|first bird of the day|busiest day yet)$/i;
  const BANNED = /checking in|unmistakable|most heard today|clear as a bell|days straight|call today|up before the sun|after dark|dawn chorus|night caller/i;
  const lab = await p.evaluate(() => ({ stamps: [...document.querySelectorAll('#lv-stage .lv-stamp')].map(e => e.textContent.trim()),
    text: (document.getElementById('lv-stage') || document.body).innerText }));
  const badStamp = lab.stamps.filter(t => !OK.test(t)), banned = (lab.text.match(BANNED) || [])[0];
  console.log('labels', JSON.stringify({ stamps: lab.stamps, badStamp, banned: banned || null }));
  if (badStamp.length || banned) process.exitCode = 1;
  await p.keyboard.press('Escape');
  const btn = p.locator('#lv-track .lv-rowplay').first();
  let viewer = 'no track buttons';
  if (await btn.count()) {
    await btn.scrollIntoViewIfNeeded(); await btn.tap(); await p.waitForTimeout(600);
    viewer = await p.evaluate(() => ({ open: !!document.querySelector('.lv-zclose'), hasClose: !!document.querySelector('.lv-zclose') }));
    if (viewer.open) { await p.tap('.lv-zclose'); await p.waitForTimeout(300); viewer.closed = await p.evaluate(() => !document.querySelector('.lv-zclose')); }
  }
  console.log('track ▶', JSON.stringify(viewer));
  console.log('errors', errs.length, errs.join(' | '));
  await b.close();
  process.exit(process.exitCode ? 1 : reel.heroInReel && viewer.open && viewer.closed && !errs.length ? 0 : 1);
})();
