"""Klawisze z Arduino Mega (skaner): czas miedzy stykami -> velocity jak w fortepianie.

19.11.2026: pierwsza wersja (tekst v1). 20.11.2026 (MEGA 2.0): ramki binarne z CRC (mega_protocol.py), czas Megi
przy kazdym zdarzeniu, mapa brzmiacych klawiszy co sekunde (gasimy zawieszone nuty), rozpoznanie zlego programu
na Medze i samodzielne wgranie skanera, nieaktualny plik mega-off juz nie blokuje Megi, zdrowie linii matrycy.

Krzywa (wzor fortepianu Bosendorfer SE, Goebl i Bresin 2003): velocity = 52 + 25 * log2(predkosc mlotka w m/s),
czyli kazde przepolowienie czasu miedzy stykami to +25 velocity. Jedyny punkt zaczepienia: czas, ktory daje
podane velocity (kotwica). Czarne klawisze maja dluzsze czasy przy tej samej sile (inna geometria), wiec ich czas
dzielimy przez staly mnoznik. Parametry w mega-krzywa.json, wczytywane na biezaco.
"""
from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import os
import statistics
import subprocess
import threading
import time
from pathlib import Path

import mega_protocol as mp

BLACK_KEYS = {1, 3, 6, 8, 10}
SLOPE = 25.0               # velocity na podwojenie predkosci (Bosendorfer SE)
RELEASE_CENTER_US = 25000  # mediana czasu puszczenia z gry 19.11 -> velocity puszczenia 64
BAUD = 250_000            # skaner v1.1+ nadaje 250 kbit
PROBE_BAUD = 115_200      # programy test i rozpoznanie
MEGA_VIDS = {0x1A86, 0x2341, 0x2A03}
SILENT_V2_S = 3.5          # v2 melduje sie co 1 s
SILENT_V1_S = 6.0          # v1 co 2 s
OFF_FLAG_MAX_AGE_S = 15.0  # mega.py odswieza plik mega-off co 2 s; starszy = narzedzie zamkniete krzyzykiem
FLASH_LIMIT = 3            # najwyzej tyle wgran na godzine (zabezpieczenie przed petla)
ROOT = Path(__file__).resolve().parent
HEX_DIR = ROOT / "skaner-mega" / "hex"
AVRDUDE = ROOT / "skaner-mega" / "narzedzia" / "avrdude" / "bin" / "avrdude.exe"
AVRCONF = ROOT / "skaner-mega" / "narzedzia" / "avrdude" / "etc" / "avrdude.conf"

# 19.11, gra 9 min: najszybsze 1% bialych 6,9 ms, czarnych 8,7 ms; mediana 15,2 / 22,8 ms.
DEFAULT_CURVES = {
    "naturalna": {"naturalna": {"K": 131.7, "tau_us": 460, "lo": 2, "hi": 118, "floor": 10, "top": 127, "g": 1.7,
                                "pivot": 100}},
    "fortepian": {"kotwica_us": 6500, "kotwica_velocity": 100},
}
# wysoka_rozdzielczosc: przed nuta CC88 z czescia ulamkowa velocity (Pianoteq: 14 bitow).
# min_us (20.11): krotszy czas miedzy stykami to nie uderzenie, tylko artefakt (najszybsze prawdziwe: 5,1 ms).
DEFAULT_SETTINGS = {"krzywa": "naturalna", "czarne_mnoznik": 1.28, "minimum": 2, "wysoka_rozdzielczosc": False,
                    "min_us": 2000, "krzywe": DEFAULT_CURVES}


