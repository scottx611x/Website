const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const [w, zoom] of [[1440, '-3'], [1440, '0'], [1440, '3'], [390, '0'], [390, '-3']]) {
    const c = await b.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 2, isMobile: w < 700, hasTouch: w < 700 });
    await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
    const p = await c.newPage();
    await p.addInitScript(z => { try { localStorage.setItem('birdsThumbZoom', z); } catch (e) {} }, zoom);
    await p.goto('http://127.0.0.1:5055/birds?area=elsewhere', { waitUntil: 'networkidle' });
    await p.waitForTimeout(1800);
    // force it visible the way focus does, and measure the real painted box
    await p.addStyleTag({ content: '.away-badge::after{opacity:1!important;transform:none!important}' });
    await p.waitForTimeout(300);
    const r = await p.evaluate(() => {
      const badge = document.querySelector('.away-badge');
      const card = badge.closest('.shot');
      const cb = card.getBoundingClientRect(), bb = badge.getBoundingClientRect();
      const a = getComputedStyle(badge, '::after');
      const right = parseFloat(a.right), width = parseFloat(a.width), height = parseFloat(a.height);
      const noteRight = bb.right - right, noteLeft = noteRight - width;
      return { cardW: Math.round(cb.width), noteW: Math.round(width), noteH: Math.round(height),
               insideLeft: noteLeft >= cb.left - 0.5, insideRight: noteRight <= cb.right + 0.5,
               lines: Math.round(height / 14.7) };
    });
    console.log('  ' + (w + 'px').padEnd(7) + ' zoom ' + zoom.padEnd(3) + ' ' + JSON.stringify(r));
    if (w === 1440 && zoom === '0') {
      const bx = await (await p.$('.away-badge')).boundingBox();
      await p.screenshot({ path: process.env.SP + '/tip_ok.png',
        clip: { x: Math.max(0, bx.x - 280), y: Math.max(0, bx.y - 16), width: 330, height: 130 } });
    }
    await c.close();
  }
  await b.close();
})();
