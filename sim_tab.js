/* ================= MATCH SIMULATOR TAB ================= */
const SIM = JSON.parse(document.getElementById('simdata').textContent);
const ENG = RRSim.make(SIM);
const SP = SIM.players, pname = id => (SP[id] && SP[id].name) || String(id);
const AVL = {available:'In auction pool', rumoured:'Release rumoured', contracted:'Under contract', rr:'RR player', retired:'Retired', ineligible:'Not eligible'};
const sst = {m: null, inn: 2, k: null, mode: 'bat', out: null, inn_: null, res: null, season: null, sCand: null, sRule: 'pos5', sMode: 'bat', busy: false};
const OL = ['Dot', '1', '2', '3', '4', '6', 'Out'];

function simMatch(){ return SIM.matches.find(m => m.id === sst.m); }
function legalCount(inn, k){ let l = 0; for (let i = 0; i < k; i++) if (inn.b[i][6]) l++; return l; }
function ovStr(l){ return `${Math.floor(l / 6)}.${l % 6}`; }
function rrInn(m){ return m.inns[0].rr ? 0 : 1; }

// which RR players can be swapped out at this moment
function swapTargets(m, inn, k, mode){
  const ri = rrInn(m), I = m.inns[ri], startInn = inn;  // inn is 1|2
  if (mode === 'bat') {
    if (ri + 1 < startInn) return [];                  // RR batted first and that innings is over
    let out = new Set(), str = null, non = null;
    if (ri + 1 === startInn) { const s = ENG.stateAt(I, k, null); out = s.out; str = s.striker; non = s.non; }
    return I.order.filter(p => !out.has(p) && SP[p] && SP[p].bat).map(p => ({id: p, tag: p === str ? 'on strike' : p === non ? 'non-striker' : 'yet to bat'}))
      .filter(x => ri + 1 === startInn || true);
  }
  const bi = 1 - ri, B = m.inns[bi];
  if (bi + 1 < startInn) return [];
  const fromOv = (bi + 1 === startInn && k < B.b.length) ? B.b[k][0] : 1;
  const left = {}; B.b.forEach(b => { if (b[0] >= fromOv) left[b[3]] = (left[b[3]] || new Set()).add(b[0]); });
  return Object.entries(left).map(([p, s]) => ({id: +p, tag: `${s.size} over${s.size > 1 ? 's' : ''} left`}));
}
function candList(kind, m){
  const inMatch = new Set([...m.inns[0].order, ...m.inns[1].order, ...m.inns[0].b.map(b => b[3]), ...m.inns[1].b.map(b => b[3])]);
  const ids = kind === 'bat' ? SIM.cand_bat : SIM.cand_bowl, rk = kind === 'bat' ? 'bat_rank' : 'bowl_rank';
  const board = new Set((kind === 'bat' ? D.bat_board : D.bowl_board).map(c => c.id));
  return ids.filter(p => SP[p] && SP[p][kind] && !inMatch.has(p))
    .map(p => ({id: p, rank: SP[p][rk] || 999, board: board.has(p), avail: SP[p].avail}))
    .sort((a, b) => (b.board - a.board) || (a.rank - b.rank));
}

function candGroups(cands, kind){
  const bk = new Set(Object.values(SC.backups[kind]).flat().map(x => x.id)), gm = new Set([...SC.gems[kind], ...(SC.wider[kind] || [])].map(x => x.id));
  const used = new Set(), take = f => cands.filter(c => !used.has(c.id) && f(c)).map(c => (used.add(c.id), c));
  return [['RR auction board', take(c => c.board)], ['Backups', take(c => bk.has(c.id))], ['Hidden gems & wider pool', take(c => gm.has(c.id))],
          ['All other players (by rank)', take(() => true)]];
}
function simDefaults(){
  if (sst.m == null) {   // open on a close RR defeat
    const lost = SIM.matches.filter(m => m.rr_won === false && !m.revised);
    const close = lost.find(m => /by [1-9] run|by [1-3] wicket/i.test(m.result)) || lost[0] || SIM.matches[0];
    sst.m = close.id; sst.inn = rrInn(close) + 1;
    const I = close.inns[sst.inn - 1]; sst.k = Math.min(I.b.length - 1, Math.max(0, I.b.findIndex(b => b[0] >= 15)));
  }
}

