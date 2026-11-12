//! Drawing. Each piece of state is one "chip"; new information = new chip
//! (or a new section below the row) without touching the reader.

use crate::live::LiveState;
use nih_plug_egui::egui::{self, Color32, RichText, Stroke};

const MUTED: Color32 = Color32::from_rgb(150, 145, 136);
const HOT: Color32 = Color32::from_rgb(208, 83, 47);
const LED_ON: Color32 = Color32::from_rgb(217, 130, 43);
const LED_OFF: Color32 = Color32::from_rgb(60, 58, 54);
const PANEL: Color32 = Color32::from_rgb(29, 28, 25);
const LINE: Color32 = Color32::from_rgb(55, 52, 47);

fn chip(ui: &mut egui::Ui, key: &str, value: &str, hot: bool, led: Option<bool>, dim: bool) {
    let stroke = if hot { Stroke::new(1.5_f32, HOT) } else { Stroke::new(1.0_f32, LINE) };
    let frame = egui::Frame::new()
        .fill(PANEL)
        .stroke(stroke)
        .corner_radius(14)
        .inner_margin(egui::Margin::symmetric(12, 6));
    frame.show(ui, |ui| {
        ui.set_opacity(if dim { 0.4 } else { 1.0 });
        ui.horizontal(|ui| {
            ui.label(RichText::new(key).size(11.0).color(MUTED));
            ui.label(RichText::new(value).size(15.0).strong());
            if let Some(on) = led {
                let (rect, _) = ui.allocate_exact_size(egui::vec2(11.0, 11.0), egui::Sense::hover());
                ui.painter().circle_filled(rect.center(), 5.5, if on { LED_ON } else { LED_OFF });
            }
        });
    });
}

fn label_touch(t: &str) -> &str {
    match t {
        "light" => "Light",
        "acoustic" => "Acoustic",
        "heavy" => "Heavy",
        other => other,
    }
}

pub fn draw(ui: &mut egui::Ui, s: &LiveState) {
    let fresh = s.is_fresh();
    let dim = !fresh;
    ui.horizontal_wrapped(|ui| {
        ui.spacing_mut().item_spacing = egui::vec2(8.0, 8.0);

        let mode = match s.pedal_mode.as_deref() {
            Some("sustain") => "Sustain",
            Some("sostenuto") => "Sostenuto",
            Some(other) => other,
            None => "?",
        };
        chip(ui, "PEDAŁ", mode, mode == "Sostenuto", Some(s.pedal_value > 0), dim);

        let una = match s.una_corda {
            Some(true) => "WŁ",
            Some(false) => "wył",
            None => "?",
        };
        chip(ui, "UNA CORDA", una, s.una_corda == Some(true), None, dim);

        let touch = s.touch.as_deref().map(label_touch).unwrap_or("?");
        chip(ui, "CZUCIE", touch, false, None, dim);

        let ones = match s.ones.as_deref() {
            Some("context") => "kontekstowe",
            Some("ppp") => "ppp",
            Some(other) => other,
            None => "?",
        };
        chip(ui, "„1”", ones, false, None, dim);

        let kbd = if !fresh {
            "router nie odpowiada"
        } else {
            match s.connected {
                Some(true) => "połączona",
                Some(false) => "brak",
                None => "?",
            }
        };
        chip(ui, "KLAWIATURA", kbd, !fresh || s.connected == Some(false), None, false);
    });
    if fresh && s.source == "status.json" {
        ui.add_space(4.0);
        ui.label(
            RichText::new("stary router: odświeżanie co 1 s (zaktualizuj router dla trybu na żywo)")
                .size(11.0)
                .color(MUTED),
        );
    }
}
