"""Low-latency Keystation P10 MIDI relay with two outputs (Claude rev. 2026-10-28b).

PLAY port  ("Keystation Pedal Modes"): only what an instrument should hear -
notes, pitch bend, mod wheel, expression, pedals (sustain/sostenuto,
una corda), channel-mode messages, and the 24 free sound knobs
(B10..B17 -> CC 14,15,20,21,86..89; B18..B33 -> CC104..119) so instruments can
MIDI-learn them. Feeds Studio One's "Keystation Pro 88"
device, i.e. the VelCal track, so nothing on the playing path changes.

CONTROL port ("Keystation Control"): faders, buttons and transport keys.
C60 (PC16) is passed through: the "Keystation Pro 88 Control" surface resets Main
to exactly 0 dB. Feeds a separate control-surface instance, so mixer moves can no longer
leak into Pianoteq/Kontakt as sound-changing CCs or Program Changes.

Celeste removed (28.10, user). B10..B17 no longer pan mixer channels.
Soft sustain release (28.10): letting go of the pedal in sustain mode sends a
short falling ramp of CC64 values instead of an instant 0, so dampers land
softly. Length in ms in the file "release-ms" (default 120, 0 = off).
Velocity calibration (28.10): note-on velocities go through "velocity-map.json"
({"white":[128], "black":[128]}, index = raw velocity, keyboard on curve C1),
reloaded when the file changes; no file = velocities untouched.
Context-aware "1" (29.10): raw velocity 1 means "slower than the sensor can
measure". Instead of a fixed ppp, it gets one dynamic step below the level of
the phrase being played (running average of the last notes), never above
ONES_CAP; after a pause it is plain ppp. File "ones-mode" = "ppp" turns it off.
A file named
"capture-notes" makes the router append every raw key event to notes.csv.
"""

from __future__ import annotations

import ctypes
import re
import json
import logging
import os
from pathlib import Path
import signal
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor"))
import rtmidi  # noqa: E402
from udp_bus import UdpBus  # noqa: E402  (06.11: live bus for plugins and trainers)

INPUT_NAME = "Keystation Pro 88"
_INPUT_RE = re.compile(r"^(?:\d+-\s*)?" + re.escape(INPUT_NAME) + r"(?:\s+\d+)?$", re.IGNORECASE)


def find_input(names) -> int | None:
    """Index of the keyboard's main MIDI input. Windows renames a device moved to
    another USB port to e.g. "2- Keystation Pro 88"; extra ports (MIDIIN2 ...) are skipped."""
    exact = [i for i, n in enumerate(names) if _INPUT_RE.match(n.strip())]
    if exact:
        return exact[0]
    loose = [i for i, n in enumerate(names)
             if INPUT_NAME.lower() in n.lower() and not n.upper().startswith(("MIDIIN", "MIDIOUT"))]
    return loose[0] if loose else None
PLAY_NAME = "Keystation Pedal Modes"   # name kept: Studio One already points here
CONTROL_NAME = "Keystation Control"
STATUS_FILE = ROOT / "status.json"
TEST_FILE = ROOT / "test-midi.hex"
DEBUG_FILE = ROOT / "debug-raw"   # create this file to log every raw CC/PC
RELEASE_FILE = ROOT / "release-ms"
VELMAP_FILE = ROOT / "velocity-map.json"
# Touch modes (02.11): like Light/Normal/Heavy on digital pianos. Buttons C53/C54/C55
# send Program Change 9/10/11; each picks velocity-map.<mode>.json. The choice is kept
# in the file "touch-mode". Without preset files the single velocity-map.json is used.
TOUCH_BUTTONS = {9: "light", 10: "acoustic", 11: "heavy"}
TOUCH_FILE = ROOT / "touch-mode"
DEFAULT_TOUCH = "acoustic"
MONITOR_NAME = "Keystation Monitor"   # copy of played notes (after mapping) for the dynamics mirror page
# Live state for the mirror page (05.11): on the monitor port only, MIDI channel 16 CCs,
# sent on every change and once a second: CC20 pedal mode (0 sustain, 1 sostenuto),
# CC21 una corda (0/127), CC22 touch (0 light, 1 acoustic, 2 heavy, 127 none),
# CC23 "1" mode (0 ppp, 1 context), CC24 keyboard connected (0/1).
# Pedal CC64/66/67 sent to the play port are mirrored to the monitor port too.
STATE_CHANNEL = 15
TOUCH_CODE = {"light": 0, "acoustic": 1, "heavy": 2}
RESTART_FILE = ROOT / "restart-router"   # create it: router exits cleanly, supervisor restarts it


