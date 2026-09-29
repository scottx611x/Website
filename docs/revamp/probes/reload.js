const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2000);
  for (let y = 300; y < 800; y += 60) {
    await p.mouse.click(700, y); await p.waitForTimeout(1300);
    if (await p.evaluate(() => !!document.querySelector('.bf-over.open'))) break;
  }
  console.log('  before reload: url =', p.url().replace('http://127.0.0.1:5055', ''));
  // location.reload() reloads the CURRENT url; playwright's reload() replays
  // the original navigation, which here was the pre-redirect /birds.
  await Promise.all([p.waitForNavigation({ waitUntil: 'networkidle' }),
                     p.evaluate(() => location.reload())]);
  await p.waitForTimeout(3200);
  console.log('  after  reload:', JSON.stringify(await p.evaluate(() => ({
    url: location.pathname + location.search + location.hash,
    open: !!document.querySelector('.bf-over.open'),
    tiles: document.querySelectorAll('.bf-tile').length,
  }))));
  await b.close();
})();
