from pedal_router import (CONTROL, KNOB_CC, MODE_CC, PAN_KNOB_CC, PLAY, PedalMapper)


def test_pedal_modes_and_una_corda():
    m = PedalMapper()
    assert m.transform([0x90, 60, 1]) == [bytes([0x90, 60, 1])]
    assert m.transform([0xB0, 64, 127]) == [bytes([0xB0, 64, 127])]
    assert m.transform([0xC0, 3]) == [bytes([0xB0, 64, 0]), bytes([0xB0, 66, 127])]
    assert m.mode == "sostenuto"
    assert m.transform([0xB0, 64, 0]) == [bytes([0xB0, 66, 0])]
    assert m.transform([0xC0, 3]) == []           # pedal up: nothing to move
    assert m.mode == "sustain"                   # second press returns to sustain
    assert m.transform([0xC0, 4]) == [bytes([0xB0, 67, 127])]
    assert m.transform([0xC0, 4]) == [bytes([0xB0, 67, 0])]
    assert m.transform([0xC0, 2]) == []
    assert set(MODE_CC) == {"sustain", "sostenuto"}


def test_celeste_gone_c60_goes_to_surface():
    m = PedalMapper()
    m.transform([0xB0, 64, 127])
    assert m.route([0xC0, 16]) == [(CONTROL, bytes([0xC0, 16]))]
    assert m.mode == "sustain"
    assert m.route([0xB0, 64, 0]) == []            # soft release ramp instead
    assert m.take_ramps()[0][2][-1] == 0


def test_playing_goes_to_play_port():
    m = PedalMapper()
    for msg in ([0x90, 60, 40], [0x80, 60, 0], [0xE0, 0, 64], [0xB0, 1, 50], [0xB0, 64, 127]):
        assert m.route(msg) == [(PLAY, bytes(msg))]
    assert m.route([0xC0, 4]) == [(PLAY, bytes([0xB0, 67, 127]))]


def test_all_23_sound_knobs_reach_instruments_on_unique_ccs():
    m = PedalMapper()
    out = []
    for raw in list(PAN_KNOB_CC) + list(KNOB_CC):
        (dest, pkt), = m.route([0xB0, raw, 33])
        assert dest == PLAY
        out.append(pkt[1])
    (d1, p1), = m.route([0xD0, 20]); (d2, p2), = m.route([0xB0, 6, 20])
    assert d1 == d2 == PLAY
    out += [p1[1], p2[1]]
    assert len(out) == len(set(out)) == 23   # B17 is the half-pedal knob since 13.11
    assert m.route([0xB0, 100, 0]) == [] and m.route([0xB0, 101, 0]) == []


def test_mixer_and_transport_go_to_control_only():
    m = PedalMapper()
    for cc in (83, 22, 23, 24, 25, 26):
        assert m.route([0xB0, cc, 100]) == [(CONTROL, bytes([0xB0, cc, 100]))], cc
    for cc in (73, 72, 91, 93, 74, 71, 5, 84):          # faders: scaled, still control only
        assert [d for d, _ in m.route([0xB0, cc, 100])] == [CONTROL], cc
    for pc in (0, 1, 5, 6, 7, 8) + tuple(range(12, 17)):
        assert m.route([0xC0, pc]) == [(CONTROL, bytes([0xC0, pc]))], pc


def test_no_pan_or_program_change_reaches_instruments_or_mixer_pan():
    m = PedalMapper()
    for raw in PAN_KNOB_CC:
        (dest, pkt), = m.route([0xB0, raw, 64])
        assert pkt[1] not in (10, 2, 12, 13, 75, 76, 92, 95)
    surface_ccs = {73, 72, 91, 93, 74, 71, 5, 84, 83, 10, 2, 12, 13, 75, 76, 92, 95,
                   102} | set(range(22, 44))
    assert not (set(PAN_KNOB_CC.values()) & surface_ccs)
    for pc in range(128):
        for dest, pkt in m.route([0xC0, pc]):
            assert not (dest == PLAY and pkt[0] & 0xF0 == 0xC0)


def test_disconnect_releases_everything():
    m = PedalMapper()
    m.transform([0xC1, 4]); m.transform([0xB1, 64, 127]); m.transform([0x91, 61, 80])
    assert m.release_all() == [bytes([0xB1, 64, 0]), bytes([0xB1, 67, 0]), bytes([0x81, 61, 0])]


