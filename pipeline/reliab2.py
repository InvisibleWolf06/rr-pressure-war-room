import sys, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
OUT=sys.argv[1]
b=pd.read_parquet(f'{OUT}/balls.parquet')
b['own_out']=(b.is_wicket&(b.dismissed_player_id==b.striker_id)).astype(int)
b['bwk']=(b.is_wicket&b.dismissal_type.ne('RunOut')).astype(int)
lg=b[b.legal].copy()
lg['need_rr']=np.where(lg.innings==2,(lg.target-lg.cum)/np.maximum(lg.balls_left,1)*6/lg.env_rpo,0)
lg['spin']=(lg.pace_or_spin=='Spin').astype(int)
F=['innings','lb','wl','env_rpo','need_rr','spin']
lg['bdry']=(lg.runs>=4).astype(int); lg['dot']=(lg.runs==0).astype(int)
for y,M in [('runs',HistGradientBoostingRegressor),('own_out',HistGradientBoostingClassifier),('bdry',HistGradientBoostingClassifier),('dot',HistGradientBoostingClassifier),('bwk',HistGradientBoostingClassifier)]:
    mdl=M(max_iter=200,max_depth=4,min_samples_leaf=300,early_stopping=False,random_state=7).fit(lg[F],lg[y])
    lg['x_'+y]=mdl.predict(lg[F]) if y=='runs' else mdl.predict_proba(lg[F])[:,1]
    lg['d_'+y]=lg[y]-lg['x_'+y]
lg['tot_d']=lg.tot-lg.groupby(['innings','lb']).tot.transform('mean')  # bowler conceded vs avg
lg['half']=lg.match_id.rank(method='dense').astype(int)%2
lg[['match_id','innings','innings_ball_num','x_runs','x_own_out','x_bdry','x_dot','x_bwk']].to_parquet(f'{OUT}/expect.parquet')
def rel(df,pid,cols,minn):
    g=df.groupby([pid,'half'])[cols].mean().unstack(); n=df.groupby([pid,'half']).size().unstack()
    ok=(n[0]>=minn)&(n[1]>=minn); g=g[ok]
    return {c:round(np.corrcoef(g[(c,0)],g[(c,1)])[0,1],3) for c in cols}, int(ok.sum())
cb=['d_runs','d_own_out','d_bdry','d_dot']; cw=['d_runs','d_bwk','d_bdry','d_dot']
print('BAT all balls',rel(lg,'striker_id',cb,150)); print('BAT pressure',rel(lg[lg.hp],'striker_id',cb,40))
print('BOWL all balls (sign: batter view)',rel(lg,'bowler_id',cw,150)); print('BOWL pressure',rel(lg[lg.hp],'bowler_id',cw,40))
# does overall skill predict pressure performance (other half)?
for pid,c in [('striker_id','d_runs'),('striker_id','d_dot'),('bowler_id','d_runs'),('bowler_id','d_dot'),('bowler_id','d_bwk')]:
    a=lg[(lg.half==0)].groupby(pid)[c].agg(['mean','size']); h=lg[(lg.half==1)&lg.hp].groupby(pid)[c].agg(['mean','size'])
    ha=lg[(lg.half==0)&lg.hp].groupby(pid)[c].mean()
    J=a.join(h,lsuffix='_all',rsuffix='_hp',how='inner').join(ha.rename('hp_a')); J=J[(J.size_all>=150)&(J.size_hp>=40)]
    print(pid,c,'overall(A)->pressure(B) r',round(np.corrcoef(J.mean_all,J.mean_hp)[0,1],3),' pressure(A)->pressure(B) r',round(np.corrcoef(J.hp_a.fillna(0),J.mean_hp)[0,1],3),len(J))
