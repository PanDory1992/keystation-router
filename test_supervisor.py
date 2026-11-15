"""Trigger files of keystation_supervisor.py (python3 -m pytest test_supervisor.py)."""
import keystation_supervisor as ks


def test_triggers_are_taken_once(tmp_path):
    (tmp_path / "restart-trener").write_text("")
    (tmp_path / "restart-nadzorca").write_text("")
    (tmp_path / "restart-router").write_text("")          # the router's own: not ours
    assert ks.take_triggers(tmp_path) == {"trener", "supervisor"}
    assert ks.take_triggers(tmp_path) == set()
    assert (tmp_path / "restart-router").exists()
    assert set(ks.TRIGGERS.values()) - {"supervisor"} <= set(ks.SERVICES)
