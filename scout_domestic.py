"""RR Domestic Scout Score (DSS): ranks the Indian domestic players RR can buy and picks a role-matched
backup (plus an alternate) for every player on RR's auction board.

Built the way a franchise analyst would scout before an auction:
  P  Pressure skill   30%  run value on pressure balls + win probability added (SMAT ball-by-ball 2015/16-2024/25)
  R  Role fit         20%  run value in the phases the board pick is bought for (e.g. overs 16-20 for a death bowler)
  F  Current form     25%  SMAT 2025/26 and the 2026/27 games so far (public numbers in datasets/smat_recent_form.csv)
  T  Trajectory       10%  is he getting better? run value since 2021/22 against his earlier seasons
  D  Dependability    15%  how often he plays: SMAT games since 2021/22 plus 2025-27 games
Every component is a percentile (0-100) against active SMAT players. Small samples are shrunk towards average,
so a player with 40 balls cannot top a player with 600 on luck alone.
Hard filters: buyable for 2027 (not retained, not RR, not retired or excluded), not a veteran, active since 2022/23
or in the 2025-27 form lists. A back-test (features up to 2020/21, outcome = pressure performance 2021/22-2024/25)
checks that the score predicts later pressure performance better than scorecard numbers.

Usage: python -I scout_domestic.py <data_dir> <out_dir>
Reads out/smat_balls_scored.parquet, out/smat.json, out/dashboard_data.json; writes out/smat_scout.json and
updates out/smat.json (backups + scout)."""
import sys, os, json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smat_common import Linker, POOL, style_of, BORN
from recent_form import FORM, SRC
from ipl2027_lists import RET, REL
DATA, OUT = sys.argv[1], sys.argv[2]
W = {'S': .25, 'R': .20, 'F': .30, 'P': .15, 'D': .10}   # set from the back-test (see backtest_components in the output)
WKT = 10.0                       # runs a wicket is worth in a T20 innings (run-value currency)
RECENT_FROM = '2021/22'

L = Linker(DATA)

