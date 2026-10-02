const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
const read = p => p.evaluate(() => {
  const r = document.getElementById('chorus');
  const sky = document.getElementById('ch-sky');
  const on = document.querySelector('.ch-mark.on');
  return {
    marks: document.querySelectorAll('.ch-mark').length,
    named: (document.querySelector('.ch-name b') || {}).textContent || null,
    meta: (document.querySelector('.ch-name i') || {}).textContent || null,
    onMark: on ? on.dataset.i : null,
    day: sky.style.getPropertyValue('--day').trim(),
    sun: sky.style.getPropertyValue('--sun').trim(),
    audioSrc: (document.getElementById('ch-audio').getAttribute('src') || '').split('/').pop(),
    spec: (document.getElementById('ch-spec').getAttribute('src') || '').split('/').pop(),
    playing: document.getElementById('chorus').classList.contains('playing'),
    h: Math.round(r.getBoundingClientRect().height),
  };
});
(async () => {
  // autoplay is blocked by default in headless, which made "Play the day" look
// broken when it was only unable to start a sound
  const b = await chromium.launch({ executablePath: EXE,
    args: ['--autoplay-policy=no-user-gesture-required'] });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 110)));
  await p.goto('http://127.0.0.1:5055/birds/live', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  console.log('  on load   ', JSON.stringify(await read(p)));

  const box = await (await p.$('#chorus')).boundingBox();
  const cy = Math.round(box.y + box.height * 0.75);
  // drag back through the morning
  for (const [label, dx] of [['drag right 500', 500], ['drag right 500 more', 500], ['drag left 800', -800]]) {
    await p.mouse.move(box.x + box.width / 2, cy);
    await p.mouse.down();
    const steps = 14;
    for (let i = 1; i <= steps; i++) await p.mouse.move(box.x + box.width / 2 + (dx * i / steps), cy);
    await p.mouse.up();
    await p.waitForTimeout(1200);
    console.log('  ' + label.padEnd(20) + JSON.stringify(await read(p)));
  }
  // "Play the day" must advance on its own and give the wheel back on a drag
  await p.click('#ch-play'); await p.waitForTimeout(1200);
  console.log('  pressed play        ' + JSON.stringify(await read(p)));
  await p.evaluate(() => { const a = document.getElementById('ch-audio');
    a.dispatchEvent(new Event('ended')); });
  await p.waitForTimeout(1400);
  console.log('  after a clip ends   ' + JSON.stringify(await read(p)));
  await p.mouse.move(box.x + 200, cy); await p.mouse.down(); await p.mouse.move(box.x + 260, cy); await p.mouse.up();
  await p.waitForTimeout(600);
  console.log('  drag interrupts     ' + JSON.stringify(await read(p)));

  await p.screenshot({ path: process.env.SP + '/chorus.png', clip: { x: 0, y: Math.max(0, box.y), width: 1440, height: Math.min(560, box.height) } });
  console.log('  errors:', errs.length); errs.forEach(e => console.log('     ! ' + e));
  await b.close();
})();
