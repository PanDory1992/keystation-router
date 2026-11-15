//! Keystation Status: shows the live state of the Keystation Pro 88 MIDI router
//! (pedal mode, una corda, touch mode, "1" mode, keyboard connection) inside the DAW.
//!
//! Audio passes through untouched, so it can sit on any track.
//! Layout of the code, so it can grow:
//!   live.rs - reading/parsing the router's live.json (add fields here)
//!   cmd.rs  - commands back to the router (live-cmd.json)
//!   ui.rs   - drawing, one row per setting (add rows here)
//!   photo.rs - 0.7.0: the default view, a photo of the keyboard with the live
//!              state on its LCD and on every knob, fader and button
//!              (positions and captions: assets/layout.json)

use nih_plug::prelude::*;
use nih_plug_egui::resizable_window::ResizableWindow;
use nih_plug_egui::{create_egui_editor, egui, EguiState};
use std::sync::Arc;
use std::time::Duration;

mod cmd;
mod live;
mod photo;
mod ui;

/// Everything the editor keeps between frames.
struct EditorState {
    reader: live::LiveReader,
    view: photo::View,
    photo: Option<egui::TextureHandle>,
}

/// The photo is 998 x 567 px; open at 110 %.
const DEFAULT_W: u32 = 1098;
const DEFAULT_H: u32 = 624;

fn install_fonts(ctx: &egui::Context) {
    let mut fonts = egui::FontDefinitions::default();
    fonts.font_data.insert(
        photo::LCD_FONT.into(),
        Arc::new(egui::FontData::from_static(include_bytes!("../assets/VT323-Regular.ttf"))),
    );
    fonts.font_data.insert(
        photo::CAPTION_FONT.into(),
        Arc::new(egui::FontData::from_static(include_bytes!("../assets/BarlowSemiCondensed-SemiBold.ttf"))),
    );
    fonts.families.insert(egui::FontFamily::Name(photo::LCD_FONT.into()), vec![photo::LCD_FONT.into()]);
    fonts.families.insert(egui::FontFamily::Name(photo::CAPTION_FONT.into()), vec![photo::CAPTION_FONT.into()]);
    ctx.set_fonts(fonts);
}

struct KeystationStatus {
    params: Arc<StatusParams>,
}

#[derive(Params)]
struct StatusParams {
    /// Window size, remembered with the project (0.7.0: new key, so projects saved with
    /// the small 0.6 window open at the photo's size).
    #[persist = "editor-state-photo"]
    editor_state: Arc<EguiState>,
}

impl Default for KeystationStatus {
    fn default() -> Self {
        Self {
            params: Arc::new(StatusParams { editor_state: EguiState::from_size(DEFAULT_W, DEFAULT_H) }),
        }
    }
}

impl Plugin for KeystationStatus {
    const NAME: &'static str = "Keystation Status";
    const VENDOR: &'static str = "Miki";
    const URL: &'static str = "";
    const EMAIL: &'static str = "";
    const VERSION: &'static str = env!("CARGO_PKG_VERSION");

    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[
        AudioIOLayout {
            main_input_channels: NonZeroU32::new(2),
            main_output_channels: NonZeroU32::new(2),
            ..AudioIOLayout::const_default()
        },
        AudioIOLayout {
            main_input_channels: NonZeroU32::new(1),
            main_output_channels: NonZeroU32::new(1),
            ..AudioIOLayout::const_default()
        },
    ];
    const MIDI_INPUT: MidiConfig = MidiConfig::None;
    const MIDI_OUTPUT: MidiConfig = MidiConfig::None;

    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn editor(&mut self, _async_executor: AsyncExecutor<Self>) -> Option<Box<dyn Editor>> {
        let egui_state = self.params.editor_state.clone();
        create_egui_editor(
            self.params.editor_state.clone(),
            EditorState { reader: live::LiveReader::default(), view: photo::View::Photo, photo: None },
            |ctx, state| {
                let mut visuals = egui::Visuals::dark();
                visuals.panel_fill = egui::Color32::from_rgb(20, 19, 17);
                visuals.resize_corner_size = 14.0;
                ctx.set_visuals(visuals);
                install_fonts(ctx);
                state.photo = photo::texture(ctx);
            },
            move |ctx, _setter, state| {
                state.reader.poll();
                // Studio One cannot resize nih-plug windows from its side, so the
                // plugin draws its own corner handle (bottom right). Both views
                // scale to the window; the settings rows scroll if it gets very small.
                let min = egui::vec2(800.0, 455.0);
                let EditorState { reader, view, photo: tex } = state;
                let clicked = ResizableWindow::new("keystation-status")
                    .min_size(min)
                    .show(ctx, &egui_state, |ui| match (*view, tex.as_ref()) {
                        (photo::View::Photo, Some(tex)) => photo::draw(ui, &reader.state, tex, view),
                        _ => egui::Frame::new()
                            .inner_margin(egui::Margin::same(8))
                            .show(ui, |ui| {
                                let k = ui::fit_scale(ui.available_size() - egui::vec2(0.0, 34.0));
                                if tex.is_some() {
                                    let r = egui::Rect::from_min_size(ui.cursor().min, egui::vec2(230.0, 24.0));
                                    if let Some(v) = photo::tabs(ui, r, 1.0, *view) {
                                        *view = v;
                                    }
                                    ui.add_space(32.0);
                                }
                                egui::ScrollArea::both()
                                    .auto_shrink([false, false])
                                    .show(ui, |ui| ui::draw(ui, &reader.state, k))
                                    .inner
                            })
                            .inner,
                    })
                    .inner;
                if let Some(command) = clicked {
                    if cmd::send(&reader.dir, &command).is_ok() {
                        reader.optimistic(&command);
                    }
                }
                ctx.request_repaint_after(Duration::from_millis(80));
            },
        )
    }

    fn process(
        &mut self,
        _buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        _context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        // Pass-through: the host's buffer is left as it is.
        ProcessStatus::Normal
    }
}

impl Vst3Plugin for KeystationStatus {
    const VST3_CLASS_ID: [u8; 16] = *b"KeystationStatus";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] =
        &[Vst3SubCategory::Fx, Vst3SubCategory::Tools];
}

nih_export_vst3!(KeystationStatus);
