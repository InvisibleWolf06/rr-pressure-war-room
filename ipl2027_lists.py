"""Official IPL 2027 retention lists (17 Nov 2026), read from datasets/ipl2027_retention.csv.
Edit the CSV (one row per player; alternate spellings = extra rows) and re-run the pipeline."""
import os, csv
_P = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datasets', 'ipl2027_retention.csv')
RET, REL = {}, {}
with open(_P, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        (RET if r['decision'].strip().lower() == 'retained' else REL)[r['player'].strip()] = r['ipl_team'].strip()
RETAINED = {t: '|'.join(n for n, tt in RET.items() if tt == t) for t in set(RET.values())}
RELEASED = {t: '|'.join(n for n, tt in REL.items() if tt == t) for t in set(REL.values())}
