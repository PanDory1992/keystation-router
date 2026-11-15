//! Spartito S1: Miki's Spartito (Max for Live) as a VST3 instrument for Studio One.
//!
//! The whole of spartito.js runs here as it ran in the Max device's editor
//! window - the same toolbar, the same score, the same mouse and keys - inside
//! QuickJS, with Max's objects replaced by small stand-ins (js/prelude.js) and
//! the part of the brain that a VST3 can have (js/glue.js):
//!   engine.rs - QuickJS and the host functions the stand-ins need
//!   core.rs   - the score's life: the notes the track plays, the clock, HEAR, saving
//!   render.rs - what spartito.js draws, rasterised by tiny-skia
//!   fonts.rs  - Arial and Times New Roman (or their metric twins)
//!   bus.rs    - HEAR through the router's UDP bus
//!   ui.rs     - the window: mouse and keys in, the picture out, file dialogs
//!
//! A VST3 cannot change Studio One's parts: the score is this plugin's own,
//! saved with the song, and goes back to a track as an exported .mid.

use nih_plug::prelude::*;
use nih_plug_egui::{create_egui_editor, EguiState};
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::{Arc, Mutex, RwLock};

pub mod bus;
pub mod core;
pub mod engine;
pub mod fonts;
pub mod render;
pub mod ui;

use crate::core::{Clock, Core, Ev};

const RING: usize = 1 << 16;

/// What the audio thread publishes.
pub struct Shared {
    rx: Mutex<rtrb::Consumer<Ev>>,
    host: AtomicU64,
    free: AtomicU64,
    tempo: AtomicU64,
    num: AtomicU32,
    den: AtomicU32,
    playing: AtomicBool,
}

fn f64_get(a: &AtomicU64) -> f64 {
    f64::from_bits(a.load(Ordering::Relaxed))
}
fn f64_set(a: &AtomicU64, v: f64) {
    a.store(v.to_bits(), Ordering::Relaxed)
}

impl Shared {
    fn new(rx: rtrb::Consumer<Ev>) -> Shared {
        Shared {
            rx: Mutex::new(rx),
            host: AtomicU64::new(0f64.to_bits()),
            free: AtomicU64::new(0f64.to_bits()),
            tempo: AtomicU64::new(120f64.to_bits()),
            num: AtomicU32::new(4),
            den: AtomicU32::new(4),
            playing: AtomicBool::new(false),
        }
    }

    pub fn clock(&self) -> Clock {
        Clock {
            host: f64_get(&self.host),
            free: f64_get(&self.free),
            playing: self.playing.load(Ordering::Relaxed),
            tempo: f64_get(&self.tempo),
            num: self.num.load(Ordering::Relaxed).max(1),
            den: self.den.load(Ordering::Relaxed).max(1),
        }
    }
}

/// The score's state shared by the plugin, its background task and the editor.
pub struct Life {
    pub shared: Shared,
    pub core: Mutex<Option<Core>>,
    /// what the project saves (JSON from glue.js s1_save)
    pub score: Arc<RwLock<String>>,
    pub start_error: Mutex<Option<String>>,
}

impl Life {
    /// Runs `f` on the core, starting it (and loading the saved score) the first time.
    pub fn with<R>(&self, f: impl FnOnce(&mut Core) -> R) -> Option<R> {
        let mut guard = match self.core.lock() {
            Ok(g) => g,
            Err(p) => p.into_inner(),
        };
        if guard.is_none() {
            match Core::new() {
                Ok(mut c) => {
                    if let Ok(s) = self.score.read() {
                        c.load(&s);
                    }
                    *guard = Some(c);
                }
                Err(e) => {
                    if let Ok(mut se) = self.start_error.lock() {
                        *se = Some(e);
                    }
                    return None;
                }
            }
        }
        guard.as_mut().map(f)
    }

    /// Notes in, clock on, saved if changed. Called by the background task and every editor frame.
    pub fn service(&self) {
        let mut evs = Vec::new();
        if let Ok(mut rx) = self.shared.rx.lock() {
            while let Ok(ev) = rx.pop() {
                evs.push(ev);
            }
        }
        let clock = self.shared.clock();
        let saved = self.with(|c| {
            c.input(&evs);
            c.tick(clock);
            c.save_if_changed()
        });
        if let Some(Some(json)) = saved {
            if let Ok(mut s) = self.score.write() {
                *s = json;
            }
        }
    }

    /// The host restored a project or a preset: show what it holds.
    pub fn reload(&self) {
        let json = self.score.read().map(|s| s.clone()).unwrap_or_default();
        self.with(|c| c.load(&json));
    }
}

#[derive(Params)]
pub struct S1Params {
    #[persist = "editor-state"]
    editor_state: Arc<EguiState>,
    /// The score, saved with the Studio One song.
    #[persist = "score"]
    pub score: Arc<RwLock<String>>,
}

