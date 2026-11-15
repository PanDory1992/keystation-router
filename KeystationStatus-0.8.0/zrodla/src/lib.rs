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
use std::sync::{Arc, RwLock};
use std::time::Duration;

mod cmd;
mod live;
mod photo;
mod velo;

struct EditorState {
    reader: live::LiveReader,
    listener: velo::Listener,
    curves: velo::Curves,
    /// backgrounds decoded so far (one per state seen; usually one or two)
    textures: Vec<(String, egui::TextureHandle)>,
}

const DEFAULT_SIDE: u32 = 1000;

fn install_fonts(ctx: &egui::Context) {
    let mut fonts = egui::FontDefinitions::default();
    let mut add = |name: &str, data: &'static [u8]| {
        fonts.font_data.insert(name.into(), Arc::new(egui::FontData::from_static(data)));
    };
    add(photo::CAP, include_bytes!("../assets/IBMPlexSansCondensed-Medium.ttf"));
    add(photo::CAP_B, include_bytes!("../assets/IBMPlexSansCondensed-SemiBold.ttf"));
    add(photo::MONO, include_bytes!("../assets/IBMPlexMono-Regular.ttf"));
    add(photo::MONO_M, include_bytes!("../assets/IBMPlexMono-Medium.ttf"));
    add("jp", include_bytes!("../assets/NotoSansJP-sub.ttf"));
    for fam in [photo::CAP, photo::CAP_B, photo::MONO, photo::MONO_M] {
        fonts.families.insert(egui::FontFamily::Name(fam.into()), vec![fam.into(), "jp".into()]);
    }
    let prop = fonts.families.entry(egui::FontFamily::Proportional).or_default();
    prop.insert(0, photo::CAP.into());
    ctx.set_fonts(fonts);
}

struct KeystationStatus {
    params: Arc<StatusParams>,
}

#[derive(Params)]
struct StatusParams {
    /// Window size, remembered with the project (0.8.0: new key, the square one-screen window).
    #[persist = "editor-state-v8"]
    editor_state: Arc<EguiState>,
    /// lower screen mode and where the pedal is plugged
    #[persist = "prefs"]
    prefs: Arc<RwLock<photo::Prefs>>,
}

impl Default for KeystationStatus {
    fn default() -> Self {
        Self {
            params: Arc::new(StatusParams {
                editor_state: EguiState::from_size(DEFAULT_SIDE, DEFAULT_SIDE),
                prefs: Arc::new(RwLock::new(photo::Prefs::default())),
            }),
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
        let prefs_arc = self.params.prefs.clone();
        create_egui_editor(
            self.params.editor_state.clone(),
            None::<EditorState>,
            |ctx, state| {
                let mut visuals = egui::Visuals::light();
                visuals.panel_fill = egui::Color32::from_rgb(28, 29, 31);
                visuals.resize_corner_size = 14.0;
                ctx.set_visuals(visuals);
                install_fonts(ctx);
                *state = Some(EditorState {
                    reader: live::LiveReader::default(),
                    listener: velo::Listener::start(),
                    curves: velo::Curves::default(),
                    textures: Vec::new(),
                });
            },
            move |ctx, _setter, state| {
                let Some(st) = state.as_mut() else { return };
                st.reader.poll();
                st.curves.update(&st.reader.dir, st.reader.state.touch.as_deref());
                let before = prefs_arc.read().map(|p| p.clone()).unwrap_or_default();
                let mut prefs = before.clone();
                // the bus thread waits for this frame (a few ms) while the columns are drawn
                let mut velo = st.listener.velo.lock().unwrap_or_else(|e| e.into_inner());
                velo.prune(live::now_unix());
                if velo.pedal_seen && prefs.jack == "none" {
                    prefs.jack = "A37".into();                   // a pedal press: the pedal is in A37
                }
                velo.pedal_seen = false;
                let keyboard_on = st.reader.state.is_fresh() && st.reader.state.connected == Some(true);
                let name = photo::layout().background(keyboard_on, &prefs.jack).to_owned();
                if !st.textures.iter().any(|t| t.0 == name) {
                    if let Some(t) = photo::texture(ctx, &name) {
                        st.textures.push((name.clone(), t));
                    }
                }
                let tex = st.textures.iter().find(|t| t.0 == name).map(|t| t.1.clone());
                let clicked = ResizableWindow::new("keystation-status")
                    .min_size(egui::vec2(640.0, 640.0))
                    .show(ctx, &egui_state, |ui| match &tex {
                        Some(tex) => photo::draw(ui, &st.reader.state, tex, &velo, &st.curves, &mut prefs),
                        None => {
                            ui.label("Brak tła (nie udało się wczytać obrazka).");
                            None
                        }
                    })
                    .inner;
                drop(velo);
                if prefs != before {
                    if let Ok(mut w) = prefs_arc.write() {
                        *w = prefs;
                    }
                }
                if let Some(command) = clicked {
                    if cmd::send(&st.reader.dir, &command).is_ok() {
                        st.reader.optimistic(&command);
                    }
                }
                ctx.request_repaint_after(Duration::from_millis(33));
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
