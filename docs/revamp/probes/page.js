const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const [url, out, h] = process.argv.slice(2);
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: +(h || 900) }, deviceScaleFactor: 1.5 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055' + url, { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  await p.screenshot({ path: out, fullPage: false });
  console.log('  docHeight', await p.evaluate(() => document.documentElement.scrollHeight));
  await b.close();
})();
