/* ================= PLAYER LAB (strengths map) · SCOUTING · RETAIN & RELEASE ================= */
const LAB = JSON.parse(document.getElementById('labdata').textContent);
const SC = JSON.parse(document.getElementById('scoutdata').textContent);
const lst = {view: 'map', disc: 'bat', id: null, comp: 'All', ph: 'All', gDisc: 'bat', gBuy: true};
const MIN = 30;
const pctS = (a, b) => b ? (a / b * 100) : 0;
const AVL2 = {available: 'In auction pool', rumoured: 'Release rumoured', contracted: 'Under contract', rr: 'RR player', retired: 'Retired', ineligible: 'Not eligible'};
const avChip = a => a ? `<span class="chip ${a === 'available' ? 'av' : a === 'rumoured' ? 'ru' : 'no'}">${AVL2[a]}</span>` : '';
const tierChip = t => t ? `<span class="chip ${t === 'High' ? 'warn' : ''}">${t} demand</span>` : '';

function labRank(id, disc){ const t = disc === 'bat' ? D.bat_table : D.bowl_table; const r = t.find(x => x.id === +id); return r ? r.rank : null; }
function labList(disc){
  const src = LAB[disc];
  return Object.keys(src).map(id => ({id: +id, name: src[id].name, rank: labRank(id, disc)}))
    .sort((a, b) => (a.rank || 999) - (b.rank || 999) || a.name.localeCompare(b.name));
}

/* wagon wheel: 8 sectors, drawn from behind the striker looking at the bowler */
function wagon(z, lhb, title){
  const tot = z.reduce((a, b) => a + b, 0) || 1, cx = 170, cy = 165, R = 140;
  const ang = [[-180, -135], [-135, -90], [-90, -45], [-45, 0], [0, 45], [45, 90], [90, 135], [135, 180]];
  const mx = Math.max(...z) || 1;
  const pt = (a, r) => { const t = (a * (lhb ? -1 : 1) - 90) * Math.PI / 180; return [cx + r * Math.cos(t), cy + r * Math.sin(t)]; };
  let g = '';
  ang.forEach(([a0, a1], i) => {
    const [x0, y0] = pt(a0, R), [x1, y1] = pt(a1, R), sweep = lhb ? 0 : 1;
    const f = z[i] / mx, col = `rgba(236,0,140,${(0.10 + 0.75 * f).toFixed(2)})`;
    g += `<path d="M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${R},${R} 0 0 ${sweep} ${x1.toFixed(1)},${y1.toFixed(1)} Z" fill="${col}" stroke="rgba(255,255,255,.25)" stroke-width="1"><title>${LAB.zones[i]}: ${z[i]} runs (${pctS(z[i], tot).toFixed(0)}%)</title></path>`;
    const [lx, ly] = pt((a0 + a1) / 2, R * .64);
    g += `<text x="${lx.toFixed(1)}" y="${(ly - 3).toFixed(1)}" text-anchor="middle" fill="#fff" font-size="15" font-weight="700" font-family="Barlow Condensed">${pctS(z[i], tot).toFixed(0)}%</text>
          <text x="${lx.toFixed(1)}" y="${(ly + 11).toFixed(1)}" text-anchor="middle" fill="rgba(238,240,247,.75)" font-size="10" font-family="IBM Plex Sans">${LAB.zones[i]}</text>`;
  });
  const [ox] = pt(90, R + 2), [lgx] = pt(-90, R + 2);
  g += `<circle cx="${cx}" cy="${cy}" r="${R * .32}" fill="none" stroke="rgba(255,255,255,.22)" stroke-dasharray="3 4"/>
        <rect x="${cx - 6}" y="${cy - 26}" width="12" height="52" rx="2" fill="rgba(214,196,150,.55)"/>
        <circle cx="${cx}" cy="${cy + 22}" r="4" fill="#fff"/>
        <text x="${ox > cx ? 330 : 10}" y="18" text-anchor="${ox > cx ? 'end' : 'start'}" fill="#F4C542" font-size="11" font-family="IBM Plex Sans" letter-spacing="2">OFF SIDE</text>
        <text x="${lgx > cx ? 330 : 10}" y="18" text-anchor="${lgx > cx ? 'end' : 'start'}" fill="#F4C542" font-size="11" font-family="IBM Plex Sans" letter-spacing="2">LEG SIDE</text>`;
  return `<svg viewBox="0 0 340 330" style="width:100%;max-width:380px;display:block;margin:auto" role="img" aria-label="${esc(title)}">${g}</svg>
    <div class="muted" style="text-align:center;font-size:12px">${lhb ? 'Left-hander' : 'Right-hander'} view · from behind the striker looking at the bowler · ${tot} runs</div>`;
}
function tbl(head, rows){ return `<div class="tbl" style="max-height:none"><table><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr>${rows.join('')}</table></div>`; }
const small = n => n < MIN ? ' style="opacity:.5"' : '';

