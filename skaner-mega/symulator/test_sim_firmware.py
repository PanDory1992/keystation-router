"""Testy prawdziwego programu skaner.elf na wirtualnym ATmega2560 (simavr) z modelem matrycy Keystation.

Uruchom: cd sim && python3 -m unittest test_sim_firmware -v   (wymaga matrix_sim i build/skaner/skaner.ino.elf)
"""
import random
import unittest

import run
import mega_protocol as mp

SCAN_US = 200          # tolerancja pomiaru: jeden pelny skan (ok. 140 us) z zapasem


def press(t, note, dur_us, hold_us=150000, rel_us=25000):
    """Uderzenie: pierwszy styk, po dur_us drugi; puszczenie: drugi, po rel_us pierwszy."""
    return [f"{t} k {note} 0 1", f"{t + dur_us} k {note} 1 1",
            f"{t + dur_us + hold_us} k {note} 1 0", f"{t + dur_us + hold_us + rel_us} k {note} 0 0"]


def events(msgs, kind=None):
    return [m for _, m in msgs if isinstance(m, mp.Event) and (kind is None or m.kind == kind)]


class FirmwareSim(unittest.TestCase):
    def test_hello_and_selftest_at_start(self):
        d, msgs = run.sim([], 1_200_000)
        hello = [m for _, m in msgs if isinstance(m, mp.Hello)]
        self.assertEqual((hello[0].proto, hello[0].version, hello[0].build), (2, "2.0", 2026112001))
        self.assertTrue(hello[0].flags & 1, "mapa pinow OK")
        self.assertTrue(any(isinstance(m, mp.SelfTest) for _, m in msgs))
        lives = [m for _, m in msgs if isinstance(m, mp.Life)]
        self.assertEqual(len(lives), 1)
        self.assertGreater(lives[0].scans, 5000)
        self.assertEqual((d.crc_errors, d.lost, d.garbage), (0, 0, 0))

    def test_every_key_once_with_exact_timing(self):
        scen, truth, t = [], {}, 100_000
        rnd = random.Random(1)
        for note in range(21, 109):
            dur = rnd.choice([5200, 7000, 12000, 16400, 40000, 170000])
            truth[note] = dur
            scen += press(t, note, dur, hold_us=30000, rel_us=20000)
            t += dur + 60000
        scen.sort(key=lambda s: float(s.split()[0]))
        d, msgs = run.sim(scen, t + 100_000)
        on = {e.note: e.us for e in events(msgs, "on")}
        self.assertEqual(sorted(on), list(range(21, 109)), "kazdy z 88 klawiszy gra dokladnie raz")
        self.assertEqual(len(events(msgs, "on")), 88)
        self.assertEqual(len(events(msgs, "off")), 88)
        for note, dur in truth.items():
            self.assertLess(abs(on[note] - dur), SCAN_US, f"MIDI {note}: {on[note]} us zamiast {dur}")
        for e in events(msgs, "off"):
            self.assertLess(abs(e.us - 20000), SCAN_US)
        self.assertEqual((d.crc_errors, d.lost), (0, 0))

    def test_old_wiring_y2_on_pin43_breaks_only_y2_keys(self):
        """Model jest wierny: z przewodem Y2 na 43 i programem dla A8 milkna dokladnie D4, Bb4, Gb5, D6, Bb6, Gb7."""
        scen, t = [], 100_000
        for note in range(61, 109):
            scen += press(t, note, 9000, hold_us=20000)
            t += 80000
        scen.sort(key=lambda s: float(s.split()[0]))
        _, msgs = run.sim(scen, t + 100_000, env={"Y2_ON_43": "1"})
        silent = sorted(set(range(61, 109)) - {e.note for e in events(msgs, "on")})
        self.assertEqual(silent, [62, 70, 78, 86, 94, 102])

    def test_chord_of_ten_keeps_each_timing(self):
        notes = [48, 52, 55, 60, 64, 67, 71, 72, 76, 79]
        scen = []
        for i, n in enumerate(notes):
            scen += press(100_000 + i * 150, n, 6000 + 700 * i, hold_us=300000)
        scen.sort(key=lambda s: float(s.split()[0]))
        d, msgs = run.sim(scen, 700_000)
        on = {e.note: e.us for e in events(msgs, "on")}
        for i, n in enumerate(notes):
            self.assertLess(abs(on[n] - (6000 + 700 * i)), SCAN_US)
        # czas Megi: odstepy miedzy uderzeniami zgadzaja sie z prawda (do jednego skanu)
        ts = {e.note: e.t for e in events(msgs, "on")}
        for i, n in enumerate(notes[1:], 1):
            want = (100_000 + i * 150 + 6000 + 700 * i) - (100_000 + 6000)
            self.assertLess(abs((ts[n] - ts[notes[0]]) * 1e6 - want), SCAN_US)

    def test_all_88_at_once_no_overflow(self):
        scen = []
        for n in range(21, 109):
            scen += press(100_000 + (n % 5) * 50, n, 8000, hold_us=200000)
        scen.sort(key=lambda s: float(s.split()[0]))
        d, msgs = run.sim(scen, 1_300_000)
        self.assertEqual(len(events(msgs, "on")), 88)
        self.assertEqual(len(events(msgs, "off")), 88)
        life = [m for _, m in msgs if isinstance(m, mp.Life)]
        self.assertEqual(life[-1].overflows, 0)
        # ostatnia nuta z 88 wychodzi z Megi w czasie przesylu ok. 88 ramek po 13 bajtow przy 250 kbit
        last = max(t for t, m in msgs if isinstance(m, mp.Event) and m.kind == "on")
        self.assertLess(last - 108_000, 60_000)

    def test_bounce_within_lockout_is_one_note(self):
        scen = ["100000 k 60 0 1", "100300 k 60 0 0", "100500 k 60 0 1", "107000 k 60 1 1",
                "107200 k 60 1 0", "107400 k 60 1 1", "300000 k 60 1 0", "320000 k 60 0 0"]
        _, msgs = run.sim(scen, 600_000)
        self.assertEqual([(e.kind, e.note) for e in events(msgs) if e.kind != "rev"], [("on", 60), ("off", 60)])

    def test_reversed_contacts_no_sound(self):
        scen = ["100000 k 40 1 1", "105000 k 40 0 1", "200000 k 40 0 0", "200100 k 40 1 0"]
        _, msgs = run.sim(scen, 500_000)
        kinds = [e.kind for e in events(msgs)]
        self.assertIn("rev", kinds)
        self.assertNotIn("on", kinds)

    def test_life_reports_held_keys_and_commands(self):
        scen = ["100000 k 33 0 1", "109000 k 33 1 1", "100000 k 90 0 1", "111000 k 90 1 1",
                "300000 rx 83", "320000 rx 73", "340000 rx 84"]   # 'S', 'I', 'T'
        scen.sort(key=lambda s: float(s.split()[0]))
        _, msgs = run.sim(scen, 700_000)
        lives = [m for _, m in msgs if isinstance(m, mp.Life)]
        self.assertTrue(lives, "polecenie S daje ZYCIE od razu")
        self.assertEqual(lives[0].sounding, {33, 90})
        self.assertGreaterEqual(lives[0].rx, 1)
        self.assertGreaterEqual(sum(isinstance(m, mp.Hello) for _, m in msgs), 2)
        self.assertGreaterEqual(sum(isinstance(m, mp.SelfTest) for _, m in msgs), 2)

    def test_slow_press_measured_up_to_seconds(self):
        _, msgs = run.sim(press(100_000, 50, 2_000_000, hold_us=100000), 2_500_000)
        on = events(msgs, "on")
        self.assertEqual(len(on), 1)
        self.assertLess(abs(on[0].us - 2_000_000), SCAN_US)

    def test_heartbeat_every_second(self):
        _, msgs = run.sim([], 3_300_000)
        times = [t for t, m in msgs if isinstance(m, mp.Life)]
        self.assertEqual(len(times), 3)
        gaps = [b - a for a, b in zip(times, times[1:])]
        for g in gaps:
            self.assertLess(abs(g - 1_000_000), 5000)


if __name__ == "__main__":
    unittest.main()
