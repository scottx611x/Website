const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const rows = p => p.evaluate(() => [...document.querySelectorAll('.bc-opt')].map(o => ({
  n: o.querySelector('.bc-name').textContent, fam: o.querySelector('.bc-name').classList.contains('is-fam') })));
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [w, h, touch] of [[1440, 860, false], [390, 780, true]]) {
    const c = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: touch, hasTouch: touch });
    await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
    await p.waitForTimeout(2000);

    // search
    if (touch) await p.tap('#speciesSearch'); else await p.click('#speciesSearch');
    await p.waitForTimeout(350);
    const empty = (await rows(p)).length;
    await p.fill('#speciesSearch', 'wood'); await p.waitForTimeout(350);
    const wood = (await rows(p)).slice(0, 4).map(r => (r.fam ? '[' + r.n + ']' : r.n)).join(' | ');
    const popIn = await p.evaluate(() => {
      const q = document.querySelector('.bird-combo-pop').getBoundingClientRect();
      return q.left >= -1 && q.right <= innerWidth + 1 && !document.querySelector('.bird-combo-pop').hidden; });
    await p.keyboard.press('Escape'); await p.waitForTimeout(200);

    // video autoplay: scroll until a video card is on screen
    await p.evaluate(() => scrollTo(0, 0));
    let vids = null;
    for (let s = 0; s < 14; s++) {
      await p.evaluate(y => scrollTo(0, y), s * 700);
      await p.waitForTimeout(900);
      vids = await p.evaluate(() => {
        const v = [...document.querySelectorAll('video.hover-video')];
        return { attached: v.length, playing: v.filter(x => !x.paused).length,
                 cards: document.querySelectorAll('.shot[data-image-videos]').length };
      });
      if (vids.attached) break;
    }
    // and that they detach when scrolled well away
    await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(1200);
    const after = await p.evaluate(() => document.querySelectorAll('video.hover-video').length);
    console.log('  ' + (w + 'px').padEnd(7) + ' search: ' + empty + ' families on focus, "wood" -> ' + wood);
    console.log('           popInViewport=' + popIn + '  video: ' + JSON.stringify(vids) + ' detachedAtTop=' + after + ' errors=' + errs.length);
    errs.forEach(e => console.log('     ! ' + e));
    await c.close();
  }
  await b.close();
})();
