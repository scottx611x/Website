const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Search boxes on /photography and /birds (shared static/js/combo.js).
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.env.OUT || '.';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const vp of [{ width: 412, height: 915, m: true }, { width: 1440, height: 900 }]) {
    const ctx = await b.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 2, isMobile: !!vp.m, hasTouch: !!vp.m });
    const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
    const opts = () => p.$$eval('#pgComboList .bc-opt', os => os.map(o => o.textContent.replace(/\s+/g, ' ').trim()).slice(0, 6));
    await p.goto(S + '/photography', { waitUntil: 'load' }); await p.waitForTimeout(800);
    await p.click('#pgSearch'); await p.waitForTimeout(200);
    console.log(vp.width, 'empty:', JSON.stringify(await opts()));
    await p.screenshot({ path: OUT + '/pgsearch-empty-' + vp.width + '.png' });
    for (const q of ['dar', 'rea st', 'sadie', 'turtle']) {
      await p.fill('#pgSearch', q); await p.waitForTimeout(150);
      console.log(vp.width, JSON.stringify(q), JSON.stringify(await opts()));
    }
    await p.fill('#pgSearch', 'darner'); await p.waitForTimeout(150);
    await Promise.all([p.waitForNavigation(), p.keyboard.press('Enter')]); await p.waitForTimeout(800);
    console.log(vp.width, 'picked ->', p.url().replace(S, ''), 'cards', await p.$$eval('#pg-grid .shot', x => x.length),
      'chips', JSON.stringify(await p.$$eval('.bird-active .chip', x => x.map(c => c.textContent.trim()))),
      'meta', await p.$eval('.bird-active-meta', e => e.textContent.trim()));
    await p.screenshot({ path: OUT + '/pgsearch-picked-' + vp.width + '.png' });
    await p.fill('#pgSearch', 'cottontail'); await p.waitForTimeout(150);
    await Promise.all([p.waitForNavigation(), p.keyboard.press('Enter')]); await p.waitForTimeout(800);
    console.log(vp.width, 'added ->', p.url().replace(S, ''), 'cards', await p.$$eval('#pg-grid .shot', x => x.length));
    await p.locator('#pg-grid .shot').nth(0).click(); await p.waitForTimeout(1000);
    console.log(vp.width, 'detail', await p.$eval('#bf-ocount', e => e.textContent));
    await p.goBack(); await p.waitForTimeout(300);
    await Promise.all([p.waitForNavigation(), p.locator('.bird-active .chip').first().click()]); await p.waitForTimeout(500);
    console.log(vp.width, 'removed ->', p.url().replace(S, ''));
    // birds search still works on the shared script
    await p.goto(S + '/birds', { waitUntil: 'load' }); await p.waitForTimeout(800);
    await p.fill('#speciesSearch', 'hawk'); await p.waitForTimeout(150);
    console.log(vp.width, 'birds "hawk":', JSON.stringify(await p.$$eval('#birdComboList .bc-opt', os => os.map(o => o.textContent.replace(/\s+/g, ' ').trim()).slice(0, 4))));
    await Promise.all([p.waitForNavigation(), p.keyboard.press('Enter')]);
    console.log(vp.width, 'birds picked ->', decodeURIComponent(p.url().replace(S, '')));
    console.log(vp.width, 'errors', errs.length ? errs : 'none');
    await ctx.close();
  }
  await b.close();
})();
