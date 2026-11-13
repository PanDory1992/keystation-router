import ctypes

class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort), ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint32), ("szPname", ctypes.c_wchar * 32),
        ("dwSupport", ctypes.c_uint32),
    ]

winmm = ctypes.WinDLL("winmm")
winmm.midiInGetNumDevs.restype = ctypes.c_uint32
winmm.midiInGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(MIDIINCAPSW), ctypes.c_uint32]
for i in range(winmm.midiInGetNumDevs()):
    caps = MIDIINCAPSW()
    result = winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
    print(i, result, caps.szPname)
