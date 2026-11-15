// ---- src/00_core.js
// ============================================================================
//  SPARTITO - a score view and editor for Live's MIDI clips.
//
//  This file is GENERATED: build/build.pl concatenates src/*.js in name order.
//  Edit the pieces in src/, never spartito.js itself.
//
//  The same file runs in four places, which is why it is written the way it is:
//
//    * in Max 8's js engine, as the brain ([js], which always runs) and as the
//      views ([jsui], which only run once they are drawn);
//    * under Windows Script Host (build/jstest.js), where the notation engine,
//      the editing model, the Live bridge and every exporter are tested against
//      fakes - and WSH speaks JScript, which is ES3. So: no forEach, no map,
//      no indexOf on arrays, no JSON, no Object.keys, no trailing commas;
//    * in a browser (build/preview.html), which is how the engraving is looked
//      at while it is being designed.
//
//  In Max every top-level function is also a message the object answers to,
//  and a function named like a built-in (box, refresh, patcher...) silently
//  replaces it. So the engine's functions all carry a module prefix:
//
//    cr_  core helpers        md_  the editing model     nt_  notation
//    gl_  glyphs              ly_  layout                dr_  drawing
//    ex_  exporters           lv_  the Live bridge       ui_  the editor
//
//  Time: the model keeps Live's own numbers - beats (quarter notes) as floats -
//  so a note nobody edited is written back exactly as it was read. Notation
//  works in TICKS, 48 to the quarter note: that divides by 16ths, 32nds, 64ths
//  and by eighth- and sixteenth-note triplets.
// ============================================================================

var TPQ = 48;
var WHOLE = 192;

function cr_mod(a, b) { var r = a % b; return r < 0 ? r + b : r; }
function cr_clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
function cr_round(v) { return Math.floor(v + 0.5); }
function cr_abs(v) { return v < 0 ? -v : v; }

function cr_has(arr, v) {
    for (var i = 0; i < arr.length; i++) if (arr[i] === v) return true;
    return false;
}

// Numeric sort that is stable - JScript's Array.sort is not guaranteed to be,
// and the order of simultaneous notes must not change between two engravings
// of the same model or the selection would flicker between chord members.
function cr_sortBy(arr, key) {
    var tmp = [], i;
    for (i = 0; i < arr.length; i++) tmp.push([key(arr[i]), i, arr[i]]);
    tmp.sort(function (a, b) {
        if (a[0] < b[0]) return -1;
        if (a[0] > b[0]) return 1;
        return a[1] - b[1];
    });
    var out = [];
    for (i = 0; i < tmp.length; i++) out.push(tmp[i][2]);
    return out;
}

function cr_uniqSorted(nums) {
    var s = nums.slice(0);
    s.sort(function (a, b) { return a - b; });
    var out = [];
    for (var i = 0; i < s.length; i++) if (i === 0 || s[i] !== s[i - 1]) out.push(s[i]);
    return out;
}

// a number as short text for SVG / PDF / Live: fixed decimals, no "-0"
function cr_num(v, dec) {
    if (dec === undefined) dec = 2;
    var s = v.toFixed(dec);
    if (s.indexOf(".") >= 0) {
        while (s.charAt(s.length - 1) === "0") s = s.substring(0, s.length - 1);
        if (s.charAt(s.length - 1) === ".") s = s.substring(0, s.length - 1);
    }
    if (s === "-0") s = "0";
    return s;
}

var cr_NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"];

// Live names middle C "C3"; notation programs and MusicXML call it C4. The
// device talks to a Live user, so what it SHOWS follows Live.
function cr_liveNoteName(p) {
    return cr_NOTE_NAMES[cr_mod(p, 12)] + (Math.floor(p / 12) - 2);
}

// ---- src/10_model.js
// ============================================================================
//  md_ - the editing model
//
//  The model is a LIST OF NOTES, exactly like the clip it mirrors - not a tree
//  of measures and voices. Every edit made on the score is an edit of that
//  list, the brain writes the list into the clip straight away, and the score
//  is engraved again from scratch. So the score can never show anything the
//  clip does not contain.
//
//  That includes the ornaments. A trill IS its notes in the clip (the main and
//  upper note alternating in 32nds) and an acciaccatura IS a 64th just before
//  its note: Live plays them, and the notation recognises them on the way back
//  and draws "tr" or a small slashed note instead.
//
//  note = { id, p (MIDI pitch), t (start, beats), d (length, beats),
//           v (velocity), m (muted 0/1), sp (spelling: 0 auto, 1 sharp,
//           -1 flat), sel (0/1), st (staff written on: -1 auto, 0, 1) }
// ============================================================================

function md_new() {
    return {
        notes: [], nextId: 1,
        num: 4, den: 4,
        lenBeats: 16,          // the clip's length; the score shows at least this
        name: "",
        undo: [], redo: [],
        version: 1,            // bumped on every change; views re-engrave on it
        editVersion: 1,        // bumped only when the NOTES change; the brain writes on it
        clipTag: ""            // which clip the notes came from
    };
}

// st: the staff a note was WRITTEN on (0 upper, 1 lower), or -1 to let the
// split point decide. A note entered on the treble staff below middle C stays
// on the treble staff, with ledger lines, instead of jumping to the bass staff.
function md_note(M, p, t, d, v, m, sp, st) {
    return { id: M.nextId++, p: p, t: t, d: d, v: v, m: m ? 1 : 0, sp: sp || 0, sel: 0,
             st: (st === undefined) ? -1 : st };
}

function md_copyNotes(ns) {
    var out = [];
    for (var i = 0; i < ns.length; i++) {
        var n = ns[i];
        out.push({ id: n.id, p: n.p, t: n.t, d: n.d, v: n.v, m: n.m, sp: n.sp, sel: n.sel, st: n.st });
    }
    return out;
}

function md_touch(M) { M.version++; }

// Call BEFORE changing anything. Undo keeps whole snapshots.
function md_snapshot(M) {
    M.undo.push({ notes: md_copyNotes(M.notes), lenBeats: M.lenBeats });
    if (M.undo.length > 200) M.undo.shift();
    M.redo = [];
}

function md_changed(M) { M.editVersion++; md_touch(M); }

function md_restore(M, s) {
    M.notes = md_copyNotes(s.notes);
    M.lenBeats = s.lenBeats;
    md_changed(M);
}

function md_undo(M) {
    if (!M.undo.length) return false;
    M.redo.push({ notes: md_copyNotes(M.notes), lenBeats: M.lenBeats });
    md_restore(M, M.undo.pop());
    return true;
}

function md_redo(M) {
    if (!M.redo.length) return false;
    M.undo.push({ notes: md_copyNotes(M.notes), lenBeats: M.lenBeats });
    md_restore(M, M.redo.pop());
    return true;
}

// A different clip: everything replaced, history cleared.
function md_load(M, list, num, den, lenBeats, name, tag) {
    M.notes = [];
    M.nextId = 1;
    for (var i = 0; i < list.length; i++) {
        var a = list[i];
        M.notes.push(md_note(M, a[0], a[1], a[2], a[3], a[4], 0));
    }
    M.num = num || 4; M.den = den || 4;
    M.lenBeats = lenBeats > 0 ? lenBeats : 4 * M.num * 4 / M.den;
    M.name = name || "";
    M.clipTag = tag || "";
    M.undo = []; M.redo = [];
    md_changed(M);
}

// The SAME clip, changed in Live. Notes that are still there keep their
// identity - their spelling, the staff they were written on, the selection -
// and only what really changed is new. First exact matches, then a note that
// kept its pitch and start (its length was dragged), then pitch and length
// (it was moved).
function md_sync(M, list, num, den, lenBeats, name) {
    var old = M.notes.slice(0), taken = [], out = [], i, j;
    // Matching by exact keys: a drum clip is thousands of notes of ONE pitch,
    // so even a per-pitch search is quadratic there. Times are compared at a
    // millionth of a beat, as the notes themselves are written.
    function r6(x) { return Math.round(x * 1e6); }
    var keyers = [
        function (p, t, d) { return p + "|" + r6(t) + "|" + r6(d); },
        function (p, t, d) { return p + "|" + r6(t); },
        function (p, t, d) { return p + "|d" + r6(d); }
    ];
    for (i = 0; i < old.length; i++) taken.push(false);
    var result = [];
    for (i = 0; i < list.length; i++) result.push(null);
    for (var k = 0; k < keyers.length; k++) {
        var buckets = {};
        for (j = 0; j < old.length; j++) {
            if (taken[j]) continue;
            var ko = keyers[k](old[j].p, old[j].t, old[j].d);
            if (!buckets[ko]) buckets[ko] = [];
            buckets[ko].push(j);
        }
        for (i = 0; i < list.length; i++) {
            if (result[i]) continue;
            var q = buckets[keyers[k](list[i][0], list[i][1], list[i][2])];
            while (q && q.length) {
                j = q.shift();
                if (!taken[j]) { taken[j] = true; result[i] = old[j]; break; }
            }
        }
    }
    for (i = 0; i < list.length; i++) {
        var a = list[i], n = result[i];
        if (n) { n.p = a[0]; n.t = a[1]; n.d = a[2]; n.v = a[3]; n.m = a[4] ? 1 : 0; }
        else n = md_note(M, a[0], a[1], a[2], a[3], a[4], 0);
        out.push(n);
    }
    M.notes = out;
    if (num) M.num = num;
    if (den) M.den = den;
    if (lenBeats > 0) M.lenBeats = lenBeats;
    if (name !== undefined) M.name = name;
    md_changed(M);
}

// A few bars of a model as a model of their own, starting at bar 1: what the
// strip's thumbnail and the live view of a recording engrave, so that neither
// ever pays for the whole score. A note sounding into the window is cut at
// its start. Read only - the notes are copies.
function md_window(M, fromBar, bars) {
    var W = md_new(), bar = M.num * 4 / M.den, a = fromBar * bar, e = a + bars * bar;
    W.num = M.num; W.den = M.den; W.name = M.name; W.lenBeats = bars * bar;
    W.version = M.version;
    for (var i = 0; i < M.notes.length; i++) {
        var n = M.notes[i];
        if (n.t >= e || n.t + n.d <= a) continue;
        var t = Math.max(n.t, a);
        var c = md_note(W, n.p, t - a, n.t + n.d - t, n.v, n.m, n.sp, n.st);
        c.sel = n.sel;
        W.notes.push(c);
    }
    return W;
}

function md_byId(M, id) {
    for (var i = 0; i < M.notes.length; i++) if (M.notes[i].id === id) return M.notes[i];
    return null;
}

function md_selected(M) {
    var out = [];
    for (var i = 0; i < M.notes.length; i++) if (M.notes[i].sel) out.push(M.notes[i]);
    return out;
}

function md_selectNone(M) {
    var any = false;
    for (var i = 0; i < M.notes.length; i++) { if (M.notes[i].sel) any = true; M.notes[i].sel = 0; }
    if (any) md_touch(M);
}

function md_selectIds(M, ids, additive) {
    for (var i = 0; i < M.notes.length; i++) {
        var n = M.notes[i];
        if (cr_has(ids, n.id)) n.sel = additive ? (n.sel ? 0 : 1) : 1;
        else if (!additive) n.sel = 0;
    }
    md_touch(M);
}

function md_selectAll(M) {
    for (var i = 0; i < M.notes.length; i++) M.notes[i].sel = 1;
    md_touch(M);
}

var md_EPS = 1e-6;

// Add a note the way a notation program does: a note already sitting at the
// same pitch and start is REPLACED, a same-pitch note sounding into the new
// one is shortened to end where it begins, and the new note stops where the
// next same-pitch note starts.
function md_add(M, p, t, d, v, sp, st) {
    var keep = [], i;
    for (i = 0; i < M.notes.length; i++) {
        var n = M.notes[i];
        if (n.p === p) {
            if (cr_abs(n.t - t) < md_EPS) continue;
            if (n.t < t && n.t + n.d > t + md_EPS) n.d = t - n.t;
            else if (n.t > t && n.t < t + d - md_EPS) d = n.t - t;
        }
        keep.push(n);
    }
    M.notes = keep;
    var nn = md_note(M, p, t, d, v, 0, sp, st);
    M.notes.push(nn);
    return nn;
}

// The flat, natural and sharp buttons SET the accidental: the note keeps its
// letter, so sharp twice on F is F#, not G.
function md_setAlter(M, notes, alter, key) {
    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        var s = nt_spell(n.p, key, n.sp);
        n.p = cr_clamp((s.oct + 1) * 12 + nt_LETTER_PC[s.letter] + alter, 0, 127);
        n.sp = alter;
    }
}

function md_deleteIds(M, ids) {
    var keep = [];
    for (var i = 0; i < M.notes.length; i++) if (!cr_has(ids, M.notes[i].id)) keep.push(M.notes[i]);
    var removed = M.notes.length - keep.length;
    M.notes = keep;
    return removed;
}

function md_deleteSelected(M) {
    var keep = [];
    for (var i = 0; i < M.notes.length; i++) if (!M.notes[i].sel) keep.push(M.notes[i]);
    var removed = M.notes.length - keep.length;
    M.notes = keep;
    return removed;
}

function md_transpose(M, notes, semis) {
    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        n.p = cr_clamp(n.p + semis, 0, 127);
        n.sp = semis > 0 ? 1 : (semis < 0 ? -1 : n.sp);
    }
}

// up or down by staff positions inside the key - what dragging a head means
// (on a drum staff: to the instrument written that many steps higher)
function md_moveSteps(M, notes, steps, key, perc) {
    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        if (perc) { n.p = nt_drumAtStep(nt_drum(n.p)[0] + steps); n.sp = 0; continue; }
        var s = nt_spell(n.p, key, n.sp);
        n.p = cr_clamp(nt_pitchOfStep(s.step + steps, key), 0, 127);
        n.sp = 0;
    }
}

function md_moveTime(M, notes, beats) {
    var minT = 1e9, i;
    for (i = 0; i < notes.length; i++) if (notes[i].t < minT) minT = notes[i].t;
    if (minT + beats < 0) beats = -minT;
    for (i = 0; i < notes.length; i++) notes[i].t += beats;
}

function md_setLength(M, notes, beats) {
    for (var i = 0; i < notes.length; i++) notes[i].d = beats;
}

function md_naturalize(M, notes, key) {
    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        var s = nt_spell(n.p, key, n.sp);
        if (s.alter !== 0) n.p = cr_clamp(n.p - s.alter, 0, 127);
        n.sp = 0;
    }
}

function md_endBeats(M) {
    var e = 0;
    for (var i = 0; i < M.notes.length; i++) {
        var x = M.notes[i].t + M.notes[i].d;
        if (x > e) e = x;
    }
    return e;
}

// what goes into the clip: [pitch, time, duration, velocity, muted]
function md_exportList(M) {
    var ns = cr_sortBy(M.notes, function (n) { return n.t * 1000 + n.p; });
    var out = [];
    for (var i = 0; i < ns.length; i++) {
        var n = ns[i];
        if (n.d <= 0) continue;
        out.push([n.p, n.t, n.d, n.v, n.m]);
    }
    return out;
}

// ---------------------------------------------------------------- ties
// In MIDI a tie is simply ONE longer note. TIE joins a note to the next note
// of the same pitch (up to a bar of silence between them is bridged); the
// score then draws the ties wherever the beat needs them.
function md_tieNext(M, n) {
    var best = null;
    for (var i = 0; i < M.notes.length; i++) {
        var m = M.notes[i];
        if (m === n || m.p !== n.p) continue;
        if (n.st >= 0 && m.st >= 0 && m.st !== n.st) continue;
        if (m.t < n.t + n.d - 1e-4 || m.t - (n.t + n.d) > 4 + 1e-6) continue;
        if (!best || m.t < best.t) best = m;
    }
    if (!best) return false;
    n.d = best.t + best.d - n.t;
    md_deleteIds(M, [best.id]);
    return true;
}

// ...and untying cuts it in two where the first tie was drawn
function md_split(M, n, at) {
    if (at <= n.t + 1e-6 || at >= n.t + n.d - 1e-6) return null;
    var n2 = md_note(M, n.p, at, n.t + n.d - at, n.v, n.m, n.sp, n.st);
    n2.sel = n.sel;
    n.d = at - n.t;
    M.notes.push(n2);
    return n2;
}

// ------------------------------------------------------------ ornaments
var md_TRILL_RATE = 0.125;     // 32nd notes
var md_GRACE = 0.0625;         // a 64th, just before the beat

// the note one step up the scale of the key
function md_upperNeighbour(p, key, sp) {
    var s = nt_spell(p, key, sp);
    return nt_pitchOfStep(s.step + 1, key);
}

// Replace a note by its trill: main and upper note alternating, starting on
// the main note, filling exactly the note's length. Returns the new ids, or
// null for a note shorter than a sixteenth.
function md_trill(M, n, key) {
    if (n.d < 0.25 - 1e-9) return null;
    var up = md_upperNeighbour(n.p, key, n.sp);
    var r = n.d >= 0.5 ? md_TRILL_RATE : n.d / 4;
    var end = n.t + n.d, ids = [], i = 0;
    md_deleteIds(M, [n.id]);
    for (var t = n.t; t < end - 1e-6; t += r, i++) {
        var nn = md_note(M, i % 2 ? up : n.p, t, Math.min(r, end - t), n.v, n.m, i % 2 ? 0 : n.sp, n.st);
        nn.sel = n.sel;
        M.notes.push(nn);
        ids.push(nn.id);
    }
    return ids;
}

// ...and back to one note
function md_untrill(M, notes) {
    var ns = cr_sortBy(notes, function (n) { return n.t; }), end = 0, ids = [], i;
    for (i = 0; i < ns.length; i++) {
        if (ns[i].t + ns[i].d > end) end = ns[i].t + ns[i].d;
        if (i > 0) ids.push(ns[i].id);
    }
    var main = ns[0];
    md_deleteIds(M, ids);
    main.d = end - main.t;
    return main;
}

// An acciaccatura: the note a step above, a 64th long, ending exactly where
// its note begins - so the note stays on the beat. On the very first beat of
// the clip there is no room before it, so the note itself moves a 64th later.
// On drums it is a flam: the same drum.
function md_addGrace(M, main, key, perc) {
    var gp = perc ? main.p : md_upperNeighbour(main.p, key, main.sp), g;
    if (main.t >= md_GRACE - 1e-9) {
        g = md_note(M, gp, main.t - md_GRACE, md_GRACE, main.v, 0, 0, main.st);
    } else {
        g = md_note(M, gp, main.t, md_GRACE, main.v, 0, 0, main.st);
        main.t += md_GRACE;
        main.d = Math.max(md_GRACE * 3, main.d - md_GRACE);
    }
    M.notes.push(g);
    return g;
}

// Taking an acciaccatura away puts a note that had to move for it back.
function md_removeGrace(M, main, grace) {
    if (cr_abs(grace.t) < 1e-9 && cr_abs(main.t - md_GRACE) < 1e-9) {
        main.t = 0;
        main.d += md_GRACE;
    }
    md_deleteIds(M, [grace.id]);
}

// ---- src/20_notate.js
// ============================================================================
//  nt_ - notation: from a list of notes to measures of notatable events
//
//  The pipeline, per staff:
//
//    1. meter      what a bar looks like: its length, its beats, the beat
//                  groups that beams follow, and a STRENGTH for every tick -
//                  bar start 0, the middle of a 4/4 bar 1, a beat 2, then
//                  the halves and quarters of a beat 3, 4, 5...
//    2. triplets   per beat: does a triplet grid explain the onsets clearly
//                  better than the straight grid? Only then is it a triplet.
//    3. quantize   onsets and ends snap to the grid of the beat they fall in
//    4. overlaps   a note sounding past the next onset in its staff is cut
//                  there (or tied, if asked), because one staff here is one
//                  voice with chords
//    5. segments   between every onset and every end the set of sounding
//                  notes is constant: that is one chord, or one rest
//    6. figures    each segment is split into values that exist (a quarter,
//                  a dotted eighth...) and that SHOW THE BEAT: a rest never
//                  hides a stronger beat than the one it starts on, a note
//                  may syncopate inside a beat but not across the middle of
//                  the bar. The pieces of a note are joined with ties.
//    7. spelling   letter and accidental from the key, and the accidental
//                  actually printed from what the bar has already said
//    8. beams      eighths and shorter, beamed per beat group, broken by rests
// ============================================================================

// ticks -> [type, dots]; type 0 whole, 1 half, 2 quarter, 3 eighth, 4 16th,
// 5 32nd, 6 64th
var nt_DUR = {
    288: [0, 1], 192: [0, 0], 144: [1, 1], 96: [1, 0], 72: [2, 1], 48: [2, 0],
    36: [3, 1], 24: [3, 0], 18: [4, 1], 12: [4, 0], 9: [5, 1], 6: [5, 0], 3: [6, 0]
};

var nt_LETTER_PC = [0, 2, 4, 5, 7, 9, 11];
var nt_SHARP_ORDER = [3, 0, 4, 1, 5, 2, 6];      // F C G D A E B
var nt_FLAT_ORDER = [6, 2, 5, 1, 4, 0, 3];       // B E A D G C F

// ---------------------------------------------------------------- 1. meter
function nt_meter(num, den) {
    var unit = WHOLE / den;
    var mi = {
        num: num, den: den, barT: num * unit, unit: unit,
        compound: false, additive: false, beatT: unit, sub: unit / 2,
        half: 0, groups: [], tripOK: false
    };
    var k, g;
    if (den >= 8 && num % 3 === 0 && num > 3) {
        // 6/8, 9/8, 12/8: the beat is three eighths
        mi.compound = true;
        mi.beatT = unit * 3;
        mi.sub = unit;
        for (k = 0; k < num / 3; k++) mi.groups.push([k * mi.beatT, mi.beatT]);
        if ((num / 3) % 2 === 0 && num / 3 >= 4) mi.half = mi.barT / 2;
    } else if (den >= 8) {
        // 3/8, 5/8, 7/8: groups of three first, then twos
        mi.additive = true;
        mi.sub = unit;
        mi.beatT = unit * 2;
        var left = num, at = 0;
        if (num % 2 === 1 && num >= 3) { mi.groups.push([0, 3 * unit]); left -= 3; at = 3 * unit; }
        while (left > 0) {
            g = left >= 2 ? 2 : 1;
            mi.groups.push([at, g * unit]);
            at += g * unit; left -= g;
        }
    } else {
        for (k = 0; k < num; k++) mi.groups.push([k * unit, unit]);
        if (num % 2 === 0 && num >= 4) mi.half = mi.barT / 2;
        mi.tripOK = (den === 4);
    }
    return mi;
}

function nt_strength(mi, o) {
    if (cr_mod(o, mi.barT) === 0) return 0;
    if (mi.half && o % mi.half === 0) return 1;
    for (var i = 0; i < mi.groups.length; i++) if (mi.groups[i][0] === o) return 2;
    var s = mi.sub, lvl = 3;
    while (s >= 1) {
        if (o % s === 0) return lvl;
        if (s % 2) break;
        s = s / 2; lvl++;
    }
    return 99;
}

// earliest boundary strictly inside (o, end) whose strength is <= lvl, or -1
function nt_boundary(mi, lvl, o, end) {
    var best = -1, b, i;
    if (lvl >= 1 && mi.half) {
        b = (Math.floor(o / mi.half) + 1) * mi.half;
        if (b < end && b % mi.barT !== 0) best = b;
    }
    if (lvl >= 2) {
        for (i = 0; i < mi.groups.length; i++) {
            b = mi.groups[i][0];
            if (b > o && b < end && (best < 0 || b < best)) { best = b; break; }
        }
    }
    var s = mi.sub, l = 3;
    while (l <= lvl && s >= 1) {
        b = (Math.floor(o / s) + 1) * s;
        if (b < end && (best < 0 || b < best)) best = b;
        if (s % 2) break;
        s = s / 2; l++;
    }
    return best;
}

// ------------------------------------------------------------- 6. figures
function nt_fitsNote(mi, o, L) {
    if (!nt_DUR[L]) return false;
    if (o === 0 && L === mi.barT) return true;
    var so = nt_strength(mi, o), end = o + L;
    // across the middle of the bar only from a beat, and no longer than half
    if (nt_boundary(mi, 1, o, end) >= 0) {
        if (so > 2) return false;
        if (so === 2 && L > mi.half) return false;
    }
    // across a beat: from a beat, or a short syncopation inside the beat
    if (nt_boundary(mi, 2, o, end) >= 0 && so > 2) {
        if (L > (mi.compound ? mi.sub * 2 : mi.beatT)) return false;
    }
    return true;
}

// a rest never hides a boundary stronger than the one it starts on
function nt_fitsRest(mi, o, L) {
    if (!nt_DUR[L]) return false;
    if (o === 0 && L === mi.barT) return true;
    var so = nt_strength(mi, o);
    if (so >= 1 && nt_boundary(mi, so - 1, o, o + L) >= 0) return false;
    // and only a rest from the bar or its middle may run over a beat: two
    // quarter rests, not a half rest, from the second beat of 3/4 or 7/8
    if (so >= 2 && nt_boundary(mi, 2, o, o + L) >= 0) return false;
    return true;
}

function nt_largestDur(L) {
    var best = 3;
    for (var k in nt_DUR) { var v = +k; if (v <= L && v > best) best = v; }
    return best;
}

// Split the span [o, o+L) (bar-relative ticks) into figures. trip(o) says
// whether the beat starting at bar-relative tick o is a triplet beat.
function nt_figures(mi, trip, o, L, rest, out) {
    if (L <= 0) return;
    var b;
    if (mi.tripOK) {
        var bs = Math.floor(o / 48) * 48;
        if (o + L > bs + 48) {
            var anyT = false;
            for (b = bs; b < o + L; b += 48) if (trip(b)) anyT = true;
            if (anyT) {
                nt_figures(mi, trip, o, bs + 48 - o, rest, out);
                nt_figures(mi, trip, bs + 48, o + L - bs - 48, rest, out);
                return;
            }
        } else if (trip(bs)) {
            var r = o - bs;
            if (L === 48 && r === 0) { out.push({ o: o, L: L, type: 2, dots: 0, tup: 0 }); return; }
            if (L === 32 || L === 16 || L === 8) {
                out.push({ o: o, L: L, type: L === 32 ? 2 : (L === 16 ? 3 : 4), dots: 0, tup: 1 });
                return;
            }
            b = (Math.floor(r / 16) + 1) * 16;
            if (!(b < r + L && b < 48)) b = (Math.floor(r / 8) + 1) * 8;
            if (b < r + L) {
                nt_figures(mi, trip, o, b - r, rest, out);
                nt_figures(mi, trip, bs + b, r + L - b, rest, out);
                return;
            }
            // not on the triplet grid at all: fall through to straight values
        }
    }
    if (rest ? nt_fitsRest(mi, o, L) : nt_fitsNote(mi, o, L)) {
        var dv = nt_DUR[L];
        out.push({ o: o, L: L, type: dv[0], dots: dv[1], tup: 0 });
        return;
    }
    b = -1;
    for (var lvl = 1; lvl <= 8 && b < 0; lvl++) b = nt_boundary(mi, lvl, o, o + L);
    if (b < 0) {
        // nothing left to split on: the grid below 64ths. Keep the time
        // right and approximate the look.
        var lv = nt_largestDur(L), dd = nt_DUR[lv];
        out.push({ o: o, L: L, type: dd[0], dots: dd[1], tup: 0 });
        return;
    }
    nt_figures(mi, trip, o, b - o, rest, out);
    nt_figures(mi, trip, b, o + L - b, rest, out);
}

