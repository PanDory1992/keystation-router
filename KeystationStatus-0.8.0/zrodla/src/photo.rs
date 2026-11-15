//! 0.8.0: one screen. Miki's drawings of the Keystation Pro 88 (six backgrounds: keyboard on or off,
//! pedal in A37, A38 or none) with, on top of them, in the technical monochrome style of his
//! reference sheets (paper labels, hairlines, corner brackets, mono figures, a little Japanese):
//!   - the LCD: the router's state, a line per setting, click a line to change it;
//!   - every knob, fader and button: what it does and its state;
//!   - the lower screen: velocity as it leaves the router (curve with columns, or the distribution),
//!     switched by the button on Audio Controls (a button of the plugin only);
//!   - the sustain jacks: where the pedal is (click to tell; a pedal press sets A37 by itself).
//! Positions are pixels of the 1920x1920 backgrounds, in assets/layout.json.

use crate::cmd::Command;
use crate::live::{now_unix, LiveState};
use crate::velo::{histogram, Curves, Velo};
use nih_plug_egui::egui::{
    self, epaint::PathStroke, Align2, Color32, CornerRadius, FontFamily, FontId, Pos2, Rect, Sense, Shape, Stroke,
    StrokeKind, TextureHandle, Vec2,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::OnceLock;

const LAYOUT: &str = include_str!("../assets/layout.json");
pub const BACKGROUNDS: [(&str, &[u8]); 6] = [
    ("KEY_DEF_A37", include_bytes!("../assets/KEY_DEF_A37.png")),
    ("KEY_A38", include_bytes!("../assets/KEY_A38.png")),
    ("KEY_AOFF", include_bytes!("../assets/KEY_AOFF.png")),
    ("KEY_GASZ_A37", include_bytes!("../assets/KEY_GASZ_A37.png")),
    ("KEY_GASZ_A38", include_bytes!("../assets/KEY_GASZ_A38.png")),
    ("KEY_GASZ_EMPTY", include_bytes!("../assets/KEY_GASZ_EMPTY.png")),
];

pub const CAP: &str = "cap";
pub const CAP_B: &str = "cap-b";
pub const MONO: &str = "mono";
pub const MONO_M: &str = "mono-m";

const PAPER: Color32 = Color32::from_rgb(232, 232, 227);
const INK: Color32 = Color32::from_rgb(17, 18, 20);
const GREY: Color32 = Color32::from_rgb(112, 113, 112);
const ACCENT: Color32 = Color32::from_rgb(52, 150, 92);
const EPAPER: Color32 = Color32::from_rgba_premultiplied(206, 209, 200, 236);
const FLASH_S: f64 = 0.6;
const TOUCH_ORDER: [&str; 5] = ["light", "acoustic", "heavy", "moje", "moje3"];
const RELEASE_ORDER: [u16; 3] = [60, 120, 250];

/// What the plugin remembers with the project.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Prefs {
    /// 0 = the curve with what you play, 1 = distribution of the last hits
    pub screen: u8,
    /// where the sustain pedal is plugged: "A37", "A38" or "none"
    pub jack: String,
}

impl Default for Prefs {
    fn default() -> Self {
        Prefs { screen: 0, jack: "A37".into() }
    }
}

pub struct Control {
    pub id: String,
    pub x: f32,
    pub y: f32,
    pub short: String,
    pub long: String,
    pub group: String,
}

pub struct Layout {
    pub w: f32,
    pub h: f32,
    pub lcd: [f32; 4],
    pub screen: [f32; 4],
    pub knob_r: f32,
    pub fader_top: f32,
    pub fader_bottom: f32,
    pub button: [f32; 2],
    pub screen_button: [f32; 3],
    pub jacks: Vec<(String, [f32; 2])>,
    pub jack_r: f32,
    pub snapshot: [f32; 2],
    pub snapshot_keys: Vec<[f32; 2]>,
    pub snapshot_key: [f32; 2],
    pub backgrounds: Vec<(String, String)>,
    pub knobs: Vec<Control>,
    pub faders: Vec<Control>,
    pub buttons: Vec<Control>,
    groups: Vec<(String, String)>,
}

fn f(v: &Value) -> f32 {
    v.as_f64().unwrap_or(0.0) as f32
}
fn rect4(v: &Value) -> [f32; 4] {
    [f(&v[0]), f(&v[1]), f(&v[2]), f(&v[3])]
}
fn pt(v: &Value) -> [f32; 2] {
    [f(&v[0]), f(&v[1])]
}

fn controls(v: &Value) -> Vec<Control> {
    v.as_array()
        .map(|a| {
            a.iter()
                .map(|c| Control {
                    id: c["id"].as_str().unwrap_or("").to_owned(),
                    x: f(&c["x"]),
                    y: f(&c["y"]),
                    short: c["short"].as_str().unwrap_or("").to_owned(),
                    long: c["long"].as_str().unwrap_or("").to_owned(),
                    group: c["group"].as_str().unwrap_or("").to_owned(),
                })
                .collect()
        })
        .unwrap_or_default()
}

