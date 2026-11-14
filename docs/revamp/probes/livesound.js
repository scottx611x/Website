// /birds/live?sound=1 — "sound on" (LIVE_STAGE_PLAN.md phase 5, show first).
//   docs/revamp/probes/run.sh livesound
// With the switch on, each of three injected arrivals plays its own clip
// once, in order, and none is cut off by the next. With it off, an arrival
// plays nothing. Clips are served as a seekable 2s WAV (no AAC headless).
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const BASE = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
function wav(seconds) {
  const rate = 8000, n = rate * seconds, b = Buffer.alloc(44 + n * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n * 2, 4); b.write('WAVE', 8); b.write('fmt ', 12);
  b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(rate, 24);
  b.writeUInt32LE(rate * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(n * 2, 40);
  return b;
}
const WAV = wav(2);

async function run(b, on) {
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.addInitScript(() => {
    window.__log = [];
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      if (!this.__hooked) {
        this.__hooked = true;
        this.addEventListener('ended', () => window.__log.push({ ev: 'ended', src: this.src.split('/').pop(), at: Date.now() }));
        this.addEventListener('pause', () => { if (!this.ended) window.__log.push({ ev: 'pause', src: this.src.split('/').pop(), t: this.currentTime, at: Date.now() }); });
      }
      window.__log.push({ ev: 'play', src: (this.src || '').split('/').pop(), at: Date.now() });
      return play.apply(this, arguments);
    };
  });
  await p.route(u => /\/sounds\/clips\/.*\.m4a$/.test(u.pathname), r => {
    const m = /bytes=(\d+)-(\d*)/.exec(r.request().headers()['range'] || '');
    if (!m) return r.fulfill({ body: WAV, contentType: 'audio/wav', headers: { 'accept-ranges': 'bytes' } });
    const a = +m[1], z = m[2] ? Math.min(+m[2], WAV.length - 1) : WAV.length - 1;
    return r.fulfill({ status: 206, body: WAV.subarray(a, z + 1), contentType: 'audio/wav',
      headers: { 'accept-ranges': 'bytes', 'content-range': `bytes ${a}-${z}/${WAV.length}` } });
  });
  let inject = false, injected = [];
  await p.route(u => u.pathname === '/birds/live.json', async route => {
    const res = await route.fetch(); const d = await res.json();
    if (inject) {
      const seen = new Set([d.recent[0].display, (d.recent.find(r => r.audio && r.conf >= 0.75) || {}).display]);
      const src = d.recent.filter(r => r.audio && r.conf >= 0.8 && !seen.has(r.display) && seen.add(r.display)).slice(0, 3);
      const now = Date.now();
      injected = src.map((r, i) => Object.assign({}, r, { t: new Date(now - (30 - 10 * i) * 1000).toISOString(), audio: `probe_${i}.m4a` }));
      d.recent = injected.slice().reverse().concat(d.recent); d.dayrecs = injected.slice().reverse().concat(d.dayrecs);
      d.generated = new Date().toISOString();
    }
    await route.fulfill({ response: res, json: d });
  });
  await p.goto(BASE + '/birds/live?sound=1', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2000);
  if (on) await p.click('#lv-sound');
  const label = await p.$eval('#lv-sound', e => e.textContent.trim());
  inject = true;
  await p.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await p.waitForTimeout(24000);
  const log = await p.evaluate(() => window.__log);
  await c.close();
  const plays = log.filter(e => e.ev === 'play').map(e => e.src);
  const cut = log.filter(e => e.ev === 'pause' && /^probe_/.test(e.src));
  return { on, label, injected: injected.map(r => r.audio), plays, cutOff: cut, errors: errs };
}

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const on = await run(b, true), off = await run(b, false);
  const ok = {
    switchShowsOn: on.label === '♪ sound on',
    eachArrivalPlaysOnce: JSON.stringify(on.plays) === JSON.stringify(on.injected),
    noneCutOff: on.cutOff.length === 0,
    offPlaysNothing: off.plays.length === 0,
    noErrors: !on.errors.length && !off.errors.length,
  };
  console.log(JSON.stringify({ ok, on, off }, null, 1));
  await b.close();
})();
