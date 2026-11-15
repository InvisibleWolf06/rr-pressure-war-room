// worked examples for the report: one moment swap and season replays for the auction-board leaders
const fs = require('fs'); const S = JSON.parse(fs.readFileSync(process.argv[2])); const D = JSON.parse(fs.readFileSync(process.argv[3]));
const E = require('./web/sim.js').make(S); const P = S.players, nm = id => P[id] ? P[id].name : id;
const rrInn = m => m.inns[0].rr ? 0 : 1;
const out = {moment: [], season: []};
// moment: LSG 2025-04-19 (lost by 2), RR batting at 18.0 / 15.0 ov
const m = S.matches.find(x => x.date === '2025-04-19' && /Lucknow/.test(x.opp)); const ri = rrInn(m), I = m.inns[ri];
for (const ov of [15, 18]) {
  const k = I.b.findIndex(b => b[0] >= ov + 1); const st = E.stateAt(I, k, ri ? m.target : null);
  const outId = st.striker, base = E.run(m, ri + 1, k, null, 4000, 5);
  const row = {ov, score: st.score, wk: st.wk, need: m.target - st.score, balls: 120 - st.legal, striker: nm(outId), base: +(base.p * 100).toFixed(1), swaps: []};
  for (const c of D.bat_board.slice(0, 4)) { const s = E.run(m, ri + 1, k, {bat: {out: outId, in: c.id}}, 4000, 5); row.swaps.push([c.name, +(s.p * 100).toFixed(1)]); }
  out.moment.push(row);
}
out.moment_match = {date: m.date, opp: m.opp, result: m.result};
const pickOut = (m, rule) => { const ri = rrInn(m), I = m.inns[ri], B = m.inns[1 - ri];
  if (rule.startsWith('pos')) return I.order[+rule.slice(3) - 1];
  const t = {}; B.b.forEach(b => { const x = t[b[3]] = t[b[3]] || {r: 0, l: 0, ov: new Set()}; x.r += b[4] + b[5]; x.l += b[6]; x.ov.add(b[0]); });
  return Object.keys(t).map(Number).filter(p => t[p].ov.size >= 2).sort((a, b) => t[b].r / t[b].l - t[a].r / t[a].l)[0]; };
const season = (id, kind, rule) => { let g = 0, n = 0, flips = []; for (const m of S.matches) { if (m.revised) continue;
  const o = pickOut(m, rule); if (o == null || new Set([...m.inns[0].order, ...m.inns[1].order]).has(id)) continue;
  const b = E.run(m, 1, 0, null, 1500, 9).p, s = E.run(m, 1, 0, {[kind]: {out: o, in: id}}, 1500, 9).p; g += s - b; n++;
  if (m.rr_won === false && b < .5 && s >= .5) flips.push(`${m.date} v ${m.opp}`); } return {gain: +g.toFixed(2), n, flips}; };
for (const c of D.bat_board.slice(0, 5)) out.season.push({name: c.name, kind: 'bat', rule: 'No. 5', ...season(c.id, 'bat', 'pos5')});
for (const c of D.bowl_board.slice(0, 5)) out.season.push({name: c.name, kind: 'bowl', rule: 'most expensive bowler', ...season(c.id, 'bowl', 'dear')});
fs.writeFileSync(process.argv[4], JSON.stringify(out, null, 1)); console.log(JSON.stringify(out, null, 1));
