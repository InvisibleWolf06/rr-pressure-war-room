"""Stage 6: Player Lab profiles, hidden-gem scouting, auction backups, RR retain/release.
Usage: python -I lab_export.py <data_dir> <out_dir>  ->  out/lab.json, out/scout.json
Shot zones are approximate: built from the stroke label plus the on/off-side tag, not ball tracking.
"""
import sys, json, numpy as np, pandas as pd
DATA, OUT = sys.argv[1], sys.argv[2]
b = pd.read_parquet(f'{OUT}/balls.parquet')
b['phase'] = b.phase.astype(str)
bat = pd.read_csv(f'{OUT}/bat_final.csv', index_col=0)
bowl = pd.read_csv(f'{OUT}/bowl_final.csv', index_col=0)
AV = pd.read_csv(f'{OUT}/availability.csv').drop_duplicates('player_id').set_index('player_id')
D = json.load(open(f'{OUT}/dashboard_data.json'))
rr = json.load(open(f'{OUT}/rr.json'))
bat_ep = pd.read_csv(f'{OUT}/bat_episodes.csv'); bowl_ep = pd.read_csv(f'{OUT}/bowl_episodes.csv')

ZONES = ['Fine leg', 'Square leg', 'Midwicket', 'Long on', 'Long off', 'Cover', 'Point', 'Third man']
ZMAP = {'Leg Glance': 0, 'Glance': 0, 'Paddle Scoop': 0, 'Paddle Sweep': 0, 'Hook Shot': 1, 'Sweep Shot': 1, 'Pull shot': 1,
        'Worked': 2, 'Flick': 2, 'Slog': 2, 'Slog Sweep': 2, 'PickUp': 2, 'On drive': 3, 'Off Drive': 4, 'Cover Drive': 5,
        'Inside out': 5, 'Square drive': 6, 'Square Cut': 6, 'Steer': 7, 'Late Cut': 7, 'UpperCut': 7, 'Reverse Sweep': 7,
        'Reverse Paddle Scoop': 7, 'Switch': 6}
def zone(stroke, side):
    if stroke == 'Straight Drive': return 3 if side == 'On-side' else 4
    if stroke in ZMAP: return ZMAP[stroke]
    return 2 if side == 'On-side' else 5
b['zone'] = [zone(s, o) for s, o in zip(b.stroke, b.on_or_off)]
def style(t):
    t = str(t).lower()
    if 'leg-break' in t or 'legbreak' in t: return 'Leg-spin'
    if 'offbreak' in t: return 'Off-spin'
    if 'orthodox' in t: return 'Left-arm orthodox'
    if 'chinaman' in t: return 'Left-arm wrist spin'
    return 'Left-arm pace' if t.startswith('left') else 'Right-arm pace'
b['style'] = b.bowling_type.map(style)
b['comp'] = np.where(b.is_ipl, 'IPL', 'T20I')
b['own_out'] = b.is_wicket & (b.dismissed_player_id == b.striker_id)
b['bwk'] = b.is_wicket & ~b.dismissal_type.isin(['RunOut', 'Retire Out', 'Obstracting the field', 'Obstructing the field'])
b['bdry'] = (b.runs >= 4) & b.legal
L = b[b.legal]

def r1(x): return round(float(x), 1)
def bat_slice(g, gall):
    n = len(g)
    if n == 0: return None
    runs = int(g.runs.sum())
    z = g.groupby('zone').runs.sum().reindex(range(8), fill_value=0).astype(int).tolist()
    side = [int(g[g.on_or_off == 'Off-side'].runs.sum()), int(g[g.on_or_off == 'On-side'].runs.sum())]
    sty = g.groupby('style').agg(n=('runs', 'size'), r=('runs', 'sum'), o=('own_out', 'sum'), d=('runs', lambda s: int((s == 0).sum())))
    dl = g.groupby('delivery_style').agg(n=('runs', 'size'), r=('runs', 'sum'), o=('own_out', 'sum'), d=('runs', lambda s: int((s == 0).sum()))).sort_values('n', ascending=False).head(10)
    st = g.groupby('stroke').agg(n=('runs', 'size'), r=('runs', 'sum'), o=('own_out', 'sum')).sort_values('r', ascending=False).head(8)
    return {'n': n, 'r': runs, 'o': int(g.own_out.sum()), 'd': int((g.runs == 0).sum()), 'b4': int(g.bdry.sum()), 'z': z, 'side': side,
            'sty': [[k, int(v.n), int(v.r), int(v.o), int(v.d)] for k, v in sty.iterrows()],
            'del': [[k, int(v.n), int(v.r), int(v.o), int(v.d)] for k, v in dl.iterrows()],
            'str': [[k, int(v.n), int(v.r), int(v.o)] for k, v in st.iterrows()]}