# ---------------- ball data and expectations
b = pd.read_parquet(f'{OUT}/smat_balls_scored.parquet')
b['wide'] = b.wide.astype(bool); b['noball'] = b.noball.astype(bool)
b['ov'] = b.over.astype(int)
# opposition quality: each team-season's runs per ball when batting and conceded per ball when bowling (shrunk)
_tb = b.groupby(['season', 'bat_team']).agg(r=('tot', 'sum'), n=('tot', 'size'))
_tw = b.groupby(['season', 'bowl_team']).agg(r=('tot', 'sum'), n=('tot', 'size'))
_lg = b.tot.mean()
BATQ = ((_tb.r + 600 * _lg) / (_tb.n + 600)).to_dict(); BOWLQ = ((_tw.r + 600 * _lg) / (_tw.n + 600)).to_dict()
b['opp_bowl_q'] = [BOWLQ[(s_, t_)] for s_, t_ in zip(b.season, b.bowl_team)]     # how leaky the attack a batter faced was
b['opp_bat_q'] = [BATQ[(s_, t_)] for s_, t_ in zip(b.season, b.bat_team)]        # how strong the line-up a bowler faced was
X = lambda d: np.c_[d.ov, d.wk, d.env, d.innings, d.bl]
XB = lambda d: np.c_[d.ov, d.wk, d.env, d.innings, d.bl, d.opp_bowl_q]
XW = lambda d: np.c_[d.ov, d.wk, d.env, d.innings, d.bl, d.opp_bat_q]
leg = b[~b.wide].copy()
leg['out'] = ((leg.player_out_id == leg.batter_id) & leg.is_wicket & ~leg.kind.isin(['retired hurt', 'retired out'])).astype(int)
rs = np.random.RandomState(7)
m_r = HistGradientBoostingRegressor(max_iter=150, learning_rate=.08, random_state=7).fit(XB(leg), leg.runs)
m_o = HistGradientBoostingClassifier(max_iter=150, learning_rate=.08, random_state=7).fit(XB(leg), leg.out)
leg['xr'] = m_r.predict(XB(leg)); leg['xo'] = m_o.predict_proba(XB(leg))[:, 1]
leg['rv'] = (leg.runs - leg.xr) + WKT * (leg.xo - leg.out)          # batter run value per ball faced
b['conc'] = b.tot - b.byes
b['bw'] = (b.is_wicket & ~b.kind.isin(['run out', 'retired hurt', 'retired out', 'obstructing the field'])).astype(int)
m_c = HistGradientBoostingRegressor(max_iter=150, learning_rate=.08, random_state=7).fit(XW(b), b.conc)
m_w = HistGradientBoostingClassifier(max_iter=150, learning_rate=.08, random_state=7).fit(XW(b), b.bw)
b['xc'] = m_c.predict(XW(b)); b['xw'] = m_w.predict_proba(XW(b))[:, 1]
b['rv'] = (b.xc - b.conc) + WKT * (b.bw - b.xw)                       # bowler run value per delivery
b['bwpa'] = -b.wpa
leg['bwpa'] = leg.wpa
# team strength: simple rating system on run-rate margin, opponent-adjusted, pooled over all seasons
# (the weaker sides mostly play each other in the same group, so raw numbers against them look inflated)
_inn = b.groupby(['match_id', 'innings', 'bat_team']).agg(r=('tot', 'sum'), n=('legal', 'sum')).reset_index()
_inn['rpo'] = _inn.r / (_inn.n.clip(lower=1) / 6)
_g = [(g_.iloc[0].bat_team, g_.iloc[1].bat_team, g_.iloc[0].rpo - g_.iloc[1].rpo) for _, g_ in _inn.groupby('match_id') if len(g_) >= 2]
_g = pd.DataFrame(_g, columns=['t1', 't2', 'm'])
TEAMR = dict.fromkeys(sorted(set(_g.t1) | set(_g.t2)), 0.0)
for _ in range(150):
    new = {t: np.mean(list(_g[_g.t1 == t].m + _g[_g.t1 == t].t2.map(TEAMR)) + list(-_g[_g.t2 == t].m + _g[_g.t2 == t].t1.map(TEAMR))) for t in TEAMR}
    mu = np.mean(list(new.values())); TEAMR = {k: v - mu for k, v in new.items()}
OPPW = {t: float(np.clip(1 + 0.3 * min(r, 0), 0.15, 1.0)) for t, r in TEAMR.items()}   # weaker than average -> counts less
WEAK_TEAMS = sorted([t for t, w in OPPW.items() if w < .7], key=lambda t: OPPW[t])
leg['wt'] = leg.bowl_team.map(OPPW).fillna(1.0)      # batter facing a weak attack
b['wt'] = b.bat_team.map(OPPW).fillna(1.0)           # bowler facing a weak line-up
print('opposition weights <0.7:', {t: round(OPPW[t], 2) for t in WEAK_TEAMS})
for t_ in (leg, b):
    t_['rvw'] = t_.rv * t_.wt; t_['bwpaw'] = t_.bwpa * t_.wt

# batting position (order of arrival in the innings)
arr = pd.concat([b[['match_id', 'innings', 'seq', 'batter_id']].rename(columns={'batter_id': 'p'}),
                 b[['match_id', 'innings', 'seq', 'non_striker_id']].rename(columns={'non_striker_id': 'p'})])
arr = arr.groupby(['match_id', 'innings', 'p']).seq.min().reset_index().sort_values('seq')
arr['pos'] = arr.groupby(['match_id', 'innings']).cumcount() + 1
POS = arr.groupby('p').pos.median()
team_games = b.groupby(['season', 'bat_team']).match_id.nunique()
FIRST_ALL = pd.concat([b[['season', 'batter_id']].set_axis(['season', 'p'], axis=1), b[['season', 'non_striker_id']].set_axis(['season', 'p'], axis=1),
                       b[['season', 'bowler_id']].set_axis(['season', 'p'], axis=1)]).groupby('p').season.min()

