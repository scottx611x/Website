// The phone menu panel is paper; every link in it must read as ink on every
// page (home and the Live stage paint their nav links cream for the photo).
const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const SRV = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
const fs = require('fs');
const dir = process.env.HOME + '/Library/Caches/ms-playwright';
const shell = fs.readdirSync(dir).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const EXE = `${dir}/${shell}/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const S = process.env.PROBE_SERVER || SRV;
const lum = c => { const m = c.match(/[\d.]+/g).map(Number); const f = v => (v /= 255) <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
  return .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]); };
const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  let bad = 0;
  for (const path of ['/', '/birds', '/birds/live', '/birds/stats', '/photography', '/projects']) {
    const c = await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const p = await c.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 90)));
    await p.goto(S + path, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1500);
    await p.tap('#navBurger'); await p.waitForTimeout(400);
    const r = await p.evaluate(() => { const nav = document.getElementById('navLinks'); const bg = getComputedStyle(nav).backgroundColor;
      return { bg, vis: getComputedStyle(nav).visibility, links: [...nav.querySelectorAll('a')].map(a => [a.textContent.trim(), getComputedStyle(a).color]) }; });
    // The link must be what a tap lands on, and the tap must navigate.
    const hit = await p.evaluate(() => { const a = document.querySelector('#navLinks a[href="/projects"]'); const r = a.getBoundingClientRect();
      const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!top && a.contains(top); });
    let went = false;
    if (hit) { await Promise.all([p.waitForURL('**/projects', { timeout: 8000 }).then(() => went = true).catch(() => {}), p.tap('#navLinks a[href="/projects"]')]); }
    const worst = Math.min(...r.links.map(([, col]) => ratio(col, r.bg)));
    const ok = hit && went && r.vis === 'visible' && worst >= 4.5 && !errs.length; if (!ok) bad++;
    console.log((ok ? 'ok  ' : 'BAD ') + path.padEnd(14) + ' worst contrast ' + worst.toFixed(1) + ' tapTarget ' + hit + ' navigates ' + went + ' ' + errs.join(' | '));
    if (false) await p.screenshot({ path: process.env.SP + '/navmenu_home.png' });
    await c.close();
  }
  await b.close(); process.exit(bad ? 1 : 0);
})();
