//! Uszy ("ears"): an AI-readable loudness meter and gain trim for Studio One.
//!
//! Audio passes through with a gain (dB) applied. Every 250 ms the plugin writes
//!   %LOCALAPPDATA%\CodexPedalModes\uszy\<id>.json
//!   {"id","created","t","sr","mom","short","peak","gain_db","plays"}
//! mom/short = BS.1770 momentary (400 ms) / short-term (3 s) loudness in LUFS of the signal
//! AFTER the gain, peak = sample peak dBFS over the last 250 ms.
//! Gain is set by writing <id>.set.json {"gain_db": x}; it is saved with the project.
//! The id is made once and saved with the project, so the same instance keeps its file.

use nih_plug::prelude::*;
use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

#[derive(Params)]
struct UszyParams {
    #[persist = "uszy-id"]
    id: RwLock<String>,
    #[persist = "uszy-created"]
    created: RwLock<f64>,
    #[persist = "uszy-gain"]
    gain_db: AtomicF32,
}

struct Shared {
    mom: AtomicF32,
    short: AtomicF32,
    peak: AtomicF32,
    sr: AtomicF32,
    alive: AtomicBool,
    blocks: std::sync::atomic::AtomicU64,
    inpk: AtomicF32,
    nch: AtomicF32,
}

#[derive(Clone, Copy, Default)]
struct Biquad { b0: f64, b1: f64, b2: f64, a1: f64, a2: f64, z1: f64, z2: f64 }
impl Biquad {
    #[inline]
    fn run(&mut self, x: f64) -> f64 {
        let y = self.b0 * x + self.z1;
        self.z1 = self.b1 * x - self.a1 * y + self.z2;
        self.z2 = self.b2 * x - self.a2 * y;
        y
    }
}

fn k_weighting(fs: f64) -> [Biquad; 2] {
    // BS.1770 K-weighting for any sample rate (same formulas as libebur128)
    let (f0, g, q) = (1681.974450955533, 3.999843853973347, 0.7071752369554196);
    let k = (std::f64::consts::PI * f0 / fs).tan();
    let vh = 10f64.powf(g / 20.0);
    let vb = vh.powf(0.4996667741545416);
    let a0 = 1.0 + k / q + k * k;
    let shelf = Biquad {
        b0: (vh + vb * k / q + k * k) / a0, b1: 2.0 * (k * k - vh) / a0, b2: (vh - vb * k / q + k * k) / a0,
        a1: 2.0 * (k * k - 1.0) / a0, a2: (1.0 - k / q + k * k) / a0, ..Default::default()
    };
    let (f0, q) = (38.13547087602444, 0.5003270373238773);
    let k = (std::f64::consts::PI * f0 / fs).tan();
    let a0 = 1.0 + k / q + k * k;
    let hp = Biquad { b0: 1.0, b1: -2.0, b2: 1.0, a1: 2.0 * (k * k - 1.0) / a0, a2: (1.0 - k / q + k * k) / a0, ..Default::default() };
    [shelf, hp]
}

const BINS: usize = 30; // 30 x 100 ms = 3 s

struct Uszy {
    params: Arc<UszyParams>,
    shared: Arc<Shared>,
    filters: [[Biquad; 2]; 2],
    bin_len: usize,
    bin_pos: usize,
    bin_acc: f64,
    bins: [f64; BINS],
    bin_idx: usize,
    bins_filled: usize,
    peak: f32,
    gain_now: f32,
    started: bool,
}

fn now() -> f64 { SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0) }

fn new_id() -> String {
    let n = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
    let salt = &n as *const u128 as usize as u128;
    format!("{:012x}", (n ^ (salt << 17)) & 0xffff_ffff_ffff)
}

fn dir() -> PathBuf {
    let base = std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_default();
    base.join("CodexPedalModes").join("uszy")
}

fn lufs(ms: f64) -> f32 { if ms <= 1e-12 { -120.0 } else { (-0.691 + 10.0 * ms.log10()) as f32 } }

