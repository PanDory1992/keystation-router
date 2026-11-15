import csv, numpy as np
rows = [r for r in csv.reader(open('/mnt/user-data/uploads/CodexPedalModes/notes/notes-2026-W46.csv')) if len(r) >= 5 and r[1] == 'on' and float(r[0]) > 1794715696.2]
T = np.array([float(r[0]) for r in rows]); N = np.array([int(r[2]) for r in rows]); R = np.array([int(r[3]) for r in rows]); O = np.array([int(r[4]) for r in rows])
# runs of notes within one 3-pitch figure
def runs(pset, minlen=40):
    ins = np.isin(N, list(pset)); out = []; s = None
    for k in range(len(N) + 1):
        if k < len(N) and ins[k] and (s is None or T[k] - T[k - 1] < 2.5):
            if s is None: s = k
        else:
            if s is not None and k - s >= minlen: out.append((s, k))
            s = k if (k < len(N) and ins[k]) else None
    return out
ramps = []
for name, ps in (('czarne Fis-As-B (54-56-58)', {54, 56, 58}), ('biale F-G-A (53-55-57)', {53, 55, 57}), ('biale C-D-E (60-62-64)', {60, 62, 64})):
    for a, z in runs(ps): ramps.append((name, a, z))
allres = []; perpitch = {}
def smooth(y, w=9):
    out = np.empty(len(y))
    for i in range(len(y)):
        lo, hi = max(0, i - w // 2), min(len(y), i + w // 2 + 1); out[i] = np.median(y[lo:hi])
    return out
for name, a, z in ramps:
    t, n, r, o = T[a:z], N[a:z], R[a:z], O[a:z]
    k0 = int(np.argmin(np.convolve(np.where(r == 1, 0, r), np.ones(8) / 8, 'same')[:len(r) // 2])) if (r[:len(r)//2] == 1).any() else 0
    t, n, r, o = t[k0:], n[k0:], r[k0:], o[k0:]
    m = r > 1
    # trend over the whole figure (all pitches): running median of a 4-note cycle x 3
    tr = smooth(np.where(m, r, np.nan) if False else r.astype(float), 13)
    res = (r - tr)[m]
    # per-pitch offset (finger evenness) then the rest
    offs = {p: float(np.median((r - tr)[m & (n == p)])) for p in sorted(set(n))}
    res2 = np.array([r[i] - tr[i] - offs[n[i]] for i in np.where(m)[0]])
    ones = {p: f'{100 * ((r == 1) & (n == p)).sum() / max(1, (n == p).sum()):.0f}%' for p in sorted(set(n))}
    print(f'{name}: nut {len(r)}, zakres {np.percentile(r[m],5):.0f}-{np.percentile(r[m],95):.0f}, "1": {ones}')
    print(f'    przesuniecie klawiszy wzgledem trendu: { {p: round(v) for p, v in offs.items()} }')
    for lo, hi in ((2, 60), (60, 85), (85, 100), (100, 128)):
        j = (tr[m] >= lo) & (tr[m] < hi)
        if j.sum() >= 6: print(f'    sila {lo}-{hi-1}: n={j.sum():3d}  rozrzut sigma calosc {1.4826*np.median(np.abs(res[j])):5.1f}  bez przesuniec palcow {1.4826*np.median(np.abs(res2[j])):5.1f}')
    allres += [(tr[m][i], res[i], res2[i]) for i in range(m.sum())]
A = np.array(allres); edges = [2, 45, 60, 75, 85, 95, 105, 115, 128]; sig1 = []; sig2 = []
print('\nWSZYSTKIE RAMPY: sila / sigma (calosc) / sigma (bez przesuniec palcow)')
for a, z in zip(edges[:-1], edges[1:]):
    j = (A[:, 0] >= a) & (A[:, 0] < z)
    s1 = 1.4826 * np.median(np.abs(A[j, 1])) if j.sum() >= 6 else np.nan; s2 = 1.4826 * np.median(np.abs(A[j, 2])) if j.sum() >= 6 else np.nan
    sig1.append(s1); sig2.append(s2); print(f'  {a:3d}-{z-1:3d}  n={j.sum():3d}  {s1:5.1f}  {s2:5.1f}')
def lev(sig, lo=2, hi=127):
    sig = np.where(np.isnan(sig), np.nanmax(sig), sig)
    return 1 + sum(max(0, min(z, hi) - max(a, lo)) / (2 * s) for (a, z), s in zip(zip(edges[:-1], edges[1:]), sig))
print(f'poziomy na calej skali 2-127: {lev(np.array(sig1)):.1f} (z nierownoscia palcow)  {lev(np.array(sig2)):.1f} (gdyby palce byly rowne)')
for lo, hi in ((2, 60), (60, 95), (95, 127)): print(f'   {lo}-{hi}: {lev(np.array(sig1), lo, hi) - 1:.1f} / {lev(np.array(sig2), lo, hi) - 1:.1f}')
