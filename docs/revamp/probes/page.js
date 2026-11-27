// Screenshot one page:  docs/revamp/probes/run.sh page [/path] [out.png] [height]
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
(async () => {
  const [url = '/', out = (process.env.OUT || '/tmp') + '/page.png', h] = process.argv.slice(2);
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: +(h || 900) }, deviceScaleFactor: 1.5 });
  await c.addCookies([{ name: 'curate', value: '0', url: SRV }]);
  const p = await c.newPage();
  await p.goto(SRV + url, { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  await p.screenshot({ path: out, fullPage: false });
  console.log('  docHeight', await p.evaluate(() => document.documentElement.scrollHeight));
  await b.close();
})();
