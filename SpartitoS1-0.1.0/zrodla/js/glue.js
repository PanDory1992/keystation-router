// ============================================================================
//  Spartito S1 - glue: the editor view of spartito.js inside a VST3
//
//  In Live the device had a brain that owned the state and kept it the same as
//  the clip. A VST3 cannot reach Studio One's parts, so here the score IS the
//  state: it is saved with the song, edited with the original tools, and the
//  notes this track plays are written into it while REC is on.
//
//    * Studio One's transport running: a note goes where Studio One has it, so
//      bar numbers are the song's; playing the same part again replaces the
//      notes instead of doubling them;
//    * transport stopped: a take starts at the bar after the last note, its
//      first note on beat 1;
//    * every take is one step of UNDO.
//
//  What the plugin calls (all names start s1_ or are spartito.js's own jsui
//  handlers: onclick, ondrag, onidle, onidleout, keyasc, focus, canvas, play):
//    s1_paint() -> ops JSON        s1_dirty() -> 1 when a repaint is due
//    s1_out() -> queued outlet messages as JSON ("" when none)
//    s1_input(json)                notes: [[on, pitch, vel, hostBeats, freeBeats, playing], ...]
//    s1_tick(host, free, playing, tempo, num, den)
//    s1_param(name, v)             a setting the editor changed (was the brain's uiparam)
//    s1_save() / s1_saveIfChanged() / s1_load(json)
//    s1_exportName(fmt) / s1_export(fmt, path) / s1_setName(s) / s1_wheel(dy)
// ============================================================================

G = br_newState();
lv_started = true;                     // br_export asks lv_tempo() for the MIDI file's tempo

var S1 = {
    rec: 1, origin: 0, anchored: false, pass: null, open: {},
    tempo: 120, num: 4, den: 4, playing: 0, host: 0, free: 0,
    dirty: 0, dirtyAt: 0, lastEv: 0, savedKey: "", statusOn: false, nameX0: -1, nameX1: -1
};
var S1_FREE_END_MS = 2500;             // a take with the transport stopped ends after this much silence
var S1_VIEW_MS = 120;                  // a take being played is re-engraved at most this often
var S1_SAME_NOTE = 0.06;               // beats: the same note played again (a loop, a second playback)

function lv_tempo() { return S1.tempo; }
function br_barOffset() { return S1.anchored ? Math.round(S1.origin / s1_bar()) : 0; }
function s1_bar() { return G.M.num * 4 / G.M.den; }
function s1_now() { return new Date().getTime(); }

// ---------------------------------------------------------------- takes
function s1_passTime(host, free) {
    var P = S1.pass;
    if (!P) return 0;
    return P.clock === "host" ? host - S1.origin : free - P.free0 + P.start;
}

function s1_startPass(clock, host, free) {
    var M = G.M;
    md_snapshot(M);
    var empty = !M.notes.length;
    if (empty) { M.num = S1.num; M.den = S1.den; M.lenBeats = M.num * 4 / M.den; }
    var bar = s1_bar(), P = { clock: clock, free0: free, start: 0, count: 0 };
    var nextBar = empty ? 0 : Math.ceil(md_endBeats(M) / bar - 1e-9) * bar;
    if (clock === "host") {
        var hostBar = Math.floor(host / bar + 1e-9) * bar;
        if (empty || !S1.anchored) {
            // bar 1 of what is played sits after what is already there
            S1.origin = hostBar - nextBar;
            if (S1.origin < 0) { s1_shift(-S1.origin); S1.origin = 0; }
            S1.anchored = true;
        } else if (hostBar < S1.origin) {
            s1_shift(S1.origin - hostBar);       // played earlier than bar 1: everything moves right
            S1.origin = hostBar;
        }
    } else {
        P.start = nextBar;
    }
    S1.pass = P;
    S1.open = {};
}

function s1_shift(beats) {
    var M = G.M;
    for (var i = 0; i < M.notes.length; i++) M.notes[i].t += beats;
    M.lenBeats += beats;
}

