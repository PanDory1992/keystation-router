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
"capture-notes" makes the router append every raw key event to notes/notes-RRRR-Wtt.csv.
Half pedal (13.11): the BFS-40 is an on/off switch; with "half_pedal" on, pedal down in
sustain mode sends CC64 = half_depth instead of 127. Knob B17 (CC95, was CC89) sets the
depth. Debounce (13.11): with "debounce" on, a note-off waits DEBOUNCE_S; a note-on of the
same key inside that window is contact bounce, so both are dropped. Both switches live in
"router-options.json" and can be changed from the plugin or the UDP bus ("set").
"""

from __future__ import annotations

import ctypes
import datetime
import re
import json
import logging
import os
import random
from pathlib import Path
import signal
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor"))
import rtmidi  # noqa: E402
from udp_bus import UdpBus  # noqa: E402  (06.11: live bus for plugins and trainers)
from fader_assign import ASSIGN_PROGRAM, FaderLink  # noqa: E402  (16.11: C2..C8 on any channel)
import mega_input  # noqa: E402  (19.11: klawisze z Arduino Mega, czas miedzy stykami -> velocity)

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
TOUCH_BUTTONS = {9: "light", 10: "acoustic", 11: "heavy"}   # file names / plugin values (old: one button each)
# 15.11 (Miki): one button for touch: program 9 (C53) steps light -> acoustic -> heavy -> moje -> light.
# Programs 10 and 11 (C54, C55) are free: swallowed, so they never reach the instruments.
TOUCH_CYCLE_BUTTON = 9
FREE_BUTTONS = (10, 11)
# 15.11: "moje" = a curve fitted to Miki's own playing (contrast-limited equalisation of his raw velocities,
# slope <= 2.5) plus contextual denoising and censored-1 handling (v2, below). Study: symulacja-krzywej-20261115.
TOUCH_MODES = ("light", "acoustic", "heavy", "moje", "moje3", "naturalna", "szeroka", "naturalna-los")
# 16.11 (Miki: "two curves, natural, wide, never think about it again"): C53 now steps only naturalna <-> szeroka.
# Both: loudness follows the log of key speed. The sensor counts the time between the two dome contacts, raw = K - t/tau
# (K = 131.7, fitted to the hand's noise at fixed intent: sigma(raw) = 12% of (K - raw) above raw 85), so
# log speed = -ln(K - raw); then an S-shape like a felt hammer (most sensitive around raw 100, gentler at both ends).
# In that scale the black hole 2..40 is only ~3 dB of key speed, so a black "1" (hole mean) sits ~2 dB below the softest
# measured black. Input stage exactly as moje3 (denoise per level and hand, censored 1s). Older modes stay selectable
# from the plugin / panel; if no cycle map exists, the button steps through all of them as before.
# Study: symulacja-krzywej-20261115/RAPORT-naturalna.md
TOUCH_CYCLE = ("naturalna", "szeroka", "naturalna-los")
DENOISE3_MODES = ("moje3", "naturalna", "szeroka", "naturalna-los")          # per-level threshold + a phrase level per hand
CENSORED_ONE_MODES = ("moje", "moje3", "naturalna", "szeroka", "naturalna-los")   # "1" = soft note in the hole, not the phrase rule
# 16.11 (Miki): "naturalna-los" = naturalna (same map file content) with a little variety in the 1s: a white 1 is drawn
# from 8..10 and a lone black 1 from 10..14, uniformly, so on average they stay at the naturalna values (9 and 12).
# A black 1 right after a loud chord keeps the chord rule (it is a read error, not a soft note). About +-0.5 dB.
RANDOM_ONES = {"naturalna-los": ((8, 10), (10, 14))}   # mode -> ((white lo, hi), (black lo, hi)), inclusive
# 15.11: "moje3" (Moje v3e) = Moje v2 + three changes, simulated in symulacja-krzywej-20261115/RAPORT-moje3.md:
#  - the denoise threshold is min(12, 2 * sigma(level)): in forte the hand repeats within +-2..4 raw, so a change of
#    6+ raw there is meant and passes (v2 shrank every change up to 12); in mezzo it stays 12 so accents keep their size;
#  - one phrase level per hand (two trackers per channel; a note joins the tracker whose last pitch is nearer, else
#    the one within an octave, else below / above middle C), so the melody is not pulled toward the accompaniment;
#  - its map has no flat ceiling above raw 110 (velocity-map.moje3.json).
V3_SIGMA_KNOTS = ((2, 15.0), (40, 18.0), (60, 20.0), (75, 12.0), (85, 5.0), (95, 4.4), (105, 3.2), (115, 2.5), (127, 2.0))
V3_SPLIT = 60
DENOISE_K = 0.35         # pull toward the phrase level (35%) ...
DENOISE_TAU = 12.0       # ... only for deviations within the sensor noise (~2 sigma); accents pass
DENOISE_ALPHA = 0.3      # phrase level: running average of raw velocities
DENOISE_GAP = 1.5        # s of silence = a new phrase
# 15.11 (moje v2): one curve for both colours (in one chord black reads -0.7 raw vs white: one sensor scale).
# Raw 1 = too slow to measure: white -> the map's white[1] (just below the floor), black -> black[1] (mean of the
# black hole, 1..40). A black 1 within ONE_CHORD_WINDOW after measured notes of median >= ONE_CHORD_LOUD is a read
# error with P = ONE_CHORD_P (4.4% of such notes vs 1.7% expected): expected output = P * chord + (1 - P) * hole.
# The phrase rule for ones (ONES_STEP / ONES_CAP) is not used in "moje". Study: symulacja-krzywej-20261115/RAPORT-moje2.md
ONE_CHORD_WINDOW = 0.03
ONE_CHORD_LOUD = 80
ONE_CHORD_P = 0.6
BLACK_MEASURED_MIN = 41  # the black sensor never sends 2..40
TOUCH_FILE = ROOT / "touch-mode"
MEGA_FILE = ROOT / "mega-krzywa.json"   # 19.11: krzywa dla klawiszy z Megi (C53 przelacza, gdy Mega gra)
DEFAULT_TOUCH = "naturalna"
MONITOR_NAME = "Keystation Monitor"   # copy of played notes (after mapping) for the dynamics mirror page
# Live state for the mirror page (05.11): on the monitor port only, MIDI channel 16 CCs,
# sent on every change and once a second: CC20 pedal mode (0 sustain, 1 sostenuto),
# CC21 una corda (0/127), CC22 touch (0 light, 1 acoustic, 2 heavy, 127 none),
# CC23 "1" mode (0 ppp, 1 context), CC24 keyboard connected (0/1).
# Pedal CC64/66/67 sent to the play port are mirrored to the monitor port too.
STATE_CHANNEL = 15
TOUCH_CODE = {"light": 0, "acoustic": 1, "heavy": 2, "moje": 3, "moje3": 4, "naturalna": 5, "szeroka": 6, "naturalna-los": 7}
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
OPTIONS_FILE = ROOT / "router-options.json"   # 13.11: {"half_pedal","half_depth","debounce"}
HALF_PEDAL_KNOB_CC = 95  # physical B17
DEFAULT_HALF_DEPTH = 80  # about 63 %, the middle of the half-pedal zone in Pianoteq
DEBOUNCE_S = 0.015       # 13.11 data: off->on of the same key under 15 ms = 30 of 92 513 notes


def load_options(path=None) -> dict:
    try:
        data = json.loads((path or OPTIONS_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
# Commands from the plugin (06.11): {"v":1,"id":..,"set":{"mode","una_corda","touch","ones"}}
CMD_FILE = ROOT / "live-cmd.json"
# 15.11: SysEx from the keyboard (memory dump RECALL + STORE, answers to probes) is saved to sysex/*.syx;
# a burst = one file (a new file after 3 s of silence). Probes the router may send (plugin command "sysex_probe"),
# taken from Evolution's Enigma 1.2 (Enigma.exe); only these two, nothing that writes to the keyboard:
SYSEX_DIR = ROOT / "sysex"
SYSEX_PROBES = {
    "identity": bytes.fromhex("F07E7F0601F7"),          # universal Identity Request: model + firmware version
    "dump": bytes.fromhex("F0002008107F0000F7"),        # Evolution request 0 (Enigma's preset request)
}


class SysexLog:
    """Collects SysEx messages into .syx files, one file per burst."""
    def __init__(self, folder: Path, gap: float = 3.0):
        self.folder, self.gap, self.path, self.last = folder, gap, None, -1e9

    def feed(self, message, now: float) -> Path:
        if self.path is None or now - self.last > self.gap:
            self.folder.mkdir(exist_ok=True)
            stamp = datetime.datetime.fromtimestamp(now).strftime("%Y%m%d-%H%M%S")
            self.path = self.folder / f"keystation-{stamp}.syx"
        with open(self.path, "ab") as f:
            f.write(bytes(message))
        self.last = now
        return self.path
CMD_POLL_S = 0.04
# UDP bus (06.11): notes, pedal, buttons and state, live, for any number of listeners on
# this PC (127.0.0.1:47800, protocol in udp_bus.py). File "szyna-off" turns it off.
BUS_OFF_FILE = ROOT / "szyna-off"
BLACK_KEYS = {1, 3, 6, 8, 10}


def _interp(x: float, knots) -> float:
    """Piecewise-linear lookup in ((x, y), ...), clamped at both ends (like numpy.interp)."""
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return knots[-1][1]


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


# 14.11: Keystation Status 0.4.0 offers 60 / 120 / 250 ms ("szybko / średnio / miękko"); any 0..1000 is accepted.
def set_release_ms(ms) -> int | None:
    """Save the sustain release ramp length (ms) to the "release-ms" file; None if the value is not a number."""
    if isinstance(ms, bool) or not isinstance(ms, (int, float)):
        return None
    value = max(0, min(1000, int(round(ms))))
    tmp = RELEASE_FILE.with_name(RELEASE_FILE.name + ".tmp")
    tmp.write_text(str(value), encoding="ascii")
    os.replace(tmp, RELEASE_FILE)
    return value


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
# B17 (CC95) is the half-pedal depth knob since 13.11, so it is not here.
# 20.11: B16 przeniesiona z CC88 na CC89 na stale (Miki), bo CC88 to prefiks wysokiej rozdzielczosci velocity
PAN_KNOB_CC = dict(zip((10, 2, 12, 13, 75, 76, 92), (14, 15, 20, 21, 86, 87, 89)))
HIRES_CC = 88            # 20.11: prefiks wysokiej rozdzielczosci velocity (MIDI CA-031), tylko dla nut z Megi
KNOB_CC = dict(zip((42, 34, 44, 45, 77, 78, 79, 94, 16, 17, 18, 19, 80, 81),
                   range(104, 118)))
CHANNEL_PRESSURE_KNOB_CC = 118  # physical B32
RPN_KNOB_CC = 119               # physical B33 (RPN 0, Data Entry)

# 15.11: the plugin's photo view shows where every knob and fader is. Physical CC -> label as printed on the
# keyboard (B10..B33 knobs, C1..C9 faders); B32 sends channel pressure, B33 sends RPN data entry (CC6).
CONTROL_LABELS = {
    **{cc: f"B{10 + i}" for i, cc in enumerate((10, 2, 12, 13, 75, 76, 92))},
    HALF_PEDAL_KNOB_CC: "B17",
    **{cc: f"B{18 + i}" for i, cc in enumerate((42, 34, 44, 45, 77, 78, 79, 94, 16, 17, 18, 19, 80, 81))},
    6: "B33",
    **{cc: f"C{1 + i}" for i, cc in enumerate(FADER_CC)},
    RAW_MAIN_FADER_CC: "C9",
}


def control_of(message) -> tuple[str, int] | None:
    """(label, value) for a knob or fader message from the keyboard, else None."""
    if len(message) >= 3 and message[0] & 0xF0 == 0xB0 and message[1] in CONTROL_LABELS:
        return CONTROL_LABELS[message[1]], int(message[2])
    if len(message) >= 2 and message[0] & 0xF0 == 0xD0:
        return "B32", int(message[1])
    return None


# 15.11: knob/fader positions survive a router restart (the knobs do not move while the PC is off).
CONTROLS_FILE = ROOT / "controls.json"
# "Read positions" from the plugin: for this long, knob/fader messages only update the positions and
# go nowhere else, so pressing SNAPSHOT (+ and - together) does not touch Pianoteq or the mixer.
READ_CONTROLS_S = 6.0


def load_controls(path=CONTROLS_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: int(v) for k, v in data.items()
                if isinstance(k, str) and isinstance(v, int) and 0 <= v <= 127 and k in set(CONTROL_LABELS.values()) | {"B32"}}
    except Exception:
        return {}


def button_label(program: int) -> str | None:
    """Program Change from the P10 buttons: 0..7 = B44..B51, 8..16 = C52..C60."""
    if 0 <= program <= 7:
        return f"B{44 + program}"
    if 8 <= program <= 16:
        return f"C{44 + program}"
    return None


PLAY, CONTROL = "play", "control"
# Controller numbers an instrument is meant to receive from a keyboard.
PLAY_CC = ({1, 11, 64, 66, 67, HIRES_CC} | set(PAN_KNOB_CC.values()) | set(range(104, 120))
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
        self.fader_link = None      # 16.11: fader_assign.FaderLink; C2..C8 + C54 go there when set
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
        self.rng = random.Random()        # "naturalna-los": the random 1s
        self.raw_level = [None] * 16      # "moje": running raw level per channel (denoising)
        self.raw_time = [0.0] * 16
        self.raw_recent = [[] for _ in range(16)]
        self.hand_level = [[None, None] for _ in range(16)]   # "moje3": per channel, per hand: level, time, last pitch
        self.hand_time = [[None, None] for _ in range(16)]
        self.hand_pitch = [[0, 0] for _ in range(16)]   # "moje": (time, raw) of measured notes in the last ONE_CHORD_WINDOW
        self.phrase_level = [None] * 16   # running output level per channel
        self.phrase_time = [0.0] * 16
        self.pedal_out = [0] * 16         # what was last sent for the pedal (half pedal: depth)
        self.half_pedal = False
        self.half_depth = DEFAULT_HALF_DEPTH
        self.half_knob = None             # last physical B17 value, None = not moved since start
        self.debounce = False
        self.pending_offs = {}            # (channel, note) -> (gen, packet) waiting DEBOUNCE_S
        self.deferred_offs = []           # (channel, note, gen) to schedule
        self.off_gen = 0
        self.bounces = 0                  # bounces removed since start
        self.last_event = None            # "deferred" / "bounce" for the last transform
        self.options_dirty = False
        self.mega_active = False          # 19.11: klawisze z Megi; wtedy nuty z Keystation sa pomijane
        self.mega_settings = mega_input.load_settings(Path("/nonexistent"))
        self.mega_dirty = False           # C53 zmienil krzywa Megi -> petla glowna zapisuje plik
        self.mega_lsb = None              # CC88 (0..127) dla najblizszej nuty z Megi, None = bez

    def options(self) -> dict:
        return {"half_pedal": self.half_pedal, "half_depth": self.half_depth, "debounce": self.debounce}

    def load(self, data: dict):
        if isinstance(data.get("half_pedal"), bool):
            self.half_pedal = data["half_pedal"]
        depth = data.get("half_depth")
        if isinstance(depth, (int, float)) and not isinstance(depth, bool):
            self.half_depth = max(1, min(127, int(depth)))
        if isinstance(data.get("debounce"), bool):
            self.debounce = data["debounce"]

    def _pedal_level(self, value: int, mode: str | None = None) -> int:
        if value and self.half_pedal and (mode or self.mode) == "sustain":
            return self.half_depth
        return value

    def set_half(self, on: bool | None = None, depth: int | None = None) -> list[bytes]:
        """Switch or move the half pedal; a pedal held right now changes at once."""
        if on is not None:
            self.half_pedal = bool(on)
        if depth is not None:
            self.half_depth = max(1, min(127, int(depth)))
        self.options_dirty = True
        packets = []
        if self.mode != "sustain":
            return packets
        for channel, value in enumerate(self.pedal_values):
            out = self._pedal_level(value)
            if value and out != self.pedal_out[channel]:
                self.pedal_out[channel] = out
                packets.append(bytes((0xB0 | channel, MODE_CC[self.mode], out)))
        return packets

    def set_debounce(self, on: bool) -> list[bytes]:
        """Turning it off sends the note-offs that were waiting."""
        self.debounce = bool(on)
        self.options_dirty = True
        packets = []
        if not on:
            for (channel, note), (_gen, packet) in sorted(self.pending_offs.items()):
                self.active_notes[channel].discard(note)
                packets.append(packet)
            self.pending_offs.clear()
        return packets

    def flush_off(self, channel: int, note: int, gen: int) -> bytes | None:
        """A waiting note-off whose time is up (None if a bounce or release_all took it)."""
        item = self.pending_offs.get((channel, note))
        if item is None or item[0] != gen:
            return None
        del self.pending_offs[(channel, note)]
        self.active_notes[channel].discard(note)
        return item[1]

    def take_offs(self):
        offs, self.deferred_offs = self.deferred_offs, []
        return offs

    def select_touch(self, mode: str) -> bool:
        if mode not in self.touch_maps:
            return False
        self.velocity_map = self.touch_maps[mode]
        self.touch_mode = mode
        self.touch_dirty = True
        return True

    def next_mega_curve(self) -> str:
        """C53, gdy graja klawisze z Megi: nastepna krzywa z mega-krzywa.json (w kolko)."""
        names = list(self.mega_settings["krzywe"])
        k = (names.index(self.mega_settings["krzywa"]) + 1) % len(names)
        self.mega_settings["krzywa"] = names[k]
        self.mega_dirty = True
        return names[k]

    def mega_message(self, kind: str, note: int, us: int, channel: int = 0) -> bytes:
        """Zdarzenie z Megi -> gotowy komunikat MIDI (velocity juz policzone, transform go nie zmienia).
        Przy wysokiej rozdzielczosci czesc ulamkowa czeka w self.mega_lsb na transform (CC88 tuz przed nuta)."""
        if kind == "on":
            v = mega_input.note_velocity_exact(note, us, self.mega_settings)
            if self.mega_settings.get("wysoka_rozdzielczosc"):
                msb, self.mega_lsb = mega_input.hires_split(v)
            else:
                msb, self.mega_lsb = int(round(v)), None
            return bytes((0x90 | channel, note, msb))
        return bytes((0x80 | channel, note, mega_input.release_velocity(us)))

    def next_touch(self) -> str | None:
        """The touch button: the next mode of TOUCH_CYCLE that has a map, wrapping round; from any other mode it goes to
        the first. Without any cycle map: all TOUCH_MODES that have a map, as before 16.11."""
        modes = [m for m in TOUCH_CYCLE if m in self.touch_maps] or [m for m in TOUCH_MODES if m in self.touch_maps]
        if not modes:
            return None
        k = modes.index(self.touch_mode) + 1 if self.touch_mode in modes else 0
        self.select_touch(modes[k % len(modes)])
        return self.touch_mode

    def denoise(self, channel: int, raw: int, now: float, lo: int = 2) -> int:
        """Empirical-Bayes shrinkage toward the phrase level: small deviations (sensor noise) are pulled in by
        DENOISE_K, bigger ones (accents, a voiced melody) keep all but a constant K*TAU. Causal: past notes only."""
        level = self.raw_level[channel]
        if level is None or now - self.raw_time[channel] > DENOISE_GAP:
            level = float(raw)
        d = raw - level
        d = d * (1 - DENOISE_K) if abs(d) <= DENOISE_TAU else d - (DENOISE_K * DENOISE_TAU if d > 0 else -DENOISE_K * DENOISE_TAU)
        self.raw_level[channel] = (1 - DENOISE_ALPHA) * level + DENOISE_ALPHA * raw
        self.raw_time[channel] = now
        return max(lo, min(127, int(round(level + d))))

    def moje_one(self, channel: int, black: bool, now: float) -> int:
        """Raw 1 in "moje": censored, not silent. See ONE_CHORD_* above. In a RANDOM_ONES mode a lone 1 is drawn
        from that mode's range instead of the map's fixed value (the chord rule stays as it is)."""
        white_t, black_t = self.velocity_map
        spread = RANDOM_ONES.get(self.touch_mode)
        if not black:
            return self.rng.randint(*spread[0]) if spread else white_t[1]
        mates = sorted(r for t0, r in self.raw_recent[channel] if now - t0 <= ONE_CHORD_WINDOW)
        if mates:
            k = len(mates) // 2
            m = mates[k] if len(mates) % 2 else (mates[k - 1] + mates[k]) / 2
            if m >= ONE_CHORD_LOUD:
                return int(round(ONE_CHORD_P * white_t[int(round(m))] + (1 - ONE_CHORD_P) * black_t[1]))
        return self.rng.randint(*spread[1]) if spread else black_t[1]

    def denoise3(self, channel: int, note: int, raw: int, now: float, lo: int = 2) -> int:
        """Moje v3e: denoise with a per-level threshold and a level per hand (see V3_SIGMA_KNOTS)."""
        times, pitches = self.hand_time[channel], self.hand_pitch[channel]
        active = [h for h in (0, 1) if times[h] is not None and now - times[h] <= DENOISE_GAP]
        if len(active) == 2:
            hand = min(active, key=lambda h: abs(note - pitches[h]))
        elif len(active) == 1 and abs(note - pitches[active[0]]) <= 12:
            hand = active[0]
        else:
            hand = 0 if note < V3_SPLIT else 1
        fresh = times[hand] is None or now - times[hand] > DENOISE_GAP
        level = float(raw) if fresh else self.hand_level[channel][hand]
        sigma = _interp(level, V3_SIGMA_KNOTS)
        tau = min(DENOISE_TAU, 2 * sigma)
        d = raw - level
        d = d * (1 - DENOISE_K) if abs(d) <= tau else d - (DENOISE_K * tau if d > 0 else -DENOISE_K * tau)
        self.hand_level[channel][hand] = float(raw) if fresh else (1 - DENOISE_ALPHA) * level + DENOISE_ALPHA * raw
        times[hand] = now
        pitches[hand] = note
        return max(lo, min(127, int(round(level + d))))

    def remember_raw(self, channel: int, raw: int, now: float):
        recent = [(t0, r) for t0, r in self.raw_recent[channel] if now - t0 <= ONE_CHORD_WINDOW]
        recent.append((now, raw))
        self.raw_recent[channel] = recent

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
                out = self._pedal_level(value, new_mode)
                self.pedal_out[channel] = out
                packets.append(bytes((0xB0 | channel, old_cc, 0)))
                packets.append(bytes((0xB0 | channel, new_cc, out)))
        self.mode = new_mode
        return packets

    def transform(self, message: list[int] | bytes, now: float | None = None, exact: bool = False) -> list[bytes]:
        """exact=True: nuta z Megi z gotowym velocity (bez map czucia i odszumiania); note-off moze niesc velocity."""
        if now is None:
            now = time.monotonic()
        if not message:
            return []
        data = bytes(message)
        status = data[0]
        channel = status & 0x0F
        self.last_event = None
        if status & 0xF0 == 0xD0 and len(data) >= 2:
            return [bytes((0xB0 | channel, CHANNEL_PRESSURE_KNOB_CC, data[1]))]
        if len(data) >= 3 and status & 0xF0 in (0x80, 0x90) and data[1] == LISTEN_KEY:
            # top C8 is a button: press = toggle Listen Bus (headphones/speakers) in Studio One
            if status & 0xF0 == 0x90 and data[2] > 0:
                return [bytes((0xC0 | channel, LISTEN_PROGRAM))]
            return []
        if len(data) >= 3 and status & 0xF0 in (0x80, 0x90):
            notes = self.active_notes[channel]
            is_on = status & 0xF0 == 0x90 and data[2] > 0
            key = (channel, data[1])
            if is_on and key in self.pending_offs:
                # the key let go and struck again within DEBOUNCE_S: a bounce, the note just goes on
                del self.pending_offs[key]
                self.bounces += 1
                self.last_event = "bounce"
                return []
            if not is_on and self.debounce and data[1] in notes:
                self.off_gen += 1
                self.pending_offs[key] = (self.off_gen, data[:3])
                self.deferred_offs.append((channel, data[1], self.off_gen))
                self.last_event = "deferred"
                return []
            if is_on:
                notes.add(data[1])
                if exact:
                    self.note_played(channel, data[2], now)
                    lsb, self.mega_lsb = self.mega_lsb, None
                    if lsb is not None:          # CC88 musi przyjsc tuz przed nuta, na tym samym kanale
                        return [bytes((0xB0 | channel, HIRES_CC, lsb)), data[:3]]
                    return [data[:3]]
                if self.velocity_map is not None:
                    black = data[1] % 12 in BLACK_KEYS
                    table = self.velocity_map[1 if black else 0]
                    moje = self.touch_mode in CENSORED_ONE_MODES
                    if data[2] == 1 and moje:
                        out = self.moje_one(channel, black, now)
                    elif data[2] == 1 and self.ones_context:
                        out = self.ones_velocity(channel, now, table[1])
                    else:
                        raw = data[2]
                        if moje and raw > 1:
                            lo = BLACK_MEASURED_MIN if black and raw >= BLACK_MEASURED_MIN else 2
                            if self.touch_mode in DENOISE3_MODES:
                                raw = self.denoise3(channel, data[1], raw, now, lo)
                            else:
                                raw = self.denoise(channel, raw, now, lo)
                            self.remember_raw(channel, data[2], now)
                        out = table[raw]
                        self.note_played(channel, out, now)
                    return [bytes((status, data[1], out))]
            else:
                notes.discard(data[1])
        if len(data) >= 2 and status & 0xF0 == 0xC0:
            if data[1] == UNA_CORDA_BUTTON:
                value = 0 if self.una_corda_values[channel] else 127
                self.una_corda_values[channel] = value
                return [bytes((0xB0 | channel, 67, value))]
            if data[1] == TOUCH_CYCLE_BUTTON:
                if self.mega_active:
                    self.next_mega_curve()
                else:
                    self.next_touch()
                return []
            if data[1] in FREE_BUTTONS:
                if data[1] == ASSIGN_PROGRAM and self.fader_link is not None:
                    self.fader_link.arm()
                return []
            selected = PROGRAM_BUTTONS.get(data[1])
            if selected:
                return self._select(selected)
        if len(data) >= 3 and status & 0xF0 == 0xB0:
            cc, value = data[1], data[2]
            if cc == HALF_PEDAL_KNOB_CC:
                self.half_knob = value
                return self.set_half(depth=max(1, value))
            if cc in KNOB_CC:
                return [bytes((status, KNOB_CC[cc], value))]
            if cc in PAN_KNOB_CC:
                return [bytes((status, PAN_KNOB_CC[cc], value))]
            if self.fader_link is not None and cc in FADER_CC[1:]:
                self.fader_link.move(f"C{FADER_CC.index(cc) + 1}", value)
                return []
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
                previous = self.pedal_out[channel]
                self.pedal_values[channel] = value
                out = self._pedal_level(value)
                self.pedal_out[channel] = out
                out_cc = MODE_CC[self.mode]
                if (out == 0 and previous > 0 and self.mode == "sustain"
                        and self.release_ms > 0):
                    self._cancel_ramp(channel)
                    self.ramp_cc[channel] = out_cc
                    self.pending_ramps.append((channel, out_cc, ramp_values(previous),
                                               self.ramp_gen[channel]))
                    return []
                self._cancel_ramp(channel)
                return [bytes((status, out_cc, out))]
        return [data]

    def route(self, message: list[int] | bytes, now: float | None = None,
              exact: bool = False) -> list[tuple[str, bytes]]:
        return [(destination(p), p) for p in self.transform(message, now, exact)]

    def release_all(self) -> list[bytes]:
        packets = []
        for channel, value in enumerate(self.pedal_values):
            ramp = self._cancel_ramp(channel)
            self.pedal_out[channel] = 0
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
        self.pending_offs.clear()
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
    try:          # 13.11: HIGH_PRIORITY_CLASS, so Windows serves the MIDI path before ordinary programs
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        if kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x00000080):
            logging.info("Process priority: high")
    except Exception:
        logging.exception("Could not raise process priority")
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
    try:          # 13.11: 1 ms timers, so the debounce wait and the pedal ramps keep their length
        ctypes.WinDLL("winmm").timeBeginPeriod(1)
    except Exception:
        logging.exception("timeBeginPeriod failed")
    mapper = PedalMapper()
    mapper.load(load_options())
    fader_link = FaderLink()
    mapper.fader_link = fader_link
    logging.info("Faders C2..C8: %s", fader_link.map)
    logging.info("Options: %s", mapper.options())
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
    sysex_log = SysexLog(SYSEX_DIR)

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

    def off_step(channel, note, gen):
        with io_lock:
            packet = mapper.flush_off(channel, note, gen)
            if packet is not None:
                send(PLAY, packet)
        bus = bus_ref[0]
        if packet is not None and bus is not None and bus.subs:
            bus.note(False, note, 0, 0, channel)

    def schedule_offs():
        for channel, note, gen in mapper.take_offs():
            t = threading.Timer(DEBOUNCE_S, off_step, (channel, note, gen))
            t.daemon = True
            t.start()

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
    live_controls = load_controls()   # 15.11: "B10".."B33", "C1".."C9" -> last value (photo view of the plugin)
    controls_saved = [dict(live_controls), 0.0]
    read_controls = [0.0]             # until when knob/fader messages are only read (SNAPSHOT from the plugin)
    live_button = {}        # 15.11: last P10 button pressed: {"label": "C53", "t": unix time}
    bus_ref = [None]

    def live_snapshot():
        return {
            "v": 1,
            "connected": midi_in is not None,
            "mode": mapper.mode,
            "pedal": max(mapper.pedal_out),
            "half_pedal": mapper.half_pedal,
            "half_depth": mapper.half_depth,
            "half_knob": mapper.half_knob,
            "debounce": mapper.debounce,
            "bounces": mapper.bounces,
            "release_ms": mapper.release_ms,
            "una_corda": bool(mapper.una_corda_values[0]),
            "touch": mapper.touch_mode,
            "ones": "context" if mapper.ones_context else "ppp",
            "last": dict(live_last) or None,
            "mega": {          # 20.11: klawisze z Megi i krzywa fortepianu (wtyczka Keystation Status)
                "connected": mapper.mega_active,
                "curve": mapper.mega_settings["krzywa"],
                "curves": mapper.mega_settings["krzywe"],
                "black": mapper.mega_settings.get("czarne_mnoznik", 1.0),
                "minimum": mapper.mega_settings.get("minimum", 1),
                "hires": bool(mapper.mega_settings.get("wysoka_rozdzielczosc")),
            },
            "controls": dict(live_controls),
            "button": dict(live_button) or None,
            "reading": round(max(0.0, read_controls[0] - time.time()), 1),
            "faders": fader_link.state(),
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
            if live_controls != controls_saved[0] and time.time() - controls_saved[1] >= 1.0:
                try:
                    tmp_c = CONTROLS_FILE.with_name("controls.json.tmp")
                    tmp_c.write_text(json.dumps(live_controls), encoding="utf-8")
                    os.replace(tmp_c, CONTROLS_FILE)
                    controls_saved[0], controls_saved[1] = dict(live_controls), time.time()
                except OSError:
                    pass
            bus = bus_ref[0]
            if bus is not None:
                # state on the bus: when a setting changes, else once a second (notes have
                # their own events, so "last"/"updated" alone don't count as a change)
                key = tuple(v for k, v in snap.items() if k not in ("last", "updated", "controls", "button", "reading"))
                if key != bus_sent[0] or time.time() - bus_sent[1] >= 1.0:
                    bus.state(snap)
                    bus_sent = (key, time.time())
            time.sleep(LIVE_MIN_GAP_S)

    threading.Thread(target=live_writer, name="live-json", daemon=True).start()
    threading.Thread(target=fader_link.run, args=(done,), name="faders", daemon=True).start()

    def send_probe(name):
        """Send one whitelisted SysEx probe to the keyboard's own MIDI input (its USB output port)."""
        out = rtmidi.MidiOut(rtmidi.API_WINDOWS_MM)
        try:
            names = out.get_ports()
            match = find_input(names)
            if match is None:
                logging.warning("SysEx probe %s: keyboard output not found; outputs: %s", name, names)
                return
            out.open_port(match)
            out.send_message(list(SYSEX_PROBES[name]))
            logging.info("SysEx probe %s sent to %s: %s", name, names[match], SYSEX_PROBES[name].hex(" "))
        except Exception as exc:
            logging.warning("SysEx probe %s failed (is another program holding the keyboard's output?): %s", name, exc)
        finally:
            try:
                out.close_port()
            except Exception:
                pass

    def apply_command(want):
        """Same effect as pressing the physical buttons."""
        fader = want.get("fader")
        if isinstance(fader, dict):
            for name, channel in fader.items():
                if channel is None or isinstance(channel, str):
                    fader_link.assign(str(name), channel or None)
            logging.info("Faders C2..C8: %s", fader_link.map)
        if want.get("sysex_probe") in SYSEX_PROBES:
            send_probe(want["sysex_probe"])
        presses = []
        mode = want.get("mode")
        if mode in PROGRAM_BUTTONS.values() and mode != mapper.mode:
            presses.append(next(k for k, v in PROGRAM_BUTTONS.items() if v == mode))
        una = want.get("una_corda")
        if isinstance(una, bool) and una != bool(mapper.una_corda_values[0]):
            presses.append(UNA_CORDA_BUTTON)
        touch = want.get("touch")
        if touch in TOUCH_MODES and touch != mapper.touch_mode:
            with io_lock:
                mapper.select_touch(touch)          # the plugin picks a mode directly; saved by the main loop
        for program in presses:
            dispatch(bytes((0xC0, program)))
        half, depth, deb = want.get("half_pedal"), want.get("half_depth"), want.get("debounce")
        if not isinstance(depth, (int, float)) or isinstance(depth, bool):
            depth = None
        with io_lock:
            packets = []
            if isinstance(half, bool) or depth is not None:
                packets += mapper.set_half(half if isinstance(half, bool) else None, depth)
            if isinstance(deb, bool):
                packets += mapper.set_debounce(deb)
            for packet in packets:
                send(PLAY, packet)
        save_options()
        if want.get("read_controls") is True:
            read_controls[0] = time.time() + READ_CONTROLS_S
            logging.info("Reading knob/fader positions for %.0f s (SNAPSHOT goes nowhere else)", READ_CONTROLS_S)
            live_event.set()
        if "release_ms" in want:
            try:
                value = set_release_ms(want.get("release_ms"))
            except OSError:
                value = None
            if value is not None:
                mapper.release_ms = value
        curve = want.get("mega_curve")
        if isinstance(curve, str) and curve in mapper.mega_settings["krzywe"]:
            with io_lock:
                mapper.mega_settings["krzywa"] = curve
                mapper.mega_dirty = True
        hires = want.get("mega_hires")
        if isinstance(hires, bool):
            with io_lock:
                mapper.mega_settings["wysoka_rozdzielczosc"] = hires
                mapper.mega_dirty = True
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

    def save_options():
        if not mapper.options_dirty:
            return
        mapper.options_dirty = False
        try:
            tmp = OPTIONS_FILE.with_name(OPTIONS_FILE.name + ".tmp")
            tmp.write_text(json.dumps(mapper.options()), encoding="utf-8")
            os.replace(tmp, OPTIONS_FILE)
        except OSError:
            mapper.options_dirty = True

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

    # 13.11: notes.csv is written by its own thread, never inside the MIDI callback (opening a 5 MB file per note
    # could block for a second, e.g. while the antivirus scans it, and every following note waited). Column 6 =
    # the driver's delta time (s) to the previous MIDI message, to tell late delivery from slow playing.
    capture_q = []
    capture_lock = threading.Lock()
    capture_on = [CAPTURE_FLAG.exists()]

    def capture(message, routed, delta=0.0):
        if not capture_on[0] or len(message) < 3 or message[0] & 0xF0 not in (0x80, 0x90):
            return
        out = next((p[2] for d, p in routed if p[0] & 0xF0 == 0x90 and len(p) >= 3), "")
        kind = "on" if message[0] & 0xF0 == 0x90 and message[2] > 0 else "off"
        with capture_lock:
            capture_q.append(f"{time.time():.4f},{kind},{message[1]},{message[2]},{out},{delta:.4f}\n")

    mega_q = []

    def capture_mega(kind, note, us, routed):
        # 19.11: osobny plik notes-mega-RRRR-Wtt.csv: czas, on/off, nuta, us (czas miedzy stykami), velocity wyjscia
        if not capture_on[0]:
            return
        out = next((p[2] for d, p in routed if p[0] & 0xF0 in (0x80, 0x90) and len(p) >= 3), "")
        with capture_lock:
            mega_q.append(f"{time.time():.4f},{kind},{note},{us},{out},{mapper.mega_settings['krzywa']}\n")

    def capture_writer():
        while not done.is_set():
            time.sleep(0.5)
            capture_on[0] = CAPTURE_FLAG.exists()
            with capture_lock:
                lines = capture_q[:]
                capture_q.clear()
                mega_lines = mega_q[:]
                mega_q.clear()
            if mega_lines:
                try:
                    with capture_file().with_name(capture_file().name.replace("notes-", "notes-mega-")).open(
                            "a", encoding="ascii") as f:
                        f.writelines(mega_lines)
                except OSError:
                    pass
            if lines:
                t0 = time.perf_counter()
                try:
                    with capture_file().open("a", encoding="ascii") as f:
                        f.writelines(lines)
                except OSError:
                    pass
                took = time.perf_counter() - t0
                if took > 0.2:
                    logging.warning("SLOW notes.csv write: %.0f ms", took * 1000)

    def capture_file():
        # 13.11: one file per ISO week (notes/notes-2026-W46.csv): small files, easy week-to-week comparisons
        y, w, _ = datetime.date.today().isocalendar()
        folder = ROOT / "notes"
        folder.mkdir(exist_ok=True)
        return folder / f"notes-{y}-W{w:02d}.csv"

    threading.Thread(target=capture_writer, name="capture", daemon=True).start()
    late = {"wall": 0.0, "logged": 0.0}
    scan_tick = [0]

    def dispatch(message, exact=False):
        with io_lock:
            routed = mapper.route(message, exact=exact)
            for dest, packet in routed:
                send(dest, packet)
            schedule_ramps()
            schedule_offs()
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
            now = time.time()
            if message and message[0] == 0xF0:
                path = sysex_log.feed(message, now)
                logging.info("SysEx from keyboard: %d bytes -> %s (%s ...)", len(message), path.name, bytes(message[:12]).hex(" "))
            t0 = time.perf_counter()
            early = control_of(message)
            if early is not None and now < read_controls[0] and early[0] != "B17":
                live_controls[early[0]] = early[1]      # read only: not to Pianoteq, not to the mixer
                live_event.set()
                messages += 1
                last_input = now
                return
            if mapper.mega_active and len(message) >= 3 and message[0] & 0xF0 in (0x80, 0x90):
                messages += 1          # 19.11: klawisze graja z Megi; nuty z zielonej plytki (bez tasm) pomijamy
                return
            old_mode = mapper.mode
            routed = dispatch(message)
            took = time.perf_counter() - t0
            if took > 0.05:
                logging.warning("SLOW dispatch: %.0f ms (io_lock or a virtual port blocked)", took * 1000)
            # the driver says this event came _delta s after the previous one, but it reached us almost together
            # with it: MIDI was held up before the router (USB / Windows MIDI)
            if _delta > 0.15 and now - late["wall"] < 0.01 and now - late["logged"] > 5:
                late["logged"] = now
                logging.warning("LATE MIDI from driver: %.0f ms apart on the keyboard, arrived %.1f ms apart", _delta * 1000, (now - late["wall"]) * 1000)
            late["wall"] = now
            capture(message, routed, _delta)
            control = control_of(message)
            if control is not None:
                live_controls[control[0]] = control[1]
            if len(message) >= 2 and message[0] & 0xF0 == 0xC0 and button_label(message[1]):
                live_button.update(label=button_label(message[1]), t=now)
            if mapper.last_event is None:          # a waiting note-off is published when it is sent
                publish_bus(message, routed)
            if mapper.last_event is None and len(message) >= 3 and message[0] & 0xF0 == 0x90 and message[2] > 0:
                out = next((p[2] for d, p in routed if p[0] & 0xF0 == 0x90 and len(p) >= 3), message[2])
                live_last.update(note=message[1], raw=message[2], out=out)
                live_last.pop("us", None)
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

    def mega_event(kind, note, us):
        nonlocal messages, last_input
        try:
            message = mapper.mega_message(kind, note, us)
            routed = dispatch(message, exact=True)
            now = time.time()
            capture_mega(kind, note, us, routed)
            bus = bus_ref[0]
            if mapper.last_event is None and bus is not None and bus.subs:
                vel = message[2] if kind == "on" else 0
                bus.note(kind == "on", note, vel, vel, 0, us=us)
            if kind == "on" and mapper.last_event is None:
                live_last.update(note=note, raw=message[2], out=message[2], us=us)
            live_event.set()
            messages += 1
            last_input = now
        except Exception:
            logging.exception("Mega event failed")

    def mega_state(on):
        with io_lock:
            mapper.mega_active = on
            if not on:          # Mega odlaczona: wylacz grajace nuty, pedal zostaje
                for ch, notes in enumerate(mapper.active_notes):
                    for note in sorted(notes):
                        send(PLAY, bytes((0x80 | ch, note, 0)))
                    notes.clear()
        logging.info("Mega %s", "connected: keys play from the Mega" if on else "disconnected: keys from Keystation again")

    mapper.mega_settings = mega_input.load_settings(MEGA_FILE)
    mega_mtime = [None]
    mega_reader = mega_input.MegaReader(mega_event, mega_state, done, ROOT / "mega-off")
    threading.Thread(target=mega_reader.run, name="mega", daemon=True).start()

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
                for path in [VELMAP_FILE] + [touch_preset_file(m) for m in TOUCH_MODES]:
                    try:
                        sig.append(path.stat().st_mtime)
                    except OSError:
                        sig.append(None)
                sig = tuple(sig)
                reload_maps = sig != velmap_mtime
                if reload_maps:
                    velmap_mtime = sig
                    maps = {}
                    for m in TOUCH_MODES:
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
                save_options()          # B17 turned: the depth survives a restart
                if mapper.mega_dirty:
                    mapper.mega_dirty = False
                    try:
                        MEGA_FILE.write_text(json.dumps(mapper.mega_settings, indent=1, ensure_ascii=False), encoding="utf-8")
                    except OSError:
                        pass
                    logging.info("Mega curve (button): %s", mapper.mega_settings["krzywa"])
                try:
                    m = MEGA_FILE.stat().st_mtime
                except OSError:
                    m = None
                if m != mega_mtime[0]:
                    mega_mtime[0] = m
                    loaded = mega_input.load_settings(MEGA_FILE)
                    with io_lock:
                        mapper.mega_settings = loaded
                    logging.info("Mega curve: %s %s", loaded["krzywa"], loaded["krzywe"][loaded["krzywa"]])
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
                    # 13.11: look for the keyboard every 3 s, not every second (scanning MIDI devices is the heaviest call)
                    scan_tick[0] += 1
                    if scan_tick[0] % 3 == 0:
                        t0 = time.perf_counter()
                        names = midi_in.get_ports()
                        took = time.perf_counter() - t0
                        if took > 0.1:
                            logging.warning("SLOW get_ports (MIDI device scan): %.0f ms", took * 1000)
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
                    **mapper.options(), "bounces": mapper.bounces,
                    "velocity_map": mapper.velocity_map is not None,
                    "touch_mode": mapper.touch_mode,
                    "mega": {"connected": mega_reader.connected, "port": mega_reader.port,
                             "events": mega_reader.events, "curve": mapper.mega_settings["krzywa"]},
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
