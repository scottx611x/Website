const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  console.log(JSON.stringify(await p.evaluate(() => {
    const rows = [...document.querySelectorAll('.bf-tile')]
      .map(x => ({ age: +x.style.getPropertyValue('--age'), date: (x._t && x._t.date) || '' }))
      .filter(r => r.date).sort((a, b) => a.age - b.age);
    // correlation between age rank and date rank: should be ~ -1 (age up, date down)
    const byDate = rows.slice().sort((a, b) => b.date.localeCompare(a.date));
    let inversions = 0;
    for (let i = 0; i < rows.length; i++) if (rows[i].date !== byDate[i].date) inversions++;
    return { n: rows.length, newest: rows[0], oldest: rows[rows.length - 1],
             orderMismatches: inversions };
  }), null, 1));
  await b.close();
})();
