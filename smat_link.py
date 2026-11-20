"""Link SMAT (Cricsheet) names to the data pack: IPL 2026 squad, IPL games 2022-26, retirements.
Usage: python -I smat_link.py <data_dir> <out_dir>  -> out/smat.json (dashboard data)"""
import sys, os, json, re, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipl2027_lists import RET, REL
from recent_form import ROWS as RECENT, SRC as RECENT_SRC
DATA, OUT = sys.argv[1], sys.argv[2]
from smat_common import Linker, POOL, EXCL_CS
L = Linker(DATA)
ipl_seasons = L.ipl_seasons
# first SMAT season per player (career-length proxy; the data has no birth dates)
_b0 = pd.read_parquet(f'{OUT}/smat_balls_scored.parquet', columns=['season', 'batter_id', 'bowler_id'])
FIRST = pd.concat([_b0[['season', 'batter_id']].set_axis(['season', 'p'], axis=1), _b0[['season', 'bowler_id']].set_axis(['season', 'p'], axis=1)]).groupby('p').season.min()
RECENT_CS = {r[6]: r for r in RECENT if r[6]}
out = {}
for kind in ('bat', 'bowl'):
    R = pd.read_csv(f'{OUT}/smat_{kind}.csv', index_col=0)
    rows = []
    for sid, r in R.iterrows():
        first = FIRST.get(sid, r['last'])
        st_ = L.status(r['name'], r['last'], first, in_form=r['name'] in RECENT_CS)
        full, status, ns, veteran = st_['full'], st_['status'], st_['ipl_seasons'], st_['veteran']
        t27 = st_['ipl_team']; t26 = None
        recent = RECENT_CS.get(r['name'])
        d = {'id': sid, 'name': r['name'], 'full': full, 'team': r.team, 'rank': int(r['rank']), 'dpr': round(float(r.DPR), 1), 'np': int(r.np),
             'n': int(r.n), 'matches': int(r.matches), 'last': r['last'], 'impact': round(float(r.impact), 2), 'turn': round(float(r.turn), 1), 'big': int(r.big),
             'conv_p': int(r.conv_p), 'imp_p': int(r.imp_p), 'gem': bool(r.gem), 'ipl_team': t27, 'ipl_seasons': ns, 'status': status,
             'first': first, 'veteran': veteran, 'recent': (recent[3] + ': ' + recent[4]) if recent and recent[2] == kind else None}
        if kind == 'bat':
            d.update(runs=int(r.runs), balls=int(r.balls), sr=round(float(r.sr), 1), avg=round(float(r.avg), 1), hp_sr=round(float(r.hp_sr)), hp_xsr=round(float(r.hp_xsr)),
                     hp_dot=round(float(r.hp_dot)), hp_xdot=round(float(r.hp_xdot)))
        else:
            d.update(wk=int(r.wk), econ=round(float(r.econ), 2), bpw=round(float(r.bpw), 1), hp_econ=round(float(r.hp_econ), 2), hp_xecon=round(float(r.hp_xecon), 2),
                     hp_dot=round(float(r.hp_dot)), hp_xdot=round(float(r.hp_xdot)))
        rows.append(d)
    out[kind] = rows
    df = pd.DataFrame(rows)
    print(kind, df.status.value_counts().to_dict(), 'unlinked', int(df.full.isna().sum()))
    print(df[df.status.isin(POOL)].head(15)[['rank', 'name', 'team', 'dpr', 'imp_p', 'conv_p', 'status', 'last']].to_string())
json.dump(out, open(f'{OUT}/smat_players.json', 'w'))

# ---------- best pressure moment per player (innings for batters, over for bowlers)
b = pd.read_parquet(f'{OUT}/smat_balls_scored.parquet')
Mm = pd.read_csv(f'{OUT}/smat_matches.csv').set_index('match_id')
def opp_of(r): return r.bowl_team
moments = {'bat': {}, 'bowl': {}}
for kind in ('bat', 'bowl'):
    ids = [x['id'] for x in out[kind]]
    if kind == 'bat':
        d = b[b.batter_id.isin(ids)]
        for (pid, mid, inn), g in d.groupby(['batter_id', 'match_id', 'innings']):
            if g.hp.sum() < 3: continue
            moments['bat'].setdefault(pid, []).append((g.wpa.sum(), mid, inn, g))
    else:
        d = b[b.bowler_id.isin(ids)]
        for (pid, mid, inn, ov), g in d.groupby(['bowler_id', 'match_id', 'innings', 'over']):
            if g.hp.mean() < .5: continue
            moments['bowl'].setdefault(pid, []).append((-g.wpa.sum(), mid, inn, g))
