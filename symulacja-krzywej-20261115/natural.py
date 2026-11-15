"""One velocity mode, built from the studies of 15.11.2026 (raw = what the keyboard sends):
 1. black raw >= 41 -> white-equivalent by quantile matching (same physics, the router's old black curve was ~5-10 low);
 2. measured notes: contextual shrinkage toward the phrase level (sensor noise sigma ~7 raw), accents pass;
 3. "1" = censored: white -> mean of measured white below 25 (the white sensor's own thin zone),
    black -> mean of white-equivalent below 42 (the black hole); black "1" right after a loud chord -> mostly the chord
    (a read error: 4.0% of black notes in loud chords vs 0.3-0.7% for genuine soft notes);
 4. one curve for both colours: contrast-limited equalisation of the hand's own distribution, slope <= 2.5."""
import numpy as np
from sim import clahe_curve

P = dict(k=0.35, tau=12.0, alpha=0.3, gap=1.5, chord_s=0.03, chord_loud=80, chord_w=0.6, white_cut=25, black_cut=42, smax=2.5)

def fit(t, n, raw, black):
    bq = np.sort(raw[black & (raw >= 41)]); wq = np.sort(raw[~black & (raw >= 41)])
    b2w = np.arange(128, dtype=float)
    for x in range(41, 128):
        b2w[x] = np.interp(np.searchsorted(bq, x, side='right') / len(bq), np.arange(1, len(wq) + 1) / len(wq), wq)
    b2w = np.maximum.accumulate(np.clip(np.round(b2w), 2, 127))
    w = raw[~black & (raw > 1)]
    hole_w = float(w[w < P['white_cut']].mean()); hole_b = float(w[w < P['black_cut']].mean())
    xs = np.r_[w, b2w[raw[black & (raw >= 41)]]].astype(int)
    curve = clahe_curve(xs, P['smax'])
    return dict(b2w=b2w.astype(int), curve=np.array(curve), hole_w=hole_w, hole_b=hole_b)

def run(M, t, n, raw, black, mode='natural'):
    """Causal, note by note, exactly as the router would do it. Returns output velocities."""
    out = np.zeros(len(t), int); L = None; last = -1e9; recent = []
    for i in range(len(t)):
        if L is not None and t[i] - last > P['gap']: L = None
        recent = [(tt, xx) for tt, xx in recent if t[i] - tt <= P['chord_s']]
        if raw[i] == 1:
            if black[i]:
                x = M['hole_b']
                if recent and np.median([xx for _, xx in recent]) >= P['chord_loud']:
                    x = P['chord_w'] * np.median([xx for _, xx in recent]) + (1 - P['chord_w']) * M['hole_b']
            else:
                x = M['hole_w']
        else:
            x0 = float(M['b2w'][raw[i]] if black[i] else raw[i])
            if L is None: L_use = x0
            else: L_use = L
            d = x0 - L_use
            d = d * (1 - P['k']) if abs(d) <= P['tau'] else d - np.sign(d) * P['k'] * P['tau']
            lo = M['b2w'][41] if black[i] else 2
            x = max(lo, min(127, L_use + d))
            L = x0 if L is None else (1 - P['alpha']) * L + P['alpha'] * x0
            recent.append((t[i], x0))
        out[i] = M['curve'][int(round(x))]
        last = t[i]
    return out