function sim(){
  simDefaults();
  const m = simMatch(), I = m.inns[sst.inn - 1];
  if (sst.k == null || sst.k > I.b.length) sst.k = 0;
  const target = sst.inn === 2 ? m.target : null, s = ENG.stateAt(I, sst.k, target); s.inn = sst.inn;
  const l = s.legal, nxt = I.b[sst.k];
  const bowler = nxt ? nxt[3] : null, ph = ENG.phaseOf(l), pr = ENG.pHP(s);
  const need = sst.inn === 2 ? `need ${Math.max(0, target - s.score)} off ${s.maxBalls - l}` : `batting first`;
  const tgts = swapTargets(m, sst.inn, sst.k, sst.mode);
  if (!tgts.some(t => t.id === sst.out)) sst.out = tgts[0] ? tgts[0].id : null;
  const cands = candList(sst.mode, m);
  if (!cands.some(c => c.id === sst.inn_)) sst.inn_ = cands[0] ? cands[0].id : null;
  const opt = (v, t, sel) => `<option value="${v}" ${sel ? 'selected' : ''}>${esc(t)}</option>`;
  let h = `<p class="muted" style="font-size:14px">Pick a real Rajasthan Royals game from IPL 2025–26, stop it at any ball, and send in a different player. The simulator replays the rest of the match ${'2,000'} times, ball by ball, with every batter and bowler acting on his own record in that phase against that type of bowling, and on how he changes when the pressure rises. Everything else stays as it was: the score, the batting order, who bowls which over.</p>
  <div class="ctrl"><b>Match</b><select id="sM">${SIM.matches.map(x => opt(x.id, `${x.date} · ${x.season} · vs ${x.opp} · ${x.rr_won === true ? 'W' : x.rr_won === false ? 'L' : 'NR'}${x.revised ? ' (shortened)' : ''}`, x.id === sst.m)).join('')}</select>
  <b>Innings</b><div class="seg">${m.inns.map((x, i) => `<button data-sinn="${i + 1}" class="${sst.inn === i + 1 ? 'on' : ''}">${x.rr ? 'RR batting' : 'RR bowling'}</button>`).join('')}</div></div>
  <div class="ctrl"><b>Moment</b><input type="range" id="sK" min="0" max="${I.b.length}" value="${sst.k}" style="flex:1;min-width:240px;accent-color:#EC008C">
    <span class="muted" style="min-width:250px">${esc(I.team)} <b>${s.score}/${s.wk}</b> after ${ovStr(l)} ov · ${need}</span></div>
  <div class="kpis" style="grid-template-columns:repeat(4,1fr)">
    <div class="kpi"><div class="l">On strike</div><div class="v" style="font-size:24px">${s.striker ? esc(pname(s.striker)) : '—'}</div><div class="s">non-striker ${s.non ? esc(pname(s.non)) : '—'}</div></div>
    <div class="kpi"><div class="l">Bowling next</div><div class="v" style="font-size:24px">${bowler ? esc(pname(bowler)) : '—'}</div><div class="s">${ph} · ${bowler ? ((SP[bowler] || {}).type || 'Pace') : ''}</div></div>
    <div class="kpi"><div class="l">Pressure on the next ball</div><div class="v">${Math.round(pr * 100)}%</div><div class="s">chance it is a top-20% pressure ball</div></div>
    <div class="kpi"><div class="l">What really happened</div><div class="v" style="font-size:22px">${m.rr_won === true ? 'RR won' : m.rr_won === false ? 'RR lost' : 'No result'}</div><div class="s">${esc(m.result)}</div></div></div>
  <h2>Make the swap</h2>
  <div class="ctrl"><div class="seg"><button data-smode="bat" class="${sst.mode === 'bat' ? 'on' : ''}">Swap a batter</button><button data-smode="bowl" class="${sst.mode === 'bowl' ? 'on' : ''}">Swap a bowler</button></div>
   <b>Take out</b><select id="sOut">${tgts.length ? tgts.map(t => opt(t.id, `${pname(t.id)} (${t.tag})`, t.id === sst.out)).join('') : '<option>No RR ' + (sst.mode === 'bat' ? 'batting' : 'bowling') + ' left after this moment</option>'}</select>
   <b>Bring in</b><select id="sIn">${candGroups(cands, sst.mode).map(([g, xs]) => xs.length ? `<optgroup label="${g}">${xs.map(c => opt(c.id, `${pname(c.id)} · ${c.rank < 999 ? 'rank ' + c.rank : 'unrated'} · ${AVL[c.avail] || ''}`, c.id === sst.inn_)).join('')}</optgroup>` : '').join('')}</select>
   <button id="sGo" class="go" ${tgts.length ? '' : 'disabled'}>Simulate 2,000 times</button></div>
  <div id="sOutBox">${sst.res && sst.res.key === key() ? simResult(sst.res) : '<div class="muted">Pick the moment and the swap, then simulate.</div>'}</div>
  <h2>Season replay</h2>
  ${seasonPanel()}
  <div class="note" style="padding:10px 14px;margin-top:16px;font-size:13px"><b>How far to trust it.</b> Checked on all ${SIM.validation.all.sim[0]} game states from 5 points in every IPL 2025–26 match: Brier score ${SIM.validation.all.sim[1].toFixed(3)} (lower is better; a coin flip scores 0.250, the win-probability model in Method &amp; Proof scores ${SIM.validation.all.engine[1].toFixed(3)}). Simulated first-innings totals average ${SIM.validation.first_inn_mean_sim} against ${SIM.validation.first_inn_mean_actual} in reality. Player records include these same games, so treat the gaps between two players as a guide, not a forecast. Toss, dew, injuries and captaincy are not modelled, and the swap changes one name only: field placings and the rest of the plan stay as they were.</div>`;
  setTimeout(simWire);
  return h;
}
function key(){ return [sst.m, sst.inn, sst.k, sst.mode, sst.out, sst.inn_].join('|'); }