// ------------------------------------------------------- 7. spelling
function nt_keyAlters(key) {
    var a = [0, 0, 0, 0, 0, 0, 0], i;
    if (key > 0) for (i = 0; i < key && i < 7; i++) a[nt_SHARP_ORDER[i]] = 1;
    if (key < 0) for (i = 0; i < -key && i < 7; i++) a[nt_FLAT_ORDER[i]] = -1;
    return a;
}

// Which letter and accidental a pitch is written with, in a key.
//   1. the key's own scale note, if the pitch is one (covers Cb, E#, B#)
//   2. a white key is written natural
//   3. a black key follows the note's own spelling if it has one (the user
//      chose sharp or flat), else the key's direction; in C: C# Eb F# G# Bb
function nt_spell(p, key, sp) {
    var pc = cr_mod(p, 12), ka = nt_keyAlters(key);
    var cand = [], L, x;
    for (L = 0; L < 7; L++) {
        x = cr_mod(pc - nt_LETTER_PC[L] + 6, 12) - 6;
        if (x >= -1 && x <= 1) cand.push([L, x]);
    }
    var pick = null, i;
    var black = (pc === 1 || pc === 3 || pc === 6 || pc === 8 || pc === 10);
    if (black && (sp === 1 || sp === -1)) {
        for (i = 0; i < cand.length; i++) if (cand[i][1] === sp) pick = cand[i];
    }
    if (!pick) for (i = 0; i < cand.length; i++) if (cand[i][1] === ka[cand[i][0]]) pick = cand[i];
    if (!pick) for (i = 0; i < cand.length; i++) if (cand[i][1] === 0) pick = cand[i];
    if (!pick) {
        var want = key > 0 ? 1 : -1;
        if (key === 0) want = (pc === 3 || pc === 10) ? -1 : 1;
        for (i = 0; i < cand.length; i++) if (cand[i][1] === want) pick = cand[i];
        if (!pick) pick = cand[0];
    }
    var oct = Math.floor((p - pick[1]) / 12) - 1;
    return { letter: pick[0], alter: pick[1], oct: oct, step: oct * 7 + pick[0] };
}

// the pitch that sits on a staff step in a key, before any accidental
function nt_pitchOfStep(step, key) {
    var letter = cr_mod(step, 7);
    var oct = Math.floor(step / 7);
    return (oct + 1) * 12 + nt_LETTER_PC[letter] + nt_keyAlters(key)[letter];
}

// ------------------------------------------------------ 2+3. quantization
// Per beat, a triplet grid is chosen only when it explains the onsets clearly
// better than the straight one AND puts at least one of them on a third of the
// beat. Straight sixteenths played a little loose must not become triplets.
// EXACT times are left alone. The grid is there to tidy up notes that were
// PLAYED; a note written in the editor, or quantized in Live, already sits on
// a 32nd or a triplet position, and rounding it to a coarser display grid
// would move what the user wrote. An exact triplet position (a third or a
// sixth of a beat) always makes its beat a triplet beat.
function nt_isExact(x, unit) { return cr_abs(x - cr_round(x / unit) * unit) < 0.02; }
function nt_isTripPos(x) { return nt_isExact(x, 8) && !nt_isExact(x, 6); }

function nt_detectTriplets(raw, mi, opt) {
    var trips = {};
    if (!opt.tuplets || !mi.tripOK) return trips;
    var g = opt.quant, beats = {}, i, k;
    for (i = 0; i < raw.length; i++) {
        var on = raw[i].on;
        if (nt_isTripPos(on)) { trips[Math.floor(on / 48 + 1e-9) * 48] = true; continue; }
        if (nt_isExact(on, 6) || g > 24) continue;
        k = Math.floor((on + 8) / 48);
        if (!beats[k]) beats[k] = [];
        beats[k].push(on);
    }
    for (var key in beats) {
        var list = beats[key], es = 0, et = 0, third = false;
        var bs = (+key) * 48;
        for (i = 0; i < list.length; i++) {
            var r = list[i];
            es += cr_abs(r - cr_round(r / g) * g);
            var qt = cr_round(r / 16) * 16;
            et += cr_abs(r - qt);
            var rel = qt - bs;
            if (rel === 16 || rel === 32) third = true;
        }
        if (third && et + 0.5 < es * 0.6) trips[bs] = true;
    }
    return trips;
}

// snap a time; `beatOf` says which beat's grid applies
function nt_snap(x, trips, g, beatOf) {
    var bs = Math.floor(beatOf / 48 + 1e-9) * 48;
    if (trips[bs]) return nt_isExact(x, 8) ? cr_round(x / 8) * 8 : cr_round(x / 16) * 16;
    if (nt_isExact(x, 6)) return cr_round(x / 6) * 6;
    return cr_round(x / g) * g;
}

function nt_quantize(raw, mi, opt, trips) {
    var g = opt.quant, out = [], i;
    for (i = 0; i < raw.length; i++) {
        var n = raw[i];
        var on = nt_snap(n.on, trips, g, nt_isExact(n.on, 8) ? n.on : n.on + 8);
        if (on < 0) on = 0;
        var off = nt_snap(n.off, trips, g, n.off);
        var unit = trips[Math.floor(on / 48) * 48] ? (on % 16 ? 8 : 16) : (nt_isExact(n.off - n.on, 6) ? 6 : g);
        if (off < on + unit) {
            off = on + unit;
            // A note stretched to the shortest value can end up INSIDE a
            // triplet beat off its grid (a straight eighth from the "and"
            // lands on a sixteenth of a triplet beat). Round it on to the
            // next position that beat can actually show.
            if (trips[Math.floor(off / 48) * 48] && off % 8) off = Math.ceil(off / 16) * 16;
        }
        out.push({ id: n.id, p: n.p, sp: n.sp, v: n.v, sel: n.sel, on: on, off: off,
                   trill: n.trill, ids: n.ids, up: n.up, grace: n.grace });
    }
    return out;
}

// --------------------------------------------------------- 4. overlaps
// Two notes of the same pitch cannot overlap. A note that sounds past the next
// onset in its staff is cut at that onset when the overhang is small (a legato
// finger) or when the user asked for CUT; with TIE it keeps sounding and the
// score ties it into the following chords.
//
// Linear, and it has to be: this used to compare every note with every other
// note, and on a 128-bar arrangement clip that one step took 90% of the
// engraving time - measured at 1.8 s under WSH - on every single edit.
function nt_fixOverlaps(qn, opt) {
    var ns = cr_sortBy(qn, function (n) { return n.on; });
    var i, j, n;
    // the next onset after each note, walking the sorted list once
    var nextOn = [];
    for (i = ns.length - 1, j = -1; i >= 0; i--) {
        if (i + 1 < ns.length && ns[i + 1].on > ns[i].on) j = ns[i + 1].on;
        else if (i + 1 < ns.length) j = nextOn[i + 1];
        nextOn[i] = j;
    }
    // the next note of the same pitch that starts later: one pass, per pitch
    var lastOfPitch = {}, laterSame = [];
    for (i = ns.length - 1; i >= 0; i--) {
        n = ns[i];
        var cand = lastOfPitch[n.p];
        laterSame[i] = cand;
        // equal onsets are duplicates, not "later": look past them
        if (!cand || cand.on > n.on) lastOfPitch[n.p] = n;
    }
    for (i = 0; i < ns.length; i++) {
        n = ns[i];
        var m = laterSame[i];
        if (m && m.on > n.on && m.on < n.off) n.off = m.on;
        var next = nextOn[i];
        if (next >= 0 && n.off > next) {
            if (opt.overlap !== "tie" || n.off - next <= opt.quant) n.off = next;
        }
    }
    // identical pitch and onset: keep the longer one
    var keep = [], seen = {};
    for (i = 0; i < ns.length; i++) {
        var key = ns[i].p + "_" + ns[i].on, k = seen[key];
        if (k) { if (ns[i].off > k.off) k.off = ns[i].off; continue; }
        seen[key] = ns[i];
        keep.push(ns[i]);
    }
    return keep;
}

// ------------------------------------------------------------ 5. segments
function nt_staffMeasures(qn, mi, nBars, trips, staffInfo, key) {
    var barT = mi.barT, total = nBars * barT, times = [], i, j;
    for (i = 0; i <= nBars; i++) times.push(i * barT);
    for (i = 0; i < qn.length; i++) {
        if (qn[i].on < total) { times.push(qn[i].on); times.push(Math.min(qn[i].off, total)); }
    }
    times = cr_uniqSorted(times);

    var ns = cr_sortBy(qn, function (n) { return n.on * 256 + n.p; });
    var measures = [];
    for (i = 0; i < nBars; i++) measures.push({ events: [], beams: [], tuplets: [], segs: [] });

    var ptr = 0, active = [];
    for (i = 0; i + 1 < times.length; i++) {
        var a = times[i], b = times[i + 1];
        var still = [];
        for (j = 0; j < active.length; j++) if (active[j].off > a) still.push(active[j]);
        active = still;
        while (ptr < ns.length && ns[ptr].on <= a) {
            if (ns[ptr].off > a) active.push(ns[ptr]);
            ptr++;
        }
        var m = Math.floor(a / barT);
        if (m >= nBars) break;
        measures[m].segs.push({ a: a, b: b, notes: cr_sortBy(active, function (n) { return n.p; }) });
    }

    var evId = 0;
    for (var mm = 0; mm < nBars; mm++) {
        var ms = measures[mm], base = mm * barT;
        var tripRel = (function (bb) { return function (o) { return !!trips[bb + o]; }; })(base);
        var allRest = true;
        for (i = 0; i < ms.segs.length; i++) if (ms.segs[i].notes.length) allRest = false;
        if (allRest) {
            ms.events.push({ o: 0, L: barT, rest: true, mrest: true, type: 0, dots: 0, tup: 0, notes: [], m: mm, eid: evId++ });
        } else {
            for (i = 0; i < ms.segs.length; i++) {
                var sg = ms.segs[i], figs = [];
                var isRest = sg.notes.length === 0;
                nt_figures(mi, tripRel, sg.a - base, sg.b - sg.a, isRest, figs);
                for (j = 0; j < figs.length; j++) {
                    var f = figs[j];
                    var ev = { o: f.o, L: f.L, rest: isRest, mrest: false, type: f.type, dots: f.dots,
                               tup: f.tup, notes: [], m: mm, eid: evId++ };
                    for (var q = 0; q < sg.notes.length; q++) {
                        var sn = sg.notes[q];
                        var firstPiece = !((j > 0) || (sn.on < sg.a));
                        ev.notes.push({
                            id: sn.id, p: sn.p, sp: sn.sp, v: sn.v, sel: sn.sel,
                            tiePrev: !firstPiece,
                            tieNext: (j < figs.length - 1) || (sn.off > sg.b),
                            trill: (firstPiece && sn.trill) ? 1 : 0, trillEnd: sn.off, up: sn.up,
                            grace: firstPiece ? (sn.grace || null) : null
                        });
                    }
                    ms.events.push(ev);
                }
            }
        }
        delete ms.segs;
        nt_accidentals(ms, key, staffInfo.perc);
        nt_beams(ms, mi);
        nt_tuplets(ms);
        for (i = 0; i < ms.events.length; i++) nt_stem(ms.events[i], staffInfo);
    }
    return measures;
}

// ----------------------------------------------------------- accidentals
function nt_accidentals(ms, key, perc) {
    var ka = nt_keyAlters(key), state = {}, i, j;
    for (i = 0; i < ms.events.length; i++) {
        var ev = ms.events[i];
        if (ev.rest) continue;
        for (j = 0; j < ev.notes.length; j++) {
            var n = ev.notes[j];
            if (perc) {
                // a drum sits where its instrument is written, never with an accidental
                var dm = nt_drum(n.p);
                n.step = dm[0]; n.alter = 0; n.letter = cr_mod(dm[0], 7); n.oct = Math.floor(dm[0] / 7);
                n.acc = null; n.head = dm[1]; n.trillAcc = null;
                if (n.grace) {
                    var gd = nt_drum(n.grace.p);
                    n.grace.step = gd[0]; n.grace.alter = 0; n.grace.letter = cr_mod(gd[0], 7);
                    n.grace.oct = Math.floor(gd[0] / 7); n.grace.acc = null; n.grace.head = gd[1];
                }
                continue;
            }
            var s = nt_spell(n.p, key, n.sp);
            n.step = s.step; n.alter = s.alter; n.letter = s.letter; n.oct = s.oct;
            var cur = (state[s.step] !== undefined) ? state[s.step] : ka[cr_mod(s.step, 7)];
            n.acc = (!n.tiePrev && s.alter !== cur) ? s.alter : null;
            if (n.grace) {
                var gs = nt_spell(n.grace.p, key, n.grace.sp);
                n.grace.step = gs.step; n.grace.alter = gs.alter; n.grace.letter = gs.letter; n.grace.oct = gs.oct;
                n.grace.acc = gs.alter !== ka[gs.letter] ? gs.alter : null;
            }
            if (n.trill) {
                // an accidental over "tr" when the upper note is not the key's
                var diat = nt_pitchOfStep(s.step + 1, key), ul = cr_mod(s.letter + 1, 7);
                n.trillAcc = (n.up === undefined || n.up === diat) ? null : n.up - (diat - nt_keyAlters(key)[ul]);
            }
        }
        for (j = 0; j < ev.notes.length; j++) {
            if (!ev.notes[j].tiePrev) state[ev.notes[j].step] = ev.notes[j].alter;
        }
    }
}

// ------------------------------------------------------------- 8. beams
function nt_groupKey(mi, ev) {
    if (ev.tup) return "t" + Math.floor(ev.o / 48);
    for (var i = mi.groups.length - 1; i >= 0; i--) if (ev.o >= mi.groups[i][0]) return "g" + i;
    return "g0";
}

function nt_beams(ms, mi) {
    var cur = [], curKey = "", i;
    function flush() {
        if (cur.length >= 2) {
            var bi = ms.beams.length;
            for (var k = 0; k < cur.length; k++) cur[k].beam = bi;
            ms.beams.push(cur);
        }
        cur = [];
    }
    for (i = 0; i < ms.events.length; i++) {
        var ev = ms.events[i];
        ev.beam = -1;
        var beamable = !ev.rest && ev.type >= 3;
        if (!beamable) { flush(); continue; }
        var k2 = nt_groupKey(mi, ev);
        if (cur.length && k2 !== curKey) flush();
        curKey = k2;
        cur.push(ev);
    }
    flush();
}

function nt_tuplets(ms) {
    var cur = [], curBeat = -1, i;
    for (i = 0; i < ms.events.length; i++) {
        var ev = ms.events[i];
        var beat = Math.floor(ev.o / 48);
        if (!ev.tup || beat !== curBeat) {
            if (cur.length) ms.tuplets.push(cur);
            cur = [];
            curBeat = -1;
        }
        if (ev.tup) { cur.push(ev); curBeat = beat; }
    }
    if (cur.length) ms.tuplets.push(cur);
}

// the furthest note from the middle line decides
function nt_stem(ev, st) {
    if (ev.rest) { ev.up = true; return; }
    var lo = 999, hi = -999;
    for (var i = 0; i < ev.notes.length; i++) {
        if (ev.notes[i].step < lo) lo = ev.notes[i].step;
        if (ev.notes[i].step > hi) hi = ev.notes[i].step;
    }
    ev.lo = lo; ev.hi = hi;
    ev.up = st.dir ? st.dir > 0 : (hi - st.mid) < (st.mid - lo);
}

// ============================================================== engrave
//  opt = { key, split, staves: "piano"|"treble"|"bass", quant (ticks),
//          tuplets (bool), overlap: "cut"|"tie", extraBar (bool) }
// ------------------------------------------------------------ ornaments
// Found in the notes themselves, before anything is quantized:
//
//   TRILL   at least four notes of a 32nd or shorter, each starting where the
//           last ended, alternating between two pitches a semitone or a tone
//           apart. It becomes ONE note from the first start to the last end,
//           marked "tr", remembering every note it stands for.
//   GRACE   a note no longer than a 64th (and a bit) ending where a note that
//           is more than twice as long begins. It becomes that note's
//           acciaccatura.
//
// These are exactly what md_trill and md_addGrace write, so what the editor
// puts in the clip comes back as the same symbol - and a trill or a grace note
// PLAYED that precisely reads the same way, which is what it is.
var nt_TRILL_MAX = 6.25, nt_GRACE_MAX = 3.4, nt_TOUCH = 0.6;

// On a drum staff there are no trills (two drums a tone apart in 32nds are a
// fill, not a trill), and a grace note on the SAME drum is a flam.
function nt_ornaments(raw, perc) {
    var ns = cr_sortBy(raw, function (n) { return n.on * 256 + n.p; });
    var used = {}, graces = {}, trills = [], rest = [], out = [], i, j;
    for (i = 0; i < ns.length; i++) {
        var n = ns[i];
        if (perc || used[n.id] || n.off - n.on > nt_TRILL_MAX) continue;
        var chain = [n], cur = n, B = null;
        for (;;) {
            var want = (chain.length % 2) ? B : n.p, found = null;
            for (j = i + 1; j < ns.length; j++) {
                var m = ns[j];
                if (m.on > cur.off + nt_TOUCH) break;
                if (used[m.id] || m.off - m.on > nt_TRILL_MAX || cr_abs(m.on - cur.off) > nt_TOUCH) continue;
                if (want === null) { var dd = cr_abs(m.p - n.p); if (dd < 1 || dd > 2) continue; }
                else if (m.p !== want) continue;
                if (cr_has(chain, m)) continue;
                found = m;
                break;
            }
            if (!found) break;
            if (B === null) B = found.p;
            chain.push(found);
            cur = found;
        }
        if (chain.length >= 4) {
            var ids = [], anySel = 0;
            for (j = 0; j < chain.length; j++) { used[chain[j].id] = 1; ids.push(chain[j].id); if (chain[j].sel) anySel = 1; }
            trills.push({ id: n.id, p: n.p, sp: n.sp, v: n.v, sel: anySel, on: n.on, off: cur.off, trill: 1, ids: ids, up: B });
        }
    }
    for (i = 0; i < ns.length; i++) if (!used[ns[i].id]) rest.push(ns[i]);
    var mains = rest.concat(trills);
    for (i = 0; i < rest.length; i++) {
        var g = rest[i];
        if (g.off - g.on > nt_GRACE_MAX) continue;
        var best = null;
        for (j = 0; j < mains.length; j++) {
            var mm = mains[j];
            if (mm === g || (used[mm.id] && !mm.trill) || graces[mm.id] || (!perc && mm.p === g.p)) continue;
            if (cr_abs(mm.on - g.off) > nt_TOUCH) continue;
            if (mm.off - mm.on <= 2 * (g.off - g.on)) continue;
            if (!best || cr_abs(mm.on - g.off) < cr_abs(best.on - g.off)) best = mm;
        }
        if (best) { used[g.id] = 1; graces[best.id] = g; }
    }
    for (i = 0; i < mains.length; i++) {
        var x = mains[i];
        if (used[x.id] && !x.trill) continue;
        var gr = graces[x.id];
        if (gr) x.grace = { id: gr.id, p: gr.p, sp: gr.sp, sel: gr.sel };
        out.push(x);
    }
    return { notes: out, graces: graces, trills: trills };
}

// where the first tie of a note is drawn (absolute ticks), or -1
function nt_firstTieEnd(S, id) {
    for (var s = 0; s < S.staves.length; s++) {
        var ms = S.staves[s].measures;
        for (var m = 0; m < ms.length; m++) {
            var evs = ms[m].events;
            for (var e = 0; e < evs.length; e++) {
                var ns = evs[e].notes;
                for (var k = 0; k < ns.length; k++) {
                    if (ns[k].id === id) return ns[k].tieNext ? m * S.mi.barT + evs[e].o + evs[e].L : -1;
                }
            }
        }
    }
    return -1;
}

var nt_STAFF = {
    G: { clef: "G", bottom: 30, mid: 34 },      // bottom line E4, middle B4
    F: { clef: "F", bottom: 18, mid: 22 }       // bottom line G2, middle D3
};

// ------------------------------------------------------------- drums
// A drum staff is one five-line staff with TWO voices on it: hands above,
// stems up; feet below, stems down - the way drum parts are written. The
// General MIDI drum notes (what Live's Drum Racks use) map to the usual
// positions and noteheads; cymbals and hi-hats are x heads.
//   pitch: [staff step, head ("n" normal, "x", "o" open hi-hat), voice, name]
var nt_DRUMS = {
    35: [31, "n", 1, "Kick"], 36: [31, "n", 1, "Kick"], 44: [29, "x", 1, "Pedal hi-hat"],
    37: [35, "x", 0, "Side stick"], 38: [35, "n", 0, "Snare"], 39: [35, "x", 0, "Clap"], 40: [35, "n", 0, "Snare"],
    41: [32, "n", 0, "Low floor tom"], 43: [33, "n", 0, "Floor tom"], 45: [34, "n", 0, "Low tom"],
    47: [34, "n", 0, "Low-mid tom"], 48: [36, "n", 0, "Hi-mid tom"], 50: [37, "n", 0, "High tom"],
    42: [39, "x", 0, "Closed hi-hat"], 46: [39, "o", 0, "Open hi-hat"],
    49: [40, "x", 0, "Crash"], 57: [40, "x", 0, "Crash 2"], 51: [38, "x", 0, "Ride"], 59: [38, "x", 0, "Ride 2"],
    53: [38, "x", 0, "Ride bell"], 52: [41, "x", 0, "China"], 55: [41, "x", 0, "Splash"],
    54: [37, "x", 0, "Tambourine"], 56: [37, "x", 0, "Cowbell"]
};

function nt_drum(p) { return nt_DRUMS[p] || [34, "n", 0, "Note " + cr_liveNoteName(p)]; }

// what a click on a staff position of a drum staff writes
var nt_DRUM_AT = { 29: 44, 31: 36, 32: 41, 33: 43, 34: 47, 35: 38, 36: 48, 37: 50, 38: 51, 39: 42, 40: 49, 41: 55 };

function nt_drumAtStep(step) {
    var best = 38, bd = 1e9;
    for (var k in nt_DRUM_AT) {
        var d = cr_abs(+k - step);
        if (d < bd) { bd = d; best = nt_DRUM_AT[k]; }
    }
    return best;
}

function nt_engrave(M, opt) {
    var mi = nt_meter(M.num, M.den);
    var staves = [], i, s;
    var perc = opt.staves === "drums";
    if (perc) {
        staves.push({ info: { clef: "P", bottom: 30, mid: 34, perc: true, dir: 1 }, raw: [] });
        staves.push({ info: { clef: "P", bottom: 30, mid: 34, perc: true, dir: -1 }, raw: [] });
    } else if (opt.staves === "treble") staves.push({ info: nt_STAFF.G, raw: [] });
    else if (opt.staves === "bass") staves.push({ info: nt_STAFF.F, raw: [] });
    else { staves.push({ info: nt_STAFF.G, raw: [] }); staves.push({ info: nt_STAFF.F, raw: [] }); }

    var endT = M.lenBeats * TPQ;
    for (i = 0; i < M.notes.length; i++) {
        var n = M.notes[i];
        if (n.d <= 0 || n.t < 0) continue;
        var r = { id: n.id, p: n.p, sp: n.sp, v: n.v, sel: n.sel, on: n.t * TPQ, off: (n.t + n.d) * TPQ };
        var si = (staves.length === 2 && n.p < opt.split) ? 1 : 0;
        if (staves.length === 2 && (n.st === 0 || n.st === 1)) si = n.st;
        if (perc) si = nt_drum(n.p)[2];
        staves[si].raw.push(r);
    }

    var groups = {}, graceOf = {};
    for (s = 0; s < staves.length; s++) {
        var st = staves[s];
        var orn = nt_ornaments(st.raw, perc);
        st.raw = orn.notes;
        for (i = 0; i < orn.trills.length; i++) {
            var tr = orn.trills[i];
            for (var ti = 0; ti < tr.ids.length; ti++) groups[tr.ids[ti]] = { kind: "trill", ids: tr.ids, main: tr.id };
        }
        for (var gm in orn.graces) {
            var gn = orn.graces[gm];
            groups[gn.id] = { kind: "grace", ids: [gn.id], main: +gm };
            graceOf[gm] = gn.id;
        }
        st.trips = nt_detectTriplets(st.raw, mi, opt);
        // A drum hit has an attack and no sustain worth writing: on a drum staff
        // a hit always lasts until the next hit of its voice, and is never tied.
        st.q = nt_fixOverlaps(nt_quantize(st.raw, mi, opt, st.trips), perc ? { overlap: "cut", quant: opt.quant } : opt);
        for (i = 0; i < st.q.length; i++) if (st.q[i].off > endT) endT = st.q[i].off;
    }
    var nBars = Math.max(1, Math.ceil(endT / mi.barT - 1e-9));
    var contentBars = nBars;
    if (opt.extraBar) nBars++;

    var S = { mi: mi, key: perc ? 0 : opt.key, nBars: nBars, contentBars: contentBars, staves: [], opt: opt,
              groups: groups, graceOf: graceOf, perc: perc };
    for (s = 0; s < staves.length; s++) {
        var sst = staves[s];
        S.staves.push({
            clef: sst.info.clef, bottom: sst.info.bottom, mid: sst.info.mid,
            perc: !!sst.info.perc, dir: sst.info.dir || 0,
            q: sst.q, trips: sst.trips,
            measures: nt_staffMeasures(sst.q, mi, nBars, sst.trips, sst.info, S.key)
        });
    }
    return S;
}

// Rebuild notes from an engraving: onsets, and lengths summed across ties.
// The test suite compares this with the quantized input - if a single tick of
// a single note is lost or invented anywhere between segmentation, figures and
// ties, it shows here.
function nt_reconstruct(S, si) {
    var st = S.staves[si], open = {}, out = [], m, e, k;
    for (m = 0; m < st.measures.length; m++) {
        var evs = st.measures[m].events;
        for (e = 0; e < evs.length; e++) {
            var ev = evs[e], abs = m * S.mi.barT + ev.o;
            for (k = 0; k < ev.notes.length; k++) {
                var n = ev.notes[k], key = n.id;
                if (n.tiePrev && open[key]) open[key].off = abs + ev.L;
                else { open[key] = { id: n.id, p: n.p, on: abs, off: abs + ev.L }; out.push(open[key]); }
                if (!n.tieNext) delete open[key];
            }
        }
    }
    return out;
}

