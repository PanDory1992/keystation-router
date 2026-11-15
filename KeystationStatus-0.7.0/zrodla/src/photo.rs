//! 0.7.0: the photo view. Two photos of Miki's Keystation Pro 88 (top panel and
//! knobs/faders) drawn as one picture; on top of it:
//!   - the LCD shows the router's state in an LCD font (click a line to change it),
//!   - every knob, fader and button gets a caption with what it really does and a
//!     small window with its current state (value, on/off, touch mode).
//! Positions and texts live in assets/layout.json (pixels of the photo), so a new
//! mapping is a JSON edit, not a code change.

use crate::cmd::Command;
use crate::live::{now_unix, LiveState};
use nih_plug_egui::egui::{
    self, Align2, Color32, CornerRadius, FontFamily, FontId, Pos2, Rect, Sense, Shape, Stroke, StrokeKind,
    TextureHandle, Vec2,
};
use serde_json::Value;
use std::sync::OnceLock;

const PHOTO: &[u8] = include_bytes!("../assets/keystation.jpg");
const LAYOUT: &str = include_str!("../assets/layout.json");

pub const LCD_FONT: &str = "lcd";
pub const CAPTION_FONT: &str = "caption";

const AMBER: Color32 = Color32::from_rgb(255, 170, 60);
const INK: Color32 = Color32::from_rgba_premultiplied(30, 35, 37, 235);
const INK_DIM: Color32 = Color32::from_rgba_premultiplied(8, 9, 10, 45);
const BOX: Color32 = Color32::from_rgba_premultiplied(9, 9, 9, 225);
const PILL: Color32 = Color32::from_rgba_premultiplied(16, 16, 18, 205);
const FLASH_S: f64 = 0.6;
const UNKNOWN: Color32 = Color32::from_rgb(120, 116, 108);
const TOUCH_ORDER: [&str; 5] = ["light", "acoustic", "heavy", "moje", "moje3"];
const RELEASE_ORDER: [u16; 3] = [60, 120, 250];

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
    pub tabs: [f32; 4],
    pub knob_r: f32,
    pub fader_top: f32,
    pub fader_bottom: f32,
    pub button: [f32; 2],
    pub knobs: Vec<Control>,
    pub faders: Vec<Control>,
    pub buttons: Vec<Control>,
    groups: Vec<(String, Color32, String)>,
}

fn f(v: &Value) -> f32 {
    v.as_f64().unwrap_or(0.0) as f32
}

fn rect4(v: &Value) -> [f32; 4] {
    [f(&v[0]), f(&v[1]), f(&v[2]), f(&v[3])]
}

fn hex(s: &str) -> Color32 {
    let n = u32::from_str_radix(s.trim_start_matches('#'), 16).unwrap_or(0xcccccc);
    Color32::from_rgb((n >> 16) as u8, (n >> 8) as u8, n as u8)
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
        let groups = v["groups"]
            .as_object()
            .map(|m| {
                m.iter()
                    .map(|(k, c)| {
                        let name = v["group_names"][k].as_str().unwrap_or(k).to_owned();
                        (k.clone(), hex(c.as_str().unwrap_or("#cccccc")), name)
                    })
                    .collect()
            })
            .unwrap_or_default();
        Layout {
            w: f(&v["width"]),
            h: f(&v["height"]),
            lcd: rect4(&v["lcd"]),
            tabs: rect4(&v["tabs"]),
            knob_r: f(&v["knob_r"]),
            fader_top: f(&v["fader_track"]["top"]),
            fader_bottom: f(&v["fader_track"]["bottom"]),
            button: [f(&v["button_size"][0]), f(&v["button_size"][1])],
            knobs: controls(&v["knobs"]),
            faders: controls(&v["faders"]),
            buttons: controls(&v["buttons"]),
            groups,
        }
    }

    fn color(&self, group: &str) -> Color32 {
        self.groups.iter().find(|g| g.0 == group).map(|g| g.1).unwrap_or(Color32::LIGHT_GRAY)
    }

    fn group_name<'a>(&'a self, group: &'a str) -> &'a str {
        self.groups.iter().find(|g| g.0 == group).map(|g| g.2.as_str()).unwrap_or(group)
    }
}

pub fn layout() -> &'static Layout {
    static L: OnceLock<Layout> = OnceLock::new();
    L.get_or_init(|| Layout::parse(LAYOUT))
}