function lineFor(kind, c, n){
  if (kind === 'bat') { const sr = c.balls ? c.runs / c.balls * 100 : 0; return `${(c.runs / n).toFixed(1)} runs off ${(c.balls / n).toFixed(1)} balls · SR ${sr.toFixed(0)} · out in ${Math.round(c.outs / n * 100)}% of games`; }
  const ov = c.legal / 6 / n; return `${ov.toFixed(1)} overs · ${(c.conc / n).toFixed(1)} runs · econ ${(c.legal ? c.conc / c.legal * 6 : 0).toFixed(2)} · ${(c.wk / n).toFixed(2)} wickets`;
}
function simResult(r){
  const d = (r.swap.p - r.base.p) * 100, col = d >= 0 ? 'var(--gold)' : '#9AA3B8';
  const m = simMatch(), I = m.inns[sst.inn - 1], nb = I.b[sst.k];
  let mu = '';
  if (r.mu) {
    const bat = r.mu.bowler != null, who = bat ? r.mu.bowler : r.mu.batter, wt = (SP[r.mu.bowler] || {}).type || 'pace';
    const intro = bat ? `Next ball from <b>${esc(pname(who))}</b> with the match state exactly as it was. Each bar is the chance of that outcome for each batter.`
                      : `Next ball to <b>${esc(pname(who))}</b> with the match state exactly as it was. Each bar is the chance of that outcome for each bowler.`;
    const unit = bat ? 'runs per ball' : 'runs conceded per ball', wl = bat ? 'out' : 'wicket';
    const hist = r.mu.h2h ? (bat ? `Real meetings: ${esc(pname(r.mu.b))} has faced him ${r.mu.h2h[0]} balls for ${r.mu.h2h[1]} runs, out ${r.mu.h2h[2]} times.`
                                 : `Real meetings: ${esc(pname(who))} has faced ${esc(pname(r.mu.b))} ${r.mu.h2h[0]} balls for ${r.mu.h2h[1]} runs, out ${r.mu.h2h[2]} times.`)
             : (bat ? `${esc(pname(r.mu.b))} has never faced him in this data, so the bar is built from each player's record against ${esc(wt.toLowerCase())} bowling in this phase.`
                    : `${esc(pname(r.mu.b))} has never bowled to him in this data, so the bar is built from each player's record in this phase.`);
    mu = `<h2>Head to head at this moment</h2><div class="two"><div class="plot" id="sMu" style="height:300px"></div><div class="muted" style="font-size:13px">
      <p>${intro}</p><p><b>${esc(pname(r.mu.a))}</b>: ${r.mu.ea.toFixed(2)} ${unit}, ${wl} ${(r.mu.da[6] * 100).toFixed(1)}%<br><b>${esc(pname(r.mu.b))}</b>: ${r.mu.eb.toFixed(2)} ${unit}, ${wl} ${(r.mu.db[6] * 100).toFixed(1)}%</p><p>${hist}</p></div></div>`;
  }
  setTimeout(() => drawPaths(r), 60);
  setTimeout(() => {
    const x = OL;
    const chase = rrInn(m) === 1;
    const cats = chase ? ['Lose by 25+ runs', 'Lose by 10–24', 'Lose by 1–9', 'Tie', 'Win, 1–3 wkts left', 'Win, 4–6 wkts left', 'Win, 7+ wkts left']
                       : ['Lose, chased with 7+ wkts left', 'Lose, 4–6 wkts left', 'Lose, 1–3 wkts left', 'Tie', 'Win by 1–9 runs', 'Win by 10–24', 'Win by 25+ runs'];
    const pc = a => a.map(v => +(v / r.base.n * 100).toFixed(1));
    const real = (() => { const t = m.inns[1].total, tgt = m.target, wk = m.inns[1].wk; return t >= tgt ? (chase ? (wk <= 3 ? 6 : wk <= 6 ? 5 : 4) : (wk <= 3 ? 0 : wk <= 6 ? 1 : 2)) : t === tgt - 1 ? 3 : (() => { const by = tgt - 1 - t, g = by >= 25 ? 2 : by >= 10 ? 1 : 0; return chase ? 2 - g : 4 + g; })(); })();
    Plotly.newPlot('sHist', [
      {type: 'bar', x: cats, y: pc(r.base.margin), name: `With ${pname(r.outId)}`, marker: {color: '#9AA3B8'}, text: pc(r.base.margin).map(v => v ? v.toFixed(0) + '%' : ''), textposition: 'outside', cliponaxis: false},
      {type: 'bar', x: cats, y: pc(r.swap.margin), name: `With ${pname(r.inId)}`, marker: {color: PINK}, text: pc(r.swap.margin).map(v => v ? v.toFixed(0) + '%' : ''), textposition: 'outside', cliponaxis: false}],
      LAY({barmode: 'group', title: {text: 'How the 2,000 replays finish (RR result)', font: {size: 14}}, margin: {l: 44, r: 10, t: 44, b: 96},
        xaxis: {type: 'category', tickangle: -25, tickfont: {size: 11}}, yaxis: {title: '% of replays', gridcolor: 'rgba(255,255,255,.08)'},
        shapes: [{type: 'rect', xref: 'x', x0: real - .5, x1: real + .5, yref: 'paper', y0: 0, y1: 1, line: {color: '#F4C542', dash: 'dot', width: 1.5}, fillcolor: 'rgba(244,197,66,.06)'}],
        annotations: [{x: cats[real], yref: 'paper', y: 1.0, text: 'what happened', showarrow: false, font: {color: '#F4C542', size: 11}}]}), PCFG);
    if (r.mu) Plotly.newPlot('sMu', [
      {type: 'bar', x, y: r.mu.da.map(v => +(v * 100).toFixed(1)), name: pname(r.mu.a), marker: {color: '#9AA3B8'}, text: r.mu.da.map(v => (v * 100).toFixed(0) + '%'), textposition: 'outside', cliponaxis: false},
      {type: 'bar', x, y: r.mu.db.map(v => +(v * 100).toFixed(1)), name: pname(r.mu.b), marker: {color: PINK}, text: r.mu.db.map(v => (v * 100).toFixed(0) + '%'), textposition: 'outside', cliponaxis: false}],
      LAY({barmode: 'group', margin: {l: 40, r: 10, t: 20, b: 60}, xaxis: {type: 'category'}, yaxis: {title: '% of balls', gridcolor: 'rgba(255,255,255,.08)'}}), PCFG);
  });
  const kind = sst.mode;
  return `<div class="kpis" style="grid-template-columns:repeat(3,1fr);margin-top:6px">
    <div class="kpi"><div class="l">RR win chance with ${esc(pname(r.outId))}</div><div class="v">${(r.base.p * 100).toFixed(0)}%</div><div class="s">the side that actually played</div></div>
    <div class="kpi"><div class="l">RR win chance with ${esc(pname(r.inId))}</div><div class="v" style="color:var(--hot)">${(r.swap.p * 100).toFixed(0)}%</div><div class="s">same moment, one name changed</div></div>
    <div class="kpi"><div class="l">Swing</div><div class="v" style="color:${col}">${d >= 0 ? '+' : ''}${d.toFixed(1)} pts</div><div class="s">${Math.abs(d) < 3 ? 'within the noise of one game' : d > 0 ? (r.base.p < .5 && r.swap.p >= .5 ? 'turns a likely defeat into a likely win' : 'better odds') : 'worse odds'}</div></div></div>
  <div class="two" style="margin-top:12px"><div class="plot" id="sHist" style="height:320px"></div><div class="muted" style="font-size:13px">
    <p><b>${esc(pname(r.outId))}</b> from here (the real choice): ${lineFor(kind, r.base.cand, r.base.n)}</p>
    <p><b>${esc(pname(r.inId))}</b> in his place: ${lineFor(kind, r.swap.cand, r.swap.n)}</p>
    <p>Both sets of replays use the same random numbers, so the gap comes from the players, not from luck. The gold box marks how the real game ended.</p></div></div>${mu}
  <h2>Ball by ball · how the match could unfold</h2>
  <div class="ctrl"><button class="go sm" id="sAnother">Show another replay</button><span class="muted" id="sPathMsg">Tracing one replay with each side…</span></div>
  <div class="plot" id="sWP" style="height:440px"></div>
  <div class="muted" style="font-size:13px;margin-top:6px">The grey line is RR's real win chance after every ball of the actual match (from the win-probability model in Method &amp; Proof). From the chosen moment, the blue and pink lines follow one single replay each: blue with ${esc(pname(r.outId))}, pink with ${esc(pname(r.inId))}, using the same random numbers. After every ball of each replay RR's win chance is re-estimated from quick simulations of the rest of the game. At the swap point the simulator's view and the grey line can differ, because they are two different models. Big dots are boundaries, crosses are wickets. One replay is one possible story; the percentages above summarise all 2,000.</div>`;
}

