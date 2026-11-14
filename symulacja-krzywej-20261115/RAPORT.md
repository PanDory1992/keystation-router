# Symulacja krzywej dynamiki (15.11.2026)

Dane: notatki routera, tydzień 45 (29 114 uderzeń) i 46 (57 279). Dopasowanie na jednym tygodniu, test na drugim, i odwrotnie.

Szum czujnika: to samo uderzenie powtórzone (ten sam klawisz < 0,5 s) różni się o ok. 7 surowych jednostek (sigma ok. 7).

| Wariant | Zakres frazy | Nierówność powtórzeń | Rozróżnialne poziomy | Głos melodii w akordzie | Akcenty |
|---|---|---|---|---|---|
| Light (teraz) | 55 | 11 | 4,5 | 27 | 34 |
| Light + odszumianie k=0,35 | 54 | 7 | 7,0 | 21 | 29 |
| Pełne wyrównanie | 86 | 16 | 4,9 | — | — |
| CLAHE 2,5 | 70 | 15 | 4,2 | 37 | 42 |
| **CLAHE 2,5 + odszumianie k=0,35** | **70** | **10** | **6,4** | **27** | **34** |
| CLAHE 2,5 + k=0,5 | 71 | 8 | 8,0 | 23 | 30 |

Wnioski: sama krzywa nie dodaje informacji (poziomy ok. 4,5–4,9 dla każdej). Dodaje ją odszumianie kontekstowe. Kandydat CLAHE 2,5 + k=0,35 poszerza zakres frazy o 28% (test odwrotny: 60 → 76), nie zwiększa nierówności, zachowuje głos melodii i akcenty jak Light. Krzywa jest stabilna między tygodniami (różnica do 3).

Pliki: velocity-map.moje-kandydat.json (nieaktywny), sim.py, load.py. Odszumianie (funkcja shrink w sim.py) jest przyczynowe: używa tylko poprzednich nut, więc da się je dodać do routera.
