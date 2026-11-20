"""Testy 20.11 (MEGA 2.0): protokol skanera Mega, ramki v2 i zgodnosc z tekstem v1."""
import json
import random
import re
import hashlib
from pathlib import Path

import mega_protocol as mp

HERE = Path(__file__).resolve().parent


def on(note, us, t, seq):
    return mp.build_frame(mp.T_NOTE_ON, seq, bytes((note,)) + us.to_bytes(3, "little") + t.to_bytes(4, "little"))


def off(note, us, t, seq):
    return mp.build_frame(mp.T_NOTE_OFF, seq, bytes((note,)) + us.to_bytes(3, "little") + t.to_bytes(4, "little"))


def life(t, seq, sounding=(), scans=7000, scan_us=140):
    bits = sum(1 << (n - 21) for n in sounding)
    p = (t.to_bytes(4, "little") + scans.to_bytes(2, "little") + scan_us.to_bytes(2, "little")
         + (190).to_bytes(2, "little") + (0).to_bytes(2, "little") + (0).to_bytes(2, "little") + bits.to_bytes(11, "little"))
    return mp.build_frame(mp.T_LIFE, seq, p)


def hello(seq=0, build=2026112001):
    return mp.build_frame(mp.T_HELLO, seq, bytes((2, 2, 0)) + build.to_bytes(4, "little") + bytes((3,)))


def test_crc_and_cobs():
    assert mp.crc8(b"123456789") == 0xF4                 # wartosc kontrolna CRC-8/SMBUS
    rnd = random.Random(5)
    for _ in range(500):
        d = bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 300)))
        enc = mp.cobs_encode(d)
        assert 0 not in enc and mp.cobs_decode(enc) == d
    assert mp.cobs_decode(b"\x05ab") is None


def test_frames_decode():
    d = mp.Decoder()
    msgs = d.feed(hello(0) + on(60, 7039, 117565, 1) + off(60, 25032, 553687, 2) + life(2033968, 3, {33, 90}))
    assert msgs[0] == mp.Hello(2, 2, 0, 2026112001, 3) and msgs[0].version == "2.0"   # starsza ramka nadal czytana
    assert msgs[1] == mp.Event("on", 60, 7039, 117565 / 2e6)
    assert msgs[2].kind == "off" and msgs[2].us == 25032
    assert msgs[3].sounding == {33, 90} and msgs[3].scans == 7000
    assert (d.frames, d.crc_errors, d.lost, d.mode) == (4, 0, 0, "v2")


def test_corruption_never_plays_a_wrong_note():
    """Kazdy pojedynczy przeklamany albo zgubiony bajt: albo ta sama nuta, albo zadna (v1 mogl zagrac fff)."""
    good = on(60, 13000, 1000, 7)
    for i in range(len(good) - 1):
        for flip in (0x01, 0x10, 0x80):
            bad = bytearray(good)
            bad[i] ^= flip
            msgs = [m for m in mp.Decoder().feed(bytes(bad) + b"\x00") if isinstance(m, mp.Event)]
            assert msgs in ([], [mp.Event("on", 60, 13000, 1000 / 2e6)]), (i, flip, msgs)
        dropped = good[:i] + good[i + 1:]
        msgs = [m for m in mp.Decoder().feed(dropped) if isinstance(m, mp.Event)]
        assert msgs in ([], [mp.Event("on", 60, 13000, 1000 / 2e6)])


def test_random_noise_gives_nothing():
    rnd = random.Random(9)
    d = mp.Decoder()
    noise = bytes(rnd.randrange(256) for _ in range(200_000))
    events = [m for m in d.feed(noise) if isinstance(m, mp.Event)]
    # CRC-8 przepuszcza ok. 1/256 losowych ramek; dekoder sprawdza jeszcze typ, dlugosc i zakres nuty
    assert len(events) < 30
    assert d.garbage > 150_000


def test_lost_frames_are_counted():
    d = mp.Decoder()
    d.feed(on(60, 9000, 10, 250) + on(62, 9000, 20, 251) + on(64, 9000, 30, 3))   # 252..255, 0..2 przepadly
    assert d.lost == 7


