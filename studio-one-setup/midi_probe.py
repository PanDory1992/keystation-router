"""Read-only WinMM MIDI monitor for checking Keystation CC messages."""
import ctypes
import time
from ctypes import wintypes

winmm = ctypes.WinDLL("winmm.dll")
DWORD_PTR = ctypes.c_size_t
HMIDIIN = ctypes.c_void_p

class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("vDriverVersion", wintypes.UINT),
        ("szPname", ctypes.c_wchar * 32),
        ("dwSupport", wintypes.DWORD),
    ]

CALLBACK = ctypes.WINFUNCTYPE(None, HMIDIIN, wintypes.UINT, DWORD_PTR, DWORD_PTR, DWORD_PTR)

@CALLBACK
def on_midi(_handle, message, _instance, param1, _param2):
    if message == 0x3C3:  # MIM_DATA
        status = param1 & 0xFF
        data1 = (param1 >> 8) & 0xFF
        data2 = (param1 >> 16) & 0xFF
        if status & 0xF0 == 0xB0:
            print(f"CC channel={(status & 0x0F) + 1} number={data1} value={data2}", flush=True)
        elif status & 0xF0 in (0x80, 0x90):
            print(f"NOTE status={status:02X} note={data1} velocity={data2}", flush=True)

winmm.midiInGetNumDevs.restype = wintypes.UINT
winmm.midiInGetDevCapsW.argtypes = [DWORD_PTR, ctypes.POINTER(MIDIINCAPSW), wintypes.UINT]
winmm.midiInOpen.argtypes = [ctypes.POINTER(HMIDIIN), wintypes.UINT, DWORD_PTR, DWORD_PTR, wintypes.DWORD]
winmm.midiInStart.argtypes = [HMIDIIN]
winmm.midiInStop.argtypes = [HMIDIIN]
winmm.midiInClose.argtypes = [HMIDIIN]

for index in range(winmm.midiInGetNumDevs()):
    caps = MIDIINCAPSW()
    if winmm.midiInGetDevCapsW(index, ctypes.byref(caps), ctypes.sizeof(caps)):
        continue
    if caps.szPname != "Keystation Pro 88":
        continue
    handle = HMIDIIN()
    rc = winmm.midiInOpen(ctypes.byref(handle), index, ctypes.cast(on_midi, ctypes.c_void_p).value, 0, 0x30000)
    print(f"OPEN {caps.szPname} index={index} rc={rc}", flush=True)
    if rc:
        break
    try:
        winmm.midiInStart(handle)
        time.sleep(20)
        winmm.midiInStop(handle)
    finally:
        winmm.midiInClose(handle)
    break