// ---- src/30_glyphs.js
// ============================================================================
//  gl_ - the music symbols, drawn as vectors
//
//  There is no music font here on purpose. Finale's Maestro and Opus happen to
//  be installed on this machine, but a device that depends on them draws empty
//  boxes on every other computer, and Segoe UI Symbol does not exist on a Mac.
//  So every clef, head, flag and rest is a path.
//
//  Everything is designed in STAFF SPACES (the distance between two staff
//  lines), with y growing downwards, and scaled by `s` pixels per space.
//
//  The drawing is kept as a DISPLAY LIST rather than drawn directly, because
//  the same list has four destinations: the editor window (mgraphics), the
//  PNG export (an offscreen MGraphics) and the PDF export.
//
//    { k: "F", d: path, c: colour }             fill (non-zero winding)
//    { k: "S", d: path, c: colour, w: width }   stroke
//    { k: "T", x, y, s: text, size, font, bold, italic, align, c }
//
//  A path is a flat array: "M", x, y, "L", x, y, "C", x1, y1, x2, y2, x, y, "Z".
//  Holes (the inside of a half note) are a second sub-path wound the other way,
//  which every one of the four renderers fills correctly with no fill-rule
//  setting - mgraphics has none to set.
// ============================================================================

var gl_INK = [0.08, 0.08, 0.09, 1];

function gl_fill(D, P, c) { D.push({ k: "F", d: P, c: c }); }
function gl_stroke(D, P, c, w) { D.push({ k: "S", d: P, c: c, w: w }); }
function gl_text(D, x, y, str, size, font, bold, italic, align, c) {
    D.push({ k: "T", x: x, y: y, s: str, size: size, font: font, bold: bold ? 1 : 0,
             italic: italic ? 1 : 0, align: align || "left", c: c });
}

function gl_line(D, x1, y1, x2, y2, w, c) { gl_stroke(D, ["M", x1, y1, "L", x2, y2], c, w); }

function gl_rect(P, x, y, w, h) { P.push("M", x, y, "L", x + w, y, "L", x + w, y + h, "L", x, y + h, "Z"); }

// an ellipse from four cubic arcs; reverse = wound the other way, for holes
function gl_ellipse(P, cx, cy, rx, ry, rot, reverse) {
    var k = 0.5522847, c = Math.cos(rot), s = Math.sin(rot);
    // mirroring the minor axis runs the same outline the other way round
    if (reverse) ry = -ry;
    function pt(u, v) { return [cx + u * c - v * s, cy + u * s + v * c]; }
    var q = [[rx, 0], [0, ry], [-rx, 0], [0, -ry]];
    // tangent handles at each quadrant point, in the direction of travel
    var h = [[0, ry * k], [-rx * k, 0], [0, -ry * k], [rx * k, 0]];
    var p0 = pt(q[0][0], q[0][1]);
    P.push("M", p0[0], p0[1]);
    for (var i = 0; i < 4; i++) {
        var a = i, b = (i + 1) % 4;
        var c1 = pt(q[a][0] + h[a][0], q[a][1] + h[a][1]);
        var c2 = pt(q[b][0] - h[b][0], q[b][1] - h[b][1]);
        var e = pt(q[b][0], q[b][1]);
        P.push("C", c1[0], c1[1], c2[0], c2[1], e[0], e[1]);
    }
    P.push("Z");
}

function gl_circle(D, x, y, r, c) { var P = []; gl_ellipse(P, x, y, r, r, 0, false); gl_fill(D, P, c); }

// ---------------------------------------------------------------- the brush
// A calligraphic stroke: a centre line made of cubic segments, with a width
// that swells and thins along it. It becomes ONE filled polygon per segment
// run, so it renders identically everywhere and needs no line caps or joins.
//   seg = [x0,y0, x1,y1, x2,y2, x3,y3, w0, wMid, w1]   (staff spaces)
function gl_brush(D, ox, oy, s, segs, c) {
    var left = [], right = [], i, j, N = 14;
    for (i = 0; i < segs.length; i++) {
        var g = segs[i];
        for (j = (i === 0 ? 0 : 1); j <= N; j++) {
            var t = j / N, u = 1 - t;
            var x = u * u * u * g[0] + 3 * u * u * t * g[2] + 3 * u * t * t * g[4] + t * t * t * g[6];
            var y = u * u * u * g[1] + 3 * u * u * t * g[3] + 3 * u * t * t * g[5] + t * t * t * g[7];
            var dx = 3 * u * u * (g[2] - g[0]) + 6 * u * t * (g[4] - g[2]) + 3 * t * t * (g[6] - g[4]);
            var dy = 3 * u * u * (g[3] - g[1]) + 6 * u * t * (g[5] - g[3]) + 3 * t * t * (g[7] - g[5]);
            var len = Math.sqrt(dx * dx + dy * dy);
            if (len < 1e-9) { dx = 1; dy = 0; len = 1; }
            var w = u * u * g[8] + 2 * u * t * g[9] + t * t * g[10];
            var nx = -dy / len * w / 2, ny = dx / len * w / 2;
            left.push([ox + (x + nx) * s, oy + (y + ny) * s]);
            right.push([ox + (x - nx) * s, oy + (y - ny) * s]);
        }
    }
    var P = ["M", left[0][0], left[0][1]];
    for (i = 1; i < left.length; i++) P.push("L", left[i][0], left[i][1]);
    for (i = right.length - 1; i >= 0; i--) P.push("L", right[i][0], right[i][1]);
    P.push("Z");
    gl_fill(D, P, c);
}

// a straight brush segment
function gl_seg(x0, y0, x1, y1, w0, w1) {
    return [x0, y0, x0 + (x1 - x0) / 3, y0 + (y1 - y0) / 3, x0 + 2 * (x1 - x0) / 3, y0 + 2 * (y1 - y0) / 3,
            x1, y1, w0, (w0 + w1) / 2, w1];
}

// ------------------------------------------------------------- noteheads
// type 0 whole, 1 half, 2+ black
var gl_HEAD_W = 1.18;

function gl_head(D, x, y, s, type, c) {
    var P = [];
    if (type === 0) {
        gl_ellipse(P, x, y, 0.80 * s, 0.50 * s, 0, false);
        gl_ellipse(P, x, y, 0.36 * s, 0.30 * s, 1.0, true);
    } else if (type === 1) {
        gl_ellipse(P, x, y, 0.62 * s, 0.46 * s, -0.36, false);
        gl_ellipse(P, x, y, 0.50 * s, 0.20 * s, -0.62, true);
    } else {
        gl_ellipse(P, x, y, 0.62 * s, 0.46 * s, -0.36, false);
    }
    gl_fill(D, P, c);
}

function gl_headWidth(type) { return type === 0 ? 1.6 : gl_HEAD_W; }

// ------------------------------------------------------------- accidentals
// x, y = the centre of the symbol; width about one space
function gl_sharp(D, x, y, s, c) {
    var P = [], t = 0.11 * s, h = 0.36 * s;
    gl_rect(P, x - 0.30 * s - t / 2, y - 1.30 * s, t, 2.75 * s);
    gl_rect(P, x + 0.30 * s - t / 2, y - 1.45 * s, t, 2.75 * s);
    var bars = [-0.46, 0.50], i;
    for (i = 0; i < 2; i++) {
        var yc = y + bars[i] * s;
        P.push("M", x - 0.55 * s, yc + 0.14 * s - h / 2, "L", x + 0.55 * s, yc - 0.14 * s - h / 2,
               "L", x + 0.55 * s, yc - 0.14 * s + h / 2, "L", x - 0.55 * s, yc + 0.14 * s + h / 2, "Z");
    }
    gl_fill(D, P, c);
}

function gl_flat(D, x, y, s, c) {
    var P = [];
    gl_rect(P, x - 0.40 * s, y - 2.15 * s, 0.12 * s, 2.75 * s);
    gl_fill(D, P, c);
    gl_brush(D, x, y, s, [
        [-0.30, 0.02, 0.05, -0.55, 0.62, -0.62, 0.52, -0.12, 0.09, 0.26, 0.30],
        [0.52, -0.12, 0.44, 0.18, 0.05, 0.42, -0.34, 0.60, 0.30, 0.18, 0.08]
    ], c);
}

function gl_natural(D, x, y, s, c) {
    var P = [], t = 0.11 * s, h = 0.34 * s;
    gl_rect(P, x - 0.30 * s - t / 2, y - 1.45 * s, t, 2.05 * s);
    gl_rect(P, x + 0.30 * s - t / 2, y - 0.62 * s, t, 2.05 * s);
    var bars = [-0.36, 0.40], i;
    for (i = 0; i < 2; i++) {
        var yc = y + bars[i] * s;
        P.push("M", x - 0.30 * s, yc + 0.10 * s - h / 2, "L", x + 0.30 * s, yc - 0.10 * s - h / 2,
               "L", x + 0.30 * s, yc - 0.10 * s + h / 2, "L", x - 0.30 * s, yc + 0.10 * s + h / 2, "Z");
    }
    gl_fill(D, P, c);
}

function gl_accidental(D, x, y, s, alter, c) {
    if (alter === 1) gl_sharp(D, x, y, s, c);
    else if (alter === -1) gl_flat(D, x, y, s, c);
    else if (alter === 0) gl_natural(D, x, y, s, c);
}

function gl_accWidth(alter) { return alter === -1 ? 1.0 : 1.2; }

// ------------------------------------------------------------------ clefs
// G clef: x = its left edge, y = the G line (second line from the bottom)
function gl_trebleClef(D, x, y, s, c) {
    gl_brush(D, x, y, s, [
        [0.62, 2.10, 0.66, 2.80, 1.55, 2.90, 1.52, 1.95, 0.14, 0.19, 0.16],
        [1.52, 1.95, 1.47, 0.40, 1.08, -2.20, 1.32, -3.55, 0.16, 0.13, 0.13],
        [1.32, -3.55, 1.42, -4.22, 1.78, -4.60, 1.98, -4.28, 0.13, 0.12, 0.13]
    ], c);
    gl_brush(D, x, y, s, [
        [1.98, -4.28, 2.20, -3.88, 2.02, -3.28, 1.55, -2.76, 0.13, 0.18, 0.22],
        [1.55, -2.76, 0.90, -2.18, 0.05, -1.42, 0.08, -0.22, 0.22, 0.36, 0.30],
        [0.08, -0.22, 0.10, 0.90, 1.00, 1.26, 1.56, 1.16, 0.30, 0.22, 0.16]
    ], c);
    gl_brush(D, x, y, s, [
        [1.56, 1.16, 2.38, 1.04, 2.78, 0.28, 2.56, -0.46, 0.16, 0.28, 0.24],
        [2.56, -0.46, 2.34, -1.22, 1.28, -1.36, 0.94, -0.74, 0.24, 0.14, 0.13],
        [0.94, -0.74, 0.66, -0.24, 1.06, 0.26, 1.46, 0.10, 0.13, 0.16, 0.20]
    ], c);
    gl_circle(D, x + 0.72 * s, y + 2.02 * s, 0.42 * s, c);
}

// F clef: x = its left edge, y = the F line (second line from the top)
function gl_bassClef(D, x, y, s, c) {
    gl_circle(D, x + 0.52 * s, y + 0.02 * s, 0.44 * s, c);
    gl_brush(D, x, y, s, [
        [0.20, 0.00, 0.30, -0.95, 1.40, -1.14, 1.98, -0.76, 0.26, 0.24, 0.34],
        [1.98, -0.76, 2.72, -0.24, 2.62, 1.26, 1.52, 2.00, 0.34, 0.40, 0.22],
        [1.52, 2.00, 1.02, 2.36, 0.52, 2.62, 0.10, 2.78, 0.22, 0.12, 0.05]
    ], c);
    gl_circle(D, x + 3.00 * s, y - 0.50 * s, 0.17 * s, c);
    gl_circle(D, x + 3.00 * s, y + 0.50 * s, 0.17 * s, c);
}

function gl_clefWidth() { return 3.4; }

// ------------------------------------------------------------------ rests
// y = the middle line of the staff
function gl_rest(D, x, y, s, type, c) {
    var P = [];
    if (type === 0) { gl_rect(P, x - 0.62 * s, y - 1.0 * s, 1.24 * s, 0.52 * s); gl_fill(D, P, c); return; }
    if (type === 1) { gl_rect(P, x - 0.62 * s, y - 0.52 * s, 1.24 * s, 0.52 * s); gl_fill(D, P, c); return; }
    if (type === 2) {
        gl_brush(D, x, y, s, [
            gl_seg(-0.22, -1.55, 0.42, -0.74, 0.07, 0.20),
            [0.42, -0.74, 0.14, -0.44, -0.12, -0.18, -0.26, 0.04, 0.20, 0.50, 0.16],
            gl_seg(-0.26, 0.04, 0.40, 0.88, 0.16, 0.26)
        ], c);
        gl_brush(D, x, y, s, [
            [0.40, 0.88, -0.02, 0.62, -0.50, 0.92, -0.20, 1.40, 0.30, 0.26, 0.20],
            [-0.20, 1.40, -0.10, 1.55, 0.02, 1.60, 0.10, 1.62, 0.20, 0.14, 0.06]
        ], c);
        return;
    }
    // eighth and shorter: one blob and hook per flag, on a slanted stem
    var nflags = type - 2, i;
    var topX = 0.52, topY = -0.78 - (nflags - 1) * 0.0, slope = 0.30;
    var botY = 0.95 + (nflags - 1) * 1.0;
    gl_brush(D, x, y, s, [gl_seg(topX, topY, topX - (botY - topY) * slope, botY, 0.13, 0.12)], c);
    for (i = 0; i < nflags; i++) {
        var hy = topY + i * 1.0, hx = topX - i * 1.0 * slope;
        gl_circle(D, x + (hx - 0.80) * s, y + (hy + 0.30) * s, 0.26 * s, c);
        gl_brush(D, x, y, s, [[hx - 0.80, hy + 0.36, hx - 0.50, hy + 0.56, hx - 0.10, hy + 0.36, hx, hy, 0.10, 0.12, 0.12]], c);
    }
}

// --------------------------------------------------------------- flags
// x, y = the end of the stem; flags hang on its right side
function gl_flag(D, x, y, s, up, count, c) {
    var dir = up ? 1 : -1, i;
    for (i = 0; i < count; i++) {
        var o = i * 0.80 * dir;
        gl_brush(D, x, y, s, [
            [0.00, o, 0.05, o + 0.90 * dir, 1.28, o + 1.30 * dir, 0.98, o + (count > 1 && i < count - 1 ? 2.10 : 2.80) * dir,
             0.34, 0.30, 0.08]
        ], c);
    }
}

// --------------------------------------------------------------- other
function gl_dot(D, x, y, s, c) { gl_circle(D, x, y, 0.19 * s, c); }

// a tie or slur: a crescent from x1 to x2, bulging up (above) or down
function gl_tie(D, x1, x2, y, s, above, c) {
    var dx = x2 - x1;
    if (dx < 0.4 * s) dx = 0.4 * s;
    var h = Math.min(1.1 * s, 0.35 * s + dx * 0.08);
    var t = 0.17 * s, d = above ? -1 : 1;
    var P = ["M", x1, y,
             "C", x1 + dx * 0.25, y + d * h, x1 + dx * 0.75, y + d * h, x1 + dx, y,
             "C", x1 + dx * 0.75, y + d * (h - t), x1 + dx * 0.25, y + d * (h - t), x1, y, "Z"];
    gl_fill(D, P, c);
}

function gl_beam(D, x1, y1, x2, y2, thick, c) {
    gl_fill(D, ["M", x1, y1 - thick / 2, "L", x2, y2 - thick / 2, "L", x2, y2 + thick / 2,
                "L", x1, y1 + thick / 2, "Z"], c);
}

// the brace in front of a piano system; x = its right edge
function gl_brace(D, x, yTop, yBot, s, c) {
    var H = (yBot - yTop) / s, m = H / 2;
    gl_brush(D, x, yTop, s, [
        [-0.10, 0.00, -1.05, 0.12 * H, 0.10, 0.36 * H, -0.92, m, 0.06, 0.40, 0.06]
    ], c);
    gl_brush(D, x, yTop, s, [
        [-0.92, m, 0.10, 0.64 * H, -1.05, 0.88 * H, -0.10, H, 0.06, 0.40, 0.06]
    ], c);
}

// the wavy line after "tr"
function gl_wave(D, x0, x1, y, s, c) {
    if (x1 - x0 < 0.6 * s) return;
    var step = 0.42 * s, a = 0.2 * s, P = ["M", x0, y], x = x0, up = true;
    while (x + step <= x1) { x += step; P.push("L", x, y + (up ? -a : a)); up = !up; }
    gl_stroke(D, P, c, 0.12 * s);
}

// an x notehead (cymbals, hi-hat); open = with the small circle of an open hi-hat
function gl_headX(D, x, y, s, c, open) {
    gl_line(D, x - 0.5 * s, y - 0.45 * s, x + 0.5 * s, y + 0.45 * s, 0.17 * s, c);
    gl_line(D, x - 0.5 * s, y + 0.45 * s, x + 0.5 * s, y - 0.45 * s, 0.17 * s, c);
    if (open) {
        var P = [];
        gl_ellipse(P, x, y - 1.7 * s, 0.40 * s, 0.40 * s, 0, false);
        gl_ellipse(P, x, y - 1.7 * s, 0.26 * s, 0.26 * s, 0, true);
        gl_fill(D, P, c);
    }
}

// the neutral (percussion) clef: two thick bars; y = the middle line
function gl_percClef(D, x, y, s, c) {
    gl_fill(D, ["M", x + 0.9 * s, y - 1.0 * s, "L", x + 1.35 * s, y - 1.0 * s, "L", x + 1.35 * s, y + 1.0 * s, "L", x + 0.9 * s, y + 1.0 * s, "Z"], c);
    gl_fill(D, ["M", x + 1.9 * s, y - 1.0 * s, "L", x + 2.35 * s, y - 1.0 * s, "L", x + 2.35 * s, y + 1.0 * s, "L", x + 1.9 * s, y + 1.0 * s, "Z"], c);
}

// ---- src/40_layout.js
// ============================================================================
//  ly_ - layout: measures into systems, events into positions, and the
//  display list that draws them
//
//  Horizontal spacing follows the durations, the way engravers space music:
//  every onset column gets room that grows with the LOGARITHM of the time to
//  the next onset, plus fixed room for what sits beside a head (accidentals in
//  front, dots and displaced seconds behind). The columns are shared by both
//  staves of a piano system, so a chord in the left hand stands exactly under
//  the note it sounds with.
//
//  Systems are filled greedily and then justified by stretching only the
//  duration-dependent part, so accidentals never drift away from their heads.
//
//  Everything the editor needs to turn a click back into music is recorded on
//  the way: where every notehead is, and for every bar a table of
//  (tick, x) points to interpolate.
//
//  o = { width, sp, marginL, marginR, top, bottom, title, ink, selc,
//        stretchLast, finalBar }
// ============================================================================

var ly_STEM_W = 0.12;
var ly_BEAM_T = 0.50;
var ly_BEAM_GAP = 0.78;

function ly_space(d) { return 1.25 + 1.45 * Math.log(d / 12 + 1) / Math.LN2; }

// seconds in a chord: the head on the wrong side of the stem
function ly_headOffsets(ev) {
    var ns = ev.notes, offs = [], i;
    for (i = 0; i < ns.length; i++) offs.push(0);
    if (ev.up) {
        for (i = 1; i < ns.length; i++)
            if (ns[i].step - ns[i - 1].step <= 1 && offs[i - 1] === 0) offs[i] = 1;
    } else {
        for (i = ns.length - 2; i >= 0; i--)
            if (ns[i + 1].step - ns[i].step <= 1 && offs[i + 1] === 0) offs[i] = -1;
    }
    return offs;
}

// accidentals in columns, top to bottom, never two within a sixth in one column
function ly_accCols(ev) {
    var ns = ev.notes, cols = [], res = [], i, c, k;
    for (i = 0; i < ns.length; i++) res.push(-1);
    for (i = ns.length - 1; i >= 0; i--) {
        if (ns[i].acc === null || ns[i].acc === undefined) continue;
        for (c = 0; ; c++) {
            if (!cols[c]) cols[c] = [];
            var ok = true;
            for (k = 0; k < cols[c].length; k++) if (cr_abs(cols[c][k] - ns[i].step) < 6) ok = false;
            if (ok) { cols[c].push(ns[i].step); res[i] = c; break; }
        }
    }
    return { col: res, n: cols.length };
}

function ly_keyWidth(key) { return key ? cr_abs(key) * 1.0 + 0.8 : 0; }

var ly_KEY_STEPS = {
    G: { sharp: [38, 35, 39, 36, 33, 37, 34], flat: [34, 37, 33, 36, 32, 35, 31] },
    F: { sharp: [24, 21, 25, 22, 19, 23, 20], flat: [20, 23, 19, 22, 18, 21, 17] }
};

function ly_layout(S, o) {
    var sp = o.sp, mi = S.mi, nst = S.staves.length, nb = S.nBars;
    var ink = o.ink || gl_INK, selc = o.selc || [0.10, 0.42, 0.95, 1];
    var m, s, i, j, e;

    // -------------------------------------------------- 1. columns per bar
    var meas = [];
    for (m = 0; m < nb; m++) {
        var colMap = {}, cols = [], allRest = true;
        for (s = 0; s < nst; s++) {
            var evs = S.staves[s].measures[m].events;
            for (e = 0; e < evs.length; e++) {
                var ev = evs[e];
                if (!ev.mrest) allRest = false;
                var c = colMap[ev.o];
                if (!c) { c = { o: ev.o, pre: 0.1, post: 0.1 }; colMap[ev.o] = c; cols.push(c); }
                if (ev.rest) {
                    if (ev.dots) c.post = Math.max(c.post, 0.9);
                    continue;
                }
                var offs = ly_headOffsets(ev), ac = ly_accCols(ev), left = false, right = false;
                for (i = 0; i < offs.length; i++) { if (offs[i] < 0) left = true; if (offs[i] > 0) right = true; }
                var extra = (gl_headWidth(ev.type) - gl_HEAD_W) / 2;
                var pre = (ac.n ? ac.n * 1.15 + 0.35 : 0) + (left ? gl_HEAD_W : 0) + extra;
                for (i = 0; i < ev.notes.length; i++) {
                    var gr0 = ev.notes[i].grace;
                    if (gr0) pre = Math.max(pre, (ac.n ? ac.n * 1.15 + 0.35 : 0) + 3.0 + (gr0.acc !== null && gr0.acc !== undefined ? 1.0 : 0));
                }
                var post = (ev.dots ? 0.5 + ev.dots * 0.55 : 0) + (right ? gl_HEAD_W : 0) + extra;
                if (pre > c.pre) c.pre = pre;
                if (post > c.post) c.post = post;
            }
        }
        cols = cr_sortBy(cols, function (x) { return x.o; });
        var nat = 1.1;
        for (i = 0; i < cols.length; i++) {
            var nextO = (i + 1 < cols.length) ? cols[i + 1].o : mi.barT;
            cols[i].spring = ly_space(nextO - cols[i].o);
            if (allRest) cols[i].spring = Math.max(cols[i].spring, 7);
            nat += cols[i].pre + cols[i].spring + cols[i].post;
        }
        meas.push({ cols: cols, colMap: colMap, nat: nat, allRest: allRest });
    }

    // ------------------------------------------------------- 2. systems
    var avail = o.width - o.marginL - o.marginR;
    var keyW = ly_keyWidth(S.key);
    var tsW = 2.6;
    function headerW(first) { return (0.7 + gl_clefWidth() + 0.7 + keyW + (first ? tsW + 0.4 : 0) + 0.2) * sp; }
    var systems = [], cur = null;
    for (m = 0; m < nb; m++) {
        var w = meas[m].nat * sp;
        if (!cur || (cur.ms.length && cur.used + w > avail)) {
            cur = { ms: [], hdr: headerW(systems.length === 0), used: 0 };
            cur.used = cur.hdr;
            systems.push(cur);
        }
        cur.ms.push(m);
        cur.used += w;
    }

    // ----------------------------------------- 3. vertical room per system
    for (i = 0; i < systems.length; i++) {
        var sy = systems[i];
        sy.hi = []; sy.lo = [];
        for (s = 0; s < nst; s++) {
            var st = S.staves[s], hi = st.bottom + 8, lo = st.bottom;
            for (j = 0; j < sy.ms.length; j++) {
                var evs2 = st.measures[sy.ms[j]].events;
                for (e = 0; e < evs2.length; e++) {
                    if (evs2[e].rest) continue;
                    var eh = evs2[e].hi + (evs2[e].up ? 7 : 0), el = evs2[e].lo - (evs2[e].up ? 0 : 7);
                    if (eh > hi) hi = eh;
                    if (el < lo) lo = el;
                }
            }
            sy.hi.push(hi); sy.lo.push(lo);
        }
    }

    var L = {
        width: o.width, sp: sp, systems: [], measures: [], hits: [], topOps: [], sysOps: [],
        staves: nst, bottoms: [], mids: [], clefs: [], barT: mi.barT, nBars: nb, trills: []
    };
    for (s = 0; s < nst; s++) { L.bottoms.push(S.staves[s].bottom); L.mids.push(S.staves[s].mid); L.clefs.push(S.staves[s].clef); }

    var y = o.top;
    if (o.title) {
        gl_text(L.topOps, o.width / 2, y + 2.6 * sp, o.title, 2.3 * sp, "serif", 1, 0, "center", ink);
        y += 4.6 * sp;
    }

    var heads = [];           // per staff: map "eid_id" -> head position, for ties
    for (s = 0; s < nst; s++) heads.push({});

    for (i = 0; i < systems.length; i++) {
        var sys = systems[i], D = [];
        var last = (i === systems.length - 1);
        var springs = 0, natural = sys.hdr;
        for (j = 0; j < sys.ms.length; j++) {
            var mm = meas[sys.ms[j]];
            natural += mm.nat * sp;
            for (e = 0; e < mm.cols.length; e++) springs += mm.cols[e].spring * sp;
        }
        var factor = 1;
        var fill = natural / avail;
        if (!last || fill > 0.72 || o.stretchLast) {
            if (springs > 0) factor = 1 + (avail - natural) / springs;
        }
        if (factor < 0.55) factor = 0.55;

        // staff positions (a drum staff's two voices share one staff)
        if (S.perc) {
            sys.hi[0] = Math.max(sys.hi[0], sys.hi[1]);
            sys.lo[nst - 1] = Math.min(sys.lo[0], sys.lo[1]);
        }
        var tops = [];
        var above = Math.max(4.2, (sys.hi[0] - (S.staves[0].bottom + 8)) * 0.5 + 2.2);
        var yTop = y + above * sp;
        tops.push(yTop);
        for (s = 1; s < nst; s++) {
            if (S.perc) { tops.push(tops[0]); continue; }
            var below =Math.max(0, (S.staves[s - 1].bottom - sys.lo[s - 1]) * 0.5);
            var abv = Math.max(0, (sys.hi[s] - (S.staves[s].bottom + 8)) * 0.5);
            var gap = Math.max(6.5, below + abv + 1.5);
            tops.push(tops[s - 1] + (4 + gap) * sp);
        }
        var yEnd = tops[nst - 1] + 4 * sp + Math.max(4.2, (S.staves[nst - 1].bottom - sys.lo[nst - 1]) * 0.5 + 2.2) * sp;

        var x0 = o.marginL, x = x0;
        var sysInfo = { y0: y, y1: yEnd, tops: tops, x0: x0, x1: 0, m0: sys.ms[0], m1: sys.ms[sys.ms.length - 1], hdrEnd: 0 };

        // staff lines are drawn once the right end is known; clefs and keys now
        var yOf = (function (tp) {
            return function (si, step) { return tp[si] + 4 * sp - (step - S.staves[si].bottom) * sp / 2; };
        })(tops);

        x += 0.7 * sp;
        for (s = 0; s < nst; s++) {
            if (S.staves[s].clef === "P") { if (s === 0) gl_percClef(D, x, yOf(s, 34), sp, ink); }
            else if (S.staves[s].clef === "G") gl_trebleClef(D, x, yOf(s, 32), sp, ink);
            else gl_bassClef(D, x, yOf(s, 24), sp, ink);
        }
        x += (gl_clefWidth() + 0.7) * sp;
        if (S.key) {
            for (s = 0; s < nst; s++) {
                var ks = ly_KEY_STEPS[S.staves[s].clef][S.key > 0 ? "sharp" : "flat"];
                for (j = 0; j < cr_abs(S.key); j++) {
                    gl_accidental(D, x + (j * 1.0 + 0.5) * sp, yOf(s, ks[j]), sp, S.key > 0 ? 1 : -1, ink);
                }
            }
            x += keyW * sp;
        }
        if (i === 0) {
            for (s = 0; s < nst; s++) {
                if (S.perc && s > 0) continue;
                var mid = S.staves[s].mid;
                gl_text(D, x + 1.2 * sp, yOf(s, mid + 2) + 1.0 * sp, "" + mi.num, 2.9 * sp, "serif", 1, 0, "center", ink);
                gl_text(D, x + 1.2 * sp, yOf(s, mid - 2) + 1.0 * sp, "" + mi.den, 2.9 * sp, "serif", 1, 0, "center", ink);
            }
            x += (tsW + 0.4) * sp;
        }
        x += 0.2 * sp;
        sysInfo.hdrEnd = x;

        // ------------------------------------------------------ the bars
        for (j = 0; j < sys.ms.length; j++) {
            m = sys.ms[j];
            var M2 = meas[m];
            var mInfo = { sys: i, x0: x, x1: 0, pts: [] };
            // bar numbers; a take recorded in the Arrangement counts from its bar there
            if (j === 0 && (i > 0 || o.barOffset)) {
                gl_text(D, x0 + 0.2 * sp, tops[0] - 2.2 * sp, "" + (m + 1 + (o.barOffset || 0)), 1.25 * sp, "serif", 0, 1, "left", ink);
            }
            var cx = x + 1.1 * sp;
            for (e = 0; e < M2.cols.length; e++) {
                var col = M2.cols[e];
                cx += col.pre * sp;
                col.x = cx;
                mInfo.pts.push([col.o, cx]);
                cx += (col.post + col.spring * factor) * sp;
            }
            mInfo.x1 = cx;
            mInfo.pts.push([mi.barT, cx]);
            L.measures[m] = mInfo;

            for (s = 0; s < nst; s++) {
                ly_drawStaffBar(D, L, S, s, m, M2, yOf, sp, ink, selc, heads[s], i, mInfo);
            }
            // barline through the whole system
            var finalBar = (m === S.contentBars - 1 && o.finalBar) || m === nb - 1;
            var yb0 = tops[0], yb1 = tops[nst - 1] + 4 * sp;
            if (finalBar && m === nb - 1) {
                gl_fill(D, (function () { var P = []; gl_rect(P, cx - 0.5 * sp, yb0, 0.5 * sp, yb1 - yb0); return P; })(), ink);
                gl_line(D, cx - 1.1 * sp, yb0, cx - 1.1 * sp, yb1, 0.14 * sp, ink);
            } else {
                gl_line(D, cx, yb0, cx, yb1, 0.14 * sp, ink);
            }
            x = cx;
        }
        sysInfo.x1 = x;

        for (s = 0; s < nst; s++) {
            if (S.perc && s > 0) continue;
            for (j = 0; j < 5; j++) gl_line(D, x0, tops[s] + j * sp, x, tops[s] + j * sp, 0.11 * sp, ink);
        }
        gl_line(D, x0, tops[0], x0, tops[nst - 1] + 4 * sp, 0.14 * sp, ink);
        if (nst > 1 && !S.perc) gl_brace(D, x0 - 0.35 * sp, tops[0], tops[nst - 1] + 4 * sp, sp, ink);

        L.systems.push(sysInfo);
        L.sysOps.push(D);
        y = yEnd + 1.2 * sp;
    }

    ly_drawTies(L, S, heads, ink, selc);
    ly_drawTrills(L, ink, selc);
    L.height = y + (o.bottom || 0);
    return L;
}

