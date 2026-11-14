"""Stage 4: variety-aware top-10 selection, RR fit tags, signature moments -> dashboard JSON.
Usage: python -I select.py <out_dir>
"""
import sys, json, numpy as np, pandas as pd
OUT = sys.argv[1]
bat = pd.read_csv(f'{OUT}/bat_final.csv', index_col=0)
bowl = pd.read_csv(f'{OUT}/bowl_final.csv', index_col=0)
b = pd.read_parquet(f'{OUT}/balls.parquet')
x = pd.read_parquet(f'{OUT}/expect.parquet')
b = b.merge(x, on=['match_id', 'innings', 'innings_ball_num'], how='left')
bat_ep = pd.read_csv(f'{OUT}/bat_episodes.csv')
bowl_ep = pd.read_csv(f'{OUT}/bowl_episodes.csv')
ext = json.load(open(f'{OUT}/extras.json'))
val = json.load(open(f'{OUT}/validation.json'))
rr = json.load(open(f'{OUT}/rr.json'))
RR_SQUAD = set(rr['squad'])

# ---------- RR-fit split metrics (pressure balls) ----------
h = b[b.hp & b.legal].copy()
h['own_out'] = (h.is_wicket & (h.dismissed_player_id == h.striker_id)).astype(float)
h['bwk'] = (h.is_wicket & h.dismissal_type.ne('RunOut')).astype(float)

def bat_split(mask, tag):
    g = h[mask].groupby('striker_id').agg(n=('runs', 'size'), r=('runs', 'sum'), xr=('x_runs', 'sum'), o=('own_out', 'sum'))
    g[tag + '_sr'] = g.r / g.n * 100; g[tag + '_xsr'] = g.xr / g.n * 100; g[tag + '_n'] = g.n; g[tag + '_outs'] = g.o
    return g[[tag + '_sr', tag + '_xsr', tag + '_n', tag + '_outs']]

def bowl_split(mask, tag):
    g = h[mask].groupby('bowler_id').agg(n=('runs', 'size'), r=('runs', 'sum'), xr=('x_runs', 'sum'), w=('bwk', 'sum'))
    g[tag + '_econ'] = g.r / g.n * 6; g[tag + '_xecon'] = g.xr / g.n * 6; g[tag + '_n'] = g.n; g[tag + '_wk'] = g.w
    return g[[tag + '_econ', tag + '_xecon', tag + '_n', tag + '_wk']]

bat = bat.join(bat_split(h.pace_or_spin == 'Spin', 'vspin')).join(bat_split(h.phase == 'Death', 'death')) \
         .join(bat_split(h.comp_name.str.startswith('IPL'), 'ipl'))
bowl = bowl.join(bowl_split(h.phase == 'Death', 'death')).join(bowl_split(h.phase == 'Middle', 'mid')) \
           .join(bowl_split(h.comp_name.str.startswith('IPL'), 'ipl'))

# ---------- variety-aware selection ----------
def select(R, rules, caps, gate):
    pool = R[gate(R)].sort_values('s_prr_raw', ascending=False)
    # a minimum can never ask for more players than the gated pool holds
    rules = {k: (f, min(need, int(sum(f(R.loc[p]) for p in pool.index)))) for k, (f, need) in rules.items()}
    chosen = []
    def counts(lst):
        return {k: sum(f(R.loc[p]) for p in lst) for k, (f, _) in {**rules, **caps}.items()}
    for p in pool.index:
        trial = chosen + [p]
        c = counts(trial)
        if any(c[k] > cap for k, (_, cap) in caps.items()):
            continue
        slots_left = 10 - len(trial)
        unmet = sum(max(0, need - c[k]) for k, (_, need) in rules.items())
        if unmet > slots_left:
            continue
        chosen.append(p)
        if len(chosen) == 10:
            break
    return chosen