def bowl_slice(g):
    n = len(g)
    if n == 0: return None
    gl = g
    hand = gl.groupby('batting_type').agg(n=('runs', 'size'), r=('tot', 'sum'), w=('bwk', 'sum'), d=('tot', lambda s: int((s == 0).sum())))
    dl = gl.groupby('delivery_style').agg(n=('runs', 'size'), r=('tot', 'sum'), w=('bwk', 'sum'), d=('tot', lambda s: int((s == 0).sum()))).sort_values('n', ascending=False).head(10)
    # zones from the batter's view; mirror LHB so the map always reads as a right-hander's field
    z = g.groupby('zone').runs.sum().reindex(range(8), fill_value=0).astype(int).tolist()
    return {'n': n, 'r': int(g.tot.sum()), 'w': int(g.bwk.sum()), 'd': int((g.tot == 0).sum()), 'b4': int(g.bdry.sum()), 'z': z,
            'side': [int(g[g.on_or_off == 'Off-side'].runs.sum()), int(g[g.on_or_off == 'On-side'].runs.sum())],
            'hand': [[k, int(v.n), int(v.r), int(v.w), int(v.d)] for k, v in hand.iterrows()],
            'del': [[k, int(v.n), int(v.r), int(v.w), int(v.d)] for k, v in dl.iterrows()]}

PH = ['All', 'Powerplay', 'Middle', 'Death', 'Pressure']
def slices(g, fn):
    out = {}
    for comp in ['All', 'IPL', 'T20I']:
        gc = g if comp == 'All' else g[g.comp == comp]
        for ph in PH:
            gp = gc if ph == 'All' else gc[gc.hp] if ph == 'Pressure' else gc[gc.phase == ph]
            s = fn(gp) if fn is bowl_slice else fn(gp, gc)
            if s: out[f'{comp}|{ph}'] = s
    return out

squad = set(rr['squad'])
name_of = {**bat.name.to_dict(), **bowl.name.to_dict()}
want_bat = set(bat.index) | set(L[L.striker_name.isin(squad)].striker_id.unique())
want_bowl = set(bowl.index) | set(L[L.bowler_name.isin(squad)].bowler_id.unique())
lab = {'zones': ZONES, 'bat': {}, 'bowl': {}}
for p, g in L[L.striker_id.isin(want_bat)].groupby('striker_id'):
    if len(g) < 60: continue
    dis = b[(b.dismissed_player_id == p) & b.is_wicket].dismissal_type.value_counts().head(6)
    lab['bat'][str(int(p))] = {'name': g.striker_name.iloc[0], 'hand': g.batting_type.mode().iloc[0], 's': slices(g, bat_slice),
                               'dis': [[k, int(v)] for k, v in dis.items()]}
for p, g in b[b.bowler_id.isin(want_bowl)].groupby('bowler_id'):
    gl = g[g.legal]
    if len(gl) < 60: continue
    # bowler slices: legal balls for counts, runs incl. extras
    lab['bowl'][str(int(p))] = {'name': g.bowler_name.iloc[0], 'type': g.bowling_type.mode().iloc[0], 's': slices(gl, bowl_slice),
                                'dis': [[k, int(v)] for k, v in gl[gl.bwk].dismissal_type.value_counts().head(6).items()]}

