// /birds/live?stage=1 — the stage (docs/revamp/LIVE_STAGE_PLAN.md).
//   docs/revamp/probes/run.sh livestage [outdir]
// Layout, per viewport: the stage is exactly one viewport tall and starts at
// the top; the name is poster-sized and at most two lines; no x-scroll; no
// errors. Each bird is put on stage by rewriting the page's embedded data
// (and live.json, so the first poll changes nothing). Contrast: the text is
// hidden, the backdrop behind each text box is sampled, and paper text over
// its 90th-percentile luminance must reach 4.5:1.
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const {PNG} = require(process.env.SP + '/node_modules/pngjs');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const OUT = process.argv[2] || '/tmp';
const BIRDS = [
  { name: 'Carolina Wren' }, { name: 'White-breasted Nuthatch' }, { name: 'Blue Jay' },
  { name: 'Black-throated Green Warbler', ghost: true },
];
const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };

function rewrite(d, bird) {
  const r = d.recent.find(x => x.audio && (x.conf || 0) >= 0.75) || d.recent.find(x => x.audio) || d.recent[0];
  r.display = r.common = bird.name; r.new = false;
  if (bird.ghost) { r.photo = null; r.shot = false; d.species = d.species.filter(s => s.display !== bird.name); }
  else {
    const sp = d.species.find(s => s.display === bird.name);
    r.photo = sp ? sp.photo : r.photo; r.fam = sp ? sp.fam : r.fam; r.shot = true;
  }
  return d;
}

