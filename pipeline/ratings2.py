"""Stage 3: final Pressure Reliability Rating (PRR).
Baseline skill (situation + pitch adjusted) + credibility-weighted pressure delta + moment success.
Usage: python -I ratings2.py <out_dir>
"""
import sys, json, numpy as np, pandas as pd
OUT = sys.argv[1]
rng = np.random.default_rng(11)
b = pd.read_parquet(f'{OUT}/balls.parquet')
x = pd.read_parquet(f'{OUT}/expect.parquet')
b = b.merge(x, on=['match_id', 'innings', 'innings_ball_num'], how='left')
lg = b[b.legal].copy()
REC = {2022: .55, 2023: .65, 2024: .80, 2025: .90, 2026: 1.0}
TW = {'IPL': 1.0, 'Full': 1.0, 'Semi': .8, 'A': .75, 'Assoc': .5}
home_bat = lg.batting_team_id == lg.home_team_id
lg['bat_tier'] = np.where(home_bat, lg.home_tier, lg.away_tier)
lg['bowl_tier'] = np.where(home_bat, lg.away_tier, lg.home_tier)
ko = ((lg.knock_out == 1) | lg.stage.isin(['Final', 'Qualifier', 'Eliminator', 'Semi Final', 'Super 4'])).values
base_w = lg.year.map(REC).values * np.where(ko, 1.25, 1.0)
lg['w_bat'] = base_w * lg.bowl_tier.map(TW).values
lg['w_bowl'] = base_w * lg.bat_tier.map(TW).values
lg['own_out'] = (lg.is_wicket & (lg.dismissed_player_id == lg.striker_id)).astype(float)
lg['bwk'] = (lg.is_wicket & lg.dismissal_type.ne('RunOut')).astype(float)
lg['isdot'] = (lg.runs == 0).astype(float)
# batter view deltas
lg['b_runs'] = lg.runs - lg.x_runs
lg['b_out'] = -(lg.own_out - lg.x_own_out)
lg['b_dot'] = -(lg.isdot - lg.x_dot)
# bowler view deltas (positive = good for bowler)
lg['w_runs'] = -(lg.runs - lg.x_runs)
lg['w_wkt'] = lg.bwk - lg.x_bwk
lg['w_dot'] = lg.isdot - lg.x_dot

bat_ep = pd.read_csv(f'{OUT}/bat_episodes.csv')
bowl_ep = pd.read_csv(f'{OUT}/bowl_episodes.csv')
batR0 = pd.read_csv(f'{OUT}/bat_ratings.csv', index_col=0)
bowlR0 = pd.read_csv(f'{OUT}/bowl_ratings.csv', index_col=0)

K_HP, K_ALL = 200.0, 300.0
SPEC = {
    'bat': dict(pid='striker_id', w='w_bat', mets=['b_runs', 'b_out', 'b_dot'], ep=bat_ep, pool=batR0.index,
                wts={'b_runs': .30, 'b_out': .20, 'b_dot': .25, 'moment': .15, 'delta': .10}),
    'bowl': dict(pid='bowler_id', w='w_bowl', mets=['w_runs', 'w_wkt', 'w_dot'], ep=bowl_ep, pool=bowlR0.index,
                 wts={'w_runs': .25, 'w_wkt': .20, 'w_dot': .30, 'moment': .15, 'delta': .10}),
}


def components(kind, mw=None, ew=None, sub=None, esub=None):
    sp = SPEC[kind]; pid = sp['pid']
    d = lg if sub is None else lg[sub]
    w = d[sp['w']].values * (1 if mw is None else mw[d.match_id.values])
    t = pd.DataFrame({pid: d[pid].values, 'w': w, 'whp': w * d.hp.values})
    for m in sp['mets']:
        t[m + '_a'] = d[m].values * w
        t[m + '_h'] = d[m].values * w * d.hp.values
    g = t.groupby(pid).sum()
    g = g[g.index.isin(sp['pool'])]
    C = pd.DataFrame(index=g.index)
    for m in sp['mets']:
        A = g[m + '_a'] / g.w
        H = g[m + '_h'] / g.whp.replace(0, np.nan)
        cred = g.whp / (g.whp + K_HP)
        A_s = A * g.w / (g.w + K_ALL)
        C[m + '_delta'] = ((H - A) * cred).fillna(0)
        C[m] = A_s + C[m + '_delta']
    e = sp['ep'] if esub is None else sp['ep'][esub]
    ewt = e.w.values * (1 if ew is None else ew[e.match_id.values])
    te = pd.DataFrame({pid: e[pid].values, 'w': ewt, 'ww': e.wpa.values * ewt, 'wn': e.win.values * ewt})
    ge = te.groupby(pid).sum()
    mu, p0 = ge.ww.sum() / ge.w.sum(), ge.wn.sum() / ge.w.sum()
    ge['impact'] = (ge.ww + 4 * mu) / (ge.w + 4)
    ge['success'] = (ge.wn + 6 * p0) / (ge.w + 6)
    C = C.join(ge[['impact', 'success']])
    return C


