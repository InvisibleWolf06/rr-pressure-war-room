"""Stage 5: data for the Match Simulator tab.
Builds (1) per-player outcome profiles (batting and bowling), (2) a pressure-ball model,
(3) the league baseline, and (4) ball-by-ball records of every RR IPL 2025-26 match.
Usage: python -I sim_export.py <data_dir> <out_dir>   ->  out/sim.json
Outcome on a legal ball: 0,1,2,3,4,6,W (index 0..6). A player's profile is a set of ratios
(his rate / the rate the league would produce in the same phase, bowler type and competition),
shrunk hard towards 1 so small samples stay close to average.
"""
import sys, os, json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
DATA, OUT = sys.argv[1], sys.argv[2]
O = ['0', '1', '2', '3', '4', '6', 'W']
PH = ['Powerplay', 'Middle', 'Death']; TY = ['Pace', 'Spin']
YW = {2022: .55, 2023: .65, 2024: .75, 2025: .9, 2026: 1.0}
K_ALL, K_CELL, K_HP = 150, 80, 120

b = pd.read_parquet(f'{OUT}/balls.parquet')
b['phase'] = b.phase.astype(str)
b['pt'] = np.where(b.pace_or_spin == 'Spin', 'Spin', 'Pace')
L = b[b.legal].copy()
own = L.is_wicket & (L.dismissed_player_id == L.striker_id) & ~L.dismissal_type.isin(['Retire Out'])
L['o'] = np.select([own, L.runs >= 6, L.runs >= 4, L.runs == 3, L.runs == 2, L.runs == 1], [6, 5, 4, 3, 2, 1], 0)
L['ctx'] = L.phase + '|' + L.pt + '|' + np.where(L.is_ipl, 'ipl', 'int')
L['w'] = L.year.map(YW).fillna(1.0)
onehot = np.eye(7)[L.o.values]
ctx_rate = pd.DataFrame(onehot, index=L.index).groupby(L.ctx).mean()
E = ctx_rate.loc[L.ctx].values                      # expected outcome dist for each ball

# league baseline used in the sim: IPL 2025-26 (current flat-wicket conditions)
cur = L[L.is_ipl & (L.year >= 2025)]
base = {f'{p}|{t}': np.eye(7)[cur[(cur.phase == p) & (cur.pt == t)].o.values].mean(0).round(5).tolist() for p in PH for t in TY}
# extras per phase (IPL 2025-26): illegal deliveries per legal ball, and bye/leg-bye runs per legal ball
allc = b[b.is_ipl & (b.year >= 2025)]
extras = {}
for p in PH:
    a = allc[allc.phase == p]; lg = a.legal.sum()
    extras[p] = {'ill': round(float((~a.legal).sum() / lg), 4),
                 'bye': round(float(a[a.legal].extras1_runs.sum() / lg), 4)}

def ratios(keycol, mask=None):
    """hierarchical shrunk ratios per player: overall, then phase x type cells, then pressure."""
    d = L if mask is None else L[mask]
    idx = d.index
    W = d.w.values[:, None]
    obs = pd.DataFrame(onehot[L.index.get_indexer(idx)] * W, index=idx).groupby(d[keycol]).sum()
    exp = pd.DataFrame(E[L.index.get_indexer(idx)] * W, index=idx).groupby(d[keycol]).sum()
    n = exp.sum(axis=1)
    pbar = exp.div(n, axis=0)
    r_all = (obs + K_ALL * pbar) / (exp + K_ALL * pbar)
    out = {}
    cell_obs = pd.DataFrame(onehot[L.index.get_indexer(idx)] * W, index=idx).groupby([d[keycol], d.phase, d.pt]).sum()
    cell_exp = pd.DataFrame(E[L.index.get_indexer(idx)] * W, index=idx).groupby([d[keycol], d.phase, d.pt]).sum()
    # pressure modifier: on hp balls, observed vs what his own cell ratios predict
    hpm = d.hp.values
    for pid in obs.index:
        ra = r_all.loc[pid].values
        cells = {}
        for p in PH:
            for t in TY:
                if (pid, p, t) in cell_obs.index:
                    co, ce = cell_obs.loc[(pid, p, t)].values, cell_exp.loc[(pid, p, t)].values
                    pb = ce / max(ce.sum(), 1e-9)
                    cells[f'{p}|{t}'] = (co + K_CELL * pb * ra) / (ce + K_CELL * pb)
                else:
                    cells[f'{p}|{t}'] = ra
        out[pid] = {'cells': cells, 'n': float(n.loc[pid])}
    # pressure
    dd = d.assign(_hp=hpm)
    for pid, g in dd[dd._hp].groupby(keycol):
        if pid not in out:
            continue
        ii = L.index.get_indexer(g.index)
        cr = np.array([out[pid]['cells'][f'{p}|{t}'] for p, t in zip(g.phase, g.pt)])
        ex = (E[ii] * cr) ; ex = ex / ex.sum(1, keepdims=True)
        w = g.w.values[:, None]
        ob, ep = (onehot[ii] * w).sum(0), (ex * w).sum(0)
        pb = ep / ep.sum()
        out[pid]['hp'] = (ob + K_HP * pb) / (ep + K_HP * pb)
        out[pid]['hp_n'] = float(len(g))
    return out

