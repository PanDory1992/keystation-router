# Velocity -> głośność: Pianoteq i Kawai EX (16.11.2026)

Metoda: ścieżka testowa, nuta C2 (MIDI 48) co 0,5 s, velocity 1-127; render ścieżki (bounce) w Studio One, na kanale tylko Keystation Status. Na nutę: szczyt (0-0,45 s) i RMS ataku (0-0,3 s). Dane: velocity-db-C2.csv.

## Pianoteq (ustawienia jak przy graniu)
- v1-2 ok. -58 dB szczytu (prawie cisza), v3 -46, v9 -38, v14 -36, v127 -1.
- Użyteczny zakres ok. 45 dB (v3-127). Powyżej v10 prawie liniowo: ok. 0,3 dB na krok velocity. v2-10 stromo (2,7 dB/krok).
- Router dziś zaczyna od 9: ok. 8 dB pianissimo (v3-8) nieużywane.

## Kawai EX (UVI)
- Round robin: kolejne uderzenia tej samej nuty i velocity biorą 4 różne próbki, różnica ok. ±1,5 dB (do ok. 4 dB między skrajnymi). Krzywą liczono po wygładzeniu co 4.
- Zakres ok. 36 dB (v3-124), bardzo nierówny: v3-10 ok. 12 dB, v10-90 ok. 20 dB, v90-124 tylko ok. 5 dB.
- Na górze dynamikę niesie barwa: środek ciężkości widma rośnie z 742 Hz (v60) do 1338 Hz (v124), głośność prawie nie.

## Wnioski do krzywej schodkowej
- Równe schodki w dB dla Pianoteqa = prawie równe schodki velocity.
- Dla Kawai te same velocity dają nierówne kroki: na dole duże, na górze 1-2 dB (słychać głównie jako jaśniejszą barwę).
- Kawai sam z siebie zmienia głośność powtórzeń o ok. ±1,5 dB (realizm próbek): to poniżej sensownego kroku schodka (3-4 dB).
- Pomiar jednej nuty (C2); inne rejestry mogą się różnić.

## Dodane: C4 (MIDI 72) i jednolite liczenie (16.11, później)
Pianoteq bez wygładzania (round robin ±0,2–0,4 dB), Kawai wygładzony oknem 4 sąsiednich velocity od v5 (bez v1–2). RMS ataku, dB. Dane: velocity-db-C2-C4.csv.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Pianoteq C2 | -52.9 | -49.0 | -40.8 | -31.7 | -23.4 | -15.1 | 3.9 | 17.3 | 8.3 | 8.3 | 37.9 |
| Pianoteq C4 | -51.9 | -47.5 | -40.1 | -32.5 | -23.6 | -15.3 | 4.4 | 15.0 | 8.9 | 8.2 | 36.6 |
| Kawai C2 | -54.9 | -49.2 | -43.2 | -34.8 | -29.4 | -24.7 | 5.7 | 14.4 | 5.4 | 4.7 | 30.2 |
| Kawai C4 | -60.8 | -50.7 | -44.3 | -35.1 | -30.0 | -25.1 | 10.1 | 15.7 | 5.0 | 4.9 | 35.7 |

- Pianoteq: oba rejestry prawie identyczne (różnica < 1,5 dB w każdym punkcie); od v10 do v124 równo ok. 0,29 dB na krok velocity.
- Kawai: od v10 do v124 ok. 25,5 dB w obu rejestrach, płaska góra (ok. 5 dB od v90); różni się tylko najcichszy skraj (v5-10).
- Poprawka do wcześniejszej sekcji: tam zakres Kawai liczony od v3 z wygładzaniem mieszającym v1-2, stąd zawyżony.

## Ulubiony fortepian Mikiego w Pianotequ: Shigeru Kawai (C2 i C4)
| | v3 | v10 | v30 | v60 | v90 | v127 | 3-10 | 10-60 | 60-90 | 90-127 | 3-127 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ulubiony C2 | -53.8 | -44.9 | -37.3 | -29.3 | -23.0 | -15.0 | 8.9 | 15.6 | 6.3 | 8.0 | 38.8 |
| Ulubiony C4 | -52.2 | -43.3 | -35.8 | -28.0 | -20.7 | -13.1 | 8.9 | 15.3 | 7.3 | 7.6 | 39.1 |
| Pierwszy preset C2 | -59.1 | -49.0 | -40.8 | -31.7 | -23.4 | -14.6 | 10.2 | 17.3 | 8.3 | 8.8 | 44.6 |
| Pierwszy preset C4 | -57.6 | -47.5 | -40.1 | -32.5 | -23.6 | -14.9 | 10.1 | 15.0 | 8.9 | 8.7 | 42.7 |

- Zakres ok. 39 dB (o ok. 5 dB węższy niż pierwszy preset): pianissimo ok. 5 dB głośniejsze, góra taka sama.
- C2 i C4 prawie równoległe (C4 ok. 1,5-2 dB głośniej), kształt prawie liniowy w dB: jedna krzywa na całą klawiaturę.
- Round robin ±0,2 dB (model, nie próbki).

## NOIRE Pure (Kontakt), C2 i C4
| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOIRE C2 | -60.7 | -57.8 | -50.2 | -41.7 | -33.7 | -25.2 | 2.9 | 16.1 | 8.0 | 8.5 | 35.5 |
| NOIRE C4 | -63.9 | -61.8 | -54.8 | -45.4 | -37.1 | -28.6 | 2.1 | 16.3 | 8.4 | 8.5 | 35.3 |

- Kształt od v10 jak Pianoteq: prawie liniowo w dB (ok. 0,3 dB na krok). Dół płaski: v1-10 brzmi prawie tak samo (ok. 3 dB różnicy), v1 nie jest ciszą.
- Rejestry równoległe, różnice między powtórzeniami ±0,2 dB.
- Wniosek: dwie rodziny krzywych. Pianoteq (oba presety) i NOIRE: równo od v10 do góry. Kawai EX: płaska góra (ok. 5 dB od v90).