function runOne(){
  const m = simMatch(), I = m.inns[sst.inn - 1];
  const kind = sst.mode, outId = sst.out, inId = sst.inn_, N = 2000, seed = 20261;
  const base = ENG.run(m, sst.inn, sst.k, {watch: {id: outId, kind}}, N, seed);
  const swap = ENG.run(m, sst.inn, sst.k, {[kind]: {out: outId, in: inId}, watch: {id: inId, kind}}, N, seed);
  const res = {key: key(), base, swap, outId, inId, actualRR: m.inns[rrInn(m)].total};
  // head-to-head on the next ball (batter swap while RR is batting, or bowler swap while RR is bowling)
  const s = ENG.stateAt(I, sst.k, sst.inn === 2 ? m.target : null); s.inn = sst.inn; const nb = I.b[sst.k];
  if (nb && kind === 'bat' && I.rr && (outId === s.striker || outId === s.non)) {
    const bw = nb[3]; const da = ENG.dist(outId, bw, s), db = ENG.dist(inId, bw, s);
    const ev = d => d.slice(0, 6).reduce((a, v, i) => a + v * [0, 1, 2, 3, 4, 6][i], 0);
    res.mu = {bowler: bw, a: outId, b: inId, da, db, ea: ev(da), eb: ev(db), h2h: SIM.h2h[`${inId}-${bw}`]};
  } else if (nb && kind === 'bowl' && !I.rr) {
    const bt = s.striker; const da = ENG.dist(bt, outId, s), db = ENG.dist(bt, inId, s);
    const ev = d => d.slice(0, 6).reduce((a, v, i) => a + v * [0, 1, 2, 3, 4, 6][i], 0);
    res.mu = {bowler: null, a: outId, b: inId, da, db, ea: ev(da), eb: ev(db), batter: bt, h2h: SIM.h2h[`${bt}-${inId}`]};
  }
  sst.res = res;
}

