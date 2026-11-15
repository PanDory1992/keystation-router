import numpy as np
from cens import load_all, BLACK, maps
import natural2 as N2
import validate as V   # reuses metrics on the test half (prints the old comparison first)
t, n, raw = V.t, V.n, V.raw; blk = V.blk; tr, te = V.tr, V.te
W, B = N2.fit(raw[tr], blk[tr])
nat2 = N2.run(W, B, V.T, V.N, V.R, V.B)
o = nat2; pr = V.phrase(o); rn = V.rep_noise(o); sig = 1.05 * rn / .954
b1 = o[V.B & (V.R == 1)]; w1 = o[~V.B & (V.R == 1)]
print(f'Moje v2     zakres frazy {pr:.0f}  nierownosc {rn:.0f}  poziomy {pr / sig:.1f}  glos melodii {V.voicing(o)[0]:.0f}  akcenty {V.accents(o):.0f}  '
      f'czarne/biale mediana {np.median(o[V.B & (V.R > 1)]):.0f}/{np.median(o[~V.B & (V.R > 1)]):.0f}  "1" czarne/biale {np.median(b1):.0f}/{np.median(w1):.0f}  czarne "1" glosniej niz zmierzone 41: {100 * (b1 > B[41]).mean():.0f}%')
Wf, Bf = N2.fit(raw, blk)
print('pelne dopasowanie: biale 1/2/20/41/60/80/90/100/110/127 =', [Wf[x] for x in (1, 2, 20, 41, 60, 80, 90, 100, 110, 127)], ' czarne 1 =', Bf[1], ' czarne 41 =', Bf[41])
print('monotoniczne:', all(np.diff(Wf[1:]) >= 0), all(np.diff(Bf[1:]) >= 0))
import json; json.dump({'W': Wf, 'B': Bf}, open('moje2.json', 'w'))
