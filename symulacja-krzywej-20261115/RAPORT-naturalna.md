# Naturalna i Szeroka: dwie ostatnie krzywe dynamiki (16.11.2026)

Router: przycisk C53 przełącza teraz tylko **Naturalna ↔ Szeroka**. Domyślna jest Naturalna. Starsze czucia (Moje 3, Moje, Light, Acoustic, Heavy) nadal da się wybrać z panelu sterowania. Wtyczka Keystation Status 0.9.0 zna nowe nazwy.

Dane: Twoja gra od 4.11 (po przebudowie mechaniki), W45-W47, 93 310 uderzeń.

## 1. Zasada: głośność idzie za logarytmem prędkości klawisza

**Jak mierzy czujnik.** Keystation mierzy czas między dwoma stykami gumki: surowe velocity = K - t/τ. Sprawdziłem to na rozrzucie ręki przy stałym zamiarze (rampy 15.11 i kalibracja). Powyżej surowego 85 rozrzut maleje liniowo ku górze: σ = 12% × (131,7 - surowe). Wniosek: ręka trzyma stały procent prędkości (ok. 12%), a czujnik jest liniowy w czasie. Stąd:
- prędkość klawisza ~ 1/(131,7 - surowe);
- logarytm prędkości = -ln(131,7 - surowe).

**Dlaczego logarytm.** W fortepianie głośność w dB rośnie z logarytmem prędkości młotka. Dlatego krzywa jest liniowa w log-prędkości. Daje to dwie rzeczy naraz:
- każdy krok wyjścia odpowiada tej samej różnicy, którą ręka potrafi zrobić celowo (stały procent prędkości);
- strefa surowe 2-40, w której nie ma informacji (rozrzut ręki 15-20 surowych), dostaje mało miejsca, bo fizycznie to tylko ok. 3 dB prędkości klawisza.

**Kształt S.** Filcowy młotek jest najczulszy w środku dynamiki, a na krańcach łagodnieje: przy ppp młotek ledwo dochodzi do struny, przy fff filc twardnieje. Krzywa ma więc kształt S wokół surowego 100 (Twoja mediana):
- nachylenie w środku: g razy (Naturalna 1,7, Szeroka 1,9);
- nachylenie na krańcach: 2-g;
- krzywa jest zawsze monotoniczna.

**Kotwice:**
- surowe 2 = 10 (ppp);
- surowe 118 (Naturalna) albo 117 (Szeroka) = 127 (fff). To Twój percentyl 99, stały we wszystkich trzech tygodniach.

## 2. Czarne klawisze

- **Jedna skala dla obu kolorów.** W tym samym akordzie czarny czyta tylko -0,7 surowego względem białego, więc obie krzywe są wspólne.
- **Czarna „1”** (klawisz wolniejszy niż próg czujnika, czyli 8,9% czarnych uderzeń) dostaje wartość oczekiwaną nuty w dziurze: średnie wyjście białych nut z surowym do 40, z ich „1” na podłodze.
  - Naturalna: 12, a najcichszy zmierzony czarny to 19.
  - Szeroka: 11 i 16.
  - Różnica ok. 1,5-2 dB na typowym instrumencie, w Moje 3 było 2,4 dB.
  - Kontekst frazy nie niesie tu informacji (RAPORT-jedynki, RAPORT-entropia), więc stała jest najlepszym możliwym wyborem.
- **Czarna „1” zaraz po głośnym akordzie** to w 60% błąd odczytu. Wynik = 0,6 × akord + 0,4 × dziura (jak w Moje 3).
- **Biała „1”** dostaje 9, tuż pod podłogą.

## 3. Wejście bez zmian: wszystko, co działało w Moje 3

- Odszumianie z progiem zależnym od siły: min(12, 2σ).
- Osobny poziom frazy dla każdej ręki.
- Akcenty powyżej progu przechodzą.

Router odtwarza symulację co do nuty: 93 310 z 93 310 identycznych wyjść dla obu krzywych.

## 4. Wyniki na Twojej grze

Wyjście velocity:

| | p1 | p5 | p50 | p95 | p99 | 127 osiągane | zakres frazy | szum akordu | rozróżnialne poziomy | nierówność powtórzeń | akcent | czarne / białe (mediana) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Light | | 35 | 79 | 111 | | | 59,6 | 10 | 5,4 | 10 | 36 | 75 / 80 |
| Acoustic | | 32 | 68 | 101 | | | 55,2 | 10 | 5,0 | 10 | 31 | 63 / 70 |
| Moje 3 | 19 | 30 | 83 | 115 | 122 | nigdy (0,0%) | 75,5 | 9 | 7,6 | 9 | 41 | 75 / 83 |
| **Naturalna** | **16** | 30 | 81 | 116 | 124 | 0,3% | **75,3** | 9 | 7,6 | 9 | 38 | 73 / 81 |
| **Szeroka** | **14** | 27 | 83 | 120 | 126 | 0,7% | **81,6** | 9 | 8,2 | 10 | 42 | 74 / 83 |

Wyniki Monte Carlo ze znanym zamiarem (8 przebiegów):

| | błąd względem zamiaru (% zakresu v45-115) | skok dynamiki dociera | w tym w forte |
|---|---|---|---|
| Moje 3 | 10,2% | 79% | 82% |
| Naturalna | 10,1% | 79% | 81% |
| Szeroka | 10,2% | 78% | 81% |

