const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  for (const bird of ['Hairy Woodpecker', 'Wood Thrush', 'Indian Peafowl', 'Northern Flicker', 'Barred Owl']) {
    const p = await c.newPage();
    await p.goto('http://127.0.0.1:5055/birds?view=field&bird=' + encodeURIComponent(bird), { waitUntil: 'networkidle' });
    await p.waitForTimeout(2200);
    const r = await p.evaluate(() => {
      const vis = [...document.querySelectorAll('.bf-tile')].filter(t => {
        const b = t.getBoundingClientRect();
        return b.bottom > 140 && b.top < innerHeight && b.right > 0 && b.left < innerWidth;
      });
      const srcs = vis.map(t => (t.querySelector('img') || {}).currentSrc || '').filter(Boolean);
      const count = {}; srcs.forEach(s => count[s] = (count[s] || 0) + 1);
      const seq = JSON.parse(document.getElementById('bf-seq').textContent);
      return { frames: seq.length, onScreen: vis.length, distinct: Object.keys(count).length,
               worstRepeat: Math.max(0, ...Object.values(count)) };
    });
    console.log('  ' + bird.padEnd(20) + ' ' + JSON.stringify(r));
    await p.close();
  }
  await b.close();
})();