# ---------------- scouting: hidden gems ----------------
def pct(s, asc=True): return s.rank(pct=True, ascending=asc)
H = L[L.hp]
def gem_table(kind):
    pid, wcol = ('striker_id', 'wpa_bat') if kind == 'bat' else ('bowler_id', 'wpa_bowl')
    R = bat if kind == 'bat' else bowl
    g = H.groupby(pid).agg(n=(wcol, 'size'), wpa=(wcol, 'sum'), big=(wcol, lambda s: int((s >= 0.05).sum())),
                           huge=(wcol, lambda s: int((s >= 0.10).sum())))
    allb = L.groupby(pid).agg(N=('runs', 'size'), runs=('runs', 'sum'), tot=('tot', 'sum'), outs=('own_out', 'sum'), wk=('bwk', 'sum'),
                              y26=('year', lambda s: int((s >= 2025).sum())))
    t = g.join(allb, how='inner')
    t = t[t.index.isin(R.index) & (t.n >= 40)]
    t['impact'] = t.wpa / (t.n + 60) * 100          # win % added per pressure ball, shrunk
    t['turn'] = t.big / (t.n + 60) * 100             # game-turning balls (>=5 pts) per 100 pressure balls
    if kind == 'bat':
        t['sr'] = t.runs / t.N * 100; t['avg'] = t.runs / t.outs.clip(lower=1)
        t['conv'] = (pct(t.sr) + pct(t.avg)) / 2
    else:
        t['econ'] = t.tot / t.N * 6; t['bpw'] = t.N / t.wk.clip(lower=1)
        t['conv'] = (pct(t.econ, asc=False) + pct(t.bpw, asc=False)) / 2
    t['imp_p'] = (pct(t.impact) * .6 + pct(t.turn) * .4)
    t['gem'] = t.imp_p - t.conv
    t['rank'] = R.s_rank.reindex(t.index); t['prr'] = R.s_PRR.reindex(t.index)
    t['avail'] = AV.status.reindex(t.index).fillna('available')
    # market-demand proxy (no price data): conventional output, IPL experience, recent volume
    ipl = R.ipl_seasons.reindex(t.index).fillna(0)
    t['demand'] = t.conv * .5 + (ipl.clip(upper=5) / 5) * .3 + pct(t.y26) * .2
    t['tier'] = pd.cut(t.demand, [-1, .45, .65, 2], labels=['Low', 'Medium', 'High']).astype(str)
    return t
G = {k: gem_table(k) for k in ['bat', 'bowl']}

def best_moment(kind, p):
    e = (bat_ep[bat_ep.striker_id == p] if kind == 'bat' else bowl_ep[bowl_ep.bowler_id == p]).sort_values('wpa', ascending=False)
    if not len(e): return None
    x = e.iloc[0]
    did = f"{int(x.runs)} off {int(x.balls)}" if kind == 'bat' else f"over {int(x.overid)}: {int(x.conceded)} runs, {int(x.wkts)} wkt"
    return {'date': str(x.match_date), 'comp': x.comp_name, 'opp': x.bowl_team if kind == 'bat' else x.bat_team, 'situation': x.situation,
            'did': did, 'wp': f"{x.wp0 * 100:.0f}% → {x.wp1 * 100:.0f}%", 'result': x.result}

def gem_rows(kind, n=25):
    t = G[kind]; R = bat if kind == 'bat' else bowl
    pool = t[(t.imp_p >= .70) & (t.gem >= .15)].sort_values(['gem', 'imp_p'], ascending=False)
    rows = []
    for p, r in pool.head(n).iterrows():
        c = R.loc[p]
        conv = f"SR {r.sr:.0f}, avg {r.avg:.0f}" if kind == 'bat' else f"econ {r.econ:.2f}, {r.bpw:.0f} balls per wicket"
        rows.append({'id': int(p), 'name': c['name'], 'role': c.role, 'nat': c.nationality, 'rank': int(r['rank']), 'prr': r1(r.prr),
                     'avail': r.avail, 'tier': r.tier, 'pb': int(r.n), 'impact': round(float(r.impact), 2), 'turn': r1(r.turn), 'big': int(r.big),
                     'imp_p': int(r.imp_p * 100), 'conv_p': int(r.conv * 100), 'gem': round(float(r.gem), 2), 'conv': conv,
                     'why': f"Ordinary on the scorecard ({conv}; better than {int(r.conv * 100)}% of rated players) but in the top {100 - int(r.imp_p * 100)}% for "
                            f"what he does to the result under pressure: {r.big} balls that each moved the win chance by 5+ points in {int(r.n)} pressure balls.",
                     'moment': best_moment(kind, p)})
    return rows