async function one(b, w, h, mobile, bird, shotName, noon) {
  const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1 });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  let data = null;
  await p.route(u => u.pathname === '/birds/live' && u.search.includes('stage=1'), async route => {
    const res = await route.fetch(); let html = await res.text();
    html = html.replace(/(<script id="lv-data" type="application\/json">)([\s\S]*?)(<\/script>)/, (m, a, j, z) => {
      data = rewrite(JSON.parse(j), bird);
      return a + JSON.stringify(data).replace(/</g, '\\u003c') + z;
    });
    await route.fulfill({ response: res, body: html, headers: Object.assign({}, res.headers(), { 'content-length': String(Buffer.byteLength(html)) }) });
  });
  await p.route(u => u.pathname === '/birds/live.json', route => route.fulfill({ json: data }));
  // Daytime pass: the night state dims the photo, which would flatter the
  // contrast. Noon on the station's own day (so nothing reads as stale).
  if (noon) await p.clock.setFixedTime(noon);
  await p.goto(BASE + '/birds/live?stage=1', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);   // photo settle + word animation
  const m = await p.evaluate(() => {
    const st = document.getElementById('lv-stage').getBoundingClientRect();
    const nm = document.querySelector('#lv-hero .lv-nm');
    const cs = getComputedStyle(nm);
    const box = s => { const e = document.querySelector(s); if (!e) return null;
      // the text's own extent, not its block (a block spans the whole stage)
      const rg = document.createRange(); rg.selectNodeContents(e); const r = rg.getBoundingClientRect();
      const m = getComputedStyle(e).color.match(/[\d.]+/g).map(Number);
      return { s, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), rgb: m.slice(0, 3), a: m[3] == null ? 1 : m[3] }; };
    const reel = document.getElementById('lv-wall').getBoundingClientRect();
    const voice = document.getElementById('lv-player').getBoundingClientRect();
    const body = document.querySelector('#lv-hero .lv-body').getBoundingClientRect();
    const top = document.querySelector('.lv-sttop').getBoundingClientRect();
    return {
      stageTop: Math.round(st.top + scrollY), stageH: Math.round(st.height), vh: innerHeight,
      nameText: nm.textContent.trim().replace(/\s+/g, ' '), namePx: parseFloat(cs.fontSize),
      nameLines: Math.round(nm.getBoundingClientRect().height / parseFloat(cs.lineHeight)),
      ghostBackdrop: !!document.querySelector('#lv-hero .lv-phspec'),
      silhouette: !!document.querySelector('#lv-hero .feather'),
      overlaps: { bodyOverVoice: body.bottom > voice.top + 1, voiceOverReel: voice.bottom > reel.top + 1, bodyUnderTop: body.top < top.bottom },
      reelFrames: document.querySelectorAll('#lv-wall .lv-chip').length,
      xScroll: document.documentElement.scrollWidth > innerWidth,
      boxes: ['#lv-hero .lv-nm', '#lv-hero .lv-when', '#lv-hero .lv-fact', '#lv-upd'].map(box).filter(Boolean),
    };
  });
  await p.screenshot({ path: `${OUT}/${shotName}.png` });
  // contrast: hide the text, sample what is behind it
  await p.addStyleTag({ content: '#lv-hero .lv-body, .lv-sttop{visibility:hidden !important}' });
  await p.waitForTimeout(150);
  const img = PNG.sync.read(await p.screenshot());
  m.contrast = {};
  for (const bx of m.boxes) {
    const Ls = [];
    for (let y = Math.max(0, bx.y); y < Math.min(bx.y + bx.h, img.height); y += 2)
      for (let x = Math.max(0, bx.x); x < Math.min(bx.x + bx.w, img.width); x += 2) {
        const i = (img.width * y + x) << 2;
        Ls.push(0.2126 * lin(img.data[i]) + 0.7152 * lin(img.data[i + 1]) + 0.0722 * lin(img.data[i + 2]));
      }
    Ls.sort((a, b) => a - b);
    const p90 = Ls[Math.floor(Ls.length * 0.9)] || 0;
    // the element's own text colour, its alpha blended over that backdrop
    const Lc = 0.2126 * lin(bx.rgb[0]) + 0.7152 * lin(bx.rgb[1]) + 0.0722 * lin(bx.rgb[2]);
    const Lt = bx.a * Lc + (1 - bx.a) * p90;
    m.contrast[bx.s.replace('#lv-hero ', '')] = +((Math.max(Lt, p90) + 0.05) / (Math.min(Lt, p90) + 0.05)).toFixed(2);
  }
  delete m.boxes;
  await c.close();
  return Object.assign({ bird: bird.name, errors: errs }, m);
}

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const out = [];
  const gen = await (await fetch(BASE + '/birds/live.json')).json();
  const noon = new Date(gen.generated); noon.setHours(12, 0, 0, 0);
  for (const day of [false, true])
    for (const [w, h, mob] of [[1440, 900, false], [412, 860, true]])
      for (const bird of BIRDS)
        out.push(Object.assign({ w, day }, await one(b, w, h, mob, bird,
          `stage-${w}-${day ? 'day' : 'now'}-${bird.name.split(' ')[0].toLowerCase()}`, day ? noon : null)));
  for (const o of out) {
    const fails = [];
    if (o.nameText !== o.bird) fails.push('stage shows ' + o.nameText);
    if (o.stageTop !== 0) fails.push('stageTop ' + o.stageTop);
    if (o.stageH !== o.vh) fails.push('stageH ' + o.stageH + '≠' + o.vh);
    if (o.namePx < (o.w > 600 ? 96 : 44)) fails.push('namePx ' + o.namePx);
    if (o.nameLines > 2) fails.push('nameLines ' + o.nameLines);
    if (o.bird.startsWith('Black') && (!o.ghostBackdrop || o.silhouette)) fails.push('ghost backdrop');
    Object.entries(o.overlaps).forEach(([k, v]) => { if (v) fails.push(k); });
    Object.entries(o.contrast).forEach(([k, v]) => { if (v < 4.5) fails.push('contrast ' + k + ' ' + v); });
    if (o.xScroll) fails.push('xScroll');
    if (o.errors.length) fails.push('errors ' + o.errors.join('; '));
    o.ok = !fails.length; o.fails = fails;
  }
  console.log(JSON.stringify(out.map(o => ({ w: o.w, day: o.day, bird: o.bird, shown: o.nameText, ok: o.ok, fails: o.fails, namePx: o.namePx, lines: o.nameLines, contrast: o.contrast, reel: o.reelFrames })), null, 1));
  await b.close();
})();
