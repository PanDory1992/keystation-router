# Moje v3e (15.11.2026): odszumianie zależne od siły, poziom frazy na rękę, bez sufitu

Router: czucie `moje3` (C53: Light → Acoustic → Heavy → Moje → Moje 3 → Light), mapa `velocity-map.moje3.json`.

## Zmiany względem Moje v2
1. Próg odszumiania = min(12, 2σ(poziom)), σ z kontrolowanych ramp (15.11) i kalibracji 29.10: w forte ±2–4 surowo, więc zmiana o 6+ to zamiar i przechodzi; w mezzo zostaje 12, więc akcenty zachowują wielkość.
2. Poziom frazy osobno dla każdej ręki (dwa liczniki na kanał; nuta idzie do licznika z bliższą ostatnią wysokością, inaczej tego w oktawie, inaczej poniżej / powyżej C4).
3. Mapa bez płaskiego sufitu powyżej surowego 110 (wyjście = max(v2, surowe)).

## Symulacja (v3sim.py, v3real.py, v3fig.py, moje-v3-symulacja.png)
Monte Carlo ze znanym zamiarem: 3 poziomy szumu ręki × 12 przebiegów × 150 fraz × 60 nut; plus gra 04–15.11 (85 158 nut, 1635 akordów obu rąk, rampy 15.11).

| | v2 | v3e | v3f (akcenty w całości) | v3a (próg 2σ) |
|---|---|---|---|---|
| błąd względem zamiaru (MC, szum ×1) | 0 | +1% | +13% | −12% |
| skok w forte dociera | 77% | 82% | 93% | 81% |
| akcenty (mediana velocity) | 41 | 41 | 51 | 26 |
| melodia nad akompaniamentem | 68% | 77% | 87% | 71% |
| nierówność powtórzeń | 9 | 10 | 10 | 10 |

v3a i v3-EB odrzucone: w mezzo zjadają akcenty. Wybrany v3e (Miki, 15.11): równość jak v2, lepsze forte i melodia.
Router odtwarza symulację co do nuty: 85 158 / 85 158 identycznych wyjść.
