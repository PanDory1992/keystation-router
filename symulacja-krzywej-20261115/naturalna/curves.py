import json, numpy as np
K_SENSOR = 131.7      # raw = K - t/tau (time between contacts); fitted to the hand's noise at fixed intent (ramps 15.11 + calibration 29.10)
def lspeed(r, K=K_SENSOR):
    """log key speed (relative) for raw velocity r: speed ~ 1/t ~ 1/(K - r)."""
    return -np.log(K - np.asarray(r, float))
def natural(lo=2, hi=122, floor=10, top=127, g=1.0, pivot=100, K=K_SENSOR):
    r = np.arange(128.0)
    n = (lspeed(np.clip(r, lo, 127), K) - lspeed(lo, K)) / (lspeed(hi, K) - lspeed(lo, K))
    if g != 1.0:
        P = (lspeed(pivot, K) - lspeed(lo, K)) / (lspeed(hi, K) - lspeed(lo, K))
        x = np.clip(n, 0, 1)
        up = x >= P
        a = np.where(up, (x - P) / (1 - P), (P - x) / P)
        h = a * (g - (g - 1) * a)                 # slope g at the pivot, 2-g at the ends: monotone for g <= 2
        x2 = np.where(up, P + (1 - P) * h, P - P * h)
        n = np.where(n > 1, 1 + (n - 1) * (2 - g), x2)   # beyond hi (raw > hi): keep the end slope, then clip
    out = floor + (top - floor) * n
    out = np.clip(np.round(out), 1, 127).astype(int)
    out[1] = floor - 1                            # white "1": slower than raw 2, just below the floor
    out[0] = 0
    return np.maximum.accumulate(out)
def map_load(name):
    d = json.load(open(f'velocity-map.{name}.json')); return np.array(d['white']), np.array(d['black'])
