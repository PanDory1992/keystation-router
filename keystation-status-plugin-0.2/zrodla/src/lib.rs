//! Keystation Status: shows the live state of the Keystation Pro 88 MIDI router
//! (pedal mode, una corda, touch mode, "1" mode, keyboard connection) inside the DAW.
//!
//! Audio passes through untouched, so it can sit on any track.
//! Layout of the code, so it can grow:
//!   live.rs - reading/parsing the router's live.json (add fields here)
//!   cmd.rs  - commands back to the router (live-cmd.json)
//!   ui.rs   - drawing, one row per setting (add rows here)

use nih_plug::prelude::*;
use nih_plug_egui::{create_egui_editor, egui, EguiState};
use std::sync::Arc;
use std::time::Duration;

mod cmd;
mod live;
mod ui;

struct KeystationStatus {
    params: Arc<StatusParams>,
}

#[derive(Params)]
struct StatusParams {
    /// Window size, remembered with the project.
    #[persist = "editor-state"]
    editor_state: Arc<EguiState>,
}

impl Default for KeystationStatus {
    fn default() -> Self {
        Self {
            params: Arc::new(StatusParams { editor_state: EguiState::from_size(380, 210) }),
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
        create_egui_editor(
            self.params.editor_state.clone(),
            live::LiveReader::default(),
            |ctx, _| {
                let mut visuals = egui::Visuals::dark();
                visuals.panel_fill = egui::Color32::from_rgb(20, 19, 17);
                ctx.set_visuals(visuals);
            },
            |ctx, _setter, reader| {
                reader.poll();
                let clicked = egui::CentralPanel::default()
                    .show(ctx, |ui| ui::draw(ui, &reader.state))
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
