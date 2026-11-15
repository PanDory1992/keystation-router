import numpy as np, warnings
from sklearn.ensemble import GradientBoostingRegressor
from cens import load_all, features, tobit, BLACK, maps
from scipy.stats import ks_2samp
warnings.filterwarnings('ignore')
t, n, raw, out = load_all(); blk = np.isin(n % 12, list(BLACK)); Lw, Lb = maps('light')
split = t[0] + (t[-1] - t[0]) * 0.5
c = 41
hide = (~blk) & (raw >= 2) & (raw < c); obs = raw.copy(); obs[hide] = 1
F = features(t, n, obs); tr, te = hide & (t < split), hide & (t >= split)
gmean = raw[tr].mean(); mu = np.where(np.isnan(F['mu']), gmean, F['mu'])
X = np.c_[np.nan_to_num(F['mu'], nan=-1), np.minimum(F['ioi'], 3), np.nan_to_num(F['prev'], nan=-1), F['chord'], F['left'], n]
gb = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0).fit(X[tr], raw[tr])
E = {'stala': np.full(len(t), gmean), 'Tobit s=20': tobit(mu, 20, c), 'GBM': np.clip(gb.predict(X), 2, c - 1)}
# 1) how much does context explain INSIDE the hole (raw units)?
print('[1] w surowych jednostkach (prog 41): rozrzut prawdy sd =', round(raw[te].std(), 1))
for k, e in E.items():
    d = e[te] - raw[te]; print(f'    {k:10s} MAE {np.abs(d).mean():.1f}  R2 {1 - (d**2).mean() / raw[te].var():+.2f}')
# 2) the same under a curve that gives the bottom more room (2..40 -> 6..40 linear, Light above)
S = Lw.copy().astype(float); S[2:41] = np.linspace(6, 40, 39); S[41:] = np.maximum(Lw[41:], 41); S = np.maximum.accumulate(S).round().astype(int)
print('[2] krzywa z rozciagnietym dolem (2..40 -> 6..40): MAE na wyjsciu')
for k, e in E.items():
    print(f'    {k:10s} {np.abs(S[np.round(e[te]).astype(int)] - S[raw[te]]).mean():.1f}')
print('    dzisiejsza regula na tej krzywej mialaby i tak bias ~+16 (nie zalezy od krzywej, bo dziala na wyjsciu)')
# 3) is white-censoring a fair stand-in for the black hole? compare contexts of real black 1s vs hidden whites
Fb = features(t, n, raw); bl1 = blk & (raw == 1)
for name in ('mu', 'ioi'):
    a = F[name][hide]; b = Fb[name][bl1]; a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    print(f'[3] kontekst {name}: biale ukryte mediana {np.median(a):.2f} vs czarne 1 {np.median(b):.2f}  KS {ks_2samp(a, b).statistic:.2f}')
# 4) same physics above the hole? black vs white raw >= 41
qb = np.percentile(raw[blk & (raw >= 41)], [10, 25, 50, 75, 90]); qw = np.percentile(raw[~blk & (raw >= 41)], [10, 25, 50, 75, 90])
print('[4] surowe >=41 kwantyle 10/25/50/75/90  czarne', qb.astype(int), ' biale', qw.astype(int), ' KS', round(ks_2samp(raw[blk & (raw >= 41)], raw[~blk & (raw >= 41)]).statistic, 3))
print('    Light na tych samych surowych: czarne 41/60/80/100 ->', [int(Lb[x]) for x in (41, 60, 80, 100)], ' biale ->', [int(Lw[x]) for x in (41, 60, 80, 100)])
# 5) soft notes inside loud chords: how common for REAL (measured) white notes? (glitch vs genuine)
def chords(sel):
    res = [];  i = 0
    while i < len(t):
        j = i
        while j + 1 < len(t) and t[j + 1] - t[i] < 0.03: j += 1
        if j > i:
            idx = np.arange(i, j + 1)
            for k in idx:
                mates = idx[(idx != k) & (raw[idx] > 1)]
                if sel[k] and len(mates) and np.median(raw[mates]) >= 80: res.append(raw[k])
        i = j + 1
    return np.array(res)
w_in = chords(~blk & (raw > 1)); b_in = chords(blk)
print(f'[5] biale w glosnym akordzie (koledzy >=80): {len(w_in)} nut, z tego ponizej 41: {100 * (w_in < 41).mean():.1f}%')
print(f'    czarne w glosnym akordzie: {len(b_in)}, z tego "1": {100 * (b_in == 1).mean():.1f}%  (a czarne 41-60: {100 * ((b_in >= 41) & (b_in < 60)).mean():.1f}%)')
# 6) real black 1s through the candidates, on two curves for black (today's black curve vs white curve)
Fr = features(t, n, raw); mur = np.where(np.isnan(Fr['mu']), gmean, Fr['mu'])
cand = {'stala': np.full(bl1.sum(), gmean), 'Tobit s=20': tobit(mur[bl1], 20, c)}
print('[6] prawdziwe czarne "1": dzis wyjscie mediana', int(np.median(out[bl1])), '; zmierzone czarne 41-55 ->', int(np.median(out[blk & (raw >= 41) & (raw <= 55)])))
for k, e in cand.items():
    e = np.round(e).astype(int)
    print(f'    {k:10s} przez krzywa czarnych: p10/50/90 {np.percentile(Lb[e], [10, 50, 90]).astype(int)}   przez krzywa bialych: {np.percentile(Lw[e], [10, 50, 90]).astype(int)}')
