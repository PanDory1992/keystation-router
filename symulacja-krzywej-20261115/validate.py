import numpy as np
from cens import load_all, BLACK, maps
from natural import fit, run, P
t, n, raw, out = load_all(); blk = np.isin(n % 12, list(BLACK)); Lw, Lb = maps('light')
split = t[0] + (t[-1] - t[0]) * 0.5; tr, te = t < split, t >= split
M = fit(t[tr], n[tr], raw[tr], blk[tr])
print('hole_w %.1f -> %d   hole_b %.1f -> %d   black41->%d   curve 2/20/41/60/80/90/100/110/127:' % (M['hole_w'], M['curve'][round(M['hole_w'])], M['hole_b'], M['curve'][round(M['hole_b'])], M['b2w'][41]),
      [int(M['curve'][x]) for x in (2, 20, 41, 60, 80, 90, 100, 110, 127)])
T, N, R, B = t[te], n[te], raw[te], blk[te]
light = np.where(B, Lb[R], Lw[R]); nat = run(M, T, N, R, B)
def phrase(o):
    Lv = np.zeros(len(o)); cur = None; last = -1e9
    for i in range(len(o)):
        if cur is None or T[i] - last > 1.5: cur = float(o[i])
        cur = .7 * cur + .3 * o[i]; Lv[i] = cur; last = T[i]
    return np.percentile(Lv[R > 1], 95) - np.percentile(Lv[R > 1], 5)
def rep_noise(o):
    i = np.where((np.diff(T) < .5) & (np.diff(N) == 0) & (R[:-1] > 1) & (R[1:] > 1))[0]; return float(np.median(np.abs(o[i + 1] - o[i])))
def voicing(o):
    v = []; i = 0
    while i < len(T):
        j = i
        while j + 1 < len(T) and T[j + 1] - T[i] < .03: j += 1
        if j > i:
            idx = np.arange(i, j + 1); top = idx[np.argmax(N[idx])]; rest = idx[idx != top]
            if (R[idx] > 1).all() and R[top] - R[rest].mean() >= 15: v.append(o[top] - o[rest].mean())
        i = j + 1
    return float(np.median(v)), len(v)
def accents(o):
    Lr = None; Lo = None; last = -1e9; a = []
    for i in range(len(R)):
        if R[i] <= 1: continue
        if Lr is None or T[i] - last > 1.5: Lr, Lo = float(R[i]), float(o[i])
        if R[i] - Lr > 24: a.append(o[i] - Lo)
        Lr = .7 * Lr + .3 * R[i]; Lo = .7 * Lo + .3 * o[i]; last = T[i]
    return float(np.median(a))
for name, o in (('Light', light), ('Naturalny', nat)):
    pr = phrase(o); rn = rep_noise(o); sig = 1.05 * rn / .954
    b1 = o[B & (R == 1)]; w1 = o[~B & (R == 1)]
    bm = o[B & (R > 1)]; wm = o[~B & (R > 1)]
    print(f'{name:10s} zakres frazy {pr:.0f}  nierownosc {rn:.0f}  poziomy {pr / sig:.1f}  glos melodii {voicing(o)[0]:.0f}  akcenty {accents(o):.0f}  '
          f'czarne/biale mediana {np.median(bm):.0f}/{np.median(wm):.0f}  "1" czarne/biale {np.median(b1):.0f}/{np.median(w1):.0f}  '
          f'czarne "1" glosniej niz zmierzone 41: {100 * (b1 > (Lb[41] if name == "Light" else M["curve"][M["b2w"][41]])).mean():.0f}%')
c = M['curve']; print('monotonicznosc krzywej:', bool((np.diff(c[1:]) >= 0).all()), ' czarne (krzywa po b2w):', bool((np.diff(c[M['b2w'][41:]]) >= 0).all()))
