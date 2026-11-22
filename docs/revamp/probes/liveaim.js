// Live stage on a phone: does the whole bird stay on screen? Puts one bird on
// stage per frame id (IDS="a,b,c", ids from that bird's photo pool; BIRD
// names the species) and screenshots each, then reports whether the reel's
// card shows the same frame as the hero, and whether the zoom-to-fit kicked in.
//   IDS=17920375854319161-1,... BIRD="Pileated Woodpecker" OUT=dir docs/revamp/probes/run.sh liveaim
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.env.OUT || '/tmp';
const BIRD = process.env.BIRD || 'Pileated Woodpecker';
const IDS = (process.env.IDS || '').split(',').filter(Boolean);
const W = +(process.env.W || 412), H = +(process.env.H || 915);

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  for (const id of IDS) {
    const c = await b.newContext({ viewport: { width: W, height: H }, isMobile: W < 900, hasTouch: W < 900, deviceScaleFactor: 1 });
    const p = await c.newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message));
    let data = null;
    await p.route(u => u.pathname === '/birds/live', async route => {
      const res = await route.fetch(); let html = await res.text();
      html = html.replace(/(<script id="lv-data" type="application\/json">)([\s\S]*?)(<\/script>)/, (m, a, j, z) => {
        const d = JSON.parse(j);
        const sp = d.species.find(s => s.display === BIRD);
        const url = sp.photos.find(u => u.includes('/' + id + '.')) || sp.photos[0];
        sp.photos = [url]; sp.photo = url;
        const r = d.recent.find(x => x.audio && (x.conf || 0) >= 0.75);
        Object.assign(r, { display: BIRD, common: BIRD, photo: url, fam: sp.fam, shot: true, new: false, t: new Date().toISOString() });
        // the reel lists today's birds from dayrecs: make sure this one is on it
        d.dayrecs.unshift(Object.assign({}, r));
        data = d;
        return a + JSON.stringify(d).replace(/</g, '\\u003c') + z;
      });
      await route.fulfill({ response: res, body: html, headers: Object.assign({}, res.headers(), { 'content-length': String(Buffer.byteLength(html)) }) });
    });
    await p.route(u => u.pathname === '/birds/live.json', route => route.fulfill({ json: data }));
    await p.goto(BASE + '/birds/live', { waitUntil: 'networkidle' });
    await p.waitForTimeout(2500);
    const r = await p.evaluate(() => {
      const els = document.querySelectorAll('#lv-hero .lv-ph'); const el = els[els.length - 1];
      const hero = (el.style.backgroundImage.match(/url\("?([^")]+)"?\)\s*$/) || [])[1] || '';
      const chip = document.querySelector('#lv-wall .lv-chip.on') || document.querySelector('#lv-wall .lv-chip');
      const cimg = chip ? (chip.style.backgroundImage.match(/url\("?([^")]+)"?\)/) || [])[1] : null;
      return { aimed: !!el.dataset.fx, bw: el.dataset.bw || null, fit: el.parentNode.classList.contains('lv-fit'),
               size: el.style.backgroundSize || 'cover', pos: el.style.backgroundPosition,
               chipMatchesHero: !!cimg && cimg.split('/').pop() === hero.split('/').pop() };
    });
    console.log(id, JSON.stringify(r), errs.length ? 'ERRORS ' + errs.join('; ') : '');
    await p.screenshot({ path: OUT + '/aim-' + id + '.png' });
    await c.close();
  }
  await b.close();
})();
