"""Robustness checks: weight/multiplier sensitivity, baseline-only benchmark, IPL vs T20I transfer.
Usage: python -I robust.py <out_dir>"""
import sys, json, numpy as np, pandas as pd
OUT = sys.argv[1]
import os; src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ratings2.py')).read(); src = src[:src.index('results, extras = {}, {}')]
sys.argv = ['x', OUT]; exec(src)
base = {k: pd.read_csv(f'{OUT}/{k}_final.csv', index_col=0).s_prr_raw for k in ['bat', 'bowl']}
names = {k: pd.read_csv(f'{OUT}/{k}_final.csv', index_col=0)['name'] for k in ['bat', 'bowl']}
top10 = {k: set(base[k].sort_values(ascending=False).index[:10]) for k in base}
W0 = {k: dict(SPEC[k]['wts']) for k in SPEC}
lg0 = lg[['w_bat', 'w_bowl']].copy()

def run(kind):
    C = components(kind); S, _ = score(C, kind); return S.prr_raw.reindex(base[kind].index)

def compare(kind, s):
    t = set(s.sort_values(ascending=False).index[:10])
    return {'overlap': len(t & top10[kind]), 'spearman': round(float(pd.concat([s, base[kind]], axis=1).corr(method='spearman').iloc[0, 1]), 3),
            'in': sorted(names[kind][list(t - top10[kind])]), 'out': sorted(names[kind][list(top10[kind] - t)])}

res = {'bat': {}, 'bowl': {}}
for kind in ['bat', 'bowl']:
    mets = SPEC[kind]['mets']
    variants = {
        'Equal weights on all five components': {k: .2 for k in W0[kind]},
        'Process only (no moments, no rise-vs-self)': {mets[0]: W0[kind][mets[0]] / .75, mets[1]: W0[kind][mets[1]] / .75, mets[2]: W0[kind][mets[2]] / .75, 'moment': 0, 'delta': 0},
        'Rise-vs-self doubled to 20%': {**{k: v * .9 / .9 for k, v in W0[kind].items()}, 'delta': .20, mets[0]: W0[kind][mets[0]] - .10},
        'Moments won doubled to 30%': {**W0[kind], 'moment': .30, mets[0]: W0[kind][mets[0]] - .15},
    }
    for nm, w in variants.items():
        SPEC[kind]['wts'] = w; res[kind][nm] = compare(kind, run(kind))
    SPEC[kind]['wts'] = dict(W0[kind])
    wcol = 'w_bat' if kind == 'bat' else 'w_bowl'
    tier = (lg.bowl_tier if kind == 'bat' else lg.bat_tier).map(TW).values
    rec = lg.year.map(REC).values
    kob = np.where(((lg.knock_out == 1) | lg.stage.isin(['Final', 'Qualifier', 'Eliminator', 'Semi Final', 'Super 4'])).values, 1.25, 1.0)
    for nm, w in {'No recency weighting': tier * kob, 'No opponent-strength weighting': rec * kob, 'No knockout boost': rec * tier}.items():
        lg[wcol] = w; res[kind][nm] = compare(kind, run(kind)); lg[wcol] = lg0[wcol]
    # baseline-only benchmark (all-ball skill, no pressure information)
    C = components(kind)
    A = {m: C[m] - C[m + '_delta'] for m in mets}
    z = lambda x: (x - x.mean()) / x.std()
    wsum = sum(W0[kind][m] for m in mets)
    bl = sum(W0[kind][m] / wsum * z(A[m]) for m in mets).reindex(base[kind].index)
    res[kind]['Baseline only (no pressure information at all)'] = compare(kind, bl)

# predictive test: rating built on odd matches -> pressure-ball performance in even matches (and vice versa)
pred = {}
for kind in ['bat', 'bowl']:
    pid, mets = SPEC[kind]['pid'], SPEC[kind]['mets']; wsum = sum(W0[kind][m] for m in mets)
    half = (lg.match_id % 2).values
    ehalf = (SPEC[kind]['ep'].match_id % 2).values
    rows = {'PRR': [], 'Baseline only': [], 'Pressure balls only': [], 'Naive clutch (win prob added)': []}
    for h in [0, 1]:
        Ca = components(kind, sub=(half == h), esub=(ehalf == h)).reindex(base[kind].index)
        Sa, _ = score(Ca, kind, None)
        z = lambda x: (x - x.mean()) / x.std()
        A = sum(W0[kind][m] / wsum * z(Ca[m] - Ca[m + '_delta']) for m in mets)
        d = lg[(half != h) & lg.hp.values]
        w = d[SPEC[kind]['w']]
        g = pd.DataFrame({pid: d[pid].values, 'w': w.values, **{m: d[m].values * w.values for m in mets}}).groupby(pid).sum()
        n = d.groupby(pid).size()
        tgt = sum(W0[kind][m] / wsum * z(g[m] / g.w) for m in mets)
        dA = lg[(half == h) & lg.hp.values]; wa = dA[SPEC[kind]['w']]
        ga = pd.DataFrame({pid: dA[pid].values, 'w': wa.values, **{m: dA[m].values * wa.values for m in mets}}).groupby(pid).sum()
        Hpa = sum(W0[kind][m] / wsum * z(ga[m] / ga.w) for m in mets)
        ok = n[n >= 40].index.intersection(base[kind].index)
        for nm, x in [('PRR', Sa.prr_raw), ('Baseline only', A), ('Pressure balls only', Hpa), ('Naive clutch (win prob added)', Ca.impact)]:
            rows[nm].append(pd.concat([x.reindex(ok), tgt.reindex(ok)], axis=1).dropna().corr().iloc[0, 1])
    pred[kind] = {k: round(float(np.mean(v)), 3) for k, v in rows.items()}

# IPL vs T20I transfer: pressure-ball process composite in each competition
transfer = {}
for kind in ['bat', 'bowl']:
    pid, mets = SPEC[kind]['pid'], SPEC[kind]['mets']; wsum = sum(W0[kind][m] for m in mets)
    d = lg[lg.hp.values & lg[pid].isin(base[kind].index)]
    ipl = d.comp_name.str.startswith('IPL')
    out = []
    for mask in [ipl, ~ipl]:
        e = d[mask.values]; g = e.groupby(pid)[mets].mean(); n = e.groupby(pid).size()
        z = lambda x: (x - x.mean()) / x.std()
        out.append((sum(W0[kind][m] / wsum * z(g[m]) for m in mets), n))
    ok = out[0][1][out[0][1] >= 40].index.intersection(out[1][1][out[1][1] >= 40].index)
    transfer[kind] = {'n': int(len(ok)), 'r': round(float(pd.concat([out[0][0].reindex(ok), out[1][0].reindex(ok)], axis=1).corr().iloc[0, 1]), 3)}

V = json.load(open(f'{OUT}/validation.json'))
sb = {k: round(2 * V[k]['split_half_prr'] / (1 + V[k]['split_half_prr']), 2) for k in V}
sbn = {k: round(2 * V[k]['split_half_naive'] / (1 + V[k]['split_half_naive']), 2) for k in V}
json.dump({'sensitivity': res, 'predictive': pred, 'transfer': transfer, 'spearman_brown': sb, 'spearman_brown_naive': sbn}, open(f'{OUT}/robust.json', 'w'), indent=1)
for k in res:
    print('==', k)
    for nm, r in res[k].items(): print(f"  {nm:52s} overlap {r['overlap']}/10  rho {r['spearman']}  in {r['in']} out {r['out']}")
print('predictive', pred); print('transfer', transfer); print('SB', sb, sbn)
