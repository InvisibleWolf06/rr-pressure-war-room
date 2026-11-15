// offline check: simulator win probability vs actual result vs the engine's WP model
const fs = require('fs'); const S = JSON.parse(fs.readFileSync(process.argv[2])); S.alpha = +(process.env.ALPHA || 1); S.inn_sd = +(process.env.SD || 0); S.bscale = +(process.env.BS || 1); const NS = +(process.env.NS || 500); const RRSim = require('./web/sim.js');
const wpRows = fs.readFileSync(process.argv[3], 'utf8').trim().split('\n').slice(1).map(l => l.split(','));
const WP = {}; for (const r of wpRows) WP[`${r[0]}|${r[1]}|${r[2]}`] = [+r[3], +r[4]];
const sim = RRSim.make(S); const rows = [];
for (const m of S.matches) {
  if (m.revised) continue;
  m.inns[0].rr = true; m.inns[1].rr = false;           // treat team batting first as "RR" -> p = P(bat-first wins)
  const t1won = m.inns[1].total < m.target - 1 ? 1 : (m.inns[1].total >= m.target ? 0 : 0.5);
  const legalIdx = (inn, ov) => { let l = 0; for (let i = 0; i < inn.b.length; i++) { if (l >= ov * 6) return i; if (inn.b[i][6]) l++; } return null; };
  for (const [inn, ov] of [[1, 0], [1, 10], [2, 0], [2, 10], [2, 15]]) {
    const k = legalIdx(m.inns[inn - 1], ov); if (k == null) continue;
    const r = sim.run(m, inn, k, null, NS, 11);
    const w = WP[`${m.id}|${inn}|${k + 1}`];
    const eng = w ? (inn === 1 ? w[0] : 1 - w[0]) : null;
    rows.push({ inn, ov, p: r.p, eng, y: t1won, rr1: r.rrTot.reduce((a, b) => a + b, 0) / r.n, act1: m.inns[0].total });
  }
}
const brier = (k) => { const v = rows.filter(r => r[k] != null); return [v.length, v.reduce((a, r) => a + (r[k] - r.y) ** 2, 0) / v.length]; };
const out = {};
for (const g of ['1|0', '1|10', '2|0', '2|10', '2|15']) {
  const v = rows.filter(r => `${r.inn}|${r.ov}` === g);
  const b = k => v.filter(r => r[k] != null).reduce((a, r) => a + (r[k] - r.y) ** 2, 0) / v.filter(r => r[k] != null).length;
  out[g] = { n: v.length, sim: +b('p').toFixed(4), engine: +b('eng').toFixed(4), coin: 0.25 };
}
const st = rows.filter(r => r.inn === 1 && r.ov === 0);
out.first_inn_mean_sim = +(st.reduce((a, r) => a + r.rr1, 0) / st.length).toFixed(1);
out.first_inn_mean_actual = +(st.reduce((a, r) => a + r.act1, 0) / st.length).toFixed(1);
out.all = { sim: brier('p'), engine: brier('eng') };
// calibration bins
const bins = [0, .2, .4, .6, .8, 1.01]; out.calib = [];
for (let i = 0; i < 5; i++) { const v = rows.filter(r => r.p >= bins[i] && r.p < bins[i + 1]); out.calib.push([bins[i], v.length, v.length ? +(v.reduce((a, r) => a + r.p, 0) / v.length).toFixed(3) : null, v.length ? +(v.reduce((a, r) => a + r.y, 0) / v.length).toFixed(3) : null]); }
console.log(JSON.stringify(out, null, 1)); fs.writeFileSync(process.argv[4], JSON.stringify(out));