def touch_preset_file(mode: str) -> Path:
    return ROOT / f"velocity-map.{mode}.json"
CAPTURE_FLAG = ROOT / "capture-notes"
ONES_MODE_FILE = ROOT / "ones-mode"
ONES_STEP = 16           # one dynamic level below the phrase
ONES_CAP = 45            # never louder than p/mp border (accidental brushes stay soft)
PHRASE_ALPHA = 0.35      # weight of the newest note in the phrase level
PHRASE_TIMEOUT = 2.0     # seconds of silence that end a phrase
CAPTURE_FILE = ROOT / "notes.csv"
# Live state for the DAW plugin "Keystation Status" (06.11): versioned JSON, written
# atomically on every change and once a second. Readers must ignore unknown fields.
LIVE_FILE = ROOT / "live.json"
LIVE_MIN_GAP_S = 0.05
# Commands from the plugin (06.11): {"v":1,"id":..,"set":{"mode","una_corda","touch","ones"}}
CMD_FILE = ROOT / "live-cmd.json"
CMD_POLL_S = 0.04
# UDP bus (06.11): notes, pedal, buttons and state, live, for any number of listeners on
# this PC (127.0.0.1:47800, protocol in udp_bus.py). File "szyna-off" turns it off.
BUS_OFF_FILE = ROOT / "szyna-off"
BLACK_KEYS = {1, 3, 6, 8, 10}