def shr(s, n, k): return s / (n + k)
def pct_of(vals, ref):
    ref = np.sort(np.asarray([r for r in ref if np.isfinite(r)]))
    return np.array([100 * np.searchsorted(ref, v, side='right') / len(ref) if np.isfinite(v) else 50.0 for v in vals])

def profile(d, kind, idcol, upto=None, since=None):
    """Per-player features from a ball table (optionally restricted to a season window)."""
    if upto: d = d[d.season <= upto]
    if since: d = d[d.season >= since]
    g = d.groupby(idcol)
    f = pd.DataFrame({'n': g.wt.sum(), 'n_raw': g.size(), 'rv': g.rvw.sum(), 'last': g.season.max(), 'first': g.season.min(),
                      'name': g[('batter' if kind == 'bat' else 'bowler')].last(),
                      'team': g[('bat_team' if kind == 'bat' else 'bowl_team')].agg(lambda s: s.mode().iat[0])})
    h = d[d.hp == 1].groupby(idcol)
    f['hp_n'] = h.wt.sum(); f['hp_rv'] = h.rvw.sum(); f['hp_wpa'] = h.bwpaw.sum()
    for ph in ('Powerplay', 'Middle', 'Death'):
        q = d[d.phase == ph].groupby(idcol)
        f[f'n_{ph}'] = q.wt.sum(); f[f'rv_{ph}'] = q.rvw.sum()
    f = f.fillna(0)
    rec_cut = since or RECENT_FROM
    r = d[d.season >= (RECENT_FROM if not upto else '2018/19')].groupby(idcol); o = d[d.season < (RECENT_FROM if not upto else '2018/19')].groupby(idcol)
    f['n_rec'] = r.wt.sum(); f['rv_rec'] = r.rvw.sum(); f['n_old'] = o.wt.sum(); f['rv_old'] = o.rvw.sum()
    gm = d[d.season >= (RECENT_FROM if not upto else '2018/19')].groupby(idcol).match_id.nunique()
    f['games_rec'] = gm
    return f.fillna(0)

def components(f, kind):
    """Raw (pre-percentile) values for P, phase skills, T, D."""
    k_all, k_hp, k_ph = (120, 40, 60) if kind == 'bat' else (120, 40, 60)
    c = pd.DataFrame(index=f.index)
    c['p_rv'] = shr(f.hp_rv, f.hp_n, k_hp); c['p_wpa'] = shr(f.hp_wpa, f.hp_n, k_hp)
    for ph in ('Powerplay', 'Middle', 'Death'):
        c[f'ph_{ph}'] = shr(f[f'rv_{ph}'], f[f'n_{ph}'], k_ph)
        c[f'sh_{ph}'] = f[f'n_{ph}'] / f.n.clip(lower=1)
    both = (f.n_rec >= 30) & (f.n_old >= 30)
    c['traj'] = np.where(both, shr(f.rv_rec, f.n_rec, 80) - f.rv_old / f.n_old.clip(lower=1), np.nan)
    c['dep'] = f.games_rec
    c['all_rv'] = shr(f.rv, f.n, k_all)
    return c