# ---------------- auction backups ----------------
def grp(kind, p):
    R = bat if kind == 'bat' else bowl; r = R.loc[p]
    if kind == 'bat': return 'top' if r.role in ('Opener', 'Top order') else 'mid'
    if r.kind != 'Pace': return 'spin'
    return 'death' if 'Death' in str(r.phase_role) else 'newball'
GL = {'top': 'top-order batter', 'mid': 'middle-order batter', 'spin': 'spinner', 'death': 'death bowler', 'newball': 'new-ball seamer'}
def backups(kind):
    R = bat if kind == 'bat' else bowl; t = G[kind]
    board = [c['id'] for c in D[f'{kind}_board']]
    buy = R[AV.status.reindex(R.index).fillna('available').isin(['available']) & ~R.index.isin(board)].copy()
    buy['g'] = [grp(kind, p) for p in buy.index]
    buy = buy.join(t[['tier', 'demand', 'gem', 'imp_p']], how='left')
    buy['demand'] = buy.demand.fillna(.3); buy['tier'] = buy.tier.fillna('Low'); buy['gem'] = buy.gem.fillna(-1)
    out = {}; seen = {}
    for p in board:
        g = grp(kind, p); pool = buy[buy.g == g]
        if len(pool) < 3: pool = buy
        used, picks = set(), []
        def take(df, label, why):
            df = df[~df.index.isin(used)]
            # spread backups across picks: prefer players not already offered as a backup
            if len(df): df = df.assign(_u=[seen.get(q, 0) for q in df.index]).sort_values('_u', kind='stable')
            if not len(df): return
            q = df.index[0]; used.add(q); seen[q] = seen.get(q, 0) + 1; r = buy.loc[q]
            picks.append({'id': int(q), 'name': r['name'], 'type': label, 'rank': int(r.s_rank), 'prr': r1(r.s_PRR), 'role': r.role, 'tier': r.tier,
                          'avail': AV.status.get(q, 'available'), 'why': why(r)})
        take(pool[pool.tier != 'High'].sort_values('s_PRR', ascending=False), 'Cheap value',
             lambda r: f"best-rated {GL[g]} with {r.tier.lower()} expected demand (rank {int(r.s_rank)})")
        take(pool[pool.s_rank <= 60].sort_values('demand', ascending=False), 'Bidding war',
             lambda r: f"the {GL[g]} other teams will want most ({r.tier.lower()} demand); bid only if the first choice goes")
        take(pool.sort_values('gem', ascending=False), 'Under the radar',
             lambda r: f"scorecard undersells him; pressure impact in the top {100 - int((r.imp_p if not pd.isna(r.imp_p) else .5) * 100)}%")
        out[str(p)] = picks
    return out

# ---------------- RR retain / release ----------------
SAL = {'Yashasvi Jaiswal': 18, 'Riyan Parag': 14, 'Ravindra Jadeja': 14, 'Dhruv Jurel': 14, 'Shimron Hetmyer': 11, 'Jofra Archer': 12.5,
       'Ravi Bishnoi': 7.2, 'Tushar Deshpande': 6.5, 'Sandeep Sharma': 4, 'Nandre Burger': 3.5, 'Sam Curran': 2.4, 'Adam Milne': 2.4,
       'Kwena Maphaka': 1.5, 'Vaibhav Sooryavanshi': 1.1, 'Donovan Ferreira': 1, 'Ravi Singh': .95, 'Shubham Dubey': .8, 'Kuldeep Sen': .75,
       'Yudhvir Singh': .35, 'Lhuan Pretorius': .3, 'Vignesh Puthur': .3, 'Sushant Mishra': .3, 'Yash Punja': .3, 'Brijesh Sharma': .3,
       'Aman Rao Perala': .3}
