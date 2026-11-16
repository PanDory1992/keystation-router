import csv,json,numpy as np
U='/mnt/user-data/uploads/CodexPedalModes/'
BLACK={1,3,6,8,10}
raw=[];note=[];t=[]
for w in ('W46','W47'):
    for row in csv.reader(open(U+f'notes/notes-2026-{w}.csv',encoding='utf-8')):
        try:
            if row[1]!='on': continue
            t.append(float(row[0])); note.append(int(row[2])); raw.append(int(row[3]))
        except: pass
raw=np.array(raw); note=np.array(note); t=np.array(t)
blk=np.isin(note%12,list(BLACK))
print('notes',len(raw),'ones white %.1f%% black %.1f%%'%(100*(raw[~blk]==1).mean(),100*(raw[blk]==1).mean()))
m=raw>1
print('raw quantiles white>1',np.percentile(raw[m&~blk],[5,10,25,50,75,90,95]),' black>1',np.percentile(raw[m&blk],[10,50,90]))
K=((2,15.0),(40,18.0),(60,20.0),(75,12.0),(85,5.0),(95,4.4),(105,3.2),(115,2.5),(127,2.0))
sig=lambda r:np.interp(r,[k[0] for k in K],[k[1] for k in K])
maps={n:json.load(open(U+f'velocity-map.{n}.json')) for n in ('light','acoustic','heavy','moje3')}
rows=list(csv.reader(open('/mnt/user-data/outputs/glosnosc/velocity-db-C2-C4.csv',encoding='utf-8')))
H=rows[0][1:]; A=np.array([[float(x) if x else np.nan for x in r[1:]] for r in rows[1:]]); D={h:A[:,j] for j,h in enumerate(H)}
inst={'Pianoteq (Shigeru)':'Ulubiony_PT','Imperial 84':'Bosendorfer290_Imperial_Kontakt','Estate':'Estate_Grand','AIR C7':'AIR_C7_GrandReal','X Grand':'EchoSoundWorks_XGrand'}
def env(n): return np.maximum.accumulate((D[n+'_C2']+D[n+'_C4'])/2)
r=raw[m]; b=blk[m]
for mode,mp in maps.items():
    W=np.array(mp['white']);B=np.array(mp['black'])
    out=np.where(b,B[r],W[r])
    print(f"\n{mode}: out p10/50/90 {np.percentile(out,[10,50,90])}")
    for name,col in inst.items():
        e=env(col); db=e[np.clip(out,1,127)-1]
        # hand noise in dB: half difference of dB at r±sigma (white map)
        s=sig(r); lo=np.clip(np.round(r-s).astype(int),2,127); hi=np.clip(np.round(r+s).astype(int),2,127)
        dlo=e[np.where(b,B[lo],W[lo])-1]; dhi=e[np.where(b,B[hi],W[hi])-1]
        noise=np.median((dhi-dlo)/2)
        p=np.percentile(db,[10,50,90])
        print(f"   {name:18s} dB p10 {p[0]:6.1f} p50 {p[1]:6.1f} p90 {p[2]:6.1f}  span10-90 {p[2]-p[0]:5.1f}  szum reki (med) {noise:4.1f} dB  span/2szum {(p[2]-p[0])/(2*noise):4.1f}  instr v10-127 {e[126]-e[9]:4.1f}")
