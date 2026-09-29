const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 100)));
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2400);
  const t = await p.evaluate(() => {
    const el = [...document.querySelectorAll('.bf-tile')].find(x => {
      const r = x.getBoundingClientRect();
      return r.top > 300 && r.left > 200 && r.right < 1200;
    });
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), name: el._t.name };
  });
  await p.mouse.move(t.x, t.y); await p.waitForTimeout(700);
  console.log('  hovering ' + t.name + ' ->', JSON.stringify(await p.evaluate(() => {
    const e = document.getElementById('bf-echo');
    return { on: e.classList.contains('on'), name: e.querySelector('b').textContent,
             meta: e.querySelector('i').textContent.trim(),
             blend: getComputedStyle(e).mixBlendMode, opacity: getComputedStyle(e).opacity };
  })));
  await p.screenshot({ path: process.env.SP + '/echo.png' });
  // leaving the field clears it
  await p.mouse.move(t.x, 40); await p.waitForTimeout(600);
  console.log('  after leaving ->', await p.evaluate(() => document.getElementById('bf-echo').classList.contains('on')));
  // dragging must not leave it stuck on
  await p.mouse.move(700, 500); await p.mouse.down();
  for (let i = 1; i <= 8; i++) await p.mouse.move(700 - i * 40, 500 - i * 20);
  await p.mouse.up(); await p.waitForTimeout(500);
  console.log('  after a drag ->', await p.evaluate(() => document.getElementById('bf-echo').classList.contains('on')));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