/// Decodes the photo once and uploads it as a texture.
pub fn texture(ctx: &egui::Context) -> Option<TextureHandle> {
    let mut decoder = jpeg_decoder::Decoder::new(PHOTO);
    let pixels = decoder.decode().ok()?;
    let info = decoder.info()?;
    let size = [info.width as usize, info.height as usize];
    let image = egui::ColorImage::from_rgb(size, &pixels);
    Some(ctx.load_texture("keystation-photo", image, egui::TextureOptions::LINEAR))
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

/// Maps photo pixels to screen points.
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
}

fn pill(painter: &egui::Painter, m: &Map, cx: f32, cy: f32, text: &str, color: Color32) {
    let font = FontId::new(9.4 * m.k, FontFamily::Name(CAPTION_FONT.into()));
    let galley = painter.layout_no_wrap(text.to_owned(), font, color);
    let size = galley.size() + Vec2::new(8.0 * m.k, 2.0 * m.k);
    let rect = Rect::from_center_size(m.p(cx, cy), size);
    let r = CornerRadius::from(size.y / 2.0);
    painter.rect_filled(rect, r, PILL);
    painter.rect_stroke(rect, r, Stroke::new(m.k.max(1.0), color.gamma_multiply(0.8)), StrokeKind::Inside);
    painter.galley(rect.center() - galley.size() / 2.0, galley, color);
}

fn value_box(painter: &egui::Painter, m: &Map, cx: f32, cy: f32, w: f32, text: &str, color: Color32) {
    let rect = m.rc(cx, cy, w, 13.0);
    painter.rect_filled(rect, CornerRadius::from(3.0 * m.k), BOX);
    painter.text(
        rect.center() + Vec2::new(0.0, 0.5 * m.k),
        Align2::CENTER_CENTER,
        text,
        FontId::new(13.0 * m.k, FontFamily::Name(LCD_FONT.into())),
        color,
    );
}

fn arc(painter: &egui::Painter, c: Pos2, r: f32, from: f32, to: f32, stroke: Stroke) {
    let steps = (((to - from).abs() / 6.0).ceil() as usize).max(2);
    let pts: Vec<Pos2> = (0..=steps)
        .map(|i| {
            let a = (from + (to - from) * i as f32 / steps as f32).to_radians();
            c + Vec2::new(a.cos(), a.sin()) * r
        })
        .collect();
    painter.add(Shape::line(pts, stroke));
}

fn tooltip(id: &str, group: &str, long: &str, now: &str) -> String {
    format!("{id} · {group}\n{long}\nTeraz: {now}")
}

/// Which view the editor shows.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum View {
    Photo,
    Settings,
}

/// Draws the two tabs; returns the view picked (if any). `rect` in screen points.
pub fn tabs(ui: &mut egui::Ui, rect: Rect, k: f32, view: View) -> Option<View> {
    let mut picked = None;
    let w = (rect.width() - 6.0 * k) / 2.0;
    for (i, (v, text)) in [(View::Photo, "KLAWIATURA"), (View::Settings, "USTAWIENIA")].into_iter().enumerate() {
        let r = Rect::from_min_size(rect.min + Vec2::new(i as f32 * (w + 6.0 * k), 0.0), Vec2::new(w, rect.height()));
        let resp = ui.interact(r, ui.id().with(("tab", i)), Sense::click());
        let active = v == view;
        let cr = CornerRadius::from(rect.height() / 2.0);
        let fill = if active { AMBER } else if resp.hovered() { Color32::from_rgb(40, 38, 35) } else { PILL };
        let painter = ui.painter();
        painter.rect_filled(r, cr, fill);
        painter.rect_stroke(r, cr, Stroke::new(k.max(1.0), AMBER.gamma_multiply(0.8)), StrokeKind::Inside);
        painter.text(
            r.center(),
            Align2::CENTER_CENTER,
            text,
            FontId::new(10.5 * k, FontFamily::Name(CAPTION_FONT.into())),
            if active { Color32::from_rgb(20, 18, 15) } else { Color32::from_rgb(232, 226, 215) },
        );
        if resp.clicked() && !active {
            picked = Some(v);
        }
    }
    picked
}

