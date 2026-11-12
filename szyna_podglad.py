"""Podgląd szyny: shows live, in plain words, everything the router shares.

Double-click "Szyna - podglad.bat". Keys in the window:
  t  play a short test arpeggio on the instrument (checks that "play" works)
  q  quit
It is also the smallest working example of a bus listener: join with "hello",
repeat it every few seconds, read JSON datagrams.
"""

import json
import socket
import sys
import time

ROUTER = ("127.0.0.1", 47800)
NAMES = "C C# D D# E F F# G G# A A# B".split()
TOUCH = {"light": "Light", "acoustic": "Acoustic", "heavy": "Heavy"}


def note_name(n: int) -> str:
    return f"{NAMES[n % 12]}{n // 12 - 1}"


def describe(e: dict, last_state: dict) -> str | None:
    t = e.get("t")
    if t == "welcome":
        return f"Połączono z routerem (protokół v{e.get('v')}). Graj - tu pojawi się każda nuta."
    if t == "note":
        who = "" if e.get("src") == "keys" else f"   [zagrał: {e.get('src')}]"
        if e.get("on"):
            raw = f" (klawiatura zmierzyła {e['raw']})" if e.get("src") == "keys" else ""
            return f"♪ {note_name(e['note']):<4} siła {e['vel']:>3}{raw}{who}"
        return None                                   # note-offs would only clutter the view
    if t == "pedal":
        state = "WCIŚNIĘTY" if e.get("value", 0) >= 64 else "puszczony"
        return f"  pedał {e.get('pedal')}: {state} ({e.get('value')})"
    if t == "button":
        return f"  przycisk na klawiaturze: Program Change {e.get('program')}"
    if t == "state":
        keys = ("mode", "una_corda", "touch", "ones", "connected")
        now = {k: e.get(k) for k in keys}
        if now == last_state:
            return None
        last_state.clear()
        last_state.update(now)
        return ("  STAN: pedał {m} | una corda {u} | czucie {t} | „1” {o} | klawiatura {c}".format(
            m=now["mode"], u="WŁ" if now["una_corda"] else "wył", t=TOUCH.get(now["touch"], now["touch"]),
            o=now["ones"], c="podłączona" if now["connected"] else "BRAK"))
    return None


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if hasattr(socket, "SIO_UDP_CONNRESET"):
        s.ioctl(socket.SIO_UDP_CONNRESET, False)
    s.bind(("127.0.0.1", 0))
    s.settimeout(0.2)
    try:
        import msvcrt
    except ImportError:
        msvcrt = None
    print("Podgląd szyny routera. Klawisze: t = test dźwięku, q = koniec.\n")
    last_hello = 0.0
    last_heard = time.time()
    warned = False
    last_state: dict = {}
    while True:
        now = time.time()
        if now - last_hello > 3:
            s.sendto(b'{"t":"hello","name":"podglad"}', ROUTER)
            last_hello = now
        if now - last_heard > 4 and not warned:
            print("!! Router nie odpowiada. Czy działa? (status.json, log routera)")
            warned = True
        if msvcrt and msvcrt.kbhit():
            key = msvcrt.getwch().lower()
            if key == "q":
                s.sendto(b'{"t":"bye"}', ROUTER)
                return
            if key == "t":
                for i, n in enumerate((60, 64, 67, 72)):
                    s.sendto(json.dumps({"t": "play", "midi": [[0x90, n, 70]]}).encode(), ROUTER)
                    time.sleep(0.18)
                time.sleep(0.4)
                s.sendto(json.dumps({"t": "play", "midi": [[0x80, n, 0] for n in (60, 64, 67, 72)]}).encode(),
                         ROUTER)
        try:
            data, _ = s.recvfrom(8192)
        except socket.timeout:
            continue
        except OSError:
            continue
        last_heard = time.time()
        if warned:
            print("Router znowu odpowiada.")
            warned = False
        try:
            line = describe(json.loads(data), last_state)
        except ValueError:
            continue
        if line:
            print(line, flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
