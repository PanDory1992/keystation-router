# Plan: krzywe routera liczone w dB instrumentu (16.11.2026)

Stan: tylko plan i analiza. W routerze nic nie zmieniono, aktywne czucie to dalej `moje3`.

Dane:
- gra z 9-16.11 (notes W46-W47): 66 950 uderzeń;
- pomiary velocity -> dB dla 35 instrumentów (RAPORT-glosnosc-velocity.md);
- σ ręki z routera (V3_SIGMA_KNOTS).

Skrypty pomocnicze: plan-an2.py, plan-an3.py (w tym folderze; ścieżki danych są chmurowe, tak jak w poprzednich skryptach).

## 0. Analiza: skąd wychodzimy

### Twoja ręka
- **Surowe velocity białych:** mediana 100, p10 76, p90 111.
- **Udział „1”:** białe 1,9%, czarne 9,1%.
- **Ile poziomów ręka rozróżnia (2σ):**
  - w całym zakresie ok. 9,7;
  - w surowym 2-80 tylko 2,4;
  - w 80-119: 5,4;
  - w 119-127: 1,9.
- **W zwykłej grze** (p5-p95 = surowe 61-113) wychodzi ok. 4,9 poziomu.

### Obecne tryby przeliczone na dB
Mediana z C2 i C4, bez odszumiania, na trzech instrumentach odniesienia:

| Tryb | Pianoteq Shigeru p10 / p50 / p90 | zakres gry | szum ręki | Imperial: zakres gry | X Grand: zakres gry |
|---|---|---|---|---|---|
| Light | -31,5 / -24,3 / -19,0 | 12,6 dB | 1,3 dB | 13,3 dB | 7,9 dB |
| Acoustic | -33,2 / -26,6 / -21,3 | 11,9 dB | 1,5 dB | 13,9 dB | 7,3 dB |
| Heavy | -34,9 / -28,7 / -22,7 | 12,2 dB | 1,5 dB | 14,2 dB | 7,2 dB |
| Moje3 (sama mapa) | -34,4 / -23,1 / -16,7 | 17,7 dB | 2,2 dB | 19,0 dB | 10,3 dB |

„Zakres gry” to odległość między p10 a p90 twoich nut. Instrumenty mają zakres (v10-127): Pianoteq Shigeru 30 dB, Imperial 37 dB, X Grand 16 dB.

### Wnioski
1. **Żadna krzywa nie dodaje informacji.** Stosunek zakresu gry do szumu ręki wynosi ok. 4 w każdym trybie i na każdym instrumencie. Krzywa decyduje tylko o tym, gdzie w dB ląduje gra i jak szeroko się rozkłada. Informację dodaje tylko:
   - odszumianie (Moje v2: z 4,5 do 6,4 rozróżnialnych poziomów);
   - stopniowanie, czyli schodki.
2. **Light, Acoustic i Heavy różnią się w dB prawie wyłącznie przesunięciem.** Mediana jest niżej o ok. 2-4 dB na każdy krok, a zakres gry zostaje ten sam (12-14 dB). Działają jak pokrętło głośności, nie jak zmiana czucia.
3. **Twoja gra zajmuje 40-55% zakresu instrumentu.** Na Light 12-13 dB z 30-37, na Moje3 18-19 dB.
4. **Ta sama krzywa daje na różnych instrumentach inny wynik.** Moje3 rozkłada grę na 18 dB w Pianotequ i na 10 dB w X Grand. Do tego instrumenty różnią się poziomem nawet o 30 dB.

Dlatego wszystkie logiki warto przenieść ze skali „velocity” na skalę „dB aktywnego instrumentu”.

## 1. Wspólna budowa wszystkich wariantów

Każdy wariant ma trzy etapy.

### Etap 1. Wejście (ręka): surowe -> oczyszczone surowe
To, co już działa w Moje3:
- jedna skala dla białych i czarnych;
- „1” = stała średnia dziury (białe tuż pod podłogą);
- czarna „1” po głośnym akordzie = mieszanka;
- odszumianie z progiem zależnym od siły, osobny poziom frazy dla każdej ręki.

Odszumianie da się włączać i wyłączać osobno w każdym wariancie.