def test_c9_cc7_drives_main_fader_and_never_reaches_instruments():
    m = PedalMapper()
    assert m.route([0xB0, 7, 126]) == [(CONTROL, bytes([0xB0, 83, 127]))]


# --- soft sustain release -----------------------------------------------------
from pedal_router import ramp_values


def test_ramp_falls_to_zero():
    v = ramp_values(127)
    assert v[-1] == 0 and v == sorted(v, reverse=True) and len(v) <= 8 and v[0] < 127
    assert ramp_values(1) == [0] or ramp_values(1)[-1] == 0


def test_release_in_sustain_schedules_ramp_not_instant_zero():
    m = PedalMapper()
    assert m.route([0xB0, 64, 127]) == [(PLAY, bytes([0xB0, 64, 127]))]
    assert m.route([0xB0, 64, 0]) == []
    (ch, cc, values, gen), = m.take_ramps()
    assert (ch, cc, values[-1]) == (0, 64, 0)
    assert m.ramp_step_done(0, gen, False)


def test_repress_cancels_ramp():
    m = PedalMapper()
    m.route([0xB0, 64, 127]); m.route([0xB0, 64, 0])
    (_, _, _, gen), = m.take_ramps()
    assert m.route([0xB0, 64, 127]) == [(PLAY, bytes([0xB0, 64, 127]))]
    assert not m.ramp_step_done(0, gen, False)


def test_release_off_and_sostenuto_are_instant():
    m = PedalMapper(); m.release_ms = 0
    m.route([0xB0, 64, 127])
    assert m.route([0xB0, 64, 0]) == [(PLAY, bytes([0xB0, 64, 0]))]
    m = PedalMapper()
    m.route([0xC0, 3]); m.route([0xB0, 64, 127])
    assert m.route([0xB0, 64, 0]) == [(PLAY, bytes([0xB0, 66, 0]))]
    assert m.take_ramps() == []


def test_disconnect_or_mode_switch_mid_ramp_sends_zero():
    m = PedalMapper()
    m.route([0xB0, 64, 127]); m.route([0xB0, 64, 0]); m.take_ramps()
    assert m.release_all() == [bytes([0xB0, 64, 0])]
    m = PedalMapper()
    m.route([0xB0, 64, 127]); m.route([0xB0, 64, 0]); m.take_ramps()
    assert m.route([0xC0, 3]) == [(PLAY, bytes([0xB0, 64, 0]))]


# --- velocity calibration -------------------------------------------------------
import json
from pathlib import Path
from pedal_router import load_velocity_map


def _map():
    white = [0] + [min(127, v + 1) for v in range(1, 128)]
    black = [0] + [15] * 39 + list(range(20, 108))
    return white, black


def test_velocity_map_applies_by_key_colour():
    m = PedalMapper(); m.velocity_map = _map()
    assert m.route([0x90, 60, 1]) == [(PLAY, bytes([0x90, 60, 2]))]      # C white
    assert m.route([0x90, 66, 1]) == [(PLAY, bytes([0x90, 66, 15]))]     # F# black
    assert m.route([0x90, 66, 40]) == [(PLAY, bytes([0x90, 66, 20]))]
    assert m.route([0x90, 66, 0]) == [(PLAY, bytes([0x90, 66, 0]))]      # release untouched
    assert m.route([0x80, 60, 0]) == [(PLAY, bytes([0x80, 60, 0]))]


def test_no_map_means_untouched():
    m = PedalMapper()
    assert m.route([0x90, 66, 1]) == [(PLAY, bytes([0x90, 66, 1]))]


def test_load_velocity_map_validates(tmp_path):
    p = tmp_path / "m.json"
    w, b = _map()
    p.write_text(json.dumps({"white": w, "black": b}))
    assert load_velocity_map(p) == (w, b)
    p.write_text(json.dumps({"white": w[:10], "black": b}))
    assert load_velocity_map(p) is None
    p.write_text("not json")
    assert load_velocity_map(p) is None
    assert load_velocity_map(tmp_path / "missing.json") is None


def test_real_calibration_file_is_valid_and_monotone():
    w, b = load_velocity_map(Path("/tmp/claude-0/velocity-map.json"))
    assert all(w[i] <= w[i + 1] for i in range(1, 127))
    assert all(b[i] <= b[i + 1] for i in range(1, 127))
    assert w[1] >= 6 and b[1] >= 15


