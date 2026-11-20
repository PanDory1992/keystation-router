"""Od klawisza do routera: prawdziwy skaner.elf (simavr) -> bajty -> MegaReader -> zdarzenia; oraz mega.py diagnoza."""
import importlib
import sys
import threading
import unittest
from pathlib import Path

import run
from test_sim_firmware import press

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import mega_input  # noqa: E402


def sim_bytes(scen, us):
    run.sim(scen, us)
    return [(float(t) / 1e6, int(b)) for t, b in (line.split() for line in open("out.txt"))]


class Replay:
    """Port, ktory oddaje bajty z symulacji w ich czasie (zegar testu przesuwa sie z odczytami)."""

    def __init__(self, clock, data):
        self.clock, self.data, self.i, self.t0 = clock, data, 0, clock.t
        self.written = b""
        self.dtr = False

    @property
    def in_waiting(self):
        return 0

    def read(self, n):
        self.clock.t += 0.002
        now = self.clock.t - self.t0
        out = bytearray()
        while self.i < len(self.data) and self.data[self.i][0] <= now:
            out.append(self.data[self.i][1])
            self.i += 1
        if self.i >= len(self.data) and now > self.data[-1][0] + 1:
            raise OSError("koniec nagrania")
        return bytes(out)

    def write(self, b):
        self.written += b

    def close(self):
        pass


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


class EndToEnd(unittest.TestCase):
    def test_keys_reach_the_router_with_exact_times(self):
        scen = []
        for i, (note, dur) in enumerate([(21, 5200), (62, 9000), (108, 16400), (60, 40000)]):
            scen += press(300_000 + i * 120_000, note, dur, hold_us=50_000)
        scen.sort(key=lambda s: float(s.split()[0]))
        data = sim_bytes(scen, 1_300_000)
        clock, done, got, sessions = Clock(), threading.Event(), [], []

        def open_port(port, baud):
            if sessions:
                done.set()
                raise OSError("tylko jedno polaczenie")
            sessions.append(1)
            return Replay(clock, data)

        r = mega_input.MegaReader(lambda *e: got.append(e), lambda on: None, done, open_port=open_port,
                                  find=lambda: "SIM", clock=clock, sleep=lambda s: done.is_set())
        th = threading.Thread(target=r.run, daemon=True)
        th.start()
        th.join(20)
        on = {n: us for k, n, us in got if k == "on"}
        self.assertEqual(sorted(on), [21, 60, 62, 108])
        for note, dur in [(21, 5200), (62, 9000), (108, 16400), (60, 40000)]:
            self.assertLess(abs(on[note] - dur), 200)
        self.assertEqual(sum(1 for k, *_ in got if k == "off"), 4)
        info = r.info()
        self.assertEqual((info["fw"], info["proto"], info["crc_errors"], info["lost"]), ("2.1", 2, 0, 0))
        self.assertEqual(info["selftest"], [])      # w symulatorze wszystkie linie sa "puste": nic nie twierdzimy

    def test_mega_py_diagnoza_reads_the_scanner(self):
        data = sim_bytes([], 1_200_000)
        sys.path.insert(0, str(ROOT / "skaner-mega"))
        mega = importlib.import_module("mega")
        clock = Clock()

        class FakeSerial:
            def __init__(self, port, baud, timeout=0.05):
                self.r = Replay(clock, data) if baud == mega.BAUD_SKANER else Replay(clock, [(0.0, 0)])

            @property
            def in_waiting(self):
                return 0

            def read(self, n):
                try:
                    return self.r.read(n)
                except OSError:
                    return b""

            def write(self, b):
                self.r.written += b

            def close(self):
                pass

        real_time = mega.time.time
        mega.serial.Serial = FakeSerial
        mega.time.time = clock
        out = []
        mega.say = lambda *a: out.append(" ".join(map(str, a)))
        mega.WYNIKI = Path(run.__file__).parent / "wyniki-test"

        class A:
            port = "SIM"
        try:
            self.assertEqual(mega.cmd_diagnoza(A()), 0)
        finally:
            mega.time.time = real_time
        text = "\n".join(out)
        self.assertIn("Skaner 2.1, protokół 2, build 2026112002, piny OK", text)
        self.assertIn("Test linii", text)
        self.assertIn("zepsutych 0, zgubionych 0", text)


if __name__ == "__main__":
    unittest.main()
