import numpy as np, pickle
from v3sim import VARS, run, SPLIT
from cens import load_all, BLACK
t, n, raw, _ = load_all(); blk = np.isin(n % 12, list(BLACK)); m = raw > 1
RES = {}
# today's ramps (indices into the full arrays)
TODAY = t > 1794715696.2
def smooth(y, w=13): return np.array([np.median(y[max(0, i - w // 2):i + w // 2 + 1]) for i in range(len(y))])
ramp_idx = []
for ps in ({54, 56, 58}, {53, 55, 57}, {60, 62, 64}):
    ins = TODAY & np.isin(n, list(ps)); s = None
    for k in range(len(n) + 1):
        if k < len(n) and ins[k] and (s is None or t[k] - t[k - 1] < 2.5):
            if s is None: s = k
        else:
            if s is not None and k - s >= 40: ramp_idx.append(np.arange(s, k))
            s = k if (k < len(n) and ins[k]) else None
groups = []; i = 0
while i < len(t):
    j = i
    while j + 1 < len(t) and t[j + 1] - t[i] < 0.03: j += 1
    idx = np.arange(i, j + 1)
    if m[idx].all() and (n[idx] >= SPLIT).any() and (n[idx] < SPLIT).any(): groups.append(idx)
    i = j + 1
for V in VARS:
    o = run(V, t, n, raw, blk); W = V['W']; ref = np.where(blk, V['B'][raw], W[raw])
    rep = np.where((np.diff(t) < 0.6) & (np.diff(n) == 0) & m[:-1] & m[1:])[0]
    rn = np.median(np.abs(np.diff(o)[rep]))
    rat = []
    for g in groups:
        R_ = g[n[g] >= SPLIT]; L_ = g[n[g] < SPLIT]; want = ref[R_].mean() - ref[L_].mean()
        if abs(want) >= 8: rat.append((o[R_].mean() - o[L_].mean()) / want)
    err = []
    for ri in ramp_idx:
        tr = smooth(raw[ri].astype(float)); ok = raw[ri] > 1
        err += list((o[ri] - W[np.round(tr).astype(int)])[ok])
    acc = []; Lr = None; last = -1e9
    for k in np.where(m)[0]:
        if Lr is None or t[k] - last > 1.5: Lr = float(raw[k])
        if raw[k] - Lr > 24: acc.append(o[k] - W[int(round(Lr))])
        Lr = .7 * Lr + .3 * raw[k]; last = t[k]
    RES[V['name']] = dict(rep=rn, voice=np.median(rat), nvoice=len(rat), ramp=np.sqrt(np.mean(np.array(err) ** 2)), acc=np.median(acc))
    print(f"{V['name']:28s} nierownosc powtorzen {rn:4.1f}  glos prawej nad lewa zachowany {100*np.median(rat):4.0f}% (n={len(rat)})  rampy blad {RES[V['name']]['ramp']:5.2f}  akcent {np.median(acc):4.0f}")
pickle.dump(RES, open('real.pkl', 'wb'))
