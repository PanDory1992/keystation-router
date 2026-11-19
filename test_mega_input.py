"""Testy 19.11: klawisze z Arduino Mega (mega_input.py) i ich droga przez router."""
import json

import mega_input
from mega_input import (DEFAULT_SETTINGS, load_settings, note_velocity, parse_line, release_velocity)
from pedal_router import TOUCH_CYCLE_BUTTON, PedalMapper


def settings(curve="fortepian"):
    s = json.loads(json.dumps(DEFAULT_SETTINGS))
    s["krzywa"] = curve
    return s


def test_anchor_and_bosendorfer_slope_on_white_keys():
    s = settings()
    assert note_velocity(60, 6500, s) == 100            # kotwica
    assert note_velocity(60, 13000, s) == 75            # dwa razy dluzej = -25
    assert note_velocity(60, 3250, s) == 125            # dwa razy krocej = +25
    assert note_velocity(60, 15200, s) == 69            # mediana bialych z gry 19.11


def test_full_curve_only_moves_the_anchor():
    s = settings("fortepian-pelny")
    assert note_velocity(60, 6500, s) == 120
    assert note_velocity(60, 13000, s) == 95


def test_black_keys_share_the_white_scale_after_the_factor():
    s = settings()
    assert note_velocity(61, int(6500 * 1.28), s) == note_velocity(60, 6500, s)
    assert note_velocity(61, 6500, s) > note_velocity(60, 6500, s)


def test_velocity_is_monotone_and_clamped():
    s = settings()
    seq = [note_velocity(60, us, s) for us in range(500, 2_000_000, 997)]
    assert all(a >= b for a, b in zip(seq, seq[1:]))
    assert max(seq) == 127 and min(seq) == s["minimum"]
    assert note_velocity(60, 0, s) == 127


def test_release_velocity():
    assert release_velocity(25000) == 64
    assert release_velocity(0) == 64
    assert release_velocity(12500) == 89 and release_velocity(50000) == 39
    assert 1 <= release_velocity(10**7) and release_velocity(1) == 127


def test_parse_line():
    assert parse_line("+ 60 12000") == ("on", 60, 12000)
    assert parse_line("- 108 0") == ("off", 108, 0)
    for bad in ("H 100 72", "+ 60", "+ 20 100", "+ 109 100", "+ x 1", "SKANER v1", "! 62 R", "+ 60 -5"):
        assert parse_line(bad) is None


def test_settings_file(tmp_path):
    assert load_settings(tmp_path / "brak.json")["krzywa"] == "fortepian"
    f = tmp_path / "m.json"
    f.write_text("{zepsute", encoding="utf-8")
    assert load_settings(f)["krzywa"] == "fortepian"
    f.write_text(json.dumps({"krzywa": "nie-ma-takiej", "minimum": 5}), encoding="utf-8")
    s = load_settings(f)
    assert s["krzywa"] == "fortepian" and s["minimum"] == 5


def test_mega_notes_keep_their_velocity_through_the_router():
    m = PedalMapper()
    m.velocity_map = ([1] * 128, [1] * 128)        # mapa czucia, ktora wszystko by splaszczyla
    on = m.mega_message("on", 60, 6500)
    assert m.transform(on, exact=True) == [bytes((0x90, 60, 100))]
    assert 60 in m.active_notes[0]
    off = m.mega_message("off", 60, 12500)
    assert m.transform(off, exact=True) == [bytes((0x80, 60, 89))]
    assert 60 not in m.active_notes[0]
    # zwykla nuta z klawiatury dalej idzie przez mape
    assert m.transform([0x90, 62, 100]) == [bytes((0x90, 62, 1))]


def test_whole_range_a0_to_c8_plays():
    m = PedalMapper()
    for note in (21, 60, 108):
        assert m.transform(m.mega_message("on", note, 13000), exact=True) == [bytes((0x90, note, 75))]


def test_c53_cycles_mega_curves_only_while_the_mega_plays():
    m = PedalMapper()
    m.touch_maps = {"naturalna": ([0] * 128, [0] * 128), "szeroka": ([0] * 128, [0] * 128)}
    m.touch_mode = "naturalna"
    m.mega_active = True
    assert m.transform([0xC0, TOUCH_CYCLE_BUTTON]) == []
    assert m.mega_settings["krzywa"] == "fortepian-pelny" and m.mega_dirty
    assert m.touch_mode == "naturalna"
    m.transform([0xC0, TOUCH_CYCLE_BUTTON])
    assert m.mega_settings["krzywa"] == "fortepian"
    m.mega_active = False
    m.transform([0xC0, TOUCH_CYCLE_BUTTON])
    assert m.touch_mode == "szeroka"


def test_debounce_keeps_the_release_velocity():
    m = PedalMapper()
    m.debounce = True
    m.transform(m.mega_message("on", 60, 6500), exact=True)
    assert m.transform(m.mega_message("off", 60, 12500), exact=True) == []
    (_, packet), = m.pending_offs.values()
    assert packet == bytes((0x80, 60, 89))


def test_module_constants():
    assert mega_input.SLOPE == 25.0 and mega_input.BAUD == 1_000_000


def test_reader_reads_a_live_port(monkeypatch):
    import os
    import pty
    import threading
    import time
    import tty
    master, slave = pty.openpty()
    tty.setraw(slave)
    monkeypatch.setattr(mega_input, "find_port", lambda: os.ttyname(slave))
    got, states = [], []
    done = threading.Event()
    r = mega_input.MegaReader(lambda *e: got.append(e), states.append, done)
    th = threading.Thread(target=r.run, daemon=True)
    th.start()
    time.sleep(0.3)
    os.write(master, b"H 27000 72\r\n+ 60 6500\r\n! 62 R\r\n- 60 25000\r\n")
    for _ in range(50):
        if len(got) == 2:
            break
        time.sleep(0.05)
    done.set()
    th.join(2)
    assert got == [("on", 60, 6500), ("off", 60, 25000)]
    assert states[0] is True and r.events == 2


def test_hires_split_follows_the_cc88_standard():
    from mega_input import hires_split
    assert hires_split(87.43) == (87, 55)          # 0,43 * 128 = 55
    assert hires_split(100.0) == (100, 0)
    assert hires_split(127.0) == (127, 0) and hires_split(0.3) == (1, 0)
    assert hires_split(126.999)[1] <= 127


def test_hires_off_sends_plain_notes_and_b16_stays_on_cc88():
    m = PedalMapper()
    assert m.transform(m.mega_message("on", 60, 7000), exact=True) == [bytes((0x90, 60, 97))]
    assert m.transform([0xB0, 92, 40]) == [bytes((0xB0, 88, 40))]


def test_hires_on_puts_cc88_right_before_the_note_and_moves_b16():
    from pedal_router import PLAY, destination
    m = PedalMapper()
    m.mega_settings["wysoka_rozdzielczosc"] = True
    out = m.transform(m.mega_message("on", 60, 7000), exact=True)
    v = mega_input.note_velocity_exact(60, 7000, m.mega_settings)
    assert out == [bytes((0xB0, 88, int((v - int(v)) * 128))), bytes((0x90, 60, int(v)))]
    assert all(destination(p) == PLAY for p in out)
    assert m.mega_lsb is None                                   # zuzyte przez te jedna nute
    assert m.transform(m.mega_message("off", 60, 25000), exact=True) == [bytes((0x80, 60, 64))]
    b16 = m.transform([0xB0, 92, 40])
    assert b16 == [bytes((0xB0, 89, 40))] and destination(b16[0]) == PLAY
