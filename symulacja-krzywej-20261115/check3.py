import numpy as np
from cens import load_all, BLACK
t,n,raw,out=load_all(); b=np.isin(n%12,list(BLACK))
# 1) chords: same moment, same hand roughly -> black vs white reading, chord fixed effect, top-note flag
rows=[]; i=0
while i<len(t):
    j=i
    while j+1<len(t) and t[j+1]-t[i]<.03: j+=1
    idx=np.arange(i,j+1)
    if len(idx)>=2 and (raw[idx]>=41).all() and b[idx].any() and (~b[idx]).any():
        top=idx[np.argmax(n[idx])]; m=raw[idx].mean()
        for k in idx: rows.append((raw[k]-m, b[k], k==top, n[k]<60))
    i=j+1
R=np.array(rows,float); X=np.c_[R[:,1],R[:,2],R[:,3],np.ones(len(R))]
beta=np.linalg.lstsq(X,R[:,0],rcond=None)[0]
print('akordy z czarnym i bialym (wszystkie >=41): %d nut, czarny wzgledem bialego w tym samym akordzie: %+.1f raw (gorny glos %+.1f)'%(len(R),beta[0],beta[1]))
# 2) unconditional quantile: where does white sit at the black "1" share
w=raw[~b]; q=(raw[b]==1).mean(); print('udzial czarnych "1" %.2f%% -> bialy kwantyl = %d raw'%(100*q,np.quantile(w,q)))
# 3) context of black "1": loudness of measured neighbours within 1 s, vs genuine soft whites and vs all
def ctx(sel):
    c=[]
    for k in np.where(sel)[0]:
        lo,hi=np.searchsorted(t,[t[k]-1,t[k]+1]); nb=[x for x in range(lo,hi) if x!=k and raw[x]>=41 and abs(t[x]-t[k])>.03]
        if len(nb)>=2: c.append(np.median(raw[nb]))
    return np.array(c)
cs=ctx(~b&(raw<=41)&(raw>=2)); c1w=ctx(~b&(raw==1)); cb=ctx(b&(raw==1)); ca=ctx(b&(raw>=41))
print('kontekst (mediana sasiadow): biale 2-41 %.0f, biale "1" %.0f, czarne "1" %.0f, czarne zmierzone %.0f'%tuple(np.median(x) for x in (cs,c1w,cb,ca)))
soft=np.r_[cs,c1w]; grid=np.linspace(0,1,101)
best=min(grid,key=lambda p: np.abs(np.quantile(cb,np.linspace(.05,.95,19))-np.quantile(np.r_[np.random.default_rng(0).choice(ca,int(p*4000)),np.random.default_rng(1).choice(soft,int((1-p)*4000)+1)],np.linspace(.05,.95,19))).sum())
print('mieszanka: czarne "1" = %.0f%% kontekstu zwyklych nut + %.0f%% kontekstu cichych'%(100*best,100*(1-best)))
