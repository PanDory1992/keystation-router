"""Testy 19.11: klawisze z Arduino Mega (mega_input.py) i ich droga przez router."""
import json
from pathlib import Path
import random

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
    s = settings("fortepian")
    s["krzywe"]["fortepian-pelny"] = {"kotwica_us": 6500, "kotwica_velocity": 120}
    s["krzywa"] = "fortepian-pelny"
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
    assert load_settings(tmp_path / "brak.json")["krzywa"] == "rowna-b"      # 20.11 wieczor: domyslna Rowna B
    f = tmp_path / "m.json"
    f.write_text("{zepsute", encoding="utf-8")
    assert load_settings(f)["krzywa"] == "rowna-b"
    f.write_text(json.dumps({"krzywa": "nie-ma-takiej", "minimum": 5}), encoding="utf-8")
    s = load_settings(f)
    assert s["krzywa"] == "rowna-b" and s["minimum"] == 5


def test_mega_notes_keep_their_velocity_through_the_router():
    m = PedalMapper()
    m.velocity_map = ([1] * 128, [1] * 128)        # mapa czucia, ktora wszystko by splaszczyla
    on = m.mega_message("on", 60, 6500)
    assert m.transform(on, exact=True) == [bytes((0x90, 60, 126))]
    assert 60 in m.active_notes[0]
    off = m.mega_message("off", 60, 12500)
    assert m.transform(off, exact=True) == [bytes((0x80, 60, 89))]
    assert 60 not in m.active_notes[0]
    # zwykla nuta z klawiatury dalej idzie przez mape
    assert m.transform([0x90, 62, 100]) == [bytes((0x90, 62, 1))]


def test_whole_range_a0_to_c8_plays():
    m = PedalMapper()
    for note in (21, 60, 108):
        assert m.transform(m.mega_message("on", note, 13000), exact=True) == [bytes((0x90, note, 74))]


def test_c53_cycles_mega_curves_only_while_the_mega_plays():
    m = PedalMapper()
    m.touch_maps = {"naturalna": ([0] * 128, [0] * 128), "szeroka": ([0] * 128, [0] * 128)}
    m.touch_mode = "naturalna"
    m.mega_active = True
    assert m.transform([0xC0, TOUCH_CYCLE_BUTTON]) == []
    assert m.mega_settings["krzywa"] == "rowna-c" and m.mega_dirty
    assert m.touch_mode == "naturalna"
    m.transform([0xC0, TOUCH_CYCLE_BUTTON])
    assert m.mega_settings["krzywa"] == "naturalna"
    m.mega_active = False
    m.transform([0xC0, TOUCH_CYCLE_BUTTON])
    assert m.touch_mode == "szeroka"


def test_debounce_does_not_touch_mega_notes():
    """20.11: Mega ma wlasne odszumianie w programie; odszumianie routera (dla zielonej plytki) jej nie opoznia."""
    m = PedalMapper()
    m.debounce = True
    m.transform(m.mega_message("on", 60, 6500), exact=True)
    assert m.transform(m.mega_message("off", 60, 12500), exact=True) == [bytes((0x80, 60, 89))]
    assert not m.pending_offs
    assert m.transform(m.mega_message("on", 60, 6500), exact=True) == [bytes((0x90, 60, 126))]


def test_module_constants():
    assert mega_input.SLOPE == 25.0 and mega_input.BAUD == 250_000


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


def test_hires_off_sends_plain_notes_and_b16_is_on_cc89():
    from pedal_router import PLAY, destination
    m = PedalMapper()
    assert m.transform(m.mega_message("on", 60, 7000), exact=True) == [bytes((0x90, 60, 119))]
    out = m.transform([0xB0, 92, 40])
    assert out == [bytes((0xB0, 89, 40))] and destination(out[0]) == PLAY


def test_hires_on_puts_cc88_right_before_the_note():
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