ipl_rr = L[L.is_ipl & (L.year >= 2025)]
mids_rr = set(b[(b.is_ipl) & (b.year >= 2025) & ((b.batting_team_id == b[b.striker_name == 'Yashasvi Jaiswal'].batting_team_id.mode().iloc[0]))].match_id)
def rr_row(n):
    ib = bat.index[bat.name == n]; iw = bowl.index[bowl.name == n]
    pb = int(ib[0]) if len(ib) else None; pw = int(iw[0]) if len(iw) else None
    rb = bat.loc[pb] if pb else None; rw = bowl.loc[pw] if pw else None
    best_rank = min([x for x in [rb.s_rank if rb is not None else None, rw.s_rank if rw is not None else None] if x is not None], default=None)
    sbat = ipl_rr[(ipl_rr.striker_name == n) & ipl_rr.match_id.isin(mids_rr)]; sbo = ipl_rr[(ipl_rr.bowler_name == n) & ipl_rr.match_id.isin(mids_rr)]
    hb, hw = sbat[sbat.hp], sbo[sbo.hp]
    wpa = float(hb.wpa_bat.sum() + hw.wpa_bowl.sum()); npb = len(hb) + len(hw)
    dem = None
    for k, p in (('bat', pb), ('bowl', pw)):
        if p is not None and p in G[k].index: dem = max(dem or 0, float(G[k].loc[p, 'demand']))
    sal = SAL.get(n)
    row = {'name': n, 'salary': sal, 'bat_rank': int(rb.s_rank) if rb is not None else None, 'bowl_rank': int(rw.s_rank) if rw is not None else None,
           'bat_prr': r1(rb.s_PRR) if rb is not None else None, 'bowl_prr': r1(rw.s_PRR) if rw is not None else None,
           'role': (rb.role if rb is not None and (rw is None or rb.s_rank <= rw.s_rank) else rw.role if rw is not None else 'Squad player'),
           'rr_pb': npb, 'rr_wpa': r1(wpa * 100), 'rr_runs': int(sbat.runs.sum()), 'rr_balls': int(len(sbat)), 'rr_overs': r1(len(sbo) / 6),
           'rr_conc': int(sbo.tot.sum()), 'rr_wk': int(sbo.bwk.sum()), 'demand': None if dem is None else ('High' if dem > .65 else 'Medium' if dem > .45 else 'Low'),
           'id_bat': pb, 'id_bowl': pw}
    # recommendation
    per = wpa / max(npb, 1) * 100
    if best_rank is not None and best_rank <= 25:
        rec, why = 'Retain: core', f"model rank {int(best_rank)}; one of the most reliable players under pressure in the data"
    elif best_rank is None and npb < 30:
        rec, why = ('Retain: cheap depth' if (sal or 0) <= 1 else 'Review'), 'too little senior T20 data to rate; ' + ('low salary, little to gain by releasing' if (sal or 0) <= 1 else 'salary is high for an unproven record')
    elif best_rank is not None and best_rank <= 60 and (sal or 0) <= 3:
        rec, why = 'Retain: value', f"rank {int(best_rank)} on a {sal} cr salary"
    elif best_rank is not None and best_rank <= 95 and (sal or 0) >= 4 and row['demand'] in ('Low', 'Medium'):
        rec, why = 'Release and buy back', f"rank {int(best_rank)}: worth having at the right price, but {sal} cr is a premium price and his expected auction demand is {row['demand'].lower()}: release, then bid lower in the auction (risk: another team bids)"
    elif best_rank is not None and best_rank <= 50:
        rec, why = 'Retain', f"rank {int(best_rank)}; replacing him at auction would cost as much"
    else:
        rec, why = 'Release', (f"model view: rank {int(best_rank)}" if best_rank else 'not rated') + (f" and {per:+.1f} win-% per pressure ball for RR" if npb >= 30 else '') + (f"; frees {sal} cr" if sal else '')
    if n in ('Vaibhav Sooryavanshi', 'Yashasvi Jaiswal') and not rec.startswith('Retain'): rec, why = 'Retain: core', why
    row['rec'], row['why'] = rec, why
    return row
