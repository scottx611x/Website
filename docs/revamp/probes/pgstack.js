const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Unfiltered: a stacked card opens only its subject (count = badge). Filtered: one card per photo, walk = grid.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const p = await (await b.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const count = () => p.$eval('#bf-ocount', e => e.textContent.split('  ·  ')[0]);
  await p.goto(S + '/photography', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1500);
  const badges = await p.$$eval('#pg-grid .shot', cs => cs.map((c, i) => [i, (c.querySelector('.multi-badge') || {}).textContent || '']).filter(x => x[1]).slice(0, 3));
  for (const [i, badge] of badges) {
    await p.locator('#pg-grid .shot').nth(i).click(); await p.waitForTimeout(900);
    const t = await p.$eval('#bf-otitle', e => e.textContent);
    const seen = new Set([t]); for (let k = 0; k < 12; k++) { await p.keyboard.press('ArrowRight'); await p.waitForTimeout(150); seen.add(await p.$eval('#bf-otitle', e => e.textContent)); }
    console.log('badge', badge.trim(), '->', await count(), t, 'titles seen', seen.size);
    await p.goBack(); await p.waitForTimeout(400);
  }
  for (const q of ['?tag=sadie', '?tag=insect', '?subject=mosaic-darner']) {
    await p.goto(S + '/photography' + q, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1200);
    const n = await p.$$eval('#pg-grid .shot', x => x.length), nb = await p.$$eval('.multi-badge', x => x.length);
    await p.locator('#pg-grid .shot').nth(3).click(); await p.waitForTimeout(900);
    console.log(q, 'cards', n, 'badges', nb, 'open 4th ->', await count());
    await p.goBack(); await p.waitForTimeout(300);
  }
  console.log('errors', errs.length ? errs : 'none'); await b.close();
})();
