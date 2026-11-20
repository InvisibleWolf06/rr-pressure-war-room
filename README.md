# RR Pressure War Room — SupeRR Selector S2, Round 1

Streamlit dashboard + reproducible pipeline for the Pressure Reliability Rating (PRR).

## Deploy (Streamlit Community Cloud)
1. Push this folder to a GitHub repo (keep `app.py`, `requirements.txt`, `data/` at the root).
2. share.streamlit.io → New app → pick the repo → main file `app.py` → Deploy.
3. Paste the app URL into the Unstop submission.

Run locally: `pip install -r requirements.txt && streamlit run app.py`

## Rebuild everything from the data pack
```
D="path/to/Data Pack"; OUT=out; mkdir -p $OUT
python pipeline/engine.py "$D" $OUT      # environment, win probability, leverage, pressure balls
python pipeline/reliab2.py $OUT          # expected outcomes per ball + reliability tests
python pipeline/moments.py "$D" $OUT     # pressure moments, roles, shot/delivery DNA
python pipeline/ratings2.py $OUT         # PRR, bootstrap bands, validation
python pipeline/rr_gaps.py "$D" $OUT     # RR pressure gaps
python pipeline/select.py $OUT           # ranking (model top 10), RR auction board, dashboard data
python pipeline/robust.py $OUT           # sensitivity, baseline benchmark, IPL vs T20I transfer
python pipeline/report.py $OUT report.pdf
cp $OUT/dashboard_data.json $OUT/worms.json data/
```
Needs: pandas, numpy, scikit-learn, pyarrow, matplotlib, reportlab, pillow.

## Stadium version
- `war_room_stadium.html` is the animated stadium dashboard as one self-contained page (open it in any browser; needs internet for Plotly).
- `app_stadium.py` serves that page inside Streamlit. Use it as the main file on Streamlit Cloud for the stadium look; `app.py` is the plain version.
- `pipeline/web/` holds the page template and build script.


## Auction availability and match simulator (added Nov 2026)
```
python -I pipeline/availability.py "<data_dir>" out   # who RR can buy, from the official 17 Nov 2026 retention lists (ipl2027_lists.py)
python -I pipeline/select.py out                     # rebuilds the auction board
python -I pipeline/lab_export.py "<data_dir>" out       # player lab, hidden gems, wider pool, backups, retain/release
python -I pipeline/sim_export.py "<data_dir>" out --val
node pipeline/simval.js out/sim_val.json out/sim_val_wp.csv out/sim_validation.json   # (ALPHA=1 SD=0.2 BS=0.93)
python -I pipeline/sim_export.py "<data_dir>" out     # writes out/sim.json with validation
node pipeline/sim_examples.js out/sim.json out/dashboard_data.json out/sim_examples.json
python pipeline/web/build_dash.py                     # stadium page incl. Match Simulator tab
```
Note: simval.js reads ALPHA/SD/BS from the environment; use ALPHA=1 SD=0.2 BS=0.93 to reproduce the shipped numbers.

## Domestic scout (Syed Mushtaq Ali Trophy, Cricsheet JSON)
```
python -I pipeline/smat_parse.py <sma_json_dir> out    # Cricsheet SMAT JSON -> out/smat_balls.parquet
python -I pipeline/smat_model.py out                   # environment, win probability, pressure balls, domestic pressure rating (DPR)
python -I pipeline/smat_link.py "<data_dir>" out       # link to IPL 2027 retention lists, veterans, backups, recent form (recent_form.py) -> out/smat.json
python pipeline/web/build_dash.py                      # rebuild the stadium page (Domestic Scout tab)
```

## Editable datasets and result tables (added 20 Nov 2026)
Hand-compiled inputs (edit these on GitHub; the code reads them, nothing is hard-coded):
- `pipeline/datasets/ipl2027_retention.csv`: every player retained or released on 17 Nov 2026, by team (player, ipl_team, decision, source). Add a row for an alternate spelling of a name.
- `pipeline/datasets/smat_recent_form.csv`: SMAT 2025/26 and 2026/27 standouts from public records (player, state, kind, season, performance, source_id, cricsheet_name, veteran). `cricsheet_name` links the player to his pressure rating; leave blank if he is not in the ball-by-ball data.
- `pipeline/datasets/sources.csv`: the source for each `source_id`.

After editing, re-run:
```
python -I pipeline/availability.py "<data_dir>" out
python -I pipeline/select.py out
python -I pipeline/lab_export.py "<data_dir>" out
python -I pipeline/smat_link.py "<data_dir>" out
python -I pipeline/export_csv.py out results
python pipeline/web/build_dash.py
```

Result tables in `results/` (computed by the model, regenerate with export_csv.py):
- `auction_board_bat.csv`, `auction_board_bowl.csv`: RR's buyable top 10s with PRR and availability
- `auction_availability.csv`: status of every rated player for the 2027 auction
- `rr_retain_release.csv`: model call vs what RR actually did on 17 Nov
- `smat_ratings_bat.csv`, `smat_ratings_bowl.csv`: domestic pressure rating (DPR), status, veteran flag, recent form
- `domestic_backups.csv`: one next-generation domestic backup per board pick
- `smat_recent_form_checked.csv`: recent-form list with IPL 2027 status and DPR
