//! Drawing. One row per piece of state (label on the left, choices on the
//! right). Clicking a choice returns a Command; lib.rs sends it to the router.
//! New information = new row here (and a field in live.rs).
//!
//! Everything is drawn at a scale that fits the window (0.2.1): the layout is
//! designed for BASE_W x BASE_H and grows or shrinks with the window, so no row
//! can end up below the edge. If the window is smaller than MIN_SCALE allows,
//! the rows scroll instead.

use crate::cmd::Command;
use crate::live::LiveState;
use nih_plug_egui::egui::{self, Color32, RichText};

const MUTED: Color32 = Color32::from_rgb(150, 145, 136);
const HOT: Color32 = Color32::from_rgb(208, 83, 47);
const LED_ON: Color32 = Color32::from_rgb(217, 130, 43);
const LED_OFF: Color32 = Color32::from_rgb(60, 58, 54);

/// Size (in points) the layout is designed for at scale 1.0.
pub const BASE_W: f32 = 370.0;
pub const BASE_H: f32 = 284.0;
const MIN_SCALE: f32 = 0.75;
const MAX_SCALE: f32 = 4.0;

const LABEL_W: f32 = 92.0;
const ROW_H: f32 = 26.0;

/// Scale factor that makes the BASE layout fit into `avail`.
pub fn fit_scale(avail: egui::Vec2) -> f32 {
    (avail.x / BASE_W).min(avail.y / BASE_H).clamp(MIN_SCALE, MAX_SCALE)
}

fn row(ui: &mut egui::Ui, k: f32, label: &str, add: impl FnOnce(&mut egui::Ui)) {
    ui.horizontal(|ui| {
        ui.allocate_ui_with_layout(
            egui::vec2(LABEL_W * k, ROW_H * k),
            egui::Layout::left_to_right(egui::Align::Center),
            |ui| {
                ui.label(RichText::new(label).size(11.0 * k).color(MUTED));
            },
        );
        add(ui);
    });
}

/// A group of mutually exclusive choices; returns the one clicked (if any).
fn choices<'a>(
    ui: &mut egui::Ui,
    k: f32,
    current: Option<&str>,
    options: &[(&'a str, &str)],
    enabled: bool,
) -> Option<&'a str> {
    let mut clicked = None;
    for (value, text) in options {
        let selected = current == Some(*value);
        let label = RichText::new(*text).size(14.0 * k);
        let label = if selected { label.strong() } else { label };
        let resp = ui.add_enabled(enabled, egui::SelectableLabel::new(selected, label));
        if resp.clicked() && !selected {
            clicked = Some(*value);
        }
    }
    clicked
}

fn led(ui: &mut egui::Ui, k: f32, on: bool) {
    let (rect, _) = ui.allocate_exact_size(egui::vec2(12.0 * k, 12.0 * k), egui::Sense::hover());
    ui.painter().circle_filled(rect.center(), 5.5 * k, if on { LED_ON } else { LED_OFF });
}

/// Rotary knob 1..127: drag up/down (or scroll) to change it. Shows the router's value,
/// so turning the physical B17 moves it too. Returns the new value while it is dragged.
fn knob(ui: &mut egui::Ui, k: f32, value: u8, enabled: bool, active: bool) -> Option<u8> {
    let size = 24.0 * k;
    let sense = if enabled { egui::Sense::click_and_drag() } else { egui::Sense::hover() };
    let (rect, resp) = ui.allocate_exact_size(egui::vec2(size, size), sense);
    let mut v = value as f32;
    if resp.dragged() {
        v -= resp.drag_delta().y * 0.6;
    }
    if resp.hovered() && enabled {
        let scroll = ui.input(|i| i.smooth_scroll_delta.y);
        if scroll != 0.0 {
            v += scroll.signum() * (scroll.abs() * 0.15).max(1.0);
        }
    }
    let new = v.round().clamp(1.0, 127.0) as u8;
    let painter = ui.painter();
    let c = rect.center();
    let r = size * 0.45;
    painter.circle_filled(c, r, Color32::from_rgb(44, 42, 39));
    painter.circle_stroke(c, r, egui::Stroke::new(1.5 * k, if active { LED_ON } else { LED_OFF }));
    // 7 o'clock (0) to 5 o'clock (127), like the knob on the keyboard
    let t = (new as f32 - 1.0) / 126.0;
    let angle = (135.0 + t * 270.0_f32).to_radians();
    let tip = c + egui::vec2(angle.cos(), angle.sin()) * (r * 0.85);
    painter.line_segment([c, tip], egui::Stroke::new(2.0 * k, if active { LED_ON } else { MUTED }));
    if new != value { Some(new) } else { None }
}

