import numpy as np
exec(open('plan-an2.py').read().split("maps={")[0])
r=raw[raw>1]; b=blk[raw>1]
rr=np.arange(1,128)
s=sig(rr)
F=np.concatenate([[0],np.cumsum(1/(2*s[1:]))])  # 2sigma-levels from raw 1
print('hand 2sigma levels raw2-127: %.1f ; 2-80: %.1f ; 80-119: %.1f ; 119-127: %.1f'%(F[126]-F[1],F[79]-F[1],F[118]-F[79],F[126]-F[118]))
# levels in Miki's used range p5-p95
p5,p95=np.percentile(r,[5,95]); print('used raw p5-p95',p5,p95,'levels %.1f'%(F[int(p95)-1]-F[int(p5)-1]))
# Schodki N=7 thresholds: equal sigma-levels over raw 40..122 (hand usable)
for N,lo,hi in ((7,30,122),(8,20,124),(6,40,120)):
    q=np.linspace(F[lo-1],F[hi-1],N+1)[1:-1]; th=[int(np.searchsorted(F,x)+1) for x in q]
    step=np.searchsorted(th,r,side='right'); share=np.bincount(step,minlength=N)/len(r)
    print(f'N={N} raw thresholds {th}  share % {np.round(100*share).astype(int)}')
# Variant A/B in dB on reference instruments
rows=list(csv.reader(open('/mnt/user-data/outputs/glosnosc/velocity-db-C2-C4.csv',encoding='utf-8')))
H=rows[0][1:]; A=np.array([[float(x) if x else np.nan for x in q[1:]] for q in rows[1:]]); D={h:A[:,j] for j,h in enumerate(H)}
inst={'Pianoteq':'Ulubiony_PT','X Grand':'EchoSoundWorks_XGrand','Imperial':'Bosendorfer290_Imperial_Kontakt'}
def env(n): return np.maximum.accumulate((D[n+'_C2']+D[n+'_C4'])/2)
for name,col in inst.items():
    e=env(col); dmin,dmax=e[9],e[126]
    # A: equal distinguishability (90% F_sigma + 10% linear) from raw 2 to 127
    fa=0.9*(F-F[1])/(F[126]-F[1])+0.1*(rr-2)/125
    dbA=dmin+(dmax-dmin)*np.clip(fa,0,1)
    # B: CLAHE in dB: hist of raw, clip slope 2.5x mean, cumulative
    h=np.bincount(r,minlength=128)[1:].astype(float); h[0]=0
    cap=2.5*h[1:].mean(); 
    for _ in range(20):
        ex=np.clip(h-cap,0,None).sum(); h=np.minimum(h,cap); h[1:]+=ex/126
    cdf=np.cumsum(h)/h.sum(); dbB=dmin+(dmax-dmin)*cdf
    for lab,db in (('A',dbA),('B',dbB)):
        d=db[r-1]; lo=np.clip(np.round(r-sig(r)).astype(int),2,127); hi=np.clip(np.round(r+sig(r)).astype(int),2,127)
        noise=np.median((db[hi-1]-db[lo-1])/2); p=np.percentile(d,[10,50,90])
        print(f'{name:9s} {lab}: dB p10 {p[0]:6.1f} p50 {p[1]:6.1f} p90 {p[2]:6.1f} span {p[2]-p[0]:5.1f} noise {noise:4.1f} ratio {(p[2]-p[0])/(2*noise):4.1f}')
