"""Stage 3b: auction availability for the IPL 2027 mini-auction (Goa, 16 Dec 2026).
Writes out/availability.csv (player_id, name, status, note). Statuses follow the official
IPL 2027 retention lists (17 Nov 2026).
Usage: python -I availability.py <data_dir> <out_dir>
Status codes
  rr         already in the RR 2026 squad (not a buy target)
  retired    retired from the IPL / all cricket
  ineligible not eligible for the IPL auction (Pakistan nationals)
  contracted retained by another franchise for 2027
  available  released on 17 Nov 2026, or no IPL 2026 contract -> can enter the auction pool
"""
import sys, pandas as pd
DATA, OUT = sys.argv[1], sys.argv[2]
RETIRED = {'Ravichandran Ashwin': 'retired from IPL (2025)', 'Andre Russell': 'retired from IPL (Nov 2025)',
           'Mohit Sharma': 'retired from all cricket (Dec 2025)', 'Vijay Shankar': 'retired (May 2026)',
           'Karn Sharma': 'retired from all cricket (Aug 2026)', 'Faf du Plessis': 'opted out of IPL 2026'}
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ipl2027_lists import RETAINED, RET, RELEASED, REL
BANNED = {'Harry Brook': 'serving a two-season IPL ban; next eligible for the 2028 mega auction'}
OVERRIDES = {}   # e.g. {'Cameron Green': ('available', 'released 17 Nov')} once the official lists are out

m = pd.read_csv(f'{DATA}/competition_team_player_mapping.csv')
ipl26 = m[m.comp_name.str.contains('Indian Premier League|IPL', regex=True) & m.comp_name.str.contains('2026')]
if ipl26.empty:
    c = pd.read_csv(f'{DATA}/competitions.csv'); ids = c[(c.season == 2026) & c.comp_name.str.contains('IPL|Premier')].comp_id
    ipl26 = m[m.comp_id.isin(ids)]
squad = ipl26.drop_duplicates('player_id').set_index('player_id').team_name
rows, UNLISTED = [], []
for k in ['bat', 'bowl']:
    R = pd.read_csv(f'{OUT}/{k}_final.csv', index_col=0)
    for p, r in R.iterrows():
        n, team = r['name'], squad.get(p)
        if n in OVERRIDES: s, note = OVERRIDES[n]
        elif n in RETIRED: s, note = 'retired', RETIRED[n]
        elif n in BANNED: s, note = 'ineligible', BANNED[n]
        elif r.nationality == 'Pakistan': s, note = 'ineligible', 'Pakistan nationals are not in the IPL auction pool'
        elif n == 'Mahendra Singh Dhoni': s, note = 'retired', 'retired from IPL (Nov 2026)'
        elif RET.get(n) == 'Rajasthan Royals': s, note = 'rr', 'retained by RR for 2027'
        elif n in RET: s, note = 'contracted', f'{RET[n]} squad; retained 17 Nov 2026'
        elif n in REL: s, note = 'available', f'released by {REL[n]} on 17 Nov 2026'
        elif team is not None:
            s, note = 'contracted', f'{team} squad; not on any released list'; UNLISTED.append((n, team))
        else: s, note = 'available', 'no IPL 2026 contract'
        rows.append((p, n, s, note))
A = pd.DataFrame(rows, columns=['player_id', 'name', 'status', 'note']).drop_duplicates('player_id')
A.to_csv(f'{OUT}/availability.csv', index=False)
print(A.status.value_counts().to_string())
print('unlisted 2026-squad players:', sorted(set(UNLISTED)))
