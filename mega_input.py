"""Klawisze z Arduino Mega (skaner, 19.11.2026): czas miedzy stykami -> velocity jak w fortepianie.

Mega wysyla po porcie szeregowym (1 000 000 bodow):
    "+ <midi> <us>"   nuta wlaczona, us = czas od pierwszego do drugiego styku
    "- <midi> <us>"   nuta wylaczona, us = czas od otwarcia drugiego do otwarcia pierwszego styku (0 = brak)

Krzywa (wzor fortepianu Bosendorfer SE, Goebl i Bresin 2003): velocity = 52 + 25 * log2(predkosc mlotka w m/s),
czyli kazde przepolowienie czasu miedzy stykami to +25 velocity. Jedyny punkt zaczepienia: czas, ktory daje
podane velocity (kotwica). Czarne klawisze maja dluzsze czasy przy tej samej sile (inna geometria), wiec ich czas
dzielimy przez staly mnoznik. Parametry w mega-krzywa.json, wczytywane na biezaco.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from pathlib import Path

BLACK_KEYS = {1, 3, 6, 8, 10}
SLOPE = 25.0               # velocity na podwojenie predkosci (Bosendorfer SE)
RELEASE_CENTER_US = 25000  # mediana czasu puszczenia z gry 19.11 -> velocity puszczenia 64
BAUD = 1_000_000
MEGA_VIDS = {0x1A86, 0x2341, 0x2A03}

# 19.11, gra 9 min: najszybsze 1% bialych 6,9 ms, czarnych 8,7 ms; mediana 15,2 / 22,8 ms.
# "fortepian": droga miedzy stykami ok. 5 mm (szacunek do zmierzenia) -> predkosc klawisza, mlotek 5x szybciej
#   (Askenfelt), wzor Bosendorfera: 6,5 ms -> ok. 100, mediana -> ok. 70 (jak u pianistow, MAESTRO 66).
# "fortepian-pelny": to samo nachylenie, ale najmocniejsze uderzenie (6,5 ms) = 120.
DEFAULT_CURVES = {
    "fortepian": {"kotwica_us": 6500, "kotwica_velocity": 100},
    "fortepian-pelny": {"kotwica_us": 6500, "kotwica_velocity": 120},
}
# wysoka_rozdzielczosc: przed nuta CC88 z czescia ulamkowa velocity (Pianoteq: 14 bitow). Galka B16 od 20.11
# wysyla CC89, wiec CC88 jest wolne; wlaczac dopiero, gdy w mapie Pianoteq nic nie jest przypisane do CC88.
DEFAULT_SETTINGS = {"krzywa": "fortepian", "czarne_mnoznik": 1.28, "minimum": 2, "wysoka_rozdzielczosc": False,
                    "krzywe": DEFAULT_CURVES}


def load_settings(path: Path) -> dict:
    data = dict(DEFAULT_SETTINGS)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data.update({k: v for k, v in loaded.items() if k in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass
    curves = data.get("krzywe")
    if not isinstance(curves, dict) or not curves:
        data["krzywe"] = DEFAULT_CURVES
    if data["krzywa"] not in data["krzywe"]:
        data["krzywa"] = next(iter(data["krzywe"]))
    return data


def note_velocity_exact(midi: int, us: int, settings: dict) -> float:
    """Czas miedzy stykami (us) -> velocity z czescia ulamkowa, w zakresie minimum..127."""
    curve = settings["krzywe"][settings["krzywa"]]
    t = max(1, int(us))
    if midi % 12 in BLACK_KEYS:
        t = t / float(settings.get("czarne_mnoznik", 1.0))
    v = curve["kotwica_velocity"] + SLOPE * math.log2(curve["kotwica_us"] / t)
    return max(float(settings.get("minimum", 1)), min(127.0, v))


def note_velocity(midi: int, us: int, settings: dict) -> int:
    """Czas miedzy stykami (us) -> velocity 1..127 wedlug aktywnej krzywej."""
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
    """'+ 60 12000' -> ('on', 60, 12000); smieci -> None."""
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


def find_port():
    from serial.tools import list_ports
    for p in list_ports.comports():
        if p.vid in MEGA_VIDS or "CH340" in (p.description or ""):
            return p.device
    return None


class MegaReader:
    """Watek: szuka Megi, czyta zdarzenia, przy rozlaczeniu probuje znowu co 3 s."""

    def __init__(self, on_event, on_state, done: threading.Event, off_flag: Path | None = None):
        self.on_event, self.on_state, self.done = on_event, on_state, done
        self.off_flag = off_flag          # plik "mega-off": router oddaje port (np. dla podgladu skanera)
        self.port = None
        self.connected = False
        self.events = 0
        self._busy_logged = 0.0

    def run(self):
        import serial
        while not self.done.is_set():
            if self.off_flag is not None and self.off_flag.exists():
                self.done.wait(1)
                continue
            port = None
            try:
                port = find_port()
            except Exception:
                logging.exception("Mega: port search failed")
            if port is None:
                self.done.wait(3)
                continue
            try:
                # bez DTR i RTS: otwarcie portu nie resetuje Megi (reset zostawial ja w bootloaderze, cisza na porcie)
                link = serial.Serial()
                link.port, link.baudrate, link.timeout = port, BAUD, 0.2
                link.dtr = False
                link.rts = False
                link.open()
            except Exception as exc:
                if time.time() - self._busy_logged > 60:
                    self._busy_logged = time.time()
                    logging.warning("Mega on %s not available (podglad otwarty?): %s", port, exc)
                self.done.wait(3)
                continue
            self.port = port
            try:
                from serial.tools import list_ports
                logging.info("Mega: port %s open, waiting for the scanner; ports: %s", port,
                             [(p.device, p.description, hex(p.vid or 0)) for p in list_ports.comports()])
            except Exception:
                logging.info("Mega: port %s open, waiting for the scanner", port)
            buf = b""
            got, t_open, told = 0, time.time(), 0
            try:
                while not self.done.is_set():
                    if self.off_flag is not None and self.off_flag.exists():
                        logging.info("Mega: port released (mega-off)")
                        break
                    # 20.11: read(256) czekal na 256 bajtow albo pelny timeout (0,2 s): nuta spozniona do 200 ms.
                    # read(1) wraca od razu po pierwszym bajcie, reszte bierzemy z bufora sterownika.
                    chunk = link.read(max(1, link.in_waiting))
                    if not self.connected and time.time() - t_open > 8 + 20 * told:
                        told += 1          # diagnostyka co 20 s: co przychodzi, gdy skaner sie nie zglasza
                        logging.warning("Mega: no scanner on %s, %d bytes read, buffer %r, cts=%s dsr=%s",
                                        port, got, buf[:60], link.cts, link.dsr)
                        if got == 0 and told == 1:   # cisza: jeden impuls DTR (reset Megi); wiecej nie, mostek USB tego nie lubi
                            link.dtr = True
                            time.sleep(0.05)
                            link.dtr = False
                            logging.info("Mega: reset pulse sent")
                    if not chunk:
                        continue
                    got += len(chunk)
                    buf += chunk
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        line = raw.decode("ascii", "replace").strip()
                        if line.startswith("SKANER") or line.startswith("H "):   # baner albo znak zycia co 2 s
                            if not self.connected:
                                self.connected = True
                                logging.info("Mega: %s on %s", line, port)
                                self.on_state(True)
                            continue
                        ev = parse_line(line)
                        if ev is not None:
                            if not self.connected:           # router restarted while the Mega kept running
                                self.connected = True
                                self.on_state(True)
                            self.events += 1
                            self.on_event(*ev)
                        elif line.startswith("!"):
                            logging.info("Mega: %s", line)
            except Exception as exc:
                logging.warning("Mega: link lost on %s: %s", port, exc)
            finally:
                try:
                    link.close()
                except Exception:
                    pass
                if self.connected:
                    self.connected = False
                    self.on_state(False)
                self.port = None
            self.done.wait(1)
