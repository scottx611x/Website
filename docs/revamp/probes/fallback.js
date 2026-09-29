const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  for (const [label, q] of [['1 frame', '?bird=Indian+Peafowl'], ['2 frames', '?bird=Hairy+Woodpecker'],
                            ['50 frames', '?bird=Northern+Flicker'], ['family', '?family=Pigeons+%26+Doves'],
                            ['all', ''], ['forced field on 1', '?bird=Indian+Peafowl&view=field']]) {
    const p = await c.newPage();
    await p.goto('http://127.0.0.1:5055/birds' + q, { waitUntil: 'networkidle' });
    await p.waitForTimeout(1800);
    const r = await p.evaluate(() => {
      const field = !!document.querySelector('.bf-canvas');
      const vis = [...document.querySelectorAll('.bf-tile, .masonry figure')].filter(t => {
        const b = t.getBoundingClientRect();
        return b.bottom > 150 && b.top < innerHeight && b.right > 0 && b.left < innerWidth; });
      const srcs = vis.map(t => (t.querySelector('img') || {}).currentSrc || '').filter(Boolean);
      const cnt = {}; srcs.forEach(s => cnt[s] = (cnt[s] || 0) + 1);
      return { view: field ? 'field' : 'grid', onScreen: vis.length,
               worstRepeat: Math.max(0, ...Object.values(cnt)) };
    });
    console.log('  ' + label.padEnd(20) + ' ' + JSON.stringify(r));
    await p.close();
  }
  await b.close();
})();
