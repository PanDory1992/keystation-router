"""Moje v2 vs v3 candidates. Real data (04-15.11) + today's ramps (ground-truth-ish intent) + Monte Carlo with known intent."""
import json, numpy as np
from cens import load_all, BLACK
J = json.load(open('velocity-map.moje.json')); W2 = np.array(J['white']); B2 = np.array(J['black'])
SPLIT = 60
# local noise of the hand at fixed intent (controlled ramps today + calibration 29.10), raw units
SK = np.array([2, 40, 60, 75, 85, 95, 105, 115, 127]); SV = np.array([15, 18, 20, 12, 5, 4.4, 3.2, 2.5, 2.0])
def sigma(r): return np.interp(r, SK, SV)

def curve_top(c):                       # v3 point 3: no flat ceiling above raw 110
    c = c.copy(); c[110:] = np.maximum(c[110:], np.arange(110, 128)); return c
def curve_blend(c, w=0.3):              # point 4: 30% uniform
    u = np.r_[0, c[1], np.round(np.linspace(c[2], 127, 126))]; out = np.round((1 - w) * c + w * u).astype(int); out[1] = c[1]; return np.maximum.accumulate(out)

def make(name, tau='fixed', hands=False, top=False, blend=0.0, k=0.35, eb=None, denoise=True, taper=False):
    W = W2.copy()
    if top: W = curve_top(W)
    if blend: W = curve_blend(W, blend)
    B = W.copy(); B[1] = B2[1]; B[2:41] = W[41]
    return dict(name=name, tau=tau, hands=hands, W=W, B=B, k=k, eb=eb, denoise=denoise, taper=taper)

def run(V, t, n, raw, black):
    out = np.zeros(len(t), int); lev = {}; last = {}; lastp = {}; recent = []
    for i in range(len(t)):
        recent = [(tt, x) for tt, x in recent if t[i] - tt <= 0.03]
        if raw[i] == 1:
            if black[i] and recent and np.median([x for _, x in recent]) >= 80:
                mm = int(round(np.median([x for _, x in recent]))); out[i] = round(0.6 * V['W'][mm] + 0.4 * V['B'][1])
            else: out[i] = V['B'][1] if black[i] else V['W'][1]
            continue
        h = 0
        if V['hands']:
            act = [hh for hh in (0, 1) if hh in last and t[i] - last[hh] <= 1.5]
            if len(act) == 2: h = min(act, key=lambda hh: abs(n[i] - lastp[hh]))
            elif len(act) == 1 and abs(n[i] - lastp[act[0]]) <= 12: h = act[0]
            else: h = 0 if n[i] < SPLIT else 1
        x0 = float(raw[i])
        L = lev.get(h) if (h in last and t[i] - last[h] <= 1.5) else None
        if V['denoise']:
            Lu = x0 if L is None else L; d = x0 - Lu
            if V['tau'] == 'fixed': tau, k = 12.0, V['k']
            else:
                s = sigma(Lu); tau = 2 * s if V['tau'] == 'sigma' else min(12.0, 2 * s)
                k = V['k'] if V['eb'] is None else float(np.clip(s * s / (s * s + V['eb'] ** 2), 0, 0.6))
            if abs(d) <= tau: d = d * (1 - k)
            elif V.get('taper') and abs(d) < 2 * tau: d = d - np.sign(d) * k * tau * (2 - abs(d) / tau)   # shrink fades out by 2*tau
            elif V.get('taper'): pass                                                                   # big accents pass whole
            else: d = d - np.sign(d) * k * tau
            x = int(round(max(41 if black[i] else 2, min(127, Lu + d))))
        else: x = int(raw[i])
        lev[h] = x0 if L is None else 0.7 * L + 0.3 * x0; last[h] = t[i]; lastp[h] = n[i]
        recent.append((t[i], int(raw[i])))
        out[i] = (V['B'] if black[i] else V['W'])[x]
    return out

VARS = [make('bez odszumiania', denoise=False), make('v2 (teraz)'),
        make('v3a: prog = 2 sigma', tau='sigma'), make('v3b: + osobno rece', tau='sigma', hands=True),
        make('v3c: + bez sufitu', tau='sigma', hands=True, top=True),
        make('v3c-EB: k z szumu', tau='sigma', hands=True, top=True, eb=8.0),
        make('v3d: + 30% miejsca dla p', tau='sigma', hands=True, top=True, blend=0.3),
        make('v3e: prog min(12, 2 sigma) + rece + bez sufitu', tau='capped', hands=True, top=True),
        make('v3e bez rak', tau='capped', top=True),
        make('v3f: v3e + akcenty w calosci', tau='capped', hands=True, top=True, taper=True)]

