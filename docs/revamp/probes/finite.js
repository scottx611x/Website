const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  for (const [label, q] of [['1 frame', '?bird=Indian+Peafowl'], ['2 frames', '?bird=Hairy+Woodpecker'],
                            ['50 frames', '?bird=Northern+Flicker'], ['family 59', '?family=Pigeons+%26+Doves'],
                            ['all', '']]) {
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto('http://127.0.0.1:5055/birds' + q, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2200);
    const before = await p.evaluate(() => {
      const vis = [...document.querySelectorAll('.bf-tile')].filter(t => {
        const b = t.getBoundingClientRect();
        return b.bottom > 150 && b.top < innerHeight && b.right > 0 && b.left < innerWidth; });
      const s = vis.map(t => (t.querySelector('img') || {}).currentSrc || '').filter(Boolean);
      const cnt = {}; s.forEach(x => cnt[x] = (cnt[x] || 0) + 1);
      return { seq: JSON.parse(document.getElementById('bf-seq').textContent).length,
               onScreen: vis.length, worstRepeat: Math.max(0, ...Object.values(cnt)),
               totalTiles: document.querySelectorAll('.bf-tile').length };
    });
    // pan hard in every direction and re-check for duplicates / emptiness
    for (const [dx, dy] of [[-1, 0], [0, -1], [1, 0], [0, 1], [-1, -1]]) {
      await p.mouse.move(700, 500); await p.mouse.down();
      for (let i = 1; i <= 15; i++) await p.mouse.move(700 + dx * i * 60, 500 + dy * i * 40);
      await p.mouse.up(); await p.waitForTimeout(400);
    }
    await p.waitForTimeout(900);
    const after = await p.evaluate(() => {
      const vis = [...document.querySelectorAll('.bf-tile')].filter(t => {
        const b = t.getBoundingClientRect();
        return b.bottom > 150 && b.top < innerHeight && b.right > 0 && b.left < innerWidth; });
      const s = vis.map(t => (t.querySelector('img') || {}).currentSrc || '').filter(Boolean);
      const cnt = {}; s.forEach(x => cnt[x] = (cnt[x] || 0) + 1);
      return { onScreen: vis.length, worstRepeat: Math.max(0, ...Object.values(cnt)) };
    });
    console.log('  ' + label.padEnd(11) + ' seq=' + String(before.seq).padEnd(4) +
                ' start:' + JSON.stringify(before).slice(0, 70) +
                '  after panning: ' + JSON.stringify(after) + ' errors=' + errs.length);
    errs.forEach(e => console.log('     ! ' + e));
    if (label === '2 frames') await p.screenshot({ path: process.env.SP + '/finite2.png' });
    await p.close();
  }
  await b.close();
})();
