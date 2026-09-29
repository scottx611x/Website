const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 110)));
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2400);
  const seen = await p.evaluate(async () => {
    const out = [];
    const t = setInterval(() => {
      document.getAnimations().forEach(a => {
        const pe = a.effect && a.effect.pseudoElement;
        if (pe && pe.indexOf('view-transition') >= 0) {
          const k = pe + '|' + (a.animationName || '') + '|' + Math.round(a.effect.getTiming().duration);
          if (!out.includes(k)) out.push(k);
        }
      });
    }, 16);
    window.bfScale(120);
    await new Promise(r => setTimeout(r, 1200));
    clearInterval(t);
    return out;
  });
  console.log('  zoom-out animations:'); seen.forEach(s => console.log('    ' + s));
  console.log('  classes cleaned up:', await p.evaluate(() => document.documentElement.className));
  // rapid thrash across the threshold must not strand the page mid-transition
  await p.evaluate(async () => {
    for (const w of [260, 120, 300, 110, 240]) { window.bfScale(w); await new Promise(r => setTimeout(r, 90)); }
  });
  await p.waitForTimeout(2000);
  console.log('  after thrash ->', JSON.stringify(await p.evaluate(() => ({
    html: document.documentElement.className,
    overview: document.querySelector('.bf-canvas').classList.contains('overview'),
    tiles: document.querySelectorAll('.bf-tile').length }))));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