best = {'bat': {}, 'bowl': {}}
for kind in moments:
    for pid, lst in moments[kind].items():
        v, mid, inn, g = max(lst, key=lambda x: x[0])
        f = g.iloc[0]; l = g.iloc[-1]
        ov = f'{int(f.legal_before // 6)}.{int(f.legal_before % 6)}'
        side = f.bat_team if kind == 'bat' else f.bowl_team
        sit = f"{f.bat_team} {int(f.score)}/{int(f.wk)} ({ov})" + (f", need {int(f.target - f.score)} off {int(f.bl)}" if f.innings == 2 else '')
        if kind == 'bat':
            did = f"{int(g.runs.sum())} off {int(g.legal.sum())}"
            wp0, wp1 = f.wp0, l.wp1
        else:
            rn, wn = int(g.tot.sum()), int((g.is_wicket & (g.kind != 'run out')).sum())
            did = f"over {int(f.over) + 1}: {rn} run{'s' if rn != 1 else ''}, {wn} wkt{'s' if wn != 1 else ''}"
            wp0, wp1 = 1 - f.wp0, 1 - l.wp1
        m = Mm.loc[mid]
        res = f"{m.winner} won" + (f" by {m.by}" if isinstance(m.by, str) and m.by else '') if m.result == 'win' else 'Tied'
        best[kind][pid] = {'date': m.date, 'season': m.season, 'side': side, 'opp': f.bowl_team if kind == 'bat' else f.bat_team, 'situation': sit, 'did': did,
                           'wp': f"{wp0 * 100:.0f}% → {wp1 * 100:.0f}%", 'gain': round(float(v) * 100, 1), 'result': res, 'stage': m.stage}
for kind in out:
    for x in out[kind]: x['moment'] = best[kind].get(x['id'])
