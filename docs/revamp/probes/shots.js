// Screenshot every main page at phone and desktop widths, for before/after
// comparisons of a visual change.
//   OUT=dir docs/revamp/probes/run.sh shots
//   PAGES="/,/projects" OUT=dir docs/revamp/probes/run.sh shots
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.env.OUT || '/tmp/shots';
const PAGES = (process.env.PAGES || '/,/birds,/birds/live,/birds/stats,/birds/map,/photography,/projects,/nope-404').split(',');
const SIZES = { phone: [412, 915], desk: [1440, 900] };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ executablePath: EXE });
  for (const [tag, [w, h]] of Object.entries(SIZES)) {
    const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: w < 900, hasTouch: w < 900, deviceScaleFactor: 1, reducedMotion: 'reduce' });
    for (const path of PAGES) {
      const p = await c.newPage();
      const errs = []; p.on('pageerror', e => errs.push(e.message));
      try { await p.goto(BASE + path, { waitUntil: 'networkidle', timeout: 30000 }); } catch (e) { errs.push('goto: ' + e.message); }
      await p.waitForTimeout(1200);
      const name = (path.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'home') + '-' + tag + '.png';
      await p.screenshot({ path: OUT + '/' + name, fullPage: false });
      console.log(name, errs.length ? 'ERR ' + errs.join(' | ') : 'ok');
      await p.close();
    }
    await c.close();
  }
  await b.close();
})();