impl Default for Uszy {
    fn default() -> Self {
        Self {
            params: Arc::new(UszyParams { id: RwLock::new(new_id()), created: RwLock::new(now()), gain_db: AtomicF32::new(0.0) }),
            shared: Arc::new(Shared { mom: AtomicF32::new(-120.0), short: AtomicF32::new(-120.0), peak: AtomicF32::new(-120.0), sr: AtomicF32::new(44100.0), alive: AtomicBool::new(true), blocks: std::sync::atomic::AtomicU64::new(0), inpk: AtomicF32::new(0.0), nch: AtomicF32::new(0.0) }),
            filters: [k_weighting(44100.0); 2],
            bin_len: 4410, bin_pos: 0, bin_acc: 0.0, bins: [0.0; BINS], bin_idx: 0, bins_filled: 0,
            peak: 0.0, gain_now: 1.0, started: false,
        }
    }
}

impl Drop for Uszy {
    fn drop(&mut self) { self.shared.alive.store(false, Ordering::Relaxed); }
}

fn writer(params: Arc<UszyParams>, shared: Arc<Shared>) {
    let d = dir();
    let _ = fs::create_dir_all(&d);
    // The gain also lives in <id>.gain: Studio One does not ask for plug-in state after a change made
    // outside the host, so the project alone would forget it.
    {
        let id = params.id.read().map(|s| s.clone()).unwrap_or_default();
        if let Ok(txt) = fs::read_to_string(d.join(format!("{id}.gain"))) {
            if let Ok(g) = txt.trim().parse::<f32>() { params.gain_db.store(g.clamp(-40.0, 24.0), Ordering::Relaxed); }
        }
    }
    while shared.alive.load(Ordering::Relaxed) {
        let id = params.id.read().map(|s| s.clone()).unwrap_or_default();
        // gain command from the AI
        let set = d.join(format!("{id}.set.json"));
        if let Ok(txt) = fs::read_to_string(&set) {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&txt) {
                if let Some(g) = v.get("gain_db").and_then(|g| g.as_f64()) {
                    let g = (g as f32).clamp(-40.0, 24.0);
                    params.gain_db.store(g, Ordering::Relaxed);
                    let _ = fs::write(d.join(format!("{id}.gain")), format!("{g}"));
                }
            }
            let _ = fs::remove_file(&set);
        }
        let created = params.created.read().map(|c| *c).unwrap_or(0.0);
        let body = serde_json::json!({
            "id": id, "created": created, "t": now(),
            "sr": shared.sr.load(Ordering::Relaxed),
            "mom": shared.mom.load(Ordering::Relaxed),
            "short": shared.short.load(Ordering::Relaxed),
            "peak": shared.peak.load(Ordering::Relaxed),
            "gain_db": params.gain_db.load(Ordering::Relaxed),
            "blocks": shared.blocks.load(Ordering::Relaxed),
            "inpk": shared.inpk.swap(0.0, Ordering::Relaxed),
            "nch": shared.nch.load(Ordering::Relaxed),
        });
        let tmp = d.join(format!("{id}.tmp"));
        if fs::write(&tmp, body.to_string()).is_ok() {
            let _ = fs::rename(&tmp, d.join(format!("{id}.json")));
        }
        thread::sleep(Duration::from_millis(250));
    }
}

impl Plugin for Uszy {
    const NAME: &'static str = "Uszy2";
    const VENDOR: &'static str = "Miki";
    const URL: &'static str = "";
    const EMAIL: &'static str = "";
    const VERSION: &'static str = "0.2.0";
    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[
        AudioIOLayout { main_input_channels: NonZeroU32::new(2), main_output_channels: NonZeroU32::new(2), ..AudioIOLayout::const_default() },
        AudioIOLayout { main_input_channels: NonZeroU32::new(1), main_output_channels: NonZeroU32::new(1), ..AudioIOLayout::const_default() },
    ];
    const MIDI_INPUT: MidiConfig = MidiConfig::None;
    const MIDI_OUTPUT: MidiConfig = MidiConfig::None;
    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> { self.params.clone() }