pub struct SpartitoS1 {
    params: Arc<S1Params>,
    life: Arc<Life>,
    tx: rtrb::Producer<Ev>,
    free_samples: u64,
    since_tick: u64,
    sample_rate: f32,
}

impl Default for SpartitoS1 {
    fn default() -> Self {
        let (tx, rx) = rtrb::RingBuffer::new(RING);
        let (w, h) = core::WINDOWS[1];
        let score = Arc::new(RwLock::new(String::new()));
        let life = Arc::new(Life {
            shared: Shared::new(rx),
            core: Mutex::new(None),
            score: score.clone(),
            start_error: Mutex::new(None),
        });
        Self {
            params: Arc::new(S1Params { editor_state: EguiState::from_size(w, h), score }),
            life,
            tx,
            free_samples: 0,
            since_tick: 0,
            sample_rate: 44100.0,
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum Task {
    Service,
}

impl Plugin for SpartitoS1 {
    const NAME: &'static str = "Spartito S1";
    const VENDOR: &'static str = "Miki";
    const URL: &'static str = "http://www.remodevicocomposer.eu";
    const EMAIL: &'static str = "";
    const VERSION: &'static str = env!("CARGO_PKG_VERSION");

    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[AudioIOLayout {
        main_input_channels: None,
        main_output_channels: NonZeroU32::new(2),
        ..AudioIOLayout::const_default()
    }];
    const MIDI_INPUT: MidiConfig = MidiConfig::Basic;
    const MIDI_OUTPUT: MidiConfig = MidiConfig::None;

    type SysExMessage = ();
    type BackgroundTask = Task;

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn task_executor(&mut self) -> TaskExecutor<Self> {
        let life = self.life.clone();
        Box::new(move |_task| life.service())
    }

    fn initialize(&mut self, _layout: &AudioIOLayout, config: &BufferConfig, _ctx: &mut impl InitContext<Self>) -> bool {
        self.sample_rate = config.sample_rate;
        // called again after the host restores the state: load what it holds
        self.life.reload();
        true
    }

    fn editor(&mut self, _async_executor: AsyncExecutor<Self>) -> Option<Box<dyn Editor>> {
        let egui_state = self.params.editor_state.clone();
        let life = self.life.clone();
        create_egui_editor(
            self.params.editor_state.clone(),
            ui::EditorState::default(),
            |_ctx, _state| {},
            move |ctx, _setter, state| ui::frame(ctx, state, &life, &egui_state),
        )
    }

    fn process(&mut self, buffer: &mut Buffer, _aux: &mut AuxiliaryBuffers, context: &mut impl ProcessContext<Self>) -> ProcessStatus {
        let tr = context.transport();
        let tempo = tr.tempo.filter(|t| *t > 1.0).unwrap_or(120.0);
        let playing = tr.playing;
        let spb = self.sample_rate as f64 * 60.0 / tempo;
        let host0 = tr.pos_beats().unwrap_or(0.0);
        let free0 = self.free_samples as f64 / spb;
        let num = tr.time_sig_numerator.unwrap_or(4).max(1) as u32;
        let den = tr.time_sig_denominator.unwrap_or(4).max(1) as u32;
        let mut sent = false;
        while let Some(event) = context.next_event() {
            let (pitch, on, vel, timing) = match event {
                NoteEvent::NoteOn { timing, note, velocity, .. } => (note, true, velocity, timing),
                NoteEvent::NoteOff { timing, note, .. } => (note, false, 0.0, timing),
                _ => continue,
            };
            let dt = timing as f64 / spb;
            let (host, free) = (host0 + dt, free0 + dt);
            let ev = if on {
                Ev::On { pitch, vel: (vel * 127.0).round().clamp(1.0, 127.0) as u8, host, free, playing }
            } else {
                Ev::Off { pitch, host, free, playing }
            };
            sent |= self.tx.push(ev).is_ok();
        }
        let n = buffer.samples() as u64;
        self.free_samples += n;
        let s = &self.life.shared;
        f64_set(&s.host, host0 + n as f64 / spb);
        f64_set(&s.free, self.free_samples as f64 / spb);
        f64_set(&s.tempo, tempo);
        s.num.store(num, Ordering::Relaxed);
        s.den.store(den, Ordering::Relaxed);
        s.playing.store(playing, Ordering::Relaxed);
        // notes now; the clock about ten times a second, so a take ends and grows with the window closed
        self.since_tick += n;
        if sent || self.since_tick as f32 > self.sample_rate * 0.1 {
            self.since_tick = 0;
            context.execute_background(Task::Service);
        }
        for channel in buffer.as_slice() {
            channel.fill(0.0);
        }
        ProcessStatus::Normal
    }
}

impl Vst3Plugin for SpartitoS1 {
    const VST3_CLASS_ID: [u8; 16] = *b"SpartitoS1Score_";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[Vst3SubCategory::Instrument, Vst3SubCategory::Tools];
}

nih_export_vst3!(SpartitoS1);
