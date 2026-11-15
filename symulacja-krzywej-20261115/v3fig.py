import pickle, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from v3sim import VARS, sigma, W2, curve_top, curve_blend
from cens import load_all
mc, bands = pickle.load(open('mc.pkl', 'rb')); real = pickle.load(open('real.pkl', 'rb'))
BG, INK, INK2, GRID, GRAY = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df', '#9a9993'
C = {'v2 (teraz)': '#2a78d6', 'v3e': '#eb6834', 'v3a': '#1baf7a', 'EB': '#eda100', 'v3f': '#e87ba4'}
KEY = {'bez odszumiania': ('bez odszum.', GRAY), 'v2 (teraz)': ('v2 (teraz)', C['v2 (teraz)']), 'v3a: prog = 2 sigma': ('v3a: próg 2σ', C['v3a']),
       'v3c-EB: k z szumu': ('v3-EB: k z szumu', C['EB']), 'v3e: prog min(12, 2 sigma) + rece + bez sufitu': ('v3e: min(12,2σ)\n+ ręce', C['v3e']), 'v3f: v3e + akcenty w calosci': ('v3f: v3e +\nakcenty w całości', C['v3f'])}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.facecolor': BG, 'figure.facecolor': BG, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6, 'axes.axisbelow': True})
fig, ax = plt.subplots(2, 3, figsize=(16, 9.2)); fig.subplots_adjust(hspace=0.42, wspace=0.28, top=0.88, bottom=0.08, left=0.05, right=0.98)
fig.suptitle('Moje v2 i kandydaci na v3: symulacja (3 poziomy szumu × 12 przebiegów × 9000 nut) i twoja gra 04–15.11', x=0.05, ha='left', fontsize=14, color=INK, weight='bold')
def title(a, s, sub): a.set_title(s, loc='left', fontsize=12, color=INK, weight='bold', pad=22); a.text(0, 1.02, sub, transform=a.transAxes, fontsize=9, color=INK2)
# 1 curves
a = ax[0, 0]; x = np.arange(2, 128)
t, n, raw, _ = load_all(); h, e = np.histogram(raw[raw > 1], bins=63, range=(2, 128)); a.fill_between(e[:-1], 0, h / h.max() * 40, step='post', color=GRID, lw=0)
a.text(4, 33, 'jak często grasz\ndaną siłę', fontsize=8, color=INK2)
a.plot(x, W2[2:], color=C['v2 (teraz)'], lw=2, label='v2 (teraz)'); a.plot(x[108:], curve_top(W2)[110:], color=C['v3e'], lw=2, label='v3: bez sufitu (od 110)')
a.plot(x, curve_blend(W2)[2:], color=C['v3a'], lw=2, label='v3d: 30% miejsca dla p')
a.set_xlabel('siła z klawiatury (surowo)'); a.set_ylabel('velocity do Pianoteqa'); a.set_xlim(2, 127); a.set_ylim(0, 128); a.legend(frameon=False, fontsize=8, loc='upper left', bbox_to_anchor=(0, 0.88))
title(a, 'Krzywa', 'v3 zmienia tylko górny koniec; v3d daje więcej miejsca cichym')
# 2 thresholds
a = ax[0, 1]; r = np.arange(2, 128)
a.plot(r, sigma(r), color=GRAY, lw=1.5, label='twój rozrzut σ (rampy)')
a.plot(r, np.full_like(r, 12.0, dtype=float), color=C['v2 (teraz)'], lw=4.5, label='v2: próg 12 wszędzie')
a.plot(r, 2 * sigma(r), color=C['v3a'], lw=2, label='v3a: próg 2σ')
a.plot(r, np.minimum(12, 2 * sigma(r)), color=C['v3e'], lw=2, label='v3e: min(12, 2σ)')
a.set_xlabel('poziom frazy (surowo)'); a.set_ylabel('próg: większe zmiany to „zamiar”'); a.set_xlim(2, 127); a.set_ylim(0, 42); a.legend(frameon=False, fontsize=8)
title(a, 'Co router uznaje za szum', 'w forte twój szum to ±3, a v2 tłumi zmiany do 12')
# 3 MC error vs v2
a = ax[0, 2]; names = ['v3a: prog = 2 sigma', 'v3c-EB: k z szumu', 'v3e: prog min(12, 2 sigma) + rece + bez sufitu', 'v3f: v3e + akcenty w calosci']; nz = [0.7, 1.0, 1.3]; w = 0.2
for k, nm in enumerate(names):
    vals = [100 * (np.mean(mc[z][nm]['rmse']) / np.mean(mc[z]['v2 (teraz)']['rmse']) - 1) for z in nz]
    b = a.bar(np.arange(3) + (k - 1.5) * w, vals, w - 0.03, color=KEY[nm][1], label=KEY[nm][0])
    for xx, v in zip(np.arange(3) + (k - 1.5) * w, vals): a.text(xx, v + (0.4 if v >= 0 else -0.9), f'{v:+.0f}%', ha='center', fontsize=8, color=INK2)