# ---------------- form (2025/26 + 2026/27 public numbers)
def form_scores(F):
    F = F.copy()
    def idx(r):
        if r.kind == 'bat':
            if pd.isna(r.runs): return np.nan
            m = r.matches if pd.notna(r.matches) and r.matches > 0 else (8 if r.season == '2025/26' else 4)
            sr = r.sr if pd.notna(r.sr) else 140
            return (r.runs / m) * (sr / 140)
        if pd.isna(r.wkts): return np.nan
        m = r.matches if pd.notna(r.matches) and r.matches > 0 else (8 if r.season == '2025/26' else 4)
        ec = r.econ if pd.notna(r.econ) else 8.5
        return (r.wkts / m) * (8.5 / ec)
    F['idx'] = F.apply(idx, axis=1)
    F['fs'] = 62.0
    plate = F.get('level', pd.Series('Elite', index=F.index)).fillna('Elite').str.lower().eq('plate')
    for (k, s), g in F.groupby(['kind', 'season']):
        ok = g.idx.notna()
        if ok.sum():
            F.loc[g.index[ok], 'fs'] = 55 + 45 * g.idx[ok].rank(pct=True)
    F.loc[plate, 'fs'] -= 20          # Plate-group runs and wickets come against the weakest sides
    F['key'] = np.where(F.cricsheet_name != '', F.cricsheet_name, F.player)
    out = {}
    for (k, key), g in F.groupby(['kind', 'key']):
        g = g.sort_values('season')
        v = g.fs.iloc[-1] if len(g) == 1 else .55 * g.fs.iloc[-1] + .45 * g.fs.iloc[-2]
        gm = g.matches.fillna(0).sum()
        out[(k, key)] = {'F': float(v), 'lines': [f"{r.season}: {r.performance}" for r in g.itertuples()], 'player': g.player.iloc[-1],
                         'state': g.state.iloc[-1], 'role': g.role.dropna().iloc[-1] if g.role.notna().any() else None,
                         'style': g['style'].dropna().iloc[-1] if g['style'].notna().any() else None, 'games': float(gm),
                         'veteran': bool(g.veteran.max()), 'src': [SRC[x][1] for x in g.source_id if x in SRC]}
    return out
FS = form_scores(FORM)

# ---------------- roles and targets
def bat_role(pid, f_row, c_row):
    pos = POS.get(pid, 5)
    if pos <= 2: return 'Opener'
    if pos <= 4: return 'Top order'
    if c_row['sh_Death'] >= .4 and pos >= 5: return 'Finisher'
    return 'Middle order'
def bowl_role(c_row):
    if c_row['sh_Death'] >= .35: return 'Death overs'
    if c_row['sh_Powerplay'] >= .40: return 'New ball'
    return 'Middle overs'
BAT_T = {'Opener': ({'Powerplay': .7, 'Middle': .3}, {'Opener', 'Top order'}),
         'Top order': ({'Powerplay': .4, 'Middle': .6}, {'Opener', 'Top order'}),
         'Middle order': ({'Middle': .6, 'Death': .4}, {'Top order', 'Middle order', 'Finisher'}),
         'Finisher': ({'Death': .75, 'Middle': .25}, {'Middle order', 'Finisher'})}
def bowl_target(role):
    r = role.lower()
    if 'spin' in r: return {'Middle': .8, 'Powerplay': .2}, 'spin', ('left' if r.startswith('left') else None), ('wrist' if 'wrist' in r else 'finger')
    arm = 'left' if r.startswith('left') else None
    if 'new ball + death' in r: return {'Powerplay': .5, 'Death': .5}, 'pace', arm, None
    if 'death' in r: return {'Death': .7, 'Middle': .3}, 'pace', arm, None
    return {'Powerplay': .7, 'Middle': .2, 'Death': .1}, 'pace', arm, None