def load_settings(path: Path) -> dict:
    data = dict(DEFAULT_SETTINGS)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data.update({k: v for k, v in loaded.items() if k in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass
    curves = data.get("krzywe")
    if isinstance(curves, dict):                       # 20.11: zla krzywa w pliku nie moze zatrzymac nut
        curves = {k: c for k, c in curves.items() if curve_ok(c)}
    if not isinstance(curves, dict) or not curves:
        data["krzywe"] = DEFAULT_CURVES
    else:
        data["krzywe"] = curves
    if data["krzywa"] not in data["krzywe"]:
        data["krzywa"] = next(iter(data["krzywe"]))
    return data


def curve_ok(c) -> bool:
    """Krzywa z kotwica {kotwica_us, kotwica_velocity} albo z punktami {punkty: [[us, velocity], ...]} (min. 2)."""
    if not isinstance(c, dict):
        return False
    try:
        if "naturalna" in c:
            p = c["naturalna"]
            return (float(p["tau_us"]) > 0 and float(p["K"]) > float(p["hi"]) > float(p["pivot"]) > float(p["lo"])
                    and 1.0 <= float(p["g"]) <= 2.0)
        if "punkty" in c:
            pts = [(float(u), float(v)) for u, v in c["punkty"]]
            return len(pts) >= 2 and all(u > 0 for u, _ in pts) and len({u for u, _ in pts}) == len(pts)
        return float(c["kotwica_us"]) > 0 and math.isfinite(float(c["kotwica_velocity"]))
    except (KeyError, TypeError, ValueError):
        return False


def curve_value(curve: dict, t: float) -> float:
    """Czas (us, juz po przeliczeniu czarnych) -> velocity przed obcieciem do zakresu.

    Kotwica: wzor Bosendorfera, +25 na kazde przepolowienie czasu. Punkty (20.11, "dopasowana"): linie miedzy
    punktami w skali log2 czasu, poza skrajnymi punktami dalej tym samym nachyleniem co skrajny odcinek."""
    t = max(1.0, float(t))
    if "naturalna" in curve:
        return naturalna_value(curve["naturalna"], t)
    if "punkty" not in curve:
        return curve["kotwica_velocity"] + SLOPE * math.log2(curve["kotwica_us"] / t)
    pts = sorted((math.log2(float(u)), float(v)) for u, v in curve["punkty"])
    x = math.log2(t)
    i = 0
    while i < len(pts) - 2 and x > pts[i + 1][0]:
        i += 1
    (x0, v0), (x1, v1) = pts[i], pts[i + 1]
    return v0 + (v1 - v0) * (x - x0) / (x1 - x0)


# 20.11 (Miki: "feeling jak przed przebudowa, z mozliwosciami Megi, zgodny z fortepianem"): Naturalna z 16.11 liczona
# z prawdziwego czasu. Zielona plytka mierzyla ten sam czas miedzy stykami: surowe = K - t/tau (K = 131,7 z rozrzutu
# reki, RAPORT-naturalna). tau = 460 us z dopasowania rozkladow tej samej reki: 83 275 bialych nut z zielonej plytki
# (W46-W47) i 689 z Megi; mediana: surowe 99 <-> 14,8 ms (tau 452), kwartyle 454-482. Sprawdzenie: Twoje najmocniejsze
# 1% (6,0 ms) = surowe 118,6, a w Naturalnej p99 surowe 118 = 127. Krzywa ta sama co w routerze (128/128 wartosci),
# ale ciagla: bez 9 schodkow, bez dziury czarnych, bez odszumiania i bez regul dla "1". Ponizej surowego 2 (wolniej niz
# prog zielonej plytki) dalej koncowym nachyleniem S (jak ledwo dotkniety mlotek), az do minimum.
NATURALNA_MEGA = {"K": 131.7, "tau_us": 460, "lo": 2, "hi": 118, "floor": 10, "top": 127, "g": 1.7, "pivot": 100}


def naturalna_raw_value(p: dict, r: float) -> float:
    """Naturalna (velocity-map.naturalna.json) jako ciagla funkcja surowego velocity r."""
    K, lo, hi, g, pivot = float(p["K"]), float(p["lo"]), float(p["hi"]), float(p["g"]), float(p["pivot"])
    floor, top = float(p.get("floor", 10)), float(p.get("top", 127))
    r = min(r, K - 1e-6)
    ls = lambda x: -math.log(K - x)  # noqa: E731  log predkosci klawisza
    span = ls(hi) - ls(lo)
    n = (ls(r) - ls(lo)) / span
    if r < lo:
        n *= (2 - g)
    elif n > 1:
        n = 1 + (n - 1) * (2 - g)
    else:
        P = (ls(pivot) - ls(lo)) / span
        up = n >= P
        a = (n - P) / (1 - P) if up else (P - n) / P
        h = a * (g - (g - 1) * a)                 # nachylenie g w srodku, 2-g na krancach (filcowy mlotek)
        n = P + (1 - P) * h if up else P - P * h
    return floor + (top - floor) * n


def naturalna_value(p: dict, t: float) -> float:
    return naturalna_raw_value(p, float(p["K"]) - t / float(p["tau_us"]))


def note_velocity_exact(midi: int, us: int, settings: dict) -> float:
    """Czas miedzy stykami (us) -> velocity z czescia ulamkowa, w zakresie minimum..127."""
    curve = settings["krzywe"][settings["krzywa"]]
    t = max(1, int(us))
    if midi % 12 in BLACK_KEYS:
        t = t / float(settings.get("czarne_mnoznik", 1.0))
    v = curve_value(curve, t)
    return max(float(settings.get("minimum", 1)), min(127.0, v))


def note_velocity(midi: int, us: int, settings: dict) -> int:
    return int(round(note_velocity_exact(midi, us, settings)))


def hires_split(v: float) -> tuple[int, int]:
    """Velocity z ulamkiem -> (velocity nuty 1..127, CC88 0..127), standard MIDI CA-031: wartosc = msb + lsb/128."""
    v = max(1.0, min(127.0, v))
    msb = int(v)
    lsb = int((v - msb) * 128)
    return msb, min(127, lsb)


def release_velocity(us: int) -> int:
    """Czas puszczenia (us) -> velocity note-off; 0 (brak pomiaru) = 64."""
    if us <= 0:
        return 64
    return max(1, min(127, int(round(64 + SLOPE * math.log2(RELEASE_CENTER_US / us)))))


def parse_line(line: str):
    """v1: '+ 60 12000' -> ('on', 60, 12000); smieci -> None (zostaje dla zgodnosci i testow)."""
    parts = line.split()
    if len(parts) != 3 or parts[0] not in ("+", "-"):
        return None
    try:
        midi, us = int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if not 21 <= midi <= 108 or us < 0:
        return None
    return ("on" if parts[0] == "+" else "off", midi, us)


NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def note_name(midi: int) -> str:
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def find_port():
    from serial.tools import list_ports
    for p in list_ports.comports():
        if p.vid in MEGA_VIDS or "CH340" in (p.description or ""):
            return p.device
    return None


def flag_active(path: Path | None, now: float | None = None) -> bool:
    """Plik mega-off obowiazuje tylko, gdy jest swiezy (narzedzie zyje i go odswieza)."""
    if path is None:
        return False
    try:
        age = (now if now is not None else time.time()) - path.stat().st_mtime
    except OSError:
        return False
    return age < OFF_FLAG_MAX_AGE_S


def load_manifest(hex_dir: Path = HEX_DIR) -> dict | None:
    """hex/skaner.json: {"proto": 2, "wersja": "2.0", "build": ..., "md5": ...} - czego router oczekuje na Medze."""
    try:
        m = json.loads((hex_dir / "skaner.json").read_text(encoding="utf-8"))
        if isinstance(m, dict) and isinstance(m.get("proto"), int) and isinstance(m.get("build"), int):
            return m
    except (OSError, ValueError):
        pass
    return None


def make_flasher(hex_dir: Path = HEX_DIR, avrdude: Path = AVRDUDE, conf: Path = AVRCONF):
    """Funkcja port -> (ok, opis): wgrywa hex/skaner.hex, ale tylko gdy jego md5 zgadza sie z manifestem."""
    def flash(port: str):
        manifest = load_manifest(hex_dir)
        hexfile = hex_dir / "skaner.hex"
        if manifest is None or not hexfile.exists() or not avrdude.exists():
            return False, "brak skaner.hex, skaner.json albo avrdude"
        digest = hashlib.md5(hexfile.read_bytes()).hexdigest()
        if manifest.get("md5") != digest:
            return False, f"skaner.hex ma inne md5 niz w skaner.json ({digest}), nie wgrywam"
        cmd = [str(avrdude), "-C", str(conf), "-p", "atmega2560", "-c", "wiring", "-P", port, "-b", "115200",
               "-D", "-U", f"flash:w:{hexfile}:i"]
        flags = 0x08000000 if os.name == "nt" else 0        # CREATE_NO_WINDOW: router dziala bez okna
        log = ""
        for attempt in range(3):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=90,
                                   creationflags=flags)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, f"avrdude: {exc}"
            log = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0:
                return True, f"wgrany skaner {manifest.get('wersja')} (proba {attempt + 1})"
            time.sleep(1.5)
        return False, "avrdude: " + " | ".join(log.strip().splitlines()[-3:])
    return flash


def ch340_driver_info() -> str | None:
    """Windows: nazwa i wersja sterownika CH340 (tylko odczyt). Znane problemy: WCH 3.8 / wersje z 2023."""
    if os.name != "nt":
        return None
    ps = ("Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_1A86' } | ForEach-Object { "
          "$v = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverVersion).Data; "
          "$d = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_DriverDate).Data; "
          "$_.FriendlyName + ' | sterownik ' + $v + ' | ' + $d }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           errors="replace", timeout=30, creationflags=0x08000000)
        return r.stdout.strip() or None
    except Exception:
        return None


def analyse_selftest(test: mp.SelfTest) -> list[str]:
    """Wynik testu linii -> zdania po polsku. Ostrozne: twierdzimy cos tylko przy wyraznej roznicy."""
    out = []
    counts = dict(zip(mp.TEST_LINES, test.counts))
    for line in mp.TEST_LINES[:-2]:
        if line in test.stuck:
            out.append(f"Linia {line}: pin nie schodzi do zera (uszkodzony pin Megi?)")
        elif counts[line] >= 255:
            out.append(f"Linia {line}: stale na masie (przewod w GND albo zwarcie?)")
    ref = max(counts["pin43"], counts["pin53"])
    lines = [counts[x] for x in mp.TEST_LINES[:-2] if x not in test.stuck and counts[x] < 255]
    if lines and statistics.median(lines) >= ref + 4:
        for line in mp.TEST_LINES[:-2]:
            if counts[line] <= ref + 1 and line not in test.stuck:
                out.append(f"Linia {line}: zachowuje sie jak pusty pin (przewod nie siedzi w gniezdzie?)")
    return out


class ArtifactFilter:
    """Nuta z czasem miedzy stykami krotszym niz min_us to artefakt (np. drgnienie przy puszczeniu), nie uderzenie.
    Odrzucamy ja razem z jej wylaczeniem. Najszybsze prawdziwe uderzenie z 19.11: 5,1 ms."""

    def __init__(self):
        self.skip: set[int] = set()
        self.count = 0

    def accept(self, kind: str, note: int, us: int, min_us: int) -> bool:
        if kind == "on":
            self.skip.discard(note)
            if us < min_us:
                self.skip.add(note)
                self.count += 1
                return False
            return True
        if note in self.skip:
            self.skip.discard(note)
            return False
        return True


class LineHealth:
    """Ktore linie matrycy graja. Linia, ktora milczy, gdy reszta polowki gra, to przewod albo gniazdo (jak Y2 20.11)."""

    def __init__(self):
        self.on = collections.Counter()
        self.rev = collections.Counter()

    def note_on(self, note: int):
        self.on[note] += 1

    def reversed(self, note: int):
        self.rev[note] += 1

    def problems(self) -> list[str]:
        out = []
        for lo, hi in ((21, 60), (61, 108)):
            total = sum(self.on[n] for n in range(lo, hi + 1))
            if total < 150:
                continue
            lines = collections.defaultdict(list)
            for n in range(lo, hi + 1):
                lines[mp.key_lines(n)[0]].append(n)
            counts = {line: sum(self.on[n] for n in notes) for line, notes in lines.items()}
            for line, c in sorted(counts.items()):
                others = [v for k, v in counts.items() if k != line]
                if c == 0 and others and statistics.median(others) >= 8:
                    names = ", ".join(note_name(n) for n in lines[line])
                    out.append(f"Linia {line} milczy ({names}), choc reszta gra: przewod albo gniazdo")
        for note, n in sorted(self.rev.items()):
            if n >= 5 and n >= self.on[note]:
                out.append(f"{note_name(note)}: drugi styk przed pierwszym {n} razy (styk albo podkladka)")
        return out


class Latency:
    """Opoznienie USB ponad najlepsze widziane: czas Megi przy zdarzeniu vs chwila odebrania na PC."""

    def __init__(self):
        self.anchor = None            # (t_mega, wall) pierwszego ZYCIA
        self.skew = 1.0               # sekundy PC na sekunde Megi (rezonator klona: do ok. 0,5%)
        self.window = collections.deque()
        self.excess = collections.deque(maxlen=400)

    def life(self, t: float, wall: float):
        if self.anchor is None:
            self.anchor = (t, wall)
        elif t - self.anchor[0] > 20:
            self.skew = (wall - self.anchor[1]) / (t - self.anchor[0])
        self._add(t, wall, keep=False)

    def event(self, t: float, wall: float):
        self._add(t, wall, keep=True)

    def _add(self, t, wall, keep):
        if self.anchor is None:
            return
        off = wall - (self.anchor[1] + (t - self.anchor[0]) * self.skew)
        self.window.append((wall, off))
        while self.window and wall - self.window[0][0] > 30:
            self.window.popleft()
        base = min(o for _, o in self.window)
        if keep:
            self.excess.append(off - base)

    def summary(self) -> dict | None:
        if len(self.excess) < 10:
            return None
        xs = sorted(self.excess)
        return {"p50_ms": round(xs[len(xs) // 2] * 1000, 2), "p99_ms": round(xs[int(len(xs) * 0.99)] * 1000, 2),
                "max_ms": round(xs[-1] * 1000, 2), "n": len(xs)}


def default_open(port: str, baud: int):
    import serial
    link = serial.Serial()
    link.port, link.baudrate, link.timeout = port, baud, 0.05
    link.dtr = False           # bez DTR i RTS: otwarcie portu nie resetuje Megi
    link.rts = False
    link.open()
    return link


class MegaReader:
    """Watek: szuka Megi, czyta ramki, pilnuje zdrowia i sam naprawia to, co da sie naprawic programem.

    Kolejnosc naprawy, gdy Mega milczy: ponowne otwarcie portu, impuls reset (DTR), wgranie skanera; potem juz tylko
    jasny komunikat (mostek USB CH340 da sie odwiesic wylacznie odlaczeniem kabla).
    """

    def __init__(self, on_event, on_state, done: threading.Event, off_flag: Path | None = None,
                 flasher=None, expected=None, open_port=None, find=None, clock=time.time, sleep=None):
        self.on_event, self.on_state, self.done = on_event, on_state, done
        self.off_flag = off_flag
        self.flasher = flasher
        self.expected = expected
        self.open_port = open_port or default_open
        self.find = find
        self.clock = clock
        self._wait = sleep or done.wait     # testy podstawiaja szybki zegar
        self.port = None
        self.connected = False
        self.events = 0
        self.last_data = 0.0
        self.state = "start"
        self.message = ""
        self.hello: mp.Hello | None = None
        self.proto = None
        self.life: mp.Life | None = None
        self.decoder: mp.Decoder | None = None
        self.totals = collections.Counter()      # crc, lost, garbage, frames: z poprzednich polaczen
        self.sounding: set[int] = set()
        self.fixed_stuck = 0
        self.lost_on = 0
        self.health = LineHealth()
        self.latency = Latency()
        self.selftest: list[str] | None = None
        self.flash_times: list[float] = []
        self.flash_log: list[str] = []
        self.failures = 0
        self._warned: set[str] = set()
        self._tested = False
        self._busy_logged = 0.0
        self._last_event = 0.0
        self._last_health = 0.0

    # --- stan dla routera / wtyczki -------------------------------------------------------------------------------
    def info(self) -> dict:
        d = self.decoder
        tot = lambda k: self.totals[k] + (getattr(d, k) if d else 0)  # noqa: E731
        life = self.life
        return {
            "state": self.state, "message": self.message,
            "fw": self.hello.version if self.hello else None, "proto": self.proto,
            "build": self.hello.build if self.hello else None,
            "frames": tot("frames"), "crc_errors": tot("crc_errors"), "lost": tot("lost"), "garbage": tot("garbage"),
            "scan_us": life.scan_us if life else None, "max_scan_us": life.max_us if life else None,
            "overflows": life.overflows if life else None,
            "fixed_stuck": self.fixed_stuck, "flashes": len(self.flash_log),
            "latency": self.latency.summary(), "selftest": self.selftest, "problems": self.health.problems(),
        }

    def _set_state(self, state: str, message: str = ""):
        if (state, message) != (self.state, self.message):
            self.state, self.message = state, message
            if message:
                logging.info("Mega state %s: %s", state, message)

    def _connect(self, on: bool):
        if on != self.connected:
            self.connected = on
            if not on:
                self.sounding.clear()
            self.on_state(on)

    # --- petla glowna ---------------------------------------------------------------------------------------------
    def run(self):
        while not self.done.is_set():
            try:
                self._run()
                return
            except Exception:                  # watek Megi nie moze umrzec po cichu (wtedy klawiatura milczy na zawsze)
                logging.exception("Mega reader crashed, restarting in 3 s")
                self._connect(False)
                self._wait(3)

    def _run(self):
        info_thread_started = False
        while not self.done.is_set():
            if flag_active(self.off_flag, self.clock()):
                self._set_state("oddana", "port oddany narzedziu skanera (mega.py)")
                self._wait(1)
                continue
            port = None
            try:
                port = (self.find or find_port)()
            except Exception:
                logging.exception("Mega: port search failed")
            if port is None:
                self._set_state("brak", "Mega nie jest podlaczona")
                self._wait(3)
                continue
            if not info_thread_started:
                info_thread_started = True
                threading.Thread(target=self._log_driver, daemon=True, name="mega-driver").start()
            pulse = self.failures == 2
            reason = self._session(port, pulse_dtr=pulse)
            if reason in ("off", "done", "busy"):
                continue
            if reason == "ok":
                self.failures = 0
                self._wait(1)
                continue
            if reason == "upgrade":
                self._flash(port, "na Medze jest starszy program niz w hex/skaner.json")
                continue
            if reason == "foreign":
                ident = self._probe(port)
                self._flash(port, f"na Medze jest inny program ({ident})")
                continue
            # "silent" albo "nothing"
            self.failures += 1
            if self.failures == 3 and self._flash(port, "Mega milczy mimo resetu"):
                continue
            if self.failures >= 3:
                self._set_state("mostek", "Mega nie odpowiada: odlacz kabel USB Megi na 5 s i podlacz z powrotem")
                self._wait(20)
            else:
                self._wait(1)

    def _log_driver(self):
        info = ch340_driver_info()
        if info:
            logging.info("Mega USB driver: %s", info)

    def _session(self, port: str, pulse_dtr: bool = False) -> str:
        try:
            link = self.open_port(port, BAUD)
        except Exception as exc:
            if self.clock() - self._busy_logged > 60:
                self._busy_logged = self.clock()
                logging.warning("Mega on %s not available (podglad otwarty?): %s", port, exc)
            self._wait(3)
            return "busy"
        self.port = port
        logging.info("Mega: port %s open (proba %d)", port, self.failures + 1)
        if self.decoder is not None:
            for k in ("frames", "crc_errors", "lost", "garbage"):
                self.totals[k] += getattr(self.decoder, k)
        dec = self.decoder = mp.Decoder()
        t_open = self.clock()
        last_valid = None
        got = 0
        good_since = None
        asked = False
        try:
            if pulse_dtr:
                link.dtr = True
                time.sleep(0.05)
                link.dtr = False
                logging.info("Mega: reset pulse sent")
                t_open = self.clock()
            while not self.done.is_set():
                now = self.clock()
                if flag_active(self.off_flag, now):
                    logging.info("Mega: port released (mega-off)")
                    return "off"
                # Otwarcie portu na Windows resetuje Mege (log 20.11: baner 1,1 s po otwarciu), wiec pytamy dopiero
                # po bootloaderze (ok. 1 s). Nigdy nie wysylamy "!!!": stary bootloader Megi wchodzi wtedy w monitor.
                if not asked and now - t_open > 1.5:
                    asked = True
                    self._ask(link, b"IS")
                chunk = link.read(max(1, link.in_waiting))
                now = self.clock()
                if chunk:
                    got += len(chunk)
                    self.last_data = now
                    for msg in dec.feed(chunk):
                        last_valid = now
                        if good_since is None:
                            good_since = now
                        self._handle(msg, now, dec)
                        if isinstance(msg, mp.Hello) and msg.proto >= 2 and not self._tested:
                            self._tested = True          # raz na uruchomienie routera: test linii (ok. 20 ms)
                            self._ask(link, b"T")
                if last_valid is None:
                    if dec.garbage > 64 and now - t_open > 3:
                        logging.warning("Mega: %d bytes without a valid frame on %s: another program?", got, port)
                        return "foreign"
                    if now - t_open > 5:
                        if got:
                            logging.warning("Mega: %d bytes in 5 s, none valid, on %s: another program?", got, port)
                            return "foreign"
                        logging.warning("Mega: no data on %s for %.0f s", port, now - t_open)
                        self._set_state("cisza", "Mega nic nie wysyla, probuje ponownie")
                        return "nothing"
                    continue
                limit = SILENT_V2_S if dec.mode == "v2" else SILENT_V1_S
                if now - last_valid > limit:
                    logging.warning("Mega: silent for %.1f s on %s (USB bridge?)", now - last_valid, port)
                    self._connect(False)
                    self._set_state("cisza", "Mega zamilkla, probuje ponownie")
                    return "silent" if good_since is None or now - good_since < 10 else "ok"
                if self._upgrade_wanted(now):
                    return "upgrade"
                if now - self._last_health > 30:
                    self._last_health = now
                    for p in self.health.problems():
                        if p not in self._warned:
                            self._warned.add(p)
                            logging.warning("Mega health: %s", p)
            return "done"
        except Exception as exc:
            logging.warning("Mega: link lost on %s: %s", port, exc)
            return "ok" if good_since is not None and self.clock() - good_since > 10 else "silent"
        finally:
            try:
                link.close()
            except Exception:
                pass
            self._connect(False)
            self.port = None

    def _ask(self, link, what: bytes):
        try:
            link.write(what)             # v2: I = przedstaw sie, S = stan, T = test linii; v1 to ignoruje
        except Exception:
            pass

    def _upgrade_wanted(self, now: float) -> bool:
        exp = self.expected() if callable(self.expected) else self.expected   # manifest czytany na biezaco
        if exp is None or self.flasher is None or self.proto is None:
            return False
        if self.proto == 2 and self.hello is None:
            return False                                      # v2 jeszcze sie nie przedstawil
        older = self.proto < exp["proto"] or (self.proto == exp["proto"] and self.hello.build != exp["build"])
        if not older:
            return False
        if self.sounding or now - self._last_event < 5:      # nie w trakcie grania
            return False
        return self._flash_allowed(now)

    def _handle(self, msg, now: float, dec: mp.Decoder):
        if isinstance(msg, mp.Hello):
            first = self.hello is None or (msg.proto, msg.build) != (self.hello.proto, self.hello.build)
            self.hello, self.proto = msg, msg.proto
            if first:
                logging.info("Mega: SKANER %s (protokol %d, build %d) on %s", msg.version, msg.proto, msg.build, self.port)
            if msg.proto >= 2 and not msg.flags & 1:
                self._set_state("blad", "skaner zglasza nietypowy uklad pinow plytki")
                return
            self._set_state("gra", "")
            self._connect(True)
            return
        if isinstance(msg, mp.Life):
            self.life = msg
            if self.proto is None:
                self.proto = 1 if dec.mode == "v1" else 2
                logging.info("Mega: scanner running (%s) on %s", "v1" if self.proto == 1 else "v2", self.port)
            if msg.t is not None:
                self.latency.life(msg.t, now)
            if self.state != "blad":
                self._set_state("gra", "")
                self._connect(True)
            if msg.sounding is not None:
                for note in sorted(self.sounding - msg.sounding):   # wylaczenie zginelo po drodze
                    self.sounding.discard(note)
                    self.fixed_stuck += 1
                    logging.warning("Mega: %s hung (note-off lost), switched off", note_name(note))
                    self.on_event("off", note, 0)
                self.lost_on += len(msg.sounding - self.sounding)
            return
        if isinstance(msg, mp.SelfTest):
            self.selftest = analyse_selftest(msg)
            logging.info("Mega self-test: %s | %s", dict(zip(mp.TEST_LINES, msg.counts)),
                         "; ".join(self.selftest) or "bez uwag")
            return
        if isinstance(msg, mp.Event):
            if self.proto is None:
                self.proto = 1 if dec.mode == "v1" else 2
            if self.state != "blad":
                self._set_state("gra", "")
                self._connect(True)
            self._last_event = now
            if msg.t is not None:
                self.latency.event(msg.t, now)
            if msg.kind == "rev":
                self.health.reversed(msg.note)
                logging.info("Mega: %s second contact before the first", note_name(msg.note))
                return
            if msg.kind == "on":
                self.sounding.add(msg.note)
                self.health.note_on(msg.note)
            else:
                self.sounding.discard(msg.note)
            self.events += 1
            self.on_event(msg.kind, msg.note, msg.us)

    # --- naprawa --------------------------------------------------------------------------------------------------
    def _flash_allowed(self, now: float) -> bool:
        self.flash_times = [t for t in self.flash_times if now - t < 3600]
        return len(self.flash_times) < FLASH_LIMIT

    def _flash(self, port: str, why: str) -> bool:
        now = self.clock()
        if self.flasher is None or not self._flash_allowed(now):
            self._set_state("program", f"{why}; uruchom 3 - Skaner podglad.bat")
            self._wait(10)
            return False
        if flag_active(self.off_flag, now):
            return False
        self.flash_times.append(now)
        self._set_state("wgrywam", f"{why}: wgrywam skaner")
        try:
            ok, text = self.flasher(port)
        except Exception as exc:              # wgrywanie nie moze zabic watku Megi
            ok, text = False, f"blad wgrywania: {exc}"
        self.flash_log.append(f"{time.strftime('%H:%M:%S')} {why}: {text}")
        logging.log(logging.INFO if ok else logging.WARNING, "Mega flash (%s): %s", why, text)
        self.hello, self.proto = None, None
        self._wait(1.5)
        return ok

    def _probe(self, port: str) -> str:
        """Kilka sekund na 115200: czy to program test albo rozpoznanie (tekst)."""
        try:
            link = self.open_port(port, PROBE_BAUD)
        except Exception:
            return "nieznany"
        buf = b""
        t0 = self.clock()
        try:
            while self.clock() - t0 < 2.5 and not self.done.is_set():
                buf += link.read(max(1, link.in_waiting))
                for name, mark in (("rozpoznanie", b"ROZPOZNANIE"), ("test", b"MEGA OK"), ("test", b"TEST v")):
                    if mark in buf:
                        return name
                if b"\nE " in buf or b"\nH " in buf:
                    return "rozpoznanie"
        except Exception:
            pass
        finally:
            try:
                link.close()
            except Exception:
                pass
        return "nieznany"
