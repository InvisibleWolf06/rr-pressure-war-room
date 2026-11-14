"""Stage 2: pressure moments (episodes), player ratings, roles, shot/delivery DNA, reliability.
Usage: python -I moments.py <data_dir> <out_dir>
"""
import sys, json, numpy as np, pandas as pd
D, OUT = sys.argv[1], sys.argv[2]
rng = np.random.default_rng(7)
b = pd.read_parquet(f'{OUT}/balls.parquet')
mp = pd.read_csv(f'{D}/competition_team_player_mapping.csv')
teams = pd.read_csv(f'{D}/teams.csv').drop_duplicates('team_id').set_index('team_id').team_name

REC = {2022: .55, 2023: .65, 2024: .80, 2025: .90, 2026: 1.0}
TIER_W = {'IPL': 1.0, 'Full': 1.0, 'Semi': .8, 'A': .75, 'Assoc': .5}
b['bat_team'] = b.batting_team_id.map(teams)
b['bowl_team'] = b.bowling_team_id.map(teams)
home_bat = b.batting_team_id == b.home_team_id
b['bat_tier'] = np.where(home_bat, b.home_tier, b.away_tier)
b['bowl_tier'] = np.where(home_bat, b.away_tier, b.home_tier)
b['ko'] = (b.knock_out == 1) | b.stage.isin(['Final', 'Qualifier', 'Eliminator', 'Semi Final', 'Super 4'])
b['over_str'] = (b.lb // 6).astype(str) + '.' + (b.lb % 6).astype(str)
b['cn'] = b.wpa_bat / b.LI          # context-neutral batting value
b['cnb'] = b.wpa_bowl / b.LI        # context-neutral bowling value
b['env_sr'] = b.env_rpo / 6 * 100   # environment strike rate (flat-wicket factor)
b['own_out'] = b.is_wicket & (b.dismissed_player_id == b.striker_id)


def situation(r):
    s = f"{r.bat_team} {int(r.cum)}/{int(r.wk)} after {r.over_str} ov"
    if r.Index[1] == 2 if isinstance(r.Index, tuple) else r.innings == 2:
        s += f", need {int(r.target - r.cum)} off {int(r.balls_left)}"
    else:
        s += f" (batting first, par ~{int(round(r.env_par))})"
    return s

# ---------------- batting episodes ----------------
b['bseq'] = b.groupby(['match_id', 'innings', 'striker_id']).cumcount()
first_hp = b[b.hp].groupby(['match_id', 'innings', 'striker_id']).bseq.min().rename('first_hp')
bb = b.join(first_hp, on=['match_id', 'innings', 'striker_id'])
bb = bb[bb.first_hp.notna() & (bb.bseq >= bb.first_hp)]
agg = bb.groupby(['match_id', 'innings', 'striker_id']).agg(
    hp_balls=('hp', 'sum'), wpa=('wpa_bat', 'sum'), runs=('runs', 'sum'),
    balls=('legal', 'sum'), out=('is_wicket', lambda s: 0), wp0=('wp_before', 'first'),
    env_sr=('env_sr', 'first'))
outs = b[b.is_wicket & (b.dismissed_player_id == b.striker_id)].groupby(['match_id', 'innings', 'striker_id']).size()
agg['out'] = agg.index.map(outs).fillna(0).astype(int).values
full = b.groupby(['match_id', 'innings', 'striker_id']).agg(inn_runs=('runs', 'sum'), inn_balls=('legal', 'sum'))
agg = agg.join(full)
lastrow = bb.groupby(['match_id', 'innings', 'striker_id']).tail(1).set_index(['match_id', 'innings', 'striker_id'])
agg['wp1'] = lastrow.wp_after_bat
firstrow = bb.groupby(['match_id', 'innings', 'striker_id']).head(1).set_index(['match_id', 'innings', 'striker_id'])
cols = ['striker_name', 'bat_team', 'bowl_team', 'bowl_tier', 'year', 'match_date', 'comp_name', 'ko',
        'bat_win', 'result', 'margin_close', 'PI']
bat_ep = agg[agg.hp_balls >= 3].join(firstrow[cols])
bat_ep['situation'] = [situation(r) for r in firstrow.loc[bat_ep.index].itertuples()]
bat_ep = bat_ep.reset_index()
bat_ep['w'] = bat_ep.year.map(REC) * bat_ep.bowl_tier.map(TIER_W) * np.where(bat_ep.ko, 1.25, 1.0)
bat_ep['win'] = (bat_ep.wpa > 0).astype(int)
bat_ep['collapse'] = (bat_ep.wpa < -0.10).astype(int)

# ---------------- bowling episodes (pressure overs) ----------------
ov = b.groupby(['match_id', 'innings', 'overid', 'bowler_id']).agg(
    meanPI=('PI', 'mean'), wpa=('wpa_bowl', 'sum'), conceded=('tot', 'sum'),
    wkts=('is_wicket', 'sum'), legal=('legal', 'sum'), hpb=('hp', 'sum'))
ro = b[b.dismissal_type == 'RunOut'].groupby(['match_id', 'innings', 'overid', 'bowler_id']).size()
ov['wkts'] = ov.wkts - ov.index.map(ro).fillna(0).values
firstb = b.groupby(['match_id', 'innings', 'overid', 'bowler_id']).head(1).set_index(['match_id', 'innings', 'overid', 'bowler_id'])
thr = b.PI.quantile(0.80)
bowl_ep = ov[(ov.meanPI >= thr) & (ov.legal >= 3)].join(
    firstb[['bowler_name', 'bat_team', 'bowl_team', 'bat_tier', 'year', 'match_date', 'comp_name', 'ko',
            'bat_win', 'result', 'margin_close', 'wp_before', 'env_rpo']])
bowl_ep['situation'] = [situation(r) for r in firstb.loc[bowl_ep.index].itertuples()]
lastb = b.groupby(['match_id', 'innings', 'overid', 'bowler_id']).tail(1).set_index(['match_id', 'innings', 'overid', 'bowler_id'])
bowl_ep['wp1'] = 1 - lastb.loc[bowl_ep.index].wp_after.values
bowl_ep['wp0'] = 1 - bowl_ep.wp_before
bowl_ep = bowl_ep.reset_index()
bowl_ep['w'] = bowl_ep.year.map(REC) * bowl_ep.bat_tier.map(TIER_W) * np.where(bowl_ep.ko, 1.25, 1.0)
bowl_ep['win'] = (bowl_ep.wpa > 0).astype(int)
bowl_ep['collapse'] = (bowl_ep.wpa < -0.08).astype(int)
bowl_ep['env_par_over'] = bowl_ep.env_rpo

# ---------------- ball-level pressure lift (own baseline) ----------------
def lift(df, pid, val):
    g = df.groupby([pid, 'hp'])[val].agg(['mean', 'size']).unstack()
    out = pd.DataFrame({'hp_mean': g[('mean', True)], 'lo_mean': g[('mean', False)],
                        'n_hp': g[('size', True)], 'n_lo': g[('size', False)]})
    out['lift'] = (out.hp_mean - out.lo_mean) * out.n_hp / (out.n_hp + 150)
    return out

bat_lift = lift(b, 'striker_id', 'cn')
bowl_lift = lift(b[b.dismissal_type.ne('RunOut')], 'bowler_id', 'cnb')

# pressure-ball strike rate & dismissal rate vs environment
def bat_ball_stats(df):
    lg = df[df.legal]
    return pd.Series({'sr': lg.runs.sum() / max(len(lg), 1) * 100,
                      'env_sr': lg.env_sr.mean(),
                      'bpd': len(lg) / max(df.own_out.sum(), 1),
                      'dot_pct': (lg.runs == 0).mean() * 100,
                      'bdry_pct': ((lg.runs >= 4)).mean() * 100})
bat_hp = b[b.hp].groupby('striker_id').apply(bat_ball_stats, include_groups=False)
bat_lo = b[~b.hp].groupby('striker_id').apply(bat_ball_stats, include_groups=False)

def bowl_ball_stats(df):
    lg = df.legal.sum()
    w = (df.is_wicket & df.dismissal_type.ne('RunOut')).sum()
    return pd.Series({'econ': df.tot.sum() / max(lg, 1) * 6, 'env_econ': df.env_rpo.mean(),
                      'dot_pct': ((df.tot == 0) & df.legal).sum() / max(lg, 1) * 100,
                      'bpw': lg / max(w, 1), 'wkts': w, 'balls': lg})
bowl_hp = b[b.hp].groupby('bowler_id').apply(bowl_ball_stats, include_groups=False)
bowl_lo = b[~b.hp].groupby('bowler_id').apply(bowl_ball_stats, include_groups=False)

# ---------------- decision vs execution ----------------
def dec_exec(df, actor, choice, keycols, val, minn=40):
    d = df[df[choice].notna()].copy()
    kmean = d.groupby(keycols)[val].transform('mean')
    gs = d.groupby(keycols + [choice])[val]
    cm, cn = gs.transform('mean'), gs.transform('size')
    ev = (cm * cn + kmean * minn) / (cn + minn)            # shrunk EV of chosen option
    d['decision'] = ev - kmean
    d['execution'] = d[val] - ev
    h = d[d.hp]
    return h.groupby(actor)[['decision', 'execution']].mean()

bkey = ['pace_or_spin', 'delivery_style', 'phase', 'innings']
bat_de = dec_exec(b, 'striker_id', 'stroke', bkey, 'cn')
wkey = ['pace_or_spin', 'batting_type', 'phase', 'innings']
bowl_de = dec_exec(b[b.dismissal_type.ne('RunOut')], 'bowler_id', 'delivery_style', wkey, 'cnb')

# ---------------- pressure debt (sequence response) ----------------
b['prev_bdry'] = b.groupby(['match_id', 'innings', 'bowler_id']).tot.shift(1).ge(4)
sq = b[(b.dot_streak >= 3) & b.legal]
bat_debt = sq.groupby('striker_id').agg(
    sq_n=('runs', 'size'),
    sq_out=('is_wicket', 'mean'), sq_score=('runs', lambda s: (s > 0).mean()))
rb = b[b.prev_bdry & b.legal]
bowl_bounce = rb.groupby('bowler_id').agg(
    bb_n=('tot', 'size'), bb_dot=('tot', lambda s: (s == 0).mean()),
    bb_bdry=('tot', lambda s: (s >= 4).mean()))

# ---------------- shot / delivery DNA ----------------
def dna(df, actor, choice, val):
    out = {}
    for pid, g in df[df[choice].notna()].groupby(actor):
        hp, lo = g[g.hp], g[~g.hp]
        if len(hp) < 25:
            continue
        ph, pl = hp[choice].value_counts(normalize=True), lo[choice].value_counts(normalize=True)
        idx = ph.index.union(pl.index)
        P_, Q_ = ph.reindex(idx, fill_value=0).values + 1e-9, pl.reindex(idx, fill_value=0).values + 1e-9
        M = (P_ + Q_) / 2
        js = 0.5 * np.sum(P_ * np.log2(P_ / M)) + 0.5 * np.sum(Q_ * np.log2(Q_ / M))
        top = hp.groupby(choice).agg(n=(val, 'size'), v=(val, 'mean'), r=('tot', 'mean')).sort_values('n', ascending=False).head(4)
        out[pid] = {'drift': round(float(js), 3),
                    'top': [{'name': k, 'share': round(r.n / len(hp) * 100, 1), 'rpb': round(r.r, 2),
                             'base_share': round(float(pl.get(k, 0)) * 100, 1)} for k, r in top.iterrows()]}
    return out
bat_dna = dna(b, 'striker_id', 'stroke', 'cn')
bowl_dna = dna(b, 'bowler_id', 'delivery_style', 'cnb')

# ---------------- player metadata ----------------
non_ipl = mp[~mp.comp_name.str.startswith('IPL')]
nat = non_ipl.groupby('player_id').team_name.agg(lambda s: s.value_counts().index[0])
nat = nat.str.replace(r' A$', '', regex=True)
NAT_FIX = {'Sunil Narine': 'West Indies', 'Faf du Plessis': 'South Africa'}
ipl_m = mp[mp.comp_name.str.startswith('IPL')].copy()
ipl_m['yr'] = ipl_m.comp_name.str[-4:].astype(int)
last_ipl = ipl_m.sort_values('yr').groupby('player_id').tail(1).set_index('player_id')
last_year = pd.concat([b[['striker_id', 'year']].rename(columns={'striker_id': 'pid'}),
                       b[['bowler_id', 'year']].rename(columns={'bowler_id': 'pid'})]).groupby('pid').year.max()
ipl_seasons = ipl_m.groupby('player_id').yr.nunique()

def batter_role(pid):
    g = b[b.striker_id == pid].groupby(['match_id', 'innings']).agg(entry=('lb', 'min'), order=('batting_order', 'first'))
    e = g.entry.median()
    if e <= 6: return 'Opener'
    if e <= 42: return 'Top order'
    if e <= 84: return 'Middle order'
    return 'Finisher'

def bowler_role(pid):
    g = b[b.bowler_id == pid]
    bt = g.bowling_type.mode().iloc[0]
    if 'Leg-Break' in bt or 'Chinaman' in bt: kind = 'Wrist spin'
    elif 'offbreak' in bt or 'orthodox' in bt: kind = 'Finger spin'
    else: kind = 'Pace'
    left = bt.startswith('Left') or 'left-arm' in bt
    lgl = g[g.legal]
    death, pp = (lgl.lb >= 90).mean(), (lgl.lb < 36).mean()
    if kind == 'Pace':
        phase = ('New ball + Death' if (pp >= .33 and death >= .25) else
                 'Death' if death >= .25 else 'New ball' if pp >= .33 else 'Middle overs')
    else:
        phase = 'Middle overs'
    return kind, left, phase, bt

def shrink(num, den, k, prior):
    return (num + k * prior) / (den + k)

def zs(s):
    return (s - s.mean()) / s.std()

def rate(ep, pid, k_imp, k_suc, priors=None):
    w = ep.w.values
    if priors is None:
        priors = ((ep.wpa * ep.w).sum() / w.sum(), (ep.win * ep.w).sum() / w.sum(), (ep.collapse * ep.w).sum() / w.sum())
    mu, p0, c0 = priors
    t = pd.DataFrame({pid: ep[pid].values, 'w': w, 'ww': ep.wpa.values * w, 'wn': ep.win.values * w,
                      'wc': ep.collapse.values * w, 'ko': ep.ko.values.astype(int),
                      'cl': ep.margin_close.values.astype(int),
                      'ipl': ep.comp_name.str.startswith('IPL').values.astype(int), 'one': 1})
    g = t.groupby(pid).sum()
    R = pd.DataFrame({'episodes': g.one, 'w_eps': g.w,
                      'impact': shrink(g.ww, g.w, k_imp, mu),
                      'success': shrink(g.wn, g.w, k_suc, p0),
                      'reliab': 1 - shrink(g.wc, g.w, k_suc, c0),
                      'ko_eps': g.ko, 'close_eps': g.cl, 'ipl_eps': g.ipl})
    R['seasons'] = ep.groupby(pid).year.nunique()
    return R, priors

WTS = {'impact': .35, 'success': .25, 'lift': .20, 'reliab': .10, 'volume': .10}

def composite(R, ref=None):
    R = R.copy(); R['volume'] = np.log1p(R.w_eps)
    ref = ref if ref is not None else {k: (R[k].mean(), R[k].std()) for k in WTS}
    R['score_raw'] = sum(w * (R[k] - ref[k][0]) / ref[k][1] for k, w in WTS.items())
    return R, ref

def build(kind):
    if kind == 'bat':
        ep, pid, nm, lf = bat_ep, 'striker_id', 'striker_name', bat_lift
        R, _ = rate(ep, pid, 4, 6)
        elig = (R.episodes >= 10) & (lf.reindex(R.index).n_hp >= 60)
    else:
        ep, pid, nm, lf = bowl_ep, 'bowler_id', 'bowler_name', bowl_lift
        R, _ = rate(ep, pid, 6, 8)
        elig = (R.episodes >= 15) & (lf.reindex(R.index).n_hp >= 90)
    R['lift'] = lf.reindex(R.index).lift
    R['last_year'] = last_year.reindex(R.index)
    R['name'] = ep.groupby(pid)[nm].first()
    R = R[elig & (R.last_year >= 2025)]
    R, ref = composite(R)
    R['score'] = (R.score_raw.rank(pct=True) * 100).round(1)
    # bootstrap rank intervals (resample episodes within player)
    ranks = []
    epi = ep[ep[pid].isin(R.index)].sort_values(pid).reset_index(drop=True)
    _, pri = rate(ep, pid, *((4, 6) if kind == 'bat' else (6, 8)))
    sizes = epi.groupby(pid, sort=True).size().values
    starts = np.repeat(np.cumsum(sizes) - sizes, sizes); ns = np.repeat(sizes, sizes)
    for it in range(400):
        idx = starts + (rng.random(len(epi)) * ns).astype(int)
        Rb, _ = rate(epi.iloc[idx], pid, *((4, 6) if kind == 'bat' else (6, 8)), priors=pri)
        Rb['lift'] = R.lift
        Rb, _ = composite(Rb, ref)
        ranks.append(Rb.score_raw.rank(ascending=False))
    rk = pd.concat(ranks, axis=1)
    R['rank_p10'] = rk.quantile(.10, axis=1); R['rank_p90'] = rk.quantile(.90, axis=1)
    R['top10_prob'] = (rk <= 10).mean(axis=1)
    # temporal split-half: 2022-24 vs 2025-26
    a, _ = rate(ep[ep.year <= 2024], pid, *((4, 6) if kind == 'bat' else (6, 8)))
    c, _ = rate(ep[ep.year >= 2025], pid, *((4, 6) if kind == 'bat' else (6, 8)))
    both = a.join(c, lsuffix='_a', rsuffix='_b', how='inner')
    both = both[(both.episodes_a >= 5) & (both.episodes_b >= 5)]
    split = {k: round(float(np.corrcoef(both[k + '_a'], both[k + '_b'])[0, 1]), 3) for k in ['impact', 'success']}
    split['n'] = int(len(both))
    return R.sort_values('score_raw', ascending=False), split

batR, bat_split = build('bat')
bowlR, bowl_split = build('bowl')
print('split-half', bat_split, bowl_split)

# enrich
for R, kind in [(batR, 'bat'), (bowlR, 'bowl')]:
    R['nationality'] = [NAT_FIX.get(n, nat.get(p, 'India')) for p, n in zip(R.index, R.name)]
    R['overseas'] = R.nationality != 'India'
    R['ipl_team'] = [last_ipl.team_name.get(p, '—') for p in R.index]
    R['ipl_last'] = [int(last_ipl.yr.get(p, 0)) or None for p in R.index]
    R['ipl_seasons'] = [int(ipl_seasons.get(p, 0)) for p in R.index]
batR['role'] = [batter_role(p) for p in batR.index]
batR['hand'] = [b[b.striker_id == p].batting_type.mode().iloc[0] for p in batR.index]
br = {p: bowler_role(p) for p in bowlR.index}
bowlR['kind'] = [br[p][0] for p in bowlR.index]
bowlR['left_arm'] = [br[p][1] for p in bowlR.index]
bowlR['phase_role'] = [br[p][2] for p in bowlR.index]
bowlR['bowling_type'] = [br[p][3] for p in bowlR.index]
bowlR['role'] = [(('Left-arm ' if br[p][1] else '') + br[p][0] + (' · ' + br[p][2] if br[p][0] == 'Pace' else '')) for p in bowlR.index]

batR = batR.join(bat_hp.add_prefix('hp_')).join(bat_lo.add_prefix('lo_')).join(bat_de).join(bat_debt)
bowlR = bowlR.join(bowl_hp.add_prefix('hp_')).join(bowl_lo.add_prefix('lo_')).join(bowl_de).join(bowl_bounce)
batR.to_csv(f'{OUT}/bat_ratings.csv'); bowlR.to_csv(f'{OUT}/bowl_ratings.csv')
bat_ep.to_csv(f'{OUT}/bat_episodes.csv', index=False); bowl_ep.to_csv(f'{OUT}/bowl_episodes.csv', index=False)
json.dump({'bat_split': bat_split, 'bowl_split': bowl_split, 'thr': float(thr),
           'bat_dna': {str(k): v for k, v in bat_dna.items() if k in batR.index},
           'bowl_dna': {str(k): v for k, v in bowl_dna.items() if k in bowlR.index}},
          open(f'{OUT}/extras.json', 'w'))
print(len(batR), 'eligible batters;', len(bowlR), 'eligible bowlers')
show = ['name', 'role', 'nationality', 'episodes', 'impact', 'success', 'lift', 'reliab', 'score', 'rank_p10', 'rank_p90', 'top10_prob']
pd.set_option('display.width', 250)
print(batR[show + ['hand']].head(30).round(3).to_string())
print(bowlR[show].head(30).round(3).to_string())
