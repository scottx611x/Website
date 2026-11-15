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
    await p.waitForTimeout(500);
    stamps.push(await p.evaluate(() => { const s = document.querySelector('#lv-hero .lv-stamp'); const f = document.querySelector('#lv-hero .lv-fact');
      return ((document.querySelector('#lv-hero .lv-nm') || {}).textContent || '').trim() + ' | ' + (s ? s.textContent : '-') + ' | ' + (f ? f.textContent : '-'); }));
  }
  stamps.forEach(s => console.log('  ' + s));
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
  process.exit(reel.heroInReel && viewer.open && viewer.closed && !errs.length ? 0 : 1);
})();
