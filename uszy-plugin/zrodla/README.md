# Uszy: źródła wtyczki VST3 (Rust, nih-plug)

Wtyczka mierzy głośność (LUFS momentary 400 ms i short-term 3 s, szczyt) i przepuszcza dźwięk z ustawionym wzmocnieniem.
Co 250 ms zapisuje `%LOCALAPPDATA%\CodexPedalModes\uszy\<id>.json`. Wzmocnienie ustawia się plikiem `<id>.set.json` `{"gain_db": x}`,
a zapamiętuje w `<id>.gain`. Opis działania i wyniki: dokument projektu „Spiew” `claude/studio-one-uszy.md`.

## Dwie wersje z jednego kodu
Kod w `src/lib.rs` jest w wersji **Uszy2** (`NAME = "Uszy2"`, `VST3_CLASS_ID = b"MikiUszyMeterAI2"`).
Zwykłe **Uszy** to ten sam kod z `NAME = "Uszy"` i `VST3_CLASS_ID = b"MikiUszyMeterAI1"`.
Nie zmieniaj tych identyfikatorów, bo Studio One przestanie rozpoznawać wtyczki w zapisanych projektach.

## Budowanie (Linux, cross-kompilacja na Windows)
```
rustup target add x86_64-pc-windows-gnu
apt install mingw-w64            # linker: skopiuj cargo-config.toml do .cargo/config.toml
cargo build --release --target x86_64-pc-windows-gnu
```
Wynik: `target/x86_64-pc-windows-gnu/release/uszy.dll`. Zainstalowana wtyczka to **ta sama dll jako jeden plik**
`Uszy.vst3` / `Uszy2.vst3` (tak działa w Studio One 7; folder `Uszy.vst3` w uszy-plugin to stara próba). Instalacja: „Zainstaluj Uszy.bat” (kopiuje do
`C:\Program Files\Common Files\VST3`, wymaga administratora). Sprawdzone offline: sinus 997 Hz, amplituda 0,1 → −20,0 LUFS.