function actualWP(m){
  const xs = [], ys = [], ev = [], tx = [];
  m.inns.forEach((I, i) => { let l = 0;
    if (i === 0) { xs.push(0); ys.push(I.rr ? I.wp0 : 1 - I.wp0); ev.push(0); tx.push('start'); }
    I.b.forEach((b, j) => { if (b[6]) l++; const w = I.wp[j]; xs.push(i * 20 + l / 6); ys.push(I.rr ? w : 1 - w); ev.push(b[7] ? 'W' : b[4] >= 4 ? b[4] : 0);
      tx.push(`${I.team}: ${Math.floor(l / 6)}.${l % 6} · ${pname(b[3])} to ${pname(b[1])}: ${b[4] + b[5]}${b[7] ? ' · WICKET ' + pname(b[7]) : ''}`); }); });
  return {xs, ys, ev, tx};
}
function drawPaths(r, seedBump){
  const el = document.getElementById('sWP'); if (!el) return;
  const m = simMatch(), seed = 4242 + (sst.pathSeed || 0);
  const nIn = sst.inn === 2 ? 80 : 40;
  const pb = ENG.path(m, sst.inn, sst.k, null, seed, nIn), ps = ENG.path(m, sst.inn, sst.k, {[sst.mode]: {out: r.outId, in: r.inId}}, seed, nIn);
  const A = actualWP(m), I = m.inns[sst.inn - 1], x0 = (sst.inn - 1) * 20 + legalCount(I, sst.k) / 6;
  const tr = (p, name, col) => {
    const pts = p.pts;
    return [{type: 'scatter', mode: 'lines+markers', name, x: pts.map(q => q.x), y: pts.map(q => +(q.wp * 100).toFixed(1)), line: {color: col, width: 2.5, shape: 'linear'}, marker: {size: 4, color: col},
             text: pts.map(q => `${q.inn === 1 ? m.inns[0].team : m.inns[1].team} ${q.score}/${q.wk}`), hovertemplate: '%{text}<br>RR win chance %{y}%<extra>' + name + '</extra>'},
            {type: 'scatter', mode: 'markers', showlegend: false, x: pts.filter(q => q.ev).map(q => q.x), y: pts.filter(q => q.ev).map(q => +(q.wp * 100).toFixed(1)),
             marker: {size: pts.filter(q => q.ev).map(q => q.ev === 'W' ? 11 : 9), symbol: pts.filter(q => q.ev).map(q => q.ev === 'W' ? 'x' : 'circle'), color: col, line: {color: '#fff', width: 1}},
             text: pts.filter(q => q.ev).map(q => q.ev === 'W' ? 'wicket' : q.ev), hovertemplate: '%{text}<extra></extra>'}];
  };
  const evA = A.xs.map((x, i) => i).filter(i => A.ev[i]);
  Plotly.newPlot('sWP', [
    {type: 'scatter', mode: 'lines+markers', name: 'Actual match', x: A.xs, y: A.ys.map(v => +(v * 100).toFixed(1)), text: A.tx, hovertemplate: '%{text}<br>RR win chance %{y}%<extra></extra>', line: {color: 'rgba(201,207,221,.75)', width: 2}, marker: {size: 3, color: 'rgba(201,207,221,.75)'}},
    {type: 'scatter', mode: 'markers', showlegend: false, x: evA.map(i => A.xs[i]), y: evA.map(i => +(A.ys[i] * 100).toFixed(1)), text: evA.map(i => A.tx[i]), hovertemplate: '%{text}<extra></extra>',
     marker: {size: evA.map(i => A.ev[i] === 'W' ? 10 : 7), symbol: evA.map(i => A.ev[i] === 'W' ? 'x' : 'circle'), color: 'rgba(201,207,221,.9)'}},
    ...tr(pb, `Replay with ${pname(r.outId)}`, '#7C9CFF'), ...tr(ps, `Replay with ${pname(r.inId)}`, PINK)],
    LAY({margin: {l: 50, r: 14, t: 20, b: 50}, xaxis: {title: 'overs (0–20 first innings, 20–40 second innings)', range: [0, 40.5], gridcolor: 'rgba(255,255,255,.06)', dtick: 5},
      yaxis: {title: 'RR win chance (%)', range: [-3, 103], gridcolor: 'rgba(255,255,255,.08)'},
      shapes: [{type: 'line', x0: 20, x1: 20, yref: 'paper', y0: 0, y1: 1, line: {color: 'rgba(255,255,255,.25)', width: 1}},
               {type: 'line', x0: x0, x1: x0, yref: 'paper', y0: 0, y1: 1, line: {color: '#F4C542', dash: 'dot', width: 2}},
               {type: 'line', x0: 0, x1: 40.5, y0: 50, y1: 50, line: {color: 'rgba(255,255,255,.2)', dash: 'dash', width: 1}}],
      annotations: [{x: x0, yref: 'paper', y: 1.03, text: 'swap made here', showarrow: false, font: {color: '#F4C542', size: 11}}]}), PCFG);
  const msg = document.getElementById('sPathMsg');
  if (msg) msg.textContent = `In this replay RR ${pb.rrWon === 1 ? 'win' : pb.rrWon === 0 ? 'lose' : 'tie'} with ${pname(r.outId)} and ${ps.rrWon === 1 ? 'win' : ps.rrWon === 0 ? 'lose' : 'tie'} with ${pname(r.inId)}.`;
  const bt = document.getElementById('sAnother'); if (bt) bt.onclick = () => { sst.pathSeed = (sst.pathSeed || 0) + 1; if (msg) msg.textContent = 'Tracing…'; setTimeout(() => drawPaths(r), 20); };
}