function s1_endPass() {
    var P = S1.pass;
    if (!P) return;
    var t = s1_passTime(S1.host, S1.free);
    for (var k in S1.open) { var o = S1.open[k]; o.d = Math.max(0.02, t - o.t); }
    S1.open = {};
    S1.pass = null;
    s1_grow();
    if (!P.count) G.M.undo.pop();
    md_changed(G.M);
    G.play = -1;
    if (P.count) ui_say("Take: " + P.count + (P.count === 1 ? " note." : " notes.") + " UNDO takes it back.");
    ui_changed();
}

function s1_grow() {
    var M = G.M, bar = s1_bar(), end = md_endBeats(M);
    if (end > M.lenBeats + 1e-9) M.lenBeats = Math.ceil(end / bar - 1e-9) * bar;
}

function s1_input(json) {
    var evs = JSON.parse(json), M = G.M, i;
    if (!S1.rec) return;
    for (i = 0; i < evs.length; i++) {
        var e = evs[i], on = !!e[0], p = e[1], v = e[2], host = e[3], free = e[4], playing = !!e[5];
        var clock = playing ? "host" : "free";
        S1.host = host; S1.free = free;
        if (on && (!S1.pass || S1.pass.clock !== clock)) {
            if (S1.pass) s1_endPass();
            s1_startPass(clock, host, free);
        }
        if (!S1.pass) continue;
        var t = Math.max(0, s1_passTime(host, free));
        if (on) {
            if (S1.open[p]) S1.open[p].d = Math.max(0.02, t - S1.open[p].t);
            if (clock === "host") {
                var keep = [];
                for (var j = 0; j < M.notes.length; j++) {
                    var n = M.notes[j];
                    if (!(n.p === p && cr_abs(n.t - t) < S1_SAME_NOTE)) keep.push(n);
                }
                M.notes = keep;
            }
            var nn = md_note(M, p, t, 0.02, cr_clamp(v, 1, 127), 0, 0);
            M.notes.push(nn);
            S1.open[p] = nn;
            S1.pass.count++;
        } else if (S1.open[p]) {
            S1.open[p].d = Math.max(0.02, t - S1.open[p].t);
            delete S1.open[p];
        }
        S1.lastEv = s1_now();
        S1.dirty = 1;
    }
    s1_grow();
}

// ---------------------------------------------------------------- the clock
function s1_tick(host, free, playing, tempo, num, den) {
    var now = s1_now();
    S1.host = host; S1.free = free; S1.playing = playing ? 1 : 0;
    if (tempo > 0) S1.tempo = tempo;
    if (num > 0 && den > 0) { S1.num = num; S1.den = den; }
    var P = S1.pass;
    if (P && P.clock === "host" && !playing) { s1_endPass(); P = null; }
    var held = false;
    for (var k in S1.open) { held = true; break; }
    if (P && P.clock === "free" && !held && now - S1.lastEv > S1_FREE_END_MS) { s1_endPass(); P = null; }
    var tNow = P ? s1_passTime(host, free) : 0;
    if (P && held) {
        for (k in S1.open) S1.open[k].d = Math.max(0.02, tNow - S1.open[k].t);
        s1_grow();
        S1.dirty = 1;
    }
    if (S1.dirty && now - S1.dirtyAt >= S1_VIEW_MS) {
        S1.dirty = 0;
        S1.dirtyAt = now;
        md_changed(G.M);
        ui_redraw();
    }
    // the playhead: the take being played, or Studio One's position in the score's bars
    var ph = -1;
    if (P) ph = tNow * TPQ;
    else if (playing && S1.anchored && host >= S1.origin) ph = (host - S1.origin) * TPQ;
    G.play = ph;
    play(ph);
    // a status message is shown for 9 s: repaint once when it goes
    var fresh = !!G.status && now - G.statusTime < 9000;
    if (S1.statusOn && !fresh) ui_redraw();
    S1.statusOn = fresh;
}

// ------------------------------------------------- settings (the brain's part)
function s1_param(name, v) {
    if (br_setOpt("" + name, v)) ui_redraw();
}

// ------------------------------------------------------------- saving
function s1_saveKey() { return G.M.editVersion + "|" + G.optVersion + "|" + S1.rec + "|" + G.M.name + "|" + S1.origin + "|" + S1.anchored; }

