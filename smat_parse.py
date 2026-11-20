"""SMAT (Cricsheet JSON) -> out/smat_balls.parquet
Usage: python -I smat_parse.py <json_dir> <out_dir>"""
import sys, json, glob, os, pandas as pd
SRC, OUT = sys.argv[1], sys.argv[2]
rows, mrows = [], []
for f in sorted(glob.glob(os.path.join(SRC, '*.json'))):
    d = json.load(open(f)); info = d['info']; mid = int(os.path.basename(f)[:-5])
    reg = info.get('registry', {}).get('people', {})
    out = info.get('outcome', {})
    revised = 'method' in out or info.get('overs', 20) != 20
    winner = out.get('winner'); res = 'tie' if out.get('result') == 'tie' else 'nr' if out.get('result') == 'no result' else 'win' if winner else 'other'
    if out.get('eliminator'): winner = out['eliminator']; res = 'tie'
    inns = [i for i in d['innings'] if not i.get('super_over')]
    teams = info['teams']
    mrows.append({'match_id': mid, 'season': info['season'], 'date': info['dates'][0], 'venue': info.get('venue'), 'city': info.get('city'),
                  'stage': info['event'].get('stage') or info['event'].get('group') or '', 'team1': teams[0], 'team2': teams[1],
                  'winner': winner, 'result': res, 'revised': revised, 'n_inn': len(inns),
                  'by': ' '.join(f"{v} {k}" for k, v in out.get('by', {}).items())})
    for ii, inn in enumerate(inns, 1):
        bat = inn['team']; bowl = teams[1] if bat == teams[0] else teams[0]
        tgt = inn.get('target', {}).get('runs')
        legal = 0
        for ov in inn['overs']:
            for k, b in enumerate(ov['deliveries']):
                ex = b.get('extras', {}); lg = not ('wides' in ex or 'noballs' in ex)
                w = b.get('wickets', [])
                rows.append({'match_id': mid, 'innings': ii, 'bat_team': bat, 'bowl_team': bowl, 'over': ov['over'], 'legal_before': legal,
                             'batter': b['batter'], 'bowler': b['bowler'], 'non_striker': b['non_striker'],
                             'batter_id': reg.get(b['batter']), 'bowler_id': reg.get(b['bowler']), 'non_striker_id': reg.get(b['non_striker']),
                             'runs': b['runs']['batter'], 'extras': b['runs']['extras'], 'tot': b['runs']['total'], 'legal': lg,
                             'wide': 'wides' in ex, 'noball': 'noballs' in ex, 'byes': ex.get('byes', 0) + ex.get('legbyes', 0),
                             'is_wicket': bool(w), 'kind': w[0]['kind'] if w else None, 'player_out': w[0]['player_out'] if w else None,
                             'player_out_id': reg.get(w[0]['player_out']) if w else None, 'target': tgt})
                if lg: legal += 1
B = pd.DataFrame(rows); M = pd.DataFrame(mrows)
B = B.merge(M[['match_id', 'season', 'date', 'venue', 'winner', 'result', 'revised']], on='match_id')
B.to_parquet(f'{OUT}/smat_balls.parquet'); M.to_csv(f'{OUT}/smat_matches.csv', index=False)
print(B.shape, M.shape); print(M.result.value_counts().to_dict(), 'revised', int(M.revised.sum()))
print(B.groupby('season').match_id.nunique().to_dict())
