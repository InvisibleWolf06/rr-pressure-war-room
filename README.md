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
