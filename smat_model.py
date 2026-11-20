"""SMAT pressure model: environment, win probability, leverage, pressure balls, expected outcomes,
domestic pressure rating (DPR), impact, best moments.
Usage: python -I smat_model.py <out_dir>  ->  out/smat_bat.csv, out/smat_bowl.csv, out/smat_validation.json, out/smat_balls_scored.parquet"""
import sys, json, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor as HGB, HistGradientBoostingClassifier as HGBC
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
OUT = sys.argv[1]
b = pd.read_parquet(f'{OUT}/smat_balls.parquet')
M = pd.read_csv(f'{OUT}/smat_matches.csv')
ok = M[(~M.revised) & M.result.isin(['win', 'tie']) & (M.n_inn == 2)].match_id
b = b[b.match_id.isin(ok)].copy()
b = b.sort_values(['match_id', 'innings', 'over', 'legal_before']).reset_index(drop=True)
b['seq'] = b.groupby(['match_id', 'innings']).cumcount()
g = b.groupby(['match_id', 'innings'])
b['score'] = g.tot.cumsum() - b.tot
b['wk'] = g.is_wicket.cumsum() - b.is_wicket.astype(int)
tot = b.groupby(['match_id', 'innings']).tot.sum().unstack()
b['target'] = np.where(b.innings == 2, b.match_id.map(tot[1]) + 1, np.nan)
b['bl'] = (120 - b.legal_before).clip(lower=0)
b['phase'] = np.select([b.legal_before < 36, b.legal_before < 90], ['Powerplay', 'Middle'], 'Death')
# ---------- scoring environment: season run rate + venue effect shrunk with 6 matches of prior weight
SW = {'2015/16': .35, '2017/18': .4, '2018/19': .45, '2019/20': .55, '2020/21': .65, '2021/22': .8, '2022/23': .9, '2023/24': 1.0, '2024/25': 1.0}
ms = b.groupby('match_id').agg(season=('season', 'first'), venue=('venue', 'first'), runs=('tot', 'sum'), lg=('legal', 'sum'))
ms['rpo'] = ms.runs / ms.lg * 6
srpo = ms.groupby('season').apply(lambda d: d.runs.sum() / d.lg.sum() * 6)
ms['dev'] = ms.rpo - ms.season.map(srpo)
vd = ms.groupby('venue').dev.agg(['sum', 'count']); vfx = vd['sum'] / (vd['count'] + 6)
ms['env'] = ms.season.map(srpo) + ms.venue.map(vfx).fillna(0)
b['env'] = b.match_id.map(ms.env)
# ---------- expected remaining runs (first-innings resource curve)
fin = b.match_id.map(tot[1]).where(b.innings == 1, b.match_id.map(tot[2]))
i1 = b[(b.innings == 1)]
Xr = lambda d: np.c_[d.bl, d.wk, d.env]
rem = HGB(max_iter=300, learning_rate=.05, monotonic_cst=[1, -1, 1], early_stopping=False, random_state=7).fit(Xr(i1), (fin - b.score)[i1.index])
def exp_rem(bl, wk, env):
    out = rem.predict(np.c_[bl, wk, env]); return np.where((bl <= 0) | (wk >= 10), 0, np.maximum(out, 0))
par = LogisticRegression  # placeholder name kept simple below
# ---------- win probability: logistic on resource margin (deliberately smooth)
def feats_chase(score, wk, bl, target, env):
    need = target - score; er = exp_rem(bl, wk, env)
    m = (er - need) / (np.sqrt(np.maximum(bl, 1)) * 2.2 + 4)
    return np.c_[m, m * bl / 120, (10 - wk) / 10, bl / 120]
def feats_first(score, wk, bl, env):
    proj = score + exp_rem(bl, wk, env); parv = env * 20 / 6 * 1.0
    d = (proj - parv) / (np.sqrt(np.maximum(bl, 1)) * 2.2 + 12)
    return np.c_[d, d * bl / 120, bl / 120]
