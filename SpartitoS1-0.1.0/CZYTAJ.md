# Spartito S1 0.1.0 (15.11.2026)

Twoje Spartito z Max for Live jako wtyczka VST3 do Studio One. Okno jest to samo co w Live: ten sam pasek (UNDO, ADD, SELECT, wartości nut, kropka, triola, łuk, tryl, przednutka, znaki, 8va, DELETE, tonacja, PIANO, VEL, HEAR, rozmiar, S/M/L, eksporty), ta sama partytura, te same gesty myszy i klawisze. Pod spodem działa Twój spartito.js bez zmian (poza dwoma zdaniami, które mówiły o Live).

## Instalacja
1. Zamknij Studio One.
2. Uruchom „Zainstaluj Spartito S1.bat” (poprosi o uprawnienia administratora).
3. Otwórz Studio One. Wtyczka jest w przeglądarce: Instruments → Miki → Spartito S1.

## Ustawienie w Studio One
1. Przeciągnij Spartito S1 na pustą przestrzeń ścieżek. Powstanie nowa ścieżka instrumentu.
2. Wejście tej ścieżki: **Keystation Pedal Modes, kanał 1** (nie „All channels”: na kanałach 2, 3, 10 i 16 gra zespół Trenera i trafiłby do nut).
3. Włącz monitorowanie ścieżki (ikona głośnika). Uzbrajać do nagrywania nie trzeba.
4. Wtyczka nie wydaje dźwięku. Słyszysz pianino ze swojej ścieżki „Ja”, jak zawsze.

## Jak działa
- **REC** (pierwszy przycisk, pomarańczowy = włączony): to, co gra ta ścieżka, wpisuje się do nut.
  - **Transport Studio One gra:** nuty trafiają do taktów piosenki, numery taktów są te same co w Studio One. Ponowne odtworzenie tej samej partii zastępuje nuty zamiast je dublować.
  - **Transport stoi:** każde nowe granie zaczyna się od nowego taktu, pierwsza nuta to raz. Ujęcie kończy się po 2,5 s ciszy.
  - Każde ujęcie to jeden krok **UNDO**.
  - Żeby zobaczyć gotową partię z piosenki: skopiuj ją na ścieżkę Spartito (albo ustaw wyjście tamtej ścieżki na Spartito) i odtwórz.
- **CLEAR**: pusta partytura (UNDO przywraca).
- Edycja jak w Live: ADD pisze kliknięciem na pięciolinii, kliknięcie nuty zaznacza i przeciąga, prawy klik albo Ctrl+klik usuwa, SELECT zaznacza prostokątem. Klawisze: 2–7 wartości, kropka, minus/plus znaki, Delete/Backspace usuwa, Ctrl+Z/Ctrl+Y cofnij i ponów. Kółko myszy przewija.
- **Tytuł**: kliknij „untitled - click to name” na pasku stanu.
- **HEAR**: kliknięta nuta brzmi na Twoim pianinie przez router (jak w Trenerze). Bez routera nic się nie dzieje.
- **S / M / L**: rozmiar okna (1000×640, 1200×760, 1400×820).
- **MIDI / PDF / PNG / MUSICXML**: pyta, gdzie zapisać (domyślnie Dokumenty\Spartito). Plik .mid przeciągasz na ścieżkę w Studio One.
- Partytura zapisuje się razem z piosenką Studio One.

## Czego nie ma (i dlaczego)
- Wtyczka VST3 nie może zmieniać partii Studio One, więc edycja nie wraca sama do partii. Drogą powrotną jest eksport MIDI.
- Miniatury z paska urządzenia Live nie ma, bo Studio One nie ma takiego paska.

## Czcionki
Na Windows wtyczka bierze prawdziwe Arial i Times New Roman z systemu, więc tekst wygląda jak w Maxie. Awaryjnie używa Arimo i Tinos (licencja OFL, pliki w `zrodla/assets`): mają te same szerokości liter.

## Źródła (`zrodla`)
- `js/spartito.js`: Twój plik z B:\Spartito, bez zmian;
- `js/prelude.js`: zastępcy obiektów Maxa (mgraphics, File, MGraphics, outlet);
- `js/glue.js`: to, co w Live robił mózg (REC, zapis, eksport), REC i CLEAR na pasku, pasek stanu;
- `js/build.py`: skleja te trzy pliki w `assets/spartito-s1.js` i podmienia dwa zdania o Live;
- `src/`: wtyczka w Rust (nih-plug, QuickJS, tiny-skia);
- `vendor/nih_plug_egui`: kopia z jedną zmianą (przyciski S/M/L zmieniają rozmiar okna).

Budowanie: `python3 js/build.py`, potem `cargo build --release --target x86_64-pc-windows-gnu`. Testy: `cargo test --release`. Podgląd bez okna: `cargo run --release --example snap -- podglad.png`.
