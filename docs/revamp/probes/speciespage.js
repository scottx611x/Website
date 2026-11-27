const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
// Species page weight and load time, phone profile (DETAIL_SPEED_PLAN.md phase 4).
const S = process.env.PROBE_SERVER || SRV;
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const slug of (process.env.SLUGS || 'barred-owl,red-tailed-hawk').split(',')) {
    const c = await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true });
    const p = await c.newPage(); const cdp = await c.newCDPSession(p);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 60, downloadThroughput: 12e6 / 8, uploadThroughput: 3e6 / 8 });
    const got = [];
    p.on('request', r => { if (process.env.WHO && /\/birds\/images\//.test(r.url())) { const f = r.frame(); console.log('  img by', r.resourceType(), r.url().split('/').pop(), JSON.stringify((r.headers()['referer']||'').slice(-30))); } });
    p.on('requestfinished', async r => { const s = await r.sizes().catch(() => ({ responseBodySize: 0 })); got.push([r.url(), s.responseBodySize, r.resourceType()]); });
    const t0 = Date.now();
    await p.goto(S + '/birds/species/' + slug, { waitUntil: 'load', timeout: 120000 });
    const load = Date.now() - t0;
    await p.waitForTimeout(2000);
    const by = {}; let tot = 0;
    for (const [u, n, t] of got) { const k = t + ':' + (u.match(/\/birds\/(images|thumbs\/micro|thumbs|sounds)\//) || [, 'other'])[1]; by[k] = (by[k] || 0) + n; tot += n; }
    const big = got.filter(g => g[1] > 150000).map(g => g[0].split('/').slice(-2).join('/') + ' ' + Math.round(g[1] / 1024) + 'KB');
    console.log(slug, JSON.stringify({ load, totalKB: Math.round(tot / 1024), byKB: Object.fromEntries(Object.entries(by).map(([k, v]) => [k, Math.round(v / 1024)])), big }));
    await c.close();
  }
  await b.close();
})();