def load_velocity_map(path=VELMAP_FILE):
    """Return (white, black) lookup lists, or None when absent/invalid."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        white, black = data["white"], data["black"]
        if len(white) != 128 or len(black) != 128:
            return None
        if not all(isinstance(v, int) and 1 <= v <= 127 for v in white[1:] + black[1:]):
            return None
        return white, black
    except Exception:
        return None
DEFAULT_RELEASE_MS = 120
RELEASE_STEPS = 8


def release_ms() -> int:
    try:
        return max(0, min(1000, int(RELEASE_FILE.read_text(encoding="ascii").strip())))
    except Exception:
        return DEFAULT_RELEASE_MS


def ramp_values(start: int, steps: int = RELEASE_STEPS) -> list[int]:
    """Falling CC values from start to 0, fast at first (dampers settle), last one 0."""
    values = [round(start * (1 - k / steps) ** 1.5) for k in range(1, steps + 1)]
    out = []
    for v in values:
        if not out or v != out[-1]:
            out.append(v)
    if out[-1] != 0:
        out.append(0)
    return out
MODE_CC = {"sustain": 64, "sostenuto": 66}
# Program Change numbers measured on the physical P10 (router.log 28.10).
PROGRAM_BUTTONS = {2: "sustain", 3: "sostenuto"}
UNA_CORDA_BUTTON = 4
# Faders (31.10, Miki): physical 0..126 = full Studio One range, silence..+10 dB
# (scaled so 126 reaches CC 127 = +10 dB); the very top, 127, is "reset": a
# Program Change the surface maps to DefaultValue = exactly 0 dB (no 7-bit CC
# value is exactly 0 dB: 96 = -0.17, 97 = +0.16).
FADER_CC = (73, 72, 91, 93, 74, 71, 5, 84)   # C1..C8, mixer channels 1..8
FADER_TOP_CC = 127
FADER_ZERO_PROGRAM = 20                        # PC 20..27 channels, 28 Main


def fader_messages(status: int, cc: int, value: int) -> list[bytes]:
    is_main = cc == RAW_MAIN_FADER_CC
    out_cc = MAIN_FADER_CC if is_main else cc
    if value >= 127:
        program = FADER_ZERO_PROGRAM + (8 if is_main else FADER_CC.index(cc))
        return [bytes((0xC0 | (status & 0x0F), program))]
    return [bytes((status, out_cc, round(value * FADER_TOP_CC / 126)))]


LISTEN_KEY = None        # optional key-as-button for Listen Bus (e.g. 108 = C8); off: C52 does it (31.10)
LISTEN_PROGRAM = 17      # Program Change sent to the control port for it
MAIN_FADER_CC = 83              # C9 in the surface map
RAW_MAIN_FADER_CC = 7           # physical C9 suspected to send CC7 (standard volume)
# B10..B17 (were mixer pan) -> free CCs no surface control listens to.
PAN_KNOB_CC = dict(zip((10, 2, 12, 13, 75, 76, 92, 95), (14, 15, 20, 21, 86, 87, 88, 89)))
KNOB_CC = dict(zip((42, 34, 44, 45, 77, 78, 79, 94, 16, 17, 18, 19, 80, 81),
                   range(104, 118)))
CHANNEL_PRESSURE_KNOB_CC = 118  # physical B32
RPN_KNOB_CC = 119               # physical B33 (RPN 0, Data Entry)

PLAY, CONTROL = "play", "control"
# Controller numbers an instrument is meant to receive from a keyboard.
PLAY_CC = ({1, 11, 64, 66, 67} | set(PAN_KNOB_CC.values()) | set(range(104, 120))
           | set(range(120, 128)))


def destination(packet: bytes) -> str:
    """Which output a transformed packet belongs to."""
    kind = packet[0] & 0xF0
    if kind in (0x80, 0x90, 0xA0, 0xE0):
        return PLAY
    if kind == 0xB0 and len(packet) >= 2 and packet[1] in PLAY_CC:
        return PLAY
    return CONTROL


class PedalMapper:
    def __init__(self):
        self.mode = "sustain"
        self.pedal_values = [0] * 16
        self.una_corda_values = [0] * 16
        self.active_notes = [set() for _ in range(16)]
        self.release_ms = DEFAULT_RELEASE_MS
        self.ramp_gen = [0] * 16          # bump to cancel a running ramp
        self.ramp_cc = [None] * 16        # CC a ramp is running on, None = idle
        self.pending_ramps = []           # (channel, cc, values, gen) to schedule
        self.velocity_map = None          # (white, black) or None = untouched
        self.touch_maps = {}              # mode -> (white, black)
        self.touch_mode = None
        self.touch_dirty = False          # button changed the mode -> main loop saves it
        self.ones_context = True
        self.phrase_level = [None] * 16   # running output level per channel
        self.phrase_time = [0.0] * 16

    def ones_velocity(self, channel: int, now: float, floor: int) -> int:
        """Raw 1 = too slow to measure. floor = what the map gives a lone 1 (ppp)."""
        level = self.phrase_level[channel]
        if level is None or now - self.phrase_time[channel] > PHRASE_TIMEOUT:
            return floor
        return int(round(max(floor, min(ONES_CAP, level - ONES_STEP))))

    def note_played(self, channel: int, out_velocity: int, now: float):
        level = self.phrase_level[channel]
        if level is None or now - self.phrase_time[channel] > PHRASE_TIMEOUT:
            level = float(out_velocity)
        else:
            level = PHRASE_ALPHA * out_velocity + (1 - PHRASE_ALPHA) * level
        self.phrase_level[channel] = level
        self.phrase_time[channel] = now

    def _cancel_ramp(self, channel: int) -> list[bytes]:
        """Stop a running ramp; returns the 0 needed if it was mid-way."""
        cc = self.ramp_cc[channel]
        self.ramp_gen[channel] += 1
        self.ramp_cc[channel] = None
        return [bytes((0xB0 | channel, cc, 0))] if cc is not None else []

    def ramp_step_done(self, channel: int, gen: int, last: bool) -> bool:
        """True if this ramp step should still be sent."""
        if self.ramp_gen[channel] != gen:
            return False
        if last:
            self.ramp_cc[channel] = None
        return True

    def take_ramps(self):
        ramps, self.pending_ramps = self.pending_ramps, []
        return ramps

    def _select(self, requested: str) -> list[bytes]:
        new_mode = "sustain" if requested == self.mode and requested != "sustain" else requested
        if new_mode == self.mode:
            return []
        old_cc, new_cc = MODE_CC[self.mode], MODE_CC[new_mode]
        packets = []
        for channel in range(16):
            packets += self._cancel_ramp(channel)
        for channel, value in enumerate(self.pedal_values):
            if value:
                packets.append(bytes((0xB0 | channel, old_cc, 0)))
                packets.append(bytes((0xB0 | channel, new_cc, value)))
        self.mode = new_mode
        return packets

    def transform(self, message: list[int] | bytes, now: float | None = None) -> list[bytes]:
        if now is None:
            now = time.monotonic()
        if not message:
            return []
        data = bytes(message)
        status = data[0]
        channel = status & 0x0F
        if status & 0xF0 == 0xD0 and len(data) >= 2:
            return [bytes((0xB0 | channel, CHANNEL_PRESSURE_KNOB_CC, data[1]))]
        if len(data) >= 3 and status & 0xF0 in (0x80, 0x90) and data[1] == LISTEN_KEY:
            # top C8 is a button: press = toggle Listen Bus (headphones/speakers) in Studio One
            if status & 0xF0 == 0x90 and data[2] > 0:
                return [bytes((0xC0 | channel, LISTEN_PROGRAM))]
            return []
        if len(data) >= 3 and status & 0xF0 in (0x80, 0x90):
            notes = self.active_notes[channel]
            if status & 0xF0 == 0x90 and data[2] > 0:
                notes.add(data[1])
                if self.velocity_map is not None:
                    table = self.velocity_map[1 if data[1] % 12 in BLACK_KEYS else 0]
                    if data[2] == 1 and self.ones_context:
                        out = self.ones_velocity(channel, now, table[1])
                    else:
                        out = table[data[2]]
                        self.note_played(channel, out, now)
                    return [bytes((status, data[1], out))]
            else:
                notes.discard(data[1])
        if len(data) >= 2 and status & 0xF0 == 0xC0:
            if data[1] == UNA_CORDA_BUTTON:
                value = 0 if self.una_corda_values[channel] else 127
                self.una_corda_values[channel] = value
                return [bytes((0xB0 | channel, 67, value))]
            touch = TOUCH_BUTTONS.get(data[1])
            if touch:
                if touch in self.touch_maps:
                    self.velocity_map = self.touch_maps[touch]
                    self.touch_mode = touch
                    self.touch_dirty = True
                return []
            selected = PROGRAM_BUTTONS.get(data[1])
            if selected:
                return self._select(selected)
        if len(data) >= 3 and status & 0xF0 == 0xB0:
            cc, value = data[1], data[2]
            if cc in KNOB_CC:
                return [bytes((status, KNOB_CC[cc], value))]
            if cc in PAN_KNOB_CC:
                return [bytes((status, PAN_KNOB_CC[cc], value))]
            if cc in FADER_CC or cc == RAW_MAIN_FADER_CC:
                return fader_messages(status, cc, value)
            # P10 B33 sends RPN 0 selector (CC100=0, CC101=0), then CC6 values.
            if cc == 100 and value == 0:
                return []
            if cc == 101 and value == 0:
                return []
            if cc == 6:
                return [bytes((status, RPN_KNOB_CC, value))]
            if cc == 64:
                previous = self.pedal_values[channel]
                self.pedal_values[channel] = value
                out_cc = MODE_CC[self.mode]
                if (value == 0 and previous > 0 and self.mode == "sustain"
                        and self.release_ms > 0):
                    self._cancel_ramp(channel)
                    self.ramp_cc[channel] = out_cc
                    self.pending_ramps.append((channel, out_cc, ramp_values(previous),
                                               self.ramp_gen[channel]))
                    return []
                self._cancel_ramp(channel)
                return [bytes((status, out_cc, value))]
        return [data]

    def route(self, message: list[int] | bytes, now: float | None = None) -> list[tuple[str, bytes]]:
        return [(destination(p), p) for p in self.transform(message, now)]

    def release_all(self) -> list[bytes]:
        packets = []
        for channel, value in enumerate(self.pedal_values):
            ramp = self._cancel_ramp(channel)
            if value:
                packets.append(bytes((0xB0 | channel, MODE_CC[self.mode], 0)))
                self.pedal_values[channel] = 0
            elif ramp:
                packets += ramp
            if self.una_corda_values[channel]:
                packets.append(bytes((0xB0 | channel, 67, 0)))
                self.una_corda_values[channel] = 0
            for note in sorted(self.active_notes[channel]):
                packets.append(bytes((0x80 | channel, note, 0)))
            self.active_notes[channel].clear()
        self.mode = "sustain"
        return packets


class VirtualPort:
    def __init__(self, name: str):
        self.name = name
        self.dll = ctypes.WinDLL(r"C:\Windows\System32\teVirtualMIDI64.dll", use_last_error=True)
        self.dll.virtualMIDICreatePortEx2.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p,
                                                      ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
        self.dll.virtualMIDICreatePortEx2.restype = ctypes.c_void_p
        self.dll.virtualMIDISendData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint32]
        self.dll.virtualMIDISendData.restype = ctypes.c_bool
        self.dll.virtualMIDIClosePort.argtypes = [ctypes.c_void_p]
        self.handle = self.dll.virtualMIDICreatePortEx2(name, None, 0, 65535, 1)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), f"Could not create {name}")

    def send(self, data: bytes):
        if len(data) > 65535:
            raise ValueError("MIDI packet exceeds port capacity")
        packet = (ctypes.c_ubyte * len(data))(*data)
        if not self.dll.virtualMIDISendData(self.handle, packet, len(data)):
            raise OSError(ctypes.get_last_error(), f"Virtual MIDI send failed on {self.name}")

    def close(self):
        if self.handle:
            self.dll.virtualMIDIClosePort(self.handle)
            self.handle = None


def run():
    logging.basicConfig(filename=ROOT / "router.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, r"Local\CodexKeystationPedalModes")
    if not mutex or ctypes.get_last_error() == 183:
        raise RuntimeError("Pedal router is already running")
    logging.info("STARTING pid %s", os.getpid())
    ports = {}
    for attempt in range(1, 151):          # right after boot the driver may not be ready yet
        try:
            ports = {PLAY: VirtualPort(PLAY_NAME), CONTROL: VirtualPort(CONTROL_NAME)}
            break
        except OSError as exc:
            for p in ports.values():
                p.close()
            ports = {}
            logging.warning("Virtual ports not ready (attempt %d): %s", attempt, exc)
            time.sleep(2)
    if not ports:
        raise RuntimeError("Virtual MIDI ports could not be created for 5 minutes")
    try:
        monitor = VirtualPort(MONITOR_NAME)
    except OSError as exc:
        monitor = None
        logging.warning("Monitor port unavailable: %s", exc)
    mapper = PedalMapper()
    done = threading.Event()
    midi_in = None
    counts = {PLAY: 0, CONTROL: 0}
    messages = 0
    errors = 0
    last_input = 0.0

    def stop(*_):
        done.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    io_lock = threading.Lock()

    def send(dest, packet):
        ports[dest].send(packet)
        counts[dest] += 1
        if monitor is not None and dest == PLAY and packet and (
                packet[0] & 0xE0 == 0x80
                or (packet[0] & 0xF0 == 0xB0 and len(packet) >= 3 and packet[1] in (64, 66, 67))):
            try:
                monitor.send(packet)          # notes + pedals, for the dynamics mirror page
            except OSError:
                pass

    def publish_state(connected):
        if monitor is None:
            return
        ch = 0xB0 | STATE_CHANNEL
        state = (
            (20, 0 if mapper.mode == "sustain" else 1),
            (21, 127 if mapper.una_corda_values[0] else 0),
            (22, TOUCH_CODE.get(mapper.touch_mode, 127)),
            (23, 1 if mapper.ones_context else 0),
            (24, 1 if connected else 0),
        )
        try:
            for cc, value in state:
                monitor.send(bytes((ch, cc, value)))
        except OSError:
            pass

    def ramp_step(channel, gen, packet, last):
        with io_lock:
            if mapper.ramp_step_done(channel, gen, last):
                send(PLAY, packet)

    def schedule_ramps():
        step_s = mapper.release_ms / 1000 / RELEASE_STEPS
        for channel, cc, values, gen in mapper.take_ramps():
            for i, v in enumerate(values):
                packet = bytes((0xB0 | channel, cc, v))
                if i == 0:
                    if mapper.ramp_step_done(channel, gen, len(values) == 1):
                        send(PLAY, packet)
                    continue
                t = threading.Timer(step_s * i, ramp_step, (channel, gen, packet, i == len(values) - 1))
                t.daemon = True
                t.start()

    velmap_mtime = None
    input_label = None
    last_missing_log = 0.0
    errors_loop = [0]

    live_event = threading.Event()
    live_last = {}
    bus_ref = [None]

    def live_snapshot():
        return {
            "v": 1,
            "connected": midi_in is not None,
            "mode": mapper.mode,
            "pedal": max(mapper.pedal_values),
            "una_corda": bool(mapper.una_corda_values[0]),
            "touch": mapper.touch_mode,
            "ones": "context" if mapper.ones_context else "ppp",
            "last": dict(live_last) or None,
            "updated": time.time(),
        }

    def live_writer():
        tmp = LIVE_FILE.with_name("live.json.tmp")
        bus_sent = (None, 0.0)
        while not done.is_set():
            live_event.wait(1.0)
            live_event.clear()
            snap = live_snapshot()
            try:
                tmp.write_text(json.dumps(snap), encoding="utf-8")
                os.replace(tmp, LIVE_FILE)
            except OSError:
                pass          # file briefly busy: the next change or tick rewrites it
            bus = bus_ref[0]
            if bus is not None:
                # state on the bus: when a setting changes, else once a second (notes have
                # their own events, so "last"/"updated" alone don't count as a change)
                key = tuple(v for k, v in snap.items() if k not in ("last", "updated"))
                if key != bus_sent[0] or time.time() - bus_sent[1] >= 1.0:
                    bus.state(snap)
                    bus_sent = (key, time.time())
            time.sleep(LIVE_MIN_GAP_S)

    threading.Thread(target=live_writer, name="live-json", daemon=True).start()

    def apply_command(want):
        """Same effect as pressing the physical buttons."""
        presses = []
        mode = want.get("mode")
        if mode in PROGRAM_BUTTONS.values() and mode != mapper.mode:
            presses.append(next(k for k, v in PROGRAM_BUTTONS.items() if v == mode))
        una = want.get("una_corda")
        if isinstance(una, bool) and una != bool(mapper.una_corda_values[0]):
            presses.append(UNA_CORDA_BUTTON)
        touch = want.get("touch")
        if touch in TOUCH_BUTTONS.values() and touch != mapper.touch_mode:
            presses.append(next(k for k, v in TOUCH_BUTTONS.items() if v == touch))
        for program in presses:
            dispatch(bytes((0xC0, program)))
        ones = want.get("ones")
        if ones in ("context", "ppp"):
            try:
                ONES_MODE_FILE.write_text(ones, encoding="ascii")
            except OSError:
                pass
            mapper.ones_context = ones == "context"
        logging.info("Plugin command %s -> programs %s", want, presses)
        with io_lock:
            publish_state(midi_in is not None)
        live_event.set()

    def command_watcher():
        while not done.is_set():
            time.sleep(CMD_POLL_S)
            try:
                text = CMD_FILE.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                CMD_FILE.unlink()
            except OSError:
                pass
            try:
                want = json.loads(text).get("set") or {}
                if isinstance(want, dict):
                    apply_command(want)
            except Exception:
                logging.exception("Plugin command rejected: %r", text[:200])

    threading.Thread(target=command_watcher, name="plugin-cmd", daemon=True).start()

    def capture(message, routed):
        if not CAPTURE_FLAG.exists() or len(message) < 3 or message[0] & 0xF0 not in (0x80, 0x90):
            return
        out = next((p[2] for d, p in routed if p[0] & 0xF0 == 0x90 and len(p) >= 3), "")
        kind = "on" if message[0] & 0xF0 == 0x90 and message[2] > 0 else "off"
        with CAPTURE_FILE.open("a", encoding="ascii") as f:
            f.write(f"{time.time():.4f},{kind},{message[1]},{message[2]},{out}\n")

    def dispatch(message):
        with io_lock:
            routed = mapper.route(message)
            for dest, packet in routed:
                send(dest, packet)
            schedule_ramps()
        return routed

    def send_routed(message):
        dispatch(message)

    def bus_play(packets):
        with io_lock:
            for packet in packets:
                send(PLAY, packet)

    if BUS_OFF_FILE.exists():
        logging.info("Bus (UDP) off: file %s", BUS_OFF_FILE.name)
    else:
        try:
            bus_ref[0] = UdpBus(on_set=apply_command, on_play=bus_play)
            bus_ref[0].state_fn = live_snapshot
            bus_ref[0].start()
            logging.info("Bus (UDP) listening on %s:%s", *bus_ref[0].address)
        except OSError as exc:
            logging.warning("Bus (UDP) unavailable: %s", exc)

    def publish_bus(message, routed):
        bus = bus_ref[0]
        if bus is None or not bus.subs or len(message) < 2:
            return
        kind = message[0] & 0xF0
        if kind in (0x80, 0x90) and len(message) >= 3:
            on = kind == 0x90 and message[2] > 0
            out = next((p[2] for d, p in routed if p[0] & 0xF0 == 0x90 and len(p) >= 3), 0) if on else 0
            bus.note(on, message[1], message[2] if on else 0, out, message[0] & 0x0F)
        elif kind == 0xB0 and len(message) >= 3 and message[1] == 64:
            bus.pedal(mapper.mode, MODE_CC[mapper.mode], message[2])
        elif kind == 0xC0:
            bus.button(message[1])

    def callback(event, _user_data):
        nonlocal messages, errors, last_input
        message, _delta = event
        try:
            old_mode = mapper.mode
            routed = dispatch(message)
            capture(message, routed)
            publish_bus(message, routed)
            if len(message) >= 3 and message[0] & 0xF0 == 0x90 and message[2] > 0:
                out = next((p[2] for d, p in routed if p[0] & 0xF0 == 0x90 and len(p) >= 3), message[2])
                live_last.update(note=message[1], raw=message[2], out=out)
            live_event.set()
            if DEBUG_FILE.exists() and message and message[0] & 0xF0 in (0xB0, 0xC0, 0xD0):
                logging.info("RAW %s -> %s", bytes(message).hex(" "),
                             ", ".join(f"{d}:{p.hex(' ')}" for d, p in routed) or "dropped")
            if len(message) >= 2 and message[0] & 0xF0 == 0xC0:
                logging.info("Physical Program Change: %s", message[1])
                with io_lock:
                    publish_state(True)
            if mapper.mode != old_mode:
                logging.info("Physical button selected pedal mode: %s", mapper.mode)
            if len(message) >= 2 and message[0] & 0xF0 == 0xC0 and message[1] == UNA_CORDA_BUTTON:
                logging.info("Physical button toggled una corda: %s", bool(mapper.una_corda_values[message[0] & 0x0F]))
            messages += 1
            last_input = time.time()
        except Exception:
            errors += 1
            logging.exception("MIDI callback failed")

    try:
        logging.info("Virtual outputs ready: play=%s control=%s", PLAY_NAME, CONTROL_NAME)
        while not done.wait(1):
            try:
                mapper.release_ms = release_ms()
                try:
                    mapper.ones_context = ONES_MODE_FILE.read_text(encoding="ascii").strip() != "ppp"
                except Exception:
                    mapper.ones_context = True
                sig = []
                for path in [VELMAP_FILE] + [touch_preset_file(m) for m in TOUCH_BUTTONS.values()]:
                    try:
                        sig.append(path.stat().st_mtime)
                    except OSError:
                        sig.append(None)
                sig = tuple(sig)
                reload_maps = sig != velmap_mtime
                if reload_maps:
                    velmap_mtime = sig
                    maps = {}
                    for m in TOUCH_BUTTONS.values():
                        loaded = load_velocity_map(touch_preset_file(m))
                        if loaded:
                            maps[m] = loaded
                    with io_lock:
                        mapper.touch_maps = maps
                    logging.info("Touch presets loaded: %s", ", ".join(maps) or "none")
                if mapper.touch_dirty:
                    mapper.touch_dirty = False
                    try:
                        TOUCH_FILE.write_text(mapper.touch_mode, encoding="ascii")
                    except OSError:
                        pass
                    logging.info("Touch mode (button): %s", mapper.touch_mode)
                try:
                    wanted = TOUCH_FILE.read_text(encoding="ascii").strip() or DEFAULT_TOUCH
                except OSError:
                    wanted = DEFAULT_TOUCH
                if mapper.touch_maps:
                    if wanted not in mapper.touch_maps:
                        wanted = DEFAULT_TOUCH if DEFAULT_TOUCH in mapper.touch_maps else next(iter(mapper.touch_maps))
                    if reload_maps or wanted != mapper.touch_mode:
                        with io_lock:
                            mapper.velocity_map = mapper.touch_maps[wanted]
                            mapper.touch_mode = wanted
                        logging.info("Touch mode: %s", wanted)
                elif reload_maps:
                    mapper.velocity_map = load_velocity_map()
                    mapper.touch_mode = None
                    logging.info("Velocity map %s", "loaded" if mapper.velocity_map else "off")
                if RESTART_FILE.exists():
                    RESTART_FILE.unlink(missing_ok=True)
                    logging.info("Restart requested by file - exiting for supervisor")
                    done.set()
                    continue
                if TEST_FILE.exists():
                    try:
                        test_message = bytes.fromhex(TEST_FILE.read_text(encoding="ascii").strip())
                        if not 1 <= len(test_message) <= 3:
                            raise ValueError("Test MIDI must be one short event")
                        send_routed(test_message)
                        logging.info("Injected test MIDI: %s", test_message.hex(" "))
                    except Exception:
                        logging.exception("Test MIDI rejected")
                    finally:
                        TEST_FILE.unlink(missing_ok=True)
                if midi_in is None:
                    candidate = rtmidi.MidiIn(rtmidi.API_WINDOWS_MM)
                    names = candidate.get_ports()
                    match = find_input(names)
                    if match is None and time.time() - last_missing_log > 60:
                        last_missing_log = time.time()
                        logging.warning("Keyboard not found; MIDI inputs: %s", names)
                    if match is not None:
                        try:
                            candidate.ignore_types(sysex=False, timing=False, active_sense=False)
                            candidate.open_port(match, "Pedal Modes Input")
                            candidate.set_callback(callback)
                            midi_in = candidate
                            input_label = names[match]
                            logging.info("Physical input open: %s", input_label)
                        except Exception as exc:
                            logging.warning("Physical input unavailable: %s", exc)
                    if midi_in is None:
                        candidate.close_port()
                else:
                    names = midi_in.get_ports()
                    if input_label not in names:
                        logging.warning("Physical input disappeared")
                        midi_in.close_port()
                        midi_in = None
                        with io_lock:
                            for packet in mapper.release_all():
                                send(PLAY, packet)
                with io_lock:
                    publish_state(midi_in is not None)
                STATUS_FILE.write_text(json.dumps({
                    "pid": os.getpid(), "connected": midi_in is not None,
                    "input": input_label if midi_in is not None else None, "output": PLAY_NAME, "control_output": CONTROL_NAME,
                    "mode": mapper.mode, "una_corda": bool(mapper.una_corda_values[0]),
                    "release_ms": mapper.release_ms,
                    "velocity_map": mapper.velocity_map is not None,
                    "touch_mode": mapper.touch_mode,
                    "monitor_port": monitor is not None,
                    "ones_mode": "context" if mapper.ones_context else "ppp",
                    "messages": messages, "sent_play": counts[PLAY], "sent_control": counts[CONTROL],
                    "errors": errors, "last_input": last_input,
                    "bus": None if bus_ref[0] is None else {
                        "port": bus_ref[0].address[1], "listeners": bus_ref[0].listeners(),
                        "sent": bus_ref[0].sent},
                    "updated": time.time()}, indent=2), encoding="utf-8")
            except Exception:
                # one bad tick (USB unplugged mid-call, status file locked...) must not kill the router
                errors_loop[0] += 1
                logging.exception("Router loop error (continuing)")
                if midi_in is not None:
                    try:
                        midi_in.close_port()
                    except Exception:
                        pass
                    midi_in = None
                    with io_lock:
                        for packet in mapper.release_all():
                            send(PLAY, packet)
                time.sleep(1)
    finally:
        if bus_ref[0] is not None:
            bus_ref[0].close()          # releases notes trainers still hold
        if midi_in is not None:
            midi_in.close_port()
        with io_lock:
            for packet in mapper.release_all():
                ports[PLAY].send(packet)
        for p in ports.values():
            p.close()
        if monitor is not None:
            monitor.close()
        kernel.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logging.basicConfig(filename=ROOT / "router.log", level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        logging.exception("Router stopped by an error")
        raise
