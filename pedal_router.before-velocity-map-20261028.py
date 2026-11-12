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
"""

from __future__ import annotations

import ctypes
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

INPUT_NAME = "Keystation Pro 88"
PLAY_NAME = "Keystation Pedal Modes"   # name kept: Studio One already points here
CONTROL_NAME = "Keystation Control"
STATUS_FILE = ROOT / "status.json"
TEST_FILE = ROOT / "test-midi.hex"
DEBUG_FILE = ROOT / "debug-raw"   # create this file to log every raw CC/PC
RELEASE_FILE = ROOT / "release-ms"
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

    def transform(self, message: list[int] | bytes) -> list[bytes]:
        if not message:
            return []
        data = bytes(message)
        status = data[0]
        channel = status & 0x0F
        if status & 0xF0 == 0xD0 and len(data) >= 2:
            return [bytes((0xB0 | channel, CHANNEL_PRESSURE_KNOB_CC, data[1]))]
        if len(data) >= 3 and status & 0xF0 in (0x80, 0x90):
            notes = self.active_notes[channel]
            if status & 0xF0 == 0x90 and data[2] > 0:
                notes.add(data[1])
            else:
                notes.discard(data[1])
        if len(data) >= 2 and status & 0xF0 == 0xC0:
            if data[1] == UNA_CORDA_BUTTON:
                value = 0 if self.una_corda_values[channel] else 127
                self.una_corda_values[channel] = value
                return [bytes((0xB0 | channel, 67, value))]
            selected = PROGRAM_BUTTONS.get(data[1])
            if selected:
                return self._select(selected)
        if len(data) >= 3 and status & 0xF0 == 0xB0:
            cc, value = data[1], data[2]
            if cc in KNOB_CC:
                return [bytes((status, KNOB_CC[cc], value))]
            if cc in PAN_KNOB_CC:
                return [bytes((status, PAN_KNOB_CC[cc], value))]
            if cc == RAW_MAIN_FADER_CC:
                return [bytes((status, MAIN_FADER_CC, value))]
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

    def route(self, message: list[int] | bytes) -> list[tuple[str, bytes]]:
        return [(destination(p), p) for p in self.transform(message)]

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
    ports = {PLAY: VirtualPort(PLAY_NAME), CONTROL: VirtualPort(CONTROL_NAME)}
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

    def dispatch(message):
        with io_lock:
            routed = mapper.route(message)
            for dest, packet in routed:
                send(dest, packet)
            schedule_ramps()
        return routed

    def send_routed(message):
        dispatch(message)

    def callback(event, _user_data):
        nonlocal messages, errors, last_input
        message, _delta = event
        try:
            old_mode = mapper.mode
            routed = dispatch(message)
            if DEBUG_FILE.exists() and message and message[0] & 0xF0 in (0xB0, 0xC0, 0xD0):
                logging.info("RAW %s -> %s", bytes(message).hex(" "),
                             ", ".join(f"{d}:{p.hex(' ')}" for d, p in routed) or "dropped")
            if len(message) >= 2 and message[0] & 0xF0 == 0xC0:
                logging.info("Physical Program Change: %s", message[1])
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
            mapper.release_ms = release_ms()
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
                match = next((i for i, name in enumerate(names)
                              if name == INPUT_NAME or name.startswith(INPUT_NAME + " ")), None)
                if match is not None:
                    try:
                        candidate.ignore_types(sysex=False, timing=False, active_sense=False)
                        candidate.open_port(match, "Pedal Modes Input")
                        candidate.set_callback(callback)
                        midi_in = candidate
                        logging.info("Physical input open: %s", INPUT_NAME)
                    except Exception as exc:
                        logging.warning("Physical input unavailable: %s", exc)
                if midi_in is None:
                    candidate.close_port()
            else:
                names = midi_in.get_ports()
                if not any(name == INPUT_NAME or name.startswith(INPUT_NAME + " ") for name in names):
                    logging.warning("Physical input disappeared")
                    midi_in.close_port()
                    midi_in = None
                    with io_lock:
                        for packet in mapper.release_all():
                            send(PLAY, packet)
            STATUS_FILE.write_text(json.dumps({
                "pid": os.getpid(), "connected": midi_in is not None,
                "input": INPUT_NAME, "output": PLAY_NAME, "control_output": CONTROL_NAME,
                "mode": mapper.mode, "una_corda": bool(mapper.una_corda_values[0]),
                "release_ms": mapper.release_ms,
                "messages": messages, "sent_play": counts[PLAY], "sent_control": counts[CONTROL],
                "errors": errors, "last_input": last_input,
                "updated": time.time()}, indent=2), encoding="utf-8")
    finally:
        if midi_in is not None:
            midi_in.close_port()
        with io_lock:
            for packet in mapper.release_all():
                ports[PLAY].send(packet)
        for p in ports.values():
            p.close()
        kernel.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == "__main__":
    run()
