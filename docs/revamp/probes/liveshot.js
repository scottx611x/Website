const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: SRV }]);
  const p = await c.newPage();
  await p.goto(SRV + '/birds/live', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  await p.evaluate(() => scrollTo(0, 1400)); await p.waitForTimeout(800);
  await p.screenshot({ path: process.env.SP + '/live-stuck.png', clip: { x: 0, y: 0, width: 1440, height: 200 } });
  await b.close();
})();
