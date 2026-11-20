"""Protokol skanera Mega (20.11.2026): ramki v2 (COBS + numer kolejny + CRC-8) i dawny tekst v1.

Jeden modul dla routera (mega_input.py) i dla narzedzia skaner-mega/mega.py, zeby oba czytaly Mege tak samo.
Opis ramek: komentarz na poczatku skaner-mega/firmware/skaner/skaner.ino.

Zasada: z ramki, ktora nie przeszla CRC, nie powstaje zadne zdarzenie. Zgubione ramki widac po numerze kolejnym.
"""
from __future__ import annotations

from dataclasses import dataclass, field

T_NOTE_ON, T_NOTE_OFF, T_REVERSED = 0x01, 0x02, 0x03
T_HELLO, T_LIFE, T_TEST = 0x10, 0x11, 0x12
TEST_LINES = (["W%d" % i for i in range(1, 11)] + ["X%d" % i for i in range(1, 11)]
              + ["Y%d" % i for i in range(1, 11)] + ["Z%d" % i for i in range(1, 9)] + ["pin43", "pin53"])
TEST_PINS = (list(range(22, 32)) + list(range(32, 42)) + [42, "A8"] + list(range(44, 52))
             + ["A%d" % i for i in range(8)] + [43, 53])
MAX_SEGMENT = 80          # dluzszy kawalek bez 0x00 to nie ramka (smieci albo inny program)


def crc8(data: bytes) -> int:
    """CRC-8/SMBUS (wielomian 0x07, start 0), tak samo jak crc8() w skaner.ino."""
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c


def cobs_encode(data: bytes) -> bytes:
    out, block = bytearray(), bytearray()
    for b in data:
        if b == 0:
            out.append(len(block) + 1)
            out += block
            block = bytearray()
        else:
            block.append(b)
            if len(block) == 254:
                out.append(255)
                out += block
                block = bytearray()
    out.append(len(block) + 1)
    out += block
    return bytes(out)


def cobs_decode(data: bytes) -> bytes | None:
    """Odwrotnosc cobs_encode; None, gdy kawalek nie jest poprawnym COBS."""
    out, i, n = bytearray(), 0, len(data)
    while i < n:
        code = data[i]
        if code == 0:
            return None
        end = i + code
        if end > n:
            return None
        chunk = data[i + 1:end]
        if 0 in chunk:
            return None
        out += chunk
        i = end
        if code != 255 and i < n:
            out.append(0)
    return bytes(out)


def build_frame(ftype: int, seq: int, payload: bytes) -> bytes:
    """Ramka jak z Megi (do testow i symulatora): COBS(typ, seq, dane, crc) + 0x00."""
    raw = bytes((ftype, seq & 0xFF)) + payload
    return cobs_encode(raw + bytes((crc8(raw),))) + b"\x00"


@dataclass
class Event:
    kind: str                 # "on", "off", "rev"
    note: int
    us: int                   # on: czas miedzy stykami, off: czas puszczenia (0 = brak), rev: 0
    t: float | None = None    # czas Megi w sekundach (rozwiniety), None w v1


@dataclass
class Hello:
    proto: int
    major: int
    minor: int
    build: int = 0
    flags: int = 0

    @property
    def version(self) -> str:
        return f"{self.major}.{self.minor}"


@dataclass
class Life:
    t: float | None = None
    scans: int = 0            # skanow w ostatnim okresie (v2: na sekunde, v1: na 2 s)
    scan_us: int = 0
    max_us: int = 0
    overflows: int = 0
    rx: int = 0
    sounding: set | None = None


@dataclass
class SelfTest:
    counts: list = field(default_factory=list)
    stuck: set = field(default_factory=set)


def _u(b: bytes) -> int:
    return int.from_bytes(b, "little")


