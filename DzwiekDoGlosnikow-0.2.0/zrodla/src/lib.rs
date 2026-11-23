//! Dźwięk do Głośników 0.2: wysyła jeden kanał Studio One na drugie wyjście Windows (np. Geniusy na karcie
//! płyty głównej), bez dokładania go do ASIO4ALL. ASIO4ALL zostaje tylko z UM2, więc bufor pianina się nie zmienia.
//!
//! Wątek Studio One tylko kopiuje próbki do kolejki bez blokad (rtrb). Resztę robi wątek głośników
//! (render.rs): MMCSS „Pro Audio”, zdarzenia karty, krótki okres, przeliczanie sinc z korektą zegara
//! (engine.rs). Wyjście wtyczki do Main jest domyślnie ciche (wysyłka), a przełącznik „Też do Main”
//! zostawia dźwięk w miksie, np. do grania na słuchawkach.

use nih_plug::prelude::*;
use nih_plug_egui::{create_egui_editor, EguiState};
use std::sync::atomic::Ordering;
use std::sync::{Arc, RwLock};

pub mod engine;
mod render;
pub mod shared;
mod ui;

use shared::Shared;

/// Kolejka: 1 s dźwięku. Regulator trzyma w niej kilka ms, reszta to bezpieczny zapas na zacięcia.
const RING_SECONDS: f64 = 1.0;

pub struct DzwiekDoGlosnikow {
    params: Arc<SendParams>,
    shared: Arc<Shared>,
    producer: Option<rtrb::Producer<f32>>,
    worker: Option<render::Worker>,
}

#[derive(Params)]
pub struct SendParams {
    #[persist = "editor-state"]
    editor_state: Arc<EguiState>,
    #[persist = "device"]
    pub device: Arc<RwLock<String>>,
    #[id = "gain"]
    pub gain: FloatParam,
    /// Zapas ponad jeden okres karty; 0 = auto (6 ms i więcej, jeśli zdarzą się przerwy).
    #[id = "cushion"]
    pub cushion_ms: IntParam,
    #[id = "main"]
    pub also_main: BoolParam,
}

impl Default for DzwiekDoGlosnikow {
    fn default() -> Self {
        Self {
            params: Arc::new(SendParams {
                editor_state: EguiState::from_size(520, 380),
                device: Arc::new(RwLock::new(String::new())),
                gain: FloatParam::new(
                    "Poziom wysyłki",
                    1.0,
                    FloatRange::Skewed {
                        min: util::db_to_gain(-60.0),
                        max: util::db_to_gain(6.0),
                        factor: FloatRange::gain_skew_factor(-60.0, 6.0),
                    },
                )
                .with_smoother(SmoothingStyle::Logarithmic(30.0))
                .with_unit(" dB")
                .with_value_to_string(formatters::v2s_f32_gain_to_db(1))
                .with_string_to_value(formatters::s2v_f32_gain_to_db()),
                cushion_ms: IntParam::new("Zapas", 0, IntRange::Linear { min: 0, max: 100 })
                    .with_unit(" ms")
                    .with_value_to_string(Arc::new(|v| if v == 0 { "auto".into() } else { format!("{v}") })),
                also_main: BoolParam::new("Też do Main", false)
                    .with_value_to_string(Arc::new(|v| if v { "tak".into() } else { "nie".into() })),
            }),
            shared: Arc::new(Shared::default()),
            producer: None,
            worker: None,
        }
    }
}

