> **23.11 (Claude):** krzywa X usunieta na prosbe Mikiego. Zostaje AX (A z wlasnym mnoznikiem czarnych), mnoznik
> zmieniony z 1,0 na 1,14: zmierzony na grze 19-23.11 (akordy czarne+biale: 1,13; sasiednie nuty: 1,16).
> Wtyczka zbudowana od nowa (etykieta "RÓWNA AX (CZARNE 1,14)"). Opis ponizej dotyczy stanu z 21.11.

# AI handover — 2026-11-21

## Scope completed

Added a Mega velocity curve `rowna-x` and made it visible in the Keystation Status VST3 UI.

### `rowna-x` semantics

- Authoritative runtime config: `mega-krzywa.json`.
- Curve parameters: `rozrzut`, `t_top_us: 5200`, `t_bot_us: 208400`, `v_top: 127`, `v_bot: 2`.
- Thus for white keys: 5.2 ms maps to MIDI velocity 127; 208.4 ms maps to 2.
- **Only `rowna-x` overrides black-key compensation:** `rozrzut.czarne_mnoznik: 1.0`. For X, equal measured contact time means equal output velocity for black and white keys. Other curves continue to use the top-level `czarne_mnoznik: 1.28`.
- Router implementation: `mega_input.note_velocity_exact()` reads a curve-level `rozrzut.czarne_mnoznik`, falling back to the top-level setting.
- C53 order for the active JSON file: `rowna-a → rowna-b → rowna-c → rowna-x → naturalna → rowna-a`.

## Changed files

- `mega_input.py`
  - `DEFAULT_CURVES` contains `rowna-x`.
  - curve validation accepts optional positive `rozrzut.czarne_mnoznik`.
  - black-key timing calculation honors this curve-level override.
- `mega-krzywa.json`
  - defines the active `rowna-x` parameters above.
- `test_mega_input.py`
  - covers X values, C53 cycling, and black=white behavior at equal time.
- `KeystationStatus-0.13.0/zrodla/src/live.rs`
  - `MegaCurve::Rozrzut` parses optional `czarne_mnoznik` and uses it for plot velocity calculation.
- `KeystationStatus-0.13.0/zrodla/src/photo.rs`
  - labels: `RÓWNA X (127 = 5,2 MS)` and `RÓW.X`; tooltip includes X.
  - Mega plot uses the router's rounded MIDI velocity and a denser curve sample, so note columns no longer appear above a continuous (fractional) curve.

## Build/install state

- Installed Rust MSVC toolchain (`rustup`, stable `x86_64-pc-windows-msvc`) and Visual Studio 2022 Build Tools with a Windows SDK.
- The 0.13 source snapshot originally lacked `zrodla/assets/`, although `include_bytes!` requires it. Restored the required assets by copying `KeystationStatus-0.10.0/zrodla/assets/` to `KeystationStatus-0.13.0/zrodla/assets/`.
- Build command (run from `KeystationStatus-0.13.0/zrodla`):

  ```bat
  call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
  C:\Users\mikit\.cargo\bin\cargo.exe build --release -j 1
  ```

- Built DLL: `KeystationStatus-0.13.0/zrodla/target/release/keystation_status.dll`.
- Copied it to both:
  - `KeystationStatus-0.13.0/KeystationStatus.vst3/Contents/x86_64-win/KeystationStatus.vst3`
  - `C:\Program Files\Common Files\VST3\KeystationStatus.vst3\Contents\x86_64-win\KeystationStatus.vst3`
- The latter requires elevation; use `KeystationStatus-0.13.0/Zainstaluj Keystation Status.bat` after copying the packaged DLL.
- Final SHA-256 for source DLL, packaged DLL, and installed DLL was identical:
  `B9849082C9EAF4A5A927DAB5C6A19CFDF39306765C42100A450D230C0C7B8F7C`.

## Verification performed

- Python check against the active JSON: for X, white note at 10,000 µs and black note at 10,000 µs both return velocity 77.
- Rust unit test `live::mega_tests::rowna_x_has_no_black_key_multiplier` passes.
- Installed VST3 binary hash matched the release build.
- Restart Studio One before expecting the new binary/UI to load.

## Gotcha

`czarne_mnoznik: 1.0` removes physical geometry compensation only for X. This deliberately makes equal *measured* times equal; equal playing intent may still produce different measured times on black and white keys. Do not change the top-level 1.28 unless the intent is to alter every other Mega curve.
