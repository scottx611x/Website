/* Categorical palette check: OKLab separation under normal vision and under
 * simulated colour-vision deficiency, plus contrast against the page ground.
 * Colour choice is computable, so it gets computed rather than eyeballed.
 *
 *   node docs/revamp/palcheck.js "#aaa,#bbb,..." "#f4f1e9"
 */
const hex = h => { h = h.replace('#',''); return [0,2,4].map(i => parseInt(h.slice(i,i+2),16)/255); };
const lin = c => c <= 0.04045 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4);
const srgb = c => c <= 0.0031308 ? c*12.92 : 1.055*Math.pow(c,1/2.4)-0.055;

function oklab([r,g,b]) {
  r=lin(r); g=lin(g); b=lin(b);
  const l=Math.cbrt(0.4122214708*r+0.5363325363*g+0.0514459929*b);
  const m=Math.cbrt(0.2119034982*r+0.6806995451*g+0.1073969566*b);
  const s=Math.cbrt(0.0883024619*r+0.2817188376*g+0.6299787005*b);
  return [0.2104542553*l+0.7936177850*m-0.0040720468*s,
          1.9779984951*l-2.4285922050*m+0.4505937099*s,
          0.0259040371*l+0.7827717662*m-0.8086757660*s];
}
const dE = (a,b) => { const A=oklab(a),B=oklab(b);
  return 100*Math.hypot(A[0]-B[0],A[1]-B[1],A[2]-B[2]); };

/* Machado et al. severity-1.0 matrices */
const CVD = {
  deuteranopia: [[0.367,0.861,-0.228],[0.280,0.673,0.047],[-0.012,0.043,0.969]],
  protanopia:   [[0.152,1.053,-0.205],[0.115,0.786,0.099],[-0.004,-0.048,1.052]],
  tritanopia:   [[1.256,-0.077,-0.179],[-0.078,0.931,0.148],[0.005,0.691,0.304]],
};
function sim(rgb, M) {
  const [r,g,b] = rgb.map(lin);
  return M.map(row => srgb(Math.min(1, Math.max(0, row[0]*r+row[1]*g+row[2]*b))));
}
const relLum = ([r,g,b]) => 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b);
const contrast = (a,b) => { const L=[relLum(a),relLum(b)].sort((x,y)=>y-x);
  return (L[0]+0.05)/(L[1]+0.05); };

const cols = (process.argv[2]||'').split(',').map(s=>s.trim()).filter(Boolean);
const ground = hex(process.argv[3] || '#f4f1e9');
let fail = 0, warn = 0;
console.log('  ' + cols.length + ' swatches against ' + (process.argv[3] || '#f4f1e9') + '\n');
for (let i=0;i<cols.length;i++) {
  const c = hex(cols[i]);
  const ct = contrast(c, ground);
  const flag = ct < 3 ? 'LOW-CONTRAST' : '';
  if (flag) warn++;
  console.log('   ' + cols[i].padEnd(9) + '  contrast ' + ct.toFixed(2).padStart(5) + '  ' + flag);
}
console.log('\n  worst pair separation (every pair, not just adjacent):');
for (const [name, M] of [['normal', null], ...Object.entries(CVD)]) {
  let worst = Infinity, pair = '';
  for (let i=0;i<cols.length;i++) for (let j=i+1;j<cols.length;j++) {
    let a = hex(cols[i]), b = hex(cols[j]);
    if (M) { a = sim(a,M); b = sim(b,M); }
    const d = dE(a,b);
    if (d < worst) { worst = d; pair = cols[i]+'/'+cols[j]; }
  }
  const floor = name === 'normal' ? 15 : 8;
  const ok = worst >= floor;
  if (!ok) fail++;
  console.log('   ' + name.padEnd(13) + ' dE ' + worst.toFixed(1).padStart(5) +
    '  (floor ' + floor + ')  ' + (ok ? 'PASS' : 'FAIL') + '  ' + pair);
}
console.log('\n  ' + (fail ? fail + ' FAILURE(S)' : (warn ? 'passes separation; ' + warn + ' low-contrast warning(s)' : 'all checks pass')));
process.exit(fail ? 1 : 0);
