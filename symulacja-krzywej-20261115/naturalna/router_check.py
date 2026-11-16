import sys, json, numpy as np
sys.path.insert(0,'/home/claude/router'); sys.path.insert(0,'/home/claude/router/vendor'); sys.path.insert(0,'/home/claude/krzywe')
import os; os.chdir('/home/claude/krzywe')
from pedal_router import PedalMapper
from sim2 import V_of, run, t, n, raw, blk
for mode in ('naturalna','szeroka'):
    d=json.load(open(f'/home/claude/router/velocity-map.{mode}.json'))
    V=dict(name=mode,tau='capped',hands=True,W=np.array(d['white']),B=np.array(d['black']),k=0.35,eb=None,denoise=True,taper=False)
    sim=run(V,t,n,raw,blk)
    m=PedalMapper(); m.touch_maps={mode:(d['white'],d['black'])}; m.select_touch(mode)
    out=np.array([m.route([0x90,int(nn),int(rr)],now=float(tt-t[0]))[0][1][2] for tt,nn,rr in zip(t,n,raw)])
    print(mode, 'notes',len(out),'identical',int((out==sim).sum()))
