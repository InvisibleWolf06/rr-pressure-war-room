/* RR Match Simulator engine: ball-by-ball Monte Carlo from any moment of a real match.
   Works in the browser (window.RRSim) and in node (module.exports) so it can be validated offline. */
(function (root) {
  function rng(seed) { let a = seed >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const phaseOf = (legal) => legal < 36 ? 'Powerplay' : legal < 90 ? 'Middle' : 'Death';
  const RUNS = [0, 1, 2, 3, 4, 6];

  function make(S) {
    const P = S.players;
    const ones = [1, 1, 1, 1, 1, 1, 1];
    const cell = (pr, key) => (pr && pr.c[key]) || ones;
    const hpv = (pr) => (pr && pr.hp) || ones;
    const btype = (id) => (P[id] && P[id].type) || 'Pace';
    const hm = S.hp_model;
    function pHP(st) {
      const chase = st.inn === 2 ? 1 : 0, bl = Math.max(1, st.maxBalls - st.legal);
      const need = chase ? Math.max(0, st.target - st.score) : 0;
      const rrr = chase ? Math.min(36, need / bl * 6) : 0;
      const x = [chase, bl / 120, st.wk / 10, rrr / 12, chase * rrr / 12 * (bl < 60 ? 1 : 0), st.dots >= 3 ? 1 : 0,
        (st.legal - st.lastWk) <= 6 ? 1 : 0, st.legal >= 90 ? 1 : 0, st.legal < 36 ? 1 : 0, chase * (rrr / 12) ** 2, chase * (bl / 120) * (st.wk / 10)];
      let z = hm.icpt; for (let i = 0; i < x.length; i++) z += hm.coef[i] * x[i];
      return 1 / (1 + Math.exp(-z));
    }
    function dist(bat, bowl, st) {
      const key = phaseOf(st.legal) + '|' + btype(bowl);
      const base = S.base[key], a = cell(P[bat] && P[bat].bat, key), w = cell(P[bowl] && P[bowl].bowl, key);
      const p = pHP(st), ha = hpv(P[bat] && P[bat].bat), hw = hpv(P[bowl] && P[bowl].bowl);
      const d = new Array(7); let s = 0; const al = S.alpha == null ? 1 : S.alpha, f = st.form || 1;
      for (let o = 0; o < 7; o++) {
        let v = base[o] * Math.pow(a[o] * w[o] * (1 + p * (ha[o] - 1)) * (1 + p * (hw[o] - 1)), al);
        if (o === 4 || o === 5) v *= f * (S.bscale || 1); else if (o === 6) v /= f;
        d[o] = v; s += v;
      }
      for (let o = 0; o < 7; o++) d[o] /= s;
      return d;
    }
    function stateAt(inn, k, target) {
      const st = { score: 0, wk: 0, legal: 0, dots: 0, lastWk: -99, out: new Set(), striker: inn.order[0], non: inn.order[1],
        maxBalls: inn.overs * 6, target: target, used: new Set() };
      for (let i = 0; i < k; i++) {
        const [ov, s, n, bw, r, x, lg, dis] = inn.b[i];
        st.used.add(s); st.used.add(n);
        st.score += r + x; if (lg) st.legal++;
        if (dis) { st.wk++; st.out.add(dis); st.lastWk = st.legal; st.dots = 0; } else if (lg) st.dots = (r + x === 0) ? st.dots + 1 : 0;
      }
      if (k < inn.b.length) { st.striker = inn.b[k][1]; st.non = inn.b[k][2]; } else { st.striker = null; st.non = null; }
      st.used.add(st.striker); st.used.add(st.non);
      return st;
    }
    const clone = st => Object.assign({}, st, { out: new Set(st.out), used: new Set(st.used) });

    function playInnings(st, order, bowlerFor, R, track, onBall) {
      const nextBat = () => { for (const p of order) if (!st.used.has(p) && !st.out.has(p)) { st.used.add(p); return p; } return null; };
      if (st.striker == null || st.out.has(st.striker)) st.striker = nextBat();
      if (st.non == null || st.out.has(st.non)) st.non = nextBat();
      if (st.form == null) { const sd = S.inn_sd || 0; const z = Math.sqrt(-2 * Math.log(R() + 1e-12)) * Math.cos(2 * Math.PI * R()); st.form = Math.exp(sd * z); }
      const lim = order.length >= 11 ? 10 : Math.max(order.length - 1, 1);
      while (st.legal < st.maxBalls && st.wk < lim && st.striker != null) {
        if (st.inn === 2 && st.score >= st.target) break;
        const ov = Math.floor(st.legal / 6) + 1, bw = bowlerFor(ov);
        const ex = S.extras[phaseOf(st.legal)];
        if (R() < ex.ill / (1 + ex.ill)) { st.score += 1; if (track) track(st, bw, -1, 1, 0); continue; }
        const d = dist(st.striker, bw, st);
        let u = R(), o = 0; while (o < 6 && u > d[o]) { u -= d[o]; o++; }
        const bat = st.striker;
        st.legal++;
        let ev = 0;
        if (o === 6) {
          if (track) track(st, bw, 6, 0, 1);
          st.out.add(st.striker); st.wk++; st.lastWk = st.legal; st.dots = 0; ev = 'W';
          st.striker = nextBat();
        } else {
          const r = RUNS[o], bye = (r === 0 && R() < ex.bye) ? 1 : 0;
          if (track) track(st, bw, o, r + bye, 0);
          st.score += r + bye; st.dots = (r + bye === 0) ? st.dots + 1 : 0; ev = r >= 4 ? r : 0;
          if ((r + bye) % 2 === 1) { const t = st.striker; st.striker = st.non; st.non = t; }
        }
        if (st.legal % 6 === 0) { const t = st.striker; st.striker = st.non; st.non = t; }
        if (onBall) onBall(st, ev, bat, bw);
      }
      return st;
    }
    function bowlerPlan(inn, swapOut, swapIn, fromOver) {
      const plan = {}, count = {};
      for (const b of inn.b) plan[b[0]] = b[3];
      const ids = Object.values(plan);
      for (const id of ids) count[id] = 0;
      for (const ov in plan) count[plan[ov]]++;
      return function (ov) {
        let id = plan[ov];
        if (id == null) {
          let best = null; for (const k in count) if (count[k] < 4 && (best == null || count[k] < count[best])) best = k;
          id = +(best || ids[ids.length - 1]); plan[ov] = id; count[id] = (count[id] || 0) + 1;
        }
        if (swapOut && id === swapOut && ov >= fromOver) return swapIn;
        return id;
      };
    }
    const swapOrder = (inn, opts) => (!opts || !opts.bat || !inn.rr) ? inn.order : inn.order.map(p => p === opts.bat.out ? opts.bat.in : p);

    // starting snapshot at ball k of innings startInn, with the swap applied
    function initial(m, startInn, k, opts) {
      const I = m.inns[startInn - 1];
      const st = stateAt(I, k, startInn === 2 ? (m.target || m.inns[0].total + 1) : null); st.inn = startInn;
      if (opts && opts.bat && I.rr) { if (st.striker === opts.bat.out) st.striker = opts.bat.in; if (st.non === opts.bat.out) st.non = opts.bat.in; }
      st.fromOv = k < I.b.length ? I.b[k][0] : 99;
      return st;
    }
    // play the match out from a snapshot; returns totals
    function finish(m, snap, opts, R, track, onBall) {
      const i1 = m.inns[0], i2 = m.inns[1];
      const bo = opts && opts.bowl ? opts.bowl : null;
      let st = clone(snap), t1;
      if (st.inn === 1) {
        const bf = bowlerPlan(i1, bo && !i1.rr ? bo.out : null, bo ? bo.in : null, st.fromOv);
        playInnings(st, swapOrder(i1, opts), bf, R, track, onBall); t1 = st.score;
        const s2 = stateAt(i2, 0, t1 + 1); s2.inn = 2; s2.fromOv = 1;
        if (opts && opts.bat && i2.rr) { const o2 = swapOrder(i2, opts); s2.striker = o2[0]; s2.non = o2[1]; }
        if (onBall) onBall(s2, 'start', null, null);
        st = s2;
        const bf2 = bowlerPlan(i2, bo && !i2.rr ? bo.out : null, bo ? bo.in : null, 1);
        playInnings(st, swapOrder(i2, opts), bf2, R, track, onBall);
        return { t1, t2: st.score, tgt: t1 + 1, wk2: st.wk };
      }
      t1 = i1.total;
      const bf2 = bowlerPlan(i2, bo && !i2.rr ? bo.out : null, bo ? bo.in : null, st.fromOv);
      playInnings(st, swapOrder(i2, opts), bf2, R, track, onBall);
      return { t1, t2: st.score, tgt: st.target, wk2: st.wk };
    }
    function rrWins(m, o) { const rrIdx = m.inns[0].rr ? 0 : 1; if (o.t2 === o.tgt - 1) return 0.5; return ((rrIdx === 1) === (o.t2 >= o.tgt)) ? 1 : 0; }

    function run(m, startInn, k, opts, n, seed) {
      const rrIdx = m.inns[0].rr ? 0 : 1;
      const res = { margin: [0, 0, 0, 0, 0, 0, 0], rrWin: 0, tie: 0, rrTot: [], oppTot: [], cand: { runs: 0, balls: 0, outs: 0, conc: 0, legal: 0, wk: 0 } };
      const W = opts && opts.watch;
      const track = !W ? null : (st, bw, o, r, w) => {
        if (W.kind === 'bat' && st.striker === W.id && o >= 0) { res.cand.balls++; res.cand.runs += (o < 6 ? RUNS[o] : 0); res.cand.outs += w; }
        if (W.kind === 'bowl' && bw === W.id) { res.cand.conc += r; if (o >= 0) res.cand.legal++; res.cand.wk += w; }
      };
      const snap = initial(m, startInn, k, opts);
      for (let s = 0; s < n; s++) {
        const R = rng(seed + s * 7919);
        const o = finish(m, snap, opts, R, track);
        record(res, rrIdx, o.t1, o.t2, o.tgt, o.wk2);
      }
      res.n = n; res.p = (res.rrWin + 0.5 * res.tie) / n;
      return res;
    }
    function record(res, rrIdx, t1, t2, tgt, wk2) {
      const chaseWon = t2 >= tgt, tie = t2 === tgt - 1;
      const runsBy = tgt - 1 - t2, wkIn = 10 - wk2;
      let mb;
      if (tie) mb = 3;
      else if (chaseWon) { const g = wkIn >= 7 ? 2 : wkIn >= 4 ? 1 : 0; mb = rrIdx === 1 ? 4 + g : 2 - g; }
      else { const g = runsBy >= 25 ? 2 : runsBy >= 10 ? 1 : 0; mb = rrIdx === 0 ? 4 + g : 2 - g; }
      res.margin[mb]++;
      if (tie) res.tie++; else if ((rrIdx === 1) === chaseWon) res.rrWin++;
      res.rrTot.push(rrIdx === 0 ? t1 : t2); res.oppTot.push(rrIdx === 0 ? t2 : t1);
    }

    /* one replay traced ball by ball, with RR's win chance re-estimated (nIn quick replays) after every ball */
    function path(m, startInn, k, opts, seed, nIn) {
      const snaps = [], evs = [];
      const snap0 = initial(m, startInn, k, opts);
      const R = rng(seed);
      snaps.push(clone(snap0)); evs.push(0);
      const o = finish(m, snap0, opts, R, null, (st, ev) => { const c = clone(st); c.form = null; snaps.push(c); evs.push(ev); });
      const pts = [];
      for (let i = 0; i < snaps.length; i++) {
        const s = snaps[i];
        let x = (s.inn - 1) * 20 + s.legal / 6;
        let w = 0;
        const done = s.inn === 2 && (s.score >= s.target || s.legal >= s.maxBalls || s.wk >= 10);
        if (done) w = rrWins(m, { t2: s.score, tgt: s.target });
        else { for (let j = 0; j < nIn; j++) w += rrWins(m, finish(m, s, opts, rng(seed * 31 + i * 977 + j * 7))); w /= nIn; }
        pts.push({ x, wp: w, ev: evs[i], score: s.score, wk: s.wk, inn: s.inn });
      }
      return { pts, final: o, rrWon: rrWins(m, o) };
    }
    return { run, stateAt, dist, pHP, phaseOf, path, rrWins };
  }
  const api = { make };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.RRSim = api;
})(typeof window !== 'undefined' ? window : this);