## Claire (Kontakt), C2 i C4
Bez wygładzania (powtórzenia ±0,1–0,5 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Claire C2 | -67.0 | -62.0 | -62.2 | -51.9 | -42.0 | -33.2 | 5.1 | 10.1 | 9.8 | 8.8 | 33.8 |
| Claire C4 | -66.5 | -64.7 | -58.8 | -50.2 | -41.2 | -33.7 | 1.8 | 14.6 | 9.0 | 7.5 | 32.8 |

- C4: gładko i prawie liniowo w dB (ok. 0,28 dB na krok od v8), zakres ok. 33 dB. Rodzina Pianoteq/NOIRE.
- C2: szwy między warstwami próbek. v8 skacze o +5 dB, a v29 jest o 4,6 dB **ciszej** niż v28 (także v60 o 2 dB ciszej niż v59, v76 o 1,6 dB ciszej niż v75). Od v8 do v35 głośność stoi w miejscu (-62 do -58 dB), zmienia się tylko barwa. W basie Claire mocniejsze uderzenie w miękkiej strefie potrafi dać cichszy dźwięk: to wygląda jak losowość klawiatury, a jest instrumentem.
- Całość ok. 18 dB ciszej niż Pianoteq przy tym samym velocity (v127: -32 dB wobec -15 dB). Poziom wyrównuje suwak, zakres się nie zmienia.
- v1 jest odrobinę głośniejsze niż v2-3 (ok. 1 dB) w obu rejestrach.

## Grandeur (Kontakt), C2 i C4
Bez wygładzania (powtórzenia ±0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Grandeur C2 | -52.4 | -50.8 | -44.4 | -36.6 | -31.4 | -21.8 | 1.6 | 14.2 | 5.3 | 9.5 | 30.6 |
| Grandeur C4 | -58.2 | -51.9 | -43.2 | -36.9 | -28.8 | -21.3 | 6.3 | 15.0 | 8.1 | 7.6 | 36.9 |

- Ogólnie rodzina Pianoteq/NOIRE: od v10 rośnie prawie równo (ok. 0,3 dB na krok), góra nie jest płaska. Zakres ok. 33 dB w C2 i ok. 39 dB w C4.
- Płaska półka w środku, w obu rejestrach: od v40 do v61 głośność rośnie tylko o 2-4 dB (2-4 razy wolniej niż poniżej i powyżej), a v52 jest o 1,3-2,1 dB ciszej niż v51. Mniejsze odwrócenia także przy v68 i v89 (C2) oraz v44 i v60 (C4), po ok. 1-2 dB.
- Dół w C4: skok +3,2 dB między v9 i v10 (inna warstwa próbek), w C2 dół łagodny.
- Poziom: v127 ok. -20 dB, czyli ok. 5 dB ciszej niż Pianoteq i ok. 4 dB głośniej niż NOIRE.

## Keyscape Yamaha C7, C2 i C4
Bez wygładzania (powtórzenia ±0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Keyscape C2 | -59.7 | -59.4 | -51.7 | -44.1 | -38.5 | -29.2 | 0.3 | 15.3 | 5.6 | 9.3 | 30.5 |
| Keyscape C4 | -57.1 | -56.9 | -49.9 | -39.6 | -33.1 | -24.5 | 0.2 | 17.3 | 6.5 | 8.7 | 32.7 |

- Dół to gotowe schodki samego instrumentu: warstwy v1-12, v13-21, v22-30, v31-37, w środku każdej głośność stoi (rozrzut 0,5-1,3 dB), a między nimi skoki 1,6-4 dB. Tak samo w obu rejestrach.
- Od v38 w górę rośnie płynnie, ok. 0,2-0,3 dB na krok. Góra nie jest płaska.
- v1-12 brzmi tak samo (ok. -60 dB w C2, -57 dB w C4), a jest wyraźnie jaśniejsze niż v13-40 (1500-2100 Hz wobec 600-1300 Hz): w najcichszej warstwie słychać pewnie głównie mechanikę i szum, mniej tonu.
- Zakres od v12 do v127 ok. 33 dB w obu rejestrach. Poziom v127 ok. -24 do -28 dB (jak NOIRE).
- Wniosek do schodków: dla Keyscape progi routera muszą trafiać w warstwy instrumentu (13, 22, 31, 38), inaczej dwa schodki w różnych miejscach dają albo dwa progi o tej samej głośności, albo zbyt duży skok.

## Pianoverse Bösendorfer V280 Black Diamond, C2 i C4
Bez wygładzania (powtórzenia ±0,5-0,7 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Bösendorfer C2 | -51.4 | -43.1 | -36.0 | -30.0 | -23.7 | -17.2 | 8.3 | 13.2 | 6.2 | 6.6 | 34.3 |
| Bösendorfer C4 | -58.2 | -47.0 | -39.0 | -29.9 | -23.2 | -16.2 | 11.2 | 17.1 | 6.7 | 7.0 | 42.0 |

- Urwisko między v8 i v9: +7 dB w C2, +12 dB w C4. v1-8 to osobna, bardzo cicha warstwa (ok. -52 dB w C2, -60 dB w C4), w której głośność stoi.
- Drugi skok przy v17 (ok. +3 dB). Od v17 w górę gładko: ok. 0,3 dB na krok do v60, potem ok. 0,2 dB na krok. Góra nie jest płaska, tylko łagodniejsza.
- Zakres od v9 do v127: ok. 27 dB w C2 i 32 dB w C4; razem z cichą warstwą v1-8 ok. 36 i 44 dB.
- Poziom v127 ok. -16 dB, prawie jak Pianoteq.
- Wniosek: najlżejsze uderzenia leżą tu na krawędzi urwiska. Różnica jednej wartości (v8 albo v9) to 7-12 dB, czyli więcej niż trzy schodki.

## Ravenscroft 275, C2 i C4
Bez wygładzania (powtórzenia ±0,3-0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ravenscroft C2 | -51.6 | -45.6 | -34.4 | -27.7 | -24.1 | -20.1 | 6.0 | 17.9 | 3.5 | 4.0 | 31.5 |
| Ravenscroft C4 | -50.9 | -40.9 | -27.9 | -22.4 | -19.0 | -15.0 | 10.1 | 18.5 | 3.4 | 4.0 | 35.9 |

- v1-2 to prawie cisza: ok. 16-25 dB ciszej niż v3 (RMS -81 dB w C2, -70 dB w C4). Grają dopiero od v3.
- Stromy dół i płaska góra (mocniej niż Kawai EX): od v3 do v40 ok. 26-32 dB, a od v40 do v127 tylko ok. 13 dB. Między v60 i v90 tylko ok. 3,5 dB (0,12 dB na krok); mocniejsze granie słychać głównie jako jaśniejszą barwę.
- Skoki: v19 (+4-5 dB) i v127 (+2 dB wobec v126).
- Zakres v3-127 ok. 39-44 dB, poziom v127 ok. -13 do -18 dB (głośny, jak Pianoteq).
- Wniosek do schodków: przy równych krokach w dB ok. 2/3 wartości wysyłanych przez router wypadnie poniżej v40. Bez schodków ta strefa (0,5 dB na krok) wzmacnia każdą niepewność ręki; schodki ją od ręki odcinają, więc tu dają najwięcej. Świadoma "jedynka" (v1) jest na Ravenscrofcie prawie niesłyszalna: w schodkach trzeba jej dać co najmniej v3.

## UVI C7 Grand, C2 i C4
Bez wygładzania (powtórzenia ±0,2-0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UVI C7 C2 | -37.4 | -37.1 | -30.1 | -22.7 | -16.6 | -12.0 | 0.3 | 14.3 | 6.1 | 4.6 | 25.4 |
| UVI C7 C4 | -38.5 | -39.2 | -29.4 | -22.2 | -18.0 | -13.8 | -0.6 | 17.0 | 4.2 | 4.2 | 24.8 |

- Najwęższy zakres ze wszystkich: v1-127 ok. 31-33 dB, v5-124 ok. 25 dB. Najcichsze v1 jest już dość głośne (ok. 31 dB pod v127, tyle co v17 w Pianotequ).
- Dół v1-12 prawie płaski (ok. 3-5 dB, z małym dołkiem przy v7 w C2 i v9 w C4). Od v10 gładko: ok. 0,35 dB na krok do v40, potem coraz łagodniej (ok. 0,13 dB na krok powyżej v90).
- Od v10 w górę prawie bez odwróceń (tylko v36 i v66 w C4, po ok. 1,5 dB). Bardzo powtarzalny.
- Poziom v127 ok. -12 do -13 dB: najgłośniejszy ze zmierzonych.
- Poprawka do wcześniejszego wniosku: nie wszystkie instrumenty z próbek mają szwy; UVI C7 od v10 jest prawie tak czysty jak Pianoteq.

## VI Labs Modern U (pianino), C2 i C4
Bez wygładzania (powtórzenia ±0,2 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Modern U C2 | -59.8 | -52.8 | -41.7 | -34.2 | -27.9 | -19.7 | 7.0 | 18.6 | 6.3 | 8.2 | 40.1 |
| Modern U C4 | -66.5 | -55.0 | -41.2 | -32.8 | -26.4 | -18.6 | 11.5 | 22.2 | 6.4 | 7.8 | 47.9 |

- Najszerszy zakres ze wszystkich: v1-127 ok. 47 dB w C2 i 55 dB w C4.
- Od v10 w górę bez żadnego odwrócenia i bez płaskiej góry: ok. 0,5 dB na krok do v40, potem równo ok. 0,21-0,25 dB na krok aż do v127.
- Dół stromy, ale ciągły (bez warstw): v3-10 to 12-17 dB, czyli ok. 2 dB na każdą wartość velocity.
- Poziom v127 ok. -18 do -20 dB.
- Wniosek: najczystszy i najszerszy instrument z pomiarów. Mieści 12-13 schodków po 4 dB; dobry wzorzec do testu celowania.

## True Keys American (Steinway D NY, ten sam model co pierwszy preset Pianoteqa), C2 i C4
Bez wygładzania (powtórzenia ±0,2-0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| True Keys C2 | -48.5 | -47.3 | -41.0 | -34.5 | -30.6 | -26.8 | 1.2 | 12.8 | 3.9 | 3.8 | 21.8 |
| True Keys C4 | -52.0 | -50.4 | -44.8 | -37.0 | -32.8 | -29.5 | 1.6 | 13.4 | 4.2 | 3.3 | 22.4 |

- Zakres najwęższy ze wszystkich: v5-124 ok. 22-23 dB (Pianoteq ten sam model: ok. 37 dB). v1-127 ok. 25 dB w C2 i 31 dB w C4.
- Płaska góra: od v60 do v127 tylko ok. 8,5 dB (Pianoteq: ok. 17 dB). Mocniej znaczy tu głównie jaśniej: w C4 jasność rośnie z ok. 860 Hz (v60) do ok. 1530 Hz (v127).
- Dół głośny i płaski: v1-12 w C2 w granicach ok. 4 dB.
- Prawie bez odwróceń (w C4 v17 i v33 po ok. 1,7 dB ciszej niż poprzednie).
- Poziom v127 ok. -26 do -29 dB, ok. 11-14 dB ciszej niż Pianoteq.
- Wniosek: ten sam fortepian w dwóch programach ma zupełnie inną krzywą, więc krzywa to wybór producenta, nie cecha fortepianu. Tabela schodków musi być na instrument, nie na model fortepianu.

## UVI Austrian Grand (Bösendorfer 280VC), C2 i C4
Bez wygładzania (powtórzenia ±0,2-0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Austrian C2 | -55.5 | -52.2 | -43.7 | -36.2 | -26.5 | -16.3 | 3.3 | 16.0 | 9.7 | 10.2 | 39.2 |
| Austrian C4 | -62.0 | -59.1 | -50.3 | -46.3 | -30.2 | -19.9 | 2.9 | 12.8 | 16.1 | 10.2 | 42.1 |

- C2: wzorowo. Bez odwróceń, szeroki zakres (v1-127 ok. 44 dB), góra nie płaska, a nawet bardziej stroma niż środek (ok. 0,3 dB na krok od v60).
- C4: dziura w środku. Warstwa v44-62 jest ok. 5 dB za cicha: v44 ok. 4,9 dB ciszej niż v43, a v63 ok. 4,7 dB głośniej niż v62. Od v43 do v61 głośność wraca do tego samego miejsca; między v40 i v60 tylko 0,7 dB. To dokładnie strefa 30-60 i rejestr melodii.
- Poziom v127 ok. -16 do -19 dB. Zakres C4 v1-127 ok. 51 dB.
- Ten sam model co Pianoverse Black Diamond, a wady w zupełnie innych miejscach (Pianoverse: urwisko v8/v9).
- Wniosek o metodzie: wada siedzi w jednym rejestrze. Dwie nuty (C2, C4) nie wystarczą, żeby uznać bibliotekę próbek za czystą; przed zbudowaniem tabeli dla instrumentów z próbek warto zmierzyć 2-3 nuty więcej.

## True Keys American, Vel. Sensitivity 60% (wcześniej 40%), C2 i C4

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| True Keys 60% C2 | -49.0 | -48.6 | -44.6 | -37.5 | -32.1 | -26.9 | 0.4 | 11.2 | 5.4 | 5.2 | 22.1 |
| True Keys 60% C4 | -52.4 | -51.7 | -48.4 | -40.0 | -34.4 | -29.6 | 0.7 | 11.8 | 5.6 | 4.7 | 22.8 |

- Końce bez zmian: v1 i v127 dokładnie tak samo głośne jak przy 40%, więc zakres się nie poszerzył (v1-127 nadal ok. 25 dB w C2 i 31 dB w C4).
- Zmienił się tylko środek: ciszej o 1,3 dB przy v10, o 3,6 dB przy v30, o 3,0 dB przy v60, o 1,5 dB przy v90. Góra jest przez to mniej płaska (v60-127: 11,6 dB zamiast 8,6 dB).
- Jasność przy każdym velocity identyczna jak przy 40%: ta gałka nie zmienia wyboru próbek, tylko dokłada głośność według krzywej.
- Wniosek: Vel. Sensitivity to po prostu krzywa velocity wewnątrz instrumentu. Router ze schodkami robi to samo, więc dla trybu Schody ustawienie tej gałki prawie nie ma znaczenia; zakresu (22-31 dB) nie poszerza.

## True Keys American, Velocity Amount 100% (domyślnie 95%), Sensitivity 40%, C2 i C4

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| True Keys 100% C2 | -71.9 | -61.4 | -44.9 | -35.6 | -30.9 | -26.8 | 10.5 | 25.8 | 4.7 | 4.1 | 45.1 |
| True Keys 100% C4 | -75.3 | -64.5 | -48.7 | -38.1 | -33.2 | -29.5 | 10.8 | 26.5 | 4.9 | 3.6 | 45.8 |

- Zakres v5-124 podwojony: ok. 45 dB zamiast 22 dB. Góra bez zmian (v124-127 identyczne), zmienia się dół: v10 ciszej o 14 dB, v5 o 23 dB, v1 o 47 dB (v1 to teraz praktycznie cisza, ok. -97 dB).
- Jasność przy każdym velocity identyczna: te same próbki, inna głośność.
- Wyjaśnienie: przy 95% instrument zostawia 5% głośności nawet przy najsłabszym uderzeniu (20·log10(0,05) = -26 dB), stąd dawny zakres ok. 25-31 dB. Przy 100% ta podłoga znika.
- Dół jest teraz bardzo stromy: v1-10 to ok. 1,5-10 dB na każdą wartość velocity. Bez schodków najsłabsze uderzenia będą skakać; ze schodkami router sam wybierze najcichszy słyszalny poziom.
- Wniosek: ustawienie w instrumencie poszerzyło zakres tam, gdzie router nie mógł. 45 dB mieści 11-12 schodków po 4 dB.

## UVI Keysuite Hybrid Custom, C2 i C4
Bez wygładzania (powtórzenia ±0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Keysuite C2 | -45.2 | -44.9 | -42.2 | -34.4 | -25.3 | -17.4 | 0.4 | 10.4 | 9.1 | 8.0 | 27.9 |
| Keysuite C4 | -51.4 | -49.7 | -46.4 | -38.0 | -29.1 | -21.1 | 1.7 | 11.7 | 9.0 | 8.0 | 30.3 |

- Odwrotność Ravenscrofta: płaski dół, żywa góra. Od v1 do v30 tylko ok. 4-8 dB, od v30 do v127 ok. 25 dB (ok. 0,25-0,3 dB na krok, bez płaskiej góry).
- Wysoka podłoga: v1 tylko ok. 29 dB (C2) i 34 dB (C4) pod v127. Ten sam podpis co True Keys przy Velocity Amount 95%; możliwe, że ma podobne ustawienie.
- Szew przy v54 w obu rejestrach: v54 ok. 3 dB ciszej niż v53 (C2 -3,4 dB, C4 -2,8 dB). Mniejsze odwrócenie przy v86 (ok. 1,2 dB).
- Poziom v127 ok. -17 do -20 dB.

## UVI Keysuite Fazioli (ten sam model co Claire), C2 i C4
Bez wygładzania (powtórzenia ±0,2-0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Keysuite Fazioli C2 | -48.8 | -45.5 | -38.4 | -31.3 | -27.0 | -23.6 | 3.3 | 14.3 | 4.2 | 3.4 | 25.2 |
| Keysuite Fazioli C4 | -51.2 | -48.0 | -38.9 | -32.2 | -27.6 | -23.8 | 3.2 | 15.8 | 4.6 | 3.8 | 27.5 |

- Wąsko: v1-127 ok. 28-30 dB, v1 tylko ok. 28-30 dB pod v127 (podpis podłogi, jak Keysuite Hybrid i True Keys przy 95%).
- Płaska góra: od v60 do v127 tylko ok. 8 dB (0,10-0,15 dB na krok). Cała dynamika siedzi w v1-60.
- Małe odwrócenia: C2 v11 (-2,3 dB) i v32 (-1,4 dB), C4 v39 (-2,0 dB).
- Poziom v127 ok. -23 dB.
- Porównanie z Claire (ten sam fortepian): Claire ma dynamikę na górze (v60-127 ok. 19 dB) i płaski, nierówny dół w C2; Keysuite Fazioli odwrotnie. Znowu: krzywa to wybór producenta.
- Oba presety Keysuite mają ten sam podpis podłogi, więc prawdopodobnie decyduje o tym jedno ustawienie silnika Keysuite.

## Addictive Keys Studio Grand (Steinway NY), C2 i C4
Bez wygładzania (powtórzenia ±0,2-0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Addictive C2 | -51.3 | -48.5 | -40.3 | -31.4 | -25.3 | -20.1 | 2.8 | 17.2 | 6.0 | 5.2 | 31.2 |
| Addictive C4 | -53.9 | -51.5 | -42.3 | -35.1 | -26.5 | -21.4 | 2.4 | 16.4 | 8.6 | 5.1 | 32.5 |

- Gładko i bez odwróceń (C2 żadnego, C4 jedno małe przy v33, ok. 1,1 dB). Krok maleje łagodnie: ok. 0,38 dB do v40, ok. 0,15 dB powyżej v90.
- Zakres v5-124 ok. 31-33 dB, v1-127 ok. 34-36 dB; v1-12 w granicach ok. 7 dB (lekki podpis podłogi).
- Środek v10-60 w C2 prawie identyczny z Pianoteqiem (ten sam Steinway NY): średnio 0.0 dB różnicy, najwyżej 0.7 dB. Rozjeżdżają się tylko końce: Pianoteq ma ok. 5-6 dB głośniejszą górę i dużo cichszy dół.
- Poziom v127 ok. -20 do -21 dB.

## Addictive Keys Modern Upright, C2 i C4
Bez wygładzania (powtórzenia ±0,1-0,2 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AK Upright C2 | -53.9 | -51.1 | -42.4 | -33.8 | -27.3 | -21.2 | 2.7 | 17.3 | 6.6 | 6.1 | 32.6 |
| AK Upright C4 | -51.9 | -49.4 | -41.1 | -32.6 | -25.3 | -18.2 | 2.6 | 16.8 | 7.3 | 7.1 | 33.8 |

- Najczystszy instrument z próbek w całych pomiarach: od v10 zero odwróceń w obu rejestrach, w C4 ani jednego skoku powyżej 1,4 dB, powtórzenia ±0,1 dB.
- Krok maleje łagodnie: ok. 0,38 dB do v40, ok. 0,2 dB powyżej v90.
- Zakres v1-127 ok. 36-37 dB, v1-12 w granicach ok. 6-8 dB (lekki podpis podłogi, jak w Studio Grand).
- Od v30 w górę prawie identyczny z VI Labs Modern U (różnica do ok. 1,5 dB). Różnią się tylko dołem: VI Labs schodzi o 10-19 dB niżej.
- Oba Addictive Keys mają podobną podłogę (v1 ok. 34-37 dB pod v127), więc to raczej cecha silnika Addictive Keys niż próbek.
- Poziom v127 ok. -18 do -21 dB.

## UVI C7 Grand, Dynamics 100% (domyślnie 95%), C2 i C4

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UVI C7 100% C2 | -60.8 | -51.2 | -34.0 | -23.8 | -17.0 | -12.0 | 9.6 | 27.4 | 6.8 | 4.9 | 48.7 |
| UVI C7 100% C4 | -61.9 | -53.3 | -33.2 | -23.3 | -18.3 | -13.8 | 8.6 | 30.0 | 4.9 | 4.5 | 48.1 |

- Zakres v5-124 prawie podwojony: ok. 48-49 dB zamiast 25 dB. Góra bez zmian (v124-127 identyczne), dół niżej: v10 o 14 dB, v5 o 23 dB, v1 o 47 dB (praktycznie cisza).
- Jasność identyczna przy każdym velocity: te same próbki, inna głośność.
- Zmiany przy każdym velocity są dokładnie takie same jak w True Keys przy Velocity Amount 95%->100% (do setnych części dB): ten sam silnik UVI, ta sama reguła (5% głośności zostaje przy 95%).
- Od v10 w górę bez odwróceń w C2; w C4 bez zmian dwa małe (v36, v66).
- Wniosek: 48 dB mieści 12 schodków po 4 dB.

## Kawai EX Pro, Dynamics 100% (domyślnie 95%), C2 i C4
Bez wygładzania; Kawai ma powtórzenia ±1,7-1,9 dB (round robin), więc pojedyncze wartości mogą się różnić o tyle.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kawai 100% C2 | -75.4 | -59.4 | -41.8 | -34.7 | -26.5 | -23.7 | 16.0 | 24.7 | 8.2 | 2.8 | 51.7 |
| Kawai 100% C4 | -81.7 | -63.9 | -45.5 | -33.9 | -30.4 | -24.3 | 17.8 | 30.0 | 3.5 | 6.1 | 57.4 |

- Zakres v5-124 z ok. 30-33 dB do ok. 52-57 dB. Dół niżej: v10 o ok. 13 dB, v5 o ok. 21-22 dB, v1 o ok. 44 dB. Od v60 w górę bez zmian (różnice w granicach powtórzeń).
- Spadki przy każdym velocity mniejsze niż w UVI C7 i True Keys (np. v30: -2 dB zamiast -3,9 dB): ta sama gałka, ale inna krzywa próbek pod spodem.
- Płaska góra została: od v60 do v124 nadal ok. 10-11 dB. Prawie cała nowa dynamika jest poniżej v40, jak w Ravenscrofcie.
- Uwaga: ten sam podpis podłogi przy 95% tu nie był widoczny (v1 już ok. 42-48 dB pod v127), bo Kawai ma też ciche warstwy próbek.

## Ivory III German D, C2 i C4
Bez wygładzania (powtórzenia ±0,2-0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ivory German D C2 | -54.4 | -52.7 | -45.9 | -37.1 | -29.5 | -19.6 | 1.7 | 15.6 | 7.6 | 9.9 | 34.8 |
| Ivory German D C4 | -59.6 | -57.9 | -51.5 | -39.9 | -30.7 | -19.6 | 1.7 | 17.9 | 9.3 | 11.0 | 39.9 |

- Prawie prosta linia w dB od v10 do v127: ok. 0,29 (C2) i 0,33 (C4) dB na krok, bez płaskiej góry (góra tak samo stroma jak środek). Odchylenie od prostej w C2 ok. 0,7 dB, tyle co Pianoteq i UVI Austrian C2; najbliżej prostej z wszystkich pomiarów razem z nimi.
- Zakres v1-127 ok. 37 dB (C2) i 42 dB (C4). Dół v1-10 płaski (ok. 3 dB).
- Wady: C2 v66 ok. 2,1 dB ciszej niż v65; C4 skok +3,6 dB przy v36 i +2,0 dB przy v111.
- Poziom v127 ok. -18,7 dB w obu rejestrach (identycznie).
- Wniosek: równe odstępy velocity dają tu prawie równe kroki w dB; schodki dla Ivory to prawie zwykły podział co ok. 13 wartości velocity (4 dB).

## Ivory III Modern Upright, C2 i C4
Bez wygładzania (powtórzenia ±0,1 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ivory Upright C2 | -57.8 | -56.2 | -49.5 | -40.6 | -32.1 | -22.2 | 1.7 | 15.5 | 8.5 | 10.0 | 35.7 |
| Ivory Upright C4 | -55.5 | -53.8 | -47.2 | -37.8 | -30.2 | -22.1 | 1.7 | 16.0 | 7.7 | 8.1 | 33.4 |

- Najprostsza krzywa ze wszystkich pomiarów: w C2 ok. 0,29 dB na krok od v1 do v127 (także na samym dole), odchylenie od prostej tylko 0,34 dB, zero odwróceń. Powtórzenia ±0,1 dB.
- C4 równie prosto (odchylenie 0,66 dB) z jedną wadą: v122 ok. 2,8 dB ciszej niż v121 (sam szczyt).
- Zakres v1-127 ok. 36-38 dB; poziom v127 ok. -21 dB.
- Podobnie jak Ivory German D (ok. 0,3 dB na krok), Ivory liczy głośność prawie jak prostą w dB. W C2 kształt obu zgadza się co do ok. 1,7 dB, ale w C4 German D jest bardziej stromy (ok. 42 dB zakresu wobec ok. 36 dB) i oba mają szwy w innych miejscach (v36 wobec v122), więc wspólna tabela byłaby tylko przybliżeniem.

## Walker 1955 Concert D, C2 i C4
Bez wygładzania; powtórzenia ok. ±0,6 dB (C2) i ±0,8 dB (C4), więc pojedyncze wartości skaczą w zygzak. RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Walker Concert D C2 | -67.3 | -64.8 | -55.9 | -47.6 | -37.7 | -34.1 | 2.5 | 17.2 | 9.9 | 3.6 | 33.2 |
| Walker Concert D C4 | -72.5 | -69.7 | -58.1 | -45.1 | -36.6 | -33.1 | 2.8 | 24.6 | 8.5 | 3.5 | 39.4 |

- Zakres v1-127 ok. 35 dB (C2) i 41 dB (C4), czyli jak Ivory German D. Dół nie jest płaski (v1-12 ok. 7-9 dB), więc nie ma podpisu podłogi.
- Płaska góra: v90-124 tylko ok. 3,5 dB, v100-127 ok. 2 dB. W C2 do tego półka v40-60 (ok. 4,5 dB na 20 kroków) i szybszy odcinek v60-80 (ok. 8 dB).
- Zygzak: w C4 v11-45 kolejne nuty na przemian ±1,5-4 dB (24 skoki powyżej 1,4 dB, 10 odwróceń). Odchylenie od prostej 1,8 dB (C2) i 2,9 dB (C4). Szum powtórzeń ok. 3 razy większy niż w Ivory, ok. 2,5 razy mniejszy niż w Kawai.
- Poziom v127 ok. -33 do -34 dB: o ok. 11-15 dB ciszej niż Ivory czy Kawai na tym samym ustawieniu. Przy przełączaniu instrumentów trzeba to wyrównać suwakiem.
- Najciemniejszy Steinway D z mierzonych: środek widma przy v127 ok. 900 Hz w C2 (Addictive ok. 1280, Pianoteq ok. 1420). Barwa rośnie dalej w v90-127 (C2 ok. 670 -> 900 Hz), choć głośność prawie stoi.
- Porównanie z innymi Steinwayami D (C2, względem v124): v30 Walker -21,5, Addictive -20,0, True Keys 100% -18,0, Pianoteq -25,2; v90 Walker -3,5, Addictive -5,0, True Keys -4,0, Pianoteq -8,4. Walker najbliżej Addictive, tylko z większym szumem.

## Walker 1955 Concert D, ustawienia domyślne (dynamika nieliniowa, 18 warstw velocity), C2 i C4
Bez wygładzania; powtórzenia ok. ±0,6 dB (C2) i ±0,9 dB (C4). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Walker domyślnie C2 | -52.0 | -51.3 | -47.7 | -43.6 | -36.5 | -34.1 | 0.7 | 7.7 | 7.1 | 2.4 | 17.9 |
| Walker domyślnie C4 | -55.8 | -55.1 | -48.4 | -41.0 | -36.0 | -33.1 | 0.7 | 14.1 | 5.0 | 2.9 | 22.8 |
| (liniowo, 36 warstw) C2 | -67.3 | -64.8 | -55.9 | -47.6 | -37.7 | -34.1 | 2.5 | 17.2 | 9.9 | 3.6 | 33.2 |
| (liniowo, 36 warstw) C4 | -72.5 | -69.7 | -58.1 | -45.1 | -36.6 | -33.1 | 2.8 | 24.6 | 8.5 | 3.5 | 39.4 |

- Zakres v1-127 spada z ok. 35/41 dB do ok. 19/23 dB: najwęższy ze wszystkich pomiarów (wcześniej najwęższe Fazioli Keysuite ok. 28-30 dB).
- Góra bez zmian (v127 ok. -33/-34 dB, od v90 różnica poniżej 0,6 dB). Dół podniesiony płynnie: v1 o ok. 16-18 dB, v20 o ok. 11-13 dB, v50 o ok. 3,5 dB. Różnica rośnie gładko w stronę dołu, więc to działa jak kompresor (wzmocnienie zależne od velocity), a nie jak inny wybór próbek.
- Barwa prawie ta sama co przy ustawieniu liniowym (środek widma C2: v10 ok. 300 Hz, v127 ok. 900 Hz). Ciche nuty to te same ciche próbki, tylko głośniej. Jedyna widoczna różnica od 18 warstw: w C2 barwa stoi w miejscu od v5 do v20 (ok. 300 Hz), a przy 36 warstwach już tam lekko jaśnieje.
- Dół płaski: v1-12 tylko ok. 4 dB, v5-10 ok. 0,7 dB (podobny podpis podłogi jak przy 95% w UVI).
- Zygzak zostaje, w C4 nawet mocniejszy (v16-49 na przemian ±2-4 dB, 18 odwróceń). W C2 nowy zygzak v77-82 (±2,7 dB).
- Zmieniono naraz dwie rzeczy (dynamika i liczba warstw). Kształt różnicy wskazuje, że prawie cały efekt głośności to dynamika; warstwy wpływają na barwę i miejsca szwów.

## Alicia's Keys (Acoustic, Yamaha), C2 i C4
Bez wygładzania (powtórzenia ±0,3-0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Alicia's Keys C2 | -51.3 | -51.2 | -43.8 | -33.6 | -26.5 | -21.4 | 0.1 | 17.7 | 7.0 | 5.1 | 29.9 |
| Alicia's Keys C4 | -44.6 | -42.3 | -37.7 | -29.2 | -23.2 | -17.7 | 2.3 | 13.1 | 6.0 | 5.5 | 26.9 |

- Zakres v1-127 ok. 30 dB (C2) i 27 dB (C4). Dół płaski: w C2 v1-14 prawie bez zmian (v5-10 tylko 0,1 dB), w C4 v1-9 ok. 1,5 dB.
- Widać budowę warstw: barwa (środek widma) stoi w miejscu w obrębie bloku i skacze na granicy. Granice co ok. 8 velocity: v20, 28, 36, 44, 52, 60, 68, 76, 84, 92, 100, 115 (ostatnie dwie warstwy szersze: v100-114 i v115-127; pod v20 jedna szeroka warstwa). Razem ok. 13 warstw. W obrębie warstwy głośność rośnie płynnie, ok. 0,3 dB na krok, przy tej samej próbce.
- Szwy na granicach warstw: C2 v28 +2,1 dB, v78 -1,9 dB; C4 v20 +2,0 dB, v28 +3,5 dB, v78 -1,9 dB.
- Największa wada: w C4 warstwa v92-99 jest o ok. 3 dB za głośna. v92 skacze o +3,3 dB, a v100 spada o -3,1 dB, więc v100-117 jest ciszej niż v99 (18 wartości velocity z rzędu odwróconych). W C2 tej wady nie ma.
- Głośny poziom: v127 ok. -21 dB (C2) i -17 dB (C4), czyli najgłośniej z mierzonych, ok. 13-16 dB głośniej niż Walker.
- Góra nie jest płaska: v90-124 ok. 5 dB (Walker ok. 3,5 dB).

## Hammers and Waves Modern Grand, C2 i C4
Bez wygładzania. RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Hammers and Waves C2 | -42.6 | -42.5 | -39.0 | -36.1 | -26.3 | -20.4 | 0.1 | 6.3 | 9.8 | 6.0 | 22.2 |
| Hammers and Waves C4 | -48.8 | -48.7 | -44.4 | -39.0 | -28.4 | -20.5 | 0.1 | 9.8 | 10.6 | 7.9 | 28.3 |

- Czyste schodki: 12 warstw, każda o stałej głośności i barwie (w obrębie warstwy odchylenie tylko 0,1-0,2 dB, bez skalowania velocity i bez powtórzeń). Głośność zmienia się tylko na granicach.
- Warstwy (velocity, poziom C2 / C4 w dB): 1-29 (-42,4 / -48,8), 30-48 (-39,3 / -44,5), 49-62 (-36,1 / -39,0), 63-71 (-32,4 / -35,6), 72-79 (-30,0 / -32,8), 80-86 (-27,9 / -30,1), 87-92 (-26,3 / -28,4), 93-98 (-24,9 / -26,7), 99-103 (-23,6 / -25,3), 104-107 (-22,5 / -23,9), 108-115 (-21,8 / -22,5), 116-127 (-20,4 / -20,7).
- Stopnie są nierówne: na dole 3-5,5 dB, na górze tylko 0,8-1,8 dB. Warstwy na dole szerokie (v1-29 to jedna próbka), na górze wąskie (v104-107 to tylko 4 wartości).
- Cała jedna czwarta zakresu velocity (v1-29) brzmi identycznie. Pianissimo nie da się tu stopniować.
- Zakres v1-127 ok. 22 dB (C2) i 28 dB (C4); wąski, podobny do Walkera na ustawieniach domyślnych. Poziom v127 ok. -20 dB (głośno, jak Alicia's Keys).
- Barwa rośnie z każdą warstwą (C2 ok. 350 -> 1050 Hz, C4 ok. 560 -> 1390 Hz), więc każdy stopień to też nowa barwa.
- Drobna wada: v2-3 ok. 2 dB ciszej niż v1 i v4.

## AIR Yamaha C7 Grand Real, ustawienia domyślne, C2 i C4
Bez wygładzania (powtórzenia ±0,3 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AIR C7 C2 | -51.8 | -49.3 | -43.1 | -36.3 | -32.3 | -26.3 | 2.5 | 13.1 | 4.0 | 6.0 | 25.5 |
| AIR C7 C4 | -52.7 | -50.2 | -44.0 | -36.4 | -31.7 | -26.8 | 2.5 | 13.8 | 4.7 | 5.0 | 25.9 |

- Zakres v1-127 ok. 31-32 dB. Gładko: odchylenie od prostej ok. 0,85 dB, zero odwróceń.
- C2 i C4 mają prawie ten sam kształt (różnica względem v124 najwyżej ok. 1 dB, średnio 0,5 dB). To pierwszy instrument, w którym jedna tabela naprawdę pasuje do obu rejestrów.
- Tylko 6 warstw próbek (barwa stała w obrębie warstwy, głośność skalowana płynnie): v1-59, v60-89, v90-104, v105-115, v116-125, v126-127. Środek widma C2: ok. 290-305 Hz, 411, 668, 952, 1272, 1375 Hz.
- Szwy na granicach: v60 +2,1/+2,8 dB, v90 +1,9 dB (C4), v116 +2,9/+2,1 dB, v126 +2,9/+3,3 dB. v126-127 to osobna warstwa akcentu ok. 3 dB ponad v125.
- Dół: v2-3 ok. 1 dB ciszej niż v1, potem v4 +2,8 dB.
- Poziom v127 ok. -23 dB.
- Kształt bardzo podobny do UVI C7 na 95% (różnica do ok. 1,5 dB aż do v90), choć to inny producent.

## AIR Steinway D Grand, ustawienia domyślne, C2 i C4
Bez wygładzania (powtórzenia ±0,3-0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AIR Steinway D C2 | -53.8 | -51.3 | -45.1 | -38.1 | -32.8 | -26.9 | 2.4 | 13.2 | 5.3 | 5.9 | 26.9 |
| AIR Steinway D C4 | -54.7 | -52.2 | -45.9 | -38.4 | -33.2 | -27.8 | 2.5 | 13.8 | 5.2 | 5.4 | 26.9 |

- Zakres v1-127 ok. 33 dB. Gładko: odchylenie od prostej ok. 0,7 dB, zero odwróceń.
- C2 i C4 prawie identyczne (różnica względem v124 najwyżej 0,66 dB, średnio 0,23 dB). Jedna tabela na oba rejestry.
- Te same granice warstw co AIR C7 Grand Real: v1-59, v60-89, v90-104, v105-115, v116-125, v126-127 (6 warstw, barwa stała w obrębie warstwy). Szwy: v60 +2,3/+2,8 dB, v90 +2,6/+2,5 dB, v105 +1,8/+1,6 dB, v116 +2,4/+1,9 dB, v126 +3,2/+3,3 dB (warstwa akcentu).
- Krzywa prawie taka sama jak AIR C7: poniżej v90 stale ok. 1,2-1,4 dB niżej (względem v124), od v90 w górę różnica do 0,5 dB. To ta sama krzywa velocity silnika AIR, tylko inaczej wyrównane warstwy.
- Poziom v127 ok. -24 dB (prawie jak AIR C7, ok. -23 dB).
- Wniosek: AIR to jedna rodzina. Jedna tabela "Schodów" pasuje do obu fortepianów AIR i obu rejestrów (błąd do ok. 1,5 dB).

## Roland Earth Classic Grand, C2 i C4
Bez wygładzania (powtórzenia ±0,2 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Roland Classic Grand C2 | -48.2 | -47.3 | -42.6 | -35.3 | -28.9 | -22.7 | 0.8 | 12.1 | 6.3 | 6.2 | 25.5 |
| Roland Classic Grand C4 | -47.1 | -46.3 | -41.2 | -33.9 | -28.1 | -22.2 | 0.8 | 12.4 | 5.8 | 5.9 | 24.8 |

- v1 to cisza (ok. -97 do -99 dB, czyli ok. 75 dB pod v2). Roland nie gra nuty z velocity 1.
- Od v2 do v127 ok. 28-29 dB. Bardzo gładko: odchylenie od prostej ok. 0,7-0,8 dB, zero odwróceń, powtórzenia ±0,2 dB. Jedyny szew: v4 +2,1-2,6 dB.
- Krzywa prawie prosta w dB: ok. 0,24 dB na krok w v10-40, 0,22 w v40-80, 0,18 w v80-127. Góra nie jest płaska (v90-124 ok. 6 dB).
- Barwa rośnie płynnie (C2 ok. 210 -> 1160 Hz, C4 ok. 505 -> 1370 Hz), bez widocznych skoków warstw.
- C2 i C4 mają ten sam kształt (różnica najwyżej 1,2 dB, średnio 0,4 dB): jedna tabela na oba rejestry.
- Poziom v127 ok. -22 dB.
- Uwaga techniczna: po bounce C4 pierwsze "cofnij" w Studio One cofnęło inny krok (nie bounce), dopiero drugie usunęło bounce. Pomiar nie jest tym dotknięty (nagranie było już gotowe).

## Galaxy Vintage D, ustawienie domyślne Basic Grand, C2 i C4
Bez wygładzania (powtórzenia ±0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Galaxy Vintage D C2 | -60.1 | -55.9 | -45.4 | -36.8 | -28.9 | -18.0 | 4.2 | 19.1 | 7.8 | 11.0 | 42.1 |
| Galaxy Vintage D C4 | -69.9 | -64.1 | -49.2 | -39.2 | -31.3 | -23.0 | 5.7 | 25.0 | 7.8 | 8.4 | 46.9 |

- Szeroki zakres: v1-127 ok. 50 dB (C2) i 56 dB (C4). Góra nie jest płaska (v90-124 ok. 8-11 dB, v120-127 rośnie ok. 0,7 dB na krok).
- Kształt piły: w obrębie warstwy głośność rośnie mocno (ok. 0,4-0,7 dB na krok), a następna warstwa zaczyna ciszej niż kończy poprzednia. Spadki: C2 v43 -3,1, v104 -2,6, v120 -2,1 dB; C4 v43 -2,5, v57 -2,1, v80 -1,7, v96 -2,8, v104 -2,4, v120 -2,0 dB. Razem 15-17 odwróceń.
- Warstwy (barwa): w górnej połowie co ok. 8 velocity (C2 ok. v57, 70, 80, 88, 96, 104, 112, 120, 127).
- C2 i C4 różnią się kształtem (do ok. 5 dB), więc osobne tabele dla rejestrów.
- Poziom v127 ok. -16 dB (C2) i -21 dB (C4): najgłośniej z mierzonych w basie.

## Galaxy Vintage D, Basic Grand, Dynamics +20%, C2 i C4
Bez wygładzania (powtórzenia ±0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Galaxy +20% C2 | -68.5 | -64.0 | -52.1 | -41.4 | -31.5 | -18.2 | 4.5 | 22.6 | 9.9 | 13.3 | 50.3 |
| Galaxy +20% C4 | -78.3 | -72.2 | -56.0 | -43.8 | -33.9 | -23.2 | 6.0 | 28.4 | 9.9 | 10.7 | 55.1 |

- Zakres v1-127 z ok. 50 do 59 dB (C2) i z ok. 56 do 65 dB (C4). v127 bez zmian (ok. -16 / -21 dB).
- Zmiana jest dokładnie liniowa w dB: różnica = -0,0692 x (127 - v) dB, czyli v1 ciszej o 8,7 dB, v64 o 4,4 dB, v127 bez zmian. Odchylenie od tej prostej najwyżej 0,06 dB, w obu rejestrach to samo.
- Te same próbki (barwa identyczna co do herca). Gałka Dynamics to tylko pochylenie głośności, nie wybór warstw.
- Piła zostaje: spadki v43 (-3,1 / -2,5 dB), v104 (-2,6 / -2,4 dB), v120 (-2,0 / -1,9 dB) prawie tej samej wielkości, 14-16 odwróceń.
- Wniosek: każde +10% Dynamics dodaje ok. 4,4 dB zakresu (0,035 dB na krok velocity poniżej 127). Krzywą dla innego ustawienia można policzyć bez nowego pomiaru.

## Piano in Blue, C2 i C4
Bez wygładzania (powtórzenia ±0,2 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Piano in Blue C2 | -49.6 | -48.0 | -42.0 | -33.5 | -25.5 | -17.0 | 1.6 | 14.5 | 8.0 | 8.5 | 32.5 |
| Piano in Blue C4 | -51.9 | -50.4 | -44.5 | -36.5 | -27.5 | -18.8 | 1.5 | 13.9 | 9.0 | 8.7 | 33.1 |

- Prawie idealna prosta w dB: ok. 0,29 dB na krok w całym zakresie (v10-40: 0,29-0,31, v40-80: 0,29-0,31, v80-127: 0,24). Odchylenie od prostej 0,44-0,48 dB (drugi wynik po Ivory Modern Upright C2), zero odwróceń.
- Zakres v1-127 ok. 34-35 dB. Góra nie jest płaska (v90-124 ok. 8,5 dB).
- Warstwy słychać tylko w barwie (C2 ok. v51, 81, 91, 101, 121), głośność przechodzi przez nie gładko. Jedyne skoki: v2-3 ok. 2 dB ciszej niż v1 i v4, w C4 v71 +1,4 dB.
- C2 i C4 prawie ten sam kształt (różnica średnio 0,8 dB, najwyżej 1,4 dB).
- Poziom v127 ok. -16,5 / -18 dB (głośno).
- Kształtem najbliżej Pianoteq (od v10: C2 średnio 0,0 dB różnicy, odchylenie 0,7 dB; C4 0,6 / 0,9 dB) i Ivory Modern Upright (C4 odchylenie 0,6 dB).

## Sforzando Ivy Piano, C2 i C4
Bez wygładzania. RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ivy Piano C2 | -100.7 | -88.5 | -75.9 | -54.7 | -45.7 | -36.6 | 12.2 | 33.9 | 8.9 | 9.1 | 64.1 |
| Ivy Piano C4 | -98.3 | -94.6 | -66.9 | -51.5 | -41.5 | -35.6 | 3.7 | 43.1 | 10.0 | 5.9 | 62.8 |

- Dół jest nieużyteczny: v1 to cisza, v2-5 ok. 60-90 dB pod v127, a w v7-33 kolejne nuty skaczą na przemian o ±5-8 dB (C2 i C4). W C4 v10-33 aż 12 odwróceń po 5-8 dB.
- Od v34 w górę spokojniej: ok. 0,31 dB na krok, zakres v34-127 ok. 29-30 dB, odchylenie od prostej ok. 1,2 dB, szum ±0,6-0,8 dB, drobny zygzak ±1,5 dB.
- W C2 nuta v122 w ogóle nie zabrzmiała (ok. -76 dB, tak jak cisza między nutami). Prawdopodobnie brak próbki w jednym wariancie albo błąd biblioteki; do sprawdzenia, czy powtarza się przy ponownym pomiarze.
- Poziom v127 ok. -33/-35 dB (cicho, jak Walker).
- C2 i C4 różnią się na dole o kilkadziesiąt dB, od v34 podobnie.
- Wniosek: do nauki dynamiki tylko zakres v34-127; "Schody" dla Ivy muszą zaczynać od ok. v34.

## Rosewood Grand, ustawienia domyślne, C2 i C4
Bez wygładzania (powtórzenia ±0,15-0,2 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rosewood C2 | -47.0 | -45.2 | -40.0 | -30.8 | -23.1 | -16.1 | 1.8 | 14.5 | 7.7 | 7.0 | 30.9 |
| Rosewood C4 | -46.1 | -44.5 | -38.0 | -30.1 | -22.9 | -15.7 | 1.6 | 14.5 | 7.1 | 7.3 | 30.5 |

- Bardzo czysto: odchylenie od prostej ok. 0,67 dB, zero odwróceń, żadnych prawdziwych szwów.
- Prawie prosta w dB: ok. 0,33 dB na krok na dole, 0,28-0,31 w środku, 0,20-0,21 na górze. Zakres v1-127 ok. 32-33 dB.
- C2 i C4 prawie ten sam kształt (różnica średnio 0,6 dB, najwyżej 1,8 dB).
- Barwa zmienia się warstwami (ok. v47, 58, 68, 79, 90, 100, 111), głośność przechodzi przez nie gładko.
- Poziom v127 ok. -15,5 dB: najgłośniejszy instrument z mierzonych.
- Kształtem najbliżej Piano in Blue (C2: odchylenie 0,5 dB, Rosewood średnio ok. 1,5 dB głośniej w środku względem v124). Należy do rodziny "prosta w dB" (Pianoteq, Piano in Blue, Ivory Upright).

## Poprawka pomiaru: dołki przy v2-3 i v7 to błąd testu, nie instrumentów
- W pliku testowym nuty v2 i v3 są o połowę krótsze (ok. 0,07 s zamiast ok. 0,15-0,2 s), v7 ok. 0,11 s, a v25 i v33 ok. 0,14 s. RMS liczymy z 0,3 s, więc krótsza nuta to wcześniejsze tłumienie i niższy wynik.
- Sprawdzone na 9 instrumentach: v2-3 wychodzą o ok. 1,3-2,3 dB za cicho, v7 o ok. 0,7-1,2 dB, v25/v33 o ok. 0,3-0,6 dB, wszędzie podobnie.
- Dlatego wcześniejsze uwagi typu "v2-3 ciszej niż v1 i v4" oraz "szew v4 +2 do 3 dB" (Walker, AIR C7, Hammers and Waves, Roland, Piano in Blue, Rosewood) to ten sam błąd testu, a nie wada instrumentu. Cisza na v1 w Rolandzie i chaos dołu w Ivy są prawdziwe (dużo większe niż 2 dB).
- Pozostałe długości nut też się różnią (ok. 0,14-0,22 s), co daje dodatkowy szum ok. ±0,2-0,3 dB w każdym pomiarze.

## Zmiana metody od 16.11 (od Berlin Concert Grand)
- Wszystkie nuty w teście mają teraz tę samą długość 0,18 s (wcześniej 0,07-0,22 s). Dołki przy v2-3 i v7 znikają, szum spada o ok. 0,2-0,3 dB. Wyniki są porównywalne ze starszymi (średnia długość prawie ta sama).

## Berlin Concert Grand, C2 i C4 (nowa metoda)
Bez wygładzania (powtórzenia ±0,1-0,4 dB). RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Berlin C2 | -62.4 | -51.5 | -40.7 | -36.0 | -28.0 | -27.0 | 10.9 | 15.6 | 8.0 | 1.0 | 35.5 |
| Berlin C4 | -59.1 | -55.4 | -45.4 | -38.8 | -32.7 | -22.9 | 3.7 | 16.7 | 6.1 | 9.8 | 36.2 |

- C4 czysto: odchylenie od prostej ok. 1,0 dB, powtórzenia ±0,1 dB, jedno drobne odwrócenie (v72 -1,4 dB). Zakres v1-127 ok. 39 dB. Warstwy co ok. 12-15 velocity (v9, 20, 32, 45, 58, 72, 85, 100).
- C2 ma dwie duże wady:
  - v1-6 to jedna płaska warstwa, potem v7 skok +6,9 dB;
  - warstwa v100-116 rośnie za mocno i v116 jest o ok. 5,6 dB głośniejsze niż v124, a v117 spada o -7,1 dB. W basie najgłośniej brzmi więc v116, a v117-127 jest o 5-7 dB ciszej (11 odwróceń).
- Poziom v127 ok. -26 dB (C2) i -22 dB (C4).
- Ogon po puszczeniu klawisza (0,07-0,27 s po zwolnieniu, z włączonym release resonance): ok. 21-25 dB pod atakiem i rośnie razem z velocity (tak samo jak w AIR i Rosewood). W samej głośności nie widać więc stałego poziomu "twangu"; jego jednolitość jest raczej w barwie. Do rozdzielenia: jeden pomiar z wyłączonym release resonance.

## Production Voices Estate Grand Piano 1b, C2 i C4 (nowa metoda)
Ustawienia ze zrzutu: Key Response ON (Strength ok. połowa, przełącznik krzywej Exponential/Sinusoidal), Velocity Smoothing i Authentic Pedalling włączone. RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Estate C2 | -56.2 | -53.2 | -43.8 | -34.2 | -26.9 | -20.8 | 3.0 | 19.0 | 7.3 | 6.1 | 35.3 |
| Estate C4 | -57.5 | -54.7 | -45.4 | -35.2 | -28.4 | -22.1 | 2.9 | 19.5 | 6.8 | 6.3 | 35.5 |

- Najczystszy instrument ze wszystkich pomiarów: powtórzenia ±0,04-0,06 dB, zero skoków powyżej 1,4 dB, zero odwróceń. Jedyna nierówność: v64 -0,7 dB (granica warstwy).
- Gładka krzywa wklęsła: ok. 0,6 dB na krok na dole, 0,45 w v10-40, 0,26 w v40-80, 0,19 na górze. Zakres v1-127 ok. 38,5 dB.
- C2 i C4 praktycznie identyczne (różnica najwyżej 0,58 dB, średnio 0,24 dB): jedna tabela na oba rejestry.
- Barwa zmienia się płynnie (C4 ok. 640 -> 1570 Hz), wyraźniejsza zmiana warstwy tylko ok. v53-64.
- Poziom v127 ok. -20 / -22 dB.
- To nie ta sama krzywa co Kawai EX Pro (w środku Estate ok. 2-3 dB niżej względem v124, dół dużo niżej, i bez powtórzeń ±1,9 dB).
- Do sprawdzenia: czy Velocity Smoothing wygładza tylko przejścia między warstwami, czy uśrednia velocity kolejnych nut. Test rosnącą rampą tego nie rozróżni.

### Estate Grand: Velocity Smoothing wyłączone (C2)
- Głośność prawie bez zmian: różnica względem włączonego najwyżej ok. 1 dB (v40-75), średnio 0,18 dB; od v80 w górę identycznie. Powtórzenia nadal ±0,04 dB, zero odwróceń.
- Zmienia się barwa: bez wygładzania są tylko 4 warstwy próbek (v1-31, v32-63, v64-95, v96-127) i barwa skacze na granicach (środek widma C2: ok. 380 -> 450 -> 950 -> 1090 Hz, przy v64 ponad dwa razy jaśniej z nuty na nutę). Z włączonym wygładzaniem te przejścia rozkładają się płynnie na ok. 20 wartości velocity wokół granic.
- Wniosek: Velocity Smoothing to przenikanie między warstwami, a nie uśrednianie siły kolejnych nut (przy uśrednianiu ramka byłaby przesunięta na całej długości, a od v80 różnica jest zerowa). Bezpieczne do testu celowania; lepiej zostawić włączone.

## Aria Sounds Silk Piano, C2 i C4 (nowa metoda)
Bez wygładzania. RMS ataku, dB.

| | v5 | v10 | v30 | v60 | v90 | v124 | 5-10 | 10-60 | 60-90 | 90-124 | 5-124 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Silk C2 | -32.7 | -32.0 | -29.2 | -24.8 | -18.0 | -12.2 | 0.7 | 7.2 | 6.8 | 5.7 | 20.5 |
| Silk C4 | -39.1 | -38.2 | -31.5 | -28.6 | -23.4 | -17.3 | 0.9 | 9.6 | 5.2 | 6.2 | 21.8 |

- Czyste schodki jak w Hammers and Waves: głośność stała w obrębie warstwy (bez skalowania velocity), zmienia się tylko na granicach.
- C2: 13 warstw po ok. 10 velocity (1-9, 10-19, 20-28, 29-38, 39-48, 49-58, 59-67, 68-77, 78-87, 88-97, 98-106, 107-116, 117-127). Skoki 0,3-4,4 dB (największy v68 +4,4 dB), dół v1-19 prawie płaski (0,7 dB).
- C4: warstwy po 3 velocity (ok. 40 stopni), z kilkoma drobnymi odwróceniami do -0,6 dB (np. v10, v58, v89).
- Wąski zakres: v1-127 ok. 20,5 dB (C2) i 24 dB (C4).
- Najgłośniejszy instrument z mierzonych: v127 ok. -12 dB (C2) i -17 dB (C4).
- C2 i C4 różnią się kształtem (do ok. 5 dB).
- Ogon po zwolnieniu klawisza: ok. 18-20 dB pod atakiem, w C4 jaśniejszy niż sam atak (więcej energii powyżej 2 kHz po zwolnieniu niż przy uderzeniu); w Berlinie, Rosewood i AIR ogon jest ciemniejszy niż atak. To samo widać jednak w Estate, więc ten pomiar sam nie opisuje "sitarowego" brzmienia; widmo ogona jest harmoniczne, podobne do Berlina.
