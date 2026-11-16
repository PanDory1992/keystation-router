import numpy as np
from data import load, BLACK
t,n,raw,blk=load(); m=raw>1
W_S=0.6; SEMI=9
lo=np.searchsorted(t,t-W_S); hi=np.searchsorted(t,t+W_S)
res=np.full(len(t),np.nan)
for i in np.where(m)[0]:
    j=np.arange(lo[i],hi[i]); j=j[(j!=i)&m[j]&(np.abs(n[j]-n[i])<=SEMI)&(raw[j]>=60)]
    if len(j)>=2 and raw[i]>=60: res[i]=raw[i]-np.mean(raw[j])
keys=np.arange(21,109)
def kb(sel):
    b=np.full(128,np.nan); c=np.zeros(128,int)
    for k in keys:
        x=res[sel&(n==k)]; x=x[~np.isnan(x)]; c[k]=len(x)
        if len(x)>=60: lo_,hi_=np.percentile(x,[10,90]); b[k]=x[(x>=lo_)&(x<=hi_)].mean()
    return b,c
def detrend(b):
    d=np.full(128,np.nan)
    for k in keys:
        if np.isnan(b[k]): continue
        col=(k%12) in BLACK
        nb=[q for q in range(k-7,k+8) if q!=k and ((q%12) in BLACK)==col and not np.isnan(b[q])]
        if len(nb)>=2: d[k]=b[k]-np.median(b[nb])
    return d
rng=np.random.default_rng(1)
# split by day parity (different sessions) to avoid sharing phrases
day=(t//86400).astype(int); A=day%2==0
bA,cA=kb(A); bB,cB=kb(~A); bAll,cAll=kb(np.ones(len(t),bool))
dA,dB,dAll=detrend(bA),detrend(bB),detrend(bAll)
ok=~np.isnan(dA)&~np.isnan(dB)
r=np.corrcoef(dA[ok],dB[ok])[0,1]
print('keys',ok.sum(),'of 88; split by day corr %.2f; sd all %.2f; counts median %d'%(r,np.nanstd(dAll),np.median(cAll[keys])))
# week stability: W45+46 vs W47
wk=t>=1794787200-3*86400  # approx from 13.11? use last 25% of data instead
q=t>=np.percentile(t,75)
bC,_=kb(~q); bD,_=kb(q); dC,dD=detrend(bC),detrend(bD); ok2=~np.isnan(dC)&~np.isnan(dD)
print('early 75%% vs last 25%%: keys %d corr %.2f'%(ok2.sum(),np.corrcoef(dC[ok2],dD[ok2])[0,1]))
rel=r  # reliability of a half; of full data (Spearman-Brown)
relf=2*r/(1+r); print('reliability full %.2f -> shrink factor'%relf)
np.save('keydev2.npy',dAll); np.save('keycount.npy',cAll)
for k in keys:
    if not np.isnan(dAll[k]) and abs(dAll[k])>=3: print(k, round(float(dAll[k]),1), cAll[k], 'czarny' if (k%12) in BLACK else 'bialy')