function labMap(){
  const list = labList(lst.disc);
  if (!list.some(x => x.id === lst.id)) lst.id = list[0].id;
  const P = LAB[lst.disc][lst.id], key = `${lst.comp}|${lst.ph}`, S = P.s[key], A = P.s[`${lst.comp}|All`], PR = P.s[`${lst.comp}|Pressure`];
  const bat = lst.disc === 'bat';
  const opt = list.map(x => `<option value="${x.id}" ${x.id === lst.id ? 'selected' : ''}>${x.rank ? '#' + x.rank + ' ' : ''}${esc(x.name)}</option>`).join('');
  let h = `<div class="ctrl"><div class="seg"><button data-ld="bat" class="${bat ? 'on' : ''}">Batters</button><button data-ld="bowl" class="${!bat ? 'on' : ''}">Bowlers</button></div>
    <select id="lp" style="min-width:240px">${opt}</select>
    <div class="seg">${['All', 'IPL', 'T20I'].map(c => `<button data-lc="${c}" class="${lst.comp === c ? 'on' : ''}">${c === 'All' ? 'Combined' : c}</button>`).join('')}</div>
    <div class="seg">${['All', 'Powerplay', 'Middle', 'Death', 'Pressure'].map(c => `<button data-lph="${c}" class="${lst.ph === c ? 'on' : ''}">${c === 'Pressure' ? 'Pressure balls' : c}</button>`).join('')}</div></div>`;
  if (!S) return h + `<div class="warnbox" style="padding:10px">No balls for ${esc(P.name)} in this filter.</div>`;
  const cards = bat ? batCards(S, P) : bowlCards(S, P);
  h += `<div class="eyebrow" style="margin-top:6px"><b>Scout the matchup</b></div><h2 style="margin-top:4px">${esc(P.name)} · strengths &amp; matchups</h2>
   <div class="muted" style="margin-bottom:10px">${bat ? P.hand : esc(P.type)} · ${lst.comp === 'All' ? 'IPL + T20I' : lst.comp} · ${lst.ph === 'All' ? 'all phases' : lst.ph === 'Pressure' ? 'pressure balls only' : lst.ph}. ${S.n} legal balls. Rates use legal balls; ${bat ? 'bat runs only, extras excluded' : 'runs include extras'}. Rows under ${MIN} balls are faded.</div>
   <div class="kpis" style="grid-template-columns:repeat(3,1fr)">${cards.map(c => `<div class="kpi"><div class="l">${c[0]}</div><div class="v" style="font-size:26px;color:${c[3] ? 'var(--hot)' : '#9AA3B8'}">${esc(c[1])}</div><div class="s" style="color:var(--ink2)">${esc(c[2])}</div></div>`).join('')}</div>`;
  const z = S.z, lhb = bat ? P.hand === 'LHB' : false;
  const side = `${pctS(S.side[0], S.side[0] + S.side[1]).toFixed(0)}% off side · ${pctS(S.side[1], S.side[0] + S.side[1]).toFixed(0)}% leg side`;
  if (bat) {
    const sr = n => S.n ? n : 0;
    h += `<div class="two" style="margin-top:14px"><div class="card"><h3 style="margin:0 0 4px">Where the runs come from</h3><div class="muted" style="font-size:12px;margin-bottom:6px">${side} · shot zones estimated from the stroke played</div>${wagon(z, lhb, 'Run map')}</div>
      <div><h3 style="margin:0 0 6px">Against bowling styles</h3>${tbl(['Style', 'Balls', 'SR', 'Outs', 'Balls/out', 'Dot %'], S.sty.sort((a, b) => b[1] - a[1]).map(r => `<tr${small(r[1])}><td><b>${esc(r[0])}</b></td><td>${r[1]}</td><td>${(r[2] / r[1] * 100).toFixed(0)}</td><td>${r[3]}</td><td>${r[3] ? (r[1] / r[3]).toFixed(0) : '–'}</td><td>${pctS(r[4], r[1]).toFixed(0)}</td></tr>`))}
      <h3 style="margin:14px 0 6px">Delivery types to prepare for</h3>${tbl(['Delivery', 'Balls', 'SR', 'Outs', 'Dot %'], S.del.map(r => `<tr${small(r[1])}><td><b>${esc(r[0])}</b></td><td>${r[1]}</td><td>${(r[2] / r[1] * 100).toFixed(0)}</td><td>${r[3]}</td><td>${pctS(r[4], r[1]).toFixed(0)}</td></tr>`))}</div></div>
      <div class="two" style="margin-top:14px"><div><h3 style="margin:0 0 6px">Go-to shots</h3>${tbl(['Stroke', 'Balls', 'Runs', 'SR', 'Outs'], S.str.map(r => `<tr${small(r[1])}><td><b>${esc(r[0])}</b></td><td>${r[1]}</td><td>${r[2]}</td><td>${(r[2] / r[1] * 100).toFixed(0)}</td><td>${r[3]}</td></tr>`))}</div>
      <div><h3 style="margin:0 0 6px">Under pressure vs all balls</h3><div id="lpr" class="plot" style="height:260px"></div>
      <div class="muted" style="font-size:12px">How he gets out (all formats): ${P.dis.map(d => `${esc(d[0])} ${d[1]}`).join(' · ')}</div></div></div>`;
  } else {
    h += `<div class="two" style="margin-top:14px"><div class="card"><h3 style="margin:0 0 4px">Where batters score off him</h3><div class="muted" style="font-size:12px;margin-bottom:6px">${side} (batter's off/leg) · drawn as a right-hander's field</div>${wagon(z, false, 'Runs conceded map')}</div>
      <div><h3 style="margin:0 0 6px">Against right- and left-handers</h3>${tbl(['Batter', 'Balls', 'Econ', 'Wkts', 'Balls/wkt', 'Dot %'], S.hand.map(r => `<tr${small(r[1])}><td><b>${r[0]}</b></td><td>${r[1]}</td><td>${(r[2] / r[1] * 6).toFixed(2)}</td><td>${r[3]}</td><td>${r[3] ? (r[1] / r[3]).toFixed(0) : '–'}</td><td>${pctS(r[4], r[1]).toFixed(0)}</td></tr>`))}
      <h3 style="margin:14px 0 6px">His deliveries</h3>${tbl(['Delivery', 'Balls', 'Share', 'Econ', 'Wkts', 'Dot %'], S.del.map(r => `<tr${small(r[1])}><td><b>${esc(r[0])}</b></td><td>${r[1]}</td><td>${pctS(r[1], S.n).toFixed(0)}%</td><td>${(r[2] / r[1] * 6).toFixed(2)}</td><td>${r[3]}</td><td>${pctS(r[4], r[1]).toFixed(0)}</td></tr>`))}</div></div>
      <div class="two" style="margin-top:14px"><div><h3 style="margin:0 0 6px">By phase</h3><div id="lphs" class="plot" style="height:260px"></div></div>
      <div><h3 style="margin:0 0 6px">Under pressure vs all balls</h3><div id="lpr" class="plot" style="height:260px"></div>
      <div class="muted" style="font-size:12px">How he takes wickets: ${P.dis.map(d => `${esc(d[0])} ${d[1]}`).join(' · ')}</div></div></div>`;
  }
  h += `<div class="muted" style="font-size:12px;margin-top:10px">Descriptive only: not adjusted for opposition, venue or who chose the matchup. Shot zones come from the stroke label and the on/off-side tag in the data, not from ball tracking.</div>`;
  setTimeout(() => {
    if (A && PR) {
      const m = bat ? [['Strike rate', s => s.r / s.n * 100], ['Dot %', s => s.d / s.n * 100], ['Boundary %', s => s.b4 / s.n * 100], ['Balls per dismissal', s => s.n / Math.max(s.o, 1)]]
                    : [['Economy', s => s.r / s.n * 6], ['Dot %', s => s.d / s.n * 100], ['Boundary %', s => s.b4 / s.n * 100], ['Balls per wicket', s => s.n / Math.max(s.w, 1)]];
      Plotly.newPlot('lpr', [{type: 'bar', x: m.map(x => x[0]), y: m.map(x => +x[1](A).toFixed(1)), name: `All balls (${A.n})`, marker: {color: GREY}, text: m.map(x => x[1](A).toFixed(1)), textposition: 'outside', cliponaxis: false},
        {type: 'bar', x: m.map(x => x[0]), y: m.map(x => +x[1](PR).toFixed(1)), name: `Pressure balls (${PR.n})`, marker: {color: PINK}, text: m.map(x => x[1](PR).toFixed(1)), textposition: 'outside', cliponaxis: false}],
        LAY({barmode: 'group', margin: {l: 36, r: 10, t: 16, b: 60}, xaxis: {type: 'category'}}), PCFG);
    }
    if (!bat) {
      const ph = ['Powerplay', 'Middle', 'Death'].map(p => [p, P.s[`${lst.comp}|${p}`]]).filter(x => x[1]);
      Plotly.newPlot('lphs', [{type: 'bar', x: ph.map(x => x[0]), y: ph.map(x => +(x[1].r / x[1].n * 6).toFixed(2)), name: 'Economy', marker: {color: PINK}, text: ph.map(x => `${(x[1].r / x[1].n * 6).toFixed(2)} · ${x[1].w} wkts · ${x[1].n} balls`), textposition: 'outside', cliponaxis: false}],
        LAY({margin: {l: 36, r: 10, t: 16, b: 40}, showlegend: false, yaxis: {title: 'economy', gridcolor: 'rgba(255,255,255,.08)'}}), PCFG);
    }
  });
  return h;
}
function batCards(S, P){
  const tot = S.side[0] + S.side[1], sr = S.r / S.n * 100, out = [];
  const zi = S.z.indexOf(Math.max(...S.z));
  out.push(['Scoring preference', tot < 30 ? 'More evidence needed' : (S.side[1] >= S.side[0] ? 'Leg side' : 'Off side'),
    tot < 30 ? `${tot} runs in this filter` : `${pctS(Math.max(...S.side), tot).toFixed(0)}% of runs; busiest area ${LAB.zones[zi]} (${pctS(S.z[zi], tot).toFixed(0)}%)`, tot >= 30]);
  const ok = S.sty.filter(r => r[1] >= MIN).map(r => ({k: r[0], n: r[1], sr: r[2] / r[1] * 100, bpo: r[3] ? r[1] / r[3] : r[1] * 2}));
  const fav = ok.slice().sort((a, b) => b.sr - a.sr)[0], weak = ok.slice().sort((a, b) => (a.sr / sr + a.bpo / (S.n / Math.max(S.o, 1))) - (b.sr / sr + b.bpo / (S.n / Math.max(S.o, 1))))[0];
  out.push(fav && ok.length >= 2 && fav.sr > sr * 1.05 ? ['Favourable matchup', `vs ${fav.k}`, `SR ${fav.sr.toFixed(0)} against ${sr.toFixed(0)} overall, ${fav.n} balls`, true]
    : ['Favourable matchup', 'More evidence needed', `needs two bowling styles with ${MIN}+ balls and a clear gap`, false]);
  out.push(weak && ok.length >= 2 && weak !== fav ? ['Matchup to investigate', `vs ${weak.k}`, `SR ${weak.sr.toFixed(0)}, out every ${weak.bpo.toFixed(0)} balls (${weak.n} balls)`, true]
    : ['Matchup to investigate', 'More evidence needed', `needs two bowling styles with ${MIN}+ balls to compare`, false]);
  return out;
}
function bowlCards(S){
  const out = [], ec = S.r / S.n * 6;
  const hs = S.hand.filter(r => r[1] >= MIN).map(r => ({k: r[0], n: r[1], e: r[2] / r[1] * 6, w: r[3]})).sort((a, b) => a.e - b.e);
  out.push(hs.length >= 2 ? ['Best against', hs[0].k === 'RHB' ? 'Right-handers' : 'Left-handers', `econ ${hs[0].e.toFixed(2)} vs ${hs[1].e.toFixed(2)} to ${hs[1].k === 'RHB' ? 'right' : 'left'}-handers`, true]
    : ['Best against', 'More evidence needed', `needs ${MIN}+ balls to both hands`, false]);
  const ds = S.del.filter(r => r[1] >= 20).map(r => ({k: r[0], n: r[1], e: r[2] / r[1] * 6, w: r[3], bpw: r[3] ? r[1] / r[3] : 1e9}));
  const wb = ds.filter(d => d.w >= 2).sort((a, b) => a.bpw - b.bpw)[0];
  out.push(wb ? ['Wicket ball', wb.k, `a wicket every ${wb.bpw.toFixed(0)} balls (${wb.w} in ${wb.n})`, true] : ['Wicket ball', 'More evidence needed', 'no delivery with 2+ wickets in 20+ balls', false]);
  const lk = ds.sort((a, b) => b.e - a.e)[0];
  out.push(lk && lk.e > ec * 1.1 ? ['Leaks against', lk.k, `econ ${lk.e.toFixed(2)} against ${ec.toFixed(2)} overall (${lk.n} balls)`, true] : ['Leaks against', 'Nothing stands out', `no delivery 10% above his ${ec.toFixed(2)} economy`, false]);
  return out;
}
function lab(){
  const tabs = `<div class="ctrl"><div class="seg"><button data-lv="map" class="${lst.view === 'map' ? 'on' : ''}">Strengths map</button><button data-lv="rating" class="${lst.view === 'rating' ? 'on' : ''}">Rating breakdown &amp; compare</button></div></div>`;
  const body = lst.view === 'map' ? labMap() : labRating();
  setTimeout(() => {
    document.querySelectorAll('[data-lv]').forEach(b => b.onclick = () => { lst.view = b.dataset.lv; render(); });
    document.querySelectorAll('[data-ld]').forEach(b => b.onclick = () => { lst.disc = b.dataset.ld; lst.id = null; render(); });
    document.querySelectorAll('[data-lc]').forEach(b => b.onclick = () => { lst.comp = b.dataset.lc; render(); });
    document.querySelectorAll('[data-lph]').forEach(b => b.onclick = () => { lst.ph = b.dataset.lph; render(); });
    const sel = document.getElementById('lp'); if (sel) sel.onchange = e => { lst.id = +e.target.value; render(); };
  });
  return tabs + body;
}
function openLab(disc, id){ lst.view = 'map'; lst.disc = disc; lst.id = id; cur = 'lab'; try { location.hash = 'lab'; } catch (e) {} render(); }
function openSim(disc, id){ sst.mode = disc; sst.inn_ = id; sst.res = null; sst.pathRes = null; const m = SIM.matches.find(x => x.id === sst.m); cur = 'sim'; try { location.hash = 'sim'; } catch (e) {} render(); }

