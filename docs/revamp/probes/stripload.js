// How long the detail view's filmstrip takes to paint, and what it queues behind.
//   PROBE_SERVER=https://scott-ouellette.com docs/revamp/probes/run.sh stripload
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const BIRD = process.argv[2] || 'eastern-towhee';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const t0 = Date.now(), reqs = new Map();
  p.on('request', r => { reqs.set(r, { url: r.url(), start: Date.now() - t0 }); });
  p.on('requestfinished', r => { const x = reqs.get(r); if (x) x.end = Date.now() - t0; });
  await p.goto(BASE + '/birds#bird/' + BIRD, { waitUntil: 'domcontentloaded' });
  const seen = {};
  while (Date.now() - t0 < 15000) {
    const s = await p.evaluate(() => {
      const im = [...document.querySelectorAll('#bf-ostrip img')];
      const stage = document.querySelector('#bf-over img.bf-photo, #bf-over .bf-stage img');
      return { n: im.length, ld: im.filter(i => i.classList.contains('ld')).length, stage: !!(stage && stage.complete && stage.naturalWidth) };
    });
    if (s.n && !seen.stripBuilt) seen.stripBuilt = Date.now() - t0;
    if (s.stage && !seen.stage) seen.stage = Date.now() - t0;
    if (s.n && s.ld === s.n && !seen.allLoaded) { seen.allLoaded = Date.now() - t0; seen.n = s.n; break; }
    await p.waitForTimeout(100);
  }
  const all = [...reqs.values()];
  const kind = u => /\/thumbs\//.test(u) ? 'thumb' : /\/images\//.test(u) ? 'web' : 'other';
  const by = {};
  for (const r of all) { const k = kind(r.url); by[k] = by[k] || { n: 0, bytesTime: 0 }; by[k].n++; }
  const inflightAtStrip = all.filter(r => r.start <= (seen.stripBuilt || 0) && (!r.end || r.end > seen.stripBuilt)).length;
  const pages = all.filter(r => !/s3\.amazonaws/.test(r.url)).map(r => [r.start, r.end, r.url.replace(/^https?:\/\/[^/]+/, '').slice(0, 60)]);
  const hosts = [...new Set(all.map(r => new URL(r.url).host))];
  console.log(JSON.stringify({ seen, pages, requests: by, inflightAtStrip, hosts,
    slowest: all.filter(r => r.end).sort((a, b) => (b.end - b.start) - (a.end - a.start)).slice(0, 5).map(r => [r.end - r.start, r.url.split('/').slice(-2).join('/')]) }, null, 1));
  await b.close();
})();
