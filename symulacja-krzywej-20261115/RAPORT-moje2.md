# Moje v2 (15.11.2026): jedna krzywa, fizycznie spójna

Dane: surowe velocity z Keystation, 04–15.11 (po przebudowie mechaniki). Walidacja: dopasowanie na pierwszej połowie, ocena na drugiej.

## Co sprawdziłem jeszcze raz i co z tego wyszło
1. **Czujnik czarnych = czujnik białych.** W tym samym akordzie (oba ≥ 41) czarny czyta −0,7 raw względem białego. Jedna skala, więc jedna krzywa dla obu kolorów. Wcześniejszy pomysł „mapowania kwantyli czarne → białe” był błędem: wyrównałby też to, że czarne gram realnie trochę ciszej (mediana 97 vs 100 raw).
2. **Czarne „1” to ciche nuty, nie losowe błędy.** Sąsiedzi czarnych „1” mają medianę 84 raw, tak jak prawdziwie ciche białe (85–89); zwykłe czarne mają 98. Dopasowanie mieszanki: 0% losowych błędów.
3. **Dziura czarnych jest głębsza niż białych:** 7,2% czarnych nut to „1”, białych ≤ 41 jest 3,8%. Szacunek wartości dziury (średnia wyjścia białych ≤ 41, z „1” na podłodze) = 14 jest więc raczej górnym.
4. **Wyjątek: zaraz po głośnym akordzie** (nuty w ciągu 30 ms przed, mediana ≥ 80) czarne w dziurze to 4,4% zamiast oczekiwanych 1,7%, więc P(błąd odczytu) = 0,6. Wtedy wynik = 0,6 · akord + 0,4 · dziura (wartość oczekiwana).
5. **Białe „1”** = wolniej niż raw 2, czyli tuż pod podłogą (9). Kontekst potwierdza: to ciche nuty.

## Reguły (router, czucie „moje”)
- krzywa: CLAHE (nachylenie ≤ 2,5) zmierzonych nut, wspólna; 127 → 127; monotoniczna;
- odszumianie kontekstowe (k 0,35, τ 12, α 0,3, przerwa 1,5 s); zmierzony czarny zostaje ≥ 41;
- „1”: białe 9, czarne 14, czarne po głośnym akordzie mieszanka; reguła frazy dla „1” nieużywana w tym trybie.

## Wynik (druga połowa danych)
| | Light | Moje v2 |
|---|---|---|
| zakres frazy | 55 | 71 |
| nierówność powtórzeń | 11 | 10 |
| rozróżnialne poziomy | 4,5 | 6,4 |
| głos melodii / akcenty | 26 / 34 | 28 / 34 |
| mediana czarne / białe | 75 / 80 | 73 / 81 |
| „1” czarne / białe | 10 / 10 | 14 / 9 |

Odtworzenie w prawdziwym routerze (tydzień 46): czarne 75, białe 83, „1” 9 / 14, czarne „1” po głośnym akordzie: 5%.
Skrypty: natural2.py, validate2.py, check3.py.