bat_r = ratios('striker_id')
bowl_r = ratios('bowler_id')

# pressure-ball model: P(hp) from state the sim can compute
def feats(d):
    chase = (d.innings == 2).astype(float)
    bl = d.balls_left.clip(1, 120)
    need = (d.target - d.cum).where(d.innings == 2, 0).clip(lower=0)
    rrr = (need / bl * 6).where(d.innings == 2, 0).clip(0, 36)
    return np.c_[chase, bl / 120, d.wk / 10, rrr / 12, chase * rrr / 12 * (bl < 60), (d.dot_streak >= 3), d.recent_wkt.astype(float),
                 d.phase.eq('Death'), d.phase.eq('Powerplay'), chase * (rrr / 12) ** 2, chase * (bl / 120) * (d.wk / 10)]
X = feats(L); y = L.hp.values
lr = LogisticRegression(max_iter=2000, C=1.0).fit(X, y)
hp_model = {'coef': lr.coef_[0].round(4).tolist(), 'icpt': round(float(lr.intercept_[0]), 4)}
from sklearn.metrics import roc_auc_score
print('hp model AUC', round(roc_auc_score(y, lr.predict_proba(X)[:, 1]), 3))

# ---------------- RR matches ----------------
M = pd.read_csv(f'{DATA}/matches.csv')
P11 = pd.read_csv(f'{DATA}/playing_eleven.csv')
mp = pd.read_csv(f'{DATA}/competition_team_player_mapping.csv')
names = mp.drop_duplicates('player_id').set_index('player_id').player_name.to_dict()
for c in ['striker', 'non_striker', 'bowler']:
    names.update(b.drop_duplicates(f'{c}_id').set_index(f'{c}_id')[f'{c}_name'].to_dict())
RR_ID = int(M[M.home_team == 'Rajasthan Royals'].home_team_id.iloc[0])
ipl = b[b.is_ipl & (b.year >= 2025)]
rr_mids = sorted(set(ipl[(ipl.batting_team_id == RR_ID) | (ipl.bowling_team_id == RR_ID)].match_id))
def build(mids):
    matches, players = [], set()
    for mid in mids:
        g = b[b.match_id == mid].sort_values(['innings', 'innings_ball_num'])
        mrow = M[M.match_id == mid].iloc[0]
        if g.innings.max() < 2 or g.innings.max() > 2:
            continue
        inns = []
        for i in (1, 2):
            gi = g[g.innings == i]
            team = int(gi.batting_team_id.iloc[0])
            p = P11[(P11.match_id == mid) & (P11.team_id == team) & (P11.is_played.astype(str).str.lower() == 'true')].sort_values('batting_order')
            seen = list(dict.fromkeys(np.ravel(np.c_[gi.striker_id, gi.non_striker_id]).tolist()))
            order = seen + [int(x) for x in p.player_id if int(x) not in seen]
            opp = P11[(P11.match_id == mid) & (P11.team_id != team) & (P11.is_played.astype(str).str.lower() == 'true')]
            players.update(order); players.update(gi.bowler_id.astype(int)); players.update(opp.player_id.astype(int))
            inns.append({'team': 'Rajasthan Royals' if team == RR_ID else (mrow.home_team if team == mrow.home_team_id else mrow.away_team),
                         'rr': team == RR_ID, 'order': [int(x) for x in order][:12],
                         'overs': int(mrow[['first_inn_revised_overs', 'second_inn_revised_overs'][i - 1]]) if not pd.isna(mrow[['first_inn_revised_overs', 'second_inn_revised_overs'][i - 1]]) else 20,
                         # ball rows: over(1-based), striker, non-striker, bowler, bat runs, extra runs, legal, dismissed id (0 = none)
                         'b': [[int(r.overid), int(r.striker_id), int(r.non_striker_id), int(r.bowler_id), int(r.runs), int(r.tot - r.runs),
                                int(r.legal), int(r.dismissed_player_id) if r.is_wicket and not pd.isna(r.dismissed_player_id) else 0]
                               for r in gi.itertuples()],
                         'total': int(gi.tot.sum()), 'wk': int(gi.is_wicket.sum()),
                         'wp': [round(float(x), 3) for x in gi.wp_after], 'wp0': round(float(gi.wp_before.iloc[0]), 3)})
        rr_won = int(mrow.win_team_id) == RR_ID if not pd.isna(mrow.win_team_id) else None
        matches.append({'id': int(mid), 'date': str(mrow.match_date), 'season': int(g.year.iloc[0]),
                        'opp': mrow.away_team if mrow.home_team == 'Rajasthan Royals' else mrow.home_team,
                        'stage': str(mrow.stage), 'result': str(mrow.result), 'rr_won': rr_won,
                        'target': int(g[g.innings == 2].target.iloc[0]), 'revised': not pd.isna(mrow.second_inn_revised_overs),
                        'env': round(float(g.env_rpo.iloc[0]), 2), 'inns': inns})
    return matches, players
