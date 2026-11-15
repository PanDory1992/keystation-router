"""Final 'moje' (15.11, v2). Checks on 04-15.11 data:
 - same chord, both keys >= 41: black reads -0.7 raw vs white -> one sensor scale, ONE curve for both colours;
 - black "1" sit in quiet contexts (neighbours 84 raw, like genuine soft white notes 85-89; measured black 98) -> soft notes,
   not random read errors; black hole holds 7.2% of black notes (white <= 41: 3.8%);
 - after a loud chord (mates within 30 ms before, median >= 80) a black hole note is 4.4% vs expected 1.7% -> P(read error) 0.6;
 - white "1" = slower than raw 2 -> just below the floor."""
import json, numpy as np
from sim import clahe_curve
K, TAU, ALPHA, GAP, WIN, LOUD, PERR = .35, 12., .3, 1.5, .03, 80, .6

def fit(raw, black):
    meas = raw[(~black & (raw > 1)) | (black & (raw >= 41))]
    c = np.array(clahe_curve(meas.astype(int), 2.5)).astype(int); c[0] = 0
    w = raw[~black]; hole = w[(w <= 41)]
    one_w = max(1, int(c[2]) - 1)
    hole_out = float(np.where(hole == 1, one_w, c[np.maximum(hole, 1)]).mean())
    white = [int(x) for x in c]; white[1] = one_w
    blk = [int(x) for x in c]; blk[1] = int(round(hole_out))
    for x in range(2, 41): blk[x] = blk[41]          # never sent by the black sensor; kept monotone
    return white, blk

def run(white, blk, t, n, raw, black):
    out = np.zeros(len(t), int); L = {}; last = -1e9; recent = []
    for i in range(len(t)):
        recent = [(tt, x) for tt, x in recent if t[i] - tt <= WIN]
        if raw[i] == 1:
            if black[i] and recent and np.median([x for _, x in recent]) >= LOUD:
                m = int(round(np.median([x for _, x in recent])))
                out[i] = round(PERR * white[m] + (1 - PERR) * blk[1])
            else:
                out[i] = blk[1] if black[i] else white[1]
            continue
        lvl = L.get('v') if t[i] - last <= GAP else None
        lvl = raw[i] if lvl is None else lvl
        d = raw[i] - lvl; d = d * (1 - K) if abs(d) <= TAU else d - np.sign(d) * K * TAU
        x = int(round(max(41 if black[i] else 2, min(127, lvl + d))))
        L['v'] = (1 - ALPHA) * lvl + ALPHA * raw[i]; last = t[i]; recent.append((t[i], int(raw[i])))
        out[i] = (blk if black[i] else white)[x]
    return out
