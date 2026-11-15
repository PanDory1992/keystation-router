import numpy as np, json, warnings
from sklearn.ensemble import GradientBoostingRegressor
from cens import load_all, features, oracle_mu, tobit, BLACK, maps
warnings.filterwarnings('ignore')
t, n, raw, out = load_all()
blk = np.isin(n % 12, list(BLACK)); Lw, Lb = maps('light')
split = t[0] + (t[-1] - t[0]) * 0.5
res = {}

def current_rule(t, outobs, measured, floor):
    """Today's router: phrase level of OUTPUT velocities (alpha .35, 2 s timeout), 1 -> level-16, cap 45."""
    est = np.full(len(t), float(floor)); L = None; last = -1e9
    for i in range(len(t)):
        if L is not None and t[i] - last <= 2.0 and not measured[i]:
            est[i] = max(floor, min(45, L - 16))
        if L is None or t[i] - last > 2.0: L = None
        if measured[i]: L = outobs[i] if L is None else 0.65 * L + 0.35 * outobs[i]
        last = t[i]
    return est

for c in (25, 41, 50):
    hide = (~blk) & (raw >= 2) & (raw < c)              # white notes the "sensor" can no longer see
    obs = raw.copy(); obs[hide] = 1
    F = features(t, n, obs); mu_o = oracle_mu(t, obs)
    tr, te = hide & (t < split), hide & (t >= split)
    truth = raw.astype(float)
    gmean = truth[tr].mean(); gmed = np.median(truth[tr])
    mu = np.where(np.isnan(F['mu']), gmean, F['mu']); muo = np.where(np.isnan(mu_o), gmean, mu_o)
    est = {}
    est['dzis (regula jedynek)'] = None   # output space, below
    est['ppp (zawsze najciszej)'] = np.full(len(t), 1.0)
    est['srodek dziury'] = np.full(len(t), (c + 2) / 2)
    est['fizyka 1/v^2'] = np.full(len(t), np.log(c / 2) / (1 / 2 - 1 / c))
    est['stala: srednia z danych'] = np.full(len(t), gmean)
    best = None
    for s in (6, 10, 15, 20, 30, 45):
        e = tobit(mu, s, c); m = np.abs(Lw[np.round(e[tr]).astype(int)] - Lw[raw[tr]]).mean()
        if best is None or m < best[0]: best = (m, s)
    est[f'Tobit, kontekst (s={best[1]})'] = tobit(mu, best[1], c)
    est['Tobit, kontekst z przyszlosci*'] = tobit(muo, best[1], c)
    # empirical Bayes: learn E[v | features, v < c] on the first half
    X = np.c_[np.nan_to_num(F['mu'], nan=-1), np.minimum(F['ioi'], 3), np.nan_to_num(F['prev'], nan=-1), F['chord'], F['left'], n]
    gb = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0).fit(X[tr], truth[tr])
    est['uczenie (GBM, 6 cech)'] = np.clip(gb.predict(X), 2, c - 1)
    # shrink Tobit toward the data mean (weight fitted on train)
    tb = est[f'Tobit, kontekst (s={best[1]})']
    ws = min(((np.abs(Lw[np.round((1 - w) * tb[tr] + w * gmean).astype(int)] - Lw[raw[tr]]).mean(), w) for w in np.linspace(0, 1, 11)))[1]
    est[f'Tobit + sciagniecie (w={ws:.1f})'] = (1 - ws) * tb + ws * gmean
    rows = {}
    tv = Lw[raw[te]].astype(float)
    for k, e in est.items():
        if e is None:
            measured = obs > 1
            eo = current_rule(t, Lw[np.maximum(obs, 1)].astype(float), measured, Lw[1])[te]
        else:
            eo = Lw[np.clip(np.round(e[te]).astype(int), 1, 127)].astype(float)
        d = eo - tv
        rows[k] = dict(MAE=round(float(np.abs(d).mean()), 1), RMSE=round(float(np.sqrt((d ** 2).mean())), 1), bias=round(float(d.mean()), 1),
                       w8=round(100 * float((np.abs(d) <= 8).mean())), nad_progiem=round(100 * float((eo > Lw[c]).mean())))
    res[c] = dict(n_test=int(te.sum()), n_train=int(tr.sum()), truth_out_median=float(np.median(tv)), rows=rows,
                  gb_importance=dict(zip(['poziom frazy', 'odstep', 'poprzednia', 'akord', 'lewa', 'wysokosc'], np.round(gb.feature_importances_, 2).tolist())))
json.dump(res, open('study.json', 'w'), indent=1, default=float)
for c, r in res.items():
    print(f'\n=== prog c={c}: test {r["n_test"]} nut (trening {r["n_train"]}), prawda na wyjsciu mediana {r["truth_out_median"]}')
    for k, v in sorted(r['rows'].items(), key=lambda kv: kv[1]['MAE']): print(f'  {k:32s} {v}')
    print('  waznosc cech GBM:', r['gb_importance'])