matches, players = build(rr_mids)
print('RR matches', len(matches), 'won', sum(m['rr_won'] is True for m in matches))

# candidates: top 40 of each ranking + auction boards
dd = json.load(open(f'{OUT}/dashboard_data.json'))
bf = pd.read_csv(f'{OUT}/bat_final.csv', index_col=0).sort_values('s_rank')
wf = pd.read_csv(f'{OUT}/bowl_final.csv', index_col=0).sort_values('s_rank')
AV = pd.read_csv(f'{OUT}/availability.csv').drop_duplicates('player_id').set_index('player_id')
SCW = json.load(open(f'{OUT}/scout.json')).get('wider', {}) if os.path.exists(f'{OUT}/scout.json') else {}
cand_bat = bf.index.tolist() + [w['id'] for w in SCW.get('bat', []) if w['id'] not in bf.index]
cand_bowl = wf.index.tolist() + [w['id'] for w in SCW.get('bowl', []) if w['id'] not in wf.index]
players.update(cand_bat); players.update(cand_bowl)
ptype = L.groupby('bowler_id').pt.agg(lambda s: s.mode().iloc[0])
def pack(r):
    d = {'c': {k: [round(float(x), 3) for x in v] for k, v in r['cells'].items()}, 'n': round(r['n'])}
    if 'hp' in r:
        d['hp'] = [round(float(x), 3) for x in r['hp']]; d['hpn'] = int(r['hp_n'])
    return d
prof = {}
for p in players:
    p = int(p)
    e = {'name': names.get(p, str(p))}
    if p in bat_r: e['bat'] = pack(bat_r[p])
    if p in bowl_r and bowl_r[p]['n'] >= 60: e['bowl'] = pack(bowl_r[p]); e['type'] = ptype.get(p, 'Pace')
    if p in bf.index: e['bat_rank'] = int(bf.loc[p].s_rank); e['bat_prr'] = round(float(bf.loc[p].s_PRR), 1)
    if p in wf.index: e['bowl_rank'] = int(wf.loc[p].s_rank); e['bowl_prr'] = round(float(wf.loc[p].s_PRR), 1)
    if p in AV.index: e['avail'] = AV.loc[p].status
    prof[str(p)] = e

# head-to-head history (all formats) for any pair we may show
h2h = L[L.striker_id.isin(players) & L.bowler_id.isin(players)].groupby(['striker_id', 'bowler_id']).agg(
    n=('o', 'size'), r=('runs', 'sum'), w=('o', lambda s: int((s == 6).sum())), d=('o', lambda s: int((s == 0).sum())))
h2h = {f'{int(a)}-{int(c)}': [int(v.n), int(v.r), int(v.w), int(v.d)] for (a, c), v in h2h.iterrows() if v.n >= 3}

if '--val' in sys.argv:
    vm, vp = build(sorted(set(ipl.match_id)))
    vprof = {}
    for p in vp | players:
        p = int(p); e = {'name': names.get(p, str(p))}
        if p in bat_r: e['bat'] = pack(bat_r[p])
        if p in bowl_r and bowl_r[p]['n'] >= 60: e['bowl'] = pack(bowl_r[p]); e['type'] = ptype.get(p, 'Pace')
        vprof[str(p)] = e
    wp = ipl.set_index(['match_id', 'innings', 'innings_ball_num']).wp_before
    json.dump({'base': base, 'extras': extras, 'hp_model': hp_model, 'matches': vm, 'players': vprof}, open(f'{OUT}/sim_val.json', 'w'))
    ipl[['match_id', 'innings', 'innings_ball_num', 'wp_before', 'bat_win', 'batting_team_id']].to_csv(f'{OUT}/sim_val_wp.csv', index=False)
sim = {'alpha': 1.0, 'inn_sd': 0.2, 'bscale': 0.93, 'O': O, 'base': base, 'extras': extras, 'hp_model': hp_model, 'matches': matches, 'players': prof,
       'cand_bat': [int(x) for x in cand_bat], 'cand_bowl': [int(x) for x in cand_bowl], 'h2h': h2h,
       'ipl_rpo': round(float(allc.tot.sum() / allc.legal.sum() * 6), 3)}
if os.path.exists(f'{OUT}/sim_validation.json'):   # written by: node simval.js out/sim_val.json out/sim_val_wp.csv out/sim_validation.json
    sim['validation'] = json.load(open(f'{OUT}/sim_validation.json'))
json.dump(sim, open(f'{OUT}/sim.json', 'w'), separators=(',', ':'))
import os
print('sim.json KB', os.path.getsize(f'{OUT}/sim.json') // 1024, 'players', len(prof), 'h2h', len(h2h))