// ---------------------------------------------------------------- one bar
function ly_drawStaffBar(D, L, S, s, m, M2, yOf, sp, ink, selc, heads, sysIdx, mInfo) {
    var st = S.staves[s], ms = st.measures[m], evs = ms.events, e, i, k;
    var mid = st.mid, bottom = st.bottom;
    var hw = gl_HEAD_W * sp;

    // beam groups decide their stems together
    for (k = 0; k < ms.beams.length; k++) {
        var grp = ms.beams[k], hi = -999, lo = 999;
        for (i = 0; i < grp.length; i++) { if (grp[i].hi > hi) hi = grp[i].hi; if (grp[i].lo < lo) lo = grp[i].lo; }
        var up = st.dir ? st.dir > 0 : (hi - mid) < (mid - lo);
        for (i = 0; i < grp.length; i++) grp[i].up = up;
    }

    // geometry of every event
    for (e = 0; e < evs.length; e++) {
        var ev = evs[e];
        var col = M2.colMap[ev.o];
        ev.cx = col.x;
        // a whole-bar rest sits in the middle of the bar, whatever its column
        if (ev.mrest) ev.cx = (mInfo.x0 + mInfo.x1) / 2;
        if (ev.rest) continue;
        ev.offs = ly_headOffsets(ev);
        ev.stemX = ev.up ? ev.cx + hw / 2 - ly_STEM_W * sp / 2 : ev.cx - hw / 2 + ly_STEM_W * sp / 2;
        var len = 3.5 + Math.max(0, ev.type - 3) * 0.75;
        if (ev.up) {
            ev.stemY0 = yOf(s, ev.lo) - 0.12 * sp;
            ev.stemY1 = yOf(s, ev.hi) - len * sp;
            if (ev.stemY1 > yOf(s, mid)) ev.stemY1 = yOf(s, mid);
        } else {
            ev.stemY0 = yOf(s, ev.hi) + 0.12 * sp;
            ev.stemY1 = yOf(s, ev.lo) + len * sp;
            if (ev.stemY1 < yOf(s, mid)) ev.stemY1 = yOf(s, mid);
        }
    }

    // beams
    ms.geo = [];
    for (k = 0; k < ms.beams.length; k++) {
        var g = ms.beams[k], f = g[0], l = g[g.length - 1], upb = f.up;
        var x1 = f.stemX, x2 = l.stemX;
        var y1 = upb ? yOf(s, f.hi) - 3.5 * sp : yOf(s, f.lo) + 3.5 * sp;
        var y2 = upb ? yOf(s, l.hi) - 3.5 * sp : yOf(s, l.lo) + 3.5 * sp;
        var levels = 1;
        for (i = 0; i < g.length; i++) if (g[i].type - 2 > levels) levels = g[i].type - 2;
        if (y2 - y1 > sp) y2 = y1 + sp;
        if (y1 - y2 > sp) y2 = y1 - sp;
        var slope = x2 > x1 ? (y2 - y1) / (x2 - x1) : 0;
        var dirIn = upb ? 1 : -1;
        var shift = 0;
        for (i = 0; i < g.length; i++) {
            var yb = y1 + slope * (g[i].stemX - x1) + dirIn * (levels - 1) * ly_BEAM_GAP * sp;
            if (upb) { var lim = yOf(s, g[i].hi) - 2.6 * sp; if (yb - lim > shift) shift = yb - lim; }
            else { var lim2 = yOf(s, g[i].lo) + 2.6 * sp; if (lim2 - yb > shift) shift = lim2 - yb; }
        }
        y1 -= dirIn * shift; y2 -= dirIn * shift;
        ms.geo.push({ x1: x1, y1: y1, x2: x2, y2: y2, up: upb });
        var T = ly_BEAM_T * sp;
        for (i = 0; i < g.length; i++) {
            g[i].stemY1 = y1 + slope * (g[i].stemX - x1) - dirIn * T / 2;
        }
        gl_beam(D, x1 - ly_STEM_W * sp / 2, y1 - slope * ly_STEM_W * sp / 2, x2 + ly_STEM_W * sp / 2, y2 + slope * ly_STEM_W * sp / 2, T, ink);
        for (var lv = 1; lv < levels; lv++) {
            var off = dirIn * lv * ly_BEAM_GAP * sp;
            for (i = 0; i < g.length; i++) {
                if (g[i].type - 2 <= lv) continue;
                var nextHas = (i + 1 < g.length) && g[i + 1].type - 2 > lv;
                var prevHas = (i > 0) && g[i - 1].type - 2 > lv;
                var xa, xb;
                if (nextHas) { xa = g[i].stemX; xb = g[i + 1].stemX; }
                else if (prevHas) continue;
                else if (i === g.length - 1) { xa = g[i].stemX - 1.1 * sp; xb = g[i].stemX; }
                else { xa = g[i].stemX; xb = g[i].stemX + 1.1 * sp; }
                gl_beam(D, xa, y1 + slope * (xa - x1) + off, xb, y1 + slope * (xb - x1) + off, T, ink);
            }
        }
    }

    // heads, accidentals, dots, ledger lines, stems, flags, rests
    for (e = 0; e < evs.length; e++) {
        var ev2 = evs[e];
        if (ev2.rest) {
            var ry = yOf(s, mid);
            if (st.perc) {
                // Two voices on one staff: a voice that is silent for a whole bar
                // shows nothing unless both are; otherwise rests move out of the
                // way, hands up and feet down.
                var other = s === 0 ? 1 : 0;
                if (ev2.mrest && (s > 0 || !ly_barEmpty(S, other, m))) continue;
                if (!ev2.mrest && !ly_barEmpty(S, other, m)) ry = yOf(s, mid + (st.dir > 0 ? 4 : -4));
            }
            var rtype = ev2.mrest ? 0 : ev2.type;
            gl_rest(D, ev2.cx, ry, sp, rtype, ink);
            if (ev2.dots && !ev2.mrest) gl_dot(D, ev2.cx + 1.0 * sp, ry - 0.5 * sp, sp, ink);
            continue;
        }
        var ac = ly_accCols(ev2);
        var hasLeft = false, hasRight = false;
        for (i = 0; i < ev2.offs.length; i++) { if (ev2.offs[i] < 0) hasLeft = true; if (ev2.offs[i] > 0) hasRight = true; }
        var whw = gl_headWidth(ev2.type) * sp;

        // ledger lines
        var lx0 = ev2.cx - whw / 2 - 0.35 * sp - (hasLeft ? hw : 0);
        var lx1 = ev2.cx + whw / 2 + 0.35 * sp + (hasRight ? hw : 0);
        for (k = bottom + 10; k <= ev2.hi; k += 2) gl_line(D, lx0, yOf(s, k), lx1, yOf(s, k), 0.16 * sp, ink);
        for (k = bottom - 2; k >= ev2.lo; k -= 2) gl_line(D, lx0, yOf(s, k), lx1, yOf(s, k), 0.16 * sp, ink);

        for (i = 0; i < ev2.notes.length; i++) {
            var n = ev2.notes[i];
            var col2 = n.sel ? selc : ink;
            var hx = ev2.cx + ev2.offs[i] * hw;
            var hy = yOf(s, n.step);
            if (n.head === "x" || n.head === "o") gl_headX(D, hx, hy, sp, col2, n.head === "o");
            else gl_head(D, hx, hy, sp, ev2.type, col2);
            L.hits.push({ k: "n", id: n.id, st: s, m: m, x0: hx - whw / 2, x1: hx + whw / 2, y0: hy - 0.55 * sp, y1: hy + 0.55 * sp });
            heads[ev2.eid + "_" + n.id] = { x: hx, y: hy, sys: sysIdx, up: ev2.up, idx: i, size: ev2.notes.length,
                                            dots: ev2.dots, tieNext: n.tieNext, right: hasRight };
            if (n.acc !== null && n.acc !== undefined) {
                var ax = ev2.cx - hw / 2 - (hasLeft ? hw : 0) - 0.35 * sp - (ac.col[i] + 0.5) * 1.15 * sp;
                gl_accidental(D, ax, hy, sp, n.acc, col2);
            }
            if (n.grace) {
                // the acciaccatura: a small eighth, stem up, slashed, slurred to its note
                var gr = n.grace, gsc = 0.62 * sp, colg = gr.sel ? selc : ink;
                var accRoom = ac.n ? ac.n * 1.15 * sp + 0.35 * sp : 0;
                var gx = ev2.cx - hw / 2 - (hasLeft ? hw : 0) - accRoom - 1.3 * sp;
                var gy = yOf(s, gr.step);
                for (k = bottom + 10; k <= gr.step; k += 2) gl_line(D, gx - 0.6 * sp, yOf(s, k), gx + 0.6 * sp, yOf(s, k), 0.12 * sp, colg);
                for (k = bottom - 2; k >= gr.step; k -= 2) gl_line(D, gx - 0.6 * sp, yOf(s, k), gx + 0.6 * sp, yOf(s, k), 0.12 * sp, colg);
                if (gr.head === "x" || gr.head === "o") gl_headX(D, gx, gy, gsc, colg, false);
                else gl_head(D, gx, gy, gsc, 2, colg);
                var gsx = gx + 0.6 * gsc;
                gl_fill(D, ["M", gsx - 0.05 * sp, gy - 0.1 * sp, "L", gsx + 0.05 * sp, gy - 0.1 * sp,
                            "L", gsx + 0.05 * sp, gy - 2.8 * sp, "L", gsx - 0.05 * sp, gy - 2.8 * sp, "Z"], colg);
                gl_flag(D, gsx - 0.05 * sp, gy - 2.8 * sp, gsc, true, 1, colg);
                gl_line(D, gsx - 0.75 * sp, gy - 1.0 * sp, gsx + 0.85 * sp, gy - 2.3 * sp, 0.1 * sp, colg);
                if (gr.acc !== null && gr.acc !== undefined) gl_accidental(D, gx - 1.0 * sp, gy, gsc, gr.acc, colg);
                gl_tie(D, gx + 0.2 * sp, ev2.cx - hw / 2 - (hasLeft ? hw : 0) - 0.15 * sp, Math.max(gy, hy) + 0.75 * sp, gsc, false, colg);
                L.hits.push({ k: "g", id: gr.id, st: s, m: m, x0: gx - 0.5 * sp, x1: gx + 0.5 * sp, y0: gy - 0.45 * sp, y1: gy + 0.45 * sp });
            }
            if (n.trill) {
                L.trills.push({ sys: sysIdx, s: s, x: ev2.cx, headY: hy, top: yOf(s, bottom + 8), up: ev2.up,
                                stemY1: ev2.stemY1, endTick: n.trillEnd, acc: n.trillAcc, sel: n.sel });
            }
            if (ev2.dots) {
                var dy = ((n.step - bottom) % 2 === 0) ? -0.5 * sp : 0;
                for (k = 0; k < ev2.dots; k++) {
                    gl_dot(D, ev2.cx + whw / 2 + (hasRight ? hw : 0) + (0.55 + k * 0.55) * sp, hy + dy, sp, col2);
                }
            }
        }
        if (ev2.type >= 1) {
            var sx = ev2.stemX - ly_STEM_W * sp / 2;
            var ya = Math.min(ev2.stemY0, ev2.stemY1), yb2 = Math.max(ev2.stemY0, ev2.stemY1);
            gl_fill(D, ["M", sx, ya, "L", sx + ly_STEM_W * sp, ya, "L", sx + ly_STEM_W * sp, yb2, "L", sx, yb2, "Z"], ink);
            if (ev2.beam < 0 && ev2.type >= 3) {
                gl_flag(D, ev2.stemX - ly_STEM_W * sp / 2, ev2.stemY1, sp, ev2.up, ev2.type - 2, ink);
            }
        }
    }

    // tuplets
    for (k = 0; k < ms.tuplets.length; k++) {
        var tp = ms.tuplets[k], fe = tp[0], le = tp[tp.length - 1];
        var beamed = !fe.rest && fe.beam >= 0;
        for (i = 0; i < tp.length; i++) if (tp[i].rest || tp[i].beam !== fe.beam) beamed = false;
        var tx = (fe.cx + le.cx) / 2;
        if (beamed) {
            var gg = ms.geo[fe.beam];
            var ymid = (gg.y1 + gg.y2) / 2;
            if (gg.up) gl_text(D, tx + 0.3 * sp, ymid - 0.9 * sp, "3", 1.7 * sp, "serif", 1, 1, "center", ink);
            else gl_text(D, tx - 0.3 * sp, ymid + 2.2 * sp, "3", 1.7 * sp, "serif", 1, 1, "center", ink);
        } else {
            var topY = yOf(s, st.bottom + 8) - 1.6 * sp;
            for (i = 0; i < tp.length; i++) {
                if (tp[i].rest) continue;
                var ty = Math.min(tp[i].stemY0, tp[i].stemY1, yOf(s, tp[i].hi)) - 1.4 * sp;
                if (ty < topY) topY = ty;
            }
            var bx0 = fe.cx - 0.7 * sp, bx1 = le.cx + 0.7 * sp;
            gl_line(D, bx0, topY + 0.6 * sp, bx0, topY, 0.1 * sp, ink);
            gl_line(D, bx0, topY, tx - 0.8 * sp, topY, 0.1 * sp, ink);
            gl_line(D, tx + 0.8 * sp, topY, bx1, topY, 0.1 * sp, ink);
            gl_line(D, bx1, topY, bx1, topY + 0.6 * sp, 0.1 * sp, ink);
            gl_text(D, tx, topY + 0.6 * sp, "3", 1.7 * sp, "serif", 1, 1, "center", ink);
        }
    }
}

// ------------------------------------------------------------------ ties
function ly_drawTies(L, S, heads, ink, selc) {
    var sp = L.sp, s, m, e, k;
    for (s = 0; s < S.staves.length; s++) {
        var flat = [];
        for (m = 0; m < S.staves[s].measures.length; m++) {
            var evs = S.staves[s].measures[m].events;
            for (e = 0; e < evs.length; e++) flat.push(evs[e]);
        }
        for (e = 0; e < flat.length; e++) {
            var ev = flat[e];
            if (ev.rest) continue;
            for (k = 0; k < ev.notes.length; k++) {
                var n = ev.notes[k];
                if (!n.tieNext) continue;
                var A = heads[s][ev.eid + "_" + n.id];
                var B = null;
                for (var f = e + 1; f < flat.length && f < e + 4 && !B; f++) {
                    if (heads[s][flat[f].eid + "_" + n.id]) B = heads[s][flat[f].eid + "_" + n.id];
                }
                if (!A || !B) continue;
                var above = A.size > 1 ? (A.idx >= A.size / 2) : !A.up;
                var dy = above ? -0.62 * sp : 0.62 * sp;
                var xa = A.x + 0.62 * sp + (A.dots ? 0.8 * sp : 0);
                var xb = B.x - 0.62 * sp;
                var col = n.sel ? selc : ink;
                if (A.sys === B.sys) {
                    gl_tie(L.sysOps[A.sys], xa, xb, A.y + dy, sp, above, col);
                } else {
                    gl_tie(L.sysOps[A.sys], xa, L.systems[A.sys].x1 + 0.4 * sp, A.y + dy, sp, above, col);
                    gl_tie(L.sysOps[B.sys], L.systems[B.sys].hdrEnd - 0.4 * sp, xb, B.y + dy, sp, above, col);
                }
            }
        }
    }
}

function ly_barEmpty(S, s, m) {
    if (!S.staves[s] || !S.staves[s].measures[m]) return true;
    var evs = S.staves[s].measures[m].events;
    for (var i = 0; i < evs.length; i++) if (!evs[i].rest) return false;
    return true;
}

// ---------------------------------------------------------------- trills
// "tr" above the note, then a wavy line to where the trill ends - across
// bar lines and on into the next system if it has to.
function ly_drawTrills(L, ink, selc) {
    var sp = L.sp, i, k;
    for (i = 0; i < L.trills.length; i++) {
        var t = L.trills[i], col = t.sel ? selc : ink, D = L.sysOps[t.sys];
        var y = Math.min(t.top - 1.3 * sp, t.headY - 2.0 * sp);
        if (t.up) y = Math.min(y, t.stemY1 - 0.9 * sp);
        gl_text(D, t.x, y, "tr", 1.9 * sp, "serif", 1, 1, "center", col);
        if (t.acc !== null && t.acc !== undefined) gl_accidental(D, t.x, y - 2.4 * sp, sp * 0.6, t.acc, col);
        var e = ly_xAtTick(L, t.endTick - 1);
        if (!e) continue;
        var x0 = t.x + 1.2 * sp, wy = y - 0.6 * sp;
        if (e.sys === t.sys) {
            gl_wave(D, x0, e.x, wy, sp, col);
        } else {
            gl_wave(D, x0, L.systems[t.sys].x1, wy, sp, col);
            for (k = t.sys + 1; k <= e.sys; k++) {
                var sy = L.systems[k];
                gl_wave(L.sysOps[k], sy.hdrEnd, k === e.sys ? e.x : sy.x1, sy.tops[t.s] - 1.9 * sp, sp, col);
            }
        }
    }
}

// ------------------------------------------------ editor geometry queries
function ly_yOf(L, sysIdx, si, step) {
    return L.systems[sysIdx].tops[si] + 4 * L.sp - (step - L.bottoms[si]) * L.sp / 2;
}

function ly_stepAtY(L, sysIdx, si, y) {
    var yb = L.systems[sysIdx].tops[si] + 4 * L.sp;
    return L.bottoms[si] + cr_round((yb - y) / (L.sp / 2));
}

// which system, bar and staff a point falls in (null outside the music)
function ly_locate(L, x, y) {
    var i, s, m;
    for (i = 0; i < L.systems.length; i++) {
        var sy = L.systems[i];
        if (y < sy.y0 || y > sy.y1) continue;
        var best = 0, bd = 1e9;
        for (s = 0; s < sy.tops.length; s++) {
            var c = sy.tops[s] + 2 * L.sp, d = cr_abs(y - c);
            if (d < bd) { bd = d; best = s; }
        }
        for (m = sy.m0; m <= sy.m1; m++) {
            var mm = L.measures[m];
            if (x >= mm.x0 && x < mm.x1) return { sys: i, st: best, m: m };
        }
        if (x >= sy.hdrEnd - L.sp && x < L.measures[sy.m0].x0) return { sys: i, st: best, m: sy.m0 };
        return null;
    }
    return null;
}

// bar-relative tick under an x, by interpolating the bar's (tick, x) points
function ly_tickAtX(L, m, x) {
    var pts = L.measures[m].pts, i;
    if (x <= pts[0][1]) return 0;
    for (i = 0; i + 1 < pts.length; i++) {
        if (x >= pts[i][1] && x <= pts[i + 1][1]) {
            var f = (x - pts[i][1]) / Math.max(1e-6, pts[i + 1][1] - pts[i][1]);
            return pts[i][0] + f * (pts[i + 1][0] - pts[i][0]);
        }
    }
    return L.barT;
}

function ly_xAtTick(L, absTick) {
    var m = Math.floor(absTick / L.barT);
    if (m < 0 || m >= L.measures.length || !L.measures[m]) return null;
    var t = absTick - m * L.barT, pts = L.measures[m].pts, i;
    for (i = 0; i + 1 < pts.length; i++) {
        if (t >= pts[i][0] && t <= pts[i + 1][0]) {
            var f = (t - pts[i][0]) / Math.max(1e-6, pts[i + 1][0] - pts[i][0]);
            return { x: pts[i][1] + f * (pts[i + 1][1] - pts[i][1]), sys: L.measures[m].sys, m: m };
        }
    }
    return { x: pts[0][1], sys: L.measures[m].sys, m: m };
}

function ly_hitNote(L, x, y) {
    for (var i = L.hits.length - 1; i >= 0; i--) {
        var h = L.hits[i];
        if (x >= h.x0 && x <= h.x1 && y >= h.y0 && y <= h.y1) return h;
    }
    return null;
}

// ---- src/50_render.js
// ============================================================================
//  dr_ - replaying a display list
//
//  Onto anything with the mgraphics drawing calls: the jsui's own mgraphics,
//  an offscreen MGraphics (the PNG export), or the canvas shim the browser
//  preview uses. dx / dy move the whole list, which is how a view scrolls and
//  how a PDF page picks up the systems that belong on it.
// ============================================================================

function dr_path(g, P, dx, dy) {
    var i = 0, n = P.length;
    g.new_path && g.new_path();
    while (i < n) {
        var c = P[i];
        if (c === "M") { g.move_to(P[i + 1] + dx, P[i + 2] + dy); i += 3; }
        else if (c === "L") { g.line_to(P[i + 1] + dx, P[i + 2] + dy); i += 3; }
        else if (c === "C") { g.curve_to(P[i + 1] + dx, P[i + 2] + dy, P[i + 3] + dx, P[i + 4] + dy, P[i + 5] + dx, P[i + 6] + dy); i += 7; }
        else if (c === "Z") { g.close_path(); i += 1; }
        else i += 1;
    }
}

// Font faces by role. mgraphics wants a family name; weight and slant are
// asked for with the extra arguments that the underlying jgraphics call takes.
var dr_FONTS = { serif: "Times New Roman", sans: "Arial" };

function dr_ops(g, ops, dx, dy, yMin, yMax) {
    for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        var c = op.c;
        if (op.k === "F") {
            g.set_source_rgba(c[0], c[1], c[2], c[3]);
            dr_path(g, op.d, dx, dy);
            g.fill();
        } else if (op.k === "S") {
            g.set_source_rgba(c[0], c[1], c[2], c[3]);
            g.set_line_width(op.w);
            dr_path(g, op.d, dx, dy);
            g.stroke();
        } else if (op.k === "T") {
            g.set_source_rgba(c[0], c[1], c[2], c[3]);
            g.select_font_face(dr_FONTS[op.font] || op.font, op.italic ? "italic" : "normal", op.bold ? "bold" : "normal");
            g.set_font_size(op.size);
            var w = 0;
            if (op.align !== "left") { var tm = g.text_measure(op.s); w = tm ? tm[0] : 0; }
            var x = op.x + dx - (op.align === "center" ? w / 2 : (op.align === "right" ? w : 0));
            g.move_to(x, op.y + dy);
            g.show_text(op.s);
        }
    }
}

// the whole layout: title first, then every system whose band is in view
function dr_layout(g, L, dx, dy, viewTop, viewBottom) {
    dr_ops(g, L.topOps, dx, dy);
    for (var i = 0; i < L.systems.length; i++) {
        var sy = L.systems[i];
        if (viewBottom !== undefined && (sy.y1 + dy < viewTop || sy.y0 + dy > viewBottom)) continue;
        dr_ops(g, L.sysOps[i], dx, dy);
    }
}

// ---- src/55_export.js
// ============================================================================
//  ex_ - exporting: Standard MIDI File, PDF, PNG and MusicXML
//
//  MIDI is written from the MODEL - the real notes, unquantized - because a
//  .mid is for another sequencer and should sound exactly like the clip.
//  Everything else is written from the ENGRAVING, because it is the score.
//
//  All text formats are kept pure ASCII (anything else becomes a character
//  reference or a PDF octal escape), so Max's File.writestring cannot change a
//  single byte on the way to disk - and a PDF's cross-reference table, which
//  counts bytes, stays right.
// ============================================================================

