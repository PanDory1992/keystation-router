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
