const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  // sample the running animations while the transition is in flight
  const sample = await p.evaluate(async () => {
    const tile = document.querySelector('.bf-tile');
    const r = tile.getBoundingClientRect();
    const seen = [];
    const t = setInterval(() => {
      document.getAnimations().forEach(a => {
        const n = a.effect && a.effect.pseudoElement;
        if (n && n.indexOf('view-transition') >= 0) {
          const key = n + '|' + Math.round(a.effect.getTiming().duration);
          if (!seen.includes(key)) seen.push(key);
        }
      });
    }, 16);
    tile.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: r.x + 5, clientY: r.y + 5, pointerId: 1 }));
    tile.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, clientX: r.x + 5, clientY: r.y + 5, pointerId: 1 }));
    await new Promise(r2 => setTimeout(r2, 1400));
    clearInterval(t);
    return seen;
  });
  console.log('  pseudo-element animations seen during the open:');
  sample.forEach(s => console.log('    ' + s));
  await b.close();
})();