// ---------------------------------------------------------------- bytes
function ex_u16(n, out) { out.push((n >> 8) & 255, n & 255); }
function ex_u32(n, out) { out.push((n >>> 24) & 255, (n >> 16) & 255, (n >> 8) & 255, n & 255); }
function ex_vlq(n, out) {
    var b = [n & 127];
    n = Math.floor(n / 128);
    while (n > 0) { b.unshift((n & 127) | 128); n = Math.floor(n / 128); }
    for (var i = 0; i < b.length; i++) out.push(b[i]);
}
function ex_ascii(s) {
    var o = "";
    for (var i = 0; i < s.length; i++) {
        var c = s.charCodeAt(i);
        o += (c >= 32 && c < 127) ? s.charAt(i) : "?";
    }
    return o;
}

// ------------------------------------------------------------------ MIDI
// Format 0, 480 ticks per quarter. At one tick, note-offs go before note-ons,
// so a repeated note is released before it is struck again.
function ex_midiBytes(M, tempo, key, title) {
    var PPQ = 480, ev = [], i;
    for (i = 0; i < M.notes.length; i++) {
        var n = M.notes[i];
        if (n.m || n.d <= 0 || n.t < 0) continue;
        var on = cr_round(n.t * PPQ), off = cr_round((n.t + n.d) * PPQ);
        if (off <= on) off = on + 1;
        ev.push([on, 1, n.p, cr_clamp(cr_round(n.v), 1, 127)]);
        ev.push([off, 0, n.p, 64]);
    }
    ev = cr_sortBy(ev, function (e) { return e[0] * 1000 + e[1] * 200 + e[2]; });

    var tr = [], name = ex_ascii(title || "Spartito");
    tr.push(0, 0xFF, 0x03); ex_vlq(name.length, tr);
    for (i = 0; i < name.length; i++) tr.push(name.charCodeAt(i));
    var usq = cr_round(60000000 / (tempo > 0 ? tempo : 120));
    tr.push(0, 0xFF, 0x51, 3, (usq >> 16) & 255, (usq >> 8) & 255, usq & 255);
    var dd = 0, den = M.den;
    while (den > 1) { den = den / 2; dd++; }
    tr.push(0, 0xFF, 0x58, 4, M.num, dd, 24, 8);
    tr.push(0, 0xFF, 0x59, 2, key < 0 ? 256 + key : key, 0);
    var last = 0;
    for (i = 0; i < ev.length; i++) {
        ex_vlq(ev[i][0] - last, tr);
        last = ev[i][0];
        tr.push(ev[i][1] ? 0x90 : 0x80, ev[i][2], ev[i][3]);
    }
    tr.push(0, 0xFF, 0x2F, 0);

    var out = [0x4D, 0x54, 0x68, 0x64];
    ex_u32(6, out); ex_u16(0, out); ex_u16(1, out); ex_u16(PPQ, out);
    out.push(0x4D, 0x54, 0x72, 0x6B);
    ex_u32(tr.length, out);
    for (i = 0; i < tr.length; i++) out.push(tr[i]);
    return out;
}

// ------------------------------------------------------------ XML text
function ex_xmlEsc(s) {
    var o = "";
    for (var i = 0; i < s.length; i++) {
        var ch = s.charAt(i), c = s.charCodeAt(i);
        if (ch === "&") o += "&amp;";
        else if (ch === "<") o += "&lt;";
        else if (ch === ">") o += "&gt;";
        else if (ch === "\"") o += "&quot;";
        else if (c < 32) o += " ";
        else if (c > 126) o += "&#" + c + ";";
        else o += ch;
    }
    return o;
}

// ------------------------------------------------------------------ PDF
// A4, systems never split across pages, standard Type 1 fonts (Times), so no
// font has to be embedded and the file opens anywhere.
var ex_PW = 595.28, ex_PH = 841.89;

function ex_pdfStr(s) {
    var o = "(";
    for (var i = 0; i < s.length; i++) {
        var ch = s.charAt(i), c = s.charCodeAt(i);
        if (ch === "(" || ch === ")" || ch === "\\") o += "\\" + ch;
        else if (c >= 32 && c < 127) o += ch;
        else if (c >= 160 && c < 256) { var oc = c.toString(8); while (oc.length < 3) oc = "0" + oc; o += "\\" + oc; }
        else o += "?";
    }
    return o + ")";
}

function ex_pdfOps(ops, cmds, oy) {
    // y in the layout grows downwards; PDF's grows upwards from the page bottom
    function Y(y) { return cr_num(ex_PH - (y - oy), 2); }
    function path(P) {
        var i = 0, s = "";
        while (i < P.length) {
            var c = P[i];
            if (c === "M") { s += cr_num(P[i + 1]) + " " + Y(P[i + 2]) + " m\n"; i += 3; }
            else if (c === "L") { s += cr_num(P[i + 1]) + " " + Y(P[i + 2]) + " l\n"; i += 3; }
            else if (c === "C") {
                s += cr_num(P[i + 1]) + " " + Y(P[i + 2]) + " " + cr_num(P[i + 3]) + " " + Y(P[i + 4]) + " "
                   + cr_num(P[i + 5]) + " " + Y(P[i + 6]) + " c\n";
                i += 7;
            } else if (c === "Z") { s += "h\n"; i++; }
            else i++;
        }
        return s;
    }
    for (var i = 0; i < ops.length; i++) {
        var op = ops[i], col = cr_num(op.c[0], 3) + " " + cr_num(op.c[1], 3) + " " + cr_num(op.c[2], 3);
        if (op.k === "F") cmds.push(col + " rg\n" + path(op.d) + "f\n");
        else if (op.k === "S") cmds.push(col + " RG\n" + cr_num(op.w) + " w\n" + path(op.d) + "S\n");
        else if (op.k === "T") {
            var f = op.bold ? (op.italic ? "/F4" : "/F2") : (op.italic ? "/F3" : "/F1");
            // Times digits are exactly half an em; other text is close enough
            var w = op.s.length * op.size * 0.5;
            var x = op.x - (op.align === "center" ? w / 2 : (op.align === "right" ? w : 0));
            cmds.push(col + " rg\nBT " + f + " " + cr_num(op.size) + " Tf 1 0 0 1 " + cr_num(x) + " " + Y(op.y)
                      + " Tm " + ex_pdfStr(op.s) + " Tj ET\n");
        }
    }
}

// Returns the PDF as a string of byte-valued characters (all ASCII).
function ex_pdf(L) {
    var MARGIN = 42, usable = ex_PH - 2 * MARGIN - 18;
    var pages = [], cur = null, i;
    for (i = 0; i < L.systems.length; i++) {
        var sy = L.systems[i];
        var top = (i === 0) ? 0 : sy.y0;
        if (!cur || sy.y1 - cur.top > usable) {
            cur = { top: top, sys: [] };
            pages.push(cur);
        }
        cur.sys.push(i);
    }
    if (!pages.length) pages.push({ top: 0, sys: [] });

    var objs = [];          // index 0 is object 1
    objs.push("<< /Type /Catalog /Pages 2 0 R >>");
    objs.push("");          // pages, filled in below
    objs.push("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>");
    objs.push("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>");
    objs.push("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic /Encoding /WinAnsiEncoding >>");
    objs.push("<< /Type /Font /Subtype /Type1 /BaseFont /Times-BoldItalic /Encoding /WinAnsiEncoding >>");
    var kids = [];
    for (var p = 0; p < pages.length; p++) {
        var cmds = [];
        var oy = pages[p].top - MARGIN;
        if (p === 0) ex_pdfOps(L.topOps, cmds, oy);
        for (i = 0; i < pages[p].sys.length; i++) ex_pdfOps(L.sysOps[pages[p].sys[i]], cmds, oy);
        if (pages.length > 1) {
            var num = "" + (p + 1);
            cmds.push("0 0 0 rg\nBT /F1 9 Tf 1 0 0 1 " + cr_num(ex_PW / 2 - num.length * 2.25) + " 24 Tm "
                      + ex_pdfStr(num) + " Tj ET\n");
        }
        var content = cmds.join("");
        var pageObj = objs.length + 1, contObj = objs.length + 2;
        objs.push("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 " + cr_num(ex_PW) + " " + cr_num(ex_PH) + "]"
                  + " /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >>"
                  + " /Contents " + contObj + " 0 R >>");
        objs.push("<< /Length " + content.length + " >>\nstream\n" + content + "endstream");
        kids.push(pageObj + " 0 R");
    }
    objs[1] = "<< /Type /Pages /Kids [" + kids.join(" ") + "] /Count " + pages.length + " >>";

    var out = "%PDF-1.4\n", offsets = [];
    for (i = 0; i < objs.length; i++) {
        offsets.push(out.length);
        out += (i + 1) + " 0 obj\n" + objs[i] + "\nendobj\n";
    }
    var xref = out.length;
    out += "xref\n0 " + (objs.length + 1) + "\n0000000000 65535 f \n";
    for (i = 0; i < offsets.length; i++) {
        var o = "" + offsets[i];
        while (o.length < 10) o = "0" + o;
        out += o + " 00000 n \n";
    }
    out += "trailer\n<< /Size " + (objs.length + 1) + " /Root 1 0 R >>\nstartxref\n" + xref + "\n%%EOF\n";
    return out;
}

// ------------------------------------------------------------- MusicXML
var ex_TYPES = ["whole", "half", "quarter", "eighth", "16th", "32nd", "64th"];
var ex_ACC = { "-1": "flat", "0": "natural", "1": "sharp" };

// beam states per event, the same rules the drawing uses
function ex_beamStates(ms) {
    var st = {}, k, i, lv;
    for (k = 0; k < ms.beams.length; k++) {
        var g = ms.beams[k], levels = 1;
        for (i = 0; i < g.length; i++) if (g[i].type - 2 > levels) levels = g[i].type - 2;
        for (i = 0; i < g.length; i++) {
            var a = [i === 0 ? "begin" : (i === g.length - 1 ? "end" : "continue")];
            for (lv = 1; lv < levels; lv++) {
                if (g[i].type - 2 <= lv) continue;
                var nextHas = (i + 1 < g.length) && g[i + 1].type - 2 > lv;
                var prevHas = (i > 0) && g[i - 1].type - 2 > lv;
                if (nextHas && prevHas) a.push("continue");
                else if (nextHas) a.push("begin");
                else if (prevHas) a.push("end");
                else a.push(i === g.length - 1 ? "backward hook" : "forward hook");
            }
            st[g[i].eid] = a;
        }
    }
    return st;
}

// a pitch, or on a drum staff the position it is written at
function ex_pitchXml(n, perc) {
    if (perc) return "<unpitched><display-step>" + "CDEFGAB".charAt(n.letter) + "</display-step><display-octave>"
                     + n.oct + "</display-octave></unpitched>";
    return "<pitch><step>" + "CDEFGAB".charAt(n.letter) + "</step>" + (n.alter ? "<alter>" + n.alter + "</alter>" : "")
         + "<octave>" + n.oct + "</octave></pitch>";
}

function ex_noteheadXml(n) { return (n.head === "x" || n.head === "o") ? "<notehead>x</notehead>" : ""; }

function ex_musicxml(S, title) {
    var mi = S.mi, nst = S.staves.length, x = [], m, s, e, k, i;
    x.push("<?xml version=\"1.0\" encoding=\"UTF-8\"?>");
    x.push("<!DOCTYPE score-partwise PUBLIC \"-//Recordare//DTD MusicXML 3.1 Partwise//EN\" \"http://www.musicxml.org/dtds/partwise.dtd\">");
    x.push("<score-partwise version=\"3.1\">");
    x.push("<work><work-title>" + ex_xmlEsc(title || "") + "</work-title></work>");
    x.push("<identification><encoding><software>Spartito for Ableton Live</software></encoding></identification>");
    x.push("<part-list><score-part id=\"P1\"><part-name>" + (nst > 1 ? "Piano" : "Part") + "</part-name></score-part></part-list>");
    x.push("<part id=\"P1\">");
    for (m = 0; m < S.nBars; m++) {
        x.push("<measure number=\"" + (m + 1) + "\">");
        if (m === 0) {
            var at = "<attributes><divisions>" + TPQ + "</divisions><key><fifths>" + S.key + "</fifths></key>"
                   + "<time><beats>" + mi.num + "</beats><beat-type>" + mi.den + "</beat-type></time>";
            if (S.perc) at += "<clef><sign>percussion</sign><line>2</line></clef>";
            if (nst > 1 && !S.perc) at += "<staves>" + nst + "</staves>";
            for (s = 0; s < nst && !S.perc; s++) {
                var cl = S.staves[s].clef === "G" ? "<sign>G</sign><line>2</line>" : "<sign>F</sign><line>4</line>";
                at += "<clef" + (nst > 1 ? " number=\"" + (s + 1) + "\"" : "") + ">" + cl + "</clef>";
            }
            x.push(at + "</attributes>");
        }
        for (s = 0; s < nst; s++) {
            if (s > 0) x.push("<backup><duration>" + mi.barT + "</duration></backup>");
            var ms = S.staves[s].measures[m], voice = S.perc ? s + 1 : (s === 0 ? 1 : 5);
            var beams = ex_beamStates(ms);
            var staff = (nst > 1 && !S.perc) ? "<staff>" + (s + 1) + "</staff>" : "";
            var tupFirst = {}, tupLast = {};
            for (k = 0; k < ms.tuplets.length; k++) {
                tupFirst[ms.tuplets[k][0].eid] = 1;
                tupLast[ms.tuplets[k][ms.tuplets[k].length - 1].eid] = 1;
            }
            for (e = 0; e < ms.events.length; e++) {
                var ev = ms.events[e];
                var dots = "";
                for (i = 0; i < ev.dots; i++) dots += "<dot/>";
                var tm = ev.tup ? "<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>" : "";
                var tupN = "";
                if (tupFirst[ev.eid]) tupN += "<tuplet type=\"start\"/>";
                if (tupLast[ev.eid]) tupN += "<tuplet type=\"stop\"/>";
                if (ev.rest) {
                    x.push("<note><rest" + (ev.mrest ? " measure=\"yes\"" : "") + "/><duration>" + ev.L + "</duration>"
                           + "<voice>" + voice + "</voice>" + (ev.mrest ? "" : "<type>" + ex_TYPES[ev.type] + "</type>" + dots)
                           + tm + staff + (tupN ? "<notations>" + tupN + "</notations>" : "") + "</note>");
                    continue;
                }
                // acciaccaturas come before their chord, and take no time
                var gc = 0;
                for (k = 0; k < ev.notes.length; k++) {
                    var gr = ev.notes[k].grace;
                    if (!gr) continue;
                    x.push("<note><grace slash=\"yes\"/>" + (gc ? "<chord/>" : "")
                           + ex_pitchXml(gr, S.perc)
                           + "<voice>" + voice + "</voice><type>eighth</type>"
                           + (gr.acc !== null && gr.acc !== undefined ? "<accidental>" + ex_ACC["" + gr.acc] + "</accidental>" : "")
                           + "<stem>up</stem>" + ex_noteheadXml(gr) + staff + "</note>");
                    gc++;
                }
                for (k = 0; k < ev.notes.length; k++) {
                    var n = ev.notes[k];
                    var s1 = "<note>" + (k > 0 ? "<chord/>" : "")
                           + ex_pitchXml(n, S.perc)
                           + "<duration>" + ev.L + "</duration>"
                           + (n.tiePrev ? "<tie type=\"stop\"/>" : "") + (n.tieNext ? "<tie type=\"start\"/>" : "")
                           + "<voice>" + voice + "</voice><type>" + ex_TYPES[ev.type] + "</type>" + dots
                           + (n.acc !== null && n.acc !== undefined ? "<accidental>" + ex_ACC["" + n.acc] + "</accidental>" : "")
                           + tm + "<stem>" + (ev.type === 0 ? "none" : (ev.up ? "up" : "down")) + "</stem>"
                           + ex_noteheadXml(n) + staff;
                    if (k === 0 && beams[ev.eid]) {
                        for (i = 0; i < beams[ev.eid].length; i++) s1 += "<beam number=\"" + (i + 1) + "\">" + beams[ev.eid][i] + "</beam>";
                    }
                    var nota = (n.tiePrev ? "<tied type=\"stop\"/>" : "") + (n.tieNext ? "<tied type=\"start\"/>" : "")
                             + (k === 0 ? tupN : "") + (n.trill ? "<ornaments><trill-mark/></ornaments>" : "");
                    if (nota) s1 += "<notations>" + nota + "</notations>";
                    x.push(s1 + "</note>");
                }
            }
        }
        if (m === S.nBars - 1) x.push("<barline location=\"right\"><bar-style>light-heavy</bar-style></barline>");
        x.push("</measure>");
    }
    x.push("</part>");
    x.push("</score-partwise>");
    return x.join("\n") + "\n";
}

// ------------------------------------------------------------ to disk
// Max's File object. Written in chunks, and the end of the file is set to
// where writing stopped, so exporting over a longer file leaves no tail.
function ex_writeBytes(path, bytes) {
    var f = new File(path, "write");
    if (!f.isopen) return false;
    for (var i = 0; i < bytes.length; i += 4096) f.writebytes(bytes.slice(i, i + 4096));
    try { f.eof = f.position; } catch (e) {}
    f.close();
    return true;
}

function ex_writeText(path, str) {
    var f = new File(path, "write");
    if (!f.isopen) return false;
    for (var i = 0; i < str.length; i += 2048) f.writestring(str.substring(i, i + 2048));
    try { f.eof = f.position; } catch (e) {}
    f.close();
    return true;
}

// PNG: draw into an offscreen MGraphics, copy it into a Jitter matrix, and let
// the matrix write the file. Returns an error string, or "" on success.
function ex_png(L, path) {
    var w = Math.ceil(L.width), h = Math.ceil(L.height);
    var mg, img, mtx;
    try { mg = new MGraphics(w, h); } catch (e1) { return "no offscreen drawing here (" + e1 + ")"; }
    try { mg.relative_coords = 0; } catch (e2) {}
    mg.set_source_rgba(1, 1, 1, 1);
    mg.rectangle(0, 0, w, h);
    mg.fill();
    dr_layout(mg, L, 0, 0);
    try {
        img = new Image(mg);
        mtx = new JitterMatrix(4, "char", w, h);
        img.tonamedmatrix(mtx.name);
        mtx.exportimage(path, "png");
    } catch (e3) { return "image export failed (" + e3 + ")"; }
    try { img.freepeer(); } catch (e4) {}
    try { mtx.freepeer(); } catch (e5) {}
    return "";
}

// the file name a clip suggests: nothing a file system would refuse
function ex_fileName(name, ext) {
    var o = "", i;
    for (i = 0; i < name.length; i++) {
        var ch = name.charAt(i), c = name.charCodeAt(i);
        if (c < 32 || "\\/:*?\"<>|".indexOf(ch) >= 0) o += "_";
        else if (c > 126) o += "_";
        else o += ch;
    }
    while (o.length && (o.charAt(0) === " " || o.charAt(0) === ".")) o = o.substring(1);
    if (!o.length) o = "Spartito";
    if (o.length > 60) o = o.substring(0, 60);
    return o + "." + ext;
}

function ex_withExt(path, ext) {
    var low = path.toLowerCase(), dot = "." + ext;
    if (low.length >= dot.length && low.substring(low.length - dot.length) === dot) return path;
    if (ext === "musicxml" && low.substring(low.length - 4) === ".xml") return path;
    return path + dot;
}

// ---- src/60_live.js
// ============================================================================
//  lv_ - talking to Live (brain only)
//
//  The score and the clip are kept the same thing, in both directions:
//
//    * every edit made on the score is written into the clip at once - and
//      ONLY what changed is written: a dragged note is one remove and one add,
//      not a rewrite of a whole arrangement clip note by note;
//    * every change Live reports on the clip is read back into the score,
//      keeping the identity of the notes that did not change.
//
//  THE COST OF TALKING TO LIVE is what this file is organised around. Every
//  LiveAPI call runs on Max's main thread, and so does drawing the score, so
//  anything spent here is time the device - and Live - is not responding:
//
//    * objects that are asked again and again (the song, this track) are
//      created once and kept;
//    * whether Live is recording on this track is never ASKED: song
//      is_playing, record_mode and the track's arm are OBSERVED, and the patch
//      is told to open or close the gate the played notes pass through;
//    * our own write makes Live report "notes changed". That echo is not read
//      back straight away: reports within a short window of a write are held,
//      and ONE read afterwards checks that the clip holds what we wrote;
//    * reads are at least lv_SYNC_GAP ms apart, so a clip that is being
//      recorded in Session, which reports every note, is followed at a steady
//      few frames a second instead of being re-read on every note.
//
//  WHICH CLIP: the one in Live's Detail View. Clicking another MIDI clip
//  switches to it (after the last edit has gone into the old one); clicking
//  anything that is not a MIDI clip keeps the current one. With no clip, the
//  first note written creates a clip in the first empty slot of this track -
//  in Session only: in the Arrangement a slot clip would appear somewhere the
//  user is not looking, so there the device asks for a clip instead.
//
//  From Live 10.1's own LOM documentation (the one inside the installed Max):
//    Clip.get_notes, select_all_notes, deselect_all_notes,
//    replace_selected_notes + notes N + note ... + done, remove_notes,
//    Clip.notes / is_arrangement_clip, Clip.View.grid_quantization,
//    ClipSlot.create_clip, Song.View.detail_clip, Song.is_playing /
//    record_mode / current_song_time, Track.arm,
//    Application.View.focused_document_view.
// ============================================================================

var lv_viewApi = null, lv_obs = [], lv_songObs = [], lv_songApi = null, lv_trackApi = null;
var lv_clipId = 0;
var lv_pending = "";
var lv_started = false;
var lv_writtenEdit = -1;       // the model edit the clip is in step with
var lv_lastWrite = 0;
var lv_clipList = [];          // what we know the clip holds: [p, t, d, v, m]
var lv_echoUntil = 0;          // reports before this are (probably) our own write
var lv_lastSync = 0;
var lv_quiet = false;          // observers fire once when attached: ignore that
var lv_rec = { playing: 0, record: 0, arm: 0 };

var lv_ECHO_MS = 350;
var lv_SYNC_GAP = 200;
var lv_DIFF_MAX = 48;          // more changes than this: rewrite the clip

var lv_GRID = { 6: 24, 7: 24, 8: 12, 9: 6 };

function lv_now() { return new Date().getTime(); }

function lv_num(v) {
    if (v === undefined || v === null) return 0;
    if (typeof v === "object" && v.length !== undefined) v = v[0];
    var n = parseFloat(v);
    return isNaN(n) ? 0 : n;
}

function lv_str(v) {
    if (v === undefined || v === null) return "";
    if (typeof v === "object" && v.length !== undefined) {
        var a = [];
        for (var i = 0; i < v.length; i++) a.push("" + v[i]);
        return a.join(" ");
    }
    return "" + v;
}

function lv_idOf(api) {
    if (!api) return 0;
    var id = parseInt(api.id, 10);
    return isNaN(id) ? 0 : id;
}

function lv_idIn(args) {
    if (!args) return 0;
    for (var i = 0; i + 1 < args.length; i++) if (args[i] === "id") return parseInt(args[i + 1], 10) || 0;
    return 0;
}

function lv_parseNotes(res) {
    var out = [];
    if (!res) return out;
    for (var i = 0; i < res.length; i++) {
        if (res[i] === "note" && i + 5 < res.length) {
            out.push([lv_num(res[i + 1]), lv_num(res[i + 2]), lv_num(res[i + 3]), lv_num(res[i + 4]), lv_num(res[i + 5])]);
            i += 5;
        }
    }
    return out;
}

function lv_status(G, s) { G.status = s; G.statusTime = lv_now(); }

function lv_isMidiClip(id) {
    if (!id) return false;
    var c = new LiveAPI("id " + id);
    return lv_idOf(c) > 0 && lv_num(c.get("is_midi_clip")) === 1;
}

function lv_song() { if (!lv_songApi) lv_songApi = new LiveAPI("live_set"); return lv_songApi; }

// ------------------------------------------------------------ observers
function lv_start(G) {
    if (lv_started) return;
    lv_started = true;
    try {
        var sn = lv_num(lv_song().get("signature_numerator")), sd = lv_num(lv_song().get("signature_denominator"));
        if (sn && sd && !G.M.clipTag) { G.M.num = sn; G.M.den = sd; md_touch(G.M); }
    } catch (e) {}
    lv_quiet = true;
    lv_viewApi = new LiveAPI(lv_onDetailClip, "live_set view");
    lv_viewApi.property = "detail_clip";
    try {
        var a1 = new LiveAPI(lv_onSong, "live_set"); a1.property = "is_playing"; lv_songObs.push(a1);
        var a2 = new LiveAPI(lv_onSong, "live_set"); a2.property = "record_mode"; lv_songObs.push(a2);
        lv_trackApi = new LiveAPI("this_device canonical_parent");
        if (lv_idOf(lv_trackApi)) {
            var a3 = new LiveAPI(lv_onSong, "this_device canonical_parent"); a3.property = "arm"; lv_songObs.push(a3);
        }
        lv_rec.playing = lv_num(lv_song().get("is_playing"));
        lv_rec.record = lv_num(lv_song().get("record_mode"));
        lv_rec.arm = lv_idOf(lv_trackApi) ? lv_num(lv_trackApi.get("arm")) : 0;
    } catch (e2) {}
    lv_quiet = false;
    var id = lv_idOf(new LiveAPI("live_set view detail_clip"));
    if (lv_isMidiClip(id)) lv_load(G, id);
    else lv_status(G, "Click a MIDI clip in Live - or just write: a clip is created on this track.");
    lv_writtenEdit = G.M.editVersion;
    lv_recChanged();
}

function lv_onDetailClip(args) {
    if (lv_quiet) return;
    var id = lv_idIn(args);
    // while a recorded take is shown, clicking even the same clip goes back to it
    if (!lv_started || !id || (id === lv_clipId && !G.capture)) return;
    lv_pending = "detail " + id;
    lv_kick();
}

function lv_onClip(args) {
    if (lv_quiet || !lv_started || !args) return;
    var what = args[0];
    if (what !== "notes" && what !== "signature_numerator" && what !== "signature_denominator"
        && what !== "loop_end" && what !== "name") return;
    if (lv_pending === "") lv_pending = "notes";
    lv_kick();
}

function lv_onPlay(args) {
    if (lv_quiet || !args || args[0] !== "playing_position") return;
    if (!lv_rec.playing) return;
    lv_playhead(lv_num(args[1]));
}

// is_playing, record_mode, arm: all three arrive here
function lv_onSong(args) {
    if (lv_quiet || !args) return;
    var v = lv_num(args[1]);
    if (args[0] === "is_playing") { lv_rec.playing = v; if (!v) lv_playhead(-1); }
    else if (args[0] === "record_mode") lv_rec.record = v;
    else if (args[0] === "arm") lv_rec.arm = v;
    else return;
    lv_recChanged();
}

// recording in the Arrangement on this track, from the observed state alone
function lv_recordingHere() { return !!(lv_rec.playing && lv_rec.record && lv_rec.arm); }

