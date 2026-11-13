"""Local MIDI transport bridge for Studio One. No UI automation."""
import ctypes
from datetime import datetime
from pathlib import Path
import socket
import sys

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
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")

vm = ctypes.WinDLL(r"C:\Windows\System32\teVirtualMIDI64.dll", use_last_error=True)
vm.virtualMIDICreatePortEx2.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
vm.virtualMIDICreatePortEx2.restype = ctypes.c_void_p
vm.virtualMIDISendData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint32]
vm.virtualMIDISendData.restype = ctypes.c_bool
vm.virtualMIDIClosePort.argtypes = [ctypes.c_void_p]

handle = vm.virtualMIDICreatePortEx2(PORT_NAME, None, 0, 65535, 1)
if not handle:
    raise OSError(ctypes.get_last_error(), "Could not create virtual MIDI port")

try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, TCP_PORT))
        server.listen(4)
        log(f"READY {PORT_NAME} {HOST}:{TCP_PORT}")
        print(f"READY {PORT_NAME} {HOST}:{TCP_PORT}", flush=True)
        while True:
            conn, _ = server.accept()
            with conn:
                conn.settimeout(2)
                command = conn.recv(64).decode("ascii", "strict").strip().lower()
                if command == "ping":
                    conn.sendall(b"pong\n")
                    continue
                if command == "doorbell":
                    for value in (127, 0):
                        packet = (ctypes.c_ubyte * 3)(0x90, 119, value)
                        if not vm.virtualMIDISendData(handle, packet, 3):
                            conn.sendall(f"error: MIDI {ctypes.get_last_error()}\n".encode())
                            break
                    else:
                        conn.sendall(b"ok\n")
                    continue
                if command.startswith("midi "):
                    try:
                        values = bytes.fromhex(command[5:])
                        if len(values) not in (2, 3):
                            raise ValueError("expected two or three MIDI bytes")
                        packet = (ctypes.c_ubyte * len(values))(*values)
                        if not vm.virtualMIDISendData(handle, packet, len(values)):
                            raise OSError(ctypes.get_last_error(), "MIDI send failed")
                        conn.sendall(b"ok\n")
                    except (ValueError, OSError) as exc:
                        conn.sendall(f"error: {exc}\n".encode())
                    continue
                if command not in COMMANDS:
                    conn.sendall(b"error: unknown command\n")
                    continue
                cc = COMMANDS[command]
                for value in (127, 0):
                    packet = (ctypes.c_ubyte * 3)(0xB0, cc, value)
                    if not vm.virtualMIDISendData(handle, packet, 3):
                        conn.sendall(f"error: MIDI {ctypes.get_last_error()}\n".encode())
                        break
                else:
                    log(f"COMMAND {command} sent")
                    conn.sendall(b"ok\n")
finally:
    vm.virtualMIDIClosePort(handle)