    fn initialize(&mut self, _l: &AudioIOLayout, cfg: &BufferConfig, _c: &mut impl InitContext<Self>) -> bool {
        let fs = cfg.sample_rate as f64;
        self.shared.sr.store(cfg.sample_rate, Ordering::Relaxed);
        self.filters = [k_weighting(fs); 2];
        self.bin_len = (fs / 10.0).round().max(1.0) as usize;
        self.reset();
        if !self.started {
            self.started = true;
            let (p, s) = (self.params.clone(), self.shared.clone());
            thread::spawn(move || writer(p, s));
        }
        true
    }

    fn reset(&mut self) {
        self.bin_pos = 0; self.bin_acc = 0.0; self.bins = [0.0; BINS]; self.bin_idx = 0; self.bins_filled = 0;
        for f in self.filters.iter_mut() { for b in f.iter_mut() { b.z1 = 0.0; b.z2 = 0.0; } }
    }

    fn process(&mut self, buffer: &mut Buffer, _a: &mut AuxiliaryBuffers, _c: &mut impl ProcessContext<Self>) -> ProcessStatus {
        let target = util::db_to_gain(self.params.gain_db.load(Ordering::Relaxed));
        self.shared.blocks.fetch_add(1, Ordering::Relaxed);
        self.shared.nch.store(buffer.channels() as f32, Ordering::Relaxed);
        let mut inpk = 0.0f32;
        for ch in buffer.as_slice_immutable() { for x in ch.iter() { inpk = inpk.max(x.abs()); } }
        if inpk > self.shared.inpk.load(Ordering::Relaxed) { self.shared.inpk.store(inpk, Ordering::Relaxed); }
        for mut frame in buffer.iter_samples() {
            self.gain_now += (target - self.gain_now) * 0.001;
            let mut ms = 0.0f64;
            for (ch, s) in frame.iter_mut().enumerate() {
                *s *= self.gain_now;
                let a = s.abs();
                if a > self.peak { self.peak = a; }
                if ch < 2 {
                    let f = &mut self.filters[ch];
                    let y0 = f[0].run(*s as f64);
                    let y = f[1].run(y0);
                    ms += y * y;
                }
            }
            self.bin_acc += ms;
            self.bin_pos += 1;
            if self.bin_pos >= self.bin_len {
                self.bins[self.bin_idx] = self.bin_acc / self.bin_len as f64;
                self.bin_idx = (self.bin_idx + 1) % BINS;
                self.bins_filled = (self.bins_filled + 1).min(BINS);
                self.bin_acc = 0.0; self.bin_pos = 0;
                let last = |n: usize| -> f64 {
                    let n = n.min(self.bins_filled).max(1);
                    (1..=n).map(|k| self.bins[(self.bin_idx + BINS - k) % BINS]).sum::<f64>() / n as f64
                };
                self.shared.mom.store(lufs(last(4)), Ordering::Relaxed);
                self.shared.short.store(lufs(last(30)), Ordering::Relaxed);
                let p = if self.peak > 0.0 { 20.0 * self.peak.log10() } else { -120.0 };
                let old = self.shared.peak.load(Ordering::Relaxed);
                // decay the reported peak so it reflects the last ~quarter second
                self.shared.peak.store(if p > old - 3.0 { p } else { old - 3.0 }, Ordering::Relaxed);
                self.peak = 0.0;
            }
        }
        ProcessStatus::Normal
    }
}

impl Vst3Plugin for Uszy {
    const VST3_CLASS_ID: [u8; 16] = *b"MikiUszyMeterAI2";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[Vst3SubCategory::Fx, Vst3SubCategory::Analyzer];
}

nih_export_vst3!(Uszy);