impl Plugin for DzwiekDoGlosnikow {
    const NAME: &'static str = "Dzwiek do Glosnikow";
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
            |ctx, _| ui::style(ctx),
            move |ctx, setter, _| {
                ui::draw(ctx, setter, &params, &shared);
                ctx.request_repaint_after(std::time::Duration::from_millis(250));
            },
        )
    }

    fn initialize(&mut self, _layout: &AudioIOLayout, buffer_config: &BufferConfig, _context: &mut impl InitContext<Self>) -> bool {
        // najpierw zatrzymać stary wątek (zmiana częstotliwości w Studio One wywołuje initialize ponownie)
        self.worker = None;
        let rate = buffer_config.sample_rate.round() as u32;
        self.shared.host_rate.store(rate, Ordering::Relaxed);
        self.shared.cushion_us.store(self.params.cushion_ms.value() as u32 * 1000, Ordering::Relaxed);
        let saved = self.params.device.read().map(|s| s.clone()).unwrap_or_default();
        if let Ok(mut w) = self.shared.wanted.lock() {
            *w = saved;
        }
        let (producer, consumer) = rtrb::RingBuffer::<f32>::new((rate as f64 * RING_SECONDS) as usize * 2);
        self.producer = Some(producer);
        self.worker = Some(render::Worker::start(self.shared.clone(), consumer));
        true
    }

    fn deactivate(&mut self) {
        self.worker = None;
        self.producer = None;
    }

    fn process(&mut self, buffer: &mut Buffer, _aux: &mut AuxiliaryBuffers, _context: &mut impl ProcessContext<Self>) -> ProcessStatus {
        self.shared.cushion_us.store(self.params.cushion_ms.value() as u32 * 1000, Ordering::Relaxed);
        let also_main = self.params.also_main.value();
        let Some(producer) = self.producer.as_mut() else {
            return ProcessStatus::Normal;
        };
        let mono = buffer.channels() == 1;
        let frames = buffer.samples();
        let mut peak = 0.0f32;
        let mut dropped = 0u32;
        // cały blok naraz, jeśli się mieści (jedna operacja na kolejce zamiast dwóch na każdą próbkę)
        let room = producer.slots() / 2;
        let mut n = frames.min(room);
        let mut chunk = producer.write_chunk_uninit(n * 2).ok();
        if chunk.is_none() {
            n = 0;
        }
        dropped += (frames - n) as u32;
        for (k, mut frame) in buffer.iter_samples().enumerate() {
            let g = self.params.gain.smoothed.next();
            let mut it = frame.iter_mut();
            let l = it.next().map(|s| *s).unwrap_or(0.0);
            let r = if mono { l } else { it.next().map(|s| *s).unwrap_or(0.0) };
            let (l, r) = (l * g, r * g);
            peak = peak.max(l.abs()).max(r.abs());
            if k < n {
                if let Some(c) = chunk.as_mut() {
                    put_frame(c, k, l, r);
                }
            }
            if !also_main {
                for s in frame.iter_mut() {
                    *s = 0.0;
                }
            }
        }
        if let Some(c) = chunk {
            // wszystkie n*2 miejsc zostało zapisanych w pętli wyżej
            unsafe { c.commit_all() };
        }
        self.shared.produced.fetch_add(n as u64, Ordering::Release);
        if dropped > 0 {
            self.shared.dropped.fetch_add(dropped, Ordering::Relaxed);
        }
        let old = f32::from_bits(self.shared.peak_bits.load(Ordering::Relaxed));
        self.shared.peak_bits.store(peak.max(old * 0.92).to_bits(), Ordering::Relaxed);
        ProcessStatus::Normal
    }
}

/// Zapis ramki `k` do kawałka kolejki, który może być rozcięty na dwa (koniec i początek bufora kołowego).
fn put_frame(c: &mut rtrb::chunks::WriteChunkUninit<'_, f32>, k: usize, l: f32, r: f32) {
    let (a, b) = c.as_mut_slices();
    for (i, v) in [(2 * k, l), (2 * k + 1, r)] {
        if i < a.len() {
            a[i].write(v);
        } else if let Some(x) = b.get_mut(i - a.len()) {
            x.write(v);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::Source;

    #[test]
    fn frames_survive_the_ring_wrap_in_order() {
        let (mut p, mut c) = rtrb::RingBuffer::<f32>::new(10);
        // przesunąć początek tak, żeby kolejny zapis 4 ramek (8 próbek) rozciął się na dwa kawałki
        let mut w = p.write_chunk_uninit(6).unwrap();
        for k in 0..3 {
            put_frame(&mut w, k, 0.0, 0.0);
        }
        unsafe { w.commit_all() };
        c.skip(3);
        let mut w = p.write_chunk_uninit(8).unwrap();
        assert!(w.as_mut_slices().1.len() > 0, "test ma sprawdzać rozcięty kawałek");
        for k in 0..4 {
            put_frame(&mut w, k, k as f32 + 0.25, -(k as f32) - 0.5);
        }
        unsafe { w.commit_all() };
        let (mut l, mut r) = ([0.0f32; 4], [0.0f32; 4]);
        c.read(&mut l, &mut r);
        assert_eq!(l, [0.25, 1.25, 2.25, 3.25]);
        assert_eq!(r, [-0.5, -1.5, -2.5, -3.5]);
    }
}

impl Vst3Plugin for DzwiekDoGlosnikow {
    const VST3_CLASS_ID: [u8; 16] = *b"MikiAudioSend001";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[Vst3SubCategory::Fx, Vst3SubCategory::Tools];
}

nih_export_vst3!(DzwiekDoGlosnikow);
