// node smoke test of the bundle with fake host functions
const fs = require('fs');
global.__s1_measure = (s, f, b, i, size) => s.length * size * 0.55;
const written = {};
global.__s1_write_text = (p, s) => { written[p] = s; return true; };
global.__s1_write_bytes = (p, a) => { written[p] = a; return true; };
global.__s1_png = (p, w, h, ops) => { written[p] = [w, h, JSON.parse(ops).length]; return ""; };
(0, eval)(fs.readFileSync(__dirname + '/../assets/spartito-s1.js', 'utf8'));
const t0 = Date.now();
canvas(1200, 760);
let ops = JSON.parse(s1_paint());
console.log('empty paint ops', ops.length, Date.now() - t0, 'ms');
// play a few notes, transport stopped
let free = 10;
const ev = [];
for (const [p, t, d] of [[60, 0, 1], [64, 1, 1], [67, 2, 2], [48, 0, 4]]) { ev.push([1, p, 90, 0, free + t, 0]); ev.push([0, p, 0, 0, free + t + d, 0]); }
ev.sort((a, b) => a[4] - b[4]);
s1_input(JSON.stringify(ev));
console.log('pass', !!S1.pass, 'notes', G.M.notes.length);
S1.lastEv -= 5000; s1_tick(0, free + 6, 0, 100, 3, 4);
console.log('pass after tick', !!S1.pass, 'status', G.status, 'len', G.M.lenBeats);
// host pass in bar 9 (beats 32..)
s1_input(JSON.stringify([[1, 72, 80, 33, 0, 1], [0, 72, 0, 34, 0, 1]]));
s1_tick(35, 0, 1, 100, 3, 4);
console.log('origin', S1.origin, 'anchored', S1.anchored, 'barOffset', br_barOffset(), 'notes', G.M.notes.map(n => [n.p, n.t, n.d]).join(' '));
s1_tick(36, 0, 0, 100, 3, 4);
// replay the same part: no doubling
s1_input(JSON.stringify([[1, 72, 80, 33.01, 0, 1], [0, 72, 0, 34, 0, 1]])); s1_tick(36, 0, 0, 100, 3, 4);
console.log('after replay', G.M.notes.length);
const t1 = Date.now(); ops = JSON.parse(s1_paint()); console.log('paint ops', ops.length, Date.now() - t1, 'ms', 'kinds', [...new Set(ops.map(o => o.k))]);
// click toolbar REC, a staff, drag, keys
onidle(300, 200, 0, 0, 0, 0, 0, 0); console.log('hint', V.hint);
onclick(300, 200, 1, 0, 0, 0, 0, 0); ondrag(300, 200, 0, 0, 0, 0, 0, 0);
console.log('after click', G.M.notes.length, 'out', s1_out());
undefined;
focus(1); keyasc(8); console.log('after delete', G.M.notes.length);
ui_action('undo'); console.log('after undo', G.M.notes.length);
ui_action('zoom_in'); console.log('out', s1_out());
s1_param('zoom', 2); console.log('zoom', G.opt.zoom);
const saved = s1_save(); s1_load(saved); console.log('reload', G.M.notes.length, s1_saveIfChanged() === '');
for (const f of ['midi', 'pdf', 'xml', 'png']) console.log(f, JSON.stringify(s1_export(f, '/x/score')), s1_exportName(f));
console.log(Object.keys(written).map(k => k + ':' + (written[k].length || written[k])).join(' '));
console.log('status', G.status);
s1_paint(); onclick(1, 750, 1, 0, 0, 0, 0, 0); console.log('rename out', s1_out(), S1.nameX0, S1.nameX1);
