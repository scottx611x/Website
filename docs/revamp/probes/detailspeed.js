const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Bird detail overlay speed, phone profile (DETAIL_SPEED_PLAN.md).
// firstPaint: anything on the stage; stageShown: the full web copy (or a
// playable video). Strip numbers count only the filmstrip's own thumbnails,
// not the field's tiles loading behind the overlay.
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const slug of ['barred-owl', 'red-tailed-hawk', 'blue-jay']) {
    const c = await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true });
    const p = await c.newPage(); const cdp = await c.newCDPSession(p);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 60, downloadThroughput: 12e6 / 8, uploadThroughput: 3e6 / 8 });
    await p.goto(S + '/birds', { waitUntil: 'load', timeout: 120000 }); await p.waitForTimeout(1500);
    const ev = {}; let t0 = 0; const sizes = {};
    p.on('requestfinished', async r => { const u = r.url(), at = Date.now() - t0; const s = await r.sizes().catch(() => ({ responseBodySize: 0 }));
      if (u.includes('/birds/species/' + slug + '.json')) ev.json = at;
      if (/\/birds\/thumbs\//.test(u) && t0) sizes[u] = s.responseBodySize;
      if (u.includes('/birds/images/') && t0) ev.stage = ev.stage || at; });
    t0 = Date.now();
    await p.evaluate(s => { location.hash = '#bird/' + s; }, slug);
    await p.waitForFunction(() => { const i = document.getElementById('bf-oimg'), v = document.getElementById('bf-ovid');
      return (i && !i.hidden && i.getAttribute('src') && i.complete && i.naturalWidth) || (v && !v.hidden && v.readyState >= 2); }, null, { timeout: 60000, polling: 16 }).catch(() => {});
    ev.firstPaint = Date.now() - t0;
    await p.waitForFunction(() => { const i = document.getElementById('bf-oimg'), v = document.getElementById('bf-ovid');
      if (v && !v.hidden) return v.readyState >= 2;
      return i && i.complete && i.naturalWidth && !/thumbs/.test(i.src) && !document.querySelector('.bf-stage.busy, #bf-oimg.loading'); }, null, { timeout: 60000 }).catch(() => {});
    ev.stageShown = Date.now() - t0;
    ev.video = await p.evaluate(() => !document.getElementById('bf-ovid').hidden);
    await p.waitForTimeout(4000);
    const strip = new Set(await p.evaluate(() => [...document.querySelectorAll('#bf-ostrip img[src]')].map(i => i.src)));
    const mine = Object.keys(sizes).filter(u => strip.has(u));
    ev.stripThumbs = mine.length; ev.stripKB = Math.round(mine.reduce((a, u) => a + sizes[u], 0) / 1024);
    ev.otherThumbs = Object.keys(sizes).length - mine.length;
    console.log(slug, JSON.stringify(ev));
    await c.close();
  }
  await b.close();
})();