def test_mega_time_unwraps():
    d = mp.Decoder()
    a, = d.feed(on(60, 9000, 0xFFFFFF00, 0))
    b, = d.feed(on(62, 9000, 0x00000100, 1))
    assert abs((b.t - a.t) - 0x200 / 2e6) < 1e-9


def test_v1_text_still_understood():
    d = mp.Decoder()
    msgs = d.feed(b"SKANER v1.2\r\nH 15000 132\r\n+ 60 12000\r\n! 62 R\r\n- 60 900\r\nmisc\r\n")
    assert msgs[0] == mp.Hello(1, 1, 2)
    assert msgs[1] == mp.Life(None, 15000, 132)
    assert msgs[2] == mp.Event("on", 60, 12000) and msgs[3] == mp.Event("rev", 62, 0)
    assert msgs[4] == mp.Event("off", 60, 900) and d.mode == "v1"
    assert d.feed(b"+ 20 100\r\n+ 109 1\r\n") == []


def test_switch_from_v1_to_v2_in_one_stream():
    d = mp.Decoder()
    d.feed(b"H 15000 132\r\n")
    msgs = d.feed(hello(0) + on(70, 8000, 5, 1))
    assert d.mode == "v2" and msgs[-1].note == 70


def test_key_lines_match_the_matrix_and_y2():
    assert mp.key_lines(21) == ("Z1", "X2", "X1")
    assert mp.key_lines(60) == ("Z8", "X10", "X9")
    assert mp.key_lines(61) == ("Y1", "W2", "W1")
    assert {n for n in range(61, 109) if mp.key_lines(n)[0] == "Y2"} == {62, 70, 78, 86, 94, 102}
    assert mp.key_lines(108) == ("Y8", "Y9", "Y10")


def test_firmware_manifest_and_constants_agree():
    """skaner.ino, hex/skaner.json i hex/skaner.hex musza do siebie pasowac (router wgrywa wedlug manifestu)."""
    ino = (HERE / "skaner-mega/firmware/skaner/skaner.ino").read_text(encoding="utf-8")
    man = json.loads((HERE / "skaner-mega/hex/skaner.json").read_text(encoding="utf-8"))
    assert int(re.search(r"BUILD_ID = (\d+)UL", ino).group(1)) == man["build"]
    proto, major, minor = map(int, re.search(r"PROTO = (\d+), FW_MAJOR = (\d+), FW_MINOR = (\d+)", ino).groups())
    assert (proto, f"{major}.{minor}") == (man["proto"], man["wersja"])
    assert hashlib.md5((HERE / "skaner-mega/hex/skaner.hex").read_bytes()).hexdigest() == man["md5"]
    assert re.search(r"TEST_N = (\d+)", ino).group(1) == str(len(mp.TEST_LINES))


def test_v2_frame_with_byte_10_at_the_very_start_is_not_cut():
    """20.11: HELLO skanera 2.1 ma kod COBS 0x0A; dekoder bral go za koniec linii v1 i gubil pierwsza ramke."""
    frame = mp.build_frame(mp.T_HELLO, 0, bytes((2, 2, 1)) + (2026112002).to_bytes(4, "little") + bytes((3,)))
    assert 0x0A in frame
    d = mp.Decoder()
    msgs = d.feed(frame + on(60, 9000, 5, 1))
    assert msgs[0] == mp.Hello(2, 2, 1, 2026112002, 3) and msgs[1].note == 60 and d.crc_errors == 0
    for n in range(1, 60):                        # kazdy bajt 10 w dowolnym miejscu ramki na starcie strumienia
        payload = bytes([n % 256]) * 2 + bytes((10,)) * (n % 7)
        f = mp.build_frame(mp.T_REVERSED, n, bytes((60,)) + (n * 1000003 % 2**32).to_bytes(4, "little"))
        assert [m.kind for m in mp.Decoder().feed(f)] == ["rev"]
    d = mp.Decoder()                              # a tekst v1 dalej dziala
    assert d.feed(b"+ 60 12000\r\n")[0] == mp.Event("on", 60, 12000)