impl Layout {
    pub fn parse(text: &str) -> Layout {
        let v: Value = serde_json::from_str(text).expect("layout.json");
        let map = |k: &str| -> Vec<(String, Value)> {
            v[k].as_object().map(|m| m.iter().map(|(a, b)| (a.clone(), b.clone())).collect()).unwrap_or_default()
        };
        Layout {
            w: f(&v["width"]),
            h: f(&v["height"]),
            lcd: rect4(&v["lcd"]),
            screen: rect4(&v["screen"]),
            knob_r: f(&v["knob_r"]),
            fader_top: f(&v["fader_track"]["top"]),
            fader_bottom: f(&v["fader_track"]["bottom"]),
            button: pt(&v["button_size"]),
            screen_button: [f(&v["screen_button"][0]), f(&v["screen_button"][1]), f(&v["screen_button"][2])],
            jacks: map("jacks").into_iter().map(|(k, p)| (k, pt(&p))).collect(),
            jack_r: f(&v["jack_r"]),
            snapshot: pt(&v["snapshot"]),
            snapshot_keys: v["snapshot_keys"].as_array().map(|a| a.iter().map(pt).collect()).unwrap_or_default(),
            snapshot_key: pt(&v["snapshot_key_size"]),
            backgrounds: map("backgrounds").into_iter().map(|(k, b)| (k, b.as_str().unwrap_or("").to_owned())).collect(),
            knobs: controls(&v["knobs"]),
            faders: controls(&v["faders"]),
            buttons: controls(&v["buttons"]),
            groups: map("group_names").into_iter().map(|(k, n)| (k, n.as_str().unwrap_or("").to_owned())).collect(),
        }
    }

    fn group_name<'a>(&'a self, group: &'a str) -> &'a str {
        self.groups.iter().find(|g| g.0 == group).map(|g| g.1.as_str()).unwrap_or(group)
    }

    /// Which background: keyboard on or off, pedal in A37, A38 or none.
    pub fn background(&self, keyboard_on: bool, jack: &str) -> &str {
        let pedal = match jack {
            "A37" => "a37",
            "A38" => "a38",
            _ => "none",
        };
        let key = format!("{}_{}", if keyboard_on { "on" } else { "off" }, pedal);
        self.backgrounds.iter().find(|b| b.0 == key).map(|b| b.1.as_str()).unwrap_or("KEY_DEF_A37")
    }
}

pub fn layout() -> &'static Layout {
    static L: OnceLock<Layout> = OnceLock::new();
    L.get_or_init(|| Layout::parse(LAYOUT))
}

/// Decodes one background (PNG, used exactly as drawn) and uploads it.
pub fn texture(ctx: &egui::Context, name: &str) -> Option<TextureHandle> {
    let bytes = BACKGROUNDS.iter().find(|b| b.0 == name)?.1;
    let mut reader = png::Decoder::new(std::io::Cursor::new(bytes)).read_info().ok()?;
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).ok()?;
    let size = [info.width as usize, info.height as usize];
    let image = match info.color_type {
        png::ColorType::Rgba => egui::ColorImage::from_rgba_unmultiplied(size, &buf[..info.buffer_size()]),
        _ => egui::ColorImage::from_rgb(size, &buf[..info.buffer_size()]),
    };
    Some(ctx.load_texture(format!("keystation-{name}"), image, egui::TextureOptions::LINEAR))
}

pub fn note_name(n: u8) -> String {
    const NAMES: [&str; 12] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "H"];
    format!("{}{}", NAMES[(n % 12) as usize], n as i32 / 12 - 1)
}

pub fn touch_name(t: Option<&str>) -> &'static str {
    match t {
        Some("light") => "LIGHT",
        Some("acoustic") => "ACOUSTIC",
        Some("heavy") => "HEAVY",
        Some("moje") => "MOJE",
        Some("moje3") => "MOJE 3",
        _ => "?",
    }
}

fn touch_short(t: Option<&str>) -> &'static str {
    match t {
        Some("acoustic") => "ACOUS",
        Some("moje3") => "MOJE3",
        other => touch_name(other),
    }
}

pub fn next_touch(t: Option<&str>) -> &'static str {
    let i = TOUCH_ORDER.iter().position(|m| Some(*m) == t).map_or(0, |i| i + 1);
    TOUCH_ORDER[i % TOUCH_ORDER.len()]
}

pub fn next_release(ms: Option<u16>) -> u16 {
    let i = RELEASE_ORDER.iter().position(|m| Some(*m) == ms).map_or(1, |i| i + 1);
    RELEASE_ORDER[i % RELEASE_ORDER.len()]
}

fn on_off(on: Option<bool>) -> &'static str {
    match on {
        Some(true) => "WŁ",
        Some(false) => "WYŁ",
        None => "?",
    }
}


/// Maps background pixels to screen points.
struct Map {
    o: Pos2,
    k: f32,
}