### Etap 2. Krzywa ręki: oczyszczone surowe -> poziom 0..1
0 to ppp, 1 to fff. **Tylko tutaj warianty się różnią.**

### Etap 3. Wyjście (instrument): poziom 0..1 -> dB -> velocity
- ppp = dB przy v10, fff = dB przy v127, plus wzmocnienie instrumentu.
- Velocity dobiera się przez odwrócenie krzywej instrumentu:
  - krzywa monotoniczna;
  - wartości dla wysokości nuty interpolowane między C2 i C4, poza nimi przytrzymane;
  - najniższa velocity, która daje żądane dB;
  - nigdy poniżej najmniejszej velocity, która w ogóle gra (Roland: v1 to cisza).
- Wąskie instrumenty: poziom 0..1 rozciąga się na ich własny zakres (w procentach zakresu), a nie na dB bezwzględne. Inaczej ppp i fff wypadłyby poza instrument.

### Nowe elementy
- **Profile instrumentów:** plik `velocity-profiles/<nazwa>.json`, generowany z velocity-db-C2-C4.csv i centroidów. Zawiera:
  - 127 wartości dB dla C2 i dla C4;
  - granice warstw barwy;
  - zakres użyteczny;
  - wzmocnienie, które wyrównuje v64 do wspólnego poziomu (mediana ok. -34 dB).
- **Wybór aktywnego instrumentu.** Router dziś nie wie, co gra w Studio One. Możliwości:
  - (a) pole `instrument` w router-options.json, zmieniane z wtyczki Keystation Status albo z szyny UDP (`set`): najprostsze, polecam na start;
  - (b) przycisk na klawiaturze, który przełącza ulubione instrumenty;
  - (c) automatycznie przez most Studio One (nazwa wtyczki na ścieżce „Ja”): najwygodniejsze, ale najbardziej kruche, więc na później.
- **Bez profilu tryb działa jak dziś** (skala velocity), więc nic się nie zepsuje. Moje3 zostaje jako punkt odniesienia.

## 2. Wariant A: logika Light / Acoustic w dB („równa rozróżnialność”)

**Logika oryginału:**
- każdy poziom, który ręka rozróżnia (2σ), dostaje tyle samo wyjścia;
- v2: 90% skumulowanego 1/σ plus 10% liniowo, kotwice ppp 10 ... fff;
- Acoustic i Heavy przesuwają twój rozkład w stronę pianistów MAESTRO (α 0,5 i 0,85).

**W dB:**
- poziom(r) = 0,9 · F_σ(r) + 0,1 · (r - 2) / 125, gdzie F_σ to skumulowane 1/(2σ) od surowego 2 do 127 (σ z V3_SIGMA_KNOTS);
- Light, Acoustic i Heavy stają się jawnym przesunięciem w dB, mierzonym na środku krzywej i malejącym do zera przy fff, tak żeby fff było zawsze osiągalne. Na przykład: Light 0, Acoustic -2,5 dB, Heavy -5 dB. Dziś jest to prawie dokładnie to samo, tylko ukryte w tabelach velocity.

**Pierwsza symulacja** (bez odszumiania):

| Instrument | p10 / p50 / p90 | zakres gry | szum ręki |
|---|---|---|---|
| Pianoteq Shigeru | -36 / -30 / -24 | 12 dB | 1,5 dB |
| Imperial | | 15 dB | 1,9 dB |
| X Grand | | 6,6 dB | 0,8 dB |

**Plusy:**
- jedna rozróżnialna zmiana ręki = tyle samo dB na każdym instrumencie;
- przewidywalny i łatwy do wytłumaczenia.

**Minusy:**
- zwykła gra zajmuje tylko ok. 40% zakresu, bo 55% wyjścia idzie na surowe 80-119;
- dół (surowe poniżej 80) dostaje mało, więc pp jest ciasne.

**Do decyzji:** czy zachować pochodzenie z MAESTRO, czy zamienić je na jedno pokrętło „ciężar” w dB.

## 3. Wariant B: logika Moje w dB („twój rozkład na cały instrument”)

**Logika Moje:**
- wyrównanie histogramu twojej gry (CLAHE, nachylenie najwyżej 2,5);
- odszumianie kontekstowe i osobny poziom dla każdej ręki;
- „1” z dziury;
- brak sufitu.

