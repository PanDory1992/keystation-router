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
