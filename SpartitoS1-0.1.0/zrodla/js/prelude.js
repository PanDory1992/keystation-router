// ============================================================================
//  Spartito S1 - prelude: what Max gives spartito.js, given by the plugin
//
//  spartito.js runs here as the EDITOR view ([jsui]), unchanged but for a few
//  sentences listed in build.py. Max's objects become small stand-ins:
//
//    mgraphics        records the drawing calls; the plugin rasterises them
//    outlet()         queues the messages; the plugin answers them
//    File             collects what is written and hands it to the plugin
//    MGraphics, Image, JitterMatrix
//                     the PNG export: an offscreen recording the plugin
//                     rasterises and writes as a .png
//    Task, Global     absent: spartito.js already copes without them
//
//  Host functions (defined by the plugin before this file runs):
//    __s1_measure(text, family, bold, italic, size) -> width in pixels
//    __s1_write_text(path, string) / __s1_write_bytes(path, array) -> bool
//    __s1_png(path, w, h, opsJson) -> "" or an error
// ============================================================================

var jsarguments = ["spartito.js", "view"];
var s1_OUT = [];

function post() {}
function outlet(n) {
    var a = [];
    for (var i = 1; i < arguments.length; i++) a.push(arguments[i]);
    s1_OUT.push(a);
}

// ------------------------------------------------------- the drawing recorder
// Every call is turned into ops: { k: "F", d: path, c } fill, { k: "S", d, c, w }
// stroke, { k: "T", x, y, s, size, fam, b, i, c } text - the same display list
// shapes the score uses, so one rasteriser draws both.
function S1Graphics(w, h) {
    this.w = w || 0;
    this.h = h || 0;
    this.relative_coords = 0;
    this.autofill = 0;
    this.ops = [];
    this.dirty = true;
    this._c = [0, 0, 0, 1];
    this._lw = 1;
    this._fam = "Arial";
    this._b = 0;
    this._i = 0;
    this._size = 10;
    this._d = [];
    this._x = 0;
    this._y = 0;
}

S1Graphics.prototype = {
    init: function () {},
    redraw: function () { this.dirty = true; },
    begin: function () { this.ops = []; this._d = []; },
    set_source_rgba: function (r, g, b, a) {
        if (r && r.length !== undefined) { this._c = [r[0], r[1], r[2], r.length > 3 ? r[3] : 1]; return; }
        this._c = [+r, +g, +b, a === undefined ? 1 : +a];
    },
    set_source_rgb: function (r, g, b) { this.set_source_rgba(r, g, b, 1); },
    set_line_width: function (w) { this._lw = +w; },
    new_path: function () { this._d = []; },
    move_to: function (x, y) { this._d.push("M", +x, +y); this._x = +x; this._y = +y; },
    line_to: function (x, y) { this._d.push("L", +x, +y); this._x = +x; this._y = +y; },
    curve_to: function (x1, y1, x2, y2, x, y) {
        this._d.push("C", +x1, +y1, +x2, +y2, +x, +y);
        this._x = +x; this._y = +y;
    },
    close_path: function () { this._d.push("Z"); },
    rectangle: function (x, y, w, h) {
        this._d.push("M", x, y, "L", x + w, y, "L", x + w, y + h, "L", x, y + h, "Z");
    },
    // Max: the corner is an oval ow wide and oh high
    rectangle_rounded: function (x, y, w, h, ow, oh) {
        var rx = Math.min(ow / 2, w / 2), ry = Math.min(oh / 2, h / 2), k = 0.5523;
        if (rx <= 0 || ry <= 0) { this.rectangle(x, y, w, h); return; }
        var d = this._d;
        d.push("M", x + rx, y, "L", x + w - rx, y,
               "C", x + w - rx + k * rx, y, x + w, y + ry - k * ry, x + w, y + ry,
               "L", x + w, y + h - ry,
               "C", x + w, y + h - ry + k * ry, x + w - rx + k * rx, y + h, x + w - rx, y + h,
               "L", x + rx, y + h,
               "C", x + rx - k * rx, y + h, x, y + h - ry + k * ry, x, y + h - ry,
               "L", x, y + ry,
               "C", x, y + ry - k * ry, x + rx - k * rx, y, x + rx, y, "Z");
    },
    fill: function () {
        if (this._d.length) this.ops.push({ k: "F", d: this._d, c: this._c.slice(0) });
        this._d = [];
    },
    fill_preserve: function () {
        if (this._d.length) this.ops.push({ k: "F", d: this._d.slice(0), c: this._c.slice(0) });
    },
    stroke: function () {
        if (this._d.length) this.ops.push({ k: "S", d: this._d, c: this._c.slice(0), w: this._lw });
        this._d = [];
    },
    stroke_preserve: function () {
        if (this._d.length) this.ops.push({ k: "S", d: this._d.slice(0), c: this._c.slice(0), w: this._lw });
    },
    select_font_face: function (family, slant, weight) {
        this._fam = "" + family;
        this._i = slant === "italic" || slant === 1 ? 1 : 0;
        this._b = weight === "bold" || weight === 1 ? 1 : 0;
    },
    set_font_size: function (s) { this._size = +s; },
    text_measure: function (s) {
        return [__s1_measure("" + s, this._fam, this._b, this._i, this._size), this._size * 1.15];
    },
    show_text: function (s) {
        s = "" + s;
        this.ops.push({ k: "T", x: this._x, y: this._y, s: s, size: this._size, fam: this._fam,
                        b: this._b, i: this._i, c: this._c.slice(0) });
        this._x += __s1_measure(s, this._fam, this._b, this._i, this._size);
    },
    save: function () {}, restore: function () {},
    translate: function () {}, scale: function () {}
};

var mgraphics = new S1Graphics(1200, 760);

function MGraphics(w, h) { S1Graphics.call(this, w, h); }
MGraphics.prototype = S1Graphics.prototype;

function Image(mg) { this.mg = mg; }
Image.prototype.tonamedmatrix = function (name) { s1_MATRICES[name].mg = this.mg; };
Image.prototype.freepeer = function () {};

var s1_MATRICES = {}, s1_matrixN = 0;
function JitterMatrix() { this.name = "s1m" + (s1_matrixN++); this.mg = null; s1_MATRICES[this.name] = this; }
JitterMatrix.prototype.exportimage = function (path) {
    var mg = this.mg;
    delete s1_MATRICES[this.name];
    if (!mg) throw "no image";
    var err = __s1_png("" + path, Math.ceil(mg.w), Math.ceil(mg.h), JSON.stringify(mg.ops));
    if (err) throw err;
};
JitterMatrix.prototype.freepeer = function () { delete s1_MATRICES[this.name]; };

// ------------------------------------------------------------------- files
function File(path, mode) {
    this.path = "" + path;
    this.mode = mode || "read";
    this.isopen = this.mode === "write";
    this.text = "";
    this.bytes = null;
    this.position = 0;
    this.eof = 0;
}
File.prototype.writestring = function (s) { this.text += s; this.position += s.length; };
File.prototype.writebytes = function (b) {
    if (!this.bytes) this.bytes = [];
    for (var i = 0; i < b.length; i++) this.bytes.push(b[i] & 255);
    this.position += b.length;
};
File.prototype.writeline = function (s) { this.writestring(s + "\n"); };
File.prototype.close = function () {
    if (!this.isopen) return;
    this.isopen = false;
    var ok = this.bytes ? __s1_write_bytes(this.path, this.bytes) : __s1_write_text(this.path, this.text);
    if (!ok) throw "cannot write " + this.path;
};

// ---- spartito.js follows
