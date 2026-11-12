"""Szyna UDP (06.11.2026): everything the router knows, sent live to any program
on this PC that asks for it.

Why: Studio One does not pass MIDI to third-party MIDI plugins, and a MIDI port
can only be opened by one program at a time. The router already sees every
note, pedal and button, so it shares them here instead. Any number of
listeners (DAW plugins, trainers, the preview script) can join and leave at
any time; nothing breaks if nobody listens.

Protocol, version 1. One JSON object per UDP datagram, UTF-8, localhost only.
Readers must ignore unknown fields and unknown "t" values.

Listener -> router (127.0.0.1:47800):
  {"t":"hello","name":"trener"}       join (repeat at least every 5 s, else dropped
                                      after EXPIRE_S); answered with "welcome" + "state"
  {"t":"bye"}                         leave now
  {"t":"set","set":{"touch":"light"}} same as the plugin's live-cmd.json
                                      (mode, una_corda, touch, ones)
  {"t":"play","midi":[[144,60,80],...]}
                                      play notes on Pianoteq through the router's play
                                      port: only note on/off (0x80/0x90), max 64 per
                                      datagram. Notes still held when the listener leaves
                                      or times out are released automatically.

Router -> listener:
  {"t":"welcome","v":1,"name":..,"expire_s":..}
  {"t":"note","on":true,"note":60,"raw":98,"vel":72,"ch":0,"src":"keys","ts":..}
        raw = what the keyboard measured, vel = what the instrument got (after the
        touch-mode map); note off: on=false, raw/vel 0. src "keys" = played by hand,
        otherwise the name of the listener that sent "play".
  {"t":"pedal","pedal":"sustain","cc":64,"value":127,"ts":..}
        the physical pedal; cc = what the instrument got (64 sustain, 66 sostenuto)
  {"t":"button","program":12,"ts":..}   a keyboard button (Program Change number)
  {"t":"state", ...same fields as live.json...}   on every change and once a second
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time

HOST = "127.0.0.1"
PORT = 47800
EXPIRE_S = 10.0
MAX_PLAY = 64
MAX_DATAGRAM = 8192


class UdpBus:
    def __init__(self, on_set=None, on_play=None, port: int = PORT, host: str = HOST,
                 clock=time.time):
        """on_set(dict) applies a settings change; on_play(list[bytes]) sends MIDI to
        the instrument. Both are called from the bus thread."""
        self.on_set = on_set
        self.on_play = on_play
        self.clock = clock
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            # Windows: don't turn "that listener is gone" into errors on our socket
            self.sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        self.sock.bind((host, port))
        self.sock.settimeout(0.5)
        self.address = self.sock.getsockname()
        self.lock = threading.Lock()
        self.subs: dict[tuple, dict] = {}     # addr -> {"name", "until", "held": set()}
        self.state_fn = None
        self.sent = 0
        self.dropped = 0
        self._stop = threading.Event()
        self._thread = None

    # --- sending -------------------------------------------------------------
    def listeners(self) -> list[str]:
        with self.lock:
            return [s["name"] for s in self.subs.values()]

    def publish(self, event: dict, only=None):
        if not self.subs:
            return
        data = json.dumps(event, separators=(",", ":")).encode("utf-8")
        with self.lock:
            targets = [only] if only else list(self.subs)
        for addr in targets:
            try:
                self.sock.sendto(data, addr)
                self.sent += 1
            except OSError:
                # Windows reports "port unreachable" from an earlier send on the next call;
                # the listener is gone, expiry removes it.
                self.dropped += 1

    def note(self, on: bool, note: int, raw: int, vel: int, ch: int = 0, src: str = "keys"):
        self.publish({"t": "note", "on": on, "note": note, "raw": raw, "vel": vel,
                      "ch": ch, "src": src, "ts": round(self.clock(), 4)})

    def pedal(self, pedal: str, cc: int, value: int):
        self.publish({"t": "pedal", "pedal": pedal, "cc": cc, "value": value,
                      "ts": round(self.clock(), 4)})

    def button(self, program: int):
        self.publish({"t": "button", "program": program, "ts": round(self.clock(), 4)})

    def state(self, snapshot: dict, only=None):
        event = dict(snapshot)
        event["t"] = "state"
        self.publish(event, only)

    # --- receiving -----------------------------------------------------------
    def handle(self, data: bytes, addr) -> None:
        try:
            msg = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return
        if not isinstance(msg, dict):
            return
        kind = msg.get("t")
        now = self.clock()
        if kind == "hello":
            name = str(msg.get("name") or f"{addr[0]}:{addr[1]}")[:40]
            with self.lock:
                new = addr not in self.subs
                sub = self.subs.setdefault(addr, {"name": name, "held": set()})
                sub["name"] = name
                sub["until"] = now + EXPIRE_S
            if new:
                logging.info("Bus listener joined: %s %s", name, addr)
                self.publish({"t": "welcome", "v": 1, "name": name, "expire_s": EXPIRE_S}, addr)
                if self.state_fn:
                    self.state(self.state_fn(), addr)
            return
        with self.lock:
            sub = self.subs.get(addr)
        if sub is None:
            return                         # only joined listeners may control the router
        if kind == "bye":
            self._drop(addr, "bye")
        elif kind == "set" and isinstance(msg.get("set"), dict) and self.on_set:
            self.on_set(msg["set"])
        elif kind == "play" and isinstance(msg.get("midi"), list) and self.on_play:
            packets = []
            for item in msg["midi"][:MAX_PLAY]:
                if (isinstance(item, list) and len(item) == 3
                        and all(isinstance(b, int) and 0 <= b <= 255 for b in item)
                        and item[0] & 0xE0 == 0x80 and item[1] < 128 and item[2] < 128):
                    packets.append(bytes(item))
            if not packets:
                return
            with self.lock:
                for p in packets:
                    key = (p[0] & 0x0F, p[1])
                    if p[0] & 0xF0 == 0x90 and p[2] > 0:
                        sub["held"].add(key)
                    else:
                        sub["held"].discard(key)
            self.on_play(packets)
            for p in packets:
                on = p[0] & 0xF0 == 0x90 and p[2] > 0
                self.note(on, p[1], 0, p[2] if on else 0, p[0] & 0x0F, sub["name"])

    def _drop(self, addr, why: str):
        with self.lock:
            sub = self.subs.pop(addr, None)
        if sub is None:
            return
        logging.info("Bus listener left (%s): %s", why, sub["name"])
        if sub["held"] and self.on_play:
            self.on_play([bytes((0x80 | ch, note, 0)) for ch, note in sorted(sub["held"])])

    def expire(self):
        now = self.clock()
        with self.lock:
            gone = [a for a, s in self.subs.items() if s["until"] < now]
        for addr in gone:
            self._drop(addr, "timeout")

    def _loop(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(MAX_DATAGRAM)
            except socket.timeout:
                self.expire()
                continue
            except OSError:
                # ConnectionResetError on Windows after sending to a closed port: harmless
                continue
            try:
                self.handle(data, addr)
            except Exception:
                logging.exception("Bus message rejected from %s", addr)
            self.expire()

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="udp-bus", daemon=True)
        self._thread.start()
        return self

    def close(self):
        self._stop.set()
        for addr in list(self.subs):
            self._drop(addr, "router stopping")
        try:
            self.sock.close()
        except OSError:
            pass
