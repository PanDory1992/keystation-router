# Biblioteki instrumentów - rozszerzenie skanera Studio One

Ten wykaz uzupełnia `studio-one-plugins.csv`. Skaner DAW wykrywa wtyczkę, ale nie jej banki brzmień. Wiersze opierają się na lokalnym rejestrze, katalogach i plikach; nie potwierdzają aktywacji licencji ani tego, że każdy bank otwiera się w projekcie.

## Zakres

- Analog Lab V / Arturia: 51 pozycji
- EZkeys 2: 81 pozycji
- Ivory VST: 1 pozycja
- Kontakt 8: 19 pozycji
- Pianoteq 9: 1 pozycja
- Pianoverse: 1 pozycja
- Reaktor 6: 1 pozycja

Plik `studio-one-library-instruments.csv` zawiera 335 znalezionych instrumentów i multis Kontakt (.nki, .nkm). W katalogach użytkownika Reaktor nie znaleziono projektów .ens/.ism.

## Wymagające uwagi

- Kontakt 8: Claire - Avant - wskazana ścieżka nie istnieje.
- Ivory VST: Biblioteka ustawiona w Ivory - wskazana ścieżka nie istnieje.
- Pianoverse: lokalna baza `instruments` jest pusta; konieczny test z poziomu wtyczki.
- Arturia: katalogi presetów nie dowodzą instalacji wszystkich oddzielnych instrumentów Arturia.
- EZkeys MIDI: pliki stylów i fraz są oddzielone od banku dźwiękowego Session Grand.

Pliki są kodowane jako UTF-8 z BOM, żeby polskie znaki otwierały się prawidłowo w Excelu.
