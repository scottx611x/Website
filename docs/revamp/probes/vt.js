const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const isOpen = p => p.evaluate(() => !!document.querySelector('.bf-over.open'));
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 110)));
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  console.log('  startViewTransition supported:', await p.evaluate(() => !!document.startViewTransition));

  // capture whether a transition actually runs, and that names are cleaned up
  await p.evaluate(() => {
    window.__vt = 0;
    const orig = document.startViewTransition && document.startViewTransition.bind(document);
    if (orig) document.startViewTransition = function (cb) { window.__vt++; return orig(cb); };
  });
  let opened = false;
  for (let y = 300; y < 800 && !opened; y += 60) {
    await p.mouse.click(700, y); await p.waitForTimeout(1400);
    opened = await isOpen(p);
  }
  await p.waitForTimeout(1500);
  const afterOpen = await p.evaluate(() => ({
    transitions: window.__vt,
    open: !!document.querySelector('.bf-over.open'),
    strandedNames: [...document.querySelectorAll('[style*="view-transition-name"]')]
      .filter(e => e.style.viewTransitionName).length,
    stageSrc: (document.getElementById('bf-oimg').getAttribute('src') || '').slice(-28),
  }));
  console.log('  open  ->', JSON.stringify(afterOpen));

  await p.click('.bf-oclose'); await p.waitForTimeout(1600);
  console.log('  close ->', JSON.stringify(await p.evaluate(() => ({
    transitions: window.__vt,
    open: !!document.querySelector('.bf-over.open'),
    strandedNames: [...document.querySelectorAll('[style*="view-transition-name"]')]
      .filter(e => e.style.viewTransitionName).length,
  }))));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
