import numpy as np
from load import load, maps, BLACK
X=np.arange(128)

def hist(r, lo=2):
    h=np.bincount(r[r>=lo], minlength=128).astype(float); h[:lo]=0
    k=np.exp(-0.5*(np.arange(-6,7)/2.0)**2); k/=k.sum()          # smooth sampling noise (sigma 2 raw)
    return np.convolve(h,k,mode='same')

def clahe_curve(r, smax, lo_out=10, hi_out=127, x_min=2):
    """Contrast-limited equalisation: slope (out units per raw unit) never above smax; the excess is spread evenly."""
    h=hist(r, x_min); h[:x_min]=0
    span=hi_out-lo_out; n=128-x_min
    p=h/h.sum()
    for _ in range(200):                                   # clip and redistribute until stable
        cap=smax/span
        ex=np.clip(p-cap,0,None).sum()
        p=np.minimum(p,cap); p[x_min:]+=ex/n
        if ex<1e-9: break
    c=np.cumsum(p); c=(c-c[x_min-1])/(c[-1]-c[x_min-1])
    out=lo_out+span*c; out[:x_min]=lo_out
    return np.clip(np.round(out),1,127).astype(int)

def eq_curve(r): return clahe_curve(r, 1e9)

def shrink(t, r, k=0.35, tau=12.0, alpha=0.3, gap=1.5):
    """Contextual (empirical-Bayes) shrinkage toward the phrase level; accents beyond tau pass (soft threshold)."""
    xh=r.astype(float).copy(); L=None; last=-1e9
    for i in range(len(r)):
        if r[i]<=1: last=t[i]; continue                    # the '1's have their own context rule
        if L is None or t[i]-last>gap: L=float(r[i])
        d=r[i]-L
        dd = d*(1-k) if abs(d)<=tau else d-np.sign(d)*k*tau
        xh[i]=L+dd
        L=(1-alpha)*L+alpha*r[i]; last=t[i]
    return np.clip(np.round(xh),2,127).astype(int)

def apply(curves, n, x):
    blk=np.isin(n%12,list(BLACK)); w,b=curves
    return np.where(blk, b[x], w[x])

def metrics(t, n, r, out):
    m={}
    ok=r>1
    m['p5,25,50,75,95']=np.percentile(out[ok],[5,25,50,75,95]).round().astype(int).tolist()
    d=np.diff(t); ch=(d<0.025)&ok[:-1]&ok[1:]
    m['chord_noise']=float(np.median(np.abs(np.diff(out))[ch]))
    # phrase level of the output (causal EMA, reset after 1.5 s)
    L=np.zeros(len(out)); cur=None; last=-1e9
    for i in range(len(out)):
        if cur is None or t[i]-last>1.5: cur=float(out[i])
        cur=0.7*cur+0.3*out[i]; L[i]=cur; last=t[i]
    lo,hi=np.percentile(L[ok],[5,95])
    m['phrase_range']=round(hi-lo,1)
    sigma=1.05*m['chord_noise']/0.954 if m['chord_noise']>0 else 1
    m['levels']=round((hi-lo)/sigma,1)
    return m
