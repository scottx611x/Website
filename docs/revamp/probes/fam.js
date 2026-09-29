const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const openOne = async (p, h) => {
  for (let y = 300; y < h - 80; y += 60) {
    await p.mouse.click(700, y); await p.waitForTimeout(1600);
    if (await p.evaluate(() => !!document.querySelector('.bf-over.open'))) return true;
  }
  return false;
};
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  for (const [label, q] of [['family', '?family=Pigeons+%26+Doves'],
                            ['one species', '?bird=Barred+Owl'],
                            ['unfiltered', '']]) {
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto('http://127.0.0.1:5055/birds' + q, { waitUntil: 'networkidle' });
    await p.waitForTimeout(1800);
    if (!await openOne(p, 860)) { console.log('  ' + label + ': could not open'); await p.close(); continue; }
    await p.waitForTimeout(2500);
    const r = await p.evaluate(() => {
      const t = s => { const e = document.querySelector(s); return e && !e.hidden ? e.textContent.trim() : null; };
      return { title: t('#bf-otitle'), sub: t('#bf-ofam'),
               facts: [...document.querySelectorAll('#bf-ofacts dt')].map(e => e.textContent),
               members: [...document.querySelectorAll('#bf-ospecies button')].map(e => e.textContent.trim()),
               ctxNav: !document.getElementById('bf-octx').hidden,
               strip: document.querySelectorAll('#bf-ostrip img').length,
               fullHref: document.getElementById('bf-ofull').getAttribute('href') };
    });
    console.log('  ' + label.padEnd(12) + ' ' + JSON.stringify(r));
    errs.forEach(e => console.log('     ! ' + e));
    if (label === 'family') await p.screenshot({ path: process.env.SP + '/fam.png' });
    await p.close();
  }
  await b.close();
})();
