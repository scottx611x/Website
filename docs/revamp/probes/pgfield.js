const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// /photography: Shuffle = the field; a tile opens its subject; filtered views walk the view; orders = grid.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.env.OUT || '.';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const vp of [{ width: 412, height: 915, m: true }, { width: 1440, height: 900 }]) {
    const p = await (await b.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 2, isMobile: !!vp.m, hasTouch: !!vp.m })).newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    const st = () => p.evaluate(() => ({ t: document.getElementById('bf-otitle').textContent, n: document.getElementById('bf-ocount').textContent.split('  ·  ')[0] }));
    const tapTile = async () => {
      const box = await p.evaluate(() => { const ts = [...document.querySelectorAll('.bf-tile')].map(t => t.getBoundingClientRect()).filter(r => r.top > 160 && r.bottom < innerHeight - 20 && r.left > 0 && r.right < innerWidth); const r = ts[0]; return r && { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
      if (!box) return 'no tile';
      if (vp.m) await p.touchscreen.tap(box.x, box.y); else await p.mouse.click(box.x, box.y);
      await p.waitForTimeout(1200); return st();
    };
    for (const q of ['', '?tag=sadie', '?subject=mosaic-darner']) {
      await p.goto(S + '/photography' + q, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1800);
      const tiles = await p.$$eval('.bf-tile', x => x.length);
      if (!q) await p.screenshot({ timeout: 90000, path: OUT + '/pgfield-' + vp.width + '.png' });
      const a = await tapTile();
      console.log(vp.width, q || '(shuffle)', 'tiles', tiles, 'tap ->', JSON.stringify(a), 'subject size', a.t && await p.evaluate(t => { const S = JSON.parse(document.getElementById('pg-subjects').textContent); const k = Object.keys(S).find(k => S[k].name === t); return k && S[k].frames.length; }, a.t));
    }
    await p.goto(S + '/photography', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1200);
    await p.click('#vmBtn'); await p.waitForTimeout(250);
    await p.screenshot({ timeout: 90000, path: OUT + '/pgmenu-' + vp.width + '.png' });
    await Promise.all([p.waitForNavigation(), p.click('#vmPop .vm-opt:has-text("Newest")')]); await p.waitForTimeout(1200);
    const cards = await p.$$eval('#pg-grid .shot', x => x.length), fv = await p.evaluate(() => document.body.classList.contains('field-view'));
    await p.screenshot({ timeout: 90000, path: OUT + '/pgnewest-' + vp.width + '.png' });
    await p.locator('#pg-grid .shot').nth(0).click(); await p.waitForTimeout(1000);
    console.log(vp.width, 'newest ->', p.url().replace(S, '').split('#')[0], 'cards', cards, 'field-view', fv, 'open first', JSON.stringify(await st()));
    await p.goBack(); await p.waitForTimeout(300);
    await p.click('#vmBtn'); await p.waitForTimeout(200);
    await p.$eval('#thumbZoom', z => { z.value = 2; z.dispatchEvent(new Event('input')); }); await p.waitForTimeout(300);
    console.log(vp.width, 'size +2 -> columns', await p.$$eval('#pg-grid .masonry-col', x => x.length));
    await p.$eval('#thumbZoom', z => { z.value = 0; z.dispatchEvent(new Event('input')); });
    console.log(vp.width, 'errors', errs.length ? errs : 'none');
  }
  await b.close();
})();
