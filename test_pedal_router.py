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
    w, b = load_velocity_map(Path(__file__).parent / "velocity-map.json")
    assert all(w[i] <= w[i + 1] for i in range(1, 127))
    assert all(b[i] <= b[i + 1] for i in range(1, 127))
    assert w[1] >= 6 and b[1] >= 6         # never inaudible (map retuned since 28.10: black 1 -> 10)


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


# --- 15.11: moje v2 (one curve, censored 1s, a black 1 after a loud chord) ------------------
def _moje2():
    m = PedalMapper()
    white = list(range(128)); white[1] = 9
    black = list(range(128)); black[1] = 14
    m.touch_maps = {"light": (list(range(128)), list(range(128))), "moje": (white, black)}
    m.select_touch("moje")
    return m


def test_moje2_ones_are_censored_soft_notes_not_the_phrase_rule():
    m = _moje2()
    m.route([0x90, 60, 100], now=0.0)
    assert m.route([0x90, 62, 1], now=0.3)[0][1][2] == 9      # white: just below the floor, whatever the phrase
    assert m.route([0x90, 61, 1], now=0.6)[0][1][2] == 14     # black alone: the hole mean


def test_moje2_black_one_right_after_a_loud_chord_is_mostly_the_chord():
    m = _moje2()
    m.route([0x90, 60, 100], now=0.0)
    m.route([0x90, 64, 100], now=0.005)
    assert m.route([0x90, 66, 1], now=0.01)[0][1][2] == round(0.6 * 100 + 0.4 * 14)
    m.route([0x90, 72, 60], now=1.0)                          # quiet chord: a real soft note
    assert m.route([0x90, 73, 1], now=1.01)[0][1][2] == 14
    assert m.route([0x90, 75, 1], now=1.2)[0][1][2] == 14     # too late for the chord


def test_moje2_measured_black_stays_measured_under_denoise():
    m = _moje2()
    m.route([0x90, 60, 20], now=0.0)
    m.route([0x90, 62, 20], now=0.2)
    assert m.route([0x90, 61, 41], now=0.4)[0][1][2] >= 41    # pulled toward 20, but a black reading is >= 41


def test_moje2_real_map_is_monotone_and_one_curve():
    import json
    d = json.loads((Path(__file__).parent / "velocity-map.moje.json").read_text(encoding="utf-8"))
    w, b = d["white"], d["black"]
    assert all(x <= y for x, y in zip(w[1:], w[2:])) and all(x <= y for x, y in zip(b[1:], b[2:]))
    assert w[41:] == b[41:] and w[127] == 127
    assert w[1] < w[2] and b[1] < b[41] and w[1] < b[1]


# --- 15.11: moje3 (v3e) ---------------------------------------------------------------
def _moje3():
    m = PedalMapper()
    ident = list(range(128))
    m.touch_maps = {"light": (ident, ident), "moje3": (ident, ident)}
    assert m.select_touch("moje3")
    return m


def test_moje3_in_forte_a_small_deliberate_change_passes():
    m3, m2 = _moje3(), _moje2()
    m2.touch_maps["moje"] = (list(range(128)), list(range(128))); m2.select_touch("moje")
    for mm in (m3, m2):
        mm.route([0x90, 72, 110], now=0.0)
    v3 = m3.route([0x90, 74, 120], now=0.2)[0][1][2]
    v2 = m2.route([0x90, 74, 120], now=0.2)[0][1][2]
    assert v3 > v2                       # +10 in forte: v2 treats it as noise (6.5), v3 keeps more
    assert v3 == round(110 + 10 - 0.35 * 2 * 2.6)


def test_moje3_keeps_mezzo_accents_like_v2():
    m3 = _moje3()
    m3.route([0x90, 72, 60], now=0.0)
    assert m3.route([0x90, 74, 100], now=0.2)[0][1][2] == round(60 + 40 - 0.35 * 12)


def test_moje3_hands_have_their_own_level():
    m3 = _moje3()
    m3.route([0x90, 40, 70], now=0.0)            # left hand, soft
    m3.route([0x90, 76, 95], now=0.01)           # right hand melody
    m3.route([0x90, 43, 70], now=0.3)
    melody = m3.route([0x90, 77, 95], now=0.31)[0][1][2]
    assert melody == 95                           # not pulled toward the left hand


