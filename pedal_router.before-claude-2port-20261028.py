"""Low-latency Keystation P10 MIDI relay for pedals and 16 plug-in knobs.

Notes and velocity pass through unchanged. The relay changes the selected physical
pedal CC, makes una corda an independent toggle, and normalizes B18..B33 to
CC104..119. This mapping assumes the factory P10 controller preset.
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
OUTPUT_NAME = "Keystation Pedal Modes"
STATUS_FILE = ROOT / "status.json"
TEST_FILE = ROOT / "test-midi.hex"
MODE_CC = {"sustain": 64, "sostenuto": 66, "celeste": 85}
# The P10 Program Change numbers are based on the existing Keystation map.
PROGRAM_BUTTONS = {2: "sustain", 3: "sostenuto", 16: "celeste"}
UNA_CORDA_BUTTON = 4
# Measured on the physical P10 keyboard, in order B18..B31. The surface and
# plug-in maps already reserve CC104..119 for B18..B33.
KNOB_CC = dict(zip((42, 34, 44, 45, 77, 78, 79, 94, 16, 17, 18, 19, 80, 81),
                   range(104, 118)))
CHANNEL_PRESSURE_KNOB_CC = 118  # physical B32
RPN_KNOB_CC = 119               # physical B33 (RPN 0, Data Entry)


class PedalMapper:
    def __init__(self):
        self.mode = "sustain"
        self.pedal_values = [0] * 16
        self.una_corda_values = [0] * 16
        self.active_notes = [set() for _ in range(16)]

    def _select(self, requested: str) -> list[bytes]:
        new_mode = "sustain" if requested == self.mode and requested != "sustain" else requested
        if new_mode == self.mode:
            return []
        old_cc, new_cc = MODE_CC[self.mode], MODE_CC[new_mode]
        packets = []
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
            notes = self.active_notes[status & 0x0F]
            if status & 0xF0 == 0x90 and data[2] > 0:
                notes.add(data[1])
            else:
                notes.discard(data[1])
        if len(data) >= 2 and status & 0xF0 == 0xC0:
            if data[1] == UNA_CORDA_BUTTON:
                channel = status & 0x0F
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
            # P10 B33 sends RPN 0 selector (CC100=0, CC101=0), then CC6 values.
            # Never forward this sequence: it changes a synth's pitch-bend range.
            if cc == 100 and value == 0:
                return []
            if cc == 101 and value == 0:
                return []
            if cc == 6:
                return [bytes((status, RPN_KNOB_CC, value))]
            if cc == 64:
                self.pedal_values[status & 0x0F] = value
                return [bytes((status, MODE_CC[self.mode], value))]
        return [data]

    def release_all(self) -> list[bytes]:
        packets = []
        for channel, value in enumerate(self.pedal_values):
            if value:
                packets.append(bytes((0xB0 | channel, MODE_CC[self.mode], 0)))
                self.pedal_values[channel] = 0
            if self.una_corda_values[channel]:
                packets.append(bytes((0xB0 | channel, 67, 0)))
                self.una_corda_values[channel] = 0
            for note in sorted(self.active_notes[channel]):
                packets.append(bytes((0x80 | channel, note, 0)))
            self.active_notes[channel].clear()
        self.mode = "sustain"
        return packets


class VirtualPort:
    def __init__(self):
        self.dll = ctypes.WinDLL(r"C:\Windows\System32\teVirtualMIDI64.dll", use_last_error=True)
        self.dll.virtualMIDICreatePortEx2.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p,
                                                      ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
        self.dll.virtualMIDICreatePortEx2.restype = ctypes.c_void_p
        self.dll.virtualMIDISendData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint32]
        self.dll.virtualMIDISendData.restype = ctypes.c_bool
        self.dll.virtualMIDIClosePort.argtypes = [ctypes.c_void_p]
        self.handle = self.dll.virtualMIDICreatePortEx2(OUTPUT_NAME, None, 0, 65535, 1)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), f"Could not create {OUTPUT_NAME}")

    def send(self, data: bytes):
        if len(data) > 65535:
            raise ValueError("MIDI packet exceeds port capacity")
        packet = (ctypes.c_ubyte * len(data))(*data)
        if not self.dll.virtualMIDISendData(self.handle, packet, len(data)):
            raise OSError(ctypes.get_last_error(), "Virtual MIDI send failed")

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
    port = VirtualPort()
    mapper = PedalMapper()
    done = threading.Event()
    midi_in = None
    messages = 0
    errors = 0
    last_input = 0.0

    def stop(*_):
        done.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    def callback(event, _user_data):
        nonlocal messages, errors, last_input
        message, _delta = event
        try:
            old_mode = mapper.mode
            for packet in mapper.transform(message):
                port.send(packet)
            if len(message) >= 2 and message[0] & 0xF0 == 0xC0:
                logging.info("Physical Program Change: %s", message[1])
            if len(message) >= 3 and message[0] & 0xF0 == 0xB0 and message[1] == 64:
                logging.info("Physical pedal CC64=%s -> %s", message[2], MODE_CC[mapper.mode])
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
        logging.info("Virtual output ready: %s", OUTPUT_NAME)
        while not done.wait(1):
            if TEST_FILE.exists():
                try:
                    test_message = bytes.fromhex(TEST_FILE.read_text(encoding="ascii").strip())
                    if not 1 <= len(test_message) <= 3:
                        raise ValueError("Test MIDI must be one short event")
                    for packet in mapper.transform(test_message):
                        port.send(packet)
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
                    for packet in mapper.release_all():
                        port.send(packet)
            STATUS_FILE.write_text(json.dumps({
                "pid": os.getpid(), "connected": midi_in is not None,
                "input": INPUT_NAME, "output": OUTPUT_NAME, "mode": mapper.mode,
                "una_corda": bool(mapper.una_corda_values[0]),
                "messages": messages, "errors": errors, "last_input": last_input,
                "updated": time.time()}, indent=2), encoding="utf-8")
    finally:
        if midi_in is not None:
            midi_in.close_port()
        for packet in mapper.release_all():
            port.send(packet)
        port.close()
        kernel.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == "__main__":
    run()
