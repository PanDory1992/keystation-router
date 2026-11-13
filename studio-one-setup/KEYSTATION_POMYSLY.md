# Keystation Pro 88 – pomysły na dalsze mapowanie

Stan na 28.10.2026. Do zrobienia później; nic z tego nie jest jeszcze wdrożone.

## Co już działa (punkt wyjścia)

- Router `pedal_router.py` (autostart) dzieli klawiaturę na dwa porty: **Keystation Pedal Modes** (granie) i **Keystation Control** (sterowanie).
- Studio One: urządzenia *Keystation Pro 88* (zwykła klawiatura → VelCal → Pianoteq/Kontakt), *Keystation Control* (profil w `User Devices\keystation-control`), *MCP Bridge*.
- C1–C9 głośność kanałów i Main, C52–C60 powrót na 0 dB, B44/B45 uzbrojenie/odsłuch, B46–B48 pedały, B49–B51 metronom/cofnij/zapisz, transport.
- 24 pokrętła B10–B33 → Pianoteq (mapa „Keystation Pro 88”). Kontakt: do zrobienia „Learn” wg tego samego schematu.

## Gdzie można mapować (4 piętra)

| Piętro | Gdzie | Do czego |
|---|---|---|
| 1. Klawiatura (P10) | sam Keystation | strefy, kanały, toggle, nuty z przycisków – nie ruszać bez ponownego pomiaru |
| 2. Router | `AppData\Local\CodexPedalModes\pedal_router.py` | dowolna przemiana komunikatów, tryby, Shift, przytrzymanie |
| 3. Profil Studio One | `KeystationControl.surface.xml` | mikser, transport, ~1000 komend Studio One, makra |
| 4. Instrument | mapa Pianoteq `.ptm`, Learn w Kontakcie | parametry brzmienia; w Pianoteq też akcje (preset, A/B) |

## Niewykorzystany sprzęt (wg instrukcji M-Audio)

- Drugie gniazdo **sustain** i gniazdo **pedału ekspresji**.
- Kółko **modulacji** i **pitch bend** (dochodzą do instrumentów, w pianinach nic nie robią).
- **4 strefy** (split/layer).
- **CTRL MUTE** i **SNAP SHOT**.
- Wyjście **MIDI DIN** (Keystation jako interfejs MIDI do Yamahy).
- Skrajne klawisze (A0, C8) jako przyciski przez router.

## Pomysły – od największej korzyści

1. **Trzy prawdziwe pedały.** Drugi pedał (np. drugi BFS-40, ok. 40–60 zł) w drugie gniazdo sustain; router zamienia go na una cordę albo sostenuto. B47/B48 przestają być potrzebne do gry. *Wymaga zakupu + pomiaru, co wysyła drugie gniazdo.*
2. **A/B pianin bez myszy.** Akcje mapy Pianoteq: następny/poprzedni preset, Compare (A/B), wczytaj konkretny preset. Np. klawisze numeryczne = ulubione fortepiany, jeden przycisk = przełącznik A/B. *Bez zakupów.*
3. **„Złap, co zagrałem”.** Komenda Studio One `Track → Recall Retrospective Recording` na przycisk (fraza zagrana bez nagrywania ląduje na ścieżce jako MIDI) + `Marker → Insert` na drugi („tu był dobry pomysł”). *Bez zakupów.*
4. **Warstwa Shift.** Jeden przytrzymany przycisk = druga funkcja wszystkiego: drugi zestaw 24 pokręteł (Kontakt/efekty), suwaki → wysyłki na pogłos, transport → `Transport → Tap Tempo`, pętla. *Bez zakupów.*
5. **Pedał ekspresji** (ok. 50–80 zł): pogłaśnianie smyczków/padów albo dynamika Pianoteq na nodze.
6. **Lewa/prawa ręka.** Strefy + router: dół = bas/Rhodes (Kontakt/Arturia), góra = Pianoteq, obie strony przez VelCal.
7. **Yamaha jako moduł brzmieniowy.** Keystation (ważona klawiatura) → DIN → PSR-E433; w Studio One ścieżka *External Instrument*; audio Yamahy do UM2 przez INST 2 (mono).

Od razu, bez zakupów, da się zrobić 2 + 3 + 4 w jednym podejściu.

## Sztuczki na skaczące suwaki (działają już teraz)

- **CTRL MUTE** → ustaw suwaki/pokrętła → **CTRL MUTE** ponownie: nic nie skacze.
- **SNAP SHOT** (+ i − naraz): wysyła położenie wszystkich kontrolek, program dopasowuje się do klawiatury.

## Ograniczenia

- Studio One nic nie odsyła na klawiaturę (brak diod, silniczków, podglądu wartości).
- Kontakt: pokrętła zawsze przez jednorazowe Learn w oknie wtyczki.
- Most MCP widzi mierniki instrumentów jako ciszę – brzmienie sprawdza się uchem.

## Inne otwarte tematy

- Learn pokręteł w bibliotekach Kontakt (NOIRE, Claire, Alicia's Keys, Silk Piano, Piano in Blue).
- Listen Bus + Altitude Crossfeed: Crossfeed siedzi w sekcji „Post” kanału Main, nie na Listen Busie.
- Charczenie Yamahy A-05 na transjentach – test poziomu wejścia AUX (ściszyć Main o ~10 dB, podgłośnić A-05).
- Stara kartka A4 Codexa (`Keystation_Pro_88_mapa_Studio_One_A4_poziomo.pdf`) jest nieaktualna – zastąpiona nową ściągawką.
