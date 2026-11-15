const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Which thumbnails load after a detail open, and what the strip and stage do meanwhile.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const SLUG = process.env.SLUG || 'red-tailed-hawk';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true });
  const p = await c.newPage(); const cdp = await c.newCDPSession(p);
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 60, downloadThroughput: 12e6 / 8, uploadThroughput: 3e6 / 8 });
  await p.goto(S + '/birds', { waitUntil: 'load', timeout: 120000 }); await p.waitForTimeout(1500);
  let n = 0; p.on('request', r => { if (/\/birds\/thumbs\//.test(r.url())) n++; });
  p.on('console', m => { if (m.type() === 'error') console.log('console:', m.text()); });
  await p.evaluate(() => { location.hash = '#bird/' + arguments[0]; }, SLUG).catch(() => {});
  await p.evaluate(s => { location.hash = '#bird/' + s; }, SLUG);
  for (let t = 0; t < 4; t++) {
    await p.waitForTimeout(1000);
    console.log((t + 1) + 's', n, JSON.stringify(await p.evaluate(() => { const s = document.getElementById('bf-ostrip'); const i = document.getElementById('bf-oimg');
      const on = s.querySelector('img.on');
      return { sl: Math.round(s.scrollLeft), rendered: s.querySelectorAll('img').length, src: s.querySelectorAll('img[src]').length, on: on && +on.dataset.i,
        stage: (i.getAttribute('src') || '').split('/').slice(-2).join('/'), cls: i.className, busy: i.parentNode.className }; })));
  }
  await p.evaluate(() => { const s = document.getElementById('bf-ostrip'); s.scrollLeft = 0; });
  await p.waitForTimeout(1500);
  console.log('after scroll to start', JSON.stringify(await p.evaluate(() => { const s = document.getElementById('bf-ostrip');
    const vis = [...s.querySelectorAll('img')].filter(i => i.offsetLeft < s.clientWidth);
    return { src: s.querySelectorAll('img[src]').length, visibleLoaded: vis.filter(i => i.getAttribute('src')).length, visible: vis.length }; })));
  await p.evaluate(() => { const s = document.getElementById('bf-ostrip'); s.scrollLeft = s.scrollWidth; });
  await p.waitForTimeout(1500);
  console.log('after scroll to end', JSON.stringify(await p.evaluate(() => { const s = document.getElementById('bf-ostrip');
    return { rendered: s.querySelectorAll('img').length, src: s.querySelectorAll('img[src]').length }; })));
  await b.close();
})();
