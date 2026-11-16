"""Faders C2..C8 on any Studio One channel (Claude, 16.11.2026, Miki).

C1 stays on the first mixer channel and C9 on Main (the control surface, as before). C2..C8 no longer go
to the surface bank (which followed the console order, so they landed on the grouped Klik channels).
Instead each is assigned to a channel by its name and the router hands the moves to the studio-one-mcp
bridge script running inside Studio One:

  router  -> mailbox/faders-in.json  {"seq": n, "moves": {"Bas Bus": 0.56, ...}}   (gain, 1.0 = 0 dB)
          -> TCP 127.0.0.1:47688 "doorbell" (studio_one_bridge.py rings the bridge device)
  bridge  -> sets the channels' volume, writes mailbox/faders-out.json
             {"seq": n, "selected": "Bas Bus", "channels": ["Out 1/2", ...]}

Assigning:
  * on the keyboard: select a channel in Studio One, press C54 ("PRZYPISZ"), move a fader C2..C8
    within ASSIGN_S seconds: that fader now drives the selected channel;
  * from the Keystation Status plugin: click a fader's label and pick a channel (live-cmd "fader").
The map lives in fader-map.json next to the router and survives restarts; a name the open song does not
have is simply ignored by the bridge.
"""
from __future__ import annotations

import json
import math
import os
import socket
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAP_FILE = ROOT / "fader-map.json"
MAILBOX = Path.home() / ".studio-one-mcp" / "mailbox"
BRIDGE = ("127.0.0.1", 47688)
FADERS = ("C2", "C3", "C4", "C5", "C6", "C7", "C8")
DEFAULT_MAP = {"C2": "Perkusja Bus", "C3": "Klawisze Bus", "C4": "Bas Bus", "C5": "Klik Bus",
               "C6": "Track 2", "C7": "FX 1", "C8": "Pianino Bus"}
ASSIGN_PROGRAM = 10        # C54 sends Program Change 10 on P10
ASSIGN_S = 10.0
SEND_GAP_S = 0.03          # at most ~33 updates a second go to Studio One
# fader position (0..1) -> dB: 0 dB at three quarters of the travel, +10 dB at the top
KNOTS = ((0.0, -60.0), (0.25, -30.0), (0.5, -12.0), (0.75, 0.0), (1.0, 10.0))


def gain_for(value: int) -> float:
    """Physical fader value -> channel gain. 0 = silence, 127 (the very top) = exactly 0 dB, as before."""
    if value <= 0:
        return 0.0
    if value >= 127:
        return 1.0
    p = value / 126
    for (x0, y0), (x1, y1) in zip(KNOTS, KNOTS[1:]):
        if p <= x1:
            db = y0 + (y1 - y0) * (p - x0) / (x1 - x0)
            return round(10 ** (db / 20), 6)
    return round(10 ** (KNOTS[-1][1] / 20), 6)


def load_map(path: Path = MAP_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_MAP)
    if not isinstance(data, dict):
        return dict(DEFAULT_MAP)
    return {f: data[f] for f in FADERS if isinstance(data.get(f), str) and data[f]}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def ring_doorbell(address=BRIDGE, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection(address, timeout=timeout) as s:
            s.sendall(b"doorbell\n")
            return s.recv(16).startswith(b"ok")
    except OSError:
        return False


class FaderLink:
    """Thread-safe: move()/arm() are called from the MIDI callback and only touch memory."""

    def __init__(self, mailbox: Path = MAILBOX, map_path: Path = MAP_FILE, doorbell=ring_doorbell):
        self.mailbox = Path(mailbox)
        self.map_path = Path(map_path)
        self.doorbell = doorbell
        self.map = load_map(self.map_path)
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.pending: dict[str, float] = {}
        self.ring = False
        self.seq = int(time.time() * 1000)
        self.armed_until = 0.0
        self.last_assigned: tuple[str, str] | None = None
        self.bridge_ok = None

    # ---- called from the MIDI path -------------------------------------------------
    def move(self, fader: str, value: int, now: float | None = None) -> str | None:
        """A fader moved. Returns the channel name it drives (None = unassigned)."""
        now = time.time() if now is None else now
        with self.lock:
            if self.armed_until and now < self.armed_until:
                selected = self.out().get("selected")
                if isinstance(selected, str) and selected:
                    self._assign(fader, selected)
                self.armed_until = 0.0
            target = self.map.get(fader)
            if target:
                self.pending[target] = gain_for(value)
                self.wake.set()
        return target

    def arm(self, now: float | None = None) -> None:
        """C54: the next fader moved takes the channel selected in Studio One."""
        now = time.time() if now is None else now
        with self.lock:
            self.armed_until = now + ASSIGN_S
            self.ring = True                      # let the bridge report the selection right now
            self.wake.set()

    # ---- commands --------------------------------------------------------------------
    def assign(self, fader: str, channel: str | None) -> bool:
        if fader not in FADERS:
            return False
        with self.lock:
            self._assign(fader, channel)
        return True

    def _assign(self, fader: str, channel: str | None) -> None:
        if channel:
            self.map[fader] = channel
        else:
            self.map.pop(fader, None)
        self.last_assigned = (fader, channel or "")
        try:
            write_json(self.map_path, self.map)
        except OSError:
            pass

    # ---- the bridge side -------------------------------------------------------------
    def out(self) -> dict:
        try:
            data = json.loads((self.mailbox / "faders-out.json").read_text(encoding="utf-8-sig"))  # Studio One writes a BOM
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def flush(self) -> bool:
        with self.lock:
            moves, self.pending = self.pending, {}
            ring, self.ring = self.ring, False
            if moves:
                self.seq += 1
            seq = self.seq
        if not moves and not ring:
            return False
        if moves:
            try:
                write_json(self.mailbox / "faders-in.json", {"seq": seq, "moves": moves})
            except OSError:
                return False
        self.bridge_ok = self.doorbell()
        return True

    def run(self, done: threading.Event) -> None:
        while not done.is_set():
            self.wake.wait(1.0)
            self.wake.clear()
            if self.flush():
                time.sleep(SEND_GAP_S)

    def state(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        out = self.out()
        with self.lock:
            return {
                "map": dict(self.map),
                "assigning": round(max(0.0, self.armed_until - now), 1),
                "selected": out.get("selected"),
                "channels": out.get("channels") if isinstance(out.get("channels"), list) else [],
                "bridge": self.bridge_ok,
            }
