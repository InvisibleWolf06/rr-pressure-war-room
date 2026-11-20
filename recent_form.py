"""Recent SMAT form (2025/26 and 2026/27) from public records, read from datasets/smat_recent_form.csv
and datasets/sources.csv. Edit the CSVs to add players or update numbers, then re-run smat_link.py.
Columns: player, state, kind (bat/bowl), season, performance, source_id, cricsheet_name (blank if not in the
SMAT ball-by-ball data), veteran (1/0)."""
import os, csv
_D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datasets')
with open(os.path.join(_D, 'sources.csv'), newline='', encoding='utf-8') as f:
    SRC = {r['source_id']: (r['title'], r['url']) for r in csv.DictReader(f)}
with open(os.path.join(_D, 'smat_recent_form.csv'), newline='', encoding='utf-8') as f:
    ROWS = [(r['player'], r['state'], r['kind'], r['season'], r['performance'], r['source_id'],
             r['cricsheet_name'].strip() or None, r['veteran'].strip() in ('1', 'true', 'True', 'yes')) for r in csv.DictReader(f)]