### Co z tego wynika
- **Naturalna nie zawęża niczego względem Moje 3.** Zakres frazy jest ten sam, ppp schodzi niżej (p1 16 zamiast 19), a fff dochodzi do 127 (w Moje 3 nigdy). Równość jest taka sama.
- **Szeroka daje o 8% więcej zakresu frazy** i jeszcze cichsze ppp. Kosztem jest odrobinę mniej równe powtarzanie (10 zamiast 9).
- **Obie są szersze i równiejsze niż Light i Acoustic.**
- **Liczba rozróżnialnych poziomów (ok. 7,5-8) to granica ręki i czujnika, nie krzywej.** Żadna krzywa nie wytworzy informacji, której czujnik nie zmierzył. Krzywa decyduje tylko o tym, gdzie ta informacja ląduje.

## 5. Odkrycie po drodze

Moje 3 (wyrównanie histogramu Twojej gry) wyszło prawie dokładnie tą samą krzywą co fizyka: przy surowym 80 / 90 / 100 / 110 daje 43 / 60 / 85 / 110, a Naturalna 46 / 61 / 83 / 111. Twoje dane same znalazły kształt fizyczny. Naturalna ma ten kształt z zasady, a nie z histogramu. Dlatego nie zmieni się, gdy przez tydzień zagrasz inny repertuar. Do tego naprawia krańce: 127 jest osiągalne, a ppp niższe.

## 6. Stabilność („za miesiąc”)

- Krzywa nie uczy się w trakcie gry, więc nie ma niespodzianek.
- Parametry pochodzą z fizyki czujnika i z Twoich krańców. Te były identyczne w każdym tygodniu:

| Tydzień | mediana surowa | p99 surowe | dziura (Naturalna) |
|---|---|---|---|
| W45 | 100 | 118 | 15 |
| W46 | 100 | 117 | 14 |
| W47 | 101 | 118 | 14 |

- Wartość dziury w mapie liczona jest na wszystkich danych.
- Jeśli kiedyś będziesz grał mocniej, góra po prostu częściej dojdzie do 127. Jeśli ciszej, krzywa dalej działa: jest monotoniczna i pokrywa całą skalę.
- Przeliczenia wymagałaby dopiero wymiana gumek stykowych albo zmiana krzywej w samej klawiaturze (C1).

## 7. Co sprawdziłem i odrzuciłem

- **Poprawka dla każdego klawisza osobno.** Odchylenia klawiszy są stabilne (korelacja 0,93 między dniami), ale zależą od nazwy dźwięku w każdej oktawie: H stale ok. 5 surowych ciszej, G i A głośniej. Tego nie da się rozdzielić na mechanikę i muzykę (repertuar, palcowanie). Część czysto indywidualna to tylko ok. 1,9 surowego. Odrzucone, bo mogłoby zabrać zamierzone akcenty.
- **11 schodków.** Ręka w zwykłej grze rozróżnia ok. 5 poziomów, przy celowych uderzeniach ok. 10, więc 11 stopni wypadałoby w dużej mierze losowo. Ciągła krzywa z odszumianiem daje więcej.
- **Krzywa dopasowana do konkretnego instrumentu.** Odrzucona na Twoje życzenie (ma być uniwersalnie). Typowy instrument ma ok. 0,3 dB na krok velocity, więc liniowe velocity = liniowe dB, a to jest właśnie założenie tej krzywej.

## 8. Pliki

- `velocity-map.naturalna.json`, `velocity-map.szeroka.json` (z parametrami K, lo, hi, g, pivot, floor).
- `pedal_router.py`: TOUCH_CYCLE, DENOISE3_MODES, CENSORED_ONE_MODES, DEFAULT_TOUCH = naturalna. Kopia poprzedniej wersji: `pedal_router.before-naturalna-20261116.py`.
- `test_pedal_router.py`: 4 nowe testy (59 razem, wszystkie przechodzą).
- `panel_sterowania.py`: nowe czucia na początku listy.
- `KeystationStatus-0.9.0`: nazwy NATURALNA / SZEROKA, przycisk w okienku przełącza te dwie. Instalacja: zamknij Studio One i uruchom „Zainstaluj Keystation Status.bat”.
- Skrypty w podfolderze `naturalna/` (korzystają też z sim.py, v3sim.py i cens.py z tego folderu):
  - `curves.py`: krzywa;
  - `data.py`;
  - `sim2.py`: porównanie;
  - `sweep.py`: przegląd parametrów;
  - `mc2.py`: Monte Carlo;
  - `perkey2.py`: klawisze;
  - `router_check.py`: zgodność z routerem.

## 9. Dodatek: Naturalna los. (16.11, na prośbę Mikiego)

Czucie `naturalna-los` ma tę samą krzywą i to samo wejście co Naturalna. Różni się tylko jedynkami: zamiast stałej wartości router losuje ją z wąskiego zakresu.

- **Biała „1”:** losowo 8-10, średnio 9.
- **Samotna czarna „1”:** losowo 10-14, średnio 12.
- **Czarna „1” po głośnym akordzie:** bez zmian, działa reguła akordu (to błąd odczytu, nie cicha nuta).

Średnie są takie same jak w Naturalnej, a zmienność wynosi ok. ±0,5 dB.

Sprawdzone na 93 310 nutach:
- różnią się wyłącznie jedynki (1935 nut);
- średnie: białe 9,02, czarne 12,00.

C53 przełącza teraz: Naturalna -> Szeroka -> Naturalna los. -> Naturalna.

Wtyczka Keystation Status 0.9.0 pokazuje nazwę NATURALNA LOS, a przy „1” napis LOSOWO.

Opinia z analizy: różnica jest prawie niesłyszalna, a to kwestia gustu, nie poprawności. Domyślna zostaje Naturalna.