mw = M.set_index('match_id')
b['bat_won'] = np.where(b.result == 'tie', np.nan, (b.winner == b.bat_team).astype(float))
c2 = b[(b.innings == 2) & b.bat_won.notna()]
lr2 = LogisticRegression(C=10, max_iter=2000).fit(feats_chase(c2.score, c2.wk, c2.bl, c2.target, c2.env), c2.bat_won)
c1 = b[(b.innings == 1) & b.bat_won.notna()]
lr1 = LogisticRegression(C=10, max_iter=2000).fit(feats_first(c1.score, c1.wk, c1.bl, c1.env), c1.bat_won)
def wp(inn, score, wk, bl, target, env):
    """P(batting side wins) for a state; vectorised; handles finished chases."""
    inn = np.asarray(inn); score = np.asarray(score, float); wk = np.asarray(wk, float); bl = np.asarray(bl, float)
    target = np.asarray(target, float); env = np.asarray(env, float)
    out = np.empty(len(score))
    m2 = inn == 2
    if m2.any():
        p = lr2.predict_proba(feats_chase(score[m2], wk[m2], bl[m2], target[m2], env[m2]))[:, 1]
        done_win = score[m2] >= target[m2]; done_lose = (~done_win) & ((wk[m2] >= 10) | (bl[m2] <= 0))
        tie = done_lose & (score[m2] == target[m2] - 1)
        p = np.where(done_win, 1.0, np.where(tie, .5, np.where(done_lose, 0.0, p)))
        out[m2] = p
    if (~m2).any():
        out[~m2] = lr1.predict_proba(feats_first(score[~m2], np.minimum(wk[~m2], 10), bl[~m2], env[~m2]))[:, 1]
    return out
b['wp0'] = wp(b.innings, b.score, b.wk, b.bl, b.target, b.env)
b['wp1'] = wp(b.innings, b.score + b.tot, b.wk + b.is_wicket, b.bl - b.legal.astype(int), b.target, b.env)
# end of first innings: carry the next state (start of chase) for the last ball, in batting-first perspective
last1 = (b.innings == 1) & (b.seq == b.groupby(['match_id', 'innings']).seq.transform('max'))
s2 = wp(np.full(last1.sum(), 2), np.zeros(last1.sum()), np.zeros(last1.sum()), np.full(last1.sum(), 120.), (b.score + b.tot)[last1] + 1, b.env[last1])
b.loc[last1, 'wp1'] = 1 - s2
b['wpa'] = b.wp1 - b.wp0
# ---------- leverage: expected |swing| over the seven outcomes (phase-specific outcome mix)
L = b.legal
oc = [0, 1, 2, 3, 4, 6]
mix = {}
for ph, d in b[L].groupby('phase'):
    w = d.is_wicket.mean(); r = d[~d.is_wicket].runs.clip(upper=6).replace(5, 4).value_counts(normalize=True)
    mix[ph] = [(o, (1 - w) * r.get(o, 0)) for o in oc] + [('W', w)]
li = np.zeros(len(b))
for ph, lst in mix.items():
    m = (b.phase == ph).values
    base = b.wp0.values[m]
    for o, p in lst:
        if o == 'W': w1 = wp(b.innings.values[m], b.score.values[m], b.wk.values[m] + 1, b.bl.values[m] - 1, b.target.values[m], b.env.values[m])
        else: w1 = wp(b.innings.values[m], b.score.values[m] + o, b.wk.values[m], b.bl.values[m] - 1, b.target.values[m], b.env.values[m])
        li[m] += p * np.abs(w1 - base)
