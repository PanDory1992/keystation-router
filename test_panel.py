"""Panel Keystation helpers (python3 -m pytest test_panel.py)."""
import json
import time

import panel_sterowania as ps


def test_router_state(tmp_path):
    assert ps.router_state(tmp_path) == {"fresh": False}
    (tmp_path / "live.json").write_text(json.dumps({"connected": True, "touch": "moje3", "updated": 100.0}))
    r = ps.router_state(tmp_path, now=105.0)
    assert r["fresh"] and r["connected"] and r["touch"] == "moje3"
    assert not ps.router_state(tmp_path, now=200.0)["fresh"]


def test_command_and_trigger(tmp_path):
    f = ps.write_command({"touch": "light"}, tmp_path)
    d = json.loads(f.read_text())
    assert d["set"] == {"touch": "light"} and d["v"] == 1 and not (tmp_path / "live-cmd.json.tmp").exists()
    assert ps.trigger("restart-trener", tmp_path).exists()


def test_running_scripts():
    lines = ['"C:\\Python312\\pythonw.exe" C:\\x\\Pedal_Router.py', "pythonw.exe C:\\x\\trener\\trener_serwer.py --no-idle-exit", ""]
    assert ps.running_scripts(lines) == {"router", "trener"}
