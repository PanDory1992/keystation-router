import numpy as np
from v3sim import synth, run, SPLIT
from sim2 import V_of, map_load
from curves import natural
W3,B3=map_load('moje3')
VS=[dict(name='moje3 (dzis)',tau='capped',hands=True,W=W3,B=B3,k=0.35,eb=None,denoise=True,taper=False),
    V_of('nat hi118 g1.0',natural(hi=118)),V_of('nat hi118 g1.3',natural(hi=118,g=1.3)),
    V_of('nat hi118 g1.5',natural(hi=118,g=1.5)),V_of('nat hi117 g1.6',natural(hi=117,g=1.6)),V_of('nat hi116 g1.5',natural(hi=116,g=1.5))]
for nz in (1.0,):
    R={V['name']:dict(e=[],st=[],stf=[],rng=[]) for V in VS}
    for sd in range(8):
        T,N,Rw,I,BL,ST=synth(np.random.default_rng(100+sd),nz); m=Rw>1
        for V in VS:
            o=run(V,T,N,Rw,BL); ideal=V['W'][np.round(I).astype(int)]
            span=V['W'][115]-V['W'][45]
            R[V['name']]['e'].append(np.sqrt(np.mean((o-ideal)[m]**2))/span)
            idx=np.where((np.abs(ST)>=6)&m)[0]; got=[];gotf=[]
            for i in idx[idx>0]:
                j=i-1
                while j>=0 and (N[j]<SPLIT)!=(N[i]<SPLIT): j-=1
                if j<0 or not m[j]: continue
                want=ideal[i]-ideal[j]
                if abs(want)>=4:
                    got.append((o[i]-o[j])/want)
                    if I[i]>=95: gotf.append((o[i]-o[j])/want)
            R[V['name']]['st'].append(np.median(got)); R[V['name']]['stf'].append(np.median(gotf)); R[V['name']]['rng'].append(span)
    for k,v in R.items(): print(f"{k:16s} blad wzgl. zamiaru {100*np.mean(v['e']):5.1f}% zakresu  skok dociera {100*np.mean(v['st']):4.0f}%  w forte {100*np.mean(v['stf']):4.0f}%  (zakres v45-115 = {np.mean(v['rng']):.0f})")