a.axhline(0, color=INK2, lw=0.8); a.set_xticks(range(3)); a.set_xticklabels(['ręka równiejsza\n(szum ×0,7)', 'jak dziś\n(×1,0)', 'mniej równa\n(×1,3)'])
a.set_ylabel('błąd względem zamiaru, zmiana do v2'); a.set_ylim(-21, 26); a.legend(frameon=False, fontsize=8, loc='upper left', ncol=2)
title(a, 'Monte Carlo: wierność zamiarowi', 'mniej = lepiej (równiej), v2 = 0')
# 4,5,6 bars
order = ['bez odszumiania', 'v2 (teraz)', 'v3a: prog = 2 sigma', 'v3c-EB: k z szumu', 'v3e: prog min(12, 2 sigma) + rece + bez sufitu', 'v3f: v3e + akcenty w calosci']
def bars(a, vals, fmt, ylab, ttl, sub, ymax):
    xs = np.arange(len(order)); a.bar(xs, vals, 0.62, color=[KEY[o][1] for o in order])
    for xx, v in zip(xs, vals): a.text(xx, v + ymax * 0.015, fmt.format(v), ha='center', fontsize=9, color=INK)
    a.set_xticks(xs); a.set_xticklabels([{'bez odszumiania':'bez\nodszum.','v2 (teraz)':'v2\n(teraz)','v3a: prog = 2 sigma':'v3a\npróg 2σ','v3c-EB: k z szumu':'v3-EB\nk z szumu','v3e: prog min(12, 2 sigma) + rece + bez sufitu':'v3e\nzrównoważ.','v3f: v3e + akcenty w calosci':'v3f\nżywszy'}[o] for o in order], fontsize=7.5); a.set_ylabel(ylab); a.set_ylim(0, ymax); a.grid(axis='x', visible=False)
    title(a, ttl, sub)
bars(ax[1, 0], [100 * np.mean(mc[1.0][o]['stepk_f']) for o in order], '{:.0f}%', 'część skoku, która dociera', 'Świadomy skok w forte', 'symulacja: zmiana o 6–24 surowo, 1. nuta po zmianie', 110)
bars(ax[1, 1], [real[o]['acc'] for o in order], '{:.0f}', 'mediana akcentu (velocity)', 'Akcenty w twojej grze', 'nuta o 24+ mocniejsza od frazy; więcej = akcent zostaje', 60)
bars(ax[1, 2], [100 * real[o]['voice'] for o in order], '{:.0f}%', 'zachowana różnica prawa − lewa', 'Melodia nad akompaniamentem', f'{real["v2 (teraz)"]["nvoice"]} akordów obu rąk z twojej gry', 115)
fig.savefig('/mnt/user-data/outputs/moje-v3-symulacja.png', dpi=150)
print('ok')
