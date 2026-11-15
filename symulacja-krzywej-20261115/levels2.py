import csv, glob, numpy as np
BLACK = {1, 3, 6, 8, 10}
rows = []
for f in sorted(glob.glob('/mnt/user-data/uploads/CodexPedalModes/notes/notes-2026-W4[56].csv')):
    rows += [r for r in csv.reader(open(f)) if len(r) >= 5 and r[1] == 'on' and r[4] != '']
T = np.array([float(r[0]) for r in rows]); N = np.array([int(r[2]) for r in rows]); R = np.array([int(r[3]) for r in rows]); O = np.array([int(r[4]) for r in rows])
o = np.argsort(T, kind='stable'); T, N, R, O = T[o], N[o], R[o], O[o]
m = R > 1
i = np.where((np.diff(T) < 0.6) & (np.diff(N) == 0) & m[:-1] & m[1:])[0]
lvl = (R[i] + R[i + 1]) / 2; d = np.abs(R[i + 1] - R[i])
edges = [2, 30, 45, 60, 75, 85, 95, 105, 115, 128]
sig = []
print('sila (surowo)  powtorzen  sigma')
for a, z in zip(edges[:-1], edges[1:]):
    j = (lvl >= a) & (lvl < z); s = np.median(d[j]) / 0.954 if j.sum() >= 10 else np.nan; sig.append(s)
    print(f'{a:3d}-{z - 1:3d}       {j.sum():5d}    {s:5.1f}')
sig = np.array(sig); sig = np.where(np.isnan(sig), np.nanmax(sig), sig)
def levels(lo, hi):
    tot = 0.0
    for (a, z), s in zip(zip(edges[:-1], edges[1:]), sig):
        w = max(0, min(z, hi) - max(a, lo)); tot += w / (2 * s)
    return tot + 1
moje = T > 1794702130
for name, sel in (('dzis, Moje v2', moje), ('tydzien przed', ~moje & (T > 1794300000))):
    r = R[sel & m]; lo, hi = np.percentile(r, [5, 95])
    print(f'{name}: nut {sel.sum()}, zakres p5-p95 {lo:.0f}-{hi:.0f} -> {levels(lo, hi):.1f} poziomow;  "1": {100*(R[sel]==1).mean():.1f}%')
print('cala skala 2-127:', round(levels(2, 127), 1))
# where the levels sit
for a, z in ((2, 60), (60, 95), (95, 128)): print(f'  z tego {a}-{z-1}: {levels(a, z)-1:.1f}')
