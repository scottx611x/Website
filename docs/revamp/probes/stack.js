const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const CASES = {
  'as-is': '',
  'no transform on #bg-effect': '#bg-effect.bg-wall{transform:none!important}',
  'no transform on .wall-run': '.wall-run{animation:none!important;will-change:auto!important}',
  'nav z-index 2': 'body.home .site-nav{z-index:2!important}',
  'bg-effect z -2': '#bg-effect{z-index:-2!important}',
};
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: SRV }]);
  for (const [name, css] of Object.entries(CASES)) {
    const p = await c.newPage();
    await p.goto(SRV + '/', { waitUntil: 'networkidle' });
    if (css) await p.addStyleTag({ content: css });
    await p.waitForTimeout(900);
    const top = await p.evaluate(() => {
      const a = document.querySelector('.site-nav nav a'); const r = a.getBoundingClientRect();
      const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      return e ? e.tagName + '.' + (e.className || '').toString().slice(0, 20) : null;
    });
    console.log('  ' + name.padEnd(28) + ' topmost at nav link: ' + top);
    await p.close();
  }
  await b.close();
})();