# ---------------- Monte Carlo with known intent ----------------
def synth(rng, noise=1.0, nseq=150):
    T, N, R, I, BL, STEP = [], [], [], [], [], []
    t0 = 0.0
    for s in range(nseq):
        base = rng.uniform(35, 118); voi = rng.uniform(0, 18); rh = []; lh = []
        lvl = base; tt = t0; root = rng.integers(48, 56)
        fig_off = {p: rng.normal(0, 3) for p in range(36, 96)}          # finger unevenness (unintended)
        for k in range(60):
            step = 0.0
            if rng.random() < 0.08: step = rng.choice([-1, 1]) * rng.uniform(6, 24)
            lvl = float(np.clip(lvl + step + rng.normal(0, 0.8), 25, 124))
            hand = rng.random() < 0.6
            p = int(root + 12 + rng.integers(0, 12)) if hand else int(root + rng.integers(-5, 5))
            intent = lvl if hand else lvl - voi
            r = intent + fig_off[p] + rng.normal(0, noise * sigma(intent))
            blk = (p % 12) in BLACK
            rr = int(round(np.clip(r, 1, 127)))
            if rr < 2 or (blk and rr < 41): rr = 1
            T.append(tt); N.append(p); R.append(rr); I.append(np.clip(intent, 2, 127)); BL.append(blk); STEP.append(step)
            tt += rng.uniform(0.12, 0.45) if rng.random() > 0.15 else rng.uniform(0.0, 0.025)
        t0 = tt + 3.0
    return [np.array(x) for x in (T, N, R, I, BL, STEP)]

def mc(noise=1.0, seeds=12):
    res = {V['name']: dict(rmse=[], band=[], stepk=[], stepk_f=[], voice=[]) for V in VARS}
    bands = [(25, 60), (60, 85), (85, 100), (100, 128)]
    for sd in range(seeds):
        T, N, R, I, BL, ST = synth(np.random.default_rng(100 + sd), noise)
        m = R > 1
        for V in VARS:
            o = run(V, T, N, R, BL); ideal = V['W'][np.round(I).astype(int)]
            e = (o - ideal)[m]; res[V['name']]['rmse'].append(np.sqrt(np.mean(e ** 2)))
            res[V['name']]['band'].append([np.sqrt(np.mean(((o - ideal)[m & (I >= a) & (I < z)]) ** 2)) for a, z in bands])
            # deliberate steps: share of the intended output jump that arrives on the first note after a step
            idx = np.where((np.abs(ST) >= 6) & m)[0]; idx = idx[idx > 0]
            got = []; gotf = []
            for i in idx:
                j = i - 1
                while j >= 0 and (N[j] < SPLIT) != (N[i] < SPLIT): j -= 1
                if j < 0 or not m[j]: continue
                want = ideal[i] - ideal[j]
                if abs(want) >= 4: got.append((o[i] - o[j]) / want); (gotf.append((o[i] - o[j]) / want) if I[i] >= 95 else None)
            res[V['name']]['stepk'].append(np.median(got)); res[V['name']]['stepk_f'].append(np.median(gotf))
    return res, bands

if __name__ == '__main__':
    import pickle
    out = {}
    for nz in (0.7, 1.0, 1.3):
        r, bands = mc(nz); out[nz] = r
        print(f'\n=== Monte Carlo, szum reki x{nz} (12 przebiegow x 150 fraz x 60 nut) ===')
        for k, v in r.items():
            b = np.mean(v['band'], 0)
            print(f'{k:28s} blad RMSE {np.mean(v["rmse"]):5.2f}+-{np.std(v["rmse"]):4.2f}  wg sily p/mp/mf-f/ff {b[0]:5.1f} {b[1]:5.1f} {b[2]:5.1f} {b[3]:5.1f}  '
                  f'skok dociera {100*np.mean(v["stepk"]):4.0f}%  w forte {100*np.mean(v["stepk_f"]):4.0f}%')
    pickle.dump((out, bands), open('mc.pkl', 'wb'))