def test_moje3_map_has_no_ceiling_and_is_monotone():
    import json
    d = json.loads((Path(__file__).parent / "velocity-map.moje3.json").read_text(encoding="utf-8"))
    w = d["white"]
    assert all(x <= y for x, y in zip(w[1:], w[2:])) and all(w[i] >= i for i in range(110, 128)) and w[1] == 9 and d["black"][1] == 14


# --- 16.11: naturalna / szeroka (log key speed, S-shape) ------------------------------------------
def _nat(mode="naturalna"):
    import json
    m = PedalMapper()
    maps = {}
    for k in ("moje3", "naturalna", "szeroka"):
        d = json.loads((Path(__file__).parent / f"velocity-map.{k}.json").read_text(encoding="utf-8"))
        maps[k] = (d["white"], d["black"])
    m.touch_maps = maps
    assert m.select_touch(mode)
    return m


def test_naturalna_and_szeroka_maps_are_one_monotone_curve_reaching_127():
    import json
    for k in ("naturalna", "szeroka"):
        d = json.loads((Path(__file__).parent / f"velocity-map.{k}.json").read_text(encoding="utf-8"))
        w, b = d["white"], d["black"]
        assert len(w) == len(b) == 128
        assert all(x <= y for x, y in zip(w[1:], w[2:])) and all(x <= y for x, y in zip(b[1:], b[2:]))
        assert w[41:] == b[41:]                        # one sensor scale for both colours
        assert w[2] == 10 and w[1] == 9                # floor; a white 1 is just below it
        assert w[118] == 127 or w[117] == 127          # fff is reachable (his p99 is raw 117-118)
        assert w[1] < b[1] < b[41]                     # black 1 = inside the hole, under the softest measured black
        assert b[41] - b[1] <= 8                       # the hole is narrow on this scale (~2 dB)


def test_button_steps_only_between_naturalna_and_szeroka():
    m = _nat("moje3")
    seen = []
    for _ in range(4):
        assert m.route([0xC0, 9]) == []
        seen.append(m.touch_mode)
    assert seen == ["naturalna", "szeroka", "naturalna", "szeroka"]
    assert m.select_touch("moje3")                     # older modes stay selectable from the plugin / panel


def test_naturalna_uses_the_moje3_input_stage():
    import json
    d = json.loads((Path(__file__).parent / "velocity-map.naturalna.json").read_text(encoding="utf-8"))
    ident = list(range(128))
    m3 = PedalMapper(); m3.touch_maps = {"moje3": (ident, ident)}; m3.select_touch("moje3")
    mn = PedalMapper(); mn.touch_maps = {"naturalna": (ident, ident)}; mn.select_touch("naturalna")
    seq = ((0.0, 40, 70), (0.01, 76, 95), (0.3, 43, 72), (0.31, 77, 101), (0.6, 79, 112), (2.5, 60, 50))
    for t, note, v in seq:
        assert m3.route([0x90, note, v], now=t) == mn.route([0x90, note, v], now=t)
    # with the real map: white 1 just below the floor, black 1 in the hole, black after a loud chord mostly the chord
    m = _nat()
    m.route([0x90, 60, 100], now=0.0)
    assert m.route([0x90, 62, 1], now=0.3)[0][1][2] == d["white"][1]
    assert m.route([0x90, 61, 1], now=0.6)[0][1][2] == d["black"][1]
    m.route([0x90, 72, 100], now=1.0); m.route([0x90, 76, 100], now=1.005)
    assert m.route([0x90, 78, 1], now=1.01)[0][1][2] == round(0.6 * d["white"][100] + 0.4 * d["black"][1])


def test_naturalna_follows_log_key_speed():
    import json, math
    d = json.loads((Path(__file__).parent / "velocity-map.naturalna.json").read_text(encoding="utf-8"))
    w = d["white"]
    # equal steps of key speed (ratio) give growing raw steps toward the soft end: raw 2..40 is a narrow slice
    assert w[40] - w[2] < w[110] - w[100]
    assert 70 <= w[100] <= 90 and 100 <= w[110] <= 120 and 15 <= w[41] <= 25


