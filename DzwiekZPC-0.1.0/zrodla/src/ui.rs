//! The window: source, volume, cushion, and a status line that says at once whether it is clean.

use crate::shared::{Shared, State};
use crate::ZPcParams;
use nih_plug::prelude::*;
use nih_plug_egui::egui::{self, Color32, RichText};
use nih_plug_egui::widgets::ParamSlider;
use std::sync::atomic::Ordering;
use std::sync::Arc;

const MUTED: Color32 = Color32::from_rgb(150, 145, 136);
const HOT: Color32 = Color32::from_rgb(208, 83, 47);
const OK: Color32 = Color32::from_rgb(120, 190, 120);

pub fn draw(ctx: &egui::Context, setter: &ParamSetter, params: &Arc<ZPcParams>, shared: &Arc<Shared>) {
    egui::CentralPanel::default().show(ctx, |ui| {
        ui.spacing_mut().item_spacing = egui::vec2(8.0, 8.0);
        ui.label(RichText::new("DŹWIĘK Z PC").size(13.0).color(MUTED));

        // source
        let devices = shared.devices.lock().unwrap().clone();
        let current = shared.wanted.lock().unwrap().clone();
        let current_label = devices
            .iter()
            .find(|d| d.key() == current)
            .map(|d| d.label())
            .unwrap_or_else(|| {
                if current.is_empty() { "samo: pierwsze CABLE Output".to_owned() } else { format!("brak: {}", current) }
            });
        ui.horizontal(|ui| {
            ui.label("Źródło");
            egui::ComboBox::from_id_salt("source")
                .width(320.0)
                .selected_text(current_label)
                .show_ui(ui, |ui| {
                    if ui.selectable_label(current.is_empty(), "samo: pierwsze CABLE Output").clicked() {
                        choose(params, shared, "");
                    }
                    for d in &devices {
                        if ui.selectable_label(d.key() == current, d.label()).clicked() {
                            choose(params, shared, &d.key());
                        }
                    }
                });
        });

        ui.horizontal(|ui| {
            ui.label("Głośność");
            ui.add(ParamSlider::for_param(&params.gain, setter).with_width(260.0));
        });
        ui.horizontal(|ui| {
            ui.label("Zapas");
            ui.add(ParamSlider::for_param(&params.cushion_ms, setter).with_width(260.0));
        });

        // status
        let state = shared.state();
        let text = shared.state_text.lock().unwrap().clone();
        let rate = shared.host_rate.load(Ordering::Relaxed).max(1);
        let fill_ms = shared.fill_frames.load(Ordering::Relaxed) as f64 * 1000.0 / rate as f64;
        let gaps = shared.gaps.load(Ordering::Relaxed);
        let dropped = shared.dropped.load(Ordering::Relaxed);
        let ppm = shared.correction_ppm.load(Ordering::Relaxed);
        let peak = f32::from_bits(shared.peak_bits.load(Ordering::Relaxed));
        let (head, color) = match state {
            State::Running if gaps == 0 => (format!("Gra: {text}"), OK),
            State::Running => (format!("Gra: {text}"), HOT),
            State::NoSource => ("Nie ma źródła. Zainstaluj VB-Cable albo wybierz wyjście z listy.".to_owned(), HOT),
            State::Error => (format!("Błąd: {text}"), HOT),
            State::Stopped => ("Zatrzymane (Studio One nie gra)".to_owned(), MUTED),
        };
        ui.label(RichText::new(head).color(color));
        ui.label(
            RichText::new(format!(
                "zapas teraz {fill_ms:.0} ms, korekta zegara {:+.3}%, przerwy {gaps}, odrzucone {dropped}",
                ppm as f64 / 10_000.0
            ))
            .size(12.0)
            .color(MUTED),
        );
        let (bar, _) = ui.allocate_exact_size(egui::vec2(320.0, 6.0), egui::Sense::hover());
        ui.painter().rect_filled(bar, 2.0, Color32::from_rgb(44, 42, 39));
        let w = (peak.clamp(0.0, 1.0)).sqrt() * bar.width();
        ui.painter().rect_filled(egui::Rect::from_min_size(bar.min, egui::vec2(w, bar.height())), 2.0, OK);
        if ui.small_button("Zeruj liczniki").clicked() {
            shared.gaps.store(0, Ordering::Relaxed);
            shared.dropped.store(0, Ordering::Relaxed);
        }
        ui.label(
            RichText::new(
                "W ASIO4ALL zostaw włączone tylko UM2. Firefox ustaw na VB-Cable \
                 (Ustawienia, Dźwięk, Mikser głośności). Przerwy rosną? Zwiększ Zapas.",
            )
            .size(11.0)
            .color(MUTED),
        );
    });
}

fn choose(params: &ZPcParams, shared: &Shared, key: &str) {
    if let Ok(mut s) = params.source.write() {
        *s = key.to_owned();
    }
    shared.choose(key);
}
