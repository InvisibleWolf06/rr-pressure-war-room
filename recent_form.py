"""Recent SMAT form (2025/26 and 2026/27) from public records, read from datasets/smat_recent_form.csv
and datasets/sources.csv. Edit the CSVs to add players or update numbers, then re-run the pipeline.
Columns: player, state, kind (bat/bowl), season, matches, runs, balls, sr, wkts, overs, econ, level (Elite/Plate), role, style (pace/spin),
performance (text), source_id, cricsheet_name (blank if not in the SMAT ball-by-ball data), veteran (1/0)."""
import os, csv
import pandas as pd
_D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datasets')
with open(os.path.join(_D, 'sources.csv'), newline='', encoding='utf-8') as f:
    SRC = {r['source_id']: (r['title'], r['url']) for r in csv.DictReader(f)}
FORM = pd.read_csv(os.path.join(_D, 'smat_recent_form.csv'), dtype={'cricsheet_name': str, 'role': str, 'style': str})
FORM['cricsheet_name'] = FORM.cricsheet_name.fillna('').str.strip()
ROWS = [(r.player, r.state, r.kind, r.season, r.performance, r.source_id, r.cricsheet_name or None, bool(r.veteran)) for r in FORM.itertuples()]