impl Map {
    fn p(&self, x: f32, y: f32) -> Pos2 {
        self.o + Vec2::new(x * self.k, y * self.k)
    }
    fn r(&self, x0: f32, y0: f32, x1: f32, y1: f32) -> Rect {
        Rect::from_min_max(self.p(x0, y0), self.p(x1, y1))
    }
    fn rc(&self, cx: f32, cy: f32, w: f32, h: f32) -> Rect {
        self.r(cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
    }
    fn font(&self, family: &str, px: f32) -> FontId {
        FontId::new(px * self.k, FontFamily::Name(family.into()))
    }
    fn w(&self, px: f32) -> f32 {
        (px * self.k).max(0.6)
    }
}

/// A paper label with a hairline border (inverted: ink with paper letters).
fn tag(p: &egui::Painter, m: &Map, cx: f32, cy: f32, text: &str, inverted: bool) -> Rect {
    tag_sized(p, m, cx, cy, text, inverted, 17.0)
}

fn tag_sized(p: &egui::Painter, m: &Map, cx: f32, cy: f32, text: &str, inverted: bool, px: f32) -> Rect {
    let (bg, fg) = if inverted { (INK, PAPER) } else { (PAPER, INK) };
    let g = p.layout_no_wrap(text.to_uppercase(), m.font(CAP, px), fg);
    let r = Rect::from_center_size(m.p(cx, cy), g.size() + Vec2::new(10.0 * m.k, 3.0 * m.k));
    p.rect_filled(r, CornerRadius::from(2.0 * m.k), bg);
    p.rect_stroke(r, CornerRadius::from(2.0 * m.k), Stroke::new(m.w(1.4), INK), StrokeKind::Inside);
    p.galley(r.center() - g.size() / 2.0, g, fg);
    r
}

/// A small ink box with a figure in it ("--" when not known).
fn figure(p: &egui::Painter, m: &Map, cx: f32, cy: f32, w: f32, text: &str, known: bool) {
    let r = m.rc(cx, cy, w, 24.0);
    p.rect_filled(r, CornerRadius::from(2.0 * m.k), Color32::from_rgba_premultiplied(14, 15, 16, 235));
    p.text(r.center(), Align2::CENTER_CENTER, text, m.font(MONO_M, 18.0), if known { PAPER } else { GREY });
}

/// Corner brackets around a rectangle (the registration marks of the reference sheets).
fn brackets(p: &egui::Painter, r: Rect, len: f32, stroke: Stroke) {
    for (c, dx, dy) in [(r.left_top(), 1.0, 1.0), (r.right_top(), -1.0, 1.0), (r.left_bottom(), 1.0, -1.0), (r.right_bottom(), -1.0, -1.0)] {
        p.line_segment([c, c + Vec2::new(dx * len, 0.0)], stroke);
        p.line_segment([c, c + Vec2::new(0.0, dy * len)], stroke);
    }
}

fn arc(p: &egui::Painter, c: Pos2, r: f32, from: f32, to: f32, stroke: Stroke) {
    let steps = (((to - from).abs() / 6.0).ceil() as usize).max(2);
    let pts: Vec<Pos2> = (0..=steps)
        .map(|i| {
            let a = (from + (to - from) * i as f32 / steps as f32).to_radians();
            c + Vec2::new(a.cos(), a.sin()) * r
        })
        .collect();
    p.add(Shape::line(pts, stroke));
}

fn dashed_h(p: &egui::Painter, a: Pos2, b: Pos2, k: f32, color: Color32) {
    p.add(Shape::dashed_line(&[a, b], Stroke::new((k * 1.0).max(0.6), color), 4.0 * k, 5.0 * k));
}

fn tip(id: &str, group: &str, long: &str, now: &str) -> String {
    format!("{id} // {group}\n{long}\nTeraz: {now}")
}

/// The whole editor: one screen. Returns a router command when something was clicked.
pub fn draw(ui: &mut egui::Ui, s: &LiveState, tex: &TextureHandle, velo: &Velo, curves: &Curves, prefs: &mut Prefs) -> Option<Command> {
    let lay = layout();
    let avail = ui.available_rect_before_wrap();
    let k = (avail.width() / lay.w).min(avail.height() / lay.h).max(0.05);
    let size = Vec2::new(lay.w * k, lay.h * k);
    let o = avail.center() - size / 2.0;
    let m = Map { o, k };
    let (canvas, _) = ui.allocate_exact_size(avail.size(), Sense::hover());
    let p = ui.painter_at(canvas);
    p.image(tex.id(), Rect::from_min_size(o, size), Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)), Color32::WHITE);

    let fresh = s.is_fresh();
    let now = now_unix();
    let pressed = s.button.as_ref().filter(|b| now - b.t < FLASH_S).map(|b| b.label.clone());
    let reading = fresh && s.reading > 0.0;
    let mut command = None;

    lcd(ui, &p, &m, s, fresh, reading, &mut command);
    screen(&p, &m, s, velo, curves, prefs.screen);

    // --- Audio Controls: the plugin's own button switches the lower screen ---
    let [bx, by, bs] = lay.screen_button;
    let br = m.rc(bx, by, bs, bs);
    let resp = ui.interact(br.expand(6.0 * k), ui.id().with("screen-mode"), Sense::click()).on_hover_text(
        "Przycisk wtyczki (nie ma go na klawiaturze): przełącza dolny ekran.\n01 KRZYWA: aktualna krzywa i to, co grasz.\n02 ROZKŁAD: których poziomów dynamiki używasz (ostatnie 400 uderzeń).",
    );
    if resp.clicked() {
        prefs.screen = (prefs.screen + 1) % 2;
    }
    brackets(&p, br.expand(5.0 * k), 9.0 * k, Stroke::new(m.w(2.0), if resp.hovered() { ACCENT } else { PAPER }));
    tag(&p, &m, bx, by + bs / 2.0 + 26.0, if prefs.screen == 0 { "Ekran 01 // krzywa" } else { "Ekran 02 // rozkład" }, true);

    // --- the sustain jacks: where the pedal is ---
    for (name, [x, y]) in &lay.jacks {
        if name == "A36" {
            continue;
        }
        let r = m.rc(*x, *y, lay.jack_r * 2.0, lay.jack_r * 2.0);
        let here = prefs.jack == *name;
        let resp = ui.interact(r, ui.id().with(("jack", name.as_str())), Sense::click()).on_hover_text(format!(
            "{name}: {}\nKliknij, gdy przełożysz pedał (drugi raz: bez pedału). Wciśnięcie pedału samo ustawia A37.",
            if here { "tu jest pedał" } else { "pusto" }
        ));
        if resp.clicked() {
            prefs.jack = if here { "none".into() } else { name.clone() };
        }
        if resp.hovered() {
            brackets(&p, r, 10.0 * k, Stroke::new(m.w(2.0), ACCENT));
        }
    }

    // --- SNAPSHOT: read where the knobs and faders are, without sending anything on ---
    let [sx, sy] = lay.snapshot;
    let label = if reading { format!("Wciśnij − i +  {:.0} s", s.reading.ceil()) } else { "Snapshot // pozycje gałek".into() };
    let sr = tag(&p, &m, sx, sy, &label, reading);
    let resp = ui.interact(sr, ui.id().with("read-controls"), if fresh { Sense::click() } else { Sense::hover() }).on_hover_text(
        "Pokazuje, gdzie stoją gałki i suwaki.\nKliknij, potem wciśnij na klawiaturze − i + naraz (SNAPSHOT).\nPrzez kilka sekund router tylko czyta pozycje: Pianoteq i mikser nic nie dostają.",
    );
    if resp.hovered() && fresh {
        brackets(&p, sr.expand(4.0 * k), 6.0 * k, Stroke::new(m.w(1.6), ACCENT));
    }
    if resp.clicked() && fresh {
        command = Some(Command::ReadControls);
    }
    if reading {
        let [kw, kh] = lay.snapshot_key;
        if (now * 3.0).fract() < 0.6 {
            for [x, y] in &lay.snapshot_keys {
                brackets(&p, m.rc(*x, *y, kw + 14.0, kh + 14.0), 12.0 * k, Stroke::new(m.w(3.0), ACCENT));
            }
        }
        ui.ctx().request_repaint();
    }

    // --- knobs ---
    let unknown = "nieznane: kliknij SNAPSHOT // POZYCJE GAŁEK i wciśnij − i + na klawiaturze";
    let r = lay.knob_r;
    for c in &lay.knobs {
        let value = if c.id == "B17" { Some(s.half_knob.unwrap_or(s.half_depth)) } else { s.controls.get(&c.id).copied() };
        tag_sized(&p, &m, c.x, c.y - r - 19.0, &c.short, false, if c.short.chars().count() > 10 { 14.5 } else { 17.0 });
        let center = m.p(c.x, c.y);
        arc(&p, center, (r + 7.0) * k, 135.0, 405.0, Stroke::new(m.w(2.0), PAPER.gamma_multiply(0.28)));
        if let Some(v) = value.filter(|v| *v > 0) {
            arc(&p, center, (r + 7.0) * k, 135.0, 135.0 + 270.0 * v as f32 / 127.0, Stroke::new(m.w(3.0), PAPER));
        }
        let shown = match value {
            Some(v) if c.id == "B17" => format!("{:.0}%", v as f32 / 127.0 * 100.0),
            Some(v) => format!("{v:03}"),
            None => "--".into(),
        };
        figure(&p, &m, c.x, c.y, if c.id == "B17" { 50.0 } else { 42.0 }, &shown, value.is_some());
        ui.interact(m.rc(c.x, c.y - 10.0, 2.0 * r + 14.0, 2.0 * r + 40.0), ui.id().with(&c.id), Sense::hover())
            .on_hover_text(tip(&c.id, lay.group_name(&c.group), &c.long, if value.is_some() { &shown } else { unknown }));
    }

    // --- faders ---
    let (top, bottom) = (lay.fader_top, lay.fader_bottom);
    for c in &lay.faders {
        tag(&p, &m, c.x, top - 22.0, &c.short, false);
        let value = s.controls.get(&c.id).copied();
        let shown = match value {
            Some(127) => "0dB".to_owned(),
            Some(v) => format!("{v:03}"),
            None => "--".into(),
        };
        match value {
            Some(v) => {
                let y = bottom - v as f32 / 127.0 * (bottom - top);
                p.line_segment([m.p(c.x - 30.0, y), m.p(c.x + 30.0, y)], Stroke::new(m.w(3.0), PAPER));
                figure(&p, &m, c.x, (y + 22.0).min(bottom + 6.0), 48.0, &shown, true);
            }
            None => figure(&p, &m, c.x, bottom - 40.0, 48.0, &shown, false),
        }
        ui.interact(m.r(c.x - 30.0, top - 36.0, c.x + 30.0, bottom + 20.0), ui.id().with(&c.id), Sense::hover())
            .on_hover_text(tip(&c.id, lay.group_name(&c.group), &c.long, if value.is_some() { &shown } else { unknown }));
    }

    // --- buttons ---
    let [bw, bh] = lay.button;
    for c in &lay.buttons {
        tag(&p, &m, c.x, c.y - bh / 2.0 - 15.0, &c.short, false);
        let (active, state, cmd): (bool, Option<String>, Option<Command>) = match c.id.as_str() {
            "B46" => {
                let on = s.pedal_mode.as_deref() == Some("sustain");
                (on, on.then(|| "WŁ".into()), Some(Command::PedalMode("sustain")))
            }
            "B47" => {
                let on = s.pedal_mode.as_deref() == Some("sostenuto");
                (on, on.then(|| "WŁ".into()), Some(Command::PedalMode("sostenuto")))
            }
            "B48" => {
                let on = s.una_corda == Some(true);
                (on, Some(if on { "WŁ" } else { "wył" }.into()), s.una_corda.map(|on| Command::UnaCorda(!on)))
            }
            "C53" => (true, Some(touch_short(s.touch.as_deref()).into()), Some(Command::Touch(next_touch(s.touch.as_deref())))),
            _ => (false, None, None),
        };
        let rect = m.rc(c.x, c.y, bw, bh);
        if active && fresh {
            brackets(&p, rect.expand(5.0 * k), 11.0 * k, Stroke::new(m.w(2.6), PAPER));
        }
        if pressed.as_deref() == Some(c.id.as_str()) {
            brackets(&p, rect.expand(9.0 * k), 13.0 * k, Stroke::new(m.w(3.0), ACCENT));
        }
        if let (Some(st), true) = (&state, fresh) {
            figure(&p, &m, c.x, c.y, bw - 6.0, st, true);
        }
        let clickable = fresh && cmd.is_some();
        let mut t = tip(&c.id, lay.group_name(&c.group), &c.long, state.as_deref().unwrap_or("przycisk chwilowy (błyska przy naciśnięciu)"));
        if clickable {
            t.push_str("\nKliknij tutaj: to samo co przycisk.");
        }
        let resp = ui.interact(rect.expand(8.0 * k), ui.id().with(&c.id), if clickable { Sense::click() } else { Sense::hover() }).on_hover_text(t);
        if clickable && resp.hovered() {
            brackets(&p, rect.expand(2.0 * k), 7.0 * k, Stroke::new(m.w(1.6), ACCENT));
        }
        if clickable && resp.clicked() {
            command = cmd;
        }
    }
    command
}

