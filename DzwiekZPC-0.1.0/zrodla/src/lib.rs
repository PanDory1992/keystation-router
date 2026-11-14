//! Dźwięk z PC: plays a Windows audio device inside Studio One.
//!
//! Why: ASIO4ALL holds the UM2 exclusively, so Firefox and other Windows programs go silent while Studio One runs.
//! Putting VB-Cable next to the UM2 inside ASIO4ALL needs a 512 buffer, because ASIO then clocks VB-Cable too.
//! Here ASIO4ALL keeps only the UM2 (buffer 128 for the piano) and this plugin reads VB-Cable (or the loopback of
//! another output) in Windows shared mode on its own thread, with its own cushion (~60 ms). Only the browser audio
//! waits; the piano does not.
//!
//!   capture.rs - the WASAPI thread (device list, shared-mode capture, drift control, ring writer)
//!   dsp.rs     - resampler and drift control (pure, tested in tests/dsp_only)
//!   shared.rs  - atomics between the threads and the editor
//!   ui.rs      - the window

use nih_plug::prelude::*;
use nih_plug_egui::{create_egui_editor, EguiState};
use std::sync::atomic::Ordering;
use std::sync::{Arc, RwLock};

mod capture;
pub mod dsp;
mod shared;
mod ui;

use shared::Shared;

const RING_SECONDS: f64 = 1.0;

pub struct DzwiekZPc {
    params: Arc<ZPcParams>,
    shared: Arc<Shared>,
    consumer: Option<rtrb::Consumer<f32>>,
    worker: Option<capture::Worker>,
    priming: bool,
    rate: u32,
}

#[derive(Params)]
pub struct ZPcParams {
    #[persist = "editor-state"]
    editor_state: Arc<EguiState>,
    /// The chosen source ("in|CABLE Output ..." or "out|Speakers ..."), saved with the song.
    #[persist = "source"]
    pub source: Arc<RwLock<String>>,
    #[id = "gain"]
    pub gain: FloatParam,
    /// Cushion between the device and Studio One. More = safer, the browser audio is that much later.
    #[id = "cushion"]
    pub cushion_ms: IntParam,
}

impl Default for DzwiekZPc {
    fn default() -> Self {
        Self {
            params: Arc::new(ZPcParams {
                editor_state: EguiState::from_size(440, 300),
                source: Arc::new(RwLock::new(String::new())),
                gain: FloatParam::new(
                    "Głośność",
                    util::db_to_gain(-6.0),
                    FloatRange::Skewed {
                        min: util::db_to_gain(-60.0),
                        max: util::db_to_gain(6.0),
                        factor: FloatRange::gain_skew_factor(-60.0, 6.0),
                    },
                )
                .with_smoother(SmoothingStyle::Logarithmic(50.0))
                .with_unit(" dB")
                .with_value_to_string(formatters::v2s_f32_gain_to_db(1))
                .with_string_to_value(formatters::s2v_f32_gain_to_db()),
                cushion_ms: IntParam::new("Zapas", 60, IntRange::Linear { min: 20, max: 250 }).with_unit(" ms"),
            }),
            shared: Arc::new(Shared::default()),
            consumer: None,
            worker: None,
            priming: true,
            rate: 48_000,
        }
    }
}

impl Plugin for DzwiekZPc {
    const NAME: &'static str = "Dzwiek z PC";
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
        let params = self.params.clone();
        let shared = self.shared.clone();
        create_egui_editor(
            self.params.editor_state.clone(),
            (),
            |ctx, _| {
                let mut v = nih_plug_egui::egui::Visuals::dark();
                v.panel_fill = nih_plug_egui::egui::Color32::from_rgb(20, 19, 17);
                ctx.set_visuals(v);
            },
            move |ctx, setter, _| {
                ui::draw(ctx, setter, &params, &shared);
                ctx.request_repaint_after(std::time::Duration::from_millis(200));
            },
        )
    }

    fn initialize(
        &mut self,
        _layout: &AudioIOLayout,
        buffer_config: &BufferConfig,
        _context: &mut impl InitContext<Self>,
    ) -> bool {
        self.worker = None; // stops an old thread first
        self.rate = buffer_config.sample_rate.round() as u32;
        self.shared.host_rate.store(self.rate, Ordering::Relaxed);
        self.shared.target_ms.store(self.params.cushion_ms.value() as u32, Ordering::Relaxed);
        let saved = self.params.source.read().map(|s| s.clone()).unwrap_or_default();
        *self.shared.wanted.lock().unwrap() = saved;
        let cap = (self.rate as f64 * RING_SECONDS) as usize * 2;
        let (producer, consumer) = rtrb::RingBuffer::<f32>::new(cap);
        self.consumer = Some(consumer);
        self.priming = true;
        self.worker = Some(capture::Worker::start(self.shared.clone(), producer, self.rate));
        true
    }

    fn deactivate(&mut self) {
        self.worker = None;
        self.consumer = None;
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        _context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        self.shared.target_ms.store(self.params.cushion_ms.value() as u32, Ordering::Relaxed);
        let Some(consumer) = self.consumer.as_mut() else {
            return ProcessStatus::Normal;
        };
        let target = self.shared.target_frames(self.rate) as usize * 2;
        if self.priming && consumer.slots() >= target {
            self.priming = false;
        }
        let mut peak = 0.0f32;
        let mono = buffer.channels() == 1;
        for mut frame in buffer.iter_samples() {
            let gain = self.params.gain.smoothed.next();
            let (l, r) = if self.priming {
                (0.0, 0.0)
            } else {
                match (consumer.pop(), consumer.pop()) {
                    (Ok(l), Ok(r)) => (l, r),
                    _ => {
                        // the ring ran dry: wait for a full cushion again instead of stuttering
                        self.priming = true;
                        self.shared.gaps.fetch_add(1, Ordering::Relaxed);
                        (0.0, 0.0)
                    }
                }
            };
            let (l, r) = (l * gain, r * gain);
            peak = peak.max(l.abs()).max(r.abs());
            let mut it = frame.iter_mut();
            if mono {
                if let Some(s) = it.next() {
                    *s += 0.5 * (l + r);
                }
            } else {
                if let Some(s) = it.next() {
                    *s += l;
                }
                if let Some(s) = it.next() {
                    *s += r;
                }
            }
        }
        let old = f32::from_bits(self.shared.peak_bits.load(Ordering::Relaxed));
        self.shared.peak_bits.store(peak.max(old * 0.9).to_bits(), Ordering::Relaxed);
        ProcessStatus::Normal
    }
}

impl Vst3Plugin for DzwiekZPc {
    const VST3_CLASS_ID: [u8; 16] = *b"MikiDzwiekZPC001";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[Vst3SubCategory::Fx, Vst3SubCategory::Tools];
}

nih_export_vst3!(DzwiekZPc);