# --- context-aware "1" ---------------------------------------------------------
from pedal_router import ONES_CAP
ONES_FLOOR = 10


def _flat_map():
    t = [0, 10] + list(range(2, 128))      # lone "1" -> ppp 10, rest identity
    return t, list(t)


def test_one_after_pause_is_ppp():
    m = PedalMapper(); m.velocity_map = _flat_map()
    assert m.route([0x90, 60, 1], now=100.0) == [(PLAY, bytes([0x90, 60, ONES_FLOOR]))]


def test_one_inside_mp_phrase_is_one_step_softer():
    m = PedalMapper(); m.velocity_map = _flat_map()
    for i in range(6):
        m.route([0x90, 60 + i, 57], now=10.0 + i * 0.3)
    (_, pkt), = m.route([0x90, 66, 1], now=12.0)
    assert pkt[2] == 41                     # 57 - 16


def test_one_capped_in_loud_phrase_and_reset_after_silence():
    m = PedalMapper(); m.velocity_map = _flat_map()
    for i in range(6):
        m.route([0x90, 60, 110], now=1.0 + i * 0.2)
    (_, pkt), = m.route([0x90, 62, 1], now=2.5)
    assert pkt[2] == ONES_CAP
    (_, pkt), = m.route([0x90, 62, 1], now=10.0)   # long pause
    assert pkt[2] == ONES_FLOOR


def test_ones_do_not_drag_phrase_level_and_mode_off_gives_ppp():
    m = PedalMapper(); m.velocity_map = _flat_map()
    m.route([0x90, 60, 80], now=1.0)
    m.route([0x90, 61, 1], now=1.2); m.route([0x90, 61, 1], now=1.4)
    assert round(m.phrase_level[0]) == 80
    m.ones_context = False
    (_, pkt), = m.route([0x90, 61, 1], now=1.6)
    assert pkt[2] == ONES_FLOOR             # mode "ppp": always the map's value


# --- input port matching (USB port change, 31.10) ------------------------------
from pedal_router import find_input


def test_find_input_variants():
    assert find_input(["Keystation Pro 88"]) == 0
    assert find_input(["Microsoft GS", "2- Keystation Pro 88"]) == 1
    assert find_input(["MIDIIN2 (Keystation Pro 88)", "Keystation Pro 88 1"]) == 1
    assert find_input(["MIDIIN2 (Keystation Pro 88)", "keystation pro 88"]) == 1
    assert find_input(["Keystation Pedal Modes", "Keystation Control", "MIDIIN3 (Keystation Pro 88)"]) is None
    assert find_input([]) is None


# --- Listen Bus key disabled: C52 button does it now (31.10) -----------------------
def test_c8_plays_normally_again():
    m = PedalMapper()
    assert m.route([0x90, 108, 90])[0][0] == PLAY
    assert m.route([0xC0, 8]) == [(CONTROL, bytes([0xC0, 8]))]


# --- faders: top = exactly 0 dB (31.10) -----------------------------------------
def test_fader_top_is_zero_db_program_change():
    m = PedalMapper()
    assert m.route([0xB0, 73, 127]) == [(CONTROL, bytes([0xC0, 20]))]   # C1
    assert m.route([0xB0, 84, 127]) == [(CONTROL, bytes([0xC0, 27]))]   # C8
    assert m.route([0xB0, 7, 127]) == [(CONTROL, bytes([0xC0, 28]))]    # C9 Main
    assert m.route([0xB0, 73, 126]) == [(CONTROL, bytes([0xB0, 73, 127]))]
    assert m.route([0xB0, 7, 63]) == [(CONTROL, bytes([0xB0, 83, 64]))]
    assert m.route([0xB0, 73, 0]) == [(CONTROL, bytes([0xB0, 73, 0]))]


