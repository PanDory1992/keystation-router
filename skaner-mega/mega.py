# -*- coding: utf-8 -*-
"""Skaner Mega: wgrywanie programu do Arduino Mega i prowadzone rozpoznanie matrycy klawiatury.

Uzycie (zwykle przez pliki .bat w tym folderze):
  python mega.py test          wgrywa program testowy i sprawdza, czy Mega odpowiada
  python mega.py rozpoznaj     wgrywa program rozpoznania i prowadzi przez 88 klawiszy
Opcje: --port COM5 (zamiast szukania), --bez-wgrywania (gdy program jest juz na plytce).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))
import serial  # noqa: E402  (pyserial z folderu vendor)
from serial.tools import list_ports  # noqa: E402

AVRDUDE = HERE / "narzedzia" / "avrdude" / "bin" / "avrdude.exe"
AVRCONF = HERE / "narzedzia" / "avrdude" / "etc" / "avrdude.conf"
HEX = {"test": HERE / "hex" / "test.hex", "rozpoznanie": HERE / "hex" / "rozpoznanie.hex"}
WYNIKI = HERE / "wyniki"
BAUD = 115200
MEGA_VIDS = {0x1A86, 0x2341, 0x2A03}  # CH340, Arduino, Arduino.org

NAMES = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B (H)"]
BLACK = {1, 3, 6, 8, 10}


def key_name(midi):
    pc, octave = midi % 12, midi // 12 - 1
    n = NAMES[pc]
    if "/" in n:
        a, b = n.split("/")
        return f"{a}{octave} / {b}{octave}"
    if pc == 11:
        return f"B{octave} (H{octave})"
    return f"{n}{octave}"


def say(*a):
    print(*a, flush=True)


# --- port ---------------------------------------------------------------------------------------------
def pnp_ch340_problem():
    """Windows: czy jest urzadzenie CH340 bez dzialajacego sterownika?"""
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PnpDevice | Where-Object { $_.InstanceId -match 'VID_1A86' } | "
             "ForEach-Object { $_.Status + '|' + $_.FriendlyName }"],
            capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return None
    return out or None


def find_port(wanted=None):
    if wanted:
        return wanted
    ports = list(list_ports.comports())
    mega = [p for p in ports if (p.vid in MEGA_VIDS) or "CH340" in (p.description or "")]
    if mega:
        p = mega[0]
        say(f"Mega znaleziona: {p.device} ({p.description})")
        return p.device
    say("Nie widzę Megi.")
    if ports:
        say("Porty, które widzi Windows:")
        for p in ports:
            say(f"  {p.device}: {p.description}")
    pnp = pnp_ch340_problem()
    if pnp:
        say("Windows widzi układ CH340, ale bez działającego sterownika:")
        say("  " + pnp.replace("\n", "\n  "))
        say("Zainstaluj sterownik CH341SER ze strony producenta (wch-ic.com) albo napisz do Claude.")
    else:
        say("Sprawdź: kabel USB do transmisji danych (nie tylko ładowanie), inny port USB z tyłu komputera,")
        say("czy na Medze świeci zielona dioda ON.")
    return None


# --- wgrywanie ------------------------------------------------------------------------------------------
def flash(port, which):
    hexfile = HEX[which]
    if not AVRDUDE.exists():
        say(f"Brak programu do wgrywania: {AVRDUDE}")
        return False
    say(f"Wgrywam program „{which}” na {port}... (ok. 10 s, na Medze mrugają diody RX/TX)")
    cmd = [str(AVRDUDE), "-C", str(AVRCONF), "-p", "atmega2560", "-c", "wiring", "-P", port,
           "-b", "115200", "-D", "-U", f"flash:w:{hexfile}:i"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        say("Wgrywanie trwało za długo i zostało przerwane. Odłącz i podłącz Megę, spróbuj jeszcze raz.")
        return False
    log = (r.stdout or "") + (r.stderr or "")
    WYNIKI.mkdir(exist_ok=True)
    (WYNIKI / f"wgrywanie-{which}.log").write_text(log, encoding="utf-8")
    if r.returncode != 0:
        say("Wgrywanie się nie udało. Ostatnie linie:")
        for line in log.strip().splitlines()[-8:]:
            say("  " + line)
        say("Najczęstsze przyczyny: port zajęty przez inny program, zły kabel, inna płytka niż Mega 2560.")
        return False
    say("Wgrane.")
    return True


def open_serial(port):
    s = serial.Serial(port, BAUD, timeout=0.05)
    return s


def read_lines(s):
    """Generator linii z portu (bez blokowania na dluzej niz timeout portu)."""
    buf = b""
    while True:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                yield line.decode("ascii", "replace").strip()
        else:
            yield None


# --- test ---------------------------------------------------------------------------------------------
def cmd_test(args):
    port = find_port(args.port)
    if not port:
        return 1
    if not args.bez_wgrywania and not flash(port, "test"):
        return 1
    s = open_serial(port)
    say("Czekam na odpowiedź Megi...")
    t_end = time.time() + 8
    ok = 0
    for line in read_lines(s):
        if time.time() > t_end:
            break
        if line and line.startswith("MEGA OK"):
            ok += 1
            say("  " + line)
            if ok >= 3:
                break
    s.close()
    if ok >= 3:
        say("")
        say("MEGA DZIAŁA: wgrywanie i łączność z komputerem są w porządku. Dioda L na płytce mruga.")
        return 0
    say("Mega nie odpowiada. Napisz do Claude, plik wyniki/wgrywanie-test.log pomoże.")
    return 1


# --- rozpoznanie -----------------------------------------------------------------------------------------
class Keys:
    """Polecenia z klawiatury komputera bez czekania na Enter (Windows: msvcrt)."""

    def __init__(self):
        try:
            import msvcrt  # type: ignore
            self.m = msvcrt
        except ImportError:
            self.m = None

    def get(self):
        if self.m and self.m.kbhit():
            return self.m.getwch().lower()
        return None


def clusters(events, gap_us=8000):
    """Zdarzenia '+' (t, i, j) w kolejnosci czasu -> grupy oddzielone przerwa > gap_us."""
    out = []
    for t, i, j in sorted(events):
        if out and t - out[-1][-1][0] <= gap_us:
            out[-1].append((t, i, j))
        else:
            out.append([(t, i, j)])
    return out


def analyse_press(events):
    """Zwraca (pierwszy_styk, drugi_styk, odstep_us) albo (pary, None, None) gdy jeden moment."""
    plus = [(t, i, j) for (sign, i, j, t) in events if sign == "+"]
    if not plus:
        return None, None, None
    cl = clusters(plus)
    first = sorted({(i, j) for _, i, j in cl[0]})
    for c in cl[1:]:
        new = sorted({(i, j) for _, i, j in c} - set(first))
        if new:
            return first, new, c[0][0] - cl[0][0][0]
    return first, None, None


def cmd_rozpoznaj(args):
    port = find_port(args.port)
    if not port:
        return 1
    if not args.bez_wgrywania and not flash(port, "rozpoznanie"):
        return 1
    WYNIKI.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_json = WYNIKI / f"matryca-{stamp}.json"
    raw = open(WYNIKI / f"surowe-{stamp}.txt", "w", encoding="utf-8")
    s = open_serial(port)
    lines = read_lines(s)

    pins, rest, low = {}, set(), []
    say("Czekam na Megę...")
    t_end = time.time() + 10
    ready = False
    for line in lines:
        if time.time() > t_end:
            break
        if not line:
            continue
        raw.write(f"{time.time():.4f} {line}\n")
        p = line.split()
        if p[0] == "PIN":
            pins[int(p[1])] = {"etykieta": p[2], "pin_megi": int(p[3])}
        elif p[0] == "LOW":
            low.append(int(p[1]))
        elif p[0] == "R":
            rest.add((int(p[1]), int(p[2])))
        elif p[0] == "GOTOWE":
            ready = True
            break
    if not ready:
        say("Mega nie zgłosiła się z programem rozpoznania. Spróbuj jeszcze raz albo napisz do Claude.")
        return 1
    lab = lambda i: pins.get(i, {}).get("etykieta", str(i))  # noqa: E731

    say("")
    say(f"Mega gotowa, {len(pins)} przewodów.")
    if low:
        say("UWAGA: te przewody są stale na masie (sprawdź, czy kabelek nie siedzi w GND): "
            + ", ".join(lab(i) for i in low))
    both = sorted({tuple(sorted(p)) for p in rest if (p[1], p[0]) in rest})
    one = sorted(p for p in rest if (p[1], p[0]) not in rest)
    if both:
        say("Przewody połączone w klawiaturze na stałe (to normalne, to te same linie): "
            + ", ".join(f"{lab(a)}={lab(b)}" for a, b in both))
    if one:
        say("Styki zamknięte już na starcie (czy jakiś klawisz jest wciśnięty?): "
            + ", ".join(f"{lab(a)}>{lab(b)}" for a, b in one))

    result = {"utworzono": stamp, "port": port, "piny": pins, "na_masie": low,
              "spoczynek": sorted(rest), "klawisze": {}}

    def save():
        out_json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    save()
    say("")
    say("Teraz po kolei każdy klawisz, od najniższego (lewa strona) do najwyższego.")
    say("Naciśnij POWOLI do dna i puść. Jeden klawisz naraz, bez pedału.")
    say("Polecenia z klawiatury komputera: P = wróć do poprzedniego klawisza, N = pomiń, K = koniec i zapis.")
    say("")

    keys = Keys()
    order = list(range(21, 109)) if not args.klawisze else [int(x) for x in args.klawisze.split(",")]
    k = 0
    tries = 0
    active = set()
    events = []
    last_ev = 0.0
    prompted = False
    while k < len(order):
        midi = order[k]
        if not prompted:
            colour = "czarny" if midi % 12 in BLACK else "biały"
            say(f"[{k + 1}/{len(order)}] Naciśnij powoli i puść: {key_name(midi)}  ({colour}, nuta MIDI {midi})")
            prompted = True
            events, last_ev = [], 0.0
        c = keys.get()
        if c in ("p", "n", "k"):
            if c == "k":
                break
            k = max(0, k - 1) if c == "p" else k + 1
            prompted, tries = False, 0
            continue
        line = next(lines)
        if line:
            raw.write(f"{time.time():.4f} {line}\n")
            p = line.split()
            if p[0] == "E" and len(p) == 5:
                sign, i, j, t = p[1], int(p[2]), int(p[3]), int(p[4])
                (active.add if sign == "+" else active.discard)((i, j))
                events.append((sign, i, j, t))
                last_ev = time.time()
            continue
        if events and not active and time.time() - last_ev > 0.4:
            first, second, gap = analyse_press(events)
            if first is None:
                events = []
                continue
            pairs = set(map(tuple, first)) | set(map(tuple, second or []))
            dup = [m for m, v in result["klawisze"].items()
                   if int(m) != midi and pairs == {tuple(x) for x in v["pierwszy"] + (v["drugi"] or [])}]
            if dup:
                say(f"    To wygląda na klawisz {key_name(int(dup[0]))}, który już był. Naciśnij {key_name(midi)}.")
                events = []
                continue
            if second is None and tries < 2:
                tries += 1
                say("    Złapałem tylko jeden moment. Jeszcze raz, wolniej, do samego dna.")
                events = []
                continue
            result["klawisze"][str(midi)] = {
                "nazwa": key_name(midi), "pierwszy": [list(x) for x in first],
                "drugi": [list(x) for x in second] if second else None,
                "odstep_us": gap, "zdarzenia": events}
            save()
            if second:
                say(f"    OK  pierwszy styk {', '.join(lab(i) + '>' + lab(j) for i, j in first)}, "
                    f"drugi {', '.join(lab(i) + '>' + lab(j) for i, j in second)}, odstęp {gap / 1000:.0f} ms")
            else:
                say("    Zapisane z jednym stykiem (sprawdzę to później).")
            k += 1
            prompted, tries = False, 0
    s.close()
    raw.close()
    save()
    done = sum(1 for v in result["klawisze"].values() if v["drugi"])
    say("")
    say(f"Koniec. Klawiszy z dwoma stykami: {done} z {len(order)}.")
    say(f"Wynik: {out_json}")
    say("Napisz do Claude, że gotowe. Klawiatura teraz nie gra, to normalne do czasu wgrania skanera.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("co", choices=["test", "rozpoznaj"])
    ap.add_argument("--port")
    ap.add_argument("--bez-wgrywania", action="store_true")
    ap.add_argument("--klawisze", help="lista nut MIDI zamiast calej klawiatury, np. 60,61,62")
    args = ap.parse_args()
    try:
        return cmd_test(args) if args.co == "test" else cmd_rozpoznaj(args)
    except serial.SerialException as e:
        say(f"Problem z portem: {e}")
        say("Zamknij inne programy, które mogą używać Megi (np. Arduino IDE), i spróbuj jeszcze raz.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