def test_reader_passes_a_note_at_once(monkeypatch):
    """Nuta z Megi nie moze czekac na timeout portu (blad z 20.11: do 200 ms opoznienia)."""
    import os
    import pty
    import threading
    import time
    import tty
    master, slave = pty.openpty()
    tty.setraw(slave)
    monkeypatch.setattr(mega_input, "find_port", lambda: os.ttyname(slave))
    got = []
    done = threading.Event()
    r = mega_input.MegaReader(lambda *e: got.append((e, time.perf_counter())), lambda on: None, done)
    th = threading.Thread(target=r.run, daemon=True)
    th.start()
    time.sleep(0.4)
    os.write(master, b"H 27000 72\r\n")
    time.sleep(0.4)
    t0 = time.perf_counter()
    os.write(master, b"+ 60 6500\r\n")
    for _ in range(200):
        if got:
            break
        time.sleep(0.002)
    done.set()
    th.join(2)
    assert got and got[0][1] - t0 < 0.05


# --- 20.11: MEGA 2.0 -------------------------------------------------------------------------------------------
import threading  # noqa: E402
from collections import deque  # noqa: E402

import mega_protocol as mp  # noqa: E402
from test_mega_protocol import hello, life, off as f_off, on as f_on  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakeLink:
    """Port Megi z gotowym scenariuszem: lista (czas_od_otwarcia, bajty)."""

    def __init__(self, clock, script, baud):
        self.clock, self.script, self.baud = clock, deque(script), baud
        self.t0 = clock.t
        self.written = b""
        self.dtr = False
        self.pulses = 0
        self.closed = False

    @property
    def in_waiting(self):
        return 0

    def read(self, n):
        self.clock.t += 0.05
        if self.script and self.clock.t - self.t0 >= self.script[0][0]:
            return self.script.popleft()[1]
        return b""

    def write(self, b):
        self.written += b

    def __setattr__(self, k, v):
        if k == "dtr" and v and hasattr(self, "pulses"):
            object.__setattr__(self, "pulses", self.pulses + 1)
        object.__setattr__(self, k, v)

    def close(self):
        self.closed = True


def make_reader(sessions, flasher=None, expected=None, off_flag=None, stop_after=None):
    """sessions: lista scenariuszy kolejnych otwarc portu (250 kbit); probe: scenariusz dla 115200."""
    clock = Clock()
    done = threading.Event()
    got, states, links = [], [], []
    queue = deque(sessions)

    def open_port(port, baud):
        if baud == mega_input.PROBE_BAUD:
            link = FakeLink(clock, [(0.1, b"ROZPOZNANIE v1 38\r\nH 1000 900\r\n")], baud)
        else:
            if not queue:
                done.set()
                raise OSError("koniec scenariusza")
            link = FakeLink(clock, queue.popleft(), baud)
        links.append(link)
        return link

    def sleep(s):
        clock.t += s
        if stop_after is not None and clock.t > stop_after:
            done.set()
        return done.is_set()

    r = mega_input.MegaReader(lambda *e: got.append(e), states.append, done, off_flag=off_flag, flasher=flasher,
                              expected=expected, open_port=open_port, find=lambda: "COM4", clock=clock, sleep=sleep)
    return r, got, states, links, clock


def run_reader(r):
    th = threading.Thread(target=r.run, daemon=True)
    th.start()
    th.join(10)
    assert not th.is_alive()


def test_v2_session_plays_and_asks_for_hello():
    s = [(0.1, hello(0)), (0.2, f_on(60, 6500, 100, 1)), (0.3, f_off(60, 25000, 900, 2)), (0.5, life(2000, 3))]
    r, got, states, links, _ = make_reader([s])
    run_reader(r)
    assert got == [("on", 60, 6500), ("off", 60, 25000)]
    assert states[0] is True and r.proto == 2 and r.hello.version == "2.0"
    assert links[0].written.startswith(b"T") and b"IS" in links[0].written   # test linii raz, potem pytanie o stan
    info = r.info()
    assert info["fw"] == "2.0" and info["frames"] == 4 and info["crc_errors"] == 0