/// The upper LCD: state of the router, a line per setting (click to change), last note.
fn lcd(ui: &mut egui::Ui, p: &egui::Painter, m: &Map, s: &LiveState, fresh: bool, reading: bool, command: &mut Option<Command>) {
    let [x0, y0, x1, y1] = layout().lcd;
    let k = m.k;
    p.rect_filled(m.r(x0, y0, x1, y1), CornerRadius::ZERO, EPAPER);
    brackets(p, m.r(x0 + 8.0, y0 + 8.0, x1 - 8.0, y1 - 8.0), 12.0 * k, Stroke::new(m.w(1.4), INK));
    p.text(m.p(x0 + 22.0, y0 + 30.0), Align2::LEFT_CENTER, "01 // ROUTER 状態", m.font(MONO, 15.0), GREY);
    let online = if fresh { "ONLINE" } else { "OFFLINE" };
    let g = p.layout_no_wrap(online.into(), m.font(MONO_M, 15.0), PAPER);
    let r = Rect::from_min_size(m.p(x1 - 22.0, y0 + 21.0) - Vec2::new(g.size().x + 10.0 * k, 0.0), g.size() + Vec2::new(10.0 * k, 2.0 * k));
    p.rect_filled(r, CornerRadius::ZERO, if fresh { INK } else { GREY });
    p.galley(r.min + Vec2::new(5.0 * k, 1.0 * k), g, PAPER);
    p.line_segment([m.p(x0 + 22.0, y0 + 46.0), m.p(x1 - 22.0, y0 + 46.0)], Stroke::new(m.w(1.0), INK));
    let (top, foot) = (y0 + 52.0, y1 - 48.0);
    if !fresh {
        for (i, t) in ["ROUTER NIE ODPOWIADA", "", "SPRAWDŹ NADZORCĘ (PANEL KEYSTATION)", "WRACA SAM W ~3 S"].iter().enumerate() {
            p.text(m.p(x0 + 26.0, top + 30.0 + i as f32 * 32.0), Align2::LEFT_CENTER, *t, m.font(CAP_B, 24.0), INK);
        }
        return;
    }
    let moje = matches!(s.touch.as_deref(), Some("moje") | Some("moje3"));
    let ones = if moje { "W KRZYWEJ" } else if s.ones.as_deref() == Some("ppp") { "PPP" } else { "KONTEKST" };
    let rows: Vec<(&str, String, Option<Command>, &str)> = vec![
        ("PEDAŁ", match s.pedal_mode.as_deref() { Some("sostenuto") => "SOSTENUTO".into(), Some("sustain") => "SUSTAIN".into(), _ => "?".into() },
            Some(Command::PedalMode(if s.pedal_mode.as_deref() == Some("sostenuto") { "sustain" } else { "sostenuto" })),
            "Tryb pedału. Kliknij: sustain ↔ sostenuto. Kreski = jak mocno pedał jest wciśnięty."),
        ("UNA CORDA", on_off(s.una_corda).into(), s.una_corda.map(|on| Command::UnaCorda(!on)), "Una corda (przycisk B48). Kliknij: włącz / wyłącz."),
        ("CZUCIE", touch_name(s.touch.as_deref()).into(), Some(Command::Touch(next_touch(s.touch.as_deref()))), "Krzywa dynamiki routera (przycisk C53). Kliknij: następna."),
        ("„1”", ones.into(), if moje { None } else { Some(Command::Ones(if s.ones.as_deref() == Some("ppp") { "context" } else { "ppp" })) },
            "Co router robi z najcichszym dotykiem („1”). W czuciu Moje decyduje sama krzywa."),
        ("PÓŁPEDAŁ", format!("{}  {:.0}%", on_off(s.half_pedal), s.half_depth as f32 / 127.0 * 100.0), s.half_pedal.map(|on| Command::HalfPedal(!on)),
            "Półpedał: pedał wciska do głębokości z pokrętła B17. Kliknij: włącz / wyłącz."),
        ("PUSZCZANIE", s.release_ms.map(|r| format!("{r} MS")).unwrap_or_else(|| "?".into()), s.release_ms.map(|r| Command::ReleaseMs(next_release(Some(r)))),
            "Jak miękko tłumiki opadają po puszczeniu pedału. Kliknij: 60 / 120 / 250 ms."),
        ("ODBICIA", format!("{}  ({})", on_off(s.debounce), s.bounces), s.debounce.map(|on| Command::Debounce(!on)),
            "Filtr odbić styków; w nawiasie: ile usunął od startu routera. Kliknij: włącz / wyłącz."),
    ];
    let lh = (foot - top) / rows.len() as f32;
    for (i, (label, value, cmd, t)) in rows.into_iter().enumerate() {
        let y = top + lh * (i as f32 + 0.5);
        let hit = m.r(x0 + 16.0, y - lh / 2.0, x1 - 16.0, y + lh / 2.0);
        let resp = ui.interact(hit, ui.id().with(("lcd", i)), Sense::click()).on_hover_text(t);
        if resp.hovered() && cmd.is_some() {
            p.rect_filled(hit, CornerRadius::ZERO, Color32::from_rgba_premultiplied(10, 11, 12, 30));
            brackets(p, hit, 6.0 * k, Stroke::new(m.w(1.2), INK));
        }
        if resp.clicked() {
            *command = cmd;
        }
        p.text(m.p(x0 + 24.0, y), Align2::LEFT_CENTER, format!("{:02}", i + 1), m.font(MONO, 14.0), GREY);
        p.text(m.p(x0 + 60.0, y), Align2::LEFT_CENTER, label, m.font(CAP_B, 21.0), INK);
        p.text(m.p(x1 - 24.0, y), Align2::RIGHT_CENTER, value, m.font(MONO_M, 20.0), INK);
        if i == 0 {
            let lit = ((s.pedal_value as f32 / 127.0) * 8.0).ceil() as usize;
            for j in 0..8 {
                let xx = x0 + 200.0 + j as f32 * 13.0;
                p.rect_filled(m.r(xx, y - 8.0, xx + 8.0, y + 8.0), CornerRadius::ZERO, if j < lit { INK } else { Color32::from_rgba_premultiplied(10, 11, 12, 40) });
            }
        }
    }
    p.line_segment([m.p(x0 + 22.0, foot + 4.0), m.p(x1 - 22.0, foot + 4.0)], Stroke::new(m.w(1.0), INK));
    let fy = (foot + y1 - 8.0) / 2.0 + 2.0;
    if reading {
        p.rect_filled(m.r(x0 + 16.0, foot + 8.0, x1 - 16.0, y1 - 12.0), CornerRadius::ZERO, INK);
        p.text(m.p(x0 + 26.0, fy), Align2::LEFT_CENTER, format!("WCIŚNIJ  −  I  +  NARAZ   {:.0} S", s.reading.ceil()), m.font(MONO_M, 18.0), PAPER);
        return;
    }
    if let Some(last) = &s.last {
        p.text(m.p(x0 + 24.0, fy), Align2::LEFT_CENTER, format!("LAST  {}  →  {:03}", note_name(last.note), last.out), m.font(MONO_M, 18.0), INK);
    }
    let status = match s.connected { Some(true) => "鍵盤 // POŁĄCZONA", Some(false) => "鍵盤 // BRAK", None => "?" };
    p.text(m.p(x1 - 24.0, fy), Align2::RIGHT_CENTER, status, m.font(MONO_M, 16.0), INK);
}

