const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
/* Walks every text node on a page and reports anything under 3:1 against its
   own painted backdrop. Catches an accent that works on one ground and
   vanishes on the other — the exact failure mode of a two-ground palette. */
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  for (const url of ['/', '/birds?view=grid', '/birds/stats', '/birds/live', '/photography', '/projects']) {
    const p = await c.newPage();
    await p.goto('http://127.0.0.1:5055' + url, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2200);
    const bad = await p.evaluate(() => {
      const L = c => { const m = (c||'').match(/[\d.]+/g); if (!m) return null;
        const f = m.slice(0,3).map(v => { v/=255; return v<=.03928 ? v/12.92 : Math.pow((v+.055)/1.055,2.4); });
        return .2126*f[0] + .7152*f[1] + .0722*f[2]; };
      const ratio = (a,b) => { const x=L(a), y=L(b); if (x===null||y===null) return 99;
        const [h,l] = x>y?[x,y]:[y,x]; return (h+.05)/(l+.05); };
      const backdrop = el => { let n = el;
        while (n && n !== document.documentElement) { const bg = getComputedStyle(n).backgroundColor;
          if (bg && !/rgba\(0, 0, 0, 0\)|transparent/.test(bg)) return bg; n = n.parentElement; }
        return getComputedStyle(document.body).backgroundColor; };
      const out = [];
      document.querySelectorAll('a,button,span,p,h1,h2,h3,b,i,strong,li,dt,dd,label').forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 4 || r.height < 4) return;
        if (!e.textContent.trim()) return;
        const s = getComputedStyle(e);
        if (s.visibility === 'hidden' || +s.opacity < 0.15) return;
        // only leaf-ish text, else parents double-count
        if ([...e.children].some(k => k.textContent.trim().length > 2)) return;
        const cr = ratio(s.color, backdrop(e));
        if (cr < 3) out.push({ t: e.textContent.trim().slice(0, 32), cls: (e.className||'').toString().slice(0,26),
                               fg: s.color, bg: backdrop(e), cr: +cr.toFixed(2) });
      });
      const seen = new Set();
      return out.filter(x => { const k = x.cls + x.fg + x.bg; if (seen.has(k)) return false; seen.add(k); return true; });
    });
    console.log('  ' + url.padEnd(18) + (bad.length ? bad.length + ' low-contrast' : 'clean'));
    bad.slice(0, 6).forEach(x => console.log('      ' + String(x.cr).padStart(5) + '  ' + x.cls.padEnd(28) + ' "' + x.t + '"'));
    await p.close();
  }
  await b.close();
})();
