const {chromium} = require(process.env.SP + '/node_modules/playwright-core');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell';
// Who requests the full web copies on a species page (CDP initiator).
const S = process.env.PROBE_SERVER || 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const c = await b.newContext({ viewport: { width: 412, height: 880 }, deviceScaleFactor: 2.6, isMobile: true });
  const p = await c.newPage(); const cdp = await c.newCDPSession(p);
  await cdp.send('Network.enable');
  cdp.on('Network.requestWillBeSent', e => { if (/\/birds\/images\//.test(e.request.url)) {
    const st = e.initiator.stack && e.initiator.stack.callFrames[0];
    console.log(e.request.url.split('/').pop(), e.initiator.type, e.initiator.url ? e.initiator.url.split('/').pop() : '', e.initiator.lineNumber || '', st ? (st.functionName + ' ' + st.url.split('/').pop() + ':' + st.lineNumber) : ''); } });
  await p.goto(S + '/birds/species/' + (process.env.SLUG || 'barred-owl'), { waitUntil: 'load', timeout: 120000 });
  await p.waitForTimeout(2000);
  console.log(JSON.stringify(await p.evaluate(() => [...document.querySelectorAll('img')].filter(i => /\/birds\/images\//.test(i.currentSrc || i.src)).slice(0, 4).map(i => ({ src: i.getAttribute('src').split('/').pop(), srcset: (i.getAttribute('srcset') || '').slice(0, 200), cls: i.className, parent: i.parentNode.className })))));
  await b.close();
})();