squad_names = [n for n in SAL] + [n for n in rr['squad'] if n not in SAL]
# what RR actually did on 17 Nov 2026 (official IPL 2027 retention lists)
ACT_REL = {'Shimron Hetmyer', 'Tushar Deshpande', 'Adam Milne', 'Kwena Maphaka', 'Ravi Singh', 'Kuldeep Sen', 'Yudhvir Singh', 'Vignesh Puthur', 'Emanjot Singh Chahal'}
ACT_TRADE = {'Sam Curran': 'Traded to LSG'}
TRADE_IN = {'Mohammed Shami': 'Traded in from LSG', 'Manimaran Siddharth': 'Traded in from LSG'}
retain = []
for n in squad_names:
    r_ = rr_row(n)
    r_['actual'] = ACT_TRADE.get(n) or ('Released' if n in ACT_REL else 'Retained')
    m_ret = r_['rec'].startswith('Retain')
    r_['agree'] = None if r_['actual'].startswith('Traded') or r_['rec'] == 'Review' else (m_ret == (r_['actual'] == 'Retained'))
    retain.append(r_)
for n, a in TRADE_IN.items():
    if (bat.name == n).any() or (bowl.name == n).any():
        r_ = rr_row(n); r_['actual'] = a; r_['agree'] = None; r_['salary'] = None; retain.append(r_)
print('retain vs actual:', [(r_['name'], r_['rec'], r_['actual'], r_['agree']) for r_ in retain])

# ---------------- wider pool: pressure performers from outside the usual IPL pipeline ----------------
MP = pd.read_csv(f'{DATA}/competition_team_player_mapping.csv')
intl = MP[~MP.comp_name.str.contains('IPL')]
NAT = intl.assign(team_name=intl.team_name.str.replace(r' A$', '', regex=True)).groupby('player_id').team_name.agg(lambda s: s.mode().iloc[0])
BIG = {'India', 'Australia', 'England', 'South Africa', 'New Zealand', 'West Indies', 'Sri Lanka', 'Afghanistan', 'Pakistan'}
b['opp_tier'] = np.where(b.batting_team_id == b.home_team_id, b.away_tier, b.home_tier)
HH = b[b.legal & b.hp]
def wider(kind):
    pid, wcol, nm = ('striker_id', 'wpa_bat', 'striker_name') if kind == 'bat' else ('bowler_id', 'wpa_bowl', 'bowler_name')
    strong = HH.opp_tier.isin(['IPL', 'Full']) if kind == 'bat' else HH.opp_tier.isin(['IPL', 'Full'])
    if kind == 'bowl': strong = np.where(HH.batting_team_id == HH.home_team_id, HH.home_tier, HH.away_tier); strong = pd.Series(strong, index=HH.index).isin(['IPL', 'Full'])
    g = HH.groupby(pid).agg(n=(wcol, 'size'), wpa=(wcol, 'sum'), big=(wcol, lambda x: int((x >= 0.05).sum())), name=(nm, 'first'))
    gs = HH[strong].groupby(pid).agg(ns=(wcol, 'size'), wpas=(wcol, 'sum'))
    t = g.join(gs, how='left').fillna({'ns': 0, 'wpas': 0})
    t = t[t.n >= 40]
    t['impact'] = t.wpa / (t.n + 60) * 100; t['turn'] = t.big / (t.n + 60) * 100
    t['imp_p'] = pct(t.impact) * .6 + pct(t.turn) * .4
    t['strong_imp'] = t.wpas / (t.ns + 60) * 100
    t['nat'] = NAT.reindex(t.index)
    t = t[t.nat.notna() & ~t.nat.isin(BIG)]
    allb = L.groupby(pid).agg(N=('runs', 'size'), runs=('runs', 'sum'), tot=('tot', 'sum'), outs=('own_out', 'sum'), wk=('bwk', 'sum'))
    t = t.join(allb)
    R = bat if kind == 'bat' else bowl
    rows = []
    for p, r in t.sort_values('imp_p', ascending=False).head(18).iterrows():
        conv = f"SR {r.runs / r.N * 100:.0f}, avg {r.runs / max(r.outs, 1):.0f}" if kind == 'bat' else f"econ {r.tot / r.N * 6:.2f}, {r.N / max(r.wk, 1):.0f} balls per wicket"
        st_share = int(r.ns / r.n * 100)
        rows.append({'id': int(p), 'name': r['name'], 'nat': r.nat, 'pb': int(r.n), 'imp_p': int(r.imp_p * 100), 'impact': round(float(r.impact), 2),
                     'big': int(r.big), 'conv': conv, 'strong_share': st_share, 'strong_imp': round(float(r.strong_imp), 2), 'strong_n': int(r.ns),
                     'rated': bool(p in R.index), 'rank': int(R.loc[p].s_rank) if p in R.index else None,
                     'avail': AV.status.get(p, 'available') if r.nat != 'Pakistan' else 'ineligible',
                     'moment': best_moment(kind, p),
                     'note': (f"{st_share}% of his pressure balls came against Full-member or IPL opposition"
                              + (f"; against them he still added {r.strong_imp:+.2f} win-% per pressure ball" if r.ns >= 15 else '; too few against strong sides to check that it carries over'))})
    return rows