V = json.load(open(f'{OUT}/smat_validation.json'))
json.dump({'validation': V, 'bat': out['bat'], 'bowl': out['bowl']}, open(f'{OUT}/smat.json', 'w'), default=str)
import os; print('smat.json KB', os.path.getsize(f'{OUT}/smat.json') // 1024)
for k in out:
    print(k, [(x['name'], x['moment']['did'] if x['moment'] else None) for x in out[k][:6]])

# ---------- domestic roles (from SMAT usage) and one domestic backup per RR board pick
pos = {}
for (mid, inn), g in b.groupby(['match_id', 'innings']):
    seen = list(dict.fromkeys(np.ravel(np.c_[g.batter_id, g.non_striker_id]).tolist()))
    for i, p in enumerate(seen, 1): pos.setdefault(p, []).append(i)
lgb = b[b.legal]
ph = lgb.groupby('bowler_id').phase.value_counts(normalize=True).unstack().fillna(0)
def bat_role(pid):
    m = float(np.median(pos.get(pid, [6])))
    return ('Opener' if m <= 2 else 'Top order' if m <= 4 else 'Middle order' if m <= 7 else 'Lower order'), ('top' if m <= 4 else 'mid'), m
def bowl_role(pid):
    s = ph.loc[pid] if pid in ph.index else pd.Series({'Death': 0, 'Powerplay': 0, 'Middle': 1})
    if s.get('Death', 0) >= .35: return 'Death overs', 'death'
    if s.get('Powerplay', 0) >= .40: return 'New ball', 'newball'
    return 'Middle overs', 'middle'
for x in out['bat']: x['role'], x['grp'], x['bpos'] = bat_role(x['id']); x['bpos'] = round(x['bpos'], 1)
for x in out['bowl']: x['role'], x['grp'] = bowl_role(x['id'])
dash = json.load(open(f'{OUT}/dashboard_data.json'))
def board_grp(kind, role):
    if kind == 'bat': return 'top' if role in ('Opener', 'Top order') else 'mid'
    r = role.lower()
    return 'death' if 'death' in r else 'newball' if 'new ball' in r else 'middle'
backups = {'bat': {}, 'bowl': {}}
GN = {'top': 'top-order', 'mid': 'middle-order', 'death': 'death-overs', 'newball': 'new-ball', 'middle': 'middle-overs'}
used_names = set()
for kind in ('bat', 'bowl'):
    # next-generation pool: buyable, not a veteran (first seen after 2015/16), active in 2023/24 or 2024/25;
    # a +3 DPR nudge for players who are also in form in SMAT 2025/26-2026/27
    pool = [x for x in out[kind] if x['status'] in POOL and not x['veteran'] and x['last'] >= '2023/24']
    pool = sorted(pool, key=lambda x: -(x['dpr'] + (3 if x['recent'] else 0)))
    used = set()
    for c in dash[f'{kind}_board']:
        g = board_grp(kind, c['role'])
        cand = [x for x in pool if x['grp'] == g and x['id'] not in used and x['name'] not in used_names] or [x for x in pool if x['id'] not in used and x['name'] not in used_names]
        if not cand: continue
        x = cand[0]; used.add(x['id']); used_names.add(x['name'])
        nm = x['full'] if x['full'] and not any(ch.isdigit() for ch in x['full']) else x['name']
        why = (f"{GN[g]} option from {x['team']}: " + (f"pressure SR {x['hp_sr']} against {x['hp_xsr']} expected" if kind == 'bat'
               else f"pressure economy {x['hp_econ']:.2f} against {x['hp_xecon']:.2f} expected") + f"; impact in the top {100 - x['imp_p']}% of SMAT")
        backups[kind][str(c['id'])] = {'id': x['id'], 'name': nm, 'team': x['team'], 'role': x['role'], 'dpr': x['dpr'], 'status': x['status'],
                                      'last': x['last'], 'first': x['first'], 'recent': x['recent'], 'why': why + (f"; in form: {x['recent']}" if x['recent'] else ''), 'for': c['name']}
    print(kind, [(v['for'], v['name'], v['role']) for v in backups[kind].values()])
# ---------- recent form (SMAT 2025/26 and 2026/27, from public records) with 2027 IPL status
byname = {k: {x['name']: x for x in out[k]} for k in out}
recent = []
for nm, st, kind, season, line, src, cs, vet in RECENT:
    x = byname[kind].get(cs) if cs else None
    st_ = L.status(cs, '2024/25', '2024/25', True) if cs else None
    t27 = (st_ or {}).get('ipl_team') if st_ and st_['status'] in ('rr', 'contracted') else L.ret_team(nm, nm)
    from ipl2027_lists import REL as _REL
    status = 'retired' if (st_ and st_['status'] == 'retired') else 'rr' if t27 == 'Rajasthan Royals' else 'contracted' if t27 else 'ipl_released' if (nm in _REL or (st_ and st_['status'] == 'ipl_released')) else 'pool'
    recent.append({'name': nm, 'state': st, 'kind': kind, 'season': season, 'line': line, 'src': src, 'veteran': bool(vet or (x and x['veteran'])),
                   'status': status, 'ipl_team': t27, 'dpr': x['dpr'] if x else None, 'rank': x['rank'] if x else None, 'n_rated': len(out[kind]),
                   'pressure': ((f"pressure SR {x['hp_sr']} v {x['hp_xsr']} expected" if kind == 'bat' else f"pressure econ {x['hp_econ']:.2f} v {x['hp_xecon']:.2f} expected") if x else None),
                   'last': x['last'] if x else None})
print('recent:', [(r['name'], r['status'], r['ipl_team'], r['dpr']) for r in recent])
json.dump({'validation': V, 'bat': out['bat'], 'bowl': out['bowl'], 'backups': backups, 'recent': recent, 'recent_src': RECENT_SRC}, open(f'{OUT}/smat.json', 'w'), default=str)