bat_rules = {'Top order (No.3-4)': (lambda r: r.role == 'Top order', 2),
             'Middle order / finisher': (lambda r: r.role in ('Middle order', 'Finisher'), 3),
             'Left-hander': (lambda r: r.hand == 'LHB', 2)}
bat_caps = {'Openers': (lambda r: r.role == 'Opener', 3),
            'Overseas': (lambda r: bool(r.overseas), 5),
            'IPL-untested': (lambda r: r.ipl_seasons == 0, 2)}
bowl_rules = {'Death specialist': (lambda r: 'Death' in str(r.phase_role), 3),
              'New-ball pace': (lambda r: 'New ball' in str(r.phase_role), 2),
              'Wrist spin': (lambda r: r.kind == 'Wrist spin', 2),
              'Finger spin': (lambda r: r.kind == 'Finger spin', 1),
              'Left-arm': (lambda r: bool(r.left_arm), 2)}
bowl_caps = {'Spinners': (lambda r: r.kind != 'Pace', 5),
             'Overseas': (lambda r: bool(r.overseas), 6),
             'IPL-untested': (lambda r: r.ipl_seasons == 0, 2)}
gate = lambda R: (R.s_p_top25 >= 0.20) & (R.s_rank <= 25) & (R.nationality != 'Pakistan')  # Pakistani players unavailable at IPL auction
# submitted ranking = the model's own top 10; the variety-constrained list is the RR auction board
bat_board = select(bat, bat_rules, bat_caps, gate)
bowl_board = select(bowl, bowl_rules, bowl_caps, gate)
pure_bat = bat.sort_values('s_prr_raw', ascending=False).index[:10].tolist()
pure_bowl = bowl.sort_values('s_prr_raw', ascending=False).index[:10].tolist()
bat_top, bowl_top = pure_bat, pure_bowl

# ---------- signature moments ----------
def fmt_bat(e):
    res = 'won' if e.bat_win == 1 else 'lost'
    return {'date': str(e.match_date), 'comp': e.comp_name, 'opp': e.bowl_team, 'ko': bool(e.ko),
            'situation': e.situation, 'did': f"{int(e.runs)} off {int(e.balls)} under pressure ({int(e.inn_runs)} off {int(e.inn_balls)} in the innings){' — out' if e.out else ' — not out'}",
            'wp': f"{e.wp0*100:.0f}% → {e.wp1*100:.0f}%", 'wpa': round(e.wpa * 100, 1), 'result': e.result, 'team_result': res}

def fmt_bowl(e):
    return {'date': str(e.match_date), 'comp': e.comp_name, 'opp': e.bat_team, 'ko': bool(e.ko),
            'situation': e.situation, 'did': f"Over {int(e.overid)}: {int(e.conceded)} runs, {int(e.wkts)} wkt{'s' if e.wkts != 1 else ''}",
            'wp': f"{e.wp0*100:.0f}% → {e.wp1*100:.0f}% (bowling side)", 'wpa': round(e.wpa * 100, 1), 'result': e.result,
            'team_result': 'won' if e.bat_win == 0 else 'lost'}

def moments(ep, pid, p, fmt):
    e = ep[ep[pid] == p].copy()
    e['rank_key'] = e.wpa * np.where(e.year >= 2024, 1.0, 0.8) * np.where(e.ko, 1.2, 1.0)
    best = e.sort_values('rank_key', ascending=False).head(3)
    worst = e.sort_values('wpa').head(1)
    return [fmt(r) for r in best.itertuples()], [fmt(r) for r in worst.itertuples()], \
           {'n': int(len(e)), 'won': int(e.win.sum()), 'ko': int(e.ko.sum()), 'close': int(e.margin_close.sum()),
            'ipl': int(e.comp_name.str.startswith('IPL').sum())}

def num(v, d=1):
    return None if pd.isna(v) else round(float(v), d)

