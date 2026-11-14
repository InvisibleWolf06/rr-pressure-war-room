import sys, json, numpy as np, pandas as pd
D, OUT = sys.argv[1], sys.argv[2]
b = pd.read_parquet(f'{OUT}/balls.parquet')
mp = pd.read_csv(f'{D}/competition_team_player_mapping.csv')
RR = 'Rajasthan Royals'
sq = mp[(mp.comp_name == 'IPL 2026') & (mp.team_name == RR)].player_name.tolist()
print('RR 2026 squad in data:', len(sq), sq)
ipl = b[b.comp_name.str.startswith('IPL') & b.year.isin([2025, 2026])].copy()
ipl['bat_team'] = np.where(ipl.batting_team_id == ipl.home_team_id, ipl.home_team, ipl.away_team)
ipl['bowl_team'] = np.where(ipl.batting_team_id == ipl.home_team_id, ipl.away_team, ipl.home_team)
ipl['role_slot'] = pd.cut(ipl.batting_order, [0, 2, 4, 7, 11], labels=['Openers (1-2)', 'Top order (3-4)', 'Middle/finish (5-7)', 'Tail (8-11)'])
rows = []
for team, g in ipl.groupby('bat_team'):
    h = g[g.hp]
    rows.append({'team': team, 'side': 'bat', 'hp_wpa_per_100': h.wpa_ball.sum() / len(h) * 100})
for team, g in ipl.groupby('bowl_team'):
    h = g[g.hp]
    rows.append({'team': team, 'side': 'bowl', 'hp_wpa_per_100': -h.wpa_ball.sum() / len(h) * 100})
T = pd.DataFrame(rows).pivot(index='team', columns='side', values='hp_wpa_per_100').round(2)
print(T.sort_values('bat'))
r = ipl[ipl.hp]
# RR batting by slot and phase; RR bowling by phase & bowler type, vs league average
def tab(df, team_col, by, sign=1):
    a = df.groupby(by, observed=True).wpa_ball.mean() * 100 * sign
    t = df[df[team_col] == RR].groupby(by, observed=True).agg(v=('wpa_ball', 'mean'), n=('wpa_ball', 'size'))
    t['v'] = t.v * 100 * sign; t['league'] = a; t['gap'] = t.v - t.league
    return t.round(2)
print('\nRR BAT pressure WPA/100 balls by slot'); print(tab(r, 'bat_team', 'role_slot'))
print('\nRR BAT by phase'); print(tab(r, 'bat_team', 'phase'))
r['btype'] = np.where(r.pace_or_spin == 'Spin', 'Spin', 'Pace')
print('\nRR BOWL by phase x type'); print(tab(r, 'bowl_team', ['phase', 'btype'], -1))
print('\nRR BAT vs pace/spin'); print(tab(r, 'bat_team', 'btype'))
# close losses
mm = ipl.groupby('match_id').agg(home=('home_team', 'first'), away=('away_team', 'first'), res=('result', 'first'), close=('margin_close', 'first'), yr=('year', 'first'))
rrm = mm[(mm.home == RR) | (mm.away == RR)]
rrm['rr_won'] = rrm.res.str.startswith(RR)
print('\nRR matches 2025-26', len(rrm), 'close', rrm.close.sum(), 'close won', (rrm.close & rrm.rr_won).sum())
print(rrm[rrm.close][['yr', 'res']].to_string())
def rec(t):
    t = t.reset_index(); t.columns = [' '.join(map(str, c)).strip() if isinstance(c, tuple) else str(c) for c in t.columns]
    return t.astype({c: str for c in t.columns if t[c].dtype.name == 'category'}).to_dict('records')
json.dump({'squad': sq, 'team_table': T.reset_index().to_dict('records'),
           'bat_slot': rec(tab(r, 'bat_team', 'role_slot')), 'bat_phase': rec(tab(r, 'bat_team', 'phase')),
           'bowl_phase_type': rec(tab(r, 'bowl_team', ['phase', 'btype'], -1)), 'bat_type': rec(tab(r, 'bat_team', 'btype')),
           'close': {'n': int(rrm.close.sum()), 'won': int((rrm.close & rrm.rr_won).sum()), 'matches': int(len(rrm))}},
          open(f'{OUT}/rr.json', 'w'))
