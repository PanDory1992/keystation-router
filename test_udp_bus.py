import json
import socket
import time

from udp_bus import UdpBus


def client(bus, name="test"):
    c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    c.bind(("127.0.0.1", 0))
    c.settimeout(1.0)
    c.sendto(json.dumps({"t": "hello", "name": name}).encode(), bus.address)
    return c


def recv(c):
    data, _ = c.recvfrom(8192)
    return json.loads(data)


def wait_for(cond, timeout=1.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_join_events_and_play():
    played, settings = [], []
    bus = UdpBus(on_set=settings.append, on_play=played.extend, port=0)
    bus.state_fn = lambda: {"v": 1, "touch": "acoustic"}
    bus.start()
    try:
        a, b = client(bus, "a"), client(bus, "b")
        assert recv(a)["t"] == "welcome" and recv(a)["touch"] == "acoustic"
        assert recv(b)["t"] == "welcome" and recv(b)["t"] == "state"
        assert sorted(bus.listeners()) == ["a", "b"]

        bus.note(True, 60, 98, 72)
        for c in (a, b):                       # every listener gets every event
            e = recv(c)
            assert (e["t"], e["note"], e["raw"], e["vel"], e["src"]) == ("note", 60, 98, 72, "keys")

        a.sendto(json.dumps({"t": "set", "set": {"touch": "light"}}).encode(), bus.address)
        assert wait_for(lambda: settings == [{"touch": "light"}])

        # play: only note messages pass; the listeners see whose notes they are
        a.sendto(json.dumps({"t": "play", "midi": [[144, 64, 80], [176, 7, 0], [144, 300, 1]]}).encode(),
                 bus.address)
        assert wait_for(lambda: played == [bytes([144, 64, 80])])
        e = recv(b)
        assert (e["note"], e["on"], e["src"]) == (64, True, "a")

        # leaving releases what it still holds
        a.sendto(b'{"t":"bye"}', bus.address)
        assert wait_for(lambda: played[-1:] == [bytes([0x80, 64, 0])])
        assert bus.listeners() == ["b"]
    finally:
        bus.close()


def test_strangers_cannot_play_and_silent_listeners_expire():
    played = []
    now = [1000.0]
    bus = UdpBus(on_play=played.extend, port=0, clock=lambda: now[0])
    stranger = ("127.0.0.1", 9)
    bus.handle(b'{"t":"play","midi":[[144,60,90]]}', stranger)
    assert played == []
    bus.handle(b'{"t":"hello","name":"t"}', stranger)
    bus.handle(b'{"t":"play","midi":[[144,60,90]]}', stranger)
    assert played == [bytes([144, 60, 90])]
    now[0] += 11                               # no hello for > 10 s
    bus.expire()
    assert bus.listeners() == [] and played[-1] == bytes([0x80, 60, 0])
    bus.handle(b"not json", stranger)          # garbage is ignored
    bus.close()
