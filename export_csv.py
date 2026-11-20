"""Export the analysis results as plain CSV tables (results/ folder) for GitHub and spreadsheets.
Usage: python -I export_csv.py <out_dir> <results_dir>"""
import sys, os, json, pandas as pd
OUT, RES = sys.argv[1], sys.argv[2]; os.makedirs(RES, exist_ok=True)
d = json.load(open(f'{OUT}/dashboard_data.json')); S = json.load(open(f'{OUT}/smat.json')); sc = json.load(open(f'{OUT}/scout.json'))
for k in ('bat', 'bowl'):
    pd.DataFrame([{'rank': c.get('rank'), 'name': c['name'], 'role': c.get('role'), 'nationality': c.get('nat') or c.get('nationality'), 'PRR': c.get('prr'),
                   'availability': c.get('avail'), 'note': c.get('avail_note')} for c in d[f'{k}_board']]).to_csv(f'{RES}/auction_board_{k}.csv', index=False)
    cols = ['rank', 'name', 'full', 'team', 'dpr', 'np', 'imp_p', 'conv_p', 'big', 'first', 'last', 'veteran', 'status', 'ipl_team', 'recent', 'role'] + \
           (['runs', 'balls', 'sr', 'avg', 'hp_sr', 'hp_xsr'] if k == 'bat' else ['wk', 'econ', 'bpw', 'hp_econ', 'hp_xecon'])
    pd.DataFrame(S[k])[cols].rename(columns={'dpr': 'DPR', 'np': 'pressure_balls', 'imp_p': 'impact_pct', 'conv_p': 'scorecard_pct', 'big': 'turning_balls',
        'first': 'first_smat_season', 'last': 'last_smat_season', 'full': 'linked_name', 'recent': 'recent_form'}).to_csv(f'{RES}/smat_ratings_{k}.csv', index=False)
rows = []
for k in ('bat', 'bowl'):
    for v in S['backups'][k].values():
        a = v['alt']
        rows.append({'kind': k, 'board_pick': v['for'], 'pick_role': v.get('pick_role'), 'backup': v['name'], 'state': v['team'], 'role': v['role'], 'style': v.get('style'),
                     'scout_score': v['dss'], 'overall_skill': v['S'], 'pressure': v['P'], 'role_fit': v['R'], 'form_2025_27': v['F'], 'plays_regularly': v['D'],
                     'confidence': v['confidence'], 'ipl_status': v['status'], 'smat_seasons': f"{v['first']}-{v['last']}" if v['first'] else 'not in ball-by-ball data',
                     'why': v['why'], 'flags': '; '.join(v['notes']), 'alternate': a['name'], 'alternate_state': a['team'], 'alternate_score': a['dss'], 'alternate_confidence': a['confidence']})
pd.DataFrame(rows).to_csv(f'{RES}/domestic_backups.csv', index=False)
for k in ('bat', 'bowl'):
    pd.DataFrame([{'rank': i + 1, 'player': x['name'], 'state': x['team'], 'role': x['role'], 'style': x.get('style'), 'scout_score': x['dss'], 'overall_skill': x['S'],
                   'pressure': x['P'], 'role_fit': x['R'], 'form_2025_27': x['F'], 'plays_regularly': x['D'], 'confidence': x['confidence'], 'ipl_status': x['status'],
                   'why': x['why'], 'flags': '; '.join(x['notes'])} for i, x in enumerate(S['scout']['targets'][k])]).to_csv(f'{RES}/domestic_targets_{k}.csv', index=False)
json.dump(S['scout']['method'], open(f'{RES}/domestic_scout_method.json', 'w'), indent=1)
pd.DataFrame([{**{x: r[x] for x in ('name', 'state', 'kind', 'season', 'line', 'status', 'ipl_team', 'veteran', 'dpr', 'rank', 'pressure', 'last')},
               'source': S['recent_src'][r['src']][1]} for r in S['recent']]).rename(columns={'line': 'performance', 'dpr': 'DPR', 'rank': 'DPR_rank', 'last': 'last_in_smat_data',
               'status': 'ipl2027_status'}).to_csv(f'{RES}/smat_recent_form_checked.csv', index=False)
pd.DataFrame([{x: r.get(x) for x in ('name', 'role', 'salary', 'bat_rank', 'bowl_rank', 'rr_wpa', 'demand', 'rec', 'actual', 'agree', 'why')} for r in sc['retain']]
             ).rename(columns={'salary': 'salary_cr_2026', 'rr_wpa': 'wins_added_x100', 'rec': 'model_call', 'actual': 'what_rr_did', 'agree': 'model_agrees'}).to_csv(f'{RES}/rr_retain_release.csv', index=False)
pd.read_csv(f'{OUT}/availability.csv')[['name', 'status', 'note']].to_csv(f'{RES}/auction_availability.csv', index=False)
print(sorted(os.listdir(RES)))
