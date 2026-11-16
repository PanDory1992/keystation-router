import numpy as np, json
from data import load
from v3sim import run, synth, SPLIT
from sim import metrics
from curves import natural, map_load
t,n,raw,blk=load(); m=raw>1
def hole_mean(W, raw=raw, blk=blk):
    """expected output of a note in the black hole: white notes <= 40 (their 1s at the floor), output domain"""
    w=(~blk)&(raw<=40); return int(round(W[raw[w]].mean()))
def V_of(name, W, B=None, denoise=True):
    if B is None:
        B=W.copy(); B[1]=hole_mean(W); B[2:41]=W[41]
    return dict(name=name, tau='capped', hands=True, W=W, B=B, k=0.35, eb=None, denoise=denoise, taper=False)
def cands():
    L=[]
    W3,B3=map_load('moje3'); L.append(dict(name='moje3 (dzis)',tau='capped',hands=True,W=W3,B=B3,k=0.35,eb=None,denoise=True,taper=False))
    Wl,Bl=map_load('light'); L.append(dict(name='light',tau='fixed',hands=False,W=Wl,B=Bl,k=0.35,eb=None,denoise=False,taper=False))
    Wa,Ba=map_load('acoustic'); L.append(dict(name='acoustic',tau='fixed',hands=False,W=Wa,B=Ba,k=0.35,eb=None,denoise=False,taper=False))
    for nm,kw in (('nat hi122',dict()),('nat hi120',dict(hi=120)),('nat g1.3',dict(g=1.3)),('nat g1.5',dict(g=1.5)),('nat g1.3 hi120',dict(g=1.3,hi=120)),('nat lo28 hi120',dict(lo=28,hi=120))):
        L.append(V_of(nm,natural(**kw)))
    return L
def real_metrics(V,o):
    W=V['W']; ref=np.where(blk,V['B'][raw],W[raw])
    rep=np.where((np.diff(t)<0.6)&(np.diff(n)==0)&m[:-1]&m[1:])[0]
    rn=np.median(np.abs(np.diff(o)[rep]))
    acc=[];Lr=None;last=-1e9
    for k in np.where(m)[0]:
        if Lr is None or t[k]-last>1.5: Lr=float(raw[k])
        if raw[k]-Lr>24: acc.append(o[k]-W[int(round(Lr))])
        Lr=.7*Lr+.3*raw[k]; last=t[k]
    return rn, np.median(acc)
if __name__=='__main__':
    print(f"{'wariant':16s} p5  p25 p50 p75 p95 | czarne/biale med | zakres frazy  szum akordu  poziomy | nierown. powt.  akcent | 1 czarna/biala")
    for V in cands():
        o=run(V,t,n,raw,blk)
        p=np.percentile(o[m],[5,25,50,75,95]).astype(int)
        mt=metrics(t,n,raw,o); rn,acc=real_metrics(V,o)
        print(f"{V['name']:16s} {p[0]:3d} {p[1]:3d} {p[2]:3d} {p[3]:3d} {p[4]:3d} | {int(np.median(o[m&blk])):3d}/{int(np.median(o[m&~blk])):3d} | {mt['phrase_range']:5.1f}  {mt['chord_noise']:4.1f}  {mt['levels']:4.1f} | {rn:4.1f} {acc:5.1f} | {V['B'][1]}/{V['W'][1]}")