/// The whole photo view. Returns a command when something was clicked; `view` may be switched by the tabs.
pub fn draw(ui: &mut egui::Ui, s: &LiveState, tex: &TextureHandle, view: &mut View) -> Option<Command> {
    let lay = layout();
    let avail = ui.available_rect_before_wrap();
    let k = (avail.width() / lay.w).min(avail.height() / lay.h).max(0.1);
    let size = Vec2::new(lay.w * k, lay.h * k);
    let o = avail.center() - size / 2.0;
    let m = Map { o, k };
    let (canvas, _) = ui.allocate_exact_size(avail.size(), Sense::hover());
    let painter = ui.painter_at(canvas);
    painter.image(tex.id(), Rect::from_min_size(o, size), Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)), Color32::WHITE);

    let fresh = s.is_fresh();
    let mut command = None;
    let now = now_unix();
    let pressed = s.button.as_ref().filter(|b| now - b.t < FLASH_S).map(|b| b.label.clone());

    // --- tabs ---
    let t = lay.tabs;
    if let Some(v) = tabs(ui, m.r(t[0], t[1], t[2], t[3]), k, *view) {
        *view = v;
    }

    // --- LCD ---
    let [x0, y0, x1, y1] = lay.lcd;
    let lcd = FontId::new(17.5 * k, FontFamily::Name(LCD_FONT.into()));
    let lh = 20.0;
    let line = |i: usize| y0 + 13.0 + i as f32 * lh;
    if !fresh {
        for (i, text) in ["ROUTER", "NIE ODPOWIADA", "", "SPRAWDŹ NADZORCĘ", "(WRACA SAM W ~3 S)"].iter().enumerate() {
            painter.text(m.p(x0 + 10.0, line(i + 1)), Align2::LEFT_CENTER, *text, lcd.clone(), INK);
        }
    } else {
        let moje = matches!(s.touch.as_deref(), Some("moje") | Some("moje3"));
        let pedal_name = match s.pedal_mode.as_deref() {
            Some("sostenuto") => "SOSTENUTO",
            Some("sustain") => "SUSTAIN",
            _ => "?",
        };
        let ones = if moje {
            "W KRZYWEJ"
        } else if s.ones.as_deref() == Some("ppp") {
            "PPP"
        } else {
            "KONTEKST"
        };
        let half = format!("{}  {:.0}%", on_off(s.half_pedal), s.half_depth as f32 / 127.0 * 100.0);
        let release = s.release_ms.map(|r| format!("{r} MS")).unwrap_or_else(|| "?".into());
        // (label, value, command on click, tooltip)
        let rows: Vec<(&str, String, Option<Command>, &str)> = vec![
            (
                "PEDAŁ",
                pedal_name.into(),
                Some(Command::PedalMode(if s.pedal_mode.as_deref() == Some("sostenuto") { "sustain" } else { "sostenuto" })),
                "Tryb pedału. Kliknij: sustain ↔ sostenuto. Paski = jak mocno pedał jest wciśnięty.",
            ),
            (
                "UNA CORDA",
                on_off(s.una_corda).into(),
                s.una_corda.map(|on| Command::UnaCorda(!on)),
                "Una corda (przycisk B48). Kliknij: włącz / wyłącz.",
            ),
            (
                "CZUCIE",
                touch_name(s.touch.as_deref()).into(),
                Some(Command::Touch(next_touch(s.touch.as_deref()))),
                "Krzywa dynamiki routera (przycisk C53). Kliknij: następna.",
            ),
            (
                "„1”",
                ones.into(),
                if moje { None } else { Some(Command::Ones(if s.ones.as_deref() == Some("ppp") { "context" } else { "ppp" })) },
                "Co router robi z najcichszym dotykiem („1”). W czuciu Moje decyduje sama krzywa.",
            ),
            (
                "PÓŁPEDAŁ",
                half,
                s.half_pedal.map(|on| Command::HalfPedal(!on)),
                "Półpedał: pedał wciska do głębokości z pokrętła B17. Kliknij: włącz / wyłącz.",
            ),
            (
                "PUSZCZANIE",
                release,
                s.release_ms.map(|r| Command::ReleaseMs(next_release(Some(r)))),
                "Jak miękko tłumiki opadają po puszczeniu pedału. Kliknij: 60 / 120 / 250 ms.",
            ),
        ];
        for (i, (label, value, cmd, tip)) in rows.into_iter().enumerate() {
            let y = line(i);
            let right = if i == 5 { x1 - 70.0 } else { x1 - 6.0 };
            let hit = m.r(x0 + 4.0, y - lh / 2.0, right, y + lh / 2.0);
            let resp = ui.interact(hit, ui.id().with(("lcd", i)), Sense::click()).on_hover_text(tip);
            if resp.hovered() && cmd.is_some() {
                painter.rect_filled(hit, CornerRadius::from(3.0 * k), INK_DIM);
            }
            if resp.clicked() {
                command = cmd;
            }
            painter.text(m.p(x0 + 10.0, y), Align2::LEFT_CENTER, label, lcd.clone(), INK);
            painter.text(m.p(x0 + 118.0, y), Align2::LEFT_CENTER, value, lcd.clone(), INK);
        }
        // pedal bar: 8 segments
        let lit = ((s.pedal_value as f32 / 127.0) * 8.0).ceil() as usize;
        for j in 0..8 {
            let xx = x0 + 214.0 + j as f32 * 9.0;
            let r = m.r(xx, y0 + 7.0, xx + 6.0, y0 + 19.0);
            painter.rect_filled(r, 0.0, if j < lit { INK } else { INK_DIM });
        }
        // debounce, right of PUSZCZANIE
        let y = line(5);
        let hit = m.r(x1 - 68.0, y - lh / 2.0, x1 - 4.0, y + lh / 2.0);
        let resp = ui
            .interact(hit, ui.id().with("lcd-debounce"), Sense::click())
            .on_hover_text(format!("Filtr odbić styków (usunięte od startu routera: {}). Kliknij: włącz / wyłącz.", s.bounces));
        if resp.hovered() {
            painter.rect_filled(hit, CornerRadius::from(3.0 * k), INK_DIM);
        }
        if resp.clicked() {
            if let Some(on) = s.debounce {
                command = Some(Command::Debounce(!on));
            }
        }
        painter.text(m.p(x1 - 10.0, y), Align2::RIGHT_CENTER, format!("ODB. {}", on_off(s.debounce)), lcd.clone(), INK);
        // status line
        painter.line_segment([m.p(x0 + 8.0, y1 - 24.0), m.p(x1 - 8.0, y1 - 24.0)], Stroke::new(k.max(1.0), INK_DIM));
        if let Some(last) = &s.last {
            let text = format!("{}  {} > {}", note_name(last.note), last.raw, last.out);
            painter.text(m.p(x0 + 10.0, y1 - 12.0), Align2::LEFT_CENTER, text, lcd.clone(), INK);
        }
        let status = match s.connected {
            Some(true) => "POŁĄCZONA",
            Some(false) => "BRAK KLAWIATURY",
            None => "?",
        };
        painter.text(m.p(x1 - 10.0, y1 - 12.0), Align2::RIGHT_CENTER, status, lcd.clone(), INK);
    }

    // --- knobs ---
    let r = lay.knob_r;
    for c in &lay.knobs {
        let color = lay.color(&c.group);
        let value = if c.id == "B17" {
            Some(s.half_knob.unwrap_or(s.half_depth))
        } else {
            s.controls.get(&c.id).copied()
        };
        pill(&painter, &m, c.x, c.y - 27.0, &c.short, color);
        let center = m.p(c.x, c.y);
        arc(&painter, center, r * k, 135.0, 405.0, Stroke::new(3.0 * k, Color32::from_black_alpha(110)));
        if let Some(v) = value {
            if v > 0 {
                arc(&painter, center, r * k, 135.0, 135.0 + 270.0 * v as f32 / 127.0, Stroke::new(3.0 * k, color));
            }
        }
        let shown = match value {
            Some(v) if c.id == "B17" => format!("{:.0}%", v as f32 / 127.0 * 100.0),
            Some(v) => v.to_string(),
            None => "–".into(),
        };
        let ink = if value.is_some() { AMBER } else { UNKNOWN };
        value_box(&painter, &m, c.x, c.y, if c.id == "B17" { 28.0 } else { 24.0 }, &shown, ink);
        let now_text = if value.is_some() { shown.clone() } else { "nieznane, rusz pokrętłem (albo SNAPSHOT: + i − naraz)".into() };
        ui.interact(m.rc(c.x, c.y - 6.0, 2.0 * r + 6.0, 2.0 * r + 24.0), ui.id().with(&c.id), Sense::hover())
            .on_hover_text(tooltip(&c.id, lay.group_name(&c.group), &c.long, &now_text));
    }

    // --- faders ---
    let (top, bottom) = (lay.fader_top, lay.fader_bottom);
    for c in &lay.faders {
        let color = lay.color(&c.group);
        pill(&painter, &m, c.x, top - 26.0, &c.short, color);
        let value = s.controls.get(&c.id).copied();
        let shown = match value {
            Some(127) => "0 dB".to_owned(),
            Some(v) => v.to_string(),
            None => "–".into(),
        };
        match value {
            Some(v) => {
                let y = bottom - v as f32 / 127.0 * (bottom - top);
                painter.rect_filled(m.rc(c.x, y, 30.0, 8.0), CornerRadius::from(2.0 * k), AMBER.gamma_multiply(0.85));
                value_box(&painter, &m, c.x, y + 13.0, 30.0, &shown, AMBER);
            }
            None => value_box(&painter, &m, c.x, bottom - 30.0, 30.0, &shown, UNKNOWN),
        }
        let now_text = if value.is_some() { shown.clone() } else { "nieznane, rusz suwakiem".into() };
        ui.interact(m.r(c.x - 18.0, top - 34.0, c.x + 18.0, bottom + 24.0), ui.id().with(&c.id), Sense::hover())
            .on_hover_text(tooltip(&c.id, lay.group_name(&c.group), &c.long, &now_text));
    }

    // --- buttons ---
    let [bw, bh] = lay.button;
    for c in &lay.buttons {
        let color = lay.color(&c.group);
        pill(&painter, &m, c.x, c.y - 25.0, &c.short, color);
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
        let active = active && fresh;
        if active {
            painter.rect_stroke(m.rc(c.x, c.y, bw + 4.0, bh + 4.0), CornerRadius::from(4.0 * k), Stroke::new(2.0 * k, AMBER), StrokeKind::Inside);
        }
        if pressed.as_deref() == Some(c.id.as_str()) {
            painter.rect_stroke(m.rc(c.x, c.y, bw + 8.0, bh + 8.0), CornerRadius::from(5.0 * k), Stroke::new(2.0 * k, Color32::WHITE), StrokeKind::Inside);
        }
        if let Some(st) = &state {
            if fresh {
                value_box(&painter, &m, c.x, c.y, bw - 2.0, st, AMBER);
            }
        }
        let clickable = fresh && cmd.is_some();
        let sense = if clickable { Sense::click() } else { Sense::hover() };
        let now_text = state.clone().unwrap_or_else(|| "przycisk chwilowy (błyska przy naciśnięciu)".into());
        let mut tip = tooltip(&c.id, lay.group_name(&c.group), &c.long, &now_text);
        if clickable {
            tip.push_str("\nKliknij tutaj: to samo co przycisk.");
        }
        let resp = ui.interact(m.rc(c.x, c.y - 8.0, bw + 18.0, bh + 26.0), ui.id().with(&c.id), sense).on_hover_text(tip);
        if clickable && resp.hovered() {
            painter.rect_stroke(m.rc(c.x, c.y, bw + 2.0, bh + 2.0), CornerRadius::from(4.0 * k), Stroke::new(k.max(1.0), Color32::from_white_alpha(140)), StrokeKind::Inside);
        }
        if clickable && resp.clicked() {
            command = cmd;
        }
    }
    command
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout_has_every_control_once() {
        let l = layout();
        assert_eq!((l.knobs.len(), l.faders.len(), l.buttons.len()), (24, 9, 17));
        let mut ids: Vec<&str> = l.knobs.iter().chain(&l.faders).chain(&l.buttons).map(|c| c.id.as_str()).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), 50);
        for c in l.knobs.iter().chain(&l.faders).chain(&l.buttons) {
            assert!(c.x > 0.0 && c.x < l.w && c.y > 0.0 && c.y < l.h, "{}", c.id);
            assert!(!c.short.is_empty() && !c.long.is_empty(), "{}", c.id);
            assert!(l.groups.iter().any(|g| g.0 == c.group), "{} group {}", c.id, c.group);
        }
        assert!(l.lcd[0] < l.lcd[2] && l.fader_top < l.fader_bottom);
    }

    #[test]
    fn photo_decodes_to_layout_size() {
        let mut d = jpeg_decoder::Decoder::new(PHOTO);
        let px = d.decode().unwrap();
        let info = d.info().unwrap();
        assert_eq!((info.width as f32, info.height as f32), (layout().w, layout().h));
        assert_eq!(px.len(), info.width as usize * info.height as usize * 3);
    }

    #[test]
    fn cycles_and_names() {
        assert_eq!(next_touch(Some("moje")), "moje3");
        assert_eq!(next_touch(Some("moje3")), "light");
        assert_eq!(next_touch(None), "light");
        assert_eq!(next_release(Some(120)), 250);
        assert_eq!(next_release(Some(250)), 60);
        assert_eq!(next_release(Some(77)), 120);
        assert_eq!(note_name(60), "C4");
        assert_eq!(note_name(70), "A#4");
        assert_eq!(note_name(21), "A0");
    }
}
