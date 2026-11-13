# Studio One 7 + Keystation Pro 88: sterowanie i pierwsze kroki

## Aktualizacja 28 października 2026

Poniższy opis dokumentuje pierwszy profil z 23 października. **Aktualna mapa** jest na kartce A4 w `output/pdf/Keystation_Pro_88_mapa_Studio_One_A4_poziomo.pdf`. Także strona 3 starszego pełnego przewodnika PDF opisuje dawny układ przycisków; w razie rozbieżności obowiązuje nowa kartka A4. B46/B47/C60 wybierają funkcję fizycznego pedału: sustain, sostenuto, celeste. **B48 włącza/wyłącza una corda niezależnie od fizycznego pedału.** Funkcje mute/solo/loop/metronom przypisane tym przyciskom w starszej tabeli nie są aktualne. B49 pozostaje metronomem, B50 cofaniem, B51 zapisem. Lokalny router `Keystation Pedal Modes` przekazuje nuty i dynamikę bez zmian, obsługuje pedały oraz normalizuje fizyczne B18–B33 do CC104–CC119. Most Studio One ma aktywne `live_eval`. Szczegóły i granice testów: `output/pedal_modes/PEDAL_STATUS_PL.md`; plan parametrów fortepianów: `output/pedal_modes/MAPA_POKRETEL_PIANO_PL.md`. Dalsze tabele tego pliku opisują historyczny pierwszy profil, nie stan wszystkich bieżących przycisków.

W bieżącym projekcie instrument Pianoteq jest w trybie bypass. Na potrzeby odsłuchu funkcji celeste trzeba go włączyć; sama mapa MIDI została sprawdzona na Pianoteq poza Studio One.

Stan z 23 października 2026. Studio One jest otwarte na projekcie `2026-10-06 mikit`. Klawiatura pozostaje na pamięci **P10** i krzywej dynamiki **C7**. Tor gry **Keystation → VelCal White5/Black15 → Pianoteq 9** został zachowany.

## Sterowanie przez agenta