function lv_attach(G, id) {
    for (var i = 0; i < lv_obs.length; i++) { try { lv_obs[i].property = ""; } catch (e) {} }
    lv_obs = [];
    lv_clipId = id;
    G.target = "";
    if (!id) return;
    G.target = lv_str(new LiveAPI("id " + id).get("name")) || "untitled clip";
    // setting .property makes Live report the current value at once
    lv_quiet = true;
    var props = ["notes", "signature_numerator", "signature_denominator", "loop_end", "name"];
    for (i = 0; i < props.length; i++) {
        var a = new LiveAPI(lv_onClip, "id " + id);
        a.property = props[i];
        lv_obs.push(a);
    }
    var pp = new LiveAPI(lv_onPlay, "id " + id);
    pp.property = "playing_position";
    lv_obs.push(pp);
    lv_quiet = false;
}

function lv_clipData(c) {
    var loopStart = lv_num(c.get("loop_start")), loopEnd = lv_num(c.get("loop_end"));
    var startM = lv_num(c.get("start_marker")), endM = lv_num(c.get("end_marker"));
    var endB = Math.max(loopEnd, endM), from = Math.min(0, loopStart, startM);
    var d = {
        list: lv_parseNotes(c.call("get_notes", from, 0, endB - from + 10000, 128)),
        num: lv_num(c.get("signature_numerator")) || 4,
        den: lv_num(c.get("signature_denominator")) || 4,
        endB: endB, name: lv_str(c.get("name")), quant: 12
    };
    try {
        var vid = lv_idIn(c.get("view"));
        if (vid) d.quant = lv_GRID[lv_num(new LiveAPI("id " + vid).get("grid_quantization"))] || 12;
    } catch (e) {}
    return d;
}

function lv_applyGrid(G, q) {
    if (G.quant !== q) { G.quant = q; G.optVersion++; }
}

function lv_key(n) { return n[0] + "|" + Math.round(n[1] * 1e5) + "|" + Math.round(n[2] * 1e5) + "|" + Math.round(n[3]) + "|" + (n[4] ? 1 : 0); }

function lv_sameNotes(a, b) {
    if (a.length !== b.length) return false;
    var count = {}, i, k;
    for (i = 0; i < a.length; i++) { k = lv_key(a[i]); count[k] = (count[k] || 0) + 1; }
    for (i = 0; i < b.length; i++) { k = lv_key(b[i]); if (!count[k]) return false; count[k]--; }
    return true;
}

// How long before a held report may be read, in ms (0 = now).
function lv_waitMs() {
    if (lv_pending !== "notes") return 0;
    var now = lv_now();
    return Math.max(0, lv_echoUntil - now, lv_lastSync + lv_SYNC_GAP - now);
}

// Work queued by the observers, done outside their callbacks. A report that
// may not be read yet stays pending; the brain asks lv_waitMs when to retry.
function lv_service(G) {
    var p = lv_pending;
    if (p === "") return "";
    if (p.indexOf("detail ") === 0) {
        lv_pending = "";
        var id = parseInt(p.substring(7), 10) || 0;
        if (!lv_isMidiClip(id)) return "";
        // the last edit belongs to the clip it was made on
        if (lv_clipId && G.M.editVersion !== lv_writtenEdit) lv_write(G);
        if (G.capture && !G.capLive) { G.capture = 0; G.optVersion++; }
        return lv_load(G, id) ? "read" : "";
    }
    if (p === "notes") {
        if (G.M.editVersion !== lv_writtenEdit) return "";      // a write is on its way; it will be checked after
        if (lv_waitMs() > 0) return "";
        lv_pending = "";
        lv_lastSync = lv_now();
        return lv_syncFromClip(G) ? "read" : "";
    }
    lv_pending = "";
    return "";
}

function lv_load(G, id) {
    var c = new LiveAPI("id " + id);
    var d = lv_clipData(c);
    md_load(G.M, d.list, d.num, d.den, d.endB, d.name, "" + id);
    lv_clipList = d.list;
    lv_applyGrid(G, d.quant);
    lv_attach(G, id);
    lv_writtenEdit = G.M.editVersion;
    lv_lastSync = lv_now();
    lv_status(G, "Showing \"" + (d.name || "untitled clip") + "\" - every change goes straight into it.");
    return true;
}

function lv_syncFromClip(G) {
    if (!lv_clipId) return false;
    var c = new LiveAPI("id " + lv_clipId);
    if (!lv_idOf(c)) {
        lv_attach(G, 0);
        lv_clipList = [];
        lv_status(G, "The clip is gone. Write a note to create a new one, or click a clip.");
        return true;
    }
    var d = lv_clipData(c), M = G.M;
    var gridChanged = G.quant !== d.quant;
    lv_applyGrid(G, d.quant);
    G.target = d.name || "untitled clip";
    lv_clipList = d.list;
    if (d.num === M.num && d.den === M.den && d.name === M.name && d.endB === M.lenBeats
        && lv_sameNotes(d.list, md_exportList(M))) return gridChanged;
    md_sync(M, d.list, d.num, d.den, d.endB, d.name);
    lv_writtenEdit = M.editVersion;
    return true;
}

// -------------------------------------------------------------- writing
// What changed between what the clip holds and what the score holds.
function lv_diff(oldList, newList) {
    var have = {}, i, k, removed = [], added = [];
    for (i = 0; i < oldList.length; i++) { k = lv_key(oldList[i]); (have[k] = have[k] || []).push(oldList[i]); }
    for (i = 0; i < newList.length; i++) {
        k = lv_key(newList[i]);
        if (have[k] && have[k].length) have[k].pop();
        else added.push(newList[i]);
    }
    for (k in have) for (i = 0; i < have[k].length; i++) removed.push(have[k][i]);
    return { removed: removed, added: added };
}

function lv_sendNotes(c, list) {
    c.call("notes", list.length);
    for (var i = 0; i < list.length; i++) {
        var n = list[i];
        c.call("note", n[0], n[1].toFixed(6), n[2].toFixed(6), cr_clamp(cr_round(n[3]), 1, 127), n[4] ? 1 : 0);
    }
    c.call("done");
}

function lv_write(G) {
    var M = G.M;
    lv_writtenEdit = M.editVersion;
    lv_lastWrite = lv_now();
    var bar = M.num * 4 / M.den;
    var endBeats = Math.ceil(Math.max(M.lenBeats, md_endBeats(M)) / bar - 1e-9) * bar;
    if (endBeats <= 0) endBeats = bar;

    var c = lv_isMidiClip(lv_clipId) ? new LiveAPI("id " + lv_clipId) : null;
    var created = false;
    if (!c) {
        c = lv_createOnOwnTrack(G, endBeats);
        if (!c) return false;
        created = true;
        lv_clipList = [];
    }

    var list = md_exportList(M), i;
    var diff = lv_diff(lv_clipList, list);
    lv_echoUntil = lv_now() + lv_ECHO_MS;
    if (diff.removed.length + diff.added.length === 0) {
        // nothing to write
    } else if (diff.removed.length + diff.added.length > lv_DIFF_MAX) {
        c.call("select_all_notes");
        c.call("replace_selected_notes");
        lv_sendNotes(c, list);
        c.call("deselect_all_notes");
    } else {
        // remove_notes deletes the notes that START in the area; a note of one
        // pitch at one start time is unique in a clip, so the area can be tiny
        for (i = 0; i < diff.removed.length; i++) {
            var r = diff.removed[i];
            c.call("remove_notes", (r[1] - 0.0001).toFixed(6), r[0], "0.000200", 1);
        }
        if (diff.added.length) {
            c.call("deselect_all_notes");
            c.call("replace_selected_notes");
            lv_sendNotes(c, diff.added);
        }
    }
    lv_clipList = list;
    lv_echoUntil = lv_now() + lv_ECHO_MS;

    // room for notes written past the end; a clip is never shortened
    try {
        if (lv_num(c.get("looping")) && lv_num(c.get("loop_end")) < endBeats) c.set("loop_end", endBeats);
        if (lv_num(c.get("end_marker")) < endBeats) c.set("end_marker", endBeats);
    } catch (e) {}
    if (M.lenBeats < endBeats) { M.lenBeats = endBeats; md_touch(M); }

    if (created) {
        var sn = lv_num(c.get("signature_numerator")), sd = lv_num(c.get("signature_denominator"));
        if (sn && sd && (sn !== M.num || sd !== M.den)) { M.num = sn; M.den = sd; md_touch(M); }
        M.clipTag = "" + lv_clipId;
        lv_status(G, "Created a clip on this track: every change now goes into it.");
    }
    // the check that the clip really holds this, once the echo has passed
    if (lv_pending === "") lv_pending = "notes";
    return true;
}

function lv_createOnOwnTrack(G, len) {
    try {
        if (lv_str(new LiveAPI("live_app view").get("focused_document_view")) === "Arranger") {
            lv_status(G, "In the Arrangement: create or select a MIDI clip there first (Ctrl+Shift+M), then write.");
            return null;
        }
    } catch (e0) {}
    var track = lv_trackApi || new LiveAPI("this_device canonical_parent");
    if (!lv_idOf(track)) { lv_status(G, "Click a MIDI clip in Live to write into it."); return null; }
    var n = track.getcount("clip_slots");
    for (var i = 0; i < n; i++) {
        var slot = new LiveAPI("this_device canonical_parent clip_slots " + i);
        if (lv_num(slot.get("has_clip"))) continue;
        slot.call("create_clip", len);
        var cid = lv_idIn(slot.get("clip"));
        if (!cid) continue;
        lv_attach(G, cid);
        try { new LiveAPI("live_set view").set("highlighted_clip_slot", "id", lv_idOf(slot)); } catch (e1) {}
        try { new LiveAPI("live_set view").set("detail_clip", "id", cid); } catch (e2) {}
        return new LiveAPI("id " + cid);
    }
    lv_status(G, "No empty clip slot on this track: add a scene, or click a MIDI clip.");
    return null;
}

function lv_songTime() { return lv_num(lv_song().get("current_song_time")); }

function lv_tempo() {
    try { return lv_num(lv_song().get("tempo")) || 120; } catch (e) { return 120; }
}

// ---- src/65_brain.js
// ============================================================================
//  br_ - the brain: shared state, Live, exports
//
//  One file, three roles, decided by how the object was created:
//
//    [js spartito.js brain]   the BRAIN. A plain js object always runs, so it
//                             owns the state, talks to Live and writes files.
//    [jsui] in the editor     the EDITOR view. A jsui that has never been drawn
//    [jsui] on the strip      does not run at all (measured), so the views
//                             hold nothing that matters: they ask the brain
//                             for the name of the shared state, and keep
//                             asking until they get it.
//
//  The state is one object in a Max Global, named uniquely per device. Views
//  edit the model in it directly and then send "changed"; the brain redraws
//  every view and writes the edit into the clip.
//
//  Messages the brain answers:
//    liveready              live.thisdevice has banged: Live can be asked
//    hello                  a view wants the state's name
//    changed                a view edited or selected something
//    setparam <name> <v>    a stored setting came back from Live
//    uiparam <name> <v>     the editor changed a setting; stored in the set
//    exportfmt <fmt>        ask where to save; exportpath <path> is the answer
//    audition <p> <v> <ms>  play a note through the track
//    openwin / openurl      the editor window / the website
//    demo                   load the demonstration piece
//    selftest <folder>      write every export there and report (test harness)
// ============================================================================

var ROLE = (typeof jsarguments !== "undefined" && jsarguments.length > 1) ? ("" + jsarguments[1]) : "view";
inlets = 1;
outlets = (ROLE === "brain") ? 3 : 1;

var G = null;
var UID = "";
var br_gObj = null;

var br_SP = [7, 9, 11, 14];                         // staff space per zoom step
var br_STAVES = ["piano", "treble", "bass", "drums"];

function br_newState() {
    return {
        M: md_new(),
        opt: { key: 0, staves: 0, zoom: 1, vel: 100, hear: 1, win: 1 },
        optVersion: 1,
        quant: 12,                                  // from the clip's grid
        status: "", statusTime: 0,
        target: "",
        play: -1,
        capture: 0,                                 // a recorded take is shown instead of the clip
        capLive: 0,                                 // ...and it is still being recorded
        CM: null, cap: null
    };
}

// The engraving options. There is nothing to choose any more: triplets are
// always recognised (the 3 button writes them), and a note sounding past the
// next chord is always shown as long as it really is, tied.
function br_nopts(extraBar) {
    var o = G.opt;
    // the grand staff always divides at middle C: from C4 (Live's C3) up is treble
    return { key: o.key, split: 60, staves: br_STAVES[o.staves] || "piano", quant: G.quant || 12,
             tuplets: true, overlap: "tie", extraBar: !!extraBar };
}

if (ROLE === "brain") {
    UID = "spartito_" + Math.floor(Math.random() * 1000000000);
    if (typeof Global !== "undefined") {
        br_gObj = new Global(UID);
        br_gObj.state = br_newState();
        G = br_gObj.state;
    } else {
        G = br_newState();
    }
}

var br_task = (typeof Task !== "undefined") ? new Task(br_tick, this) : null;
var br_playTask = (typeof Task !== "undefined") ? new Task(br_playFlush, this) : null;
var br_writeTask = (typeof Task !== "undefined") ? new Task(br_flushWrite, this) : null;
var br_writeQueued = false;
var br_pendingFmt = "";
var br_lastPlaySent = 0;
var br_playValue = -1;

function br_isBrain() { return ROLE === "brain" && G; }

function br_update() {
    if (ROLE !== "brain") return;
    outlet(0, "update");
}

function lv_kick() { if (br_task) br_task.schedule(Math.max(20, lv_waitMs())); else br_tick(); }

function br_tick() {
    if (!br_isBrain()) return;
    var r = lv_service(G);
    // a report that may not be read yet: come back when it may
    if (lv_pending !== "" && br_task) br_task.schedule(Math.max(20, lv_waitMs()));
    if (r) br_update();
}

// Every edit goes into the clip - at most every 120 ms while a note is being
// dragged, so Live is not asked to rewrite a clip fifty times a second.
function br_scheduleWrite() {
    if (!lv_started || G.M.editVersion === lv_writtenEdit) return;
    if (!br_writeTask) { br_flushWrite(); return; }
    if (br_writeQueued) return;
    br_writeQueued = true;
    br_writeTask.schedule(Math.max(25, 120 - (lv_now() - lv_lastWrite)));
}

function br_flushWrite() {
    br_writeQueued = false;
    if (!br_isBrain() || !lv_started || G.M.editVersion === lv_writtenEdit) return;
    try { lv_write(G); }
    catch (e) { lv_writtenEdit = G.M.editVersion; lv_status(G, "Could not write the clip: " + e); }
    br_update();
}

// The playhead: at most about 12 times a second. Every one of these makes
// both views repaint, and a repaint of a full page of music is not free.
var br_PLAY_MS = 80;

function lv_playhead(beats) {
    if (G && G.capLive) return;                     // the take moves its own playhead
    br_playValue = beats < 0 ? -1 : beats * TPQ;
    if (!br_playTask) { br_playFlush(); return; }
    if (lv_now() - br_lastPlaySent > br_PLAY_MS || br_playValue < 0) br_playFlush();
    else br_playTask.schedule(br_PLAY_MS);
}

function br_playFlush() {
    if (!br_isBrain()) return;
    br_lastPlaySent = lv_now();
    G.play = br_playValue;
    outlet(0, "play", br_playValue);
}

// ------------------------------------------------------------- messages
function liveready() {
    if (!br_isBrain()) return;
    try { lv_start(G); } catch (e) { lv_status(G, "Live API not available: " + e); }
    br_update();
}

function hello() {
    if (!br_isBrain()) return;
    outlet(0, "uid", UID);
}

function changed() {
    if (!br_isBrain()) return;
    br_update();
    br_scheduleWrite();
}

function br_setOpt(name, v) {
    var o = G.opt;
    v = +v;
    if (name === "key") o.key = cr_clamp(Math.floor(v), 0, 14) - 7;
    else if (name === "staves") o.staves = cr_clamp(Math.floor(v), 0, 3);
    else if (name === "zoom") o.zoom = cr_clamp(Math.floor(v), 0, 3);
    else if (name === "vel") o.vel = cr_clamp(Math.floor(v), 1, 127);
    else if (name === "hear") o.hear = v ? 1 : 0;
    else if (name === "win") o.win = cr_clamp(Math.floor(v), 0, 2);
    else return false;
    G.optVersion++;
    return true;
}

function br_optToParam(name) {
    if (name === "key") return G.opt.key + 7;
    return G.opt[name];
}

function setparam(name, v) {
    if (!br_isBrain()) return;
    if (br_setOpt("" + name, v)) br_update();
}

function uiparam(name, v) {
    if (!br_isBrain()) { outlet(0, "uiparam", name, v); return; }
    if (!br_setOpt("" + name, v)) return;
    outlet(2, "param", "" + name, br_optToParam("" + name));
    br_update();
}

function audition(p, v, ms) {
    if (!br_isBrain()) { outlet(0, "audition", p, v, ms); return; }
    if (!G.opt.hear) return;
    outlet(1, cr_clamp(Math.floor(p), 0, 127), cr_clamp(Math.floor(v), 1, 127), Math.max(30, Math.floor(ms)));
}

function openwin() {
    if (!br_isBrain()) { outlet(0, "openwin"); return; }
    outlet(2, "open");
}

function openurl() {
    if (!br_isBrain()) { outlet(0, "openurl"); return; }
    outlet(2, "web");
}

var br_EXT = { midi: "mid", pdf: "pdf", png: "png", xml: "musicxml" };

function exportfmt(fmt) {
    fmt = "" + fmt;
    if (!br_isBrain()) { outlet(0, "exportfmt", fmt); return; }
    if (!br_EXT[fmt]) return;
    br_pendingFmt = fmt;
    outlet(2, "dialog", ex_fileName(G.M.name || "Spartito", br_EXT[fmt]));
}

function exportpath() {
    if (!br_isBrain() || !br_pendingFmt) return;
    var a = [];
    for (var i = 0; i < arguments.length; i++) a.push("" + arguments[i]);
    var path = a.join(" ");
    if (!path || path === "0") return;
    var fmt = br_pendingFmt;
    br_pendingFmt = "";
    var err = br_export(fmt, path);
    lv_status(G, err ? "Export failed: " + err : "Exported " + ex_withExt(path, br_EXT[fmt]).replace(/^.*[\/\\]/, "") + ".");
    br_update();
}

function br_layoutFor(fmt) {
    var MM = br_model(), bo = br_barOffset();
    var S = nt_engrave(MM, br_nopts(false));
    var title = MM.name || "";
    var ink = [0, 0, 0, 1];
    if (fmt === "pdf") {
        return { S: S, L: ly_layout(S, { width: ex_PW, sp: 5.0, marginL: 60, marginR: 42, top: 0, bottom: 0,
                                         title: title, ink: ink, selc: ink, finalBar: true, barOffset: bo }) };
    }
    if (fmt === "png") {
        var sp = 14, L = null;
        for (var k = 0; k < 4; k++) {
            L = ly_layout(S, { width: 2000 * sp / 14, sp: sp, marginL: 4 * sp, marginR: 3 * sp, top: 2 * sp, bottom: 3 * sp,
                               title: title, ink: ink, selc: ink, finalBar: true, barOffset: bo });
            if (L.height < 12000) break;
            sp = Math.max(6, sp * 0.7);
        }
        return { S: S, L: L };
    }
    return { S: S, L: null };
}

function br_export(fmt, path) {
    path = ex_withExt(path, br_EXT[fmt]);
    try {
        if (fmt === "midi") {
            return ex_writeBytes(path, ex_midiBytes(br_model(), lv_started ? lv_tempo() : 120, G.opt.key, br_model().name)) ? "" : "cannot write the file";
        }
        var LS = br_layoutFor(fmt);
        if (fmt === "pdf") return ex_writeText(path, ex_pdf(LS.L)) ? "" : "cannot write the file";
        if (fmt === "xml") return ex_writeText(path, ex_musicxml(LS.S, G.M.name)) ? "" : "cannot write the file";
        if (fmt === "png") {
            var err = ex_png(LS.L, path);
            if (err && ROLE === "brain") { outlet(0, "renderpng", path); return ""; }
            return err;
        }
    } catch (e) { return "" + e; }
    return "unknown format";
}

// --------------------------------------------------- demonstration piece
function br_demoNotes(M) {
    function n(p, t, d, v) { var x = md_note(M, p, t, d, v || 96, 0, 0); M.notes.push(x); return x; }
    var arp = [72, 76, 79, 84, 79, 76, 72, 67], i;
    for (i = 0; i < 8; i++) n(arp[i], i * 0.5, 0.5, 80 + i * 4);
    n(48, 0, 4); n(52, 0, 4); n(55, 0, 4);
    n(74, 4, 1 / 3); n(78, 4 + 1 / 3, 1 / 3); n(81, 4 + 2 / 3, 1 / 3);
    var trilled = n(79, 5, 1);
    n(77, 6, 0.75); n(76, 6.75, 0.25);
    n(72, 7, 1); n(74, 7, 1); n(77, 7, 1);
    n(43, 4, 2); n(50, 4, 2); n(41, 6, 2); n(48, 6, 2);
    var graced = n(76, 8, 0.5);
    n(77, 8.5, 1); n(79, 9.5, 0.5);
    var run = [72, 74, 70, 69];
    for (i = 0; i < 4; i++) n(run[i], 11 + i * 0.25, 0.25);
    n(36, 8, 1); n(43, 9, 1); n(48, 10, 2);
    n(84, 12, 2); n(91, 14, 0.5); n(93, 14.5, 0.5); n(88, 15, 1.5); n(86, 16.5, 0.5); n(84, 17, 3);
    n(29, 12, 4); n(36, 16, 2); n(33, 18, 2);
    md_trill(M, trilled, 0);
    md_addGrace(M, graced, 0);
    M.lenBeats = 20;
}

function demo() {
    if (!G) return;
    md_load(G.M, [], 4, 4, 20, "Demo", "");
    br_demoNotes(G.M);
    md_changed(G.M);
    if (ROLE === "brain") { lv_status(G, "Demonstration piece loaded."); br_update(); }
}

// -------------------------------------------------------------- self test
function selftest() {
    if (!br_isBrain()) return;
    var a = [];
    for (var i = 0; i < arguments.length; i++) a.push("" + arguments[i]);
    var dir = a.join(" ");
    if (dir.charAt(dir.length - 1) !== "/") dir += "/";
    var lines = [];
    demo();
    lines.push("notes " + G.M.notes.length);
    var fmts = ["midi", "pdf", "xml", "png"];
    for (i = 0; i < fmts.length; i++) {
        var t0 = lv_now();
        var err = br_export(fmts[i], dir + "selftest");
        lines.push("export " + fmts[i] + " " + (err ? "ERROR " + err : "ok") + " " + (lv_now() - t0) + "ms");
    }
    ex_writeText(dir + "truncate.txt", "0123456789012345678901234567890123456789");
    ex_writeText(dir + "truncate.txt", "short");
    var f = new File(dir + "truncate.txt", "read");
    lines.push("truncate eof " + (f.isopen ? f.eof : -1));
    if (f.isopen) f.close();
    lines.push.apply(lines, br_benchLines());
    lines.push("mgraphics-in-js " + (typeof MGraphics));
    var rep = new File(dir + "selftest_brain.txt", "write");
    if (rep.isopen) {
        for (i = 0; i < lines.length; i++) rep.writeline(lines[i]);
        try { rep.eof = rep.position; } catch (e) {}
        rep.close();
    }
    outlet(0, "update");
}

// ------------------------------------------------ recording in Arrangement
// Live 10's API cannot reach the clip being recorded in the Arrangement, so
// the notes played INTO the device become a take shown in place of the clip.
//
// The path is built to cost nothing when nothing records:
//
//    * the patch sends played notes on only through a [gate] the brain opens
//      when Live is playing, the Arrangement record button is on and this
//      track is armed - all three observed, never asked (lv_recChanged);
//    * each note is stamped in the patch by [transport] with Live's song
//      position, before the deferlow, so the time is the time it was played;
//    * a note only changes the take. A 100 ms tick grows the held notes,
//      moves the playhead and - at most every br_CAP_VIEW_MS - rebuilds the
//      view, which shows only the last br_CAP_BARS bars while recording.
//      Engraving the whole take on every note is what made recording lag.
//
// When recording stops the whole take is shown. It stays until a clip is
// clicked (the recorded one, typically) or BACK TO CLIP. It is not editable:
// it is not a clip yet.

var br_capTask = (typeof Task !== "undefined") ? new Task(br_capTick, this) : null;
var br_CAP_BARS = 8;
var br_CAP_VIEW_MS = 120;

// what the views and the exports show
function br_model() {
    if (!G) return null;
    if (G.capture && G.capLive && G.CV) return G.CV;
    return (G.capture && G.CM) ? G.CM : G.M;
}
function br_barOffset() {
    if (!G || !G.capture || !G.cap) return 0;
    return G.cap.startBar + (G.capLive && G.CV ? G.cap.viewBar : 0);
}

// Live's recording state changed (observed): open or close the gate, and end
// a take the moment recording stops.
function lv_recChanged() {
    if (!br_isBrain()) return;
    var on = lv_recordingHere();
    outlet(2, "capgate", on ? 1 : 0);
    if (!on && G.capLive) br_capStop();
}

// capture <pitch> <velocity> <ticks> <ticks per quarter>, from the patch
function capture(p, v, ticks, res) {
    if (!br_isBrain() || !lv_started) return;
    var beats = (+ticks) / ((+res) > 0 ? +res : 480);
    p = Math.floor(+p); v = Math.floor(+v);
    if (!G.capLive) {
        if (v <= 0 || !lv_recordingHere()) return;
        br_capStart(beats);
    }
    var C = G.cap;
    // earlier than the take's first bar: loop recording went round, or a
    // pickup. Move the origin back and keep everything already played.
    if (beats < C.origin - 1e-6) br_capShift(Math.max(0, Math.floor(beats / C.bar + 1e-9)));
    var t = beats - C.origin;
    if (v > 0) {
        if (C.open[p]) C.open[p].d = Math.max(0.02, t - C.open[p].t);
        var n = md_note(G.CM, p, Math.max(0, t), 0.05, v, 0, 0);
        G.CM.notes.push(n);
        C.open[p] = n;
    } else if (C.open[p]) {
        C.open[p].d = Math.max(0.02, t - C.open[p].t);
        delete C.open[p];
    }
    br_capGrow(t);
    C.lastT = Math.max(C.lastT, t);
    C.dirty = 1;
}

function br_capStart(beats) {
    var num = 4, den = 4;
    try {
        num = lv_num(lv_song().get("signature_numerator")) || 4;
        den = lv_num(lv_song().get("signature_denominator")) || 4;
    } catch (e) {}
    var bar = num * 4 / den, startBar = Math.max(0, Math.floor(beats / bar + 1e-9));
    G.CM = md_new();
    G.CM.num = num; G.CM.den = den; G.CM.lenBeats = bar; G.CM.name = "";
    G.CV = null;
    G.cap = { origin: startBar * bar, bar: bar, startBar: startBar, open: {}, lastT: 0, dirty: 1,
              viewBar: 0, viewAt: 0 };
    G.capture = 1; G.capLive = 1;
    G.optVersion++;
    lv_status(G, "Recording in the Arrangement from bar " + (startBar + 1) + ".");
    br_capView(true);
    if (br_capTask) { br_capTask.interval = 100; br_capTask.repeat(); }
}