/* ---------------- SCOUTING ---------------- */
function scout(){
  const k = lst.gDisc, gems = SC.gems[k].filter(g => !lst.gBuy || g.avail === 'available' || g.avail === 'rumoured');
  let h = `<p class="muted" style="font-size:14px">Strike rate and economy count every ball the same. Matches are not decided that way: a single boundary at 19.4 or a dot ball to the set batter can move the result more than a whole spell. This tab looks for players whose numbers look ordinary but who keep producing those moments under pressure, then turns the auction board into a bidding plan with three fallbacks for every target.</p>
   <h2>Hidden gems</h2>
   <div class="ctrl"><div class="seg"><button data-gd="bat" class="${k === 'bat' ? 'on' : ''}">Batters</button><button data-gd="bowl" class="${k === 'bowl' ? 'on' : ''}">Bowlers</button></div>
     <div class="seg"><button data-gb="1" class="${lst.gBuy ? 'on' : ''}">RR can buy</button><button data-gb="0" class="${!lst.gBuy ? 'on' : ''}">Everyone</button></div></div>
   <div class="two"><div class="plot" id="gScat" style="height:420px"></div><div class="muted" style="font-size:13px">
     <p><b>How to read it.</b> Across: how good his ordinary scorecard is (${k === 'bat' ? 'strike rate and average' : 'economy and balls per wicket'}), as a percentile of rated players. Up: his pressure impact percentile, made of the win probability he adds per pressure ball (60%) and how often a single ball of his moves the game by 5+ points (40%), both shrunk towards zero for small samples.</p>
     <p>Players in the <b style="color:var(--gold)">top-left</b> are the gems: the scorecard says average, the match situations say otherwise. Gold dots are ones RR can bid for.</p>
     <p>A gem must be in the top 30% for pressure impact and at least 15 percentile points higher on impact than on the scorecard.</p></div></div>
   <div class="grid3" style="margin-top:12px">${gems.slice(0, 12).map(g => `<div class="card"><h4 style="font-size:20px"><span class="rank">${g.rank}</span>${esc(g.name)}</h4>
      <span class="chip">${esc(g.role)}</span><span class="chip">${esc(g.nat)}</span>${avChip(g.avail)}${tierChip(g.tier)}
      <div style="margin:8px 0 4px;font-size:12px" class="muted">Pressure impact <b>${g.imp_p}th</b> pct · scorecard <b>${g.conv_p}th</b> pct</div>
      <div style="height:6px;background:rgba(255,255,255,.08);border-radius:3px;position:relative"><div style="position:absolute;left:0;width:${g.conv_p}%;height:6px;background:#9AA3B8;border-radius:3px"></div></div>
      <div style="height:6px;background:rgba(255,255,255,.08);border-radius:3px;margin-top:3px;position:relative"><div style="position:absolute;left:0;width:${g.imp_p}%;height:6px;background:var(--pink);border-radius:3px"></div></div>
      <p class="muted" style="font-size:12.5px">${esc(g.why)}</p>
      ${g.moment ? `<div class="moment" style="padding:8px 10px;font-size:12px"><b>${esc(g.moment.date)} v ${esc(g.moment.opp)}</b> · ${esc(g.moment.situation)}: ${esc(g.moment.did)}, win chance ${esc(g.moment.wp)}. ${esc(g.moment.result)}.</div>` : ''}
      <div style="margin-top:8px;display:flex;gap:8px"><button class="go sm" data-open="${k}|${g.id}">Strengths</button>${SIM.players[g.id] && SIM.players[g.id][k] ? `<button class="go sm" data-sim="${k}|${g.id}">Simulate</button>` : ''}</div></div>`).join('') || '<div class="muted">None in this filter.</div>'}</div>
   <h2>Wider pool · beyond the usual IPL nations</h2>
   <p class="muted" style="font-size:14px">The ranking needs a lot of evidence, which favours players from the big cricket nations. This list relaxes that: it takes every batter and bowler with at least 40 pressure balls from Zimbabwe, Ireland, Bangladesh, the UAE, Scotland, the Netherlands and other nations outside the usual IPL pipeline, and orders them by pressure impact (percentile against all players). Much of their cricket is against weaker sides, so each card shows how much came against Full-member or IPL opposition and whether the impact held up there. These are calculated punts: cheap, high-upside picks for the end of the auction.</p>
   <div class="grid3">${(SC.wider[k] || []).slice(0, 12).map(w => `<div class="card"><h4 style="font-size:20px">${w.rank ? `<span class="rank">${w.rank}</span>` : ''}${esc(w.name)}</h4>
      <span class="chip">${esc(w.nat)}</span>${w.rated ? '<span class="chip">rated</span>' : '<span class="chip warn">below the rating threshold</span>'}${avChip(w.avail)}
      <div style="margin:8px 0 4px;font-size:12px" class="muted">Pressure impact <b>${w.imp_p}th</b> pct · ${w.pb} pressure balls · ${w.big} game-turning balls</div>
      <div style="height:6px;background:rgba(255,255,255,.08);border-radius:3px;position:relative"><div style="position:absolute;left:0;width:${w.imp_p}%;height:6px;background:var(--pink);border-radius:3px"></div></div>
      <div style="height:6px;background:rgba(255,255,255,.08);border-radius:3px;margin-top:3px;position:relative" title="share vs strong opposition"><div style="position:absolute;left:0;width:${w.strong_share}%;height:6px;background:var(--gold);border-radius:3px"></div></div>
      <p class="muted" style="font-size:12.5px">Scorecard: ${esc(w.conv)}. ${esc(w.note)}.</p>
      ${w.moment ? `<div class="moment" style="padding:8px 10px;font-size:12px"><b>${esc(w.moment.date)} v ${esc(w.moment.opp)}</b> · ${esc(w.moment.situation)}: ${esc(w.moment.did)}, win chance ${esc(w.moment.wp)}.</div>` : ''}
      <div style="margin-top:8px;display:flex;gap:8px">${LAB[k][w.id] ? `<button class="go sm" data-open="${k}|${w.id}">Strengths</button>` : ''}${SIM.players[w.id] && SIM.players[w.id][k] ? `<button class="go sm" data-sim="${k}|${w.id}">Simulate</button>` : ''}</div></div>`).join('')}</div>
   <div class="muted" style="font-size:12px;margin:6px 0 4px">Pink bar: pressure impact percentile. Gold bar: share of his pressure balls against Full-member or IPL opposition.</div>
   <h2>Auction plan · first choice and three backups</h2>
   <p class="muted" style="font-size:14px">No one can predict an auction room. For every player on RR's board there are three fallbacks from the same role: <b style="color:#8EF0B0">Cheap value</b> (the best-rated option other teams are unlikely to chase), <b style="color:var(--gold)">Bidding war</b> (the alternative most teams will want, so expect to pay), and <b style="color:var(--hot)">Under the radar</b> (the player whose scorecard undersells what he does under pressure). Demand is estimated from scorecard numbers, IPL experience and recent volume, because the data has no auction prices.</p>
   ${['bat', 'bowl'].map(d => `<h3 style="margin:16px 0 8px">${d === 'bat' ? 'Batters' : 'Bowlers'}</h3>` + tbl(['#', 'First choice', 'Cheap value', 'Bidding war', 'Under the radar'],
     D[d + '_board'].map(c => { const bk = SC.backups[d][c.id] || []; const cell = t => { const x = bk.find(y => y.type === t); return x ? `<td style="white-space:normal;min-width:170px"><b class="lk" data-open="${d}|${x.id}">${esc(x.name)}</b> <span class="muted">#${x.rank} · ${x.tier}</span><br><span class="muted" style="font-size:11.5px">${esc(x.why)}</span></td>` : '<td>–</td>'; };
       return `<tr><td>${c.rank}</td><td style="white-space:normal;min-width:150px"><b class="lk" data-open="${d}|${c.id}">${esc(c.name)}</b><br><span class="muted">#${c.raw_rank} · ${esc(c.role)}</span></td>${cell('Cheap value')}${cell('Bidding war')}${cell('Under the radar')}</tr>`; }))).join('')}
   <div class="muted" style="font-size:12px;margin-top:8px">Click any name to open his strengths map. Every name here can be dropped into a real RR match in the Match Simulator.</div>`;
  h += smatSection();
  setTimeout(() => {
    document.querySelectorAll('[data-gd]').forEach(b => b.onclick = () => { lst.gDisc = b.dataset.gd; render(); });
    document.querySelectorAll('[data-gb]').forEach(b => b.onclick = () => { lst.gBuy = b.dataset.gb === '1'; render(); });
    document.querySelectorAll('[data-open]').forEach(b => b.onclick = () => { const [d, id] = b.dataset.open.split('|'); openLab(d, +id); });
    document.querySelectorAll('[data-sim]').forEach(b => b.onclick = () => { const [d, id] = b.dataset.sim.split('|'); openSim(d, +id); });
    const pts = SC.scatter[k], gid = new Set(SC.gems[k].map(g => g.id));
    const buy = a => a === 'available' || a === 'rumoured';
    const grp = [['Other players', p => !gid.has(p[0]), 'rgba(201,207,221,.35)', 7], ['Gems (not buyable)', p => gid.has(p[0]) && !buy(p[5]), '#9AA3B8', 10], ['Gems RR can buy', p => gid.has(p[0]) && buy(p[5]), '#F4C542', 13]];
    Plotly.newPlot('gScat', grp.map(([n, f, c, s]) => { const q = pts.filter(f); return {type: 'scatter', mode: 'markers', name: n, x: q.map(p => p[2]), y: q.map(p => p[3]), text: q.map(p => `${p[1]} · rank ${p[4]} · ${AVL2[p[5]]}`), hovertemplate: '%{text}<br>scorecard %{x}th · pressure impact %{y}th<extra></extra>', marker: {color: c, size: s, line: {color: 'rgba(0,0,0,.4)', width: 1}}}; }),
      LAY({margin: {l: 50, r: 10, t: 10, b: 50}, xaxis: {title: 'scorecard percentile', range: [0, 101], gridcolor: 'rgba(255,255,255,.08)'}, yaxis: {title: 'pressure impact percentile', range: [0, 101], gridcolor: 'rgba(255,255,255,.08)'},
        shapes: [{type: 'line', x0: 0, y0: 15, x1: 85, y1: 100, line: {color: 'rgba(244,197,66,.5)', dash: 'dot'}}, {type: 'rect', x0: 0, x1: 55, y0: 70, y1: 101, fillcolor: 'rgba(244,197,66,.06)', line: {width: 0}}]}), PCFG);
  });
  return h;
}

/* ---------------- RETAIN & RELEASE ---------------- */
function retain(){
  const R = SC.retain, col = r => r.startsWith('Retain') ? '#8EF0B0' : r.startsWith('Release and') ? 'var(--gold)' : r === 'Review' ? 'var(--ink2)' : 'var(--hot)';
  const sum = f => R.filter(r => !String(r.actual || '').startsWith('Traded in')).filter(f).reduce((a, r) => a + (r.salary || 0), 0);
  const R0 = R.filter(r => !String(r.actual || '').startsWith('Traded in'));
  const rel = R0.filter(r => r.rec === 'Release'), rb = R0.filter(r => r.rec.startsWith('Release and')), kp = R0.filter(r => r.rec.startsWith('Retain'));
  const sq = R.filter(r => !String(r.actual || '').startsWith('Traded in'));
  const cmp = sq.filter(r => r.agree !== null && r.agree !== undefined), ag = cmp.filter(r => r.agree);
  const actCol = a => a === 'Retained' ? '#8EF0B0' : a === 'Released' ? 'var(--hot)' : 'var(--gold)';
  let h = `<div class="note" style="padding:10px 14px;margin-bottom:12px;font-size:13px"><b>RR's real decisions are in (17 Nov 2026).</b> RR kept ${sq.filter(r => r.actual === 'Retained').length}, released ${sq.filter(r => r.actual === 'Released').length}, sent Sam Curran to LSG and traded in Mohammed Shami and Manimaran Siddharth. They go to the auction with ₹${SC.purse_2027} cr. The model's call matches RR's on <b>${ag.length} of ${cmp.length}</b> players; the "What RR did" column shows where they differ.</div>
  <p class="muted" style="font-size:14px">The same lens turned on RR's own squad. For each player: what he costs, how he rates under pressure across all T20 cricket, what he actually did for RR in IPL 2025–26 pressure situations, and how much other teams are likely to want him. "Release and buy back" is a common IPL move: let a player go to free his salary, then bid for him again at a lower price, accepting that someone else may take him.</p>
   <div class="kpis" style="grid-template-columns:repeat(4,1fr)">
    <div class="kpi"><div class="l">Retain</div><div class="v">${kp.length}</div><div class="s">₹${sum(r => r.rec.startsWith('Retain')).toFixed(1)} cr kept</div></div>
    <div class="kpi"><div class="l">Release and buy back</div><div class="v">${rb.length}</div><div class="s">₹${sum(r => r.rec.startsWith('Release and')).toFixed(1)} cr freed, part spent again</div></div>
    <div class="kpi"><div class="l">Release</div><div class="v">${rel.length}</div><div class="s">₹${sum(r => r.rec === 'Release').toFixed(1)} cr freed</div></div>
    <div class="kpi"><div class="l">Real purse for 2027</div><div class="v">₹${SC.purse_2027} cr</div><div class="s">model plan would free ₹${(sum(r => r.rec.startsWith('Release')) + 1.1).toFixed(1)} cr</div></div></div>
   <div class="tbl" style="margin-top:12px;max-height:none"><table><tr><th>Player</th><th>Salary</th><th>Bat rank</th><th>Bowl rank</th><th>For RR in pressure (IPL 25–26)</th><th>Wins added</th><th>Demand</th><th>Model call</th><th>What RR did</th><th>Why (model)</th></tr>
   ${R.map(r => `<tr><td><b class="lk" data-open="${r.id_bat && (!r.id_bowl || (r.bat_rank || 999) <= (r.bowl_rank || 999)) ? 'bat|' + r.id_bat : r.id_bowl ? 'bowl|' + r.id_bowl : ''}">${esc(r.name)}</b><br><span class="muted">${esc(r.role)}</span></td>
     <td>${r.salary != null ? '₹' + r.salary + ' cr' : '–'}</td><td>${r.bat_rank || '–'}</td><td>${r.bowl_rank || '–'}</td>
     <td style="white-space:normal;min-width:150px">${r.rr_balls ? `${r.rr_runs} runs off ${r.rr_balls} balls` : ''}${r.rr_balls && r.rr_overs ? '<br>' : ''}${r.rr_overs ? `${r.rr_overs} ov, ${r.rr_conc} runs, ${r.rr_wk} wkts` : ''}${!r.rr_balls && !r.rr_overs ? '<span class="muted">did not play</span>' : ''}</td>
     <td>${r.rr_pb >= 20 ? (r.rr_wpa > 0 ? '+' : '') + (r.rr_wpa / 100).toFixed(2) : '<span class="muted">small sample</span>'}</td><td>${r.demand || '–'}</td>
     <td style="color:${col(r.rec)};font-weight:600;white-space:normal;min-width:110px">${esc(r.rec)}</td><td style="white-space:normal;min-width:100px"><b style="color:${actCol(r.actual)}">${esc(r.actual || '')}</b>${r.agree === true ? '<br><span class="muted">matches model</span>' : r.agree === false ? '<br><span style="color:var(--gold)">differs from model</span>' : ''}</td><td style="white-space:normal;min-width:260px;font-size:12px" class="muted">${esc(r.why)}</td></tr>`).join('')}</table></div>
   <div class="warnbox" style="padding:10px 14px;margin-top:12px;font-size:13px"><b>Model view, set against the real calls.</b> It weighs only pressure performance, price and likely demand. It cannot see captaincy, wicketkeeping, fitness, age, the Indian-player quota or a player's future, all of which a real retention decision has to weigh. Batting runs for RR are all IPL 2025–26 innings; "Wins added" is the win probability he added for RR on pressure balls (bat + ball), summed over IPL 2025 and 2026: +1.00 is one extra win. Salaries are RR's IPL 2026 figures from public squad lists.</div>`;
  setTimeout(() => document.querySelectorAll('[data-open]').forEach(b => b.onclick = () => { const v = b.dataset.open; if (!v) return; const [d, id] = v.split('|'); openLab(d, +id); }));
  return h;
}