def card(R, p, kind, rank, top_ids):
    r = R.loc[p]
    ep, pid, fmt = (bat_ep, 'striker_id', fmt_bat) if kind == 'bat' else (bowl_ep, 'bowler_id', fmt_bowl)
    best, worst, ms = moments(ep, pid, p, fmt)
    d = {'id': int(p), 'name': r['name'], 'rank': rank, 'prr': num(r.s_PRR), 'raw_rank': int(r.s_rank),
         'rank_band': [int(r.s_rank_lo), int(r.s_rank_hi)], 'p_top10': num(r.s_p_top10 * 100, 0), 'p_top25': num(r.s_p_top25 * 100, 0),
         'role': r.role, 'nationality': r.nationality, 'overseas': bool(r.overseas), 'ipl_team': r.ipl_team,
         'ipl_seasons': int(r.ipl_seasons), 'in_rr': r['name'] in RR_SQUAD, 'moments': best, 'blemish': worst, 'moment_stats': ms,
         'components': {k: num(r['s_' + k], 2) for k in (['b_runs', 'b_out', 'b_dot'] if kind == 'bat' else ['w_runs', 'w_wkt', 'w_dot']) + ['moment', 'delta']}}
    dna = (ext['bat_dna'] if kind == 'bat' else ext['bowl_dna']).get(str(p))
    d['dna'] = dna
    if kind == 'bat':
        d['hand'] = r.hand
        d['pressure'] = {'balls': int(r.pb_hb), 'sr': num(r.pb_hp_sr), 'xsr': num(r.pb_hp_xsr), 'avg': num(r.pb_hp_avg),
                         'dot': num(r.pb_hp_dot), 'xdot': num(r.pb_hp_xdot)}
        d['splits'] = {'vs_spin': [num(r.vspin_sr), num(r.vspin_xsr), int(r.vspin_n) if not pd.isna(r.vspin_n) else 0],
                       'death': [num(r.death_sr), num(r.death_xsr), int(r.death_n) if not pd.isna(r.death_n) else 0],
                       'ipl': [num(r.ipl_sr), num(r.ipl_xsr), int(r.ipl_n) if not pd.isna(r.ipl_n) else 0]}
        d['decision'] = num(r.decision * 1000, 2); d['execution'] = num(r.execution * 1000, 2)
        d['squeeze'] = {'n': int(r.sq_n) if not pd.isna(r.sq_n) else 0, 'out': num(r.sq_out * 100), 'score': num(r.sq_score * 100)}
    else:
        d['kind'] = r.kind; d['phase_role'] = r.phase_role; d['bowling_type'] = r.bowling_type
        d['pressure'] = {'balls': int(r.pb_hb), 'econ': num(r.pb_hp_econ, 2), 'xecon': num(r.pb_hp_xecon, 2),
                         'bpw': num(r.pb_hp_bpw), 'dot': num(r.pb_hp_dot), 'xdot': num(r.pb_hp_xdot)}
        d['splits'] = {'death': [num(r.death_econ, 2), num(r.death_xecon, 2), int(r.death_n) if not pd.isna(r.death_n) else 0],
                       'middle': [num(r.mid_econ, 2), num(r.mid_xecon, 2), int(r.mid_n) if not pd.isna(r.mid_n) else 0],
                       'ipl': [num(r.ipl_econ, 2), num(r.ipl_xecon, 2), int(r.ipl_n) if not pd.isna(r.ipl_n) else 0]}
        d['decision'] = num(r.decision * 1000, 2); d['execution'] = num(r.execution * 1000, 2)
        d['bounce'] = {'n': int(r.bb_n) if not pd.isna(r.bb_n) else 0, 'dot': num(r.bb_dot * 100), 'bdry': num(r.bb_bdry * 100)}
    return d

