//! Drawing. One row per piece of state (label on the left, choices on the
//! right). Clicking a choice returns a Command; lib.rs sends it to the router.
//! New information = new row here (and a field in live.rs).

use crate::cmd::Command;
use crate::live::LiveState;
use nih_plug_egui::egui::{self, Color32, RichText};

const MUTED: Color32 = Color32::from_rgb(150, 145, 136);
const HOT: Color32 = Color32::from_rgb(208, 83, 47);
const LED_ON: Color32 = Color32::from_rgb(217, 130, 43);
const LED_OFF: Color32 = Color32::from_rgb(60, 58, 54);
const LABEL_W: f32 = 92.0;

fn row(ui: &mut egui::Ui, label: &str, add: impl FnOnce(&mut egui::Ui)) {
    ui.horizontal(|ui| {
        ui.allocate_ui_with_layout(
            egui::vec2(LABEL_W, 26.0),
            egui::Layout::left_to_right(egui::Align::Center),
            |ui| {
                ui.label(RichText::new(label).size(11.0).color(MUTED));
            },
        );
        add(ui);
    });
}

/// A group of mutually exclusive choices; returns the one clicked (if any).
fn choices<'a>(
    ui: &mut egui::Ui,
    current: Option<&str>,
    options: &[(&'a str, &str)],
    enabled: bool,
) -> Option<&'a str> {
    let mut clicked = None;
    for (value, text) in options {
        let selected = current == Some(*value);
        let label = RichText::new(*text).size(14.0);
        let label = if selected { label.strong() } else { label };
        let resp = ui.add_enabled(enabled, egui::SelectableLabel::new(selected, label));
        if resp.clicked() && !selected {
            clicked = Some(*value);
        }
    }
    clicked
}

fn led(ui: &mut egui::Ui, on: bool) {
    let (rect, _) = ui.allocate_exact_size(egui::vec2(12.0, 12.0), egui::Sense::hover());
    ui.painter().circle_filled(rect.center(), 5.5, if on { LED_ON } else { LED_OFF });
}

pub fn draw(ui: &mut egui::Ui, s: &LiveState) -> Option<Command> {
    let fresh = s.is_fresh();
    let mut command = None;
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 6.0);
    ui.spacing_mut().button_padding = egui::vec2(8.0, 3.0);

    row(ui, "PEDAŁ", |ui| {
        let opts = [("sustain", "Sustain"), ("sostenuto", "Sostenuto")];
        if let Some(v) = choices(ui, s.pedal_mode.as_deref(), &opts, fresh) {
            command = Some(Command::PedalMode(v));
        }
        led(ui, fresh && s.pedal_value > 0);
    });

    row(ui, "UNA CORDA", |ui| {
        let current = s.una_corda.map(|on| if on { "on" } else { "off" });
        let opts = [("off", "wył"), ("on", "WŁ")];
        if let Some(v) = choices(ui, current, &opts, fresh) {
            command = Some(Command::UnaCorda(v == "on"));
        }
        if s.una_corda == Some(true) && fresh {
            ui.label(RichText::new("●").color(HOT));
        }
    });

    row(ui, "CZUCIE", |ui| {
        let opts = [("light", "Light"), ("acoustic", "Acoustic"), ("heavy", "Heavy")];
        if let Some(v) = choices(ui, s.touch.as_deref(), &opts, fresh) {
            command = Some(Command::Touch(v));
        }
    });

    row(ui, "„1”", |ui| {
        let opts = [("context", "kontekstowe"), ("ppp", "ppp")];
        if let Some(v) = choices(ui, s.ones.as_deref(), &opts, fresh) {
            command = Some(Command::Ones(v));
        }
    });

    row(ui, "KLAWIATURA", |ui| {
        let (text, color) = if !fresh {
            ("router nie odpowiada", HOT)
        } else {
            match s.connected {
                Some(true) => ("połączona", ui.visuals().text_color()),
                Some(false) => ("brak", HOT),
                None => ("?", MUTED),
            }
        };
        ui.label(RichText::new(text).size(14.0).color(color));
    });

    if fresh && s.source == "status.json" {
        ui.label(
            RichText::new("stary router: odświeżanie co 1 s, bez przełączania")
                .size(11.0)
                .color(MUTED),
        );
    }
    command
}