def test_hung_note_is_switched_off_by_the_life_map():
    s = [(0.1, hello(0)), (0.2, f_on(60, 6500, 100, 1)), (0.3, f_on(64, 7000, 200, 2)),
         (1.2, life(2000, 4, {64}))]                     # ramka 3 (wylaczenie 60) zginela
    r, got, *_ = make_reader([s])
    run_reader(r)
    assert ("off", 60, 0) in got and ("off", 64, 0) not in got
    assert r.fixed_stuck == 1 and r.info()["lost"] == 1


def test_silent_mega_escalates_reopen_reset_flash_then_asks_for_the_cable():
    alive = [(0.1, hello(0)), (0.5, life(2000, 1))]
    flashes = []
    r, got, states, links, _ = make_reader(
        [alive + [(12.0, life(4000, 2))], [], [], [], []],
        flasher=lambda port: (flashes.append(port) or (False, "avrdude: not in sync")), stop_after=1400)
    run_reader(r)
    assert links[2].pulses == 1                        # trzecie otwarcie: impuls reset
    assert flashes == ["COM4"]                         # potem jedna proba wgrania
    assert r.state == "mostek" and "odlacz kabel USB" in r.message
    assert True in states and states[-1] is False


def test_foreign_program_is_identified_and_replaced():
    garbage = bytes(random.Random(3).randrange(1, 256) for _ in range(300))
    flashes = []
    r, *_ = make_reader([[(0.1, garbage[:150]), (0.5, garbage[150:])], [(0.1, hello(0))]],
                        flasher=lambda port: (flashes.append(port) or (True, "ok")))
    run_reader(r)
    assert flashes == ["COM4"]
    assert any("rozpoznanie" in x for x in r.flash_log)


def test_old_v1_firmware_is_upgraded_only_when_nothing_plays():
    v1 = [(0.1, b"+ 60 9000\r\n"), (2.0, b"H 15000 132\r\n"), (4.0, b"- 60 25000\r\n"),
          (6.0, b"H 15000 132\r\n"), (8.0, b"H 15000 132\r\n"), (10.0, b"H 15000 132\r\n"), (12.0, b"H 15000 132\r\n")]
    flashes = []
    r, got, *_ = make_reader([v1, [(0.1, hello(0))]], flasher=lambda port: (flashes.append(r.clock()) or (True, "ok")),
                             expected={"proto": 2, "build": 2026112001})
    t_open = r.clock()
    run_reader(r)
    assert got == [("on", 60, 9000), ("off", 60, 25000)]
    assert len(flashes) == 1 and flashes[0] - t_open > 8.9    # dopiero 5 s po puszczeniu ostatniej nuty
    assert r.proto == 2


def test_same_build_is_not_flashed_and_flash_limit_holds():
    calls = []
    r, *_ = make_reader([[(0.1, hello(0)), (0.5, life(2000, 1))]], flasher=lambda p: (calls.append(p) or (True, "")),
                        expected={"proto": 2, "build": 2026112001})
    run_reader(r)
    assert calls == []
    r2, *_ = make_reader([[(0.1, b"\x01\x02" * 100)]] * 6, flasher=lambda p: (calls.append(p) or (True, "")))
    run_reader(r2)
    assert len(calls) == mega_input.FLASH_LIMIT


def test_stale_mega_off_flag_no_longer_blocks(tmp_path):
    import os
    import time as _t
    flag = tmp_path / "mega-off"
    flag.write_text("mega.py", encoding="ascii")
    assert mega_input.flag_active(flag, _t.time())
    os.utime(flag, (_t.time() - 60, _t.time() - 60))           # narzedzie zamkniete krzyzykiem minute temu
    assert not mega_input.flag_active(flag, _t.time())
    assert not mega_input.flag_active(tmp_path / "brak", _t.time())


def test_line_health_finds_a_dead_line_like_y2():
    h = mega_input.LineHealth()
    rnd = random.Random(2)
    for _ in range(400):
        n = rnd.randrange(61, 109)
        if mp.key_lines(n)[0] != "Y2":
            h.note_on(n)
    p = h.problems()
    assert len(p) == 1 and p[0].startswith("Linia Y2 milczy") and "D4" in p[0] and "Bb4" in p[0]
    for _ in range(6):
        h.reversed(39)
    assert any(x.startswith("Eb2: drugi styk") for x in h.problems())
    assert mega_input.LineHealth().problems() == []          # za malo gry: nic nie twierdzimy


