import csv, numpy as np, datetime as dt
U='/mnt/user-data/uploads/CodexPedalModes/notes/'
BLACK={1,3,6,8,10}
def load(weeks=('W45','W46','W47'), since=dt.datetime(2026,11,4)):
    rows=[]
    for wk in weeks:
        for r in csv.reader(open(U+f'notes-2026-{wk}.csv',encoding='utf-8')):
            try:
                if r[1]=='on' and float(r[0])>=since.timestamp(): rows.append((float(r[0]),int(r[2]),int(r[3])))
            except (ValueError,IndexError): pass
    a=np.array(rows); a=a[np.argsort(a[:,0],kind='stable')]
    t,n,r=a[:,0],a[:,1].astype(int),a[:,2].astype(int)
    return t,n,r,np.isin(n%12,list(BLACK))
