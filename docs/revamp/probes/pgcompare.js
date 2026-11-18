const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Photography vs the bird gallery: grid and the opened detail, phone + desktop.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [tag, vp, mob] of [['phone', { width: 412, height: 915 }, true], ['desk', { width: 1440, height: 900 }, false]]) {
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: mob ? 2 : 1, isMobile: mob, hasTouch: mob });
    const p = await ctx.newPage();
    await p.goto(S + '/photography', { waitUntil: 'load' }); await p.waitForTimeout(2000);
    await p.screenshot({ path: `${process.env.OUT}/pg-grid-${tag}.png` });
    await p.locator('#pg-grid .shot').nth(1).click(); await p.waitForTimeout(2000);
    await p.screenshot({ path: `${process.env.OUT}/pg-open-${tag}.png` });
    console.log(tag, 'pg open overlay:', await p.evaluate(() => [...document.querySelectorAll('body > div, body > section')].filter(e => getComputedStyle(e).position === 'fixed' && e.offsetWidth).map(e => e.id || e.className).join(' | ')));
    await p.goto(S + '/birds/species/eastern-bluebird', { waitUntil: 'load' }); await p.waitForTimeout(2000);
    await p.screenshot({ path: `${process.env.OUT}/sp-grid-${tag}.png` });
    await p.locator('.masonry [data-images]').nth(1).click(); await p.waitForTimeout(2500);
    await p.screenshot({ path: `${process.env.OUT}/sp-open-${tag}.png` });
    await ctx.close();
  }
  await b.close();
})();
