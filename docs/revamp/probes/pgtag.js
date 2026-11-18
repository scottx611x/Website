const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// /photography?tag=sadie: the detail view walks every Sadie photo; the panel follows the subject.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const ctx = await b.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  const st = () => p.evaluate(() => ({ title: document.getElementById('bf-otitle').textContent, count: document.getElementById('bf-ocount').textContent.split('  ·  ')[0],
    strip: document.querySelectorAll('#bf-ostrip img').length, hash: location.hash, photos: (document.querySelector('#bf-ofacts dd') || {}).textContent }));
  for (const tag of [process.env.TAG || 'sadie', '']) {
    await p.goto(S + '/photography' + (tag ? '?tag=' + tag : ''), { waitUntil: 'load' }); await p.waitForTimeout(1500);
    await p.locator('#pg-grid .shot').nth(2).click(); await p.waitForTimeout(1200);
    const a = await st(); const seen = new Set([a.title]);
    for (let i = 0; i < 12; i++) { await p.keyboard.press('ArrowRight'); await p.waitForTimeout(250); seen.add((await st()).title); }
    const z = await st();
    console.log(tag || 'all', 'open', JSON.stringify(a), '-> after 12 steps', JSON.stringify(z), 'subjects seen', seen.size);
    await p.goBack(); await p.waitForTimeout(400);
    console.log('  Back closes:', !(await p.evaluate(() => document.getElementById('bf-over').classList.contains('open'))));
  }
  console.log('errors', errs.length ? errs : 'none');
  await b.close();
})();