b['li'] = li / b.groupby('innings').li.transform('mean') if 'li' in b else 0
b['li'] = li; b['li'] = b.li / b.groupby('innings').li.transform('mean')
# dots before the ball and wicket in the previous six balls
dot = ((b.tot == 0) & b.legal).astype(int)
grp = (dot == 0).groupby([b.match_id, b.innings]).cumsum()
streak = dot.groupby([b.match_id, b.innings, grp]).cumsum()
b['dot_streak'] = streak.groupby([b.match_id, b.innings]).shift(1).fillna(0)
w = b.is_wicket.astype(int)
b['recent_wkt'] = w.groupby([b.match_id, b.innings]).transform(lambda s: s.shift(1).rolling(6, min_periods=1).sum()).fillna(0) > 0
b['pi'] = b.li * np.where(b.dot_streak >= 3, 1.2, 1) * np.where(b.recent_wkt, 1.2, 1)
thr = b[L].pi.quantile(.8); b['hp'] = b.pi >= thr
# ---------- expected outcomes on legal balls
lg = b[L].copy()
lg['own_out'] = lg.is_wicket & (lg.player_out == lg.batter) & (lg.kind != 'run out')
lg['bwk'] = lg.is_wicket & ~lg.kind.isin(['run out', 'retired hurt', 'retired out', 'obstructing the field'])
lg['isdot'] = lg.tot == 0
need = (lg.target - lg.score).fillna(0); rrr = np.where(lg.innings == 2, need / np.maximum(lg.bl, 1) * 6, 0)
X = np.c_[lg.innings, lg.legal_before, lg.wk, lg.env, rrr]
def fit(y, clf=False):
    mdl = (HGBC if clf else HGB)(max_iter=250, learning_rate=.05, early_stopping=False, random_state=7).fit(X, y)
    return mdl.predict_proba(X)[:, 1] if clf else mdl.predict(X)
lg['x_runs'] = fit(lg.runs); lg['x_out'] = fit(lg.own_out, True); lg['x_dot'] = fit(lg.isdot, True); lg['x_bwk'] = fit(lg.bwk, True); lg['x_tot'] = fit(lg.tot)
lg['w'] = lg.season.map(SW)
# ---------- ratings
def shrink(A, H, n, npb, kA=300, kH=200):
    return A * n / (n + kA) + (H - A) * npb / (npb + kH)
recent = lg[lg.season.isin(['2021/22', '2022/23', '2023/24', '2024/25'])]
def rate(kind):
    pid, nm = ('batter_id', 'batter') if kind == 'bat' else ('bowler_id', 'bowler')
    d = lg.copy()
    if kind == 'bat':
        d['v_run'] = d.runs - d.x_runs; d['v_out'] = d.x_out - d.own_out; d['v_dot'] = d.x_dot - d.isdot; d['imp'] = d.wpa
    else:
        d['v_run'] = d.x_tot - d.tot; d['v_out'] = d.bwk - d.x_bwk; d['v_dot'] = d.isdot - d.x_dot; d['imp'] = -d.wpa
    d['turn'] = (d.imp >= .05).astype(int)
    comps = ['v_run', 'v_out', 'v_dot']
    def wmean(x, c): return (x[c] * x.w).sum() / x.w.sum()
    rows = []
    for p, x in d.groupby(pid):
        h = x[x.hp]
        if len(h) < (40 if kind == 'bat' else 60): continue
        if not x.season.isin(['2021/22', '2022/23', '2023/24', '2024/25']).any(): continue
        r = {'id': p, 'name': x[nm].iloc[0], 'team': (x.bat_team if kind == 'bat' else x.bowl_team).mode().iloc[0], 'n': len(x), 'np': len(h),
             'last': x.season.max(), 'matches': x.match_id.nunique()}
        for c in comps: r[c] = shrink(wmean(x, c), wmean(h, c), x.w.sum(), h.w.sum())
        r['impact'] = (h.imp * h.w).sum() / (h.w.sum() + 60) * 100
        r['turn'] = (h.turn * h.w).sum() / (h.w.sum() + 60) * 100
        r['big'] = int(h.turn.sum())
        if kind == 'bat':
            r['runs'] = int(x.runs.sum()); r['balls'] = len(x); r['outs'] = int(x.own_out.sum())
            r['sr'] = x.runs.sum() / len(x) * 100; r['avg'] = x.runs.sum() / max(x.own_out.sum(), 1)
            r['hp_sr'] = h.runs.sum() / len(h) * 100; r['hp_xsr'] = h.x_runs.sum() / len(h) * 100
            r['hp_dot'] = h.isdot.mean() * 100; r['hp_xdot'] = h.x_dot.mean() * 100
        else:
            r['conc'] = int(x.tot.sum()); r['wk'] = int(x.bwk.sum()); r['econ'] = x.tot.sum() / len(x) * 6; r['bpw'] = len(x) / max(x.bwk.sum(), 1)
            r['hp_econ'] = h.tot.sum() / len(h) * 6; r['hp_xecon'] = h.x_tot.sum() / len(h) * 6
            r['hp_dot'] = h.isdot.mean() * 100; r['hp_xdot'] = h.x_dot.mean() * 100
        rows.append(r)
    R = pd.DataFrame(rows).set_index('id')
    W = {'v_run': .25, 'v_out': .15, 'v_dot': .15, 'impact': .30, 'turn': .15}
    z = sum(((R[c] - R[c].mean()) / R[c].std()) * wt for c, wt in W.items())
    R['DPR'] = 50 + 10 * (z - z.mean()) / z.std()
    R['rank'] = R.DPR.rank(ascending=False, method='first').astype(int)
    pct = lambda s, asc=True: s.rank(pct=True, ascending=asc)
    R['conv_p'] = ((pct(R.sr) + pct(R.avg)) / 2 if kind == 'bat' else (pct(R.econ, False) + pct(R.bpw, False)) / 2) * 100
    R['imp_p'] = (pct(R.impact) * .6 + pct(R.turn) * .4) * 100
    R['gem'] = (R.imp_p >= 70) & (R.imp_p - R.conv_p >= 15)
    return R.sort_values('rank'), d