def test_selftest_analysis_is_careful():
    names = mp.TEST_LINES
    ok = mp.SelfTest([24] * 38 + [6, 7], set())
    assert mega_input.analyse_selftest(ok) == []
    loose = mp.SelfTest([24] * 21 + [7] + [24] * 16 + [6, 7], set())        # Y2 jak pusty pin
    assert mega_input.analyse_selftest(loose) == ["Linia Y2: zachowuje sie jak pusty pin (przewod nie siedzi w gniezdzie?)"]
    flat = mp.SelfTest([7] * 40, set())                                       # brak roznicy: nic nie twierdzimy
    assert mega_input.analyse_selftest(flat) == []
    bad = mp.SelfTest([24] * 40, {"X3"})
    assert mega_input.analyse_selftest(bad) == ["Linia X3: pin nie schodzi do zera (uszkodzony pin Megi?)"]
    assert len(names) == 40


def test_artifact_filter_drops_note_and_its_off():
    f = mega_input.ArtifactFilter()
    assert not f.accept("on", 60, 900, 2000) and not f.accept("off", 60, 25000, 2000)
    assert f.accept("on", 60, 6000, 2000) and f.accept("off", 60, 25000, 2000)
    assert f.count == 1
    assert f.accept("off", 61, 0, 2000)


def test_flasher_refuses_hex_that_does_not_match_the_manifest(tmp_path):
    (tmp_path / "skaner.hex").write_text(":00000001FF\n")
    (tmp_path / "skaner.json").write_text(json.dumps({"proto": 2, "build": 1, "md5": "0" * 32}))
    dude = tmp_path / "avrdude.exe"
    dude.write_text("")
    ok, text = mega_input.make_flasher(tmp_path, dude, tmp_path / "c")("COM4")
    assert not ok and "inne md5" in text


def test_latency_summary_measures_excess_over_best():
    lat = mega_input.Latency()
    lat.life(0.0, 100.0)
    for i in range(50):
        lat.event(i * 0.1, 100.0 + i * 0.1 + (0.004 if i % 10 == 0 else 0.001))
    s = lat.summary()
    assert s["p50_ms"] == 1.0 and abs(s["max_ms"] - 4.0) < 0.01      # wzgledem najlepszej ramki (ZYCIE)


def test_v1_idle_at_start_is_upgraded_at_once():
    flashes = []
    r, *_ = make_reader([[(0.1, b"H 15000 132\r\n")], [(0.1, hello(0))]],
                        flasher=lambda p: (flashes.append(p) or (True, "ok")), expected={"proto": 2, "build": 2026112001})
    run_reader(r)
    assert flashes == ["COM4"] and r.flash_log and "starszy program" in r.flash_log[0]


def test_reader_survives_a_crashing_flasher_and_bad_callbacks():
    calls = []

    def boom(port):
        calls.append(port)
        raise UnicodeDecodeError("cp1250", b"\x98", 0, 1, "zly bajt w wyjsciu avrdude")
    r, *_ = make_reader([[(0.1, b"\x01\x02" * 100)], [(0.1, hello(0)), (0.5, life(2000, 1))]], flasher=boom)
    run_reader(r)
    assert calls and "blad wgrywania" in r.flash_log[0] and r.proto == 2


# --- 20.11: Naturalna z czasu Megi ----------------------------------------------------------------------------
def test_naturalna_is_the_router_curve_made_continuous():
    """Ta sama krzywa co velocity-map.naturalna.json (zielona plytka): kazda wartosc surowego 2..118 zgadza sie."""
    table = json.loads(Path(__file__).with_name("velocity-map.naturalna.json").read_text(encoding="utf-8"))["white"]
    p = mega_input.NATURALNA_MEGA
    for r in range(2, 119):
        assert min(127, round(mega_input.naturalna_raw_value(p, r))) == table[r], r