function br_capShift(newStartBar) {
    var C = G.cap, delta = (C.startBar - newStartBar) * C.bar;
    if (delta <= 0) return;
    for (var i = 0; i < G.CM.notes.length; i++) G.CM.notes[i].t += delta;
    C.startBar = newStartBar; C.origin = newStartBar * C.bar;
    C.lastT += delta;
    G.CM.lenBeats += delta;
}

function br_capGrow(t) {
    var need = Math.ceil((t + 0.001) / G.cap.bar) * G.cap.bar;
    if (need > G.CM.lenBeats) G.CM.lenBeats = need;
}

// the view of a take being recorded: its last bars only
function br_capView(force) {
    var C = G.cap, now = lv_now();
    if (!force && (!C.dirty || now - C.viewAt < br_CAP_VIEW_MS)) return false;
    var lastBar = Math.floor(Math.max(0, C.lastT - 1e-6) / C.bar);
    C.viewBar = Math.max(0, lastBar - br_CAP_BARS + 1);
    G.CV = md_window(G.CM, C.viewBar, Math.min(br_CAP_BARS, lastBar + 1));
    G.CV.version = ++G.CM.version;
    C.dirty = 0;
    C.viewAt = now;
    return true;
}

function br_capTick() {
    if (!br_isBrain() || !G.capLive) { if (br_capTask) br_capTask.cancel(); return; }
    if (!lv_recordingHere()) { br_capStop(); return; }
    var now = 0;
    try { now = lv_songTime(); } catch (e) {}
    var C = G.cap, t = now - C.origin;
    if (t >= 0) {
        var held = false;
        for (var k in C.open) { C.open[k].d = Math.max(0.02, t - C.open[k].t); held = true; }
        br_capGrow(t);
        if (held || t > C.lastT + 0.001) {
            if (Math.floor(t / C.bar) !== Math.floor(C.lastT / C.bar) || held) C.dirty = 1;
            C.lastT = Math.max(C.lastT, t);
        }
    }
    var viewChanged = br_capView(false);
    G.play = (t >= 0 && G.CV) ? (t - C.viewBar * C.bar) * TPQ : -1;
    if (viewChanged) br_update();
    else outlet(0, "play", G.play);
}

function br_capStop() {
    G.capLive = 0;
    if (br_capTask) br_capTask.cancel();
    var t = G.cap.lastT;
    for (var k in G.cap.open) { var o = G.cap.open[k]; if (t > o.t) o.d = Math.max(0.02, t - o.t); }
    G.cap.open = {};
    G.CV = null;
    G.play = -1;
    md_changed(G.CM);
    if (G.CM.notes.length) {
        lv_status(G, "Take recorded: " + G.CM.notes.length + " notes. Click the new clip in the Arrangement to edit it.");
    } else {
        G.capture = 0;
    }
    G.optVersion++;
    br_update();
}

function capclose() {
    if (!br_isBrain()) { outlet(0, "capclose"); return; }
    if (G.capLive) return;
    G.capture = 0;
    G.optVersion++;
    br_update();
}

// Engraving cost measured inside Max itself, for the harness report.
function br_benchLines() {
    var out = [], M = md_new(), b, i;
    for (b = 0; b < 64; b++) {
        for (i = 0; i < 16; i++) M.notes.push(md_note(M, 60 + ((b * 7 + i * 5) % 24), b * 4 + i * 0.25, 0.25, 90, 0, 0));
        M.notes.push(md_note(M, 36 + (b % 12), b * 4, 2, 90, 0, 0));
        M.notes.push(md_note(M, 43 + (b % 12), b * 4 + 2, 2, 90, 0, 0));
    }
    M.lenBeats = 256;
    var o = { key: 0, split: 60, staves: "piano", quant: 12, tuplets: true, overlap: "tie", extraBar: false };
    var t0 = lv_now(), S = nt_engrave(M, o), t1 = lv_now();
    var L = ly_layout(S, { width: 1188, sp: 9, marginL: 30, marginR: 18, top: 6, bottom: 45, title: "x", finalBar: false });
    var t2 = lv_now();
    out.push("bench 64 bars " + M.notes.length + " notes: engrave " + (t1 - t0) + " ms, layout " + (t2 - t1) + " ms");
    try {
        var mg = new MGraphics(1188, 700);
        mg.relative_coords = 0;
        var t3 = lv_now();
        dr_layout(mg, L, 0, 0, 0, 700);
        out.push("bench draw one editor screen " + (lv_now() - t3) + " ms");
    } catch (e) { out.push("bench draw: " + e); }
    var t4 = lv_now(), W = md_window(M, 30, 4);
    var SW = nt_engrave(W, o);
    ly_layout(SW, { width: 332, sp: 3.2, marginL: 14, marginR: 6, top: 0, bottom: 0, title: "", finalBar: true });
    out.push("bench strip thumbnail " + (lv_now() - t4) + " ms");
    return out;
}

// a groove, for the drum-staff photograph and the harness
function drumdemo() {
    if (!G) return;
    md_load(G.M, [], 4, 4, 8, "Groove", "");
    var M = G.M, i;
    function n(p, t, d, v) { var x = md_note(M, p, t, d, v || 100, 0, 0); M.notes.push(x); return x; }
    for (i = 0; i < 8; i++) n(i === 7 ? 46 : 42, i * 0.5, 0.5, i % 2 ? 70 : 100);
    n(36, 0, 0.5); n(38, 1, 0.5); n(36, 2, 0.5); n(36, 2.5, 0.5); n(38, 3, 0.5);
    n(49, 4, 1); n(36, 4, 0.5);
    var fl = n(38, 5, 0.5);
    n(42, 4.5, 0.5, 80); n(42, 5.5, 0.5, 80);
    var fill = [50, 50, 48, 48, 45, 45, 43, 43];
    for (i = 0; i < 8; i++) n(fill[i], 6 + i * 0.25, 0.25, 90);
    n(36, 6, 0.5); n(44, 5, 0.5, 60);
    md_addGrace(M, fl, 0, true);
    G.opt.staves = 3;
    G.optVersion++;
    md_changed(M);
    if (ROLE === "brain") { lv_status(G, "Drum demonstration loaded."); br_update(); }
}

// ---- src/70_ui.js
// ============================================================================
//  ui_ - the views: the editor window and the thumbnail on the device strip
//
//  A view owns nothing that matters. It asks the brain for the name of the
//  shared state (and keeps asking - a jsui that is not drawn runs no code),
//  engraves the model when its version changes, and turns mouse gestures into
//  edits of that same model. The brain puts every edit into the clip.
//
//  THE EDITOR - every setting of the device lives here
//    row 1   UNDO REDO | ADD SELECT | note values, dot, triplet |
//            TIE, trill, acciaccatura | flat natural sharp | 8va + - DELETE
//    row 2   key | staves | velocity | hear | zoom | window size |
//            MIDI PDF PNG MUSICXML | the website
//    page    ADD: click a staff to write a note. Any tool: click a note to
//            select it, drag it up/down by staff step and sideways by the
//            note value; ctrl-click or right-click deletes. SELECT draws a box.
//
//  Value, accidental, tie, trill and acciaccatura buttons act on the
//  selection; a note just written IS selected, so it can be corrected at once.
// ============================================================================

var UI_TB = 76, UI_SB = 24, UI_SCR = 12;
var UI_MINI_W = 336, UI_MINI_H = 145;
var ui_WEB = "www.remodevicocomposer.eu";

var ui_C = {
    bg: [0.155, 0.16, 0.17, 1], btn: [0.27, 0.28, 0.30, 1], btnHi: [0.35, 0.36, 0.39, 1], lab: [0.20, 0.205, 0.215, 1],
    on: [1.0, 0.64, 0.13, 1], txt: [0.88, 0.88, 0.89, 1], dim: [0.52, 0.53, 0.55, 1], txtOn: [0.07, 0.07, 0.08, 1],
    paper: [0.985, 0.978, 0.958, 1], warn: [1.0, 0.44, 0.18, 1], ok: [0.42, 0.78, 0.45, 1], link: [0.47, 0.74, 0.98, 1],
    sel: [0.10, 0.42, 0.95, 1], ghost: [0.93, 0.40, 0.06, 0.55], play: [1.0, 0.52, 0.08, 0.9],
    band: [0.10, 0.42, 0.95, 0.14]
};

var ui_KEYS = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#"];
var ui_VALUES = [192, 96, 48, 24, 12, 6];

var V = {
    w: 1200, h: 760, mini: false, roleSet: false,
    lkey: "", S: null, L: null, scroll: 0,
    tool: "add", dur: 2, dot: 0, trip: 0, acc: null,
    ghost: null, hint: "", drag: null, focus: 0, btns: [], mx: -1, my: -1,
    miniKey: "", miniS: null, miniL: null
};

if (ROLE !== "brain" && typeof mgraphics !== "undefined") {
    mgraphics.init();
    mgraphics.relative_coords = 0;
    mgraphics.autofill = 0;
}

var ui_helloTask = (ROLE !== "brain" && typeof Task !== "undefined") ? new Task(ui_hello, this) : null;
if (ui_helloTask) { ui_helloTask.interval = 300; ui_helloTask.repeat(); }

function ui_isView() { return ROLE !== "brain"; }

function ui_detectRole() {
    if (V.roleSet) return;
    V.roleSet = true;
    try {
        if (this.box && this.box.varname === "spartitomini") { V.mini = true; V.w = UI_MINI_W; V.h = UI_MINI_H; }
    } catch (e) {}
}

function ui_hello() {
    ui_detectRole();
    if (G) { if (ui_helloTask) ui_helloTask.cancel(); return; }
    outlet(0, "hello");
}

function ui_redraw() { if (ui_isView() && typeof mgraphics !== "undefined") mgraphics.redraw(); }
function ui_changed() { outlet(0, "changed"); ui_redraw(); }
function ui_audition(p, v) { outlet(0, "audition", p, v || G.opt.vel, 380); }
function ui_say(s) { G.status = s; G.statusTime = new Date().getTime(); ui_redraw(); }

// ------------------------------------------------------------- messages
function role(r) { if (!ui_isView()) return; V.mini = ("" + r) === "mini"; V.roleSet = true; V.lkey = ""; ui_redraw(); }

function canvas(w, h) {
    if (!ui_isView()) return;
    V.w = Math.max(200, Math.floor(+w));
    V.h = Math.max(100, Math.floor(+h));
    V.lkey = ""; V.miniKey = "";
    ui_clampScroll();
    ui_redraw();
}

function uid(name) {
    if (!ui_isView() || typeof Global === "undefined") return;
    var g = new Global("" + name);
    if (!g.state) return;
    br_gObj = g;
    G = g.state;
    V.lkey = ""; V.miniKey = "";
    if (ui_helloTask) ui_helloTask.cancel();
    ui_redraw();
}

function update() { if (ui_isView()) ui_redraw(); }

// A playhead message repaints only if the line actually moved on screen: a
// page of music is not repainted to move a line by less than a pixel.
function play(t) {
    if (!ui_isView() || !G) return;
    t = +t;
    var key;
    if (V.mini) {
        key = t < 0 ? "stop" : ui_miniPlayKey(t);
    } else {
        ui_followPlay(t);
        var ph = (t >= 0 && V.L) ? ly_xAtTick(V.L, t) : null;
        key = ph ? ph.sys + "_" + Math.round(ph.x) + "_" + V.scroll : "none";
    }
    if (key === V.playKey) return;
    V.playKey = key;
    ui_redraw();
}

function ui_miniPlayKey(t) {
    var L = V.miniL;
    if (!L || !V.miniS) return "x";
    var bar = Math.floor(t / V.miniS.mi.barT);
    if (bar < V.miniBar || bar >= V.miniBar + V.miniBars) return "win" + bar;
    var ph = ly_xAtTick(L, t - V.miniBar * V.miniS.mi.barT);
    return ph ? "x" + Math.round(ph.x / 2) : "x";
}

function focus(f) { if (ui_isView()) V.focus = +f; }

function renderpng() {
    if (!ui_isView() || !G || V.mini) return;
    var a = [];
    for (var i = 0; i < arguments.length; i++) a.push("" + arguments[i]);
    var path = a.join(" ");
    var err = ex_png(br_layoutFor("png").L, path);
    ui_say(err ? "PNG export failed: " + err : "Exported " + path.replace(/^.*[\/\\]/, "") + ".");
}

function keyasc(c) {
    if (!ui_isView() || !G || V.mini || !V.focus || G.capture) return;
    c = +c;
    if (c === 8 || c === 127) ui_action("del");
    else if (c >= 50 && c <= 55) ui_action("dur_" + (55 - c));
    else if (c === 46) ui_action("dot");
    else if (c === 45) ui_action("acc_-1");
    else if (c === 43 || c === 61) ui_action("acc_1");
    ui_redraw();
}

function notifydeleted() {
    if (ui_helloTask) ui_helloTask.cancel();
    if (br_task) br_task.cancel();
    if (br_playTask) br_playTask.cancel();
    if (br_writeTask) br_writeTask.cancel();
}

// ------------------------------------------------------------ drawing kit
function ui_fill(g, x, y, w, h, c) {
    g.set_source_rgba(c[0], c[1], c[2], c[3]);
    g.rectangle(x, y, w, h);
    g.fill();
}

function ui_rfill(g, x, y, w, h, r, c) {
    g.set_source_rgba(c[0], c[1], c[2], c[3]);
    g.rectangle_rounded(x, y, w, h, r, r);
    g.fill();
}

function ui_text(g, s, x, y, size, c, align, bold) {
    g.set_source_rgba(c[0], c[1], c[2], c[3]);
    g.select_font_face("Arial", "normal", bold ? "bold" : "normal");
    g.set_font_size(size);
    var w = 0;
    if (align && align !== "left") { var tm = g.text_measure(s); w = tm ? tm[0] : 0; }
    g.move_to(x - (align === "center" ? w / 2 : (align === "right" ? w : 0)), y);
    g.show_text(s);
}

function ui_textWidth(g, s, size, bold) {
    g.select_font_face("Arial", "normal", bold ? "bold" : "normal");
    g.set_font_size(size);
    var tm = g.text_measure(s);
    return tm ? tm[0] : s.length * size * 0.55;
}

// ---------------------------------------------------------------- paint
function paint() {
    if (!ui_isView()) return;
    ui_detectRole();
    var g = mgraphics;
    if (!G) {
        ui_fill(g, 0, 0, V.w, V.h, ui_C.bg);
        ui_text(g, "SPARTITO - connecting to the device...", 10, 20, 11, ui_C.dim, "left", 0);
        return;
    }
    if (V.mini) ui_paintMini(g);
    else ui_paintWindow(g);
}

function ui_ensureLayout() {
    var sp = br_SP[G.opt.zoom] || 9;
    var W = V.w - UI_SCR;
    var MM = br_model();
    var key = MM.version + "|" + G.optVersion + "|" + W + "|" + sp + "|" + MM.name + "|" + G.capture;
    if (key === V.lkey && V.L) return;
    V.S = nt_engrave(MM, br_nopts(!G.capture));
    V.L = ly_layout(V.S, { width: W, sp: sp, marginL: 3.4 * sp, marginR: 2 * sp, top: 0.6 * sp, bottom: 5 * sp,
                           title: MM.name || "", ink: gl_INK, selc: ui_C.sel, finalBar: false,
                           barOffset: br_barOffset() });
    V.lkey = key;
    ui_clampScroll();
}

function ui_areaH() { return V.h - UI_TB - UI_SB; }

function ui_clampScroll() {
    if (!V.L) return;
    V.scroll = cr_clamp(V.scroll, 0, Math.max(0, V.L.height - ui_areaH()));
}

function ui_followPlay(t) {
    if (V.drag || t < 0 || !V.L) return;
    var ph = ly_xAtTick(V.L, t);
    if (!ph) return;
    var sy = V.L.systems[ph.sys];
    if (sy.y1 - V.scroll > ui_areaH() || sy.y0 - V.scroll < 0) {
        V.scroll = sy.y0 - 4;
        ui_clampScroll();
    }
}

function ui_paintWindow(g) {
    ui_ensureLayout();
    var L = V.L, W = V.w - UI_SCR, top = UI_TB, areaH = ui_areaH();
    var dy = top - V.scroll, sp = L.sp;

    ui_fill(g, 0, top, W, areaH, ui_C.paper);
    dr_layout(g, L, 0, dy, top - 40, top + areaH + 40);

    if (G.play >= 0) {
        var ph = ly_xAtTick(L, G.play);
        if (ph) {
            var sy = L.systems[ph.sys];
            ui_fill(g, ph.x - 1, sy.tops[0] - 2 * sp + dy, 2, sy.tops[sy.tops.length - 1] + 6 * sp - sy.tops[0], ui_C.play);
        }
    }
    if (V.ghost && V.tool === "add" && !V.drag) ui_drawGhost(g, dy);
    if (V.drag && V.drag.kind === "band") {
        var d = V.drag;
        ui_fill(g, Math.min(d.x0, d.x1), Math.min(d.y0, d.y1) + dy, cr_abs(d.x1 - d.x0), cr_abs(d.y1 - d.y0), ui_C.band);
    }
    if (!br_model().notes.length && !G.capture) {
        ui_text(g, "Click a MIDI clip in Live, or click on a staff to write. Every change goes straight into the clip.",
                W / 2, top + Math.min(areaH - 30, L.height + 30), 13, [0.35, 0.35, 0.37, 1], "center", 0);
    }
    ui_scrollbar(g);
    ui_toolbar(g);
    ui_statusbar(g);
}

function ui_drawGhost(g, dy) {
    var L = V.L, sp = L.sp, gh = V.ghost, D = [], k;
    var bottom = L.bottoms[gh.st], c = ui_C.ghost;
    var gHead = V.S && V.S.perc ? nt_drum(ui_ghostPitch(gh))[1] : "n";
    if (gHead === "x" || gHead === "o") gl_headX(D, gh.x, gh.y, sp, c, gHead === "o");
    else gl_head(D, gh.x, gh.y, sp, V.dur < 2 ? V.dur : 2, c);
    for (k = bottom + 10; k <= gh.step; k += 2) gl_line(D, gh.x - 1.0 * sp, ly_yOf(L, gh.sys, gh.st, k), gh.x + 1.0 * sp, ly_yOf(L, gh.sys, gh.st, k), 0.16 * sp, c);
    for (k = bottom - 2; k >= gh.step; k -= 2) gl_line(D, gh.x - 1.0 * sp, ly_yOf(L, gh.sys, gh.st, k), gh.x + 1.0 * sp, ly_yOf(L, gh.sys, gh.st, k), 0.16 * sp, c);
    if (V.acc !== null) gl_accidental(D, gh.x - 1.9 * sp, gh.y, sp, V.acc, c);
    dr_ops(g, D, 0, dy);
}

function ui_scrollInfo() {
    var areaH = ui_areaH(), content = V.L ? V.L.height : areaH;
    var thumbH = content <= areaH ? areaH : Math.max(30, areaH * areaH / content);
    var range = Math.max(1, content - areaH);
    var thumbY = UI_TB + (areaH - thumbH) * (content <= areaH ? 0 : V.scroll / range);
    return { thumbY: thumbY, thumbH: thumbH, range: range, areaH: areaH };
}

function ui_scrollbar(g) {
    var x = V.w - UI_SCR, info = ui_scrollInfo();
    ui_fill(g, x, UI_TB, UI_SCR, info.areaH, [0.21, 0.215, 0.225, 1]);
    ui_rfill(g, x + 2, info.thumbY + 2, UI_SCR - 4, info.thumbH - 4, 3, [0.45, 0.46, 0.48, 1]);
}

// ------------------------------------------------------------- toolbar
function ui_toolbarSpec() {
    var M = br_model(), o = G.opt, r1 = [], r2 = [], k;
    var sel = md_selected(M);
    var has = sel.length > 0 && !G.capture;
    var perc = o.staves === 3;
    function b(row, id, label, w, opt) {
        opt = opt || {};
        row.push({ id: id, label: label, w: w, on: !!opt.on, icon: opt.icon || "", dim: !!opt.dim,
                   gap: !!opt.gap, lab: !!opt.lab, link: !!opt.link });
    }
    if (G.capture) b(r1, "cap_close", G.capLive ? "RECORDING" : "BACK TO CLIP", 100, { on: G.capLive });
    b(r1, "undo", "UNDO", 46, { dim: !M.undo.length || G.capture, gap: G.capture });
    b(r1, "redo", "REDO", 46, { dim: !M.redo.length });
    b(r1, "tool_add", "ADD", 42, { gap: 1, on: V.tool === "add" });
    b(r1, "tool_select", "SELECT", 56, { on: V.tool === "select" });
    for (k = 0; k < 6; k++) b(r1, "dur_" + k, "", 30, { icon: "dur" + k, on: V.dur === k, gap: k === 0 });
    b(r1, "dot", "", 26, { icon: "dot", on: V.dot });
    b(r1, "trip", "3", 26, { on: V.trip });
    b(r1, "tie", "", 34, { icon: "tie", gap: 1, dim: !has });
    b(r1, "trill", "tr", 30, { dim: !has || perc });
    b(r1, "grace", "", 30, { icon: "grace", dim: !has });
    b(r1, "acc_-1", "", 28, { icon: "flat", gap: 1, on: V.acc === -1, dim: perc });
    b(r1, "acc_0", "", 28, { icon: "natural", on: V.acc === 0, dim: perc });
    b(r1, "acc_1", "", 28, { icon: "sharp", on: V.acc === 1, dim: perc });
    b(r1, "oct_up", "8va +", 44, { gap: 1, dim: !has });
    b(r1, "oct_dn", "8va -", 44, { dim: !has });
    b(r1, "del", "DELETE", 56, { dim: !has });

    b(r2, "key_prev", "<", 20);
    b(r2, "key", "KEY " + ui_KEYS[o.key + 7] + " major", 112, { dim: perc });
    b(r2, "key_next", ">", 20);
    b(r2, "staves", ["PIANO", "TREBLE", "BASS", "DRUMS"][o.staves], 60, { gap: 1, on: perc });
    var vShown = has ? sel[0].v : o.vel;
    b(r2, "vel_dn", "-", 20, { gap: 1 });
    b(r2, "vel", "VEL " + vShown, 58, { lab: 1 });
    b(r2, "vel_up", "+", 20);
    b(r2, "hear", "HEAR " + (o.hear ? "ON" : "OFF"), 66, { gap: 1, on: o.hear });
    b(r2, "zoom_out", "-", 22, { gap: 1 });
    b(r2, "zoom_in", "+", 22);
    b(r2, "win_0", "S", 22, { gap: 1, on: o.win === 0 });
    b(r2, "win_1", "M", 22, { on: o.win === 1 });
    b(r2, "win_2", "L", 22, { on: o.win === 2 });
    b(r2, "x_midi", "MIDI", 44, { gap: 1 });
    b(r2, "x_pdf", "PDF", 38);
    b(r2, "x_png", "PNG", 38);
    b(r2, "x_xml", "MUSICXML", 72);
    b(r2, "web", ui_WEB, 150, { gap: 1, link: 1 });
    return [r1, r2];
}

function ui_layoutButtons() {
    var rows = ui_toolbarSpec(), out = [], r, i;
    for (r = 0; r < rows.length; r++) {
        var row = rows[r], natural = 8;
        for (i = 0; i < row.length; i++) natural += row[i].w + (row[i].gap ? 14 : 4);
        var f = Math.min(1, (V.w - 16) / natural);
        var x = 8, y = 8 + r * 32;
        for (i = 0; i < row.length; i++) {
            if (row[i].gap && i > 0) x += 10 * f;
            row[i].x = x; row[i].y = y; row[i].h = 26; row[i].w = row[i].w * f;
            x += row[i].w + 4 * f;
            out.push(row[i]);
        }
        var last = row[row.length - 1];
        if (last.link) last.x = Math.max(last.x, V.w - 8 - last.w);
    }
    V.btns = out;
    return out;
}

