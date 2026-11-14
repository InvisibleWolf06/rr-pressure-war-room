"""Stage 1: pitch-adjusted win probability, leverage and per-ball WPA.
Usage: python -I engine.py <data_dir> <out_dir>
"""
import sys, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, brier_score_loss

D, OUT = sys.argv[1], sys.argv[2]
b = pd.read_csv(f'{D}/ball_by_ball.csv', low_memory=False)
m = pd.read_csv(f'{D}/matches.csv')
c = pd.read_csv(f'{D}/competitions.csv')
m = m.merge(c[['comp_id', 'comp_name', 'match_format', 'season']], on='comp_id')

FULL = {'India', 'England', 'Australia', 'South Africa', 'New Zealand', 'Pakistan',
        'Sri Lanka', 'West Indies', 'Afghanistan', 'Bangladesh'}
SEMI = {'Ireland', 'Zimbabwe'}

def tier(team, comp):
    if comp.startswith('IPL'):
        return 'IPL'
    if team in FULL: return 'Full'
    if team in SEMI: return 'Semi'
    if team.endswith(' A'): return 'A'
    return 'Assoc'

m['is_ipl'] = m.comp_name.str.startswith('IPL')
m['home_tier'] = [tier(t, cn) for t, cn in zip(m.home_team, m.comp_name)]
m['away_tier'] = [tier(t, cn) for t, cn in zip(m.away_team, m.comp_name)]
m['year'] = pd.to_datetime(m.match_date).dt.year
m['margin_close'] = m.result.str.extract(r'by (\d+) [Rr]un', expand=False).astype(float).le(15) | \
    m.result.str.extract(r'by (\d+) [Ww]icket', expand=False).astype(float).le(3)
m['tied_so'] = m.result.str.contains('Super Over|Tie|tied', case=False, na=False)
valid = m[m.first_inn_revised_overs.isna() & m.second_inn_revised_overs.isna()
          & m.win_team_id.notna() & (m.win_team_id > 0)
          & ~m.result.str.contains('Abandon|No Result', case=False, na=False)].copy()

b = b[b.innings <= 2].merge(valid[['match_id', 'win_team_id', 'is_ipl', 'venue_id', 'year', 'season',
                                     'comp_name', 'knock_out', 'stage', 'match_date', 'home_team',
                                     'away_team', 'home_team_id', 'away_team_id', 'home_tier',
                                     'away_tier', 'margin_close', 'tied_so', 'result']], on='match_id')
b['tot'] = b.runs + b.extras1_runs + b.extras_2_runs
b['legal'] = ~b.extras_type.isin(['wide', 'Overstep'])
b = b.sort_values(['match_id', 'innings', 'innings_ball_num']).reset_index(drop=True)
g = b.groupby(['match_id', 'innings'])
b['cum'] = g.tot.cumsum() - b.tot
b['wk'] = g.is_wicket.cumsum() - b.is_wicket.astype(int)
b['lb'] = g.legal.cumsum() - b.legal.astype(int)
b['balls_left'] = 120 - b.lb
b['wl'] = 10 - b.wk
inn_tot = b.groupby(['match_id', 'innings']).tot.sum().unstack()
b['target'] = b.match_id.map(inn_tot[1] + 1)

# ---------- scoring environment (flat-wicket factor) ----------
# Run rate per match (both innings, legal balls), then a shrunk venue x competition-type x season par.
mr = b.groupby('match_id').agg(r=('tot', 'sum'), lb=('legal', 'sum'))
mr = mr.join(valid.set_index('match_id')[['venue_id', 'is_ipl', 'year']])
mr['rpo'] = mr.r / mr.lb * 6
grand = mr.rpo.mean()
k = 6.0  # prior strength in matches
ys = mr.groupby(['is_ipl', 'year']).rpo.mean().rename('ys')
mr = mr.join(ys, on=['is_ipl', 'year'])
mr['dev'] = mr.rpo - mr.ys
vs = mr.groupby('venue_id').dev.agg(['sum', 'count'])
vs['venue_eff'] = vs['sum'] / (vs['count'] + k)
mr = mr.join(vs.venue_eff, on='venue_id')
mr['env_rpo'] = mr.ys + mr.venue_eff
b['env_rpo'] = b.match_id.map(mr.env_rpo)
b['env_par'] = b.env_rpo * 20
mr[['rpo', 'ys', 'venue_eff', 'env_rpo']].to_csv(f'{OUT}/match_env.csv')