pub fn draw(ui: &mut egui::Ui, s: &LiveState, k: f32) -> Option<Command> {
    let fresh = s.is_fresh();
    let mut command = None;
    ui.spacing_mut().item_spacing = egui::vec2(6.0 * k, 6.0 * k);
    ui.spacing_mut().button_padding = egui::vec2(8.0 * k, 3.0 * k);

    row(ui, k, "PEDAŁ", |ui| {
        let opts = [("sustain", "Sustain"), ("sostenuto", "Sostenuto")];
        if let Some(v) = choices(ui, k, s.pedal_mode.as_deref(), &opts, fresh) {
            command = Some(Command::PedalMode(v));
        }
        led(ui, k, fresh && s.pedal_value > 0);
    });

    row(ui, k, "UNA CORDA", |ui| {
        let current = s.una_corda.map(|on| if on { "on" } else { "off" });
        let opts = [("off", "wył"), ("on", "WŁ")];
        if let Some(v) = choices(ui, k, current, &opts, fresh) {
            command = Some(Command::UnaCorda(v == "on"));
        }
        if s.una_corda == Some(true) && fresh {
            ui.label(RichText::new("●").size(14.0 * k).color(HOT));
        }
    });

    row(ui, k, "CZUCIE", |ui| {
        let opts = [("light", "Light"), ("acoustic", "Acoustic"), ("heavy", "Heavy")];
        if let Some(v) = choices(ui, k, s.touch.as_deref(), &opts, fresh) {
            command = Some(Command::Touch(v));
        }
    });

    row(ui, k, "„1”", |ui| {
        let opts = [("context", "kontekstowe"), ("ppp", "ppp")];
        if let Some(v) = choices(ui, k, s.ones.as_deref(), &opts, fresh) {
            command = Some(Command::Ones(v));
        }
    });

    row(ui, k, "PÓŁPEDAŁ", |ui| {
        let current = s.half_pedal.map(|on| if on { "on" } else { "off" });
        let opts = [("off", "wył"), ("on", "WŁ")];
        if let Some(v) = choices(ui, k, current, &opts, fresh) {
            command = Some(Command::HalfPedal(v == "on"));
        }
        if let Some(d) = knob(ui, k, s.half_depth, fresh, s.half_pedal == Some(true)) {
            command = Some(Command::HalfDepth(d));
        }
        let pct = (s.half_depth as f32 / 127.0 * 100.0).round();
        ui.label(RichText::new(format!("{pct:.0}%")).size(14.0 * k));
    });
    ui.label(
        RichText::new("głębokość: gałka B17 na klawiaturze albo przeciągnij w górę/dół")
            .size(10.0 * k)
            .color(MUTED),
    );

    row(ui, k, "ODBICIA", |ui| {
        let current = s.debounce.map(|on| if on { "on" } else { "off" });
        let opts = [("off", "wył"), ("on", "WŁ")];
        if let Some(v) = choices(ui, k, current, &opts, fresh) {
            command = Some(Command::Debounce(v == "on"));
        }
        if s.debounce == Some(true) {
            ui.label(
                RichText::new(format!("usunięte: {}", s.bounces)).size(12.0 * k).color(MUTED),
            );
        }
    });

    row(ui, k, "KLAWIATURA", |ui| {
        let (text, color) = if !fresh {
            ("router nie odpowiada", HOT)
        } else {
            match s.connected {
                Some(true) => ("połączona", ui.visuals().text_color()),
                Some(false) => ("brak", HOT),
                None => ("?", MUTED),
            }
        };
        ui.label(RichText::new(text).size(14.0 * k).color(color));
    });

    if fresh && s.source == "status.json" {
        ui.label(
            RichText::new("stary router: odświeżanie co 1 s, bez przełączania")
                .size(11.0 * k)
                .color(MUTED),
        );
    }
    command
}