# --- 15.11: SysEx backup ------------------------------------------------------------------
from pedal_router import SYSEX_PROBES, SysexLog  # noqa: E402


def test_sysex_log_one_file_per_burst(tmp_path):
    log = SysexLog(tmp_path)
    a = log.feed([0xF0, 0x00, 0x20, 0x08, 0xF7], 1000.0)
    b = log.feed([0xF0, 0x01, 0xF7], 1001.0)
    c = log.feed([0xF0, 0x02, 0xF7], 1010.0)
    assert a == b and c != a
    assert a.read_bytes() == bytes([0xF0, 0x00, 0x20, 0x08, 0xF7, 0xF0, 0x01, 0xF7])


def test_sysex_probes_are_read_only_requests():
    assert set(SYSEX_PROBES) == {"identity", "dump"}
    for msg in SYSEX_PROBES.values():
        assert msg[0] == 0xF0 and msg[-1] == 0xF7 and all(b < 0x80 for b in msg[1:-1])
    assert SYSEX_PROBES["identity"] == bytes.fromhex("F07E7F0601F7")


# --- 15.11: photo view of the plugin -------------------------------------------------------
from pedal_router import button_label, control_of  # noqa: E402


def test_control_labels_cover_every_knob_and_fader():
    assert control_of([0xB0, 10, 64]) == ("B10", 64)
    assert control_of([0xB0, 95, 80]) == ("B17", 80)
    assert control_of([0xB0, 42, 1]) == ("B18", 1)
    assert control_of([0xB0, 81, 127]) == ("B31", 127)
    assert control_of([0xD0, 33]) == ("B32", 33)
    assert control_of([0xB0, 6, 99]) == ("B33", 99)
    assert control_of([0xB0, 73, 100]) == ("C1", 100)
    assert control_of([0xB0, 7, 127]) == ("C9", 127)
    assert control_of([0xB0, 64, 127]) is None and control_of([0x90, 60, 100]) is None
    labels = {control_of([0xB0, cc, 0])[0] for cc in range(128) if control_of([0xB0, cc, 0])} | {"B32"}
    assert labels == {f"B{i}" for i in range(10, 34)} | {f"C{i}" for i in range(1, 10)}


def test_button_labels():
    assert [button_label(p) for p in (0, 2, 4, 7, 8, 9, 16)] == ["B44", "B46", "B48", "B51", "C52", "C53", "C60"]
    assert button_label(17) is None


def test_load_controls_keeps_only_valid_positions(tmp_path):
    from pedal_router import load_controls
    f = tmp_path / "controls.json"
    f.write_text('{"B10": 64, "C9": 127, "B32": 5, "X1": 3, "B11": 300, "B12": "a"}', encoding="utf-8")
    assert load_controls(f) == {"B10": 64, "C9": 127, "B32": 5}
    assert load_controls(tmp_path / "missing.json") == {}


def test_faders_c2_c8_and_c54_go_to_the_fader_link():
    class Link:
        def __init__(self):
            self.moves, self.armed = [], 0

        def move(self, fader, value):
            self.moves.append((fader, value))

        def arm(self):
            self.armed += 1

    m = PedalMapper()
    m.fader_link = link = Link()
    assert m.route([0xB0, 72, 100]) == []                       # C2: to the bridge, not the surface
    assert m.route([0xB0, 84, 5]) == []                         # C8
    assert link.moves == [("C2", 100), ("C8", 5)]
    assert m.route([0xB0, 73, 100])[0][0] == CONTROL            # C1 stays on the surface
    assert m.route([0xB0, 7, 64])[0][0] == CONTROL              # C9 (Main) too
    assert m.route([0xC0, 10]) == [] and link.armed == 1        # C54 = assign
    assert m.route([0xC0, 11]) == [] and link.armed == 1        # C55 still free
    plain = PedalMapper()                                       # no link: faders as before
    assert plain.route([0xB0, 72, 100])[0][0] == CONTROL
