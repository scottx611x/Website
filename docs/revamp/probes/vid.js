const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [w, h, touch] of [[1440, 860, false], [390, 780, true]]) {
    const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: touch, hasTouch: touch });
    await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto('http://127.0.0.1:5055/birds?media=video', { waitUntil: 'networkidle' });
    await p.waitForTimeout(3000);
    const top = await p.evaluate(() => {
      const v = [...document.querySelectorAll('video.hover-video')];
      return { cards: document.querySelectorAll('.shot').length, attached: v.length,
               playing: v.filter(x => !x.paused).length };
    });
    await p.evaluate(() => scrollTo(0, 3000)); await p.waitForTimeout(2500);
    const down = await p.evaluate(() => {
      const v = [...document.querySelectorAll('video.hover-video')];
      const onScreen = v.filter(x => { const r = x.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; });
      return { attached: v.length, playing: v.filter(x => !x.paused).length, onScreen: onScreen.length };
    });
    console.log('  ' + (w + 'px').padEnd(7) + ' at top: ' + JSON.stringify(top) +
                '  scrolled: ' + JSON.stringify(down) + ' errors=' + errs.length);
    errs.forEach(e => console.log('     ! ' + e));
    await c.close();
  }
  await b.close();
})();
