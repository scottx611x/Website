const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2600);
  // sample the rendered backdrop luminance behind each text block
  const shot = await p.screenshot({ type: 'png' });
  const boxes = await p.evaluate(() => {
    const pick = s => { const e = document.querySelector(s); if (!e) return null;
      const r = e.getBoundingClientRect(); return { s, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; };
    return ['.hero-title', '.hero-sub', '.hero-eyebrow', '.site-nav nav a'].map(pick).filter(Boolean);
  });
  const { PNG } = (() => { try { return require(process.env.SP + '/node_modules/pngjs'); } catch (e) { return {}; } })();
  if (!PNG) { console.log('  boxes:', JSON.stringify(boxes)); await b.close(); return; }
  const img = PNG.sync.read(shot);
  for (const bx of boxes) {
    let sum = 0, n = 0;
    for (let y = bx.y; y < Math.min(bx.y + bx.h, img.height); y += 2)
      for (let x = bx.x; x < Math.min(bx.x + bx.w, img.width); x += 2) {
        const i = (img.width * y + x) << 2;
        sum += 0.2126 * img.data[i] + 0.7152 * img.data[i+1] + 0.0722 * img.data[i+2]; n++;
      }
    console.log('  ' + bx.s.padEnd(18) + ' mean luminance behind+text: ' + (sum / n).toFixed(1));
  }
  await b.close();
})();
