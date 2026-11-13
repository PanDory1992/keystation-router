"""Local MIDI transport bridge for Studio One. No UI automation.

31.10.2026 (Claude): hardened. A single bad client connection (timeout, reset,
garbage bytes) used to raise out of the accept loop, close the virtual port and
end the process silently - Studio One then showed "MCP Bridge: Port not found".
Now every connection is isolated, every error is logged to bridge.log, and the
loop keeps serving. Protocol is unchanged. Previous version:
studio_one_bridge.before-hardening-20261031.py
"""
import ctypes
from datetime import datetime
from pathlib import Path
import socket
import time
import traceback

PORT_NAME = "Codex Studio One Control"
HOST = "127.0.0.1"
TCP_PORT = 47688
COMMANDS = {
    "rewind": 0x16,
    "forward": 0x17,
    "stop": 0x18,
    "play": 0x19,
    "record": 0x1A,
    "click": 0x2B,
}
LOG = Path(__file__).with_name("bridge.log")


def log(message):
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
    except OSError:
        pass


log("STARTING")
vm = ctypes.WinDLL(r"C:\Windows\System32\teVirtualMIDI64.dll", use_last_error=True)
vm.virtualMIDICreatePortEx2.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
vm.virtualMIDICreatePortEx2.restype = ctypes.c_void_p
vm.virtualMIDISendData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint32]
vm.virtualMIDISendData.restype = ctypes.c_bool
vm.virtualMIDIClosePort.argtypes = [ctypes.c_void_p]


def send(handle, values):
    packet = (ctypes.c_ubyte * len(values))(*values)
    if not vm.virtualMIDISendData(handle, packet, len(values)):
        raise OSError(ctypes.get_last_error(), "MIDI send failed")


def handle_command(handle, command):
    if command == "ping":
        return b"pong\n"
    if command == "doorbell":
        for value in (127, 0):
            send(handle, (0x90, 119, value))
        return b"ok\n"
    if command.startswith("midi "):
        values = bytes.fromhex(command[5:])
        if len(values) not in (2, 3):
            raise ValueError("expected two or three MIDI bytes")
        send(handle, tuple(values))
        return b"ok\n"
    if command not in COMMANDS:
        return b"error: unknown command\n"
    for value in (127, 0):
        send(handle, (0xB0, COMMANDS[command], value))
    log(f"COMMAND {command} sent")
    return b"ok\n"


handle = None
for attempt in range(1, 151):  # right after boot the driver may not be ready yet
    handle = vm.virtualMIDICreatePortEx2(PORT_NAME, None, 0, 65535, 1)
    if handle:
        break
    log(f"port not ready (attempt {attempt}, error {ctypes.get_last_error()})")
    time.sleep(2)
if not handle:
    log(f"EXIT could not create virtual MIDI port (error {ctypes.get_last_error()}) - already running?")
    raise OSError(ctypes.get_last_error(), "Could not create virtual MIDI port")

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        # exclusive: a second copy must fail here instead of silently sharing the port
        server.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR), 1)
        server.bind((HOST, TCP_PORT))
        server.listen(8)
        log(f"READY {PORT_NAME} {HOST}:{TCP_PORT}")
        print(f"READY {PORT_NAME} {HOST}:{TCP_PORT}", flush=True)
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                log("ACCEPT error (continuing): " + traceback.format_exc().strip().splitlines()[-1])
                time.sleep(0.5)
                continue
            try:
                with conn:
                    conn.settimeout(2)
                    command = conn.recv(64).decode("ascii", "replace").strip().lower()
                    try:
                        reply = handle_command(handle, command)
                    except (ValueError, OSError) as exc:
                        reply = f"error: {exc}\n".encode()
                    conn.sendall(reply)
            except Exception:
                log("CONNECTION error (continuing): " + traceback.format_exc().strip().splitlines()[-1])
except Exception:
    log("FATAL " + traceback.format_exc().replace("\n", " | "))
    raise
finally:
    vm.virtualMIDIClosePort(handle)
    log("STOPPED")
