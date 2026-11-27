const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: SRV }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 90)); });
  await p.goto(SRV + '/birds#bird/barred-owl', { waitUntil: 'networkidle' });
  await p.waitForTimeout(3500);
  console.log(JSON.stringify(await p.evaluate(() => ({
    hash: location.hash,
    open: !!document.querySelector('.bf-over.open'),
    title: document.getElementById('bf-otitle').textContent,
    strip: document.querySelectorAll('#bf-ostrip img').length,
    overClasses: document.getElementById('bf-over').className,
  })), null, 1));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
