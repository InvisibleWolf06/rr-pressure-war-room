"""Stage 3b: auction availability for the IPL 2027 mini-auction (Goa, 16 Dec 2026).
Writes out/availability.csv (player_id, name, status, note). Edit OVERRIDES after the
retention lists come out on 17 Nov 2026 and re-run select.py.
Usage: python -I availability.py <data_dir> <out_dir>
Status codes
  rr         already in the RR 2026 squad (not a buy target)
  retired    retired from the IPL / all cricket
  ineligible not eligible for the IPL auction (Pakistan nationals)
  contracted in another franchise's 2026 squad; assumed retained until the lists are out
  rumoured   in another squad but publicly reported as a likely release
  available  no IPL 2026 contract -> can enter the auction pool
"""
import sys, pandas as pd
DATA, OUT = sys.argv[1], sys.argv[2]
RETIRED = {'Ravichandran Ashwin': 'retired from IPL (2025)', 'Andre Russell': 'retired from IPL (Nov 2025)',
           'Mohit Sharma': 'retired from all cricket (Dec 2025)', 'Vijay Shankar': 'retired (May 2026)',
           'Karn Sharma': 'retired from all cricket (Aug 2026)', 'Faf du Plessis': 'opted out of IPL 2026'}
RUMOURED = {'Cameron Green': 'KKR', 'Matheesha Pathirana': 'KKR', 'Ajinkya Rahane': 'KKR', 'Liam Livingstone': 'SRH',
            'Trent Boult': 'MI', 'Deepak Chahar': 'MI', 'Sherfane Rutherford': 'MI', 'Quinton de Kock': 'MI',
            'Rahul Chahar': 'CSK', 'Deepak Hooda': 'CSK', 'Kartik Sharma': 'CSK', 'Avesh Khan': 'LSG', 'Mohsin Khan': 'LSG',
            'Mohammed Shami': 'LSG', 'Wanindu Hasaranga': 'LSG', 'Josh Inglis': 'LSG'}
BANNED = {'Harry Brook': 'serving a two-season IPL ban; next eligible for the 2028 mega auction'}
OVERRIDES = {}   # e.g. {'Cameron Green': ('available', 'released 17 Nov')} once the official lists are out

m = pd.read_csv(f'{DATA}/competition_team_player_mapping.csv')
ipl26 = m[m.comp_name.str.contains('Indian Premier League|IPL', regex=True) & m.comp_name.str.contains('2026')]
if ipl26.empty:
    c = pd.read_csv(f'{DATA}/competitions.csv'); ids = c[(c.season == 2026) & c.comp_name.str.contains('IPL|Premier')].comp_id
    ipl26 = m[m.comp_id.isin(ids)]
squad = ipl26.drop_duplicates('player_id').set_index('player_id').team_name
rows = []
for k in ['bat', 'bowl']:
    R = pd.read_csv(f'{OUT}/{k}_final.csv', index_col=0)
    for p, r in R.iterrows():
        n, team = r['name'], squad.get(p)
        if n in OVERRIDES: s, note = OVERRIDES[n]
        elif n in RETIRED: s, note = 'retired', RETIRED[n]
        elif n in BANNED: s, note = 'ineligible', BANNED[n]
        elif r.nationality == 'Pakistan': s, note = 'ineligible', 'Pakistan nationals are not in the IPL auction pool'
        elif team == 'Rajasthan Royals': s, note = 'rr', 'already in the RR squad'
        elif n in RUMOURED: s, note = 'rumoured', f'{team or RUMOURED[n]}: reported release candidate (unconfirmed)'
        elif team is not None: s, note = 'contracted', f'{team} squad; assumed retained until 17 Nov lists'
        else: s, note = 'available', 'no IPL 2026 contract'
        rows.append((p, n, s, note))
A = pd.DataFrame(rows, columns=['player_id', 'name', 'status', 'note']).drop_duplicates('player_id')
A.to_csv(f'{OUT}/availability.csv', index=False)
print(A.status.value_counts().to_string())