/* ---------- season replay: one candidate in every RR game of a season ---------- */
function seasonPanel(){
  const cands = candList(sst.sMode, {inns: [{order: [], b: []}, {order: [], b: []}]});
  if (!cands.some(c => c.id === sst.sCand)) sst.sCand = cands[0] && cands[0].id;
  const rules = sst.sMode === 'bat'
    ? [['pos3', 'RR\'s No. 3'], ['pos4', 'RR\'s No. 4'], ['pos5', 'RR\'s No. 5'], ['pos6', 'RR\'s No. 6'], ['pos7', 'RR\'s No. 7']]
    : [['dear', 'RR\'s most expensive bowler that day'], ['death', 'the RR bowler with most death overs'], ['spin', 'RR\'s main spinner'], ['pace', 'RR\'s main seamer']];
  if (!rules.some(r => r[0] === sst.sRule)) sst.sRule = rules[0][0];
  const S = sst.season && sst.season.key === skey() ? sst.season : null;
  return `<p class="muted" style="font-size:14px">The same idea across a whole season: drop one player into every RR game from the first ball and count the results that change. A defeat "flips" when RR lost it in reality, the replays with the real side also lose it more often than not, and the replays with the new player win it more often than not. From the first ball one player rarely moves a game by more than a few points; from a tight moment late on he can move it a lot, so try the moment view for that.</p>
   <div class="ctrl"><div class="seg"><button data-ssmode="bat" class="${sst.sMode === 'bat' ? 'on' : ''}">Batter</button><button data-ssmode="bowl" class="${sst.sMode === 'bowl' ? 'on' : ''}">Bowler</button></div>
   <b>Player</b><select id="ssC">${cands.map(c => `<option value="${c.id}" ${c.id === sst.sCand ? 'selected' : ''}>${esc(pname(c.id))}${c.board ? ' · auction board' : ''} · ${AVL[c.avail] || ''}</option>`).join('')}</select>
   <b>replaces</b><select id="ssR">${rules.map(r => `<option value="${r[0]}" ${r[0] === sst.sRule ? 'selected' : ''}>${r[1]}</option>`).join('')}</select>
   <button id="ssGo" class="go">Replay ${SIM.matches.length} games</button><span id="ssProg" class="muted"></span></div>
   <div id="ssBox">${S ? seasonResult(S) : ''}</div>`;
}
function skey(){ return [sst.sMode, sst.sCand, sst.sRule].join('|'); }
function pickOut(m, rule){
  const ri = rrInn(m), I = m.inns[ri], B = m.inns[1 - ri];
  if (rule.startsWith('pos')) return I.order[+rule.slice(3) - 1];
  const tally = {}; B.b.forEach(b => { const t = tally[b[3]] = tally[b[3]] || {r: 0, l: 0, death: new Set(), ov: new Set()}; t.r += b[4] + b[5]; t.l += b[6]; t.ov.add(b[0]); if (b[0] >= 16) t.death.add(b[0]); });
  const ids = Object.keys(tally).map(Number).filter(p => tally[p].ov.size >= 2);
  const by = f => ids.sort((a, b) => f(b) - f(a))[0];
  if (rule === 'dear') return by(p => tally[p].r / Math.max(tally[p].l, 1));
  if (rule === 'death') return by(p => tally[p].death.size * 10 + tally[p].ov.size);
  const want = rule === 'spin' ? 'Spin' : 'Pace';
  return by(p => (((SP[p] || {}).type || 'Pace') === want ? 100 : 0) + tally[p].ov.size);
}
function runSeason(done){
  const out = [], ms = SIM.matches.filter(m => !m.revised), N = 600; let i = 0;
  const step = () => {
    const t0 = performance.now();
    while (i < ms.length && performance.now() - t0 < 60) {
      const m = ms[i++], o = pickOut(m, sst.sRule), inId = sst.sCand;
      const inMatch = new Set([...m.inns[0].order, ...m.inns[1].order]);
      if (o == null || inMatch.has(inId)) { out.push({m, skip: o == null ? 'no one to replace' : 'played in this game'}); continue; }
      const b = ENG.run(m, 1, 0, null, N, 777), s = ENG.run(m, 1, 0, {[sst.sMode]: {out: o, in: inId}}, N, 777);
      out.push({m, out: o, b: b.p, s: s.p});
    }
    const pr = document.getElementById('ssProg'); if (pr) pr.textContent = i < ms.length ? ` ${i}/${ms.length} games…` : '';
    if (i < ms.length) setTimeout(step, 0); else done({key: skey(), rows: out});
  };
  step();
}
function seasonResult(S){
  const ok = S.rows.filter(r => !r.skip), gain = ok.reduce((a, r) => a + (r.s - r.b), 0);
  const flips = ok.filter(r => r.m.rr_won === false && r.b < .5 && r.s >= .5), lose = ok.filter(r => r.m.rr_won === true && r.b >= .5 && r.s < .5);
  const bySeason = {}; ok.forEach(r => { const k = r.m.season; bySeason[k] = bySeason[k] || {g: 0, w: 0, d: 0}; bySeason[k].g++; bySeason[k].w += r.m.rr_won === true ? 1 : 0; bySeason[k].d += r.s - r.b; });
  setTimeout(() => {
    const rows = ok.slice().sort((a, b) => (b.s - b.b) - (a.s - a.b));
    Plotly.newPlot('ssPlot', [{type: 'bar', orientation: 'h', y: rows.map(r => `${r.m.date} vs ${r.m.opp.replace(/ (Super Kings|Indians|Capitals|Titans|Knight Riders|Super Giants|Kings|Challengers Bengaluru|Sunrisers Hyderabad)$/, m => ' ' + m.trim().split(' ').map(w => w[0]).join(''))} ${r.m.rr_won ? 'W' : 'L'}`),
      x: rows.map(r => +((r.s - r.b) * 100).toFixed(1)), marker: {color: rows.map(r => r.m.rr_won === false && r.b < .5 && r.s >= .5 ? '#F4C542' : (r.s >= r.b ? PINK : '#9AA3B8'))},
      hovertemplate: rows.map(r => `${esc(r.m.result)}<br>out: ${esc(pname(r.out))}<br>win chance ${(r.b * 100).toFixed(0)}% → ${(r.s * 100).toFixed(0)}%<extra></extra>`)}],
      LAY({height: Math.max(360, rows.length * 19 + 80), margin: {l: 190, r: 20, t: 20, b: 40}, xaxis: {title: 'change in RR win chance (points)', gridcolor: 'rgba(255,255,255,.08)', zerolinecolor: 'rgba(255,255,255,.4)'}, yaxis: {autorange: 'reversed', tickfont: {size: 11}}}), PCFG);
  });
  return `<div class="kpis" style="grid-template-columns:repeat(3,1fr)">
    <div class="kpi"><div class="l">Expected extra wins</div><div class="v" style="color:${gain >= 0 ? 'var(--gold)' : '#9AA3B8'}">${gain >= 0 ? '+' : ''}${gain.toFixed(2)}</div><div class="s">${ok.length} games from the first ball, win-chance changes added up</div></div>
    <div class="kpi"><div class="l">Defeats that flip</div><div class="v">${flips.length}</div><div class="s">${flips.map(r => `${r.m.date.slice(5)} v ${esc(r.m.opp.split(' ').map(w => w[0]).join(''))}`).join(' · ') || 'none'}</div></div>
    <div class="kpi"><div class="l">Wins put at risk</div><div class="v">${lose.length}</div><div class="s">RR wins that drop below 50% with him</div></div></div>
  <div class="muted" style="margin:6px 0 10px">${Object.entries(bySeason).map(([k, v]) => `IPL ${k}: RR won ${v.w}/${v.g}; with this change about ${(v.w + v.d).toFixed(1)}`).join(' · ')}${S.rows.some(r => r.skip) ? ` · skipped ${S.rows.filter(r => r.skip).length} game(s) where he played or no one fit the rule` : ''}</div>
  <div class="plot" id="ssPlot"></div>`;
}

