const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const {PNG} = require(process.env.SP + '/node_modules/pngjs');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2600);
  console.log('  stack at the first nav link:', await p.evaluate(() => {
    const a = document.querySelector('.site-nav nav a'); const r = a.getBoundingClientRect();
    return (document.elementsFromPoint(r.x + r.width/2, r.y + r.height/2) || [])
      .slice(0, 4).map(e => e.tagName + '.' + (e.className||'').toString().slice(0,18)).join(' > ');
  }));
  // luminance of the nav strip with the links hidden, i.e. the backdrop alone
  await p.addStyleTag({ content: '.site-nav nav, .site-nav .brand { visibility: hidden !important; }' });
  await p.waitForTimeout(250);
  const img = PNG.sync.read(await p.screenshot({ clip: { x: 900, y: 0, width: 540, height: 60 } }));
  let sum = 0, n = 0, mx = 0;
  for (let y = 0; y < img.height; y += 2) for (let x = 0; x < img.width; x += 2) {
    const i = (img.width * y + x) << 2;
    const L = 0.2126*img.data[i] + 0.7152*img.data[i+1] + 0.0722*img.data[i+2];
    sum += L; n++; if (L > mx) mx = L;
  }
  console.log('  nav-strip backdrop: mean ' + (sum/n).toFixed(1) + '  brightest ' + mx.toFixed(0) +
              '   (white text needs this well under ~110)');
  await b.close();
})();
