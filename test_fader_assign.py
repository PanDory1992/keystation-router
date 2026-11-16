import json

from fader_assign import DEFAULT_MAP, FaderLink, gain_for, load_map


def test_gain_curve():
    assert gain_for(0) == 0.0
    assert gain_for(127) == 1.0                       # the very top = exactly 0 dB
    assert abs(gain_for(round(0.75 * 126)) - 1.0) < 0.03
    assert abs(gain_for(126) - 10 ** 0.5) < 1e-3      # +10 dB
    values = [gain_for(v) for v in range(127)]
    assert values == sorted(values)


def test_moves_go_to_assigned_channels_through_the_mailbox(tmp_path):
    rings = []
    link = FaderLink(mailbox=tmp_path / "mb", map_path=tmp_path / "map.json", doorbell=lambda: rings.append(1) or True)
    assert link.map == DEFAULT_MAP
    assert link.move("C4", 127) == "Bas Bus"
    link.move("C4", 0)                                   # only the latest value is sent
    assert link.flush()
    data = json.loads((tmp_path / "mb" / "faders-in.json").read_text(encoding="utf-8"))
    assert data["moves"] == {"Bas Bus": 0.0} and rings == [1]
    assert not link.flush()                              # nothing new
    seq = data["seq"]
    link.move("C5", 127)
    link.flush()
    assert json.loads((tmp_path / "mb" / "faders-in.json").read_text(encoding="utf-8"))["seq"] == seq + 1


def test_c54_then_a_fader_takes_the_selected_channel(tmp_path):
    mb = tmp_path / "mb"
    mb.mkdir()
    link = FaderLink(mailbox=mb, map_path=tmp_path / "map.json", doorbell=lambda: True)
    (mb / "faders-out.json").write_text(json.dumps({"selected": "FX 1", "channels": ["FX 1", "Main"]}), encoding="utf-8")
    link.arm(now=100.0)
    assert link.flush()                                  # rings so the bridge reports the selection
    assert link.move("C2", 64, now=105.0) == "FX 1"
    assert load_map(tmp_path / "map.json")["C2"] == "FX 1"
    assert link.move("C3", 64, now=106.0) == DEFAULT_MAP["C3"]   # disarmed after one fader
    link.arm(now=200.0)
    assert link.move("C3", 64, now=211.0) == DEFAULT_MAP["C3"]   # too late
    assert link.state(now=211.0)["channels"] == ["FX 1", "Main"]


def test_assign_from_plugin_and_clear(tmp_path):
    link = FaderLink(mailbox=tmp_path / "mb", map_path=tmp_path / "map.json", doorbell=lambda: True)
    assert link.assign("C8", "Main")
    assert link.assign("C7", None)
    assert not link.assign("C1", "Main")                 # C1 and C9 stay on the surface
    m = load_map(tmp_path / "map.json")
    assert m["C8"] == "Main" and "C7" not in m
    assert link.move("C7", 50) is None
    assert not link.flush()