class Decoder:
    """Bajty z portu -> wiadomosci (Event / Hello / Life / SelfTest). Rozpoznaje v2 i v1 sam."""

    def __init__(self):
        self.buf = bytearray()
        self.mode = None              # None (jeszcze nie wiadomo), "v2", "v1"
        self.frames = 0
        self.crc_errors = 0
        self.lost = 0                 # ramki, ktorych numer kolejny przepadl
        self.garbage = 0              # bajty, z ktorych nic nie powstalo
        self.text_lines = 0
        self._seq = None
        self._t_last = None
        self._t_high = 0

    # --- czas Megi: licznik 0,5 us, 32 bity, przekreca sie co 35,8 min
    def _time(self, raw: int) -> float:
        if self._t_last is not None and raw < self._t_last and self._t_last - raw > 0x80000000:
            self._t_high += 1 << 32
        self._t_last = raw
        return (self._t_high + raw) / 2_000_000

    def feed(self, data: bytes) -> list:
        out = []
        for b in data:
            if b == 0:
                seg = bytes(self.buf)
                self.buf.clear()
                if self.mode == "v1":
                    self.mode = None          # v1 nigdy nie wysyla 0x00: to juz inny program
                if seg:
                    msg = self._frame(seg)
                    if msg is not None:
                        out.append(msg)
                continue
            if b == 0x0A and self.mode != "v2":
                seg = bytes(self.buf)
                self.buf.clear()
                msg = self._text(seg)
                if msg is not None:
                    out.append(msg)
                elif seg.strip():
                    self.garbage += len(seg) + 1
                continue
            self.buf.append(b)
            if len(self.buf) > MAX_SEGMENT:
                self.garbage += len(self.buf)
                self.buf.clear()
        return out

    def _frame(self, seg: bytes):
        raw = cobs_decode(seg)
        if raw is None or len(raw) < 3 or crc8(raw[:-1]) != raw[-1]:
            self.crc_errors += 1
            self.garbage += len(seg) + 1
            return None
        ftype, seq, p = raw[0], raw[1], raw[2:-1]
        msg = self._parse(ftype, p)
        if msg is None:
            self.crc_errors += 1
            return None
        if self._seq is not None:
            self.lost += (seq - self._seq - 1) & 0xFF
        self._seq = seq
        self.frames += 1
        self.mode = "v2"
        return msg

    def _parse(self, ftype: int, p: bytes):
        if ftype in (T_NOTE_ON, T_NOTE_OFF) and len(p) == 8:
            note = p[0]
            if not 21 <= note <= 108:
                return None
            return Event("on" if ftype == T_NOTE_ON else "off", note, _u(p[1:4]), self._time(_u(p[4:8])))
        if ftype == T_REVERSED and len(p) == 5:
            if not 21 <= p[0] <= 108:
                return None
            return Event("rev", p[0], 0, self._time(_u(p[1:5])))
        if ftype == T_HELLO and len(p) == 8:
            return Hello(p[0], p[1], p[2], _u(p[3:7]), p[7])
        if ftype == T_LIFE and len(p) == 25:
            bits = _u(p[14:25])
            return Life(self._time(_u(p[0:4])), _u(p[4:6]), _u(p[6:8]), _u(p[8:10]), _u(p[10:12]), _u(p[12:14]),
                        {21 + n for n in range(88) if bits >> n & 1})
        if ftype == T_TEST and len(p) == len(TEST_LINES) + 5:
            bits = _u(p[len(TEST_LINES):])
            return SelfTest(list(p[:len(TEST_LINES)]), {TEST_LINES[i] for i in range(len(TEST_LINES)) if bits >> i & 1})
        return None

    def _text(self, seg: bytes):
        """Skaner v1 (tekst): '+ 60 12000', '- 60 900', '! 60 R', 'H 15000 132', 'SKANER v1.2'."""
        try:
            line = seg.decode("ascii").strip()
        except UnicodeDecodeError:
            return None
        if not line:
            return None
        parts = line.split()
        msg = None
        if line.startswith("SKANER v1"):
            ver = line.split("v", 1)[1]
            major, _, minor = ver.partition(".")
            msg = Hello(1, int(major) if major.isdigit() else 1, int(minor) if minor.isdigit() else 0)
        elif parts[0] == "H" and len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            msg = Life(None, int(parts[1]), int(parts[2]))
        elif parts[0] in ("+", "-") and len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            midi, us = int(parts[1]), int(parts[2])
            if 21 <= midi <= 108:
                msg = Event("on" if parts[0] == "+" else "off", midi, us)
        elif parts[0] == "!" and len(parts) == 3 and parts[1].isdigit() and 21 <= int(parts[1]) <= 108:
            msg = Event("rev", int(parts[1]), 0)
        if msg is not None:
            self.text_lines += 1
            self.mode = "v1"
        return msg


def key_lines(note: int) -> tuple[str, str, str]:
    """Nuta -> (linia klawisza, linia pierwszego styku, linia drugiego styku), wedlug matrycy z 19.11."""
    if note <= 60:
        g, k = divmod(note - 21, 8)
        return f"Z{k + 1}", f"X{2 * g + 2}", f"X{2 * g + 1}"
    g, k = divmod(note - 61, 8)
    if g < 5:
        return f"Y{k + 1}", f"W{2 * g + 2}", f"W{2 * g + 1}"
    return f"Y{k + 1}", "Y9", "Y10"
