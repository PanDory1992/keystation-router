# Keystation: router MIDI, nadzorca, szyna UDP i wtyczki

Domowy system Mikiego do gry na M-Audio **Keystation Pro 88** (mechanika młoteczkowa, przebudowana bez sprężyn) z **Studio One 7** na Windows. Wszystko pisane z Claude, październik–listopad 2026. Folder na PC: `C:\Users\mikit\AppData\Local\CodexPedalModes`.

Trener (aplikacja do nauki) ma osobne repozytorium: **PanDory1992/trener** (folder `trener/` jest tu pominięty).

## Tor sygnału
```
Keystation Pro 88 ──USB──> pedal_router.py
                             ├─ port „Keystation Pedal Modes”  → Studio One: instrumenty (nuty, pedały, 24 gałki jako CC)
                             ├─ port „Keystation Control”      → Studio One: powierzchnia sterująca (suwaki, transport, przyciski)
                             ├─ port „Keystation Monitor”      → kopia zagranych nut (po mapowaniu)
                             └─ szyna UDP 127.0.0.1:47800 (udp_bus.py) → Trener, wtyczki, podgląd
```

## Pliki
| Plik | Co robi |
|---|---|
| `pedal_router.py` | Router MIDI: rozdziela granie i sterowanie na dwa porty, tryby pedału (sustain / sostenuto, una corda), miękkie puszczanie sustainu (`release-ms`), krzywe velocity, „kontekstowe 1” (najcichsze uderzenia), łata na dziurę 1–40 w czarnych klawiszach, nagrywanie surowych zdarzeń (`capture-notes` → `notes.csv`). Opis na początku pliku. |
| `udp_bus.py` | Szyna UDP (protokół v1, JSON w datagramach, tylko localhost). Słuchacz wysyła `hello` co ≤5 s (inaczej wypada po 10 s), dostaje `welcome` + `state`; zdarzenia `note`, `pedal`, `state`, `button`; polecenia `set` (tryb, una corda, czułość, „jedynki”) i `play` (granie przez router). Opis protokołu na początku pliku. |
| `keystation_supervisor.py` | Nadzorca uruchamiany przy logowaniu: pilnuje routera, mostu Studio One (`studio_one_bridge.py`, leży w folderze `studio-one-setup` poza tym repo) i serwera Trenera (port 47810). Każdy start, wyjście i błąd w `supervisor.log`. |
| `szyna_podglad.py` | Podgląd szyny na żywo (konsola). |
| `velocity-map*.json` | Krzywe velocity `{"white":[128], "black":[128]}` (indeks = surowa siła). `velocity-map.json` jest aktywna; `acoustic` / `light` / `heavy` to czułości przełączane z wtyczki albo szyny; `v1…v4` to historia kalibracji. `kalibracja-1-surowe-C1-20261028.json` to surowe pomiary. |
| `uszy/` | Stan wtyczek Uszy (pomiary, wzmocnienia, nazwy kanałów). |
| `uszy-plugin/zrodla/` | Źródła wtyczki VST3 **Uszy** (Rust, nih-plug): pomiar LUFS i wzmocnienie, sterowane przez most MCP (`uszy_*`). Budowanie: `README.md` w środku. |
| `keystation-status-plugin*/`, `KeystationStatus-0.2.1/` | Źródła wtyczki VST3 **Keystation Status** (Rust): stan routera na żywo w Studio One (tryb, pedał, czułość), czyta `live.json` / `status.json`. `CZYTAJ.txt` opisuje instalację. |
| `test_pedal_router.py`, `test_udp_bus.py` | Testy (pytest). Na Windows, bo `vendor/rtmidi` to binarka Windows. |
| `vendor/` | python-rtmidi 1.5.8 (Windows). |
| `Router - restart.bat`, `Nadzorca - restart.bat`, `Szyna - podglad.bat`, `install-autostart.ps1`, `startup-backup/` | Restart routera (plik `restart-router`), restart nadzorcy, podgląd szyny, autostart z Windows. |
| `*.before-*.py` | Kopie routera i nadzorcy sprzed każdej większej zmiany (historia sprzed gita). |
| `mapa-06.11-z-zalecane-light.pdf` | Mapa velocity klawiatury. |

## Pliki ustawień w locie (nie w gicie)
`touch-mode`, `ones-mode`, `release-ms`, `debug-raw.off`, `restart-router`, `live.json`, `status.json`, `live-cmd.json`, `notes.csv`, logi. Router czyta je na bieżąco; zmienia je wtyczka Keystation Status albo szyna (`set`).

## Kanały MIDI (umowa z Trenerem i projektem Studio One)
1 twoje pianino (tylko klawiatura), 2 bas zespołu, 3 wszystko, co Trener gra na pianinie, 10 perkusja, 16 klik.

## Zasady
- Przed zmianą routera lub nadzorcy: `git commit` (albo kopia `*.before-<co>-RRRRMMDD.py`), potem testy na Windows, potem „Router - restart.bat”.
- Nie commitować: `klucz-telefonu.txt`, danych Trenera, logów, binariów `.vst3` i `.zip` (zbudować ze źródeł).
- Most MCP do Studio One: repozytorium **PanDory1992/studio-one-mcp**, gałąź `miki-poprawki` (opis w `MIKI.md`).
