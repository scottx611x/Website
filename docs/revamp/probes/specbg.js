const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Species page: the spectrogram paints when scrolled to; the player still plays.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const p = await (await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2.6, isMobile: true })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(S + '/birds/species/barred-owl', { waitUntil: 'load' });
  const before = await p.evaluate(() => { const s = document.querySelector('.sp-spec'); return s && s.style.backgroundImage; });
  await p.evaluate(() => document.getElementById('sp-player').scrollIntoView());
  await p.waitForTimeout(800);
  const after = await p.evaluate(() => { const s = document.querySelector('.sp-spec'); return s && s.style.backgroundImage.slice(0, 60); });
  await p.click('#sp-play'); await p.waitForTimeout(2500);
  const playing = await p.evaluate(() => document.getElementById('sp-play').innerHTML);
  console.log(JSON.stringify({ before, after, playBtn: playing, errs }));
  await b.close();
})();