# ---------------- build candidate tables
def build(kind):
    d = leg if kind == 'bat' else b
    idcol = 'batter_id' if kind == 'bat' else 'bowler_id'
    f = profile(d, kind, idcol); c = components(f, kind)
    ref = f[(f.n >= 60) & (f['last'] >= '2019/20')].index           # active reference population
    P = (pct_of(c.p_rv, c.loc[ref, 'p_rv']) + pct_of(c.p_wpa, c.loc[ref, 'p_wpa'])) / 2
    Sk = pct_of(c.all_rv, c.loc[ref, 'all_rv'])
    T = pct_of(c.traj, c.loc[ref, 'traj'])
    PH = {ph: pct_of(c[f'ph_{ph}'], c.loc[ref, f'ph_{ph}']) for ph in ('Powerplay', 'Middle', 'Death')}
    rows = []
    for i, pid in enumerate(f.index):
        fr, cr = f.loc[pid], c.loc[pid]
        if fr.n_raw < 30: continue
        cs = fr['name']
        fm = FS.get((kind, cs))
        st = L.status(cs, fr['last'], FIRST_ALL.get(pid, fr['first']), in_form=fm is not None)
        if kind == 'bat': role = (fm or {}).get('role') or bat_role(pid, fr, cr); style = arm = btype = None; ssrc = None
        else:
            role = bowl_role(cr)
            style, arm, ssrc = style_of(cs, st['full'], st['bowling_type'])
            if not style and fm and fm.get('style'): style, ssrc = fm['style'], 'form list'
            if not style: style, ssrc = ('pace' if cr.sh_Powerplay + cr.sh_Death >= .5 else 'spin'), 'inferred from overs bowled'
            btype = st['bowling_type']
        rows.append({'id': pid, 'name': cs, 'full': st['full'], 'team': fr.team, 'kind': kind, 'role': role, 'style': style, 'arm': arm, 'btype': btype, 'style_src': ssrc,
                     'status': st['status'], 'ipl_team': st['ipl_team'], 'excluded': st['excluded'],
                     'veteran': bool(st['veteran'] or (fm or {}).get('veteran', False)), 'first': FIRST_ALL.get(pid, fr['first']), 'last': fr['last'],
                     'balls': int(fr.n_raw), 'hp_balls': int(round(fr.hp_n)), 'weak_share': round(1 - fr.n / max(fr.n_raw, 1), 2), 'P': float(P[i]), 'T': float(T[i]), 'S': float(Sk[i]),
                     'sh': {ph: float(cr[f'sh_{ph}']) for ph in ('Powerplay', 'Middle', 'Death')},
                     'PH': {ph: float(PH[ph][i]) for ph in PH}, 'dep_raw': float(fr.games_rec + ((fm or {}).get('games') or 0)),
                     'F': (fm or {}).get('F', 35.0), 'form': (fm or {}).get('lines', []), 'form_src': (fm or {}).get('src', []), 'in_data': True,
                     'rv100': round(float(cr.all_rv) * 100, 1), 'hp_rv100': round(float(cr.p_rv) * 100, 1)})
    seen = {r['name'] for r in rows}
    # form-list players with no ball-by-ball record (or a blank cricsheet name)
    for (k, key), fm in FS.items():
        if k != kind or key in seen: continue
        nm = fm['player']
        t27 = RET.get(nm) or L.ret_team(nm, nm)
        exc = None
        from smat_common import EXCL_FULL
        exc = EXCL_FULL.get(nm)
        status = 'retired' if exc else 'rr' if t27 == 'Rajasthan Royals' else 'contracted' if t27 else 'ipl_released' if nm in REL else 'uncapped'
        rows.append({'id': f'form:{nm}', 'name': nm, 'full': nm, 'team': fm['state'], 'kind': kind, 'role': fm['role'] or ('Middle order' if kind == 'bat' else 'Middle overs'),
                     'role_known': bool(fm['role']), 'style': fm['style'], 'arm': None, 'btype': None, 'style_src': 'form list' if fm['style'] else None,
                     'status': status, 'ipl_team': t27, 'excluded': exc, 'veteran': fm['veteran'] or BORN.get(nm, 2100) <= 1993, 'first': None, 'last': None,
                     'balls': 0, 'hp_balls': 0, 'P': 50.0, 'T': 50.0, 'S': 50.0, 'sh': None, 'PH': {'Powerplay': 50.0, 'Middle': 50.0, 'Death': 50.0}, 'dep_raw': fm['games'] or 3,
                     'F': fm['F'], 'form': fm['lines'], 'form_src': fm['src'], 'in_data': False, 'rv100': None, 'hp_rv100': None})
    df = pd.DataFrame(rows)
    df['D'] = pct_of(df.dep_raw, df.loc[df.in_data & (df['last'].fillna('') >= '2019/20'), 'dep_raw'])
    return df

def disp(r):
    f = r.get('full')
    return f if isinstance(f, str) and f and not any(ch.isdigit() for ch in f) else r['name']

def confidence(r):
    if not r['in_data']: return 'Low'
    if r['balls'] >= 250 and r['hp_balls'] >= 40 and (r['form'] or r['last'] >= '2023/24'): return 'High'
    if r['balls'] >= 100 or (r['form'] and r['balls'] >= 40): return 'Medium'
    return 'Low'

