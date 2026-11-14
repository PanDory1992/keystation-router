import csv, json, numpy as np
U='/mnt/user-data/uploads/CodexPedalModes/'
BLACK={1,3,6,8,10}
def load(week):
    t,n,r=[],[],[]
    for row in csv.reader(open(U+f'notes/notes-2026-{week}.csv',encoding='utf-8')):
        try:
            if row[1]!='on': continue
            t.append(float(row[0])); n.append(int(row[2])); r.append(int(row[3]))
        except (ValueError,IndexError): pass
    t,n,r=map(np.array,(t,n,r)); o=np.argsort(t,kind='stable')
    return t[o],n[o],r[o]
def maps(name):
    d=json.load(open(U+f'velocity-map.{name}.json')); return np.array(d['white']),np.array(d['black'])