# ---------- win probability models (smooth, resource-based) ----------
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
b['bat_win'] = (b.batting_team_id == b.win_team_id).astype(int)
s1 = b.innings == 1
s2 = b.innings == 2
fin = b[s1].groupby('match_id').tot.sum()
b['rem'] = np.where(s1, b.match_id.map(fin) - b.cum, np.nan)
RF = ['balls_left', 'wl', 'env_rpo']
er = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_depth=4, min_samples_leaf=300, early_stopping=False, random_state=7,
                                   monotonic_cst=[1, 1, 1]).fit(b.loc[s1, RF], b.loc[s1, 'rem'])
# residual spread grows with balls left
res = b.loc[s1, 'rem'] - er.predict(b.loc[s1, RF])
sd_tab = res.groupby(b.loc[s1, 'balls_left']).agg(['std', 'size'])
sd_tab = sd_tab[(sd_tab['size'] >= 50) & sd_tab['std'].notna()]['std']
sd_fit = np.polyfit(np.sqrt(sd_tab.index.values + 1), sd_tab.values, 1)

def exp_rem(bl, wl, env):
    bl = np.asarray(bl, float); wl = np.asarray(wl, float)
    d = pd.DataFrame({'balls_left': np.clip(bl, 0, 120), 'wl': np.clip(wl, 0, 10), 'env_rpo': env})
    e = er.predict(d)
    return np.where((bl <= 0) | (wl <= 0), 0.0, np.maximum(e, 0))

def sd_rem(bl):
    return np.maximum(np.polyval(sd_fit, np.sqrt(np.clip(np.asarray(bl, float), 0, 120) + 1)), 2.0)

def feats2(need, bl, wl, env):
    m_ = (exp_rem(bl, wl, env) - need) / sd_rem(bl)
    return np.column_stack([m_, m_ * np.sqrt(np.clip(bl, 0, 120) / 120)])

def feats1(cum, bl, wl, env):
    proj = cum + exp_rem(bl, wl, env)
    par = np.asarray(env) * 20
    tot_sd = np.sqrt(sd_rem(bl) ** 2 + 22.0 ** 2)
    m_ = (proj - par) / tot_sd
    return np.column_stack([m_])

n2 = (b.loc[s2, 'target'] - b.loc[s2, 'cum']).values
X2 = feats2(n2, b.loc[s2, 'balls_left'].values, b.loc[s2, 'wl'].values, b.loc[s2, 'env_rpo'].values)
X1 = feats1(b.loc[s1, 'cum'].values, b.loc[s1, 'balls_left'].values, b.loc[s1, 'wl'].values, b.loc[s1, 'env_rpo'].values)
y2, y1 = b.loc[s2, 'bat_win'].values, b.loc[s1, 'bat_win'].values
live2 = (n2 > 0) & (b.loc[s2, 'wl'].values > 0)
m2 = LogisticRegression(C=10).fit(X2[live2], y2[live2])
m1 = LogisticRegression(C=10).fit(X1, y1)
for nm, X, y, mdl, grp in [('chase', X2[live2], y2[live2], m2, b.loc[s2, 'match_id'].values[live2]),
                           ('set', X1, y1, m1, b.loc[s1, 'match_id'].values)]:
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, grp):
        oof[te] = LogisticRegression(C=10).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    cal = pd.DataFrame({'p': oof, 'y': y})
    cal['bin'] = pd.cut(cal.p, np.linspace(0, 1, 11))
    cal.groupby('bin', observed=True).agg(pred=('p', 'mean'), actual=('y', 'mean'), n=('y', 'size')).to_csv(f'{OUT}/calib_{nm}.csv')
    print(nm, 'out-of-fold AUC', round(roc_auc_score(y, oof), 3), 'Brier', round(brier_score_loss(y, oof), 3))


def wp_chase(need, bl, wl, env):
    need, bl, wl = np.asarray(need, float), np.asarray(bl, float), np.asarray(wl, float)
    p = m2.predict_proba(feats2(need, bl, wl, env))[:, 1]
    p = np.where(need <= 0, 1.0, p)
    p = np.where((need > 0) & ((wl <= 0) | (bl <= 0)), 0.0, p)
    return p


def wp_first(cum, bl, wl, env):
    cum, bl, wl = np.asarray(cum, float), np.asarray(bl, float), np.asarray(wl, float)
    env = np.asarray(env, float)
    p = m1.predict_proba(feats1(cum, bl, wl, env))[:, 1]
    end = (bl <= 0) | (wl <= 0)
    if end.any():
        p[end] = 1 - wp_chase(cum[end] + 1, np.full(end.sum(), 120.), np.full(end.sum(), 10.), env[end])
    return p