def score(C, kind, ref=None):
    sp = SPEC[kind]
    z = lambda s, k: (s - ref[k][0]) / ref[k][1]
    if ref is None:
        ref = {}
        cols = sp['mets'] + [m + '_delta' for m in sp['mets']] + ['impact', 'success']
        for k in cols:
            ref[k] = (C[k].mean(), C[k].std())
    S = pd.DataFrame(index=C.index)
    for m in sp['mets']:
        S[m] = z(C[m], m)
    S['moment'] = 0.6 * z(C.success, 'success') + 0.4 * z(C.impact, 'impact')
    dm = sp['mets']
    S['delta'] = z(C[dm[0] + '_delta'], dm[0] + '_delta') + 0.5 * z(C[dm[1] + '_delta'], dm[1] + '_delta') + 0.5 * z(C[dm[2] + '_delta'], dm[2] + '_delta')
    if 'delta_sd' not in ref:
        ref['delta_sd'], ref['moment_sd'] = S.delta.std(), S.moment.std()
    S['delta'] = S.delta / ref['delta_sd']
    S['moment'] = S.moment / ref['moment_sd']
    S['prr_raw'] = sum(wt * S[k] for k, wt in sp['wts'].items())
    return S, ref


results, extras = {}, {}
max_mid = int(lg.match_id.max()) + 1
for kind in ['bat', 'bowl']:
    C = components(kind)
    S, ref = score(C, kind)
    S['PRR'] = (50 + 10 * (S.prr_raw - S.prr_raw.mean()) / S.prr_raw.std()).round(1)
    # Poisson bootstrap over matches
    rk = []
    for it in range(300):
        mw = rng.poisson(1.0, max_mid).astype(float)
        Cb = components(kind, mw=mw, ew=mw)
        Sb, _ = score(Cb.reindex(C.index), kind, ref)
        rk.append(Sb.prr_raw.rank(ascending=False))
    rk = pd.concat(rk, axis=1)
    S['rank'] = S.prr_raw.rank(ascending=False).astype(int)
    S['rank_lo'] = rk.quantile(.10, axis=1).round().astype(int)
    S['rank_hi'] = rk.quantile(.90, axis=1).round().astype(int)
    S['p_top10'] = (rk <= 10).mean(axis=1).round(3)
    S['p_top25'] = (rk <= 25).mean(axis=1).round(3)
    # odd/even match reliability: PRR vs naive clutch (episode WPA only)
    half = lg.match_id.rank(method='dense').astype(int) % 2
    ehalf = SPEC[kind]['ep'].match_id.rank(method='dense').astype(int) % 2
    hs, naive = [], []
    for h in [0, 1]:
        Ch = components(kind, sub=(half == h).values, esub=(ehalf == h).values)
        Sh, _ = score(Ch.reindex(C.index), kind, None)
        hs.append(Sh.prr_raw); naive.append(Ch.impact.reindex(C.index))
    r_prr = pd.concat(hs, axis=1).dropna().corr().iloc[0, 1]
    r_naive = pd.concat(naive, axis=1).dropna().corr().iloc[0, 1]
    # temporal persistence 2022-24 -> 2025-26
    early = (lg.year <= 2024).values; e_early = (SPEC[kind]['ep'].year <= 2024).values
    Ce = components(kind, sub=early, esub=e_early); Cl = components(kind, sub=~early, esub=~e_early)
    Se, _ = score(Ce.reindex(C.index), kind, None); Sl, _ = score(Cl.reindex(C.index), kind, None)
    r_time = pd.concat([Se.prr_raw, Sl.prr_raw], axis=1).dropna().corr().iloc[0, 1]
    r_time_naive = pd.concat([Ce.impact.reindex(C.index), Cl.impact.reindex(C.index)], axis=1).dropna().corr().iloc[0, 1]
    extras[kind] = {'split_half_prr': round(float(r_prr), 3), 'split_half_naive': round(float(r_naive), 3),
                    'temporal_prr': round(float(r_time), 3), 'temporal_naive': round(float(r_time_naive), 3),
                    'n': int(len(S))}
    print(kind, extras[kind])
    R0 = batR0 if kind == 'bat' else bowlR0
    out = R0.join(C.add_prefix('c_')).join(S.add_prefix('s_'))
    out = out.sort_values('s_prr_raw', ascending=False)
    # readable pressure-ball numbers vs expected
    pid = SPEC[kind]['pid']
    h = lg[lg.hp & lg[pid].isin(out.index)]
    if kind == 'bat':
        rb = h.groupby(pid).agg(hb=('runs', 'size'), hr=('runs', 'sum'), xr=('x_runs', 'sum'),
                                ho=('own_out', 'sum'), xo=('x_own_out', 'sum'), hd=('isdot', 'mean'), xd=('x_dot', 'mean'))
        rb['hp_sr'] = rb.hr / rb.hb * 100; rb['hp_xsr'] = rb.xr / rb.hb * 100
        rb['hp_avg'] = rb.hr / rb.ho.clip(lower=1); rb['hp_dot'] = rb.hd * 100; rb['hp_xdot'] = rb.xd * 100
    else:
        rb = h.groupby(pid).agg(hb=('runs', 'size'), hr=('tot', 'sum'), xr=('x_runs', 'sum'),
                                hw=('bwk', 'sum'), xw=('x_bwk', 'sum'), hd=('isdot', 'mean'), xd=('x_dot', 'mean'))
        rb['hp_econ'] = rb.hr / rb.hb * 6; rb['hp_xecon'] = rb.xr / rb.hb * 6
        rb['hp_bpw'] = rb.hb / rb.hw.clip(lower=1); rb['hp_dot'] = rb.hd * 100; rb['hp_xdot'] = rb.xd * 100
    out = out.join(rb.add_prefix('pb_'))
    out.to_csv(f'{OUT}/{kind}_final.csv')
    results[kind] = out
    cols = ['name', 'role', 'nationality', 's_PRR', 's_rank_lo', 's_rank_hi', 's_p_top10'] + \
           ['s_' + k for k in SPEC[kind]['wts']]
    print(out[cols].head(30).round(2).to_string())
json.dump(extras, open(f'{OUT}/validation.json', 'w'), indent=1)
