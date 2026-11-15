const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Bird detail overlay speed, phone profile (DETAIL_SPEED_PLAN.md).
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const slug of ['barred-owl', 'red-tailed-hawk', 'blue-jay']) {
    const c = await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true });
    const p = await c.newPage(); const cdp = await c.newCDPSession(p);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 60, downloadThroughput: 12e6 / 8, uploadThroughput: 3e6 / 8 });
    await p.goto(S + '/birds', { waitUntil: 'load', timeout: 120000 }); await p.waitForTimeout(1500);
    const ev = {}; let t0 = 0; let stripKB = 0, stripN = 0, stageKB = 0;
    p.on('requestfinished', async r => { const u = r.url(), at = Date.now() - t0; const s = await r.sizes().catch(() => ({ responseBodySize: 0 }));
      if (u.includes('/birds/species/' + slug + '.json')) ev.json = at;
      if (u.includes('/birds/thumbs/') && t0) { stripN++; stripKB += s.responseBodySize / 1024; ev.lastThumb = at; }
      if (u.includes('/birds/images/') && t0) { stageKB += s.responseBodySize / 1024; ev.stage = ev.stage || at; } });
    t0 = Date.now();
    await p.evaluate(s => { location.hash = '#bird/' + s; }, slug);
    await p.waitForFunction(() => { const i = document.getElementById('bf-oimg'); return i && i.complete && i.naturalWidth && !/thumbs/.test(i.src) && !document.querySelector('.bf-stage.busy, #bf-oimg.loading'); }, null, { timeout: 60000 }).catch(() => {});
    ev.stageShown = Date.now() - t0;
    await p.waitForTimeout(4000);
    console.log(slug, JSON.stringify({ ...ev, stripThumbs: stripN, stripKB: Math.round(stripKB), stageKB: Math.round(stageKB) }));
    await c.close();
  }
  await b.close();
})();