function s1_save() {
    var M = G.M, notes = [];
    for (var i = 0; i < M.notes.length; i++) {
        var n = M.notes[i];
        notes.push([n.p, Math.round(n.t * 1e6) / 1e6, Math.round(n.d * 1e6) / 1e6, n.v, n.m, n.sp, n.st]);
    }
    return JSON.stringify({ v: 1, notes: notes, num: M.num, den: M.den, len: M.lenBeats, name: M.name,
                            opt: G.opt, rec: S1.rec, origin: S1.origin, anchored: S1.anchored });
}

function s1_saveIfChanged() {
    if (S1.pass) return "";                       // a take is saved when it ends
    var k = s1_saveKey();
    if (k === S1.savedKey) return "";
    S1.savedKey = k;
    return s1_save();
}

function s1_load(json) {
    var d = JSON.parse(json), M = G.M, i;
    if (!d || d.v !== 1) return false;
    S1.pass = null; S1.open = {};
    M.notes = []; M.nextId = 1;
    for (i = 0; i < (d.notes || []).length; i++) {
        var a = d.notes[i];
        M.notes.push(md_note(M, a[0], +a[1], +a[2], a[3], a[4], a[5], a[6]));
    }
    M.num = d.num || 4; M.den = d.den || 4;
    M.lenBeats = d.len > 0 ? d.len : 4 * M.num * 4 / M.den;
    M.name = d.name || "";
    M.undo = []; M.redo = [];
    md_changed(M);
    var o = d.opt || {};
    for (var key in G.opt) if (o[key] !== undefined) br_setOpt(key, key === "key" ? o[key] + 7 : o[key]);
    G.optVersion++;
    S1.rec = d.rec === undefined ? 1 : (d.rec ? 1 : 0);
    S1.origin = +d.origin || 0;
    S1.anchored = !!d.anchored;
    S1.savedKey = s1_saveKey();
    V.lkey = "";
    ui_redraw();
    return true;
}

// ------------------------------------------------------------- exports
function s1_exportName(fmt) { return ex_fileName(G.M.name || "Spartito", br_EXT[fmt] || fmt); }

function s1_export(fmt, path) {
    var err = br_export(fmt, path);
    ui_say(err ? "Export failed: " + err : "Exported " + ex_withExt(path, br_EXT[fmt]).replace(/^.*[\/\\]/, "") + ".");
    return err || "";
}

function s1_setName(s) {
    s = ("" + s).replace(/[\r\n\t]/g, " ").substring(0, 80);
    if (s === G.M.name) return;
    G.M.name = s;
    md_touch(G.M);
    ui_changed();
}

function s1_wheel(dy) {
    if (!V.L) return;
    V.scroll -= dy;
    ui_clampScroll();
    ui_redraw();
}

// ------------------------------------------------------------- drawing
function s1_paint() {
    mgraphics.begin();
    mgraphics.dirty = false;
    paint();
    return JSON.stringify(mgraphics.ops);
}
function s1_dirty() { return mgraphics.dirty ? 1 : 0; }
function s1_out() {
    if (!s1_OUT.length) return "";
    var o = s1_OUT;
    s1_OUT = [];
    return JSON.stringify(o);
}

// ---------------------------------------- the toolbar: REC and CLEAR first
var s1_specOrig = ui_toolbarSpec;
ui_toolbarSpec = function () {
    var rows = s1_specOrig(), r1 = rows[0];
    function btn(id, label, w, on, dim) {
        return { id: id, label: label, w: w, on: !!on, icon: "", dim: !!dim, gap: false, lab: false, link: false };
    }
    r1.unshift(btn("s1_rec", S1.pass ? "RECORDING" : "REC", S1.pass ? 84 : 42, S1.rec),
               btn("s1_clear", "CLEAR", 50, false, !G.M.notes.length));
    r1[2].gap = true;
    return rows;
};