def table(R, kind, top_ids, board_ids=()):
    keep = []
    for p, r in R.sort_values('s_prr_raw', ascending=False).iterrows():
        row = {'id': int(p), 'name': r['name'], 'prr': num(r.s_PRR), 'rank': int(r.s_rank), 'lo': int(r.s_rank_lo), 'hi': int(r.s_rank_hi),
               'p10': num(r.s_p_top10 * 100, 0), 'role': r.role, 'nat': r.nationality, 'ipl_team': r.ipl_team,
               'eps': int(r.episodes), 'selected': p in top_ids, 'board': p in board_ids, 'balls': int(r.pb_hb)}
        if kind == 'bat':
            row.update({'hand': r.hand, 'sr': num(r.pb_hp_sr), 'xsr': num(r.pb_hp_xsr), 'dot': num(r.pb_hp_dot), 'xdot': num(r.pb_hp_xdot), 'avg': num(r.pb_hp_avg)})
        else:
            row.update({'econ': num(r.pb_hp_econ, 2), 'xecon': num(r.pb_hp_xecon, 2), 'dot': num(r.pb_hp_dot), 'xdot': num(r.pb_hp_xdot), 'bpw': num(r.pb_hp_bpw)})
        keep.append(row)
    return keep

def why_excluded(R, top, pure, rules, caps):
    out = []
    for p in pure:
        if p in top:
            continue
        r = R.loc[p]
        above = [q for q in top if R.loc[q].s_prr_raw > r.s_prr_raw]
        reason = []
        if r.nationality == 'Pakistan':
            reason.append('not available at IPL auction (Pakistan national)')
        if r.s_p_top25 < .20:
            reason.append('rank too unstable (<20% chance of top 25)')
        for k, (f, cap) in caps.items():
            if f(r) and sum(f(R.loc[q]) for q in above) >= cap:
                reason.append(f'{k} cap ({cap}) already filled by higher-rated players')
        out.append({'name': r['name'], 'prr': num(r.s_PRR), 'role': r.role, 'nat': r.nationality,
                    'reason': '; '.join(reason) or 'slot needed to meet a role minimum'})
    return out

data = {
    'validation': val,
    'thr': ext['thr'],
    'bat_top': [card(bat, p, 'bat', i + 1, bat_top) for i, p in enumerate(bat_top)],
    'bowl_top': [card(bowl, p, 'bowl', i + 1, bowl_top) for i, p in enumerate(bowl_top)],
    'bat_board': [card(bat, p, 'bat', i + 1, bat_board) for i, p in enumerate(bat_board)],
    'bowl_board': [card(bowl, p, 'bowl', i + 1, bowl_board) for i, p in enumerate(bowl_board)],
    'bat_table': table(bat, 'bat', bat_top, bat_board), 'bowl_table': table(bowl, 'bowl', bowl_top, bowl_board),
    'bat_excluded': why_excluded(bat, bat_board, pure_bat, bat_rules, bat_caps),
    'bowl_excluded': why_excluded(bowl, bowl_board, pure_bowl, bowl_rules, bowl_caps),
    'bat_added': [{'name': bat.loc[p]['name'], 'rank': int(bat.loc[p].s_rank), 'role': bat.loc[p].role, 'prr': num(bat.loc[p].s_PRR)} for p in bat_board if p not in pure_bat],
    'bowl_added': [{'name': bowl.loc[p]['name'], 'rank': int(bowl.loc[p].s_rank), 'role': bowl.loc[p].role, 'prr': num(bowl.loc[p].s_PRR)} for p in bowl_board if p not in pure_bowl],
    'rr': rr,
}
json.dump(data, open(f'{OUT}/dashboard_data.json', 'w'), default=lambda o: o.item() if hasattr(o, 'item') else str(o))
for k in ['bat_top', 'bowl_top']:
    print(k)
    for c in data[k]:
        print(f"  {c['rank']:2d}. {c['name']:24s} PRR {c['prr']:5.1f} raw#{c['raw_rank']:3d} band {c['rank_band']} {c['role']:28s} {c['nationality']:12s} IPL:{c['ipl_team']}")
