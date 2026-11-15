import csv, sys, numpy as np
BLACK = {1, 3, 6, 8, 10}
rows = [r for r in csv.reader(open('/mnt/user-data/uploads/CodexPedalModes/notes/notes-2026-W46.csv')) if len(r) >= 5 and r[1] == 'on' and r[4] != '']
T = np.array([float(r[0]) for r in rows]); N = np.array([int(r[2]) for r in rows]); R = np.array([int(r[3]) for r in rows]); O = np.array([int(r[4]) for r in rows])
def stats(name, sel):
    t, n, r, o = T[sel], N[sel], R[sel], O[sel]; b = np.isin(n % 12, list(BLACK)); m = r > 1
    i = np.where((np.diff(t) < 0.6) & (np.diff(n) == 0) & m[:-1] & m[1:])[0]
    sr = np.median(np.abs(np.diff(r)[i])) / 0.954; so = np.median(np.abs(np.diff(o)[i])) / 0.954
    lo, hi = np.percentile(r[m], [5, 95]); olo, ohi = np.percentile(o[m], [5, 95])
    # phrase level range (EMA 0.3, new phrase after 1.5 s)
    L = []; cur = None; last = -1e9
    for k in np.where(m)[0]:
        if cur is None or t[k] - last > 1.5: cur = float(o[k])
        cur = .7 * cur + .3 * o[k]; L.append(cur); last = t[k]
    pr = np.percentile(L, 95) - np.percentile(L, 5)
    # sigma by band (raw)
    band = {}
    for a, z in ((41, 85), (85, 105), (105, 128)):
        j = i[(r[i] >= a) & (r[i] < z)]
        band[f'{a}-{z-1}'] = (len(j), np.median(np.abs(np.diff(r)[j])) / 0.954 if len(j) >= 8 else float('nan'))
    print(f'{name}: nut {sel.sum()}, powtorzen {len(i)}, "1" {100*(~m).mean():.1f}%')
    print(f'   surowo: zakres p5-p95 {lo:.0f}-{hi:.0f}, sigma {sr:.1f}  -> poziomy (odstep 2 sigma) {(hi-lo)/(2*sr)+1:.1f}')
    print(f'   wyjscie: zakres p5-p95 {olo:.0f}-{ohi:.0f}, sigma {so:.1f} -> poziomy (odstep 2 sigma) {(ohi-olo)/(2*so)+1:.1f};  fraza: zakres {pr:.0f} -> {pr/(2*so)+1:.1f}')
    print('   sigma surowo wg sily:', {k: f'{v[1]:.1f} (n={v[0]})' for k, v in band.items()})
moje = T > 1794702130
stats('Moje v2 (dzis)', moje)
stats('Light (13-15.11, przed)', (T > 1794600000) & ~moje & (T < 1794702000))
stats('caly tydzien 46 przed Moje', ~moje)