**W dB:**
- poziom(r) = CDF twoich surowych velocity po CLAHE, czyli każdy procent twoich nut dostaje równy kawałek dB instrumentu;
- wejście jak w Moje3.

**Pierwsza symulacja** (bez odszumiania, które zwykle zmniejsza szum o ok. 30%):

| Instrument | p10 / p50 / p90 | zakres gry | szum ręki |
|---|---|---|---|
| Pianoteq Shigeru | -35 / -25 / -18 | 18 dB | 2,2 dB |
| Imperial | | 22 dB | 2,8 dB |
| X Grand | | 9,6 dB | 1,2 dB |

**Plusy:**
- najszersza gra ze wszystkich wariantów, najbardziej „twoja”;
- akcenty i melodia zachowane tak jak w Moje3 (te same parametry).

**Minusy:**
- **Krzywa idzie za tym, jak grasz.** Jeśli przez tydzień ćwiczysz cicho, krzywa się przesunie. Trzeba ją zamrażać, czyli przeliczać rzadko (np. raz w miesiącu) i z wersją. Inaczej porównania tygodniowe w Trenerze tracą sens.
- Najbardziej wzmacnia szum ręki tam, gdzie grasz najczęściej (surowe 95-110).

**Do decyzji:** z jakiego okresu liczyć rozkład (proponuję od 4.11, po przebudowie mechaniki) i jak często go przeliczać.

## 4. Wariant C: Schodki

**Idea:** zamiast ciągłej krzywej jest K stałych poziomów, jak tarasy dynamiki w muzyce barokowej albo rejestry organów. Każde uderzenie trafia w jeden stopień, a w obrębie stopnia głośność jest stała.

### Ile stopni
Ręka w zwykłej grze rozróżnia ok. 5 poziomów. Przy pojedynczych, celowych uderzeniach rozróżnia ok. 10, ale prawie połowa z nich leży w ff i fff. Przy 11 stopniach sąsiednie stopnie wypadałyby więc w dużej mierze losowo.

Propozycja:
- 7 stopni (ppp ... ff) plus fff jako 8. dla instrumentów o zakresie co najmniej 30 dB;
- 5-6 stopni dla instrumentów wąskich i warstwowych;
- w symulacji porównać 7 z 11.

### Progi wejścia
Progi w skali surowej wynikają z równej rozróżnialności (F_σ, zakres 30-122).

Dla 7 stopni progi to: 70, 88, 98, 106, 112, 117. Twoje nuty rozkładają się tak:

| Stopień | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Udział nut | 8% | 14% | 22% | 30% | 18% | 7% | 1% |

Gra skupia się na stopniach 3-5.

### Histereza
Kolejna nuta tej samej ręki zostaje w poprzednim stopniu, chyba że przekroczy próg o więcej niż ½σ. Dzięki temu powtórzenia są równe co do dB i nie ma migotania na progu.

### Wyjście
- Stopnie rozłożone równo w dB od ppp do fff instrumentu. Na przykład 7 stopni na 30 dB daje 5 dB na stopień, co jest wyraźnie słyszalne także pod zespołem.
- Instrumenty warstwowe (AIR, Hammers and Waves, Sunroom, X Grand): stopień wypada w środku warstwy, a stopni jest tyle, ile warstw.

### Ocena
**Plusy:**
- powtórzenia równe (w obrębie stopnia brak nierówności);
- stała barwa w stopniu;
- czytelne celowanie: wiesz, który stopień trafiłeś.

**Minusy:**
- brak crescendo wewnątrz stopnia;
- akcent mniejszy niż odległość do progu znika;
- gra brzmi bardziej mechanicznie;
- nawet z histerezą na granicy zdarzy się skok o cały stopień.

**Najlepsze zastosowanie:** ćwiczenie kontroli dynamiki (test celowania) i akompaniament do śpiewu, gdzie liczy się stały poziom.

## 5. Wariant D (nowy): Tarasy z oddechem, czyli poziom frazy plus akcent

**Idea:** każdą nutę rozkładam na dwie części:
- wolną: poziom frazy ręki, licznik z Moje3;
- szybką: odchylenie tej nuty od poziomu (akcent, głos melodii, szum).