def eligible(r):
    if r['status'] not in POOL: return False
    if r['veteran'] or isinstance(r['excluded'], str): return False
    return bool(r['form']) or (r['last'] or '') >= '2022/23'

def score_for(r, phases, kind, tgt=None):
    R = sum(w * r['PH'][ph] for ph, w in phases.items())
    s = W['S'] * r['S'] + W['P'] * r['P'] + W['R'] * R + W['F'] * r['F'] + W['D'] * r['D']
    adj, notes = 0.0, []
    if kind == 'bowl' and tgt:
        _, style, arm, spin_kind = tgt
        if arm == 'left' and r.get('arm') == 'left': adj += 3; notes.append('left-arm like the board pick')
        if spin_kind and isinstance(r.get('btype'), str):
            wrist = any(k in r['btype'] for k in ('Leg', 'Chinaman'))
            if (spin_kind == 'wrist') == wrist: adj += 2; notes.append(f'{spin_kind}-spinner like the board pick')
        if r.get('style_src') == 'inferred from overs bowled': adj -= 3; notes.append('bowling style inferred, check video')
    if not r['in_data']: adj -= 4; notes.append('no SMAT ball-by-ball before 2025; scout on video')
    elif r.get('weak_share', 0) >= .2: notes.append(f"much of his record is against weaker sides (discounted {round(r['weak_share'] * 100)}%)")
    return round(s + adj, 1), round(R, 1), notes

def why(r, R):
    bits = []
    if r['in_data']:
        bits.append(f"overall skill in the top {max(1, round(100 - r['S']))}% of active SMAT players ({r['rv100']:+.1f} runs per 100 balls against expectation, adjusted for opposition)" if r['S'] >= 60
                    else f"overall skill {r['S']:.0f}th percentile ({r['rv100']:+.1f} runs per 100 balls)")
        if r['P'] >= 70: bits.append(f"strong under pressure ({r['hp_rv100']:+.1f} runs per 100 pressure balls)")
        bits.append(f"role fit {R:.0f}th percentile for this job")
        if r['T'] >= 65: bits.append('improving: better since 2021/22 than before')
    if r['form']: bits.append('in form: ' + '; '.join(r['form']))
    else: bits.append('not among the 2025-27 leading run-scorers or wicket-takers in our sources')
    return '; '.join(bits)

tables = {k: build(k) for k in ('bat', 'bowl')}
for k, df in tables.items():
    df['confidence'] = df.apply(confidence, axis=1)
    df['eligible'] = df.apply(eligible, axis=1)