function simWire(){
  const g = id => document.getElementById(id);
  g('sM').onchange = e => { sst.m = +e.target.value; const m = simMatch(); sst.inn = rrInn(m) + 1; sst.k = Math.max(0, m.inns[sst.inn - 1].b.findIndex(b => b[0] >= 15)); sst.res = null; render(); };
  document.querySelectorAll('[data-sinn]').forEach(b => b.onclick = () => { sst.inn = +b.dataset.sinn; sst.k = 0; sst.res = null; render(); });
  g('sK').oninput = e => { sst.k = +e.target.value; sst.res = null; render(); const n = g('sK'); if (n) n.focus(); };
  document.querySelectorAll('[data-smode]').forEach(b => b.onclick = () => { sst.mode = b.dataset.smode; sst.out = null; sst.inn_ = null; sst.res = null; render(); });
  g('sOut').onchange = e => { sst.out = +e.target.value; render(); };
  g('sIn').onchange = e => { sst.inn_ = +e.target.value; render(); };
  g('sGo').onclick = () => { g('sGo').textContent = 'Simulating…'; setTimeout(() => { runOne(); render(); const o = g('sOutBox'); if (o) o.scrollIntoView({behavior: 'smooth', block: 'start'}); }, 20); };
  document.querySelectorAll('[data-ssmode]').forEach(b => b.onclick = () => { sst.sMode = b.dataset.ssmode; sst.sCand = null; sst.sRule = sst.sMode === 'bat' ? 'pos5' : 'dear'; render(); });
  g('ssC').onchange = e => { sst.sCand = +e.target.value; render(); };
  g('ssR').onchange = e => { sst.sRule = e.target.value; render(); };
  g('ssGo').onclick = () => { if (sst.busy) return; sst.busy = true; g('ssGo').disabled = true; runSeason(S => { sst.season = S; sst.busy = false; render(); }); };
}