def test_naturalna_from_mega_times():
    s = settings("naturalna")
    v = lambda us, n=60: note_velocity(n, us, s)  # noqa: E731
    assert v(6008) == 127                   # najmocniejsze 1% Twojej gry = fff, jak p99 w Naturalnej
    assert v(14775) == 82                   # mediana = 82 (w Naturalnej mediana bialych 81)
    assert v(32720) == 29 and v(44328) == 17
    assert v(int(14775 * 1.28), 61) == 82   # czarne: ta sama skala po przeliczniku
    seq = [v(us) for us in range(3000, 400_000, 211)]
    assert seq == sorted(seq, reverse=True)
    assert v(120_000) == 2 and 2 < v(70_000) < 10   # wolniej niz prog zielonej plytki: dalej lagodnie w dol


def test_bad_curves_in_the_file_are_dropped(tmp_path):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"krzywa": "zla", "krzywe": {
        "zla": {"naturalna": {"K": 100, "tau_us": 460, "lo": 2, "hi": 118, "g": 1.7, "pivot": 100}},
        "pusta": {"punkty": [[1000, 100]]}, "dobra": {"kotwica_us": 6500, "kotwica_velocity": 90}}}))
    s = load_settings(f)
    assert list(s["krzywe"]) == ["dobra"] and s["krzywa"] == "dobra"


# --- 20.11 wieczor: krzywe "rowna" A, B, C (kazdy krok tak szeroki jak rozrzut odczytu) ------------------------
def test_rowna_curves_values():
    for name, want in [("rowna-a", [124, 99, 84, 73, 61, 49, 40, 34, 27, 21, 17, 13, 9, 6, 3, 2]),
                       ("rowna-b", [127, 107, 90, 79, 66, 53, 43, 36, 29, 23, 18, 14, 10, 6, 3, 2]),
                       ("rowna-c", [127, 113, 96, 83, 70, 56, 46, 38, 31, 24, 19, 15, 10, 7, 3, 2])]:
        s = settings(name)
        got = [note_velocity(60, ms * 1000, s) for ms in (6, 8, 10, 12, 15, 20, 26, 33, 44, 60, 80, 100, 130, 160, 200, 250)]
        assert got == want, name


def test_rowna_steps_are_as_wide_as_the_scatter():
    p = mega_input.DEFAULT_CURVES["rowna-b"]["rozrzut"]
    v = lambda us: mega_input.rozrzut_value(p, us)  # noqa: E731
    assert abs(v(6400) - 127) < 1e-9 and abs(v(208400) - 2) < 1e-9
    def t_of(vel):
        lo, hi = 3000.0, 400000.0
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if v(mid) > vel else (lo, mid)
        return lo
    widths = [t_of(x - 1) - t_of(x) for x in (120, 100, 80, 60, 40, 20, 10, 5, 3)]
    assert widths == sorted(widths)                              # w dol coraz szerzej
    # w miejscu, gdzie rozrzut sie nie zmienia, krok w log2 czasu = staly ulamek rozrzutu
    a, b = p["a"], p["b"]
    for ms in (8, 15, 25):
        sigma = a * ms ** b
        dv = v(ms * 1000 * 2 ** (sigma / 100)) - v(ms * 1000)   # 1/100 rozrzutu w log2 czasu
        assert abs(dv + 125 / 10.88 / 100) < 0.02                  # ok. 10,9 poziomu na caly zakres
    seq = [v(us) for us in range(3000, 400000, 173)]
    assert seq == sorted(seq, reverse=True)
    s = settings("rowna-b")
    assert note_velocity(61, int(16000 * 1.28), s) == note_velocity(60, 16000, s)


def test_rowna_bad_params_dropped():
    assert not mega_input.curve_ok({"rozrzut": {"a": 0.04, "b": 0.76, "smax": 1, "t_top_us": 9000, "t_bot_us": 8000,
                                                "v_top": 127, "v_bot": 2}})
    assert mega_input.curve_ok(mega_input.DEFAULT_CURVES["rowna-a"])