# ---------------- backups for RR's board
D_ = json.load(open(f'{OUT}/dashboard_data.json'))
backups, targets = {'bat': {}, 'bowl': {}}, {}
for kind in ('bat', 'bowl'):
    df = tables[kind]; pool = [r for r in df.to_dict('records') if r['eligible']]
    used_p, used_a = set(), set()
    for c in D_[f'{kind}_board']:
        if kind == 'bat':
            phases, okroles = BAT_T.get(c['role'], BAT_T['Top order']); tgt = None
            cand = [r for r in pool if r['role'] in okroles or (not r.get('role_known', True))]
        else:
            tgt = bowl_target(c['role']); phases = tgt[0]
            need = {'Death': ('Death', .20), 'Powerplay': ('Powerplay', .25)}
            key = max(phases, key=phases.get)
            def fits(r):
                if r['style'] not in (tgt[1], None): return False
                if r['sh'] is None or key not in need: return True
                return r['sh'][need[key][0]] >= need[key][1]          # actually bowls in that phase
            cand = [r for r in pool if fits(r)]
        scored = []
        for r in cand:
            s, R, notes = score_for(r, phases, kind, tgt)
            scored.append((s, R, notes, r))
        scored.sort(key=lambda x: -x[0])
        pick = lambda used, ok=lambda r: True: next((x for x in scored if x[3]['name'] not in used and ok(x[3])), None)
        p = pick(used_p | used_a, lambda r: r['confidence'] in ('High', 'Medium')) or pick(used_p | used_a); used_p.add(p[3]['name'])
        a = pick(used_p | used_a); used_a.add(a[3]['name'])
        def pack(x):
            s, R, notes, r = x
            return {'name': disp(r), 'cs': r['name'], 'team': r['team'], 'role': r['role'],
                    'style': r['style'], 'dss': s, 'P': round(r['P']), 'R': round(R), 'F': round(r['F']), 'S': round(r['S']), 'D': round(r['D']),
                    'confidence': r['confidence'], 'status': r['status'], 'first': r['first'], 'last': r['last'], 'balls': r['balls'],
                    'form': r['form'], 'form_src': r['form_src'], 'notes': notes, 'why': why(r, R),
                    'dpr': s, 'recent': (r['form'][-1] if r['form'] else None)}      # dpr/recent keep the old RR Fit widget working
        backups[kind][str(c.get('id', c['name']))] = {**pack(p), 'for': c['name'], 'pick_role': c['role'], 'alt': pack(a)}
    # overall top targets (role-neutral: R = average of the player's own role phases)
    allr = []
    for r in pool:
        if kind == 'bat': ph = BAT_T.get(r['role'], BAT_T['Middle order'])[0]
        else: ph = {'Death overs': {'Death': .7, 'Middle': .3}, 'New ball': {'Powerplay': .7, 'Middle': .3}}.get(r['role'], {'Middle': .8, 'Powerplay': .2})
        s, R, notes = score_for(r, ph, kind)
        allr.append({'name': disp(r), 'team': r['team'], 'role': r['role'], 'style': r['style'],
                     'dss': s, 'P': round(r['P']), 'R': round(R), 'F': round(r['F']), 'S': round(r['S']), 'D': round(r['D']), 'confidence': r['confidence'],
                     'status': r['status'], 'first': r['first'], 'last': r['last'], 'balls': r['balls'], 'form': r['form'], 'notes': notes, 'why': why(r, R)})
    targets[kind] = sorted(allr, key=lambda x: -x['dss'])[:25]
    print(kind, 'eligible', len(pool), 'of', len(df))
    for nm, x in backups[kind].items():
        print(f"  {x['for']:22s} -> {x['name']:22s} {x['team'][:14]:14s} {x['role']:12s} {x['dss']:5.1f} [{x['confidence']}]  alt: {x['alt']['name']} {x['alt']['dss']}")

# ---------------- back-test: does the score predict later pressure performance?
def backtest(kind, cut, fseason, post_from):
    """Score players with data up to `cut` + form from `fseason`; outcome = pressure run value from `post_from` on."""
    d = leg if kind == 'bat' else b
    idcol = 'batter_id' if kind == 'bat' else 'bowler_id'
    pre = profile(d, kind, idcol, upto=cut); cp = components(pre, kind)
    s1 = d[d.season == fseason].groupby(idcol)
    fs = s1.rvw.sum() / (s1.wt.sum() + 60)
    post = d[d.season >= post_from]; h = post[post.hp == 1].groupby(idcol)
    y = shr(h.rvw.sum(), h.wt.sum(), 40)
    ids = [i for i in pre.index if pre.loc[i, 'n'] >= 60 and h.size().get(i, 0) >= 25]
    ref = pre.index[pre.n >= 60]
    C = {'S': pct_of(cp.loc[ids, 'all_rv'], cp.loc[ref, 'all_rv']),
         'P': (pct_of(cp.loc[ids, 'p_rv'], cp.loc[ref, 'p_rv']) + pct_of(cp.loc[ids, 'p_wpa'], cp.loc[ref, 'p_wpa'])) / 2,
         'R': np.mean([pct_of(cp.loc[ids, f'ph_{ph}'], cp.loc[ref, f'ph_{ph}']) for ph in ('Powerplay', 'Middle', 'Death')], axis=0),
         'T': pct_of(cp.loc[ids, 'traj'], cp.loc[ref, 'traj']), 'D': pct_of(cp.loc[ids, 'dep'], cp.loc[ref, 'dep'])}
    fm = pd.Series(ids).map(fs)
    C['F'] = np.where(fm.notna(), 55 + 45 * fm.rank(pct=True).fillna(0), 35)
    dss = sum(W[k] * C[k] for k in W)
    yy = y.loc[ids].values
    g = d[d.season <= cut].groupby(idcol)
    if kind == 'bat':
        naive = ((g.runs.sum() / g.out.sum().clip(lower=1)) * (g.runs.sum() / g.size())).loc[ids]     # average x strike rate
    else:
        naive = ((g.bw.sum() / g.size()) * 24 - (g.conc.sum() / g.size()) * 6 / 4).loc[ids]           # wickets per 4 overs minus economy/4
    q = np.quantile(dss, .8); thr = np.quantile(yy, .6); qn = np.quantile(naive.values, .8)
    return {'n': len(ids), 'dss': spearmanr(dss, yy)[0], 'scorecard': spearmanr(naive, yy)[0],
            'top20_hit': float((yy[dss >= q] >= thr).mean()), 'top20_hit_scorecard': float((yy[naive.values >= qn] >= thr).mean()),
            'components': {k: round(float(spearmanr(v, yy)[0]), 3) for k, v in C.items()}}