var s1_actionOrig = ui_action;
ui_action = function (id) {
    if (id === "s1_rec") {
        S1.rec = S1.rec ? 0 : 1;
        if (!S1.rec) s1_endPass();
        ui_say(S1.rec ? "REC on: what this track plays is written into the score." : "REC off: the score is not changed by playing.");
        return;
    }
    if (id === "s1_clear") {
        var M = G.M;
        if (!M.notes.length) return;
        s1_endPass();
        md_snapshot(M);
        M.notes = [];
        M.lenBeats = 4 * s1_bar();
        S1.origin = 0;
        S1.anchored = false;
        md_changed(M);
        ui_changed();
        ui_say("An empty score. UNDO brings the notes back.");
        return;
    }
    return s1_actionOrig(id);
};

var s1_hintOrig = ui_btnHint;
ui_btnHint = function (id) {
    if (id === "s1_rec") return "Write what this track plays into the score: with Studio One playing, in the song's bars";
    if (id === "s1_clear") return "Start an empty score (UNDO brings it back)";
    if (id === "x_midi") return "Export a Standard MIDI File: drag it onto a track in Studio One";
    return s1_hintOrig(id);
};

// a click on the title in the status bar names the score
var s1_downOrig = ui_down;
ui_down = function (x, y, mod1, shift, opt, mod2) {
    if (y >= V.h - UI_SB) {
        if (x >= S1.nameX0 && x <= S1.nameX1) outlet(0, "s1_rename", G.M.name);
        return;
    }
    return s1_downOrig(x, y, mod1, shift, opt, mod2);
};

// the status bar: what REC is doing instead of which Live clip is shown
ui_statusbar = function (g) {
    var y = V.h - UI_SB, M = br_model(), D = [];
    ui_fill(g, 0, y, V.w, UI_SB, ui_C.bg);
    var P = S1.pass;
    gl_circle(D, 14, y + 12, 4, P ? ui_C.warn : (S1.rec ? ui_C.ok : ui_C.dim));
    dr_ops(g, D, 0, 0);
    var s1 = P ? (P.clock === "host" ? "RECORDING in the song's bars" : "RECORDING - transport stopped, a take starts on a new bar")
               : (S1.rec ? "REC on - play, or let Studio One play this track" : "REC off - write and edit on the staves");
    ui_text(g, s1, 24, y + 16, 11, P ? ui_C.warn : ui_C.txt, "left", 1);
    var x = 24 + ui_textWidth(g, s1, 11, 1) + 14;
    var meter = M.num + "/" + M.den;
    ui_text(g, meter, x, y + 16, 11, ui_C.dim, "left", 0);
    x += ui_textWidth(g, meter, 11, 0) + 14;
    var title = M.name ? "\"" + M.name + "\"" : "untitled - click to name";
    var hot = V.my >= y && V.mx >= x && V.mx <= x + ui_textWidth(g, title, 11, 0);
    ui_text(g, title, x, y + 16, 11, hot ? ui_C.on : (M.name ? ui_C.txt : ui_C.dim), "left", 0);
    S1.nameX0 = x; S1.nameX1 = x + ui_textWidth(g, title, 11, 0);
    var now = s1_now();
    var fresh = G.status && now - G.statusTime < 9000;
    var msg = fresh ? G.status : V.hint;
    if (msg) ui_text(g, msg, V.w - 10, y + 16, 11, fresh ? ui_C.on : ui_C.txt, "right", 0);
};

// the status bar's title lights up under the mouse
var s1_hoverOrig = ui_hover;
ui_hover = function (x, y) {
    var was = V.my >= V.h - UI_SB && V.mx >= S1.nameX0 && V.mx <= S1.nameX1;
    s1_hoverOrig(x, y);
    var is = y >= V.h - UI_SB && x >= S1.nameX0 && x <= S1.nameX1;
    if (was !== is) ui_redraw();
};

// the jsui mouse handlers take eight arguments: x, y, button, mod1, shift, caps, option, mod2
// (packed here: 1 mod1, 2 shift, 4 option, 8 mod2 - the right button on Windows)
function s1_mouse(kind, x, y, but, m) {
    var a = [x, y, but, m & 1 ? 1 : 0, m & 2 ? 1 : 0, 0, m & 4 ? 1 : 0, m & 8 ? 1 : 0];
    if (kind === "click") onclick.apply(null, a);
    else if (kind === "drag") ondrag.apply(null, a);
    else if (kind === "idle") onidle.apply(null, a);
}