/// The lower screen: velocity as the instrument gets it.
fn screen(p: &egui::Painter, m: &Map, s: &LiveState, velo: &Velo, curves: &Curves, mode: u8) {
    let [x0, y0, x1, y1] = layout().screen;
    let k = m.k;
    let now = now_unix();
    p.rect_filled(m.r(x0, y0, x1, y1), CornerRadius::ZERO, EPAPER);
    // header
    p.text(m.p(x0 + 26.0, y0 + 34.0), Align2::LEFT_CENTER, "強弱 // VELOCITY", m.font(CAP_B, 26.0), INK);
    let mode_txt = if mode == 0 { "MODE 01 // KRZYWA 曲線" } else { "MODE 02 // ROZKŁAD 分布" };
    let g = p.layout_no_wrap(mode_txt.into(), m.font(MONO_M, 16.0), PAPER);
    let tr = Rect::from_min_size(m.p(x1 - 26.0, y0 + 22.0) - Vec2::new(g.size().x + 12.0 * k, 0.0), g.size() + Vec2::new(12.0 * k, 4.0 * k));
    p.rect_filled(tr, CornerRadius::ZERO, INK);
    p.galley(tr.min + Vec2::new(6.0 * k, 2.0 * k), g, PAPER);
    p.text(tr.left_center() - Vec2::new(12.0 * k, 0.0), Align2::RIGHT_CENTER, touch_name(s.touch.as_deref()), m.font(MONO_M, 16.0), INK);
    // plot frame
    let (px0, py0, px1, py1) = (x0 + 78.0, y0 + 70.0, x1 - 30.0, y1 - 72.0);
    let plot = m.r(px0, py0, px1, py1);
    p.rect_stroke(plot, CornerRadius::ZERO, Stroke::new(m.w(1.0), INK), StrokeKind::Middle);
    brackets(p, plot.expand(8.0 * k), 14.0 * k, Stroke::new(m.w(1.6), INK));
    let x_of = |v: f32| px0 + v / 127.0 * (px1 - px0);
    let y_of = |v: f32| py1 - v / 127.0 * (py1 - py0);
    for v in [32.0, 64.0, 96.0] {
        dashed_h(p, m.p(px0, y_of(v)), m.p(px1, y_of(v)), k, GREY.gamma_multiply(0.7));
        if mode == 0 {
            p.text(m.p(px0 - 10.0, y_of(v)), Align2::RIGHT_CENTER, format!("{:03}", v as u8), m.font(MONO, 14.0), GREY);
        }
        p.line_segment([m.p(x_of(v), py1), m.p(x_of(v), py1 + 8.0)], Stroke::new(m.w(1.0), INK));
        p.text(m.p(x_of(v), py1 + 22.0), Align2::CENTER_CENTER, format!("{:03}", v as u8), m.font(MONO, 14.0), GREY);
    }
    if mode == 0 {
        p.text(m.p(px0 - 10.0, y_of(127.0)), Align2::RIGHT_CENTER, "127", m.font(MONO, 14.0), GREY);
    }
    let foot_y = y1 - 26.0;
    if mode == 0 {
        // the curve of the touch in use: white keys solid, black keys dashed
        let line = |c: &Vec<u8>| -> Vec<Pos2> { (0..128).map(|i| m.p(x_of(i as f32), y_of(c[i] as f32))).collect() };
        if curves.white.len() == 128 {
            p.add(Shape::line(line(&curves.black), PathStroke::new(m.w(1.6), GREY)));
            p.add(Shape::line(line(&curves.white), PathStroke::new(m.w(2.6), INK)));
        }
        // columns: x = how hard the key was struck, height = what the instrument got
        let cw = ((px1 - px0) / 128.0 * 1.7).max(3.0 / k);
        let mut last: Option<&crate::velo::Hit> = None;
        for h in &velo.hits {
            let a = h.alpha(now);
            if a <= 0.0 {
                continue;
            }
            let black = matches!(h.note % 12, 1 | 3 | 6 | 8 | 10);
            let col = if black { ACCENT } else { INK };
            // the column ends on the curve of its key colour, never above it
            let curve = if black { &curves.black } else { &curves.white };
            let top = curve.get(h.raw as usize).copied().unwrap_or(h.vel);
            let x = x_of(h.raw as f32);
            p.rect_filled(m.r(x - cw / 2.0, y_of(top as f32), x + cw / 2.0, py1), CornerRadius::ZERO, col.gamma_multiply(0.82 * a));
            if last.map_or(true, |l| h.t_on >= l.t_on) {
                last = Some(h);
            }
        }
        if let Some(h) = last {
            let a = h.alpha(now).max(0.25);
            p.text(m.p(px0 + 22.0, py0 + 40.0), Align2::LEFT_CENTER, format!("{:03}", h.vel), m.font(MONO_M, 54.0), INK.gamma_multiply(a));
            p.text(m.p(px0 + 24.0, py0 + 80.0), Align2::LEFT_CENTER, format!("{} {}", note_name(h.note), if h.sustained { "// PEDAŁ" } else { "" }), m.font(MONO, 16.0), GREY);
        }
        p.text(m.p(px1, py0 + 18.0), Align2::RIGHT_CENTER, "━ BIAŁE   ━ CZARNE (ZIELONE KOLUMNY)", m.font(MONO, 13.0), GREY);
        p.text(m.p(x0 + 26.0, foot_y), Align2::LEFT_CENTER, "X: SIŁA KLAWISZA  //  Y: CO DOSTAJE INSTRUMENT", m.font(MONO, 14.0), GREY);
    } else {
        let bins = histogram(&velo.history, 32);
        let max = bins.iter().copied().max().unwrap_or(0).max(1) as f32;
        let bw = (px1 - px0) / 32.0;
        for (i, &n) in bins.iter().enumerate() {
            if n == 0 {
                continue;
            }
            let xa = px0 + i as f32 * bw + bw * 0.12;
            p.rect_filled(m.r(xa, py1 - n as f32 / max * (py1 - py0) * 0.92, xa + bw * 0.76, py1), CornerRadius::ZERO, INK.gamma_multiply(0.88));
        }
        for (v, name) in [(16.0, "pp"), (33.0, "p"), (49.0, "mp"), (64.0, "mf"), (80.0, "f"), (96.0, "ff"), (112.0, "fff")] {
            let x = x_of(v);
            p.add(Shape::dashed_line(&[m.p(x, py0), m.p(x, py1)], Stroke::new(m.w(0.8), GREY.gamma_multiply(0.6)), 3.0 * k, 5.0 * k));
            p.text(m.p(x + 4.0, py0 + 16.0), Align2::LEFT_CENTER, name, m.font(MONO_M, 15.0), GREY);
        }
        let mut v: Vec<u8> = velo.history.iter().copied().collect();
        v.sort_unstable();
        let txt = if v.is_empty() {
            "ZAGRAJ COŚ: ROZKŁAD OSTATNICH 400 UDERZEŃ".to_owned()
        } else {
            let q = |f: f32| v[((v.len() - 1) as f32 * f).round() as usize];
            format!("N={:03}  //  MEDIANA {:03}  //  10–90%: {:03}–{:03}", v.len(), q(0.5), q(0.1), q(0.9))
        };
        p.text(m.p(x0 + 26.0, foot_y), Align2::LEFT_CENTER, txt, m.font(MONO, 14.0), GREY);
    }
    let bus = if velo.heard > 0.0 && now - velo.heard < 12.0 { "SZYNA // OK" } else { "SZYNA // CZEKAM" };
    p.text(m.p(x1 - 26.0, foot_y), Align2::RIGHT_CENTER, bus, m.font(MONO, 14.0), GREY);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout_has_every_control_once_inside_the_picture() {
        let l = layout();
        assert_eq!((l.knobs.len(), l.faders.len(), l.buttons.len()), (24, 9, 17));
        let mut ids: Vec<&str> = l.knobs.iter().chain(&l.faders).chain(&l.buttons).map(|c| c.id.as_str()).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), 50);
        for c in l.knobs.iter().chain(&l.faders).chain(&l.buttons) {
            assert!(c.x > 0.0 && c.x < l.w && c.y >= 0.0 && c.y < l.h, "{}", c.id);
            assert!(!c.short.is_empty() && !c.long.is_empty(), "{}", c.id);
        }
        assert!(l.lcd[0] < l.lcd[2] && l.screen[1] < l.screen[3] && l.fader_top < l.fader_bottom);
        assert_eq!(l.jacks.len(), 3);
    }

    #[test]
    fn six_backgrounds_for_six_states_used_as_drawn() {
        let l = layout();
        assert_eq!(l.background(true, "A37"), "KEY_DEF_A37");
        assert_eq!(l.background(true, "A38"), "KEY_A38");
        assert_eq!(l.background(true, "none"), "KEY_AOFF");
        assert_eq!(l.background(false, "A37"), "KEY_GASZ_A37");
        assert_eq!(l.background(false, "A38"), "KEY_GASZ_A38");
        assert_eq!(l.background(false, "none"), "KEY_GASZ_EMPTY");
        for (name, bytes) in BACKGROUNDS {
            let info = png::Decoder::new(std::io::Cursor::new(bytes)).read_info().unwrap().info().clone();
            assert_eq!((info.width, info.height), (1920, 1920), "{name}");
        }
    }

    #[test]
    fn cycles_and_names() {
        assert_eq!(next_touch(Some("moje3")), "light");
        assert_eq!(next_release(Some(250)), 60);
        assert_eq!(note_name(60), "C4");
        assert_eq!(Prefs::default(), Prefs { screen: 0, jack: "A37".into() });
    }
}
