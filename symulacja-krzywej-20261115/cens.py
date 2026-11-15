"""Censored-velocity study (15.11.2026). Ground truth: white keys measure 2..127, so white notes are censored
artificially below c (like the black-key hole) and each estimator tries to recover them. Causal features only
(what the router knows at the moment of the note) unless marked 'oracle'."""
import csv, numpy as np, datetime as dt
from scipy.stats import norm
from load import BLACK, U, maps

def load_all(since=dt.datetime(2026, 11, 4)):
    rows = []
    for wk in ('W45', 'W46'):
        for r in csv.reader(open(U + f'notes/notes-2026-{wk}.csv', encoding='utf-8')):
            try:
                if r[1] == 'on' and float(r[0]) >= since.timestamp():
                    rows.append((float(r[0]), int(r[2]), int(r[3]), int(r[4])))
            except (ValueError, IndexError):
                pass
    a = np.array(rows); a = a[np.argsort(a[:, 0], kind='stable')]
    return a[:, 0], a[:, 1].astype(int), a[:, 2].astype(int), a[:, 3].astype(int)

def features(t, n, raw, alpha=0.3, gap=1.5):
    """Per note, from previous notes only: phrase level (EMA of measured raws), time since previous note,
    previous raw, chord flag (another note within 30 ms before), hand."""
    N = len(t); mu = np.full(N, np.nan); ioi = np.full(N, 9.0); prev = np.full(N, np.nan); chord = np.zeros(N, bool)
    L = None; last = -1e9; lastraw = np.nan
    for i in range(N):
        if L is not None and t[i] - last <= gap:
            mu[i] = L; ioi[i] = t[i] - last; prev[i] = lastraw; chord[i] = t[i] - last < 0.03
        else:
            L = None
        if raw[i] > 1:                       # only measured values update the level
            L = raw[i] if L is None else (1 - alpha) * L + alpha * raw[i]
            lastraw = raw[i]
        last = t[i]
    return dict(mu=mu, ioi=ioi, prev=prev, chord=chord, left=n < 60)

def oracle_mu(t, raw, w=0.5):
    """Mean of measured neighbours within +-w s, future included (the router cannot have this)."""
    out = np.full(len(t), np.nan)
    lo = np.searchsorted(t, t - w); hi = np.searchsorted(t, t + w)
    cs = np.r_[0, np.cumsum(np.where(raw > 1, raw, 0))]; cn = np.r_[0, np.cumsum(raw > 1)]
    s = cs[hi] - cs[lo] - np.where(raw > 1, raw, 0); c = cn[hi] - cn[lo] - (raw > 1)
    ok = c > 0; out[ok] = s[ok] / c[ok]
    return out

def tobit(mu, s, c, lo=2.0):
    """E[v | lo <= v < c] for v ~ N(mu, s): the mean of the prior truncated to the hole."""
    a, b = (lo - mu) / s, (c - mu) / s
    Z = norm.cdf(b) - norm.cdf(a)
    m = mu + s * (norm.pdf(a) - norm.pdf(b)) / np.maximum(Z, 1e-12)
    return np.clip(np.where(Z > 1e-9, m, c - 1), lo, c - 1)
