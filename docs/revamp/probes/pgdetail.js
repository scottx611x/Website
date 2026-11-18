const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// /photography opens subjects in the birds' detail view: opens, panel, close, Back, links.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [tag, vp, mob] of [['phone', { width: 412, height: 915 }, true], ['desk', { width: 1440, height: 900 }, false]]) {
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: mob ? 2 : 1, isMobile: mob, hasTouch: mob });
    const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await p.goto(S + '/photography', { waitUntil: 'load' }); await p.waitForTimeout(1500);
    // a multi-photo subject
    const card = p.locator('#pg-grid .shot:has(.multi-badge)').first();
    const want = await card.getAttribute('data-subject');
    await card.click(); await p.waitForTimeout(2000);
    const st = () => p.evaluate(() => ({
      open: document.getElementById('bf-over').classList.contains('open'), kind: document.getElementById('bf-over').dataset.kind,
      oldLightbox: !document.getElementById('lightbox').hidden, hash: location.hash,
      title: document.getElementById('bf-otitle').textContent, sub: document.getElementById('bf-ofam').textContent,
      count: document.getElementById('bf-ocount').textContent, strip: document.querySelectorAll('#bf-ostrip img').length,
      facts: [...document.querySelectorAll('#bf-ofacts div')].map(d => d.textContent.trim().replace(/\s+/g, ' ')).join(' | '),
      months: document.querySelectorAll('#bf-omonths i').length, sound: !document.getElementById('bf-sound').hidden || !document.getElementById('bf-nosound').hidden,
      stage: document.getElementById('bf-oimg').naturalWidth }));
    console.log(tag, want, JSON.stringify(await st()));
    await p.screenshot({ path: `${process.env.OUT}/pgd-${tag}.png` });
    await p.keyboard.press('ArrowRight'); await p.waitForTimeout(800);
    console.log(tag, 'after →', (await st()).count);
    await p.goBack(); await p.waitForTimeout(600);
    console.log(tag, 'after Back', JSON.stringify({ open: (await st()).open, hash: await p.evaluate(() => location.hash) }));
    const pid = await p.evaluate(() => { const s = JSON.parse(document.getElementById('pg-subjects').textContent); const k = Object.keys(s).find(k => s[k].frames.length > 2); return s[k].frames[2].pid; });
    await p.goto('about:blank'); await p.goto(S + '/photography#img-' + pid + '.0', { waitUntil: 'load' }); await p.waitForTimeout(2000);
    console.log(tag, 'old share link', JSON.stringify(await st()).slice(0, 200));
    console.log(tag, 'errors', errs.length ? errs : 'none');
    await ctx.close();
  }
  await b.close();
})();
