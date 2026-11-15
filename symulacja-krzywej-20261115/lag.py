"""Chord-lag test: in a chord, does a softer note arrive later (longer key travel)?"""
import numpy as np
from cens import load_all, BLACK
t, n, raw, out = load_all(); b = np.isin(n % 12, list(BLACK))
W = 0.08
rows = []   # (lag ms after the loudest-measured mate that came first, raw, black)
i = 0
while i < len(t):
    j = i
    while j + 1 < len(t) and t[j + 1] - t[i] < W: j += 1
    idx = np.arange(i, j + 1)
    if 2 <= len(idx) <= 5:
        ref = idx[raw[idx] >= 80]
        if len(ref):
            t0 = t[ref].min()
            for k in idx:
                if k in ref and t[k] == t0: continue
                rows.append(((t[k] - t0) * 1000, raw[k], b[k]))
    i = j + 1
R = np.array(rows)
lag, r, bk = R[:, 0], R[:, 1], R[:, 2].astype(bool)
def show(name, sel):
    x = lag[sel]
    print(f'{name:34s} n={sel.sum():5d}  mediana opoznienia {np.median(x):6.1f} ms   IQR {np.percentile(x,25):6.1f}..{np.percentile(x,75):6.1f}')
for lo, hi in ((2, 41), (41, 70), (70, 90), (90, 105), (105, 128)):
    show(f'biale raw {lo}-{hi - 1}', ~bk & (r >= lo) & (r < hi))
show('czarne raw 41-69', bk & (r >= 41) & (r < 70))
show('czarne raw >=90', bk & (r >= 90))
show('czarne "1"', bk & (r == 1))
show('biale "1"', ~bk & (r == 1))
x = lag[bk & (r == 1)]; print('czarne "1" opoznienie < 8 ms: %.0f%%,  > 25 ms: %.0f%%' % (100 * (x < 8).mean(), 100 * (x > 25).mean()))
x = lag[~bk & (r >= 2) & (r < 41)]; print('biale 2-40   opoznienie < 8 ms: %.0f%%,  > 25 ms: %.0f%%' % (100 * (x < 8).mean(), 100 * (x > 25).mean()))
x = lag[~bk & (r >= 90)]; print('biale >=90   opoznienie < 8 ms: %.0f%%,  > 25 ms: %.0f%%' % (100 * (x < 8).mean(), 100 * (x > 25).mean()))