Zainstalowany jest lokalny most `studio-one-local` oparty na [studio-one-mcp](https://github.com/NeanderthalMan/studio-one-mcp). Studio One uruchamia wewnętrzny moduł, który odczytuje i zmienia stan otwartego projektu. Lokalny port MIDI wybudza moduł, a żądania i odpowiedzi przechodzą przez folder na tym komputerze. Most nie steruje kursorem i nie wymaga internetu. `live_eval` jest obecnie aktywne; nie daje jednak dostępu do wewnętrznych parametrów instrumentów VST w racku. Wynik badania Kontakt i Pianoteq: [MAPA_POKRETEL_PIANO_PL.md](../pedal_modes/MAPA_POKRETEL_PIANO_PL.md).

Sprawdzono na żywym projekcie: odpowiedź mostu, nazwę utworu, pozycję i stan transportu, listę kanałów, zmianę głośności kanału Kontakt i dokładne przywrócenie poprzedniej wartości, odtwarzanie i zatrzymanie oraz zapis projektu. `live_channels` potwierdziło wartości po zmianach.

Most ładuje się ze Studio One. Port `Codex Studio One Control` startuje po zalogowaniu do Windows przez skrót w Autostarcie. Konfiguracja MCP jest zarejestrowana globalnie w Codex jako `studio-one-local`.

## Mapa sprzętowa

| Element | Funkcja |
|---|---|
| **C1–C8** | Głośność **pierwszych ośmiu kanałów miksera** kolejno od lewej. W obecnym projekcie C1 to `01- MIDI MASTER` (VelCal), C2 to `KT Out 1` (Kontakt), C3 to `Output` (Pianoteq), C4 to `Analog Lab V`. Wybranie innej ścieżki nie zmienia tej kolejności. |
| **B10–B17** | Panorama tych samych ośmiu kanałów, też kolejno od lewej. |
| **C52–C59**, przyciski pod suwakami | Przywracają głośność odpowiednich kanałów do **0 dB**, czyli poziomu neutralnego. To nie jest wyciszenie. |
| **C9** | Głośność główna Main; porusz ostrożnie przy cichym odsłuchu. |
| **Play, Stop, Record, Rewind, Forward** | Transport Studio One. Play i Stop potwierdzone wcześniej na fizycznej klawiaturze. |
| **B18–B33** | 16 pokręteł dostępnych w Control Link do parametrów aktualnie używanej wtyczki. Wewnętrzne parametry każdej wtyczki wymagają osobnej mapy. |
| **B44–B47** | Dla aktualnie wybranego kanału: uzbrój do nagrania, odsłuch, wycisz, solo. |
| **B48–B51** | Pętla, metronom, cofnięcie, zapis projektu. |
| **C60** | Metronom. |

Mapa suwaków C1–C8 używa numerów MIDI **73, 72, 91, 93, 74, 71, 5, 84**, zgodnych z C1–C3 odczytanymi na Twojej klawiaturze oraz [mapą tego modelu w Ableton Live](https://github.com/gluon/AbletonLive11_MIDIRemoteScripts/blob/main/Keystation_Pro_88/consts.py). B10 używa MIDI CC10, zgodnie z Twoim odczytem. Fabryczne przyciski P10 są w trybie `Program/Bank` (kod 145). Na klawiaturze odczytano **C52 = program 08, C53 = program 09, kanał globalny c00**. Profil obsługuje C52–C59 jako numery 08–15; pozostałe numery są wywnioskowane z kolejności, a nie odczytane fizycznie. Numery 00–07 dla B44–B51 również są wnioskowane. Instrukcja podaje ogólną tabelę MIDI i P10 jako „Defaults for learn”, lecz nie zawiera pełnej tabeli fabrycznych przypisań P10.

Wewnętrzny test Studio One potwierdził po przeładowaniu nowej mapy: wirtualne CC73/CC72/CC91 zmieniają kolejno kanał 1/2/3; CC10 zmienia panoramę kanału 1; Program Change 08/09/10 przywracają odpowiednio kanał 1/2/3 do 0 dB. Wirtualne CC27 uzbraja wybrany kanał do nagrania. Po każdym teście przywrócono poziomy, panoramę i stan uzbrojenia/odsłuchu. Testy dowodzą działania profilu w Studio One, ale nie dowodzą jeszcze, że fizyczny przycisk emituje dokładnie te bajty.

## Co oznacza „uniwersalne”

Suwaki, panorama i przywracanie 0 dB dotyczą **kolejności kanałów miksera**, więc działają niezależnie od instrumentu lub efektu na kanale. Zaznaczenie ścieżki wpływa na B44–B47, ale nie przesuwa C1–C8. Jeśli kanał Pianoteq jest trzeci w mikserze, odpowiadają mu C3, B12 i C54. Po zmianie kolejności kanałów kolejność na klawiaturze też się zmieni.

Parametry **wewnątrz** każdej wtyczki mają różne nazwy i zakresy. Studio One Control Link zapamiętuje mapę osobno dla wtyczki; nie ma jednej sensownej funkcji pokrętła „Cutoff” dla każdego korektora, pogłosu i fortepianu. B18–B33 to pula 16 pokręteł do takich map. Odczytaliśmy listę wtyczek wykrytych przez Studio One: [studio-one-plugins.csv](studio-one-plugins.csv) zawiera 135 wpisów skanera (19 instrumentów, 116 efektów, 124 różne nazwy). Most na żywo wykrył m.in. Pianoteq 9, Kontakt 8, Analog Lab V oraz efekty Pro EQ i Room Reverb. Lista wtyczek nie oznacza jeszcze mapy każdego ich parametru.

Gdy zechcesz przypisać B18 do jednego konkretnego parametru wtyczki: otwórz tę wtyczkę, upewnij się, że jej przycisk **Focus** pokazuje Keystation, porusz żądanym parametrem, porusz B18, a następnie użyj ikony połączenia w górnym pasku Studio One. Taką mapę Focus Studio One zapamiętuje dla danego rodzaju wtyczki i wykorzystuje też w innych utworach. [Opis Focus Mapping od PreSonus](https://support.presonus.com/hc/en-us/articles/210050323-Studio-One-3-Global-and-Focus-MIDI-Mapping).

## Granie, śpiew i nagrywanie

1. **Graj:** Na ścieżce `01- MIDI MASTER` pozostaw wejście Keystation i włączony Monitor. Ta ścieżka przepuszcza nuty przez VelCal. Na ścieżce Pianoteq wejściem jest VelCal, a Monitor również ma być włączony. Nie ustawiaj jednocześnie bezpośredniego wejścia klawiatury na Pianoteq, bo można uzyskać podwójne nuty.
2. **Zmieniaj instrument:** Dodaj instrument na nową ścieżkę, ustaw jej wejście na VelCal i włącz Monitor. Wyłącz Monitor innych instrumentów, chyba że chcesz je świadomie nakładać.
3. **Nagraj piano:** Uzbrój ścieżkę instrumentu do nagrania (przycisk z kropką), włącz Monitor, naciśnij Record. Powstaną edytowalne nuty MIDI. Stop kończy nagranie, Save zapisuje projekt.
4. **Nagraj głos:** Dodaj ścieżkę audio mono, wybierz wejście mikrofonu interfejsu UM2, uzbrój ją i sprawdź poziom przy najgłośniejszej frazie. Monitoruj głos albo przez UM2, albo przez Studio One, aby nie słyszeć podwójnego odsłuchu z opóźnieniem.
5. **Gdy brak dźwięku:** Sprawdź kolejno wejście Keystation na VelCal, Monitor VelCal, wejście VelCal na ścieżce instrumentu, Monitor instrumentu oraz wyjście Main na UM2.

Wcześniejszy test MIDI pokazał, że klawiatura wysyła prawidłowe `Note On` z bardzo małym velocity i `Note On 0` jako zwolnienie nuty. Nie zmienialiśmy C7 ani kalibracji VelCal podczas instalacji mostu.

## Wynik kontroli i pozostający test fizyczny

- Most odpowiedział, odczytał niezapisany stan, zmienił i przywrócił mikser oraz uruchomił i zatrzymał transport.
- Natywny profil po restarcie załadował się bez błędu; wirtualne komunikaty C1, C2, C3, B10, C52, C53, C54 i B44 zmieniły właściwe kanały/funkcje, a wartości odtworzono.
- Tor nut z fizycznej klawiatury pozostał bezpośredni, więc żaden pośrednik programowy nie opóźnia gry na pianinie.
- Fizyczne C52–C59, B11–B33, B44–B51, C9 oraz Record nie zostały jeszcze naciśnięte w końcowym profilu. Ich działanie nie jest oznaczone jako potwierdzone. Użytkownik odczytał numery programów 08/09 z pamięci C52/C53; to nie jest pomiar wysłanego komunikatu MIDI. Test fizyczny jest ostatnim poziomem potwierdzenia. Własne mapy parametrów wszystkich 124 rodzajów wtyczek również nie zostały wykonane.
- **Ryzyko do obserwacji:** odłączenie uzbrojenia B44 może w Studio One wyłączyć odsłuch wybranego instrumentu; wtedy włącz B45 (odsłuch). W teście wewnętrznym odsłuch ręcznie przywrócono. Program Change z przycisków może też trafić do instrumentu i zmienić jego preset, zależnie od jego konfiguracji.
- Kopie ustawień i profilu są w [backups](backups). Zainstalowany profil ma kopię [KSPro88.universal.surface.xml](KSPro88.universal.surface.xml). Po aktualizacji Studio One można go przywrócić skryptem [reinstall_universal_surface.py](reinstall_universal_surface.py) po zamknięciu DAW.
