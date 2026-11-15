# Brakujące velocity: „1” i dziura czarnych klawiszy (15.11.2026)

Dane: 4–15.11 (po przebudowie klawiatury). Prawda: białe klawisze mierzą 2–127, więc białe nuty poniżej progu c zostały sztucznie „zakryte” (jak dziura czarnych), a metody próbowały je odtworzyć. Uczenie na pierwszej połowie okresu, test na drugiej. Progi c = 25, 41, 50.

Wyniki (c = 41, 1002 nuty testowe, błąd na wyjściu krzywej Light białych):

| Metoda | Śr. błąd | Odchylenie | Głośniej niż próg |
|---|---|---|---|
| Dziś: poziom frazy −16, sufit 45 | 18,1 | +16,0 | 82% |
| Zawsze ppp | 10,4 | −10,4 | 0% |
| Fizyka (gęstość 1/v²) | 7,4 | −7,4 | 0% |
| Środek dziury | 3,3 | −1,4 | 0% |
| Tobit z kontekstem frazy | 3,0 | +1,4 | 0% |
| Uczenie maszynowe (GBM, 6 cech) | 3,0 | +0,3 | 0% |
| Stała: średnia dziury | 2,9 | +0,6 | 0% |

Ten sam porządek przy c = 25 i c = 50.

1. Dzisiejsza reguła jest najgorsza: zakryte nuty grają średnio o 16 velocity za głośno, 4 na 5 głośniej niż najcichsza zmierzona.
2. Kontekst nie mówi, gdzie w dziurze leży nuta: R² ≈ 0 dla Tobita i uczenia (rozrzut prawdy 10,8 surowych jednostek). Najlepsza jest stała: średnia dziury ≈ 28 surowych → 20 na wyjściu. Tak samo przy krzywej z rozciągniętym dołem.
3. Teoria fizyczna (równy rozkład czasu przelotu klawisza) przegrywa z danymi: ciche nuty skupiają się tuż pod progiem, nie przy zerze.
4. Wyjątek: czarna „1” w głośnym akordzie. Białe zmierzone nuty tylko w 0,7% przypadków są ciche w głośnym akordzie, czarne „1” w 4,0%: większość z nich to raczej błąd odczytu niż ciche palce. Tu kontekst akordu ma sens (gdy koledzy zabrzmieli wcześniej).
5. Czarne powyżej dziury mają prawie ten sam rozkład co białe (mediana 97 vs 100), a krzywa Light czarnych zaniża je (41 → 15 wobec 25, mediana wyjścia 75 wobec 80). Dopasowanie kwantyli czarne→białe + krzywa białych wyrównuje kolory (mediana 81 vs 80).

Propozycja: czarna i biała „1” poza głośnym akordem → stała średnia dziury (wyjście ~20); czarna „1” po głośnym akordzie → 0,6·poziom akordu + 0,4·średnia dziury; czarne ≥ 41 → dopasowanie kwantyli do białych i krzywa białych. Dotyczy też trybu „Moje” (jego czarna krzywa ma ten sam błąd).

Skrypty: cens.py, study.py, study2.py.