print('excluded', data['bat_excluded'], data['bowl_excluded'])


# ---------- extended export for dashboard: cards for top-30 + notable names, WP worms ----------
NOTABLE_BAT = ['Virat Kohli', 'Shubman Gill', 'Phil Salt', 'Jos Buttler', 'Abhishek Sharma', 'Yashasvi Jaiswal']
NOTABLE_BOWL = ['Jasprit Bumrah', 'Sufiyan Muqeem', 'Arshdeep Singh', 'Kagiso Rabada', 'Eshan Malinga']
def pool(R, notable):
    top30 = R.sort_values('s_prr_raw', ascending=False).index[:30].tolist()
    return list(dict.fromkeys(top30 + R[R.name.isin(notable)].index.tolist()))
bat_cards = {str(int(p)): card(bat, p, 'bat', int(bat.loc[p].s_rank), bat_top) for p in pool(bat, NOTABLE_BAT)}
bowl_cards = {str(int(p)): card(bowl, p, 'bowl', int(bowl.loc[p].s_rank), bowl_top) for p in pool(bowl, NOTABLE_BOWL)}

teams_by_id = {}
for e in [bat_ep, bowl_ep]:
    pass
b['p1'] = np.where(b.innings == 1, b.wp_after, 1 - b.wp_after)
worms = {}
def worm(mid):
    k = str(mid)
    if k in worms:
        return
    g = b[b.match_id == mid].sort_values(['innings', 'innings_ball_num'])
    worms[k] = {'result': str(g.result.iloc[0]),
                'x': [round(float(v), 3) for v in (g.innings - 1) * 20 + (g.lb + 1) / 6],
                'p1': [round(float(v), 3) for v in g.p1],
                'inn': g.innings.astype(int).tolist(),
                'striker': g.striker_id.astype(int).tolist(), 'bowler': g.bowler_id.astype(int).tolist(),
                'label': [f"Inn {i} · {int(l // 6)}.{int(l % 6) + 1} · {bn} to {sn}: {int(t)}{' WICKET' if w else ''}"
                          for i, l, bn, sn, t, w in zip(g.innings, g.lb, g.bowler_name, g.striker_name, g.tot, g.is_wicket)]}

def attach(cards, ep, pid):
    for k, c in cards.items():
        e = ep[ep[pid] == int(k)]
        for mo in c['moments'] + c['blemish']:
            hit = e[(e.match_date.astype(str) == mo['date']) & (e.situation == mo['situation'])]
            if len(hit):
                mid = int(hit.match_id.iloc[0]); mo['match_id'] = mid; worm(mid)
attach(bat_cards, bat_ep, 'striker_id'); attach(bowl_cards, bowl_ep, 'bowler_id')
for lst, cards in [(data['bat_top'], bat_cards), (data['bowl_top'], bowl_cards), (data['bat_board'], bat_cards), (data['bowl_board'], bowl_cards)]:
    for c in lst:
        src = cards[str(c['id'])]
        for a, bb in zip(c['moments'] + c['blemish'], src['moments'] + src['blemish']):
            a['match_id'] = bb.get('match_id')
data['bat_cards'] = bat_cards; data['bowl_cards'] = bowl_cards
env = pd.read_csv(f'{OUT}/match_env.csv')
mm = b.groupby('match_id').agg(ipl=('comp_name', lambda s: s.iloc[0].startswith('IPL')), yr=('year', 'first'))
env = env.join(mm, on='match_id')
data['env'] = env.groupby(['ipl', 'yr']).agg(actual=('rpo', 'mean'), env=('env_rpo', 'mean')).round(2).reset_index().to_dict('records')
json.dump(data, open(f'{OUT}/dashboard_data.json', 'w'), default=lambda o: o.item() if hasattr(o, 'item') else str(o))
json.dump(worms, open(f'{OUT}/worms.json', 'w'))
print('cards', len(bat_cards), len(bowl_cards), 'worms', len(worms))
