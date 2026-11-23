//! Okno wtyczki: wybór głośników, poziom, zapas, „Też do Main”, test i stan po polsku.

use crate::shared::{Shared, State};
use crate::SendParams;
use nih_plug::prelude::*;
use nih_plug_egui::egui::{self, Color32, RichText};
use nih_plug_egui::widgets::ParamSlider;
use std::sync::atomic::Ordering;
use std::sync::Arc;

const BG: Color32 = Color32::from_rgb(20, 19, 17);
const MUTED: Color32 = Color32::from_rgb(150, 145, 136);
const TEXT: Color32 = Color32::from_rgb(226, 220, 208);
const HOT: Color32 = Color32::from_rgb(214, 96, 58);
const OK: Color32 = Color32::from_rgb(126, 196, 126);

pub fn style(ctx: &egui::Context) {
    let mut v = egui::Visuals::dark();
    v.panel_fill = BG;
    v.override_text_color = Some(TEXT);
    ctx.set_visuals(v);
}

pub fn draw(ctx: &egui::Context, setter: &ParamSetter, params: &Arc<SendParams>, shared: &Arc<Shared>) {
    egui::CentralPanel::default().show(ctx, |ui| {
        ui.spacing_mut().item_spacing = egui::vec2(8.0, 7.0);
        ui.label(RichText::new("DŹWIĘK DO GŁOŚNIKÓW 0.2.1").size(13.0).color(MUTED));

        let devices = shared.devices.lock().map(|d| d.clone()).unwrap_or_default();
        let current = shared.wanted.lock().map(|w| w.clone()).unwrap_or_default();
        let auto_name = crate::shared::default_device(&devices).map(|d| d.name).unwrap_or_else(|| "brak".into());
        let current_label = if current.is_empty() {
            format!("samo: {auto_name}")
        } else {
            devices.iter().find(|d| d.key() == current).map(|d| d.name.clone()).unwrap_or_else(|| format!("nie ma teraz: {}", current.trim_start_matches("out|")))
        };
        ui.horizontal(|ui| {
            ui.label("Głośniki");
            egui::ComboBox::from_id_salt("device").width(330.0).selected_text(current_label).show_ui(ui, |ui| {
                if ui.selectable_label(current.is_empty(), format!("samo: {auto_name}")).clicked() {
                    choose(params, shared, "");
                }
                for d in &devices {
                    let label = if d.is_asio_interface() {
                        format!("{} (UM2, zajęty przez ASIO)", d.name)
                    } else if d.is_not_speakers() {
                        format!("{} (cyfrowe/wirtualne)", d.name)
                    } else {
                        d.name.clone()
                    };
                    if ui.selectable_label(d.key() == current, label).clicked() {
                        choose(params, shared, &d.key());
                    }
                }
            });
            if ui.small_button("Odśwież").clicked() {
                shared.refresh.store(true, Ordering::SeqCst);
            }
        });
        ui.horizontal(|ui| {
            ui.label("Poziom  ");
            ui.add(ParamSlider::for_param(&params.gain, setter).with_width(300.0));
        });
        ui.horizontal(|ui| {
            ui.label("Zapas    ");
            ui.add(ParamSlider::for_param(&params.cushion_ms, setter).with_width(300.0));
        });
        ui.horizontal(|ui| {
            let mut main = params.also_main.value();
            if ui.checkbox(&mut main, "Też do Main (słyszysz to także w słuchawkach i na UM2)").changed() {
                setter.begin_set_parameter(&params.also_main);
                setter.set_parameter(&params.also_main, main);
                setter.end_set_parameter(&params.also_main);
            }
        });

        ui.separator();
        let state = shared.state();
        let text = shared.state_text.lock().map(|t| t.clone()).unwrap_or_default();
        let gaps = shared.gaps.load(Ordering::Relaxed);
        let skips = shared.skips.load(Ordering::Relaxed);
        let dropped = shared.dropped.load(Ordering::Relaxed);
        let idle = shared.idle.load(Ordering::Relaxed);
        let (head, color) = match state {
            State::Running if idle => (format!("Gotowe: {text}. Studio One nic nie wysyła."), MUTED),
            State::Running if gaps == 0 => (format!("Gra do: {text}"), OK),
            State::Running => (format!("Gra do: {text} (były przerwy)"), HOT),
            State::NoDevice => (text.clone(), HOT),
            State::Error => (format!("Błąd: {text}"), HOT),
            State::Stopped => ("Zatrzymane: Studio One wyłączyło wtyczkę.".to_owned(), MUTED),
        };
        ui.label(RichText::new(head).color(color));

        if state == State::Running {
            let rate = shared.dev_rate.load(Ordering::Relaxed);
            let period = shared.period_frames.load(Ordering::Relaxed);
            let low = shared.low_latency.load(Ordering::Relaxed);
            let mmcss = shared.mmcss.load(Ordering::Relaxed);
            let ms = |us: u32| us as f64 / 1000.0;
            let plugin = ms(shared.plugin_latency_us.load(Ordering::Relaxed));
            let device = ms(shared.device_latency_us.load(Ordering::Relaxed));
            let cushion = ms(shared.cushion_now_us.load(Ordering::Relaxed));
            let ppm = shared.correction_ppm.load(Ordering::Relaxed);
            ui.label(RichText::new(format!(
                "Karta: {:.1} kHz, {}, okres {:.1} ms{}",
                rate as f64 / 1000.0,
                shared.dev_channels.load(Ordering::Relaxed),
                period as f64 * 1000.0 / rate.max(1) as f64,
                if low { " (tryb niskiego opóźnienia)" } else { " (zwykły tryb Windows)" }
            )).size(12.0).color(MUTED));
            ui.label(RichText::new(format!(
                "Opóźnienie tej drogi: ok. {:.0} ms (zapas {:.0} ms + przeliczanie {:.0} ms + Windows {:.0} ms)",
                plugin + device,
                cushion,
                (plugin - cushion).max(0.0),
                device
            )).size(12.0));
            ui.label(RichText::new(format!(
                "Korekta zegara {:+} ppm · przerwy {gaps} · przeskoki {skips} · odrzucone {dropped}{}",
                ppm,
                if mmcss { "" } else { " · BEZ priorytetu audio" }
            )).size(12.0).color(MUTED));
        }

        let peak = f32::from_bits(shared.peak_bits.load(Ordering::Relaxed));
        let (bar, _) = ui.allocate_exact_size(egui::vec2(470.0, 6.0), egui::Sense::hover());
        ui.painter().rect_filled(bar, 2.0, Color32::from_rgb(44, 42, 39));
        let w = (peak.clamp(1e-6, 1.0).log10() * 20.0 + 60.0).clamp(0.0, 60.0) / 60.0;
        ui.painter().rect_filled(egui::Rect::from_min_size(bar.min, egui::vec2(w * bar.width(), bar.height())), 2.0, if peak >= 1.0 { HOT } else { OK });

        ui.horizontal(|ui| {
            if ui.button("Test: dźwięk na głośnikach").clicked() {
                shared.tone.store(true, Ordering::SeqCst);
            }
            if ui.small_button("Zeruj liczniki").clicked() {
                shared.reset_counters();
            }
        });
        ui.label(RichText::new(
            "Wstaw jako ostatni insert na kanale FX, do którego wysyłasz to, co ma grać z drugich głośników. \
             Przerwy > 0: zapas „auto” sam urośnie; przy ręcznym zapasie dodaj 2–4 ms. \
             Opóźnienie tej drogi możesz odjąć od predelay pogłosu, wtedy sala na głośnikach przychodzi na czas."
        ).size(11.0).color(MUTED));
    });
}

fn choose(params: &SendParams, shared: &Shared, key: &str) {
    if let Ok(mut s) = params.device.write() {
        *s = key.to_owned();
    }
    shared.choose(key);
}