def scatter(kind):
    t = G[kind]; R = bat if kind == 'bat' else bowl
    return [[int(p), R.loc[p]['name'], int(r.conv * 100), int(r.imp_p * 100), int(r['rank']), r.avail] for p, r in t.iterrows()]
scout = {'wider': {'bat': wider('bat'), 'bowl': wider('bowl')}, 'scatter': {'bat': scatter('bat'), 'bowl': scatter('bowl')}, 'gems': {'bat': gem_rows('bat'), 'bowl': gem_rows('bowl')}, 'backups': {'bat': backups('bat'), 'bowl': backups('bowl')}, 'retain': retain,
         'salary_note': 'RR 2026 salaries from public squad lists (crore INR).', 'purse_2027': 27.05}
for w in scout['wider']['bat']:
    p = w['id']
    if str(p) not in lab['bat']:
        g = L[L.striker_id == p]
        dis = b[(b.dismissed_player_id == p) & b.is_wicket].dismissal_type.value_counts().head(6)
        lab['bat'][str(p)] = {'name': g.striker_name.iloc[0], 'hand': g.batting_type.mode().iloc[0], 's': slices(g, bat_slice), 'dis': [[k, int(v)] for k, v in dis.items()]}
for w in scout['wider']['bowl']:
    p = w['id']
    if str(p) not in lab['bowl']:
        g = b[b.bowler_id == p]; gl = g[g.legal]
        lab['bowl'][str(p)] = {'name': g.bowler_name.iloc[0], 'type': g.bowling_type.mode().iloc[0], 's': slices(gl, bowl_slice), 'dis': [[k, int(v)] for k, v in gl[gl.bwk].dismissal_type.value_counts().head(6).items()]}
json.dump(lab, open(f'{OUT}/lab.json', 'w'), separators=(',', ':'))
json.dump(scout, open(f'{OUT}/scout.json', 'w'), separators=(',', ':'), default=lambda o: o.item() if hasattr(o, 'item') else str(o))
import os
print('lab KB', os.path.getsize(f'{OUT}/lab.json') // 1024, 'bat', len(lab['bat']), 'bowl', len(lab['bowl']))
for k in ['bat', 'bowl']:
    print(k, 'gems', [(g['name'], g['rank'], g['avail'], g['imp_p'], g['conv_p']) for g in scout['gems'][k][:12]])
for k in ['bat', 'bowl']:
    for p, v in list(scout['backups'][k].items())[:3]: print(name_of.get(int(p)), [(x['type'], x['name'], x['tier']) for x in v])
for k in ['bat','bowl']: print('wider', k, [(w['name'], w['nat'], w['imp_p'], w['strong_share'], w['rated']) for w in scout['wider'][k]])
for r in retain[:0]: print(f"{r['name']:22s} {r['salary']} {r['bat_rank']} {r['bowl_rank']} {r['demand']} {r['rec']}: {r['why']}")