RB, db = rate('bat'); RW, dw = rate('bowl')

# ---------- split-half reliability (odd/even matches) of DPR
def halves(kind, R):
    pid = 'batter_id' if kind == 'bat' else 'bowler_id'
    out = []
    for par_ in (0, 1):
        sub = lg[lg.match_id % 2 == par_]
        d = sub.copy()
        if kind == 'bat': d['v'] = (d.runs - d.x_runs) + 0.0; d['imp'] = d.wpa
        else: d['v'] = d.x_tot - d.tot; d['imp'] = -d.wpa
        h = d[d.hp]
        s = h.groupby(pid).apply(lambda x: (x.imp * x.w).sum() / (x.w.sum() + 60) * 100) + h.groupby(pid).v.mean().reindex(h[pid].unique()).fillna(0) * 0
        out.append(s)
    j = pd.concat(out, axis=1).dropna(); j = j[j.index.isin(R.index)]
    return round(float(j.corr(method='spearman').iloc[0, 1]), 3), len(j)
vb, nb = halves('bat', RB); vw, nw = halves('bowl', RW)
y2 = c2.bat_won; p2 = wp(c2.innings, c2.score, c2.wk, c2.bl, c2.target, c2.env)
y1 = c1.bat_won; p1 = wp(c1.innings, c1.score, c1.wk, c1.bl, c1.target, c1.env)
V = {'chase_auc': round(roc_auc_score(y2, p2), 3), 'chase_brier': round(brier_score_loss(y2, p2), 3),
     'first_auc': round(roc_auc_score(y1, p1), 3), 'thr': round(float(thr), 3), 'impact_split_half': {'bat': [vb, nb], 'bowl': [vw, nw]},
     'matches': int(b.match_id.nunique()), 'balls': int(L.sum()), 'seasons': sorted(b.season.unique().tolist()),
     'death_share_of_hp': round(float(b[L & b.hp].phase.eq('Death').mean()), 3),
     'hp_share_by_phase': {f'{i}|{p}': round(float(v), 3) for (i, p), v in b[L].groupby(['innings', 'phase']).hp.mean().items()}}
print(json.dumps(V, indent=1))
RB.to_csv(f'{OUT}/smat_bat.csv'); RW.to_csv(f'{OUT}/smat_bowl.csv'); json.dump(V, open(f'{OUT}/smat_validation.json', 'w'))
b.to_parquet(f'{OUT}/smat_balls_scored.parquet')
for k, R in (('bat', RB), ('bowl', RW)):
    print(k, len(R)); print(R.head(20)[['name', 'team', 'DPR', 'np', 'impact', 'big', 'conv_p', 'imp_p', 'last']].round(2).to_string())
