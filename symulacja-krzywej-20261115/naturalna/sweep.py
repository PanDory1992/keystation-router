import numpy as np
from sim2 import *
rows=[]
W3,B3=map_load('moje3')
base=[dict(name='moje3 (dzis)',tau='capped',hands=True,W=W3,B=B3,k=0.35,eb=None,denoise=True,taper=False)]
grid=[]
for hi in (116,118,120):
    for lo in (2,20):
        for g in (1.0,1.3,1.5):
            grid.append(V_of(f'hi{hi} lo{lo} g{g}',natural(lo=lo,hi=hi,g=g)))
for V in base+grid:
    o=run(V,t,n,raw,blk); mt=metrics(t,n,raw,o); rn,acc=real_metrics(V,o)
    p=np.percentile(o[m],[1,5,50,95,99]).astype(int)
    print(f"{V['name']:20s} p1 {p[0]:3d} p5 {p[1]:3d} p50 {p[2]:3d} p95 {p[3]:3d} p99 {p[4]:3d} @127 {100*(o[m]>=127).mean():4.1f}% | fraza {mt['phrase_range']:5.1f} szum {mt['chord_noise']:4.1f} poz {mt['levels']:4.1f} powt {rn:4.1f} akc {acc:4.0f} | dziura {V['B'][1]}")
