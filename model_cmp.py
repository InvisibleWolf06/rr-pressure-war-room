import sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import HistGradientBoostingRegressor as HR, HistGradientBoostingClassifier as HC
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.pipeline import make_pipeline; from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss, mean_squared_error
from catboost import CatBoostRegressor as CR, CatBoostClassifier as CC
from lightgbm import LGBMRegressor as LR, LGBMClassifier as LC
OUT = sys.argv[1]
b = pd.read_parquet(f'{OUT}/balls.parquet')
b['own_out'] = (b.is_wicket & (b.dismissed_player_id == b.striker_id)).astype(int)
b['bwk'] = (b.is_wicket & b.dismissal_type.ne('RunOut')).astype(int)
lg = b[b.legal].copy()
lg['need_rr'] = np.where(lg.innings == 2, (lg.target - lg.cum) / np.maximum(lg.balls_left, 1) * 6 / lg.env_rpo, 0)
lg['spin'] = (lg.pace_or_spin == 'Spin').astype(int); lg['dot'] = (lg.runs == 0).astype(int)
F = ['innings', 'lb', 'wl', 'env_rpo', 'need_rr', 'spin']; CAT = ['batting_type', 'bowling_type']
for cc in CAT: lg[cc] = lg[cc].fillna('NA').astype(str)
res = {}
def cv(name, target, make, cols, clf, data=lg, cat=None):
    X, y, g = data[cols], data[target].values, data.match_id.values; oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, g):
        m = make(); 
        if cat: m.fit(X.iloc[tr], y[tr], cat_features=cat)
        else: m.fit(X.iloc[tr], y[tr])
        oof[te] = m.predict_proba(X.iloc[te])[:, 1] if clf else m.predict(X.iloc[te])
    sc = log_loss(y, np.clip(oof, 1e-6, 1 - 1e-6)) if clf else mean_squared_error(y, oof) ** .5
    res.setdefault(target, {})[name] = round(float(sc), 5); print(target, name, round(sc, 5), flush=True)
for tgt, clf in [('runs', False), ('own_out', True), ('dot', True), ('bwk', True)]:
    cv('linear', tgt, (lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=300))) if clf else (lambda: make_pipeline(StandardScaler(), Ridge())), F, clf)
    cv('sklearn_hgb (current)', tgt, (lambda: HC(max_iter=200, max_depth=4, min_samples_leaf=300)) if clf else (lambda: HR(max_iter=200, max_depth=4, min_samples_leaf=300)), F, clf)
    cv('lightgbm', tgt, (lambda: LC(n_estimators=300, learning_rate=.05, num_leaves=15, min_child_samples=300, verbose=-1)) if clf else (lambda: LR(n_estimators=300, learning_rate=.05, num_leaves=15, min_child_samples=300, verbose=-1)), F, clf)
    cv('catboost', tgt, (lambda: CC(iterations=400, learning_rate=.06, depth=5, verbose=0, thread_count=4)) if clf else (lambda: CR(iterations=400, learning_rate=.06, depth=5, verbose=0, thread_count=4)), F, clf)
    cv('catboost + bowler type & batting hand', tgt, (lambda: CC(iterations=400, learning_rate=.06, depth=5, verbose=0, thread_count=4)) if clf else (lambda: CR(iterations=400, learning_rate=.06, depth=5, verbose=0, thread_count=4)), F + CAT, clf, cat=CAT)
# remaining-runs model behind win probability
s1 = b[b.innings == 1].copy(); fin = s1.groupby('match_id').tot.sum(); s1['rem'] = s1.match_id.map(fin) - s1.cum
RF = ['balls_left', 'wl', 'env_rpo']
cv('linear', 'rem', lambda: make_pipeline(StandardScaler(), Ridge()), RF, False, s1)
cv('sklearn_hgb (current)', 'rem', lambda: HR(max_iter=400, learning_rate=.05, max_depth=4, min_samples_leaf=300, monotonic_cst=[1, 1, 1]), RF, False, s1)
cv('lightgbm', 'rem', lambda: LR(n_estimators=400, learning_rate=.05, num_leaves=15, min_child_samples=300, monotone_constraints=[1, 1, 1], verbose=-1), RF, False, s1)
cv('catboost', 'rem', lambda: CR(iterations=500, learning_rate=.05, depth=5, monotone_constraints=[1, 1, 1], verbose=0, thread_count=4), RF, False, s1)
json.dump(res, open(f'{OUT}/model_cmp.json', 'w'), indent=1)