# --- touch modes on C53/C54/C55 (02.11) -------------------------------------------
def test_touch_buttons_switch_maps_and_are_consumed():
    m = PedalMapper()
    light = ([0, 10] + list(range(2, 128)), [0, 10] + list(range(2, 128)))
    heavy = ([0, 10] + [max(2, v - 20) for v in range(2, 128)], [0, 10] + [max(2, v - 20) for v in range(2, 128)])
    m.touch_maps = {"light": light, "heavy": heavy}
    m.velocity_map = light
    m.touch_mode = "light"
    assert m.route([0xC0, 9]) == []                  # C53 steps: light -> heavy (acoustic has no map, skipped)
    assert m.touch_mode == "heavy" and m.touch_dirty
    assert m.route([0x90, 60, 80], now=1.0) == [(PLAY, bytes([0x90, 60, 60]))]
    assert m.route([0xC0, 9]) == []                  # -> back to light
    assert m.route([0x90, 62, 80], now=1.1) == [(PLAY, bytes([0x90, 62, 80]))]
    assert m.route([0xC0, 10]) == [] and m.route([0xC0, 11]) == []   # C54, C55 free: consumed, no change
    assert m.touch_mode == "light"
    assert m.route([0xC0, 8]) == [(CONTROL, bytes([0xC0, 8]))]   # C52 Listen Bus untouched


# --- half pedal and debounce (13.11) -----------------------------------------------
from pedal_router import HALF_PEDAL_KNOB_CC, load_options


def test_half_pedal_sends_depth_and_ramps_from_it():
    m = PedalMapper(); m.set_half(True, 70)
    assert m.route([0xB0, 64, 127]) == [(PLAY, bytes([0xB0, 64, 70]))]
    assert m.route([0xB0, 64, 0]) == []
    (_, cc, values, _), = m.take_ramps()
    assert cc == 64 and values[0] < 70 and values[-1] == 0


def test_half_pedal_off_is_full_and_sostenuto_untouched():
    m = PedalMapper(); m.set_half(False, 70)
    assert m.route([0xB0, 64, 127]) == [(PLAY, bytes([0xB0, 64, 127]))]
    m = PedalMapper(); m.set_half(True, 70); m.route([0xC0, 3])
    assert m.route([0xB0, 64, 127]) == [(PLAY, bytes([0xB0, 66, 127]))]


def test_b17_knob_moves_depth_live_and_is_consumed():
    m = PedalMapper(); m.set_half(True)
    m.route([0xB0, 64, 127])
    assert m.route([0xB0, HALF_PEDAL_KNOB_CC, 50]) == [(PLAY, bytes([0xB0, 64, 50]))]
    assert m.half_depth == 50 and m.half_knob == 50
    m.set_half(False)
    assert m.route([0xB0, HALF_PEDAL_KNOB_CC, 90]) == []      # pedal is full now, nothing to change
    assert m.half_depth == 90


def test_switching_half_pedal_while_held_changes_level_at_once():
    m = PedalMapper(); m.route([0xB0, 64, 127])
    assert m.set_half(True, 60) == [bytes([0xB0, 64, 60])]
    assert m.set_half(False) == [bytes([0xB0, 64, 127])]


def test_mode_switch_keeps_half_pedal_level_right():
    m = PedalMapper(); m.set_half(True, 60); m.route([0xC0, 3])
    m.route([0xB0, 64, 127])
    assert m.route([0xC0, 2]) == [(PLAY, bytes([0xB0, 66, 0])), (PLAY, bytes([0xB0, 64, 60]))]


def test_debounce_drops_bounce_and_keeps_note():
    m = PedalMapper(); m.set_debounce(True)
    m.route([0x90, 60, 80])
    assert m.route([0x80, 60, 0]) == []
    assert m.last_event == "deferred"
    (ch, note, gen), = m.take_offs()
    assert m.route([0x90, 60, 30]) == [] and m.bounces == 1 and m.last_event == "bounce"
    assert m.flush_off(ch, note, gen) is None and 60 in m.active_notes[0]


def test_debounce_sends_off_when_no_bounce():
    m = PedalMapper(); m.set_debounce(True)
    m.route([0x90, 60, 80]); m.route([0x90, 60, 0])
    (ch, note, gen), = m.take_offs()
    assert m.flush_off(ch, note, gen) == bytes([0x90, 60, 0])
    assert 60 not in m.active_notes[0]
    assert m.route([0x90, 60, 70]) == [(PLAY, bytes([0x90, 60, 70]))]