**Jak działa:**
- Wolna część trafia na schodki (jak w C, z histerezą). Poziom frazy jest więc stały i czytelny: p, mf, f.
- Szybka część przechodzi w dB z odszumianiem:
  - małe odchylenia (szum ręki do 2σ) są ściągane do zera;
  - większe (akcent, melodia) zostają, najwyżej o ±1 stopień.
- Crescendo słychać, bo poziom frazy wchodzi kolejno na następne stopnie, taras po tarasie, ale bez drżenia.

**Plusy:** równość schodków razem z akcentami i melodią z Moje. To najbliżej tego, jak myśli pianista: dynamika z nut plus akcenty.

**Minusy:**
- najtrudniejszy do strojenia (dwa progi);
- zmiana poziomu frazy przychodzi z opóźnieniem 1-2 nut, bo poziom to średnia;
- trzeba go sprawdzić w symulacji ze znanym zamiarem.

## 6. Wariant E (najmniejszy krok): Moje3 brzmiące wszędzie jak na Pianotequ

To nie jest nowa krzywa, tylko etap 3 dołożony do obecnego Moje3:
- velocity z Moje3 -> dB Pianoteqa Shigeru (twoja skala odniesienia);
- -> odwrócenie krzywej aktywnego instrumentu.

Każdy instrument odpowiada wtedy na dotyk głośnością tak jak Pianoteq, a barwa zostaje jego własna. To jest najmniejsza zmiana i od razu porządkuje wszystkie instrumenty. Nadaje się na pierwszy etap, zanim wybierzesz A-D.

## 7. Jak to sprawdzimy, zanim coś trafi do routera

1. **Symulacja na grze 4-16.11** (W45-W47, ok. 90 tys. nut), 5 instrumentów: Pianoteq Shigeru, Imperial, Estate, AIR C7, X Grand. Metryki w dB:
   - zakres frazy;
   - nierówność powtórzeń;
   - liczba rozróżnialnych poziomów;
   - melodia nad akompaniamentem;
   - akcenty;
   - dla C i D dodatkowo: jak często powtórzenie trafia w ten sam stopień i ile jest przeskoków na granicy.
2. **Monte Carlo ze znanym zamiarem** (jak v3sim.py):
   - błąd względem zamiaru;
   - czy skok w forte dociera;
   - czy crescendo przechodzi.
3. **Odsłuch na ślepo:** ta sama nagrana fraza (surowe dane z notes) przepuszczona przez A-E i wyrenderowana w Studio One na 2 instrumentach. Wybierasz bez znajomości nazw.
4. **Dopiero potem router:**
   - nowe tryby w cyklu C53;
   - profile instrumentów;
   - testy w test_pedal_router.py;
   - wdrożenie ze sprawdzeniem md5 i commitem;
   - stare tryby zostają.

## 8. Kolejność (propozycja)

1. Profile instrumentów, wybór instrumentu i wyrównanie poziomu (wzmocnienie przy v64). Bez zmiany krzywych.
2. Wariant E: Moje3 -> dB odniesienia -> instrument.
3. Symulacje A, B, C i D w jednym raporcie z jedną tabelą.
4. Odsłuch na ślepo i wybór 1-2 wariantów do routera.

## 9. Decyzje dla Ciebie

- Jak router ma się dowiadywać o instrumencie: ręcznie (wtyczka lub szyna), przyciskiem czy automatycznie przez most?
- Ile stopni w Schodkach: 7 (+fff) jak wynika z danych, czy 11, jak planowaliśmy (do porównania w symulacji)?
- Czy Light, Acoustic i Heavy mają w nowej wersji zostać jawnym przesunięciem w dB, skoro dziś w praktyce tym właśnie są?
- Z jakiego okresu liczyć rozkład dla Moje w dB i jak często go przeliczać?

## 10. Ograniczenia

- Krzywe instrumentów znamy tylko dla C2 i C4. Dla wysokich rejestrów warto dołożyć pomiar C6.
- σ ręki pochodzi z ramp i kalibracji, a nie z każdego klawisza osobno.
- Liczby w tym planie to pierwsze przybliżenia: liczone bez odszumiania i na średniej z C2 i C4.
- Poziom wyjścia instrumentów zależy od ich pokręteł Volume. Wzmocnienie w profilu trzeba poprawić po każdej zmianie presetu.
