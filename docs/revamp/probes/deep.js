const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const isOpen = p => p.evaluate(() => !!document.querySelector('.bf-over.open'));
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 860 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));

  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1800);
  for (let y = 300; y < 800; y++) { y += 59; await p.mouse.click(700, y); await p.waitForTimeout(1400); if (await isOpen(p)) break; }
  const hash = await p.evaluate(() => location.hash);
  const title = await p.evaluate(() => document.getElementById('bf-otitle').textContent);
  console.log('  opened  -> hash=' + hash + '  title=' + title);

  await p.reload({ waitUntil: 'networkidle' });
  await p.waitForTimeout(3000);
  console.log('  reload  -> open=' + await isOpen(p) +
              '  title=' + await p.evaluate(() => document.getElementById('bf-otitle').textContent) +
              '  frames=' + await p.evaluate(() => document.querySelectorAll('#bf-ostrip img').length));

  await p.goBack({ waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1500);
  console.log('  back    -> open=' + await isOpen(p) + ' hash=' + JSON.stringify(await p.evaluate(() => location.hash)));

  // close button strips the hash
  await p.goto('http://127.0.0.1:5055/birds', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1600);
  for (let y = 300; y < 800; y++) { y += 59; await p.mouse.click(700, y); await p.waitForTimeout(1300); if (await isOpen(p)) break; }
  await p.click('.bf-oclose'); await p.waitForTimeout(1200);
  console.log('  close   -> open=' + await isOpen(p) + ' hash=' + JSON.stringify(await p.evaluate(() => location.hash)));

  // a family deep link
  await p.goto('http://127.0.0.1:5055/birds?family=Pigeons+%26+Doves#family/pigeons-doves', { waitUntil: 'networkidle' });
  await p.waitForTimeout(3000);
  console.log('  family link -> open=' + await isOpen(p) +
              '  title=' + await p.evaluate(() => document.getElementById('bf-otitle').textContent));
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