def test_debounce_off_is_instant_and_turning_off_flushes():
    m = PedalMapper()
    m.route([0x90, 60, 80])
    assert m.route([0x80, 60, 0]) == [(PLAY, bytes([0x80, 60, 0]))]
    m.set_debounce(True); m.route([0x90, 61, 80]); m.route([0x80, 61, 0])
    assert m.set_debounce(False) == [bytes([0x80, 61, 0])]
    m = PedalMapper(); m.set_debounce(True); m.route([0x90, 62, 80]); m.route([0x80, 62, 0])
    assert bytes([0x80, 62, 0]) in m.release_all() and not m.pending_offs


def test_options_load_and_validate(tmp_path):
    f = tmp_path / "o.json"
    f.write_text('{"half_pedal": true, "half_depth": 300, "debounce": "yes"}')
    m = PedalMapper(); m.load(load_options(f))
    assert m.half_pedal and m.half_depth == 127 and not m.debounce
    assert load_options(tmp_path / "missing.json") == {}


# --- 14.11: release length from the plugin ------------------------------------
import pedal_router


def test_set_release_ms_saves_and_clamps(tmp_path, monkeypatch):
    monkeypatch.setattr(pedal_router, "RELEASE_FILE", tmp_path / "release-ms")
    assert pedal_router.release_ms() == pedal_router.DEFAULT_RELEASE_MS     # no file: 120
    assert pedal_router.set_release_ms(250) == 250
    assert pedal_router.release_ms() == 250
    assert pedal_router.set_release_ms(60.4) == 60
    assert pedal_router.set_release_ms(5000) == 1000
    assert pedal_router.set_release_ms(-3) == 0
    assert pedal_router.set_release_ms("250") is None and pedal_router.release_ms() == 0
    assert pedal_router.set_release_ms(True) is None


def test_longer_release_means_the_same_ramp_spread_over_more_time():
    m = PedalMapper(); m.release_ms = 250
    m.route([0xB0, 64, 127])
    assert m.route([0xB0, 64, 0]) == []
    ramps = m.take_ramps()
    assert len(ramps) == 1 and ramps[0][2][-1] == 0


# --- 15.11: "moje" (own curve + contextual denoising) -----------------------------
def _moje_mapper():
    m = PedalMapper()
    ident = list(range(128))
    m.touch_maps = {"light": (ident, ident), "moje": (ident, ident)}
    assert m.select_touch("moje") and m.touch_mode == "moje"
    return m


def test_moje_pulls_small_deviations_toward_the_phrase():
    m = _moje_mapper()
    outs = [m.route([0x90, 60, v], now=t)[0][1][2] for t, v in ((0.0, 90), (0.2, 100), (0.4, 84))]
    assert outs[0] == 90                       # first note of a phrase: as played
    assert outs[1] == 96                       # +10 over the level 90 -> +6.5 (96.5 rounds to even)
    assert 84 < outs[2] < 93                   # pulled up toward the level


def test_moje_keeps_accents_and_resets_after_a_pause():
    m = _moje_mapper()
    m.route([0x90, 60, 80], now=0.0)
    accent = m.route([0x90, 62, 120], now=0.2)[0][1][2]
    assert accent == 116                        # +40 -> keeps all but 0.35 * 12
    after_pause = m.route([0x90, 64, 50], now=5.0)[0][1][2]
    assert after_pause == 50                    # a new phrase


def test_other_touch_modes_are_not_denoised():
    m = _moje_mapper()
    m.select_touch("light")
    m.route([0x90, 60, 90], now=0.0)
    assert m.route([0x90, 62, 100], now=0.2)[0][1][2] == 100


def test_unknown_touch_is_refused():
    m = PedalMapper()
    assert not m.select_touch("moje")


def test_one_button_steps_through_touch_modes():
    m = PedalMapper()
    ident = list(range(128))
    m.touch_maps = {k: (ident, ident) for k in ("light", "acoustic", "heavy", "moje")}
    m.select_touch("light")
    seen = []
    for _ in range(5):
        assert m.route([0xC0, 9]) == []
        seen.append(m.touch_mode)
    assert seen == ["acoustic", "heavy", "moje", "light", "acoustic"]
    assert m.route([0xC0, 10]) == [] and m.route([0xC0, 11]) == [] and m.touch_mode == "acoustic"
    del m.touch_maps["heavy"]                   # a missing preset file is skipped
    m.route([0xC0, 9]); assert m.touch_mode == "moje"
