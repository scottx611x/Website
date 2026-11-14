// /birds/live — the stage's voiceprint (LIVE_STAGE_PLAN.md phase 3).
//   docs/revamp/probes/run.sh livevoice [outdir]
// While a clip plays the needle stays put and the spectrogram moves under
// it; pausing freezes it; a click on the print seeks to the point under the
// cursor; with no photo the full-screen spectrogram moves too; with reduced
// motion the needle moves instead and nothing translates.
// The headless shell cannot decode AAC, so clips are served as a 6s WAV.
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
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(Math.sin(i / rate * 2 * Math.PI * 3000) * 3000), 44 + i * 2);
  return b;
}
const WAV = wav(6);

const sample = p => p.evaluate(() => {
  const img = document.querySelector('#lv-spec img'), nd = document.getElementById('lv-needle');
  const ph = document.querySelector('#lv-hero .lv-phspec');
  return {
    needleX: Math.round(nd.getBoundingClientRect().left),
    imgShift: getComputedStyle(img).translate,
    bgShift: ph ? getComputedStyle(ph).translate : null,
    t: window.__audio ? +window.__audio.currentTime.toFixed(3) : null,
    voiced: document.getElementById('lv-player').classList.contains('voiced'),
  };
});

async function run(b, reduced) {
  const c = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  await c.addCookies([{ name: 'curate', value: '0', url: BASE }]);
  const p = await c.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.addInitScript(() => {
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () { window.__audio = this; return play.apply(this, arguments); };
  });
  // byte ranges, or Chrome treats the clip as unseekable and every seek is 0
  await p.route(u => /\/sounds\/clips\/.*\.m4a$/.test(u.pathname), r => {
    const m = /bytes=(\d+)-(\d*)/.exec(r.request().headers()['range'] || '');
    if (!m) return r.fulfill({ body: WAV, contentType: 'audio/wav', headers: { 'accept-ranges': 'bytes' } });
    const a = +m[1], z = m[2] ? Math.min(+m[2], WAV.length - 1) : WAV.length - 1;
    return r.fulfill({ status: 206, body: WAV.subarray(a, z + 1), contentType: 'audio/wav',
      headers: { 'accept-ranges': 'bytes', 'content-range': `bytes ${a}-${z}/${WAV.length}` } });
  });
  await p.goto(BASE + '/birds/live', { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);
  await p.click('#lv-playbtn');
  await p.waitForFunction(() => window.__audio && window.__audio.currentTime > 0.3, null, { timeout: 8000 }).catch(() => {});
  const play = [];
  for (let i = 0; i < 6; i++) { play.push(await sample(p)); await p.waitForTimeout(250); }
  if (!reduced) await p.screenshot({ path: (process.argv[2] || '/tmp') + '/livevoice-playing.png' });
  await p.click('#lv-playbtn');     // pause
  await p.waitForTimeout(300);
  const paused = [await sample(p)]; await p.waitForTimeout(600); paused.push(await sample(p));
  // click 10% of the print right of the needle: expect +10% of the clip
  const spec = await p.$eval('#lv-spec', e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y + r.height / 2, w: r.width }; });
  const before = await p.evaluate(() => ({ t: window.__audio.currentTime, d: window.__audio.duration }));
  const clickX = reduced ? spec.x + spec.w * 0.5 : spec.x + spec.w * 0.48;
  await p.mouse.click(clickX, spec.y);
  await p.waitForTimeout(40);
  const after = await p.evaluate(() => window.__audio.currentTime);
  const want = reduced ? 0.5 * before.d : (before.t / before.d + 0.10) * before.d;
  await c.close();
  const uniq = a => new Set(a).size;
  return {
    reduced, play, paused, seek: { want: +want.toFixed(3), got: +after.toFixed(3) },
    needleFixed: uniq(play.map(s => s.needleX)) === 1,
    printMoves: uniq(play.map(s => s.imgShift)) > 3,
    backdropMoves: play[0].bgShift == null ? 'no ghost backdrop on stage' : uniq(play.map(s => s.bgShift)) > 3,
    pauseFreezes: paused[0].imgShift === paused[1].imgShift && paused[0].t === paused[1].t,
    seekWithin100ms: Math.abs(after - want) <= 0.1,
    errors: errs,
  };
}

(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const motion = await run(b, false), reduced = await run(b, true);
  const ok = {
    needleFixed: motion.needleFixed, printMoves: motion.printMoves, backdropMoves: motion.backdropMoves,
    pauseFreezes: motion.pauseFreezes, seek: motion.seekWithin100ms,
    reducedNeedleMoves: !reduced.needleFixed, reducedNothingTranslates: reduced.play.every(s => s.imgShift === 'none'),
    reducedSeek: reduced.seekWithin100ms, noErrors: !motion.errors.length && !reduced.errors.length,
  };
  console.log(JSON.stringify({ ok, motion, reduced }, null, 1));
  await b.close();
})();