function ui_btnAt(x, y) {
    for (var i = 0; i < V.btns.length; i++) {
        var b = V.btns[i];
        if (!b.lab && x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return b;
    }
    return null;
}

function ui_toolbar(g) {
    ui_fill(g, 0, 0, V.w, UI_TB, ui_C.bg);
    var bs = ui_layoutButtons(), i;
    for (i = 0; i < bs.length; i++) {
        var b = bs[i];
        var hover = !b.lab && V.mx >= b.x && V.mx <= b.x + b.w && V.my >= b.y && V.my <= b.y + b.h;
        if (b.link) {
            ui_text(g, b.label, b.x + b.w, b.y + 17, 11, hover ? ui_C.on : ui_C.link, "right", 1);
            continue;
        }
        var bg = b.on ? ui_C.on : (b.lab ? ui_C.lab : (hover ? ui_C.btnHi : ui_C.btn));
        var fg = b.on ? ui_C.txtOn : (b.dim ? ui_C.dim : ui_C.txt);
        ui_rfill(g, b.x, b.y, b.w, b.h, 4, bg);
        if (b.icon) ui_icon(g, b.icon, b.x + b.w / 2, b.y + b.h / 2, fg);
        else ui_text(g, b.label, b.x + b.w / 2, b.y + 17, b.label.length > 2 ? 10 : 13, fg, "center", 1);
    }
}

function ui_icon(g, icon, cx, cy, c) {
    var D = [], s = 4.4;
    if (icon.indexOf("dur") === 0) {
        var type = +icon.substring(3);
        var hx = cx - 2, hy = cy + 5;
        gl_head(D, type === 0 ? cx : hx, type === 0 ? cy : hy, s, type < 2 ? type : 2, c);
        if (type >= 1) {
            var sx = hx + gl_HEAD_W * s / 2 - 0.6;
            gl_fill(D, ["M", sx - 0.6, hy - 1, "L", sx + 0.6, hy - 1, "L", sx + 0.6, cy - 9, "L", sx - 0.6, cy - 9, "Z"], c);
            if (type >= 3) gl_flag(D, sx - 0.3, cy - 9, s * 0.9, true, type - 2, c);
        }
    } else if (icon === "dot") {
        gl_circle(D, cx, cy + 1, 2.4, c);
    } else if (icon === "flat") {
        gl_flat(D, cx + 1, cy + 2, 5.2, c);
    } else if (icon === "natural") {
        gl_natural(D, cx, cy, 5.2, c);
    } else if (icon === "sharp") {
        gl_sharp(D, cx, cy, 5.2, c);
    } else if (icon === "tie") {
        gl_head(D, cx - 8, cy + 4, 3.6, 2, c);
        gl_head(D, cx + 8, cy + 4, 3.6, 2, c);
        gl_tie(D, cx - 7, cx + 7, cy - 1, 6, true, c);
    } else if (icon === "grace") {
        var gx = cx - 2, gy = cy + 5, gs = 3.6;
        gl_head(D, gx, gy, gs, 2, c);
        var gsx = gx + 0.6 * gs;
        gl_fill(D, ["M", gsx - 0.5, gy, "L", gsx + 0.5, gy, "L", gsx + 0.5, cy - 8, "L", gsx - 0.5, cy - 8, "Z"], c);
        gl_flag(D, gsx - 0.4, cy - 8, gs, true, 1, c);
        gl_line(D, gsx - 5, gy - 3, gsx + 5, cy - 6, 1.1, c);
    }
    dr_ops(g, D, 0, 0);
}

function ui_statusbar(g) {
    var y = V.h - UI_SB, M = br_model(), D = [];
    ui_fill(g, 0, y, V.w, UI_SB, ui_C.bg);
    var linked = !!G.target;
    gl_circle(D, 14, y + 12, 4, G.capLive ? ui_C.warn : (linked || G.capture ? ui_C.ok : ui_C.warn));
    dr_ops(g, D, 0, 0);
    var s1 = G.capLive ? "RECORDING in the Arrangement"
           : (G.capture ? "Recorded take - click its clip in the Arrangement to edit it"
           : (linked ? "Live clip: " + G.target : "No clip - write to create one on this track"));
    ui_text(g, s1, 24, y + 16, 11, G.capLive || (!linked && !G.capture) ? ui_C.warn : ui_C.txt, "left", 1);
    var x = 24 + ui_textWidth(g, s1, 11, 1) + 14;
    ui_text(g, M.num + "/" + M.den + " (the clip's)", x, y + 16, 11, ui_C.dim, "left", 0);
    var now = new Date().getTime();
    var fresh = G.status && now - G.statusTime < 9000;
    var msg = fresh ? G.status : V.hint;
    if (msg) ui_text(g, msg, V.w - 10, y + 16, 11, fresh ? ui_C.on : ui_C.txt, "right", 0);
}

// -------------------------------------------------------------- thumbnail
// The thumbnail engraves FOUR BARS - the ones the playhead is in - never the
// whole score: it is repainted with every edit and every playhead step, and it
// used to engrave an entire arrangement clip each time.
var UI_MINI_BARS = 4;

function ui_paintMini(g) {
    var w = V.w, h = V.h, M = br_model(), sp = 3.2;
    ui_fill(g, 0, 0, w, h, [0.11, 0.112, 0.12, 1]);
    var barB = M.num * 4 / M.den;
    var totalBars = Math.max(1, Math.ceil(Math.max(M.lenBeats, md_endBeats(M)) / barB - 1e-9));
    var wantBar = 0;
    if (G.play >= 0) wantBar = Math.floor(G.play / TPQ / barB / UI_MINI_BARS) * UI_MINI_BARS;
    wantBar = Math.max(0, Math.min(wantBar, totalBars - 1));
    var key = M.version + "|" + G.optVersion + "|" + w + "|" + G.capture + "|" + wantBar;
    if (key !== V.miniKey) {
        V.miniBar = wantBar;
        V.miniBars = Math.max(1, Math.min(UI_MINI_BARS, totalBars - wantBar));
        V.miniS = nt_engrave(md_window(M, V.miniBar, V.miniBars), br_nopts(false));
        V.miniL = ly_layout(V.miniS, { width: w - 4, sp: sp, marginL: 4.5 * sp, marginR: 2 * sp, top: 0, bottom: 0,
                                       title: "", ink: gl_INK, selc: ui_C.sel, finalBar: V.miniBar + V.miniBars >= totalBars,
                                       barOffset: V.miniBar + br_barOffset() });
        V.miniKey = key;
    }
    var L = V.miniL, paperTop = 18, paperH = h - 36;
    ui_rfill(g, 2, paperTop, w - 4, paperH, 3, ui_C.paper);
    if (L.systems.length) {
        var sy = L.systems[0];
        var dy = paperTop + (paperH - (sy.y1 - sy.y0)) / 2 - sy.y0;
        dr_ops(g, L.sysOps[0], 2, dy);
        if (G.play >= 0) {
            var p2 = ly_xAtTick(L, G.play - V.miniBar * V.miniS.mi.barT);
            if (p2 && p2.sys === 0) ui_fill(g, p2.x + 1, sy.tops[0] - 2 * sp + dy, 1.5, sy.tops[sy.tops.length - 1] - sy.tops[0] + 8 * sp, ui_C.play);
        }
    }
    var bars = totalBars;
    ui_text(g, G.capLive ? "RECORDING" : (G.capture ? "recorded take" : (G.target || "no clip")), 4, 13, 10,
            G.capLive ? ui_C.warn : (G.target || G.capture ? ui_C.txt : ui_C.dim), "left", 1);
    ui_text(g, bars + (bars === 1 ? " bar  " : " bars  ") + M.notes.length + " notes  " + M.num + "/" + M.den, w - 4, 13, 9, ui_C.dim, "right", 0);
    ui_text(g, "in sync with the clip", 4, h - 6, 9, ui_C.dim, "left", 0);
    ui_text(g, "click to open the score", w - 4, h - 6, 9, ui_C.dim, "right", 0);
}

// ---------------------------------------------------------------- groups
// A trill is many notes in the clip and one note on the page; an acciaccatura
// belongs to its note. Selecting, moving and deleting treat them as one.
function ui_group(id) { return (V.S && V.S.groups && V.S.groups[id]) || null; }

function ui_groupIds(id) {
    var g = ui_group(id);
    return (g && g.kind === "trill") ? g.ids.slice(0) : [id];
}

// the selection plus the notes that travel with it
function ui_expandedIds() {
    var sel = md_selected(G.M), out = [], i, j;
    for (i = 0; i < sel.length; i++) {
        var ids = ui_groupIds(sel[i].id);
        for (j = 0; j < ids.length; j++) if (!cr_has(out, ids[j])) out.push(ids[j]);
    }
    var n = out.length;
    for (i = 0; i < n; i++) {
        var gid = V.S && V.S.graceOf[out[i]];
        if (gid && !cr_has(out, gid)) out.push(gid);
    }
    return out;
}

function ui_notesOf(ids) {
    var out = [];
    for (var i = 0; i < ids.length; i++) { var n = md_byId(G.M, ids[i]); if (n) out.push(n); }
    return out;
}

// the selection split into trill groups, plain notes and acciaccaturas
function ui_partition() {
    var sel = md_selected(G.M), groups = [], seen = {}, singles = [], graces = [], i;
    for (i = 0; i < sel.length; i++) {
        var g = ui_group(sel[i].id);
        if (g && g.kind === "trill") { if (!seen[g.main]) { seen[g.main] = 1; groups.push(g); } }
        else if (g && g.kind === "grace") graces.push(sel[i]);
        else singles.push(sel[i]);
    }
    return { groups: groups, singles: singles, graces: graces };
}

// apply fn to plain notes, and to each trill as its one main note
function ui_withTrills(parts, fn) {
    if (parts.singles.length) fn(parts.singles);
    for (var i = 0; i < parts.groups.length; i++) {
        var members = ui_notesOf(parts.groups[i].ids);
        if (!members.length) continue;
        var main = md_untrill(G.M, members);
        fn([main]);
        md_trill(G.M, main, G.opt.key);
    }
}

// ---------------------------------------------------------------- mouse
function onclick(x, y, but, mod1, shift, caps, opt, mod2) {
    if (!ui_isView() || !G) return;
    if (V.mini) { outlet(0, "openwin"); return; }
    ui_down(x, y, mod1, shift, opt, mod2);
}

function ondblclick(x, y, but, mod1, shift, caps, opt, mod2) { onclick(x, y, but, mod1, shift, caps, opt, mod2); }

function ondrag(x, y, but, mod1, shift, caps, opt, mod2) {
    if (!ui_isView() || !G || V.mini) return;
    if (but) ui_dragMove(x, y, shift);
    else ui_dragEnd();
}

function onidle(x, y, but, mod1, shift, caps, opt, mod2) {
    if (!ui_isView() || !G || V.mini) return;
    ui_hover(x, y);
}

function onidleout() {
    if (!ui_isView()) return;
    V.ghost = null; V.mx = -1; V.my = -1; V.hint = "";
    ui_redraw();
}

function ui_toPage(y) { return y - UI_TB + V.scroll; }

function ui_down(x, y, mod1, shift, opt, mod2) {
    if (y < UI_TB) {
        ui_layoutButtons();
        var b = ui_btnAt(x, y);
        if (b) ui_action(b.id);
        ui_redraw();
        return;
    }
    if (y >= V.h - UI_SB) return;
    ui_ensureLayout();
    var M = G.M, L = V.L, i;
    if (x >= V.w - UI_SCR) {
        var info = ui_scrollInfo();
        if (y >= info.thumbY && y <= info.thumbY + info.thumbH) V.drag = { kind: "scroll", y0: y, s0: V.scroll };
        else { V.scroll += (y < info.thumbY ? -1 : 1) * info.areaH * 0.9; ui_clampScroll(); }
        ui_redraw();
        return;
    }
    if (G.capture) {
        ui_say(G.capLive ? "Recording - the take is not a clip yet." : "This is the recorded take: click its clip in the Arrangement to edit it.");
        return;
    }
    var px = x, py = ui_toPage(y);
    var hit = ly_hitNote(L, px, py);
    if (mod1 || mod2) {
        if (hit) {
            var ids = hit.k === "g" ? [hit.id] : ui_groupIds(hit.id);
            var gid = V.S.graceOf[ids[0]];
            if (gid) ids.push(gid);
            md_snapshot(M);
            md_deleteIds(M, ids);
            md_changed(M);
            ui_changed();
        }
        return;
    }
    if (hit) {
        var hitIds = hit.k === "g" ? [hit.id] : ui_groupIds(hit.id);
        var n = md_byId(M, hitIds[0]);
        if (!n) return;
        if (shift) md_selectIds(M, hitIds, true);
        else if (!n.sel) md_selectIds(M, hitIds, false);
        var loc = ly_locate(L, px, py);
        var moveIds = ui_expandedIds(), orig = [], onlyGraces = true;
        var ns = ui_notesOf(moveIds);
        for (i = 0; i < ns.length; i++) {
            orig.push({ n: ns[i], p: ns[i].p, t: ns[i].t, sp: ns[i].sp });
            var g = ui_group(ns[i].id);
            if (!g || g.kind !== "grace") onlyGraces = false;
        }
        V.drag = { kind: "move", x0: px, y0: py, loc: loc, orig: orig, moved: false, dSteps: 0, dT: 0,
                   onlyGraces: onlyGraces, t0: loc ? loc.m * L.barT + ly_tickAtX(L, loc.m, px) : 0 };
        ui_audition(n.p, n.v);
        ui_changed();
        return;
    }
    if (V.tool === "add") { ui_addAt(px, py); return; }
    var base = [];
    if (shift) { var s2 = md_selected(M); for (i = 0; i < s2.length; i++) base.push(s2[i].id); }
    else md_selectNone(M);
    V.drag = { kind: "band", x0: px, y0: py, x1: px, y1: py, base: base };
    ui_changed();
}

function ui_dragMove(x, y, shift) {
    var d = V.drag;
    if (!d) return;
    ui_ensureLayout();
    var M = G.M, L = V.L, px = x, py = ui_toPage(y), i;
    if (d.kind === "scroll") {
        var info = ui_scrollInfo();
        V.scroll = d.s0 + (y - d.y0) * info.range / Math.max(1, info.areaH - info.thumbH);
        ui_clampScroll();
        ui_redraw();
        return;
    }
    if (d.kind === "band") {
        d.x1 = px; d.y1 = py;
        var x0 = Math.min(d.x0, d.x1), x1 = Math.max(d.x0, d.x1), y0 = Math.min(d.y0, d.y1), y1 = Math.max(d.y0, d.y1);
        var ids = d.base.slice(0);
        for (i = 0; i < L.hits.length; i++) {
            var hh = L.hits[i];
            if (hh.x1 >= x0 && hh.x0 <= x1 && hh.y1 >= y0 && hh.y0 <= y1) {
                var gi = hh.k === "g" ? [hh.id] : ui_groupIds(hh.id);
                for (var j = 0; j < gi.length; j++) ids.push(gi[j]);
            }
        }
        md_selectIds(M, ids, false);
        ui_redraw();
        return;
    }
    if (d.kind === "move") {
        var steps = cr_round((d.y0 - py) / (L.sp / 2));
        var dT = 0;
        if (!d.onlyGraces && d.loc && L.systems[d.loc.sys]) {
            var sy = L.systems[d.loc.sys];
            var loc2 = ly_locate(L, px, sy.tops[d.loc.st] + 2 * L.sp);
            if (loc2) {
                var tNow = loc2.m * L.barT + ly_tickAtX(L, loc2.m, px);
                var gsn = ui_snapTicks();
                dT = cr_round((tNow - d.t0) / gsn) * gsn;
            }
        }
        if (steps === d.dSteps && dT === d.dT) return;
        if (!d.moved) { md_snapshot(M); d.moved = true; }
        var notes = [];
        for (i = 0; i < d.orig.length; i++) {
            d.orig[i].n.p = d.orig[i].p; d.orig[i].n.t = d.orig[i].t; d.orig[i].n.sp = d.orig[i].sp;
            notes.push(d.orig[i].n);
        }
        if (steps) md_moveSteps(M, notes, steps, G.opt.key, V.S.perc);
        if (dT) md_moveTime(M, notes, dT / TPQ);
        var pitchMoved = steps !== d.dSteps;
        d.dSteps = steps; d.dT = dT;
        md_changed(M);
        if (pitchMoved && notes.length) ui_audition(notes[0].p, notes[0].v);
        outlet(0, "changed");
        ui_redraw();
    }
}

function ui_dragEnd() {
    var d = V.drag;
    V.drag = null;
    if (d && d.kind !== "scroll") ui_changed();
    else ui_redraw();
}

// Every mouse movement arrives here. It repaints only when what is shown
// changed - another button lit, the ghost note on another line or beat,
// another hint - not for every pixel the mouse travels.
function ui_hover(x, y) {
    ui_hoverCompute(x, y);
    var gh = V.ghost;
    var btn = y < UI_TB ? ui_btnAt(x, y) : null;
    var key = (btn ? btn.id : "-") + "|" + V.hint + "|" + (gh ? gh.sys + "_" + gh.st + "_" + gh.m + "_" + gh.tick + "_" + gh.step : "");
    if (key === V.hoverKey) return;
    V.hoverKey = key;
    ui_redraw();
}

function ui_hoverCompute(x, y) {
    V.mx = x; V.my = y;
    if (G.capture) { V.ghost = null; V.hint = ""; if (y < UI_TB) { ui_layoutButtons(); var bc = ui_btnAt(x, y); V.hint = bc ? ui_btnHint(bc.id) : ""; } return; }
    if (y < UI_TB || y >= V.h - UI_SB || x >= V.w - UI_SCR) {
        V.ghost = null;
        V.hint = "";
        if (y < UI_TB) { ui_layoutButtons(); var b = ui_btnAt(x, y); V.hint = b ? ui_btnHint(b.id) : ""; }
        return;
    }
    ui_ensureLayout();
    var px = x, py = ui_toPage(y);
    var hit = ly_hitNote(V.L, px, py);
    if (hit) {
        var n = md_byId(G.M, hit.id), g = ui_group(hit.id);
        V.ghost = null;
        V.hint = n ? ui_noteName(n.p) + (g ? (g.kind === "trill" ? "   trill" : "   acciaccatura") : "")
                   + "   velocity " + n.v + "   bar " + (hit.m + 1) : "";
    } else if (V.tool === "add") {
        V.ghost = ui_ghostAt(px, py);
        V.hint = V.ghost ? ui_noteName(ui_ghostPitch(V.ghost)) + "   bar " + (V.ghost.m + 1) + "   beat "
                           + cr_num(1 + V.ghost.tick / V.S.mi.beatT, 2) : "";
    } else {
        V.ghost = null;
        V.hint = "";
    }
}

function ui_btnHint(id) {
    var H = {
        undo: "Undo", redo: "Redo",
        tool_add: "Click on a staff to write a note; click a note to select and drag it",
        tool_select: "Drag a box to select notes",
        dot: "Dotted value", trip: "Triplet value",
        tie: "Tie the selected note to the next one of the same pitch (again: untie)",
        trill: "Trill on the selected note (again: remove it). Live plays it",
        grace: "Acciaccatura before the selected note (again: remove it). Drag it up or down to change it",
        "acc_-1": "Flat (on the selection, or on the next note)", acc_0: "Natural", acc_1: "Sharp",
        oct_up: "Selection up an octave", oct_dn: "Selection down an octave",
        del: "Delete the selection (also: Delete key, ctrl-click or right-click on a note)",
        key: "Key signature", key_prev: "Key: one fifth down", key_next: "Key: one fifth up",
        staves: "Grand staff, treble only or bass only",
        vel_dn: "Velocity down (of the selection, or of the next notes)", vel_up: "Velocity up",
        hear: "Hear the notes while writing", zoom_out: "Smaller", zoom_in: "Larger",
        win_0: "Small window", win_1: "Medium window", win_2: "Large window",
        x_midi: "Export a Standard MIDI File", x_pdf: "Export the score as an A4 PDF",
        x_png: "Export the score as a PNG picture", x_xml: "Export MusicXML for MuseScore, Sibelius, Finale, Dorico",
        web: "Remo De Vico - composer"
    };
    if (id.indexOf("dur_") === 0) return ["Whole", "Half", "Quarter", "Eighth", "Sixteenth", "Thirty-second"][+id.substring(4)] + " note";
    return H[id] || "";
}

// ------------------------------------------------------------ note entry
function ui_durTicks() {
    return ui_VALUES[V.dur] * (V.dot ? 1.5 : 1) * (V.trip ? 2 / 3 : 1);
}

function ui_snapTicks() {
    var base = ui_VALUES[V.dur];
    if (V.trip) return Math.min(base * 2 / 3, 16);
    var mi = V.S ? V.S.mi : nt_meter(4, 4);
    return Math.min(base, mi.compound || mi.additive ? mi.sub : mi.beatT);
}

function ui_ghostAt(px, py) {
    var L = V.L, loc = ly_locate(L, px, py);
    if (!loc || !L.measures[loc.m]) return null;
    var b = L.bottoms[loc.st];
    var step = cr_clamp(ly_stepAtY(L, loc.sys, loc.st, py), b - 14, b + 22);
    if (V.S.perc) step = nt_drum(nt_drumAtStep(step))[0];     // onto the instrument's own line
    var tick = ly_tickAtX(L, loc.m, px), pts = L.measures[loc.m].pts, snapped = false, i;
    for (i = 0; i + 1 < pts.length; i++) {
        if (cr_abs(pts[i][1] - px) < 0.8 * L.sp) { tick = pts[i][0]; snapped = true; break; }
    }
    var g = ui_snapTicks();
    if (!snapped) tick = cr_round(tick / g) * g;
    if (tick >= L.barT) tick = L.barT - g;
    if (tick < 0) tick = 0;
    var xa = ly_xAtTick(L, loc.m * L.barT + tick);
    return { sys: loc.sys, st: loc.st, m: loc.m, tick: tick, step: step,
             x: xa ? xa.x : px, y: ly_yOf(L, loc.sys, loc.st, step) };
}

function ui_ghostPitch(gh) {
    if (V.S && V.S.perc) return nt_drumAtStep(gh.step);
    if (V.acc !== null) return nt_pitchOfStep(gh.step, 0) + V.acc;
    return nt_pitchOfStep(gh.step, G.opt.key);
}

function ui_addAt(px, py) {
    var gh = ui_ghostAt(px, py);
    if (!gh) return;
    var M = G.M;
    var p = cr_clamp(ui_ghostPitch(gh), 0, 127);
    var t = (gh.m * V.L.barT + gh.tick) / TPQ, d = ui_durTicks() / TPQ;
    var st = (V.S.staves.length === 2 && !V.S.perc) ? gh.st : -1;
    md_snapshot(M);
    var nn = md_add(M, p, t, d, G.opt.vel, (V.acc !== null && !V.S.perc) ? V.acc : 0, st);
    md_selectIds(M, [nn.id], false);
    var bar = M.num * 4 / M.den;
    if (t + d > M.lenBeats) M.lenBeats = Math.ceil((t + d) / bar - 1e-9) * bar;
    md_changed(M);
    V.acc = null;
    V.ghost = null;
    ui_audition(p, G.opt.vel);
    ui_changed();
}

// --------------------------------------------------------------- actions
function ui_action(id) {
    var M = G.M, o = G.opt, i, parts, ns;
    // A button can be pressed before the last edit has been drawn: the trill
    // just shortened, the acciaccatura just added. The groups have to be read
    // from the model as it is NOW, not from the last picture.
    ui_ensureLayout();
    if (id === "cap_close") { outlet(0, "capclose"); return; }
    if (G.capture && (id === "undo" || id === "redo" || id === "tie" || id === "trill" || id === "grace"
                      || id === "del" || id.indexOf("acc_") === 0 || id.indexOf("oct_") === 0)) {
        ui_say("The recorded take is not a clip yet: click its clip in the Arrangement to edit it.");
        return;
    }
    if (id === "undo") { if (md_undo(M)) ui_changed(); return; }
    if (id === "redo") { if (md_redo(M)) ui_changed(); return; }
    if (id.indexOf("tool_") === 0) { V.tool = id.substring(5); V.ghost = null; return; }
    if (id.indexOf("dur_") === 0 || id === "dot" || id === "trip") {
        if (id === "dot") V.dot = V.dot ? 0 : 1;
        else if (id === "trip") V.trip = V.trip ? 0 : 1;
        else V.dur = +id.substring(4);
        if (V.dur === 5 && V.dot) V.dot = 0;
        parts = ui_partition();
        if (parts.singles.length || parts.groups.length) {
            var len = ui_durTicks() / TPQ;
            md_snapshot(M);
            ui_withTrills(parts, function (list) { md_setLength(M, list, len); });
            md_changed(M);
            ui_changed();
        }
        return;
    }
    if (id.indexOf("acc_") === 0) {
        if (V.S.perc) return;
        var a = +id.substring(4);
        parts = ui_partition();
        if (parts.singles.length || parts.groups.length || parts.graces.length) {
            md_snapshot(M);
            if (parts.graces.length) md_setAlter(M, parts.graces, a, o.key);
            ui_withTrills(parts, function (list) { md_setAlter(M, list, a, o.key); });
            md_changed(M);
            ui_changed();
        } else {
            V.acc = (V.acc === a) ? null : a;
        }
        return;
    }
    if (id === "tie") { ui_tie(); return; }
    if (id === "trill") { ui_trill(); return; }
    if (id === "grace") { ui_grace(); return; }
    if (id === "oct_up" || id === "oct_dn") {
        ns = ui_notesOf(ui_expandedIds());
        if (!ns.length) return;
        md_snapshot(M);
        for (i = 0; i < ns.length; i++) ns[i].p = cr_clamp(ns[i].p + (id === "oct_up" ? 12 : -12), 0, 127);
        md_changed(M);
        ui_audition(ns[0].p, ns[0].v);
        ui_changed();
        return;
    }
    if (id === "del") {
        var ids = ui_expandedIds();
        if (!ids.length) return;
        md_snapshot(M);
        md_deleteIds(M, ids);
        md_changed(M);
        ui_changed();
        return;
    }
    if (id === "key_prev" || id === "key_next") { outlet(0, "uiparam", "key", cr_clamp(o.key + 7 + (id === "key_next" ? 1 : -1), 0, 14)); return; }
    if (id === "key") { outlet(0, "uiparam", "key", cr_mod(o.key + 8, 15)); return; }
    if (id === "staves") { outlet(0, "uiparam", "staves", (o.staves + 1) % 4); return; }
    if (id === "vel_dn" || id === "vel_up") {
        var dv = id === "vel_up" ? 5 : -5;
        ns = md_selected(M);
        if (ns.length) {
            md_snapshot(M);
            for (i = 0; i < ns.length; i++) ns[i].v = cr_clamp(ns[i].v + dv, 1, 127);
            md_changed(M);
            ui_audition(ns[0].p, ns[0].v);
            ui_changed();
        } else {
            outlet(0, "uiparam", "vel", cr_clamp(o.vel + dv, 1, 127));
        }
        return;
    }
    if (id === "hear") { outlet(0, "uiparam", "hear", o.hear ? 0 : 1); return; }
    if (id === "zoom_out" || id === "zoom_in") { outlet(0, "uiparam", "zoom", cr_clamp(o.zoom + (id === "zoom_in" ? 1 : -1), 0, 3)); return; }
    if (id.indexOf("win_") === 0) { outlet(0, "uiparam", "win", +id.substring(4)); return; }
    if (id.indexOf("x_") === 0) { outlet(0, "exportfmt", id.substring(2)); return; }
    if (id === "web") { outlet(0, "openurl"); return; }
}

// TIE joins each selected note to the next note of the same pitch - which in
// MIDI simply makes it one longer note. With nothing to join, it unties: a
// note drawn with a tie is cut in two where that tie is.
function ui_tie() {
    var M = G.M, parts = ui_partition(), i;
    var ns = cr_sortBy(parts.singles, function (n) { return n.t; });
    if (!ns.length) { ui_say("Select a note, then TIE joins it to the next note of the same pitch."); return; }
    md_snapshot(M);
    var did = false;
    for (i = 0; i < ns.length; i++) if (md_byId(M, ns[i].id) && md_tieNext(M, ns[i])) did = true;
    if (!did) {
        for (i = 0; i < ns.length; i++) {
            var at = nt_firstTieEnd(V.S, ns[i].id);
            if (at > 0 && md_split(M, ns[i], at / TPQ)) did = true;
        }
    }
    if (did) { md_changed(M); ui_changed(); }
    else { M.undo.pop(); ui_say("There is no later note of the same pitch to tie to."); }
}

function ui_noteName(p) { return (V.S && V.S.perc) ? nt_drum(p)[3] : cr_liveNoteName(p); }

function ui_trill() {
    var M = G.M, parts = ui_partition(), i;
    if (V.S && V.S.perc) { ui_say("No trills on a drum staff - use a roll of notes, or a flam."); return; }
    if (parts.groups.length) {
        md_snapshot(M);
        for (i = 0; i < parts.groups.length; i++) {
            var members = ui_notesOf(parts.groups[i].ids);
            if (members.length) md_untrill(M, members);
        }
        md_changed(M);
        ui_changed();
        return;
    }
    if (!parts.singles.length) { ui_say("Select a note, then tr."); return; }
    md_snapshot(M);
    var made = 0;
    for (i = 0; i < parts.singles.length; i++) if (md_trill(M, parts.singles[i], G.opt.key)) made++;
    if (made) { md_changed(M); ui_changed(); }
    else { M.undo.pop(); ui_say("A trill needs a note of at least a sixteenth."); }
}

function ui_grace() {
    var M = G.M, parts = ui_partition(), mains = parts.singles.slice(0), i;
    for (i = 0; i < parts.groups.length; i++) { var mm = md_byId(M, parts.groups[i].main); if (mm) mains.push(mm); }
    if (!mains.length) { ui_say("Select a note, then the acciaccatura button."); return; }
    md_snapshot(M);
    for (i = 0; i < mains.length; i++) {
        var gid = V.S && V.S.graceOf[mains[i].id];
        var gnote = gid ? md_byId(M, gid) : null;
        if (gnote) md_removeGrace(M, mains[i], gnote);
        else md_addGrace(M, mains[i], G.opt.key, V.S && V.S.perc);
    }
    md_changed(M);
    ui_audition(mains[0].p, mains[0].v);
    ui_changed();
}