WINDOWS = [('2018/19', '2019/20', '2020/21'), ('2019/20', '2020/21', '2021/22')]
BT = {}
for k in ('bat', 'bowl'):
    rs = [backtest(k, *w) for w in WINDOWS]
    BT[k] = {'windows': [f'data to {w[0]}, form {w[1]}, judged on pressure balls {w[2]} onwards' for w in WINDOWS],
             'n': [r['n'] for r in rs], 'dss': round(float(np.mean([r['dss'] for r in rs])), 3), 'scorecard': round(float(np.mean([r['scorecard'] for r in rs])), 3),
             'top20_hit': round(float(np.mean([r['top20_hit'] for r in rs])), 3), 'top20_hit_scorecard': round(float(np.mean([r['top20_hit_scorecard'] for r in rs])), 3),
             'components': {c: round(float(np.mean([r['components'][c] for r in rs])), 3) for c in rs[0]['components']}}

print('backtest', BT)

method = {'weights': W, 'wicket_runs': WKT,
          'components': {'S': 'Overall skill: run value per ball against expectation (game state, ground, season and the strength of the opposition), SMAT 2015/16-2024/25, shrunk towards average for small samples',
                         'P': 'Pressure skill: run value and win probability added on pressure balls (the 20% of balls that can swing a game most)',
                         'R': "Role fit: run value in the phases the board pick is bought for (openers: powerplay; finishers and death bowlers: overs 16-20; spinners: overs 7-15)",
                         'F': 'Current form: SMAT 2025/26 and 2026/27 (to 20 Nov 2026), runs per game x strike rate or wickets per game x economy, ranked within each season (55-100; Plate group -20); 35 if not among the leaders',
                         'D': 'Dependability: SMAT games since 2021/22 plus 2025-27 games'},
          'opposition': 'Every ball is weighted by the strength of the opposition (a rating of all 38 sides from run-rate margins, opponent-adjusted, 2015/16-2024/25): balls against below-average sides count less, down to 15% against the weakest; expectations also adjust for each opponent team-season',
          'weak_teams': {t: round(OPPW[t], 2) for t in WEAK_TEAMS},
          'filters': ['no IPL 2027 contract (all ten retention lists, 17 Nov 2026)', 'not retired or excluded (datasets/exclusions.csv)',
                      'not a veteran: not playing the SMAT in 2015/16 and not aged 33+', 'active since 2022/23 or in the 2025-27 form lists',
                      'same role (batting slot) or same bowling type (pace/spin) as the board pick'],
          'backtest': BT}
scout = {'method': method, 'backups': backups, 'targets': targets}
json.dump(scout, open(f'{OUT}/smat_scout.json', 'w'), default=float)
S = json.load(open(f'{OUT}/smat.json'))
S['backups'] = backups; S['scout'] = {'method': method, 'targets': targets}
json.dump(S, open(f'{OUT}/smat.json', 'w'), default=float)
print('wrote smat_scout.json')
