const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addCookies([{ name: 'curate', value: '0', url: 'http://127.0.0.1:5055' }]);
  const p = await c.newPage();
  await p.goto('http://127.0.0.1:5055/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2600);
  console.log(JSON.stringify(await p.evaluate(() => {
    const nav = document.querySelector('.site-nav');
    const links = [...document.querySelectorAll('.site-nav nav a')];
    const cs = getComputedStyle(nav);
    return {
      bodyClass: document.body.className,
      navRect: (r => ({ x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }))(nav.getBoundingClientRect()),
      navOpacity: cs.opacity, navZ: cs.zIndex, navBg: cs.backgroundColor, navPos: cs.position,
      links: links.map(a => {
        const r = a.getBoundingClientRect(), s = getComputedStyle(a);
        return { t: a.textContent.trim(), x: Math.round(r.x), y: Math.round(r.y),
                 color: s.color, opacity: s.opacity, vis: s.visibility };
      }),
      topmostAtLink: (() => { const a = links[0]; const r = a.getBoundingClientRect();
        const e = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
        return e ? e.tagName + '.' + (e.className||'').toString().slice(0,24) : null; })(),
    };
  }), null, 1));
  await b.close();
})();