def wp_bat(inn, cum, target, bl, wl, env):
    out = np.empty(len(inn))
    i1 = inn == 1
    out[i1] = wp_first(cum[i1], bl[i1], wl[i1], env[i1])
    out[~i1] = wp_chase(target[~i1] - cum[~i1], bl[~i1], wl[~i1], env[~i1])
    return out

inn = b.innings.values; cum = b.cum.values.astype(float); tg = b.target.values.astype(float)
bl = b.balls_left.values.astype(float); wl = b.wl.values.astype(float); env = b.env_rpo.values
legal = b.legal.values.astype(int)

b['wp_before'] = wp_bat(inn, cum, tg, bl, wl, env)
# full ball outcome (bowler / team view)
b['wp_after'] = wp_bat(inn, cum + b.tot.values, tg, bl - legal, wl - b.is_wicket.values.astype(int), env)
b['wpa_ball'] = b.wp_after - b.wp_before  # batting-side view
# batter credit: bat runs + his own dismissal only (extras are not his)
own_out = (b.is_wicket & (b.dismissed_player_id == b.striker_id)).values.astype(int)
b['wp_after_bat'] = wp_bat(inn, cum + b.runs.values + (b.tot - b.runs).values, tg, bl - legal, wl - own_out, env)
b['wpa_bat'] = b.wp_after_bat - b.wp_before
# bowler credit: everything except run-outs
ro = (b.dismissal_type == 'RunOut').values.astype(int)
b['wp_after_bowl'] = wp_bat(inn, cum + b.tot.values, tg, bl - legal, wl - b.is_wicket.values.astype(int) + ro, env)
b['wpa_bowl'] = -(b.wp_after_bowl - b.wp_before)

# ---------- leverage ----------
# Tango-style leverage: expected |WP swing| over the outcome distribution for this phase
ph = pd.cut(b.lb, [-1, 35, 89, 200], labels=[0, 1, 2]).astype(int).values
oc = np.select([~b.legal, b.is_wicket, b.tot >= 6, b.tot >= 4, b.tot == 0, b.tot == 1, b.tot >= 2],
               ['x', 'W', '6', '4', '0', '1', '2'], 'x')
outcomes = {'0': (0, 1, 0), '1': (1, 1, 0), '2': (2, 1, 0), '4': (4, 1, 0), '6': (6, 1, 0), 'W': (0, 1, 1), 'x': (1, 0, 0)}
freq = pd.crosstab([b.innings, ph], oc, normalize='index')
li = np.zeros(len(b))
for o, (r, lg, w) in outcomes.items():
    pr = freq[o].reindex(list(zip(b.innings, ph))).values
    li += pr * np.abs(wp_bat(inn, cum + r, tg, bl - lg, wl - w, env) - b.wp_before.values)
b['li_raw'] = li
b['LI'] = b.li_raw / b.groupby('innings').li_raw.transform('mean')

# felt-pressure modifiers: dot-ball squeeze, recent wicket
b['is_dot'] = (b.tot == 0) & b.legal
# consecutive dots BEFORE this ball (never includes the ball's own outcome)
grp = (~b.is_dot).groupby([b.match_id, b.innings]).cumsum()
run_incl = b.groupby([b.match_id, b.innings, grp]).is_dot.cumsum()
b['dot_streak'] = run_incl.groupby([b.match_id, b.innings]).shift(1).fillna(0).astype(int)
b['recent_wkt'] = g.is_wicket.transform(lambda s: s.shift(1).rolling(6, min_periods=1).sum()).fillna(0) > 0
b['PI'] = b.LI * (1 + 0.20 * (b.dot_streak >= 3) + 0.20 * b.recent_wkt)
thr = b.PI.quantile(0.80)
b['hp'] = b.PI >= thr
print('PI threshold (top 20%)', round(thr, 3))

b['phase'] = pd.cut(b.lb, [-1, 35, 89, 200], labels=['Powerplay', 'Middle', 'Death'])
print(b.groupby(['innings', 'phase'], observed=True).hp.mean().round(3))
b.to_parquet(f'{OUT}/balls.parquet')
nw = ~b.is_wicket
print('smoothness: 99th pct |dWP| non-wicket balls', round(np.percentile(np.abs(b.wpa_ball[nw]), 99), 3), ' max', round(np.abs(b.wpa_ball[nw]).max(), 3))
print('rows', len(b))
