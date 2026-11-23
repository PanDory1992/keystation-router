//! Rdzeń wysyłki: bez Windows i bez typów wtyczki, więc testowany na symulowanych zegarach (`cargo test`).
//!
//! Studio One (zegar UM2 przez ASIO4ALL) wkłada ramki do kolejki. Wątek głośników co okres karty
//! (zegar karty płyty głównej) bierze z niej tyle, ile trzeba, i przelicza je na częstotliwość karty.
//! Dwa zegary nigdy nie idą równo (typowo 20–300 ppm różnicy), więc:
//!
//! - **resampler sinc (rubato)** przelicza 44,1 → 48 kHz i jednocześnie odrobinę przyspiesza albo zwalnia;
//! - **regulator PI** pilnuje, żeby w kolejce zawsze był ten sam zapas czasu. Część P reaguje na błąd,
//!   część I uczy się stałej różnicy zegarów, więc w stanie ustalonym zapas stoi dokładnie na celu;
//! - **przeskok**: gdy Windows zatnie się na dłużej i w kolejce zbierze się dużo zaległego dźwięku, nadmiar
//!   jest wyrzucany od razu, a nie odrabiany minutami (opóźnienie nigdy nie zostaje duże);
//! - **przerwa** (kolejka pusta, choć Studio One gra): okres ciszy, potem znowu zbieranie zapasu. W trybie
//!   „auto” zapas rośnie wtedy o 2 ms, aż przerwy ustaną;
//! - **Studio One nie gra** (nic nie przychodzi): cisza, ale to nie jest przerwa i nie zwiększa zapasu.

use rubato::audioadapter_buffers::direct::SequentialSliceOfVecs;
use rubato::{
    Adjustable, Async, FixedAsync, Resampler, SincInterpolationParameters, SincInterpolationType,
    WindowFunction,
};

/// Najwyższa korekta zegara: 0,2% (3,5 centa). Prawdziwy dryf to setne części procenta.
pub const MAX_CORRECTION: f64 = 0.002;
/// Regulator: P 0,1/s (1 ms błędu = 100 ppm), I dobrane do tłumienia krytycznego, wygładzanie 1 s.
/// Spokojny, bo dryf zegarów zmienia się powoli, a każda nerwowość korekty to drobne falowanie wysokości.
const KP: f64 = 0.1;
const KI: f64 = KP * KP / 4.0;
const EMA_TAU: f64 = 1.0;
/// Po ilu sekundach bez nowych ramek uznajemy, że Studio One nie gra (do wyświetlania).
const IDLE_S: f64 = 0.06;
/// Auto-zapas ponad jeden okres karty: 6 ms na nierówne bloki ASIO (128 ramek = 2,9 ms) i budzenie wątku.
pub const AUTO_BASE_S: f64 = 0.006;
/// Auto-zapas: krok po każdej przerwie i górna granica.
pub const AUTO_STEP_S: f64 = 0.002;
pub const AUTO_MAX_S: f64 = 0.060;
/// Sygnał testowy: 440 Hz, −18 dBFS, 0,8 s.
const TONE_HZ: f64 = 440.0;
const TONE_AMP: f32 = 0.125;
const TONE_S: f64 = 0.8;

/// Źródło ramek stereo (kolejka od Studio One).
pub trait Source {
    fn frames(&self) -> usize;
    /// Czyta dokładnie `l.len()` ramek (wywołujący sprawdza wcześniej `frames()`).
    fn read(&mut self, l: &mut [f32], r: &mut [f32]);
    fn skip(&mut self, n: usize);
}

impl Source for rtrb::Consumer<f32> {
    fn frames(&self) -> usize {
        self.slots() / 2
    }
    fn read(&mut self, l: &mut [f32], r: &mut [f32]) {
        let n = l.len().min(r.len());
        if let Ok(chunk) = self.read_chunk(n * 2) {
            let (a, b) = chunk.as_slices();
            let mut it = a.iter().chain(b.iter());
            for k in 0..n {
                l[k] = *it.next().unwrap_or(&0.0);
                r[k] = *it.next().unwrap_or(&0.0);
            }
            chunk.commit_all();
        }
    }
    fn skip(&mut self, n: usize) {
        let n = (n * 2).min(self.slots() & !1);
        if let Ok(chunk) = self.read_chunk(n) {
            chunk.commit_all();
        }
    }
}

/// Regulator PI zapasu. Wejście: zapas w sekundach; wyjście: o ile szybciej czytać kolejkę (względnie).
#[derive(Debug, Clone)]
pub struct Controller {
    ema: f64,
    started: bool,
    integ: f64,
    pub correction: f64,
}

impl Default for Controller {
    fn default() -> Self {
        Controller { ema: 0.0, started: false, integ: 0.0, correction: 0.0 }
    }
}

impl Controller {
    pub fn update(&mut self, fill_s: f64, target_s: f64, dt: f64) -> f64 {
        if !self.started {
            self.ema = fill_s;
            self.started = true;
        }
        let a = 1.0 - (-dt / EMA_TAU).exp();
        self.ema += a * (fill_s - self.ema);
        let e = self.ema - target_s;
        self.integ = (self.integ + KI * e * dt).clamp(-MAX_CORRECTION, MAX_CORRECTION);
        self.correction = (KP * e + self.integ).clamp(-MAX_CORRECTION, MAX_CORRECTION);
        self.correction
    }
    /// Po przeskoku: wygładzony zapas od nowa, ale wyuczona różnica zegarów (I) zostaje.
    pub fn rebase(&mut self, fill_s: f64) {
        self.ema = fill_s;
    }
    pub fn smoothed(&self) -> f64 {
        self.ema
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Phase {
    /// Zbiera zapas (na starcie, po przerwie, po ciszy w Studio One).
    Priming,
    Running,
}

#[derive(Debug, Clone, Default)]
pub struct Stats {
    pub fill_s: f64,
    pub smoothed_s: f64,
    pub target_s: f64,
    pub correction: f64,
    pub gaps: u32,
    pub skips: u32,
    pub idle: bool,
    pub priming: bool,
    pub auto_extra_s: f64,
    /// Opóźnienie po stronie wtyczki: zapas + resampler (bez bufora Windows).
    pub latency_s: f64,
}

pub struct Engine {
    host_rate: f64,
    dev_rate: f64,
    chunk: usize,
    out_channels: usize,
    rs: Async<f32>,
    inb: Vec<Vec<f32>>,
    outb: Vec<Vec<f32>>,
    ctl: Controller,
    phase: Phase,
    last_produced: u64,
    idle_s: f64,
    tone_left: usize,
    tone_pos: usize,
    pub stats: Stats,
}

impl Engine {
    /// `chunk`: ramki karty na jedno wywołanie `render` (okres karty).
    pub fn new(host_rate: f64, dev_rate: f64, chunk: usize, out_channels: usize) -> Result<Self, String> {
        let params = SincInterpolationParameters {
            sinc_len: 128,
            f_cutoff: None,
            oversampling_factor: 256,
            interpolation: SincInterpolationType::Cubic,
            window: WindowFunction::BlackmanHarris2,
        };
        let rs = Async::<f32>::new_sinc(
            dev_rate / host_rate,
            1.0 + 4.0 * MAX_CORRECTION,
            &params,
            chunk.max(1),
            2,
            FixedAsync::Output,
        )
        .map_err(|e| e.to_string())?;
        let max_in = rs.input_frames_max();
        Ok(Engine {
            host_rate,
            dev_rate,
            chunk: chunk.max(1),
            out_channels: out_channels.max(1),
            rs,
            inb: vec![vec![0.0; max_in]; 2],
            outb: vec![vec![0.0; chunk.max(1)]; 2],
            ctl: Controller::default(),
            phase: Phase::Priming,
            last_produced: u64::MAX,
            idle_s: 0.0,
            tone_left: 0,
            tone_pos: 0,
            stats: Stats::default(),
        })
    }

    pub fn chunk(&self) -> usize {
        self.chunk
    }

    pub fn start_tone(&mut self) {
        self.tone_left = (TONE_S * self.dev_rate) as usize;
        self.tone_pos = 0;
    }

    /// Jeden okres karty. `produced`: licznik wszystkich ramek, które Studio One włożyło do kolejki.
    /// `cushion_s`: zapas ponad jeden okres karty z ustawień (0 = auto). `out`: przeplatane próbki karty,
    /// `chunk * out_channels`.
    ///
    /// Zapas jest liczony w chwili budzenia, zanim wątek weźmie okres: cel = to, co zaraz zabierze (okres)
    /// plus zapas. Dzięki temu ten sam zapas działa przy okresie 3 ms i 10 ms.
    pub fn render(&mut self, src: &mut impl Source, produced: u64, cushion_s: f64, out: &mut [f32]) {
        let dt = self.chunk as f64 / self.dev_rate;
        let auto = cushion_s <= 0.0;
        let cushion = if auto { AUTO_BASE_S + self.stats.auto_extra_s } else { cushion_s };
        let need_s = self.rs.input_frames_next() as f64 / self.host_rate;
        let target = need_s + cushion;
        self.stats.target_s = cushion;

        // czy Studio One dołożyło coś od poprzedniego okresu (pusta kolejka bez tego to nie nasza przerwa)
        let host_moved = produced != self.last_produced;
        if host_moved {
            self.idle_s = 0.0;
        } else {
            self.idle_s += dt;
        }
        self.last_produced = produced;
        let idle = self.idle_s > IDLE_S;
        self.stats.idle = idle;

        let mut fill = src.frames();
        let mut fill_s = fill as f64 / self.host_rate;

        if self.phase == Phase::Priming {
            if fill_s + 1e-9 >= target {
                // zbieranie sprawdzamy raz na okres, więc zapas mógł przeskoczyć cel nawet o cały okres:
                // nadmiar od razu precz (to start albo i tak przerwa), żeby regulator nie odrabiał go minutami
                let keep = (target * self.host_rate).round() as usize;
                if fill > keep {
                    src.skip(fill - keep);
                    fill = src.frames();
                    fill_s = fill as f64 / self.host_rate;
                }
                self.phase = Phase::Running;
                self.ctl.rebase(fill_s);
            } else {
                self.silence(out);
                self.finish_stats(fill_s);
                return;
            }
        }

        // przeskok: zaległość większa niż cel plus drugi zapas (co najmniej 20 ms) -> od razu do celu
        let limit = target + cushion.max(0.020);
        if fill_s > limit {
            let keep = (target * self.host_rate).round() as usize;
            src.skip(fill - keep);
            fill = src.frames();
            fill_s = fill as f64 / self.host_rate;
            self.ctl.rebase(fill_s);
            self.stats.skips += 1;
        }

        let c = self.ctl.update(fill_s, target, dt);
        // >1 = wolniej czyta wejście; za pełno (c > 0) -> czytaj szybciej -> mniej niż 1
        let _ = self.rs.set_resample_ratio_relative(1.0 / (1.0 + c), true);

        let need = self.rs.input_frames_next();
        if fill < need {
            self.silence(out);
            self.phase = Phase::Priming;
            if host_moved && produced > 0 {
                self.stats.gaps += 1;
                if auto {
                    self.stats.auto_extra_s = (self.stats.auto_extra_s + AUTO_STEP_S).min(AUTO_MAX_S);
                }
            }
            self.finish_stats(fill_s);
            return;
        }
        let (l, r) = self.inb.split_at_mut(1);
        src.read(&mut l[0][..need], &mut r[0][..need]);
        let ok = {
            let input = SequentialSliceOfVecs::new(&self.inb, 2, need);
            let output = SequentialSliceOfVecs::new_mut(&mut self.outb, 2, self.chunk);
            match (input, output) {
                (Ok(i), Ok(mut o)) => self.rs.process_into_buffer(&i, &mut o, None).is_ok(),
                _ => false,
            }
        };
        if !ok {
            self.silence(out);
            self.finish_stats(fill_s);
            return;
        }
        self.write_out(out);
        self.finish_stats(fill_s);
    }

    fn finish_stats(&mut self, fill_s: f64) {
        self.stats.fill_s = fill_s;
        self.stats.smoothed_s = if self.ctl.started { self.ctl.smoothed() } else { fill_s };
        self.stats.correction = self.ctl.correction;
        self.stats.priming = self.phase == Phase::Priming;
        // ramka czeka średnio: zapas w chwili budzenia minus pół okresu, plus opóźnienie filtra
        let half = 0.5 * self.rs.input_frames_next() as f64 / self.host_rate;
        self.stats.latency_s = (self.stats.smoothed_s - half).max(0.0) + self.rs.output_delay() as f64 / self.dev_rate;
    }

    fn silence(&mut self, out: &mut [f32]) {
        for c in self.outb.iter_mut() {
            c.iter_mut().for_each(|s| *s = 0.0);
        }
        self.write_out(out);
    }

    fn write_out(&mut self, out: &mut [f32]) {
        let ch = self.out_channels;
        for k in 0..self.chunk.min(out.len() / ch) {
            let (mut l, mut r) = (self.outb[0][k], self.outb[1][k]);
            if self.tone_left > 0 {
                let t = self.tone_pos as f64 / self.dev_rate;
                let fade = (t / 0.01).min((self.tone_left as f64 / self.dev_rate) / 0.01).min(1.0) as f32;
                let s = (2.0 * std::f64::consts::PI * TONE_HZ * t).sin() as f32 * TONE_AMP * fade;
                l += s;
                r += s;
                self.tone_left -= 1;
                self.tone_pos += 1;
            }
            let f = &mut out[k * ch..(k + 1) * ch];
            if ch == 1 {
                f[0] = 0.5 * (l + r);
            } else {
                f[0] = l;
                f[1] = r;
                for s in f[2..].iter_mut() {
                    *s = 0.0;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Prosty deterministyczny generator (powtarzalne testy).
    struct Lcg(u64);
    impl Lcg {
        fn next(&mut self) -> f64 {
            self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (self.0 >> 11) as f64 / (1u64 << 53) as f64
        }
    }

    struct Sim {
        host_rate: f64,
        dev_rate: f64,
        host_drift: f64,
        dev_drift: f64,
        block: usize,
        jitter_s: f64,
        host_jitter_s: f64,
        target_s: f64,
        signal: Box<dyn FnMut(u64) -> f32>,
    }

    struct Run {
        out: Vec<f32>,
        lat: Vec<(f64, f64)>, // (czas, wygładzony zapas)
        corr: Vec<(f64, f64)>,
        eng: Engine,
    }

    /// Symulacja w czasie rzeczywistym: Studio One oddaje bloki po `block` ramek co blok/zegar hosta,
    /// karta budzi wątek co okres (z losowym opóźnieniem budzenia do `jitter_s`).
    /// `host_pause`/`dev_pause`: (od, do) w sekundach, kiedy dana strona stoi.
    fn simulate(sim: &mut Sim, seconds: f64, chunk: usize, host_pause: (f64, f64), dev_pause: (f64, f64)) -> Run {
        let (mut prod, mut cons) = rtrb::RingBuffer::<f32>::new((sim.host_rate as usize) * 2);
        let mut eng = Engine::new(sim.host_rate, sim.dev_rate, chunk, 2).unwrap();
        let host_dt = sim.block as f64 / (sim.host_rate * (1.0 + sim.host_drift));
        let dev_dt = chunk as f64 / (sim.dev_rate * (1.0 + sim.dev_drift));
        let mut rng = Lcg(7);
        let (mut th, mut td) = (0.0f64, dev_dt);
        let mut td_wake = td;
        let mut th_wake = th;
        let mut n_in: u64 = 0;
        let mut produced: u64 = 0;
        let mut buf = vec![0.0f32; chunk * 2];
        let mut run = Run { out: Vec::new(), lat: Vec::new(), corr: Vec::new(), eng: Engine::new(1.0, 1.0, 1, 2).unwrap() };
        while th_wake < seconds || td_wake < seconds {
            if th_wake <= td_wake {
                if !(th >= host_pause.0 && th < host_pause.1) {
                    for _ in 0..sim.block {
                        let s = (sim.signal)(n_in);
                        n_in += 1;
                        if prod.slots() >= 2 {
                            let _ = prod.push(s);
                            let _ = prod.push(s);
                        }
                    }
                    produced += sim.block as u64;
                }
                th += host_dt;
                // spóźniony blok Studio One przychodzi później, ale następne trzymają swój rytm
                th_wake = (th + rng.next() * sim.host_jitter_s).max(th_wake);
            } else {
                if !(td_wake >= dev_pause.0 && td_wake < dev_pause.1) {
                    // po zacięciu karta oddaje zaległe okresy naraz (tak robi Windows po wznowieniu)
                    eng.render(&mut cons, produced, sim.target_s, &mut buf);
                    run.out.extend(buf.iter().step_by(2));
                    run.lat.push((td, eng.stats.smoothed_s));
                    run.corr.push((td, eng.stats.correction));
                }
                td += dev_dt;
                td_wake = td + rng.next() * sim.jitter_s;
            }
        }
        run.eng = eng;
        run
    }

    fn sim(host_drift: f64, dev_drift: f64, target_s: f64, signal: Box<dyn FnMut(u64) -> f32>) -> Sim {
        Sim { host_rate: 44_100.0, dev_rate: 48_000.0, host_drift, dev_drift, block: 128, jitter_s: 0.001, host_jitter_s: 0.0005, target_s, signal }
    }

    fn after(v: &[(f64, f64)], t0: f64) -> impl Iterator<Item = f64> + '_ {
        v.iter().filter(move |(t, _)| *t >= t0).map(|(_, x)| *x)
    }

    #[test]
    fn holds_the_cushion_and_learns_the_clock_difference() {
        // UM2 o 150 ppm za szybko, karta o 80 ppm za wolno: razem host szybszy o ok. 230 ppm
        let mut s = sim(150e-6, -80e-6, 0.006, Box::new(|_| 0.0));
        let run = simulate(&mut s, 120.0, 480, (-1.0, -1.0), (-1.0, -1.0));
        assert_eq!(run.eng.stats.gaps, 0, "przerwy");
        assert_eq!(run.eng.stats.skips, 0, "przeskoki");
        let goal = 480.0 / 48_000.0 + 0.006;
        let worst = after(&run.lat, 30.0).map(|x| (x - goal).abs()).fold(0.0, f64::max);
        assert!(worst < 0.0015, "zapas odchodzi od celu o {:.2} ms", worst * 1e3);
        let expected = (1.0 + 150e-6) / (1.0 - 80e-6) - 1.0;
        let late: Vec<f64> = after(&run.corr, 60.0).collect();
        let mean = late.iter().sum::<f64>() / late.len() as f64;
        assert!((mean - expected).abs() < 15e-6, "korekta {:.1} ppm, prawdziwa różnica {:.1} ppm", mean * 1e6, expected * 1e6);
        let spread = late.iter().map(|x| (x - mean).abs()).fold(0.0, f64::max);
        assert!(spread < 60e-6, "korekta pływa o {:.1} ppm", spread * 1e6);
        eprintln!("[pomiar] korekta {:.1} ppm (prawdziwa {:.1}), wahania ±{:.1} ppm, zapas ±{:.2} ms", mean * 1e6, expected * 1e6, spread * 1e6, worst * 1e3);
    }

    #[test]
    fn auto_cushion_is_small_with_low_latency_period() {
        // tryb niskiego opóźnienia: okres 3 ms (144 ramek), auto-zapas 6 ms ponad okres
        let mut s = sim(-200e-6, 120e-6, 0.0, Box::new(|_| 0.0));
        let run = simulate(&mut s, 60.0, 144, (-1.0, -1.0), (-1.0, -1.0));
        assert_eq!(run.eng.stats.gaps, 0);
        assert!((run.eng.stats.target_s - AUTO_BASE_S).abs() < 1e-9, "{}", run.eng.stats.target_s);
        assert!(run.eng.stats.latency_s < 0.010, "opóźnienie wtyczki {:.1} ms", run.eng.stats.latency_s * 1e3);
        eprintln!("[pomiar] okres 3 ms: opóźnienie po stronie wtyczki {:.1} ms", run.eng.stats.latency_s * 1e3);
    }

    #[test]
    fn sine_comes_out_clean() {
        // 1 kHz przez 44,1 -> 48 kHz z dryfem: dopasowanie sinusa do wyjścia, reszta to szum i zniekształcenia
        let f = 1000.0;
        let mut s = sim(100e-6, -50e-6, 0.006, Box::new(move |n| (2.0 * std::f64::consts::PI * f * n as f64 / 44_100.0).sin() as f32 * 0.5));
        let run = simulate(&mut s, 30.0, 480, (-1.0, -1.0), (-1.0, -1.0));
        assert_eq!(run.eng.stats.gaps, 0);
        // okno 50 ms w 25. sekundzie (dłuższe mierzy już powolną zmianę korekty, nie jakość przeliczania)
        let start = (25.0 * 48_000.0) as usize;
        let w = &run.out[start..start + 2_400];
        let snr = best_sine_snr(w, f / 48_000.0);
        eprintln!("[pomiar] SNR 1 kHz po przeliczeniu 44,1->48 kHz z dryfem: {snr:.1} dB");
        assert!(snr > 90.0, "SNR {snr:.1} dB");
    }

    /// Dopasowanie a·sin + b·cos + c przy częstotliwości szukanej wokół `f0` (cykle na próbkę); zwraca SNR w dB.
    fn best_sine_snr(x: &[f32], f0: f64) -> f64 {
        let fit = |f: f64| -> (f64, f64) {
            let (mut ss, mut cc, mut sc, mut xs, mut xc, mut xx) = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0);
            for (n, &v) in x.iter().enumerate() {
                let p = 2.0 * std::f64::consts::PI * f * n as f64;
                let (s, c, v) = (p.sin(), p.cos(), v as f64);
                ss += s * s;
                cc += c * c;
                sc += s * c;
                xs += v * s;
                xc += v * c;
                xx += v * v;
            }
            let det = ss * cc - sc * sc;
            let a = (xs * cc - xc * sc) / det;
            let b = (xc * ss - xs * sc) / det;
            let sig = a * a * ss + b * b * cc + 2.0 * a * b * sc;
            (sig, (xx - sig).max(1e-30))
        };
        let (mut lo, mut hi) = (f0 * (1.0 - 1e-3), f0 * (1.0 + 1e-3));
        for _ in 0..60 {
            let m1 = lo + (hi - lo) / 3.0;
            let m2 = hi - (hi - lo) / 3.0;
            if fit(m1).1 < fit(m2).1 {
                hi = m2;
            } else {
                lo = m1;
            }
        }
        let (sig, noise) = fit((lo + hi) / 2.0);
        10.0 * (sig / noise).log10()
    }

    #[test]
    fn a_windows_stall_does_not_leave_a_big_delay() {
        // błąd wersji 0.1: po zacięciu zaległość odrabiana z prędkością 0,3%, czyli minutami
        let mut s = sim(0.0, 0.0, 0.006, Box::new(|_| 0.0));
        let run = simulate(&mut s, 20.0, 480, (-1.0, -1.0), (5.0, 5.5));
        assert!(run.eng.stats.skips >= 1);
        let worst = after(&run.lat, 6.0).fold(0.0, f64::max);
        assert!(worst < 0.045, "po zacięciu zapas {:.1} ms", worst * 1e3);
        let last = run.lat.last().unwrap().1;
        assert!((last - 0.016).abs() < 0.002, "na końcu {:.1} ms", last * 1e3);
    }

    #[test]
    fn studio_one_silence_is_not_a_gap() {
        let mut s = sim(0.0, 0.0, 0.0, Box::new(|_| 0.0));
        let run = simulate(&mut s, 12.0, 480, (4.0, 7.0), (-1.0, -1.0));
        assert_eq!(run.eng.stats.gaps, 0, "cisza w Studio One liczona jako przerwa");
        assert_eq!(run.eng.stats.auto_extra_s, 0.0);
        let last = run.lat.last().unwrap().1;
        assert!((last - (0.010 + AUTO_BASE_S)).abs() < 0.002, "{last}");
    }

    #[test]
    fn auto_cushion_grows_until_gaps_stop() {
        // bardzo nierówne bloki Studio One (spóźnienia do 10 ms): auto-zapas musi urosnąć i przerwy mają ustać
        let mut s = sim(0.0, 0.0, 0.0, Box::new(|_| 0.0));
        s.host_jitter_s = 0.010;
        let run = simulate(&mut s, 60.0, 144, (-1.0, -1.0), (-1.0, -1.0));
        let gaps_total = run.eng.stats.gaps;
        assert!(gaps_total >= 1 && run.eng.stats.auto_extra_s > 0.0);
        let mut s2 = sim(0.0, 0.0, 0.0, Box::new(|_| 0.0));
        s2.host_jitter_s = 0.010;
        let run2 = simulate(&mut s2, 120.0, 144, (-1.0, -1.0), (-1.0, -1.0));
        assert_eq!(run2.eng.stats.gaps, gaps_total, "przerwy dalej rosną po nauczeniu zapasu");
        assert!(run2.eng.stats.auto_extra_s < AUTO_MAX_S);
        eprintln!("[pomiar] bloki spóźnione do 10 ms: {} przerw na starcie, potem 0; auto-zapas urósł o {:.0} ms", gaps_total, run2.eng.stats.auto_extra_s * 1e3);
    }

    #[test]
    fn test_tone_and_channel_mapping() {
        let mut e = Engine::new(44_100.0, 48_000.0, 480, 6).unwrap();
        let (_p, mut c) = rtrb::RingBuffer::<f32>::new(1024);
        e.start_tone();
        let mut out = vec![1.0f32; 480 * 6];
        e.render(&mut c, 0, 0.0, &mut out);
        let peak = out.chunks(6).map(|f| f[0].abs()).fold(0.0f32, f32::max);
        assert!(peak > 0.03 && peak <= TONE_AMP + 1e-6, "{peak}");
        assert!(out.chunks(6).all(|f| f[0] == f[1] && f[2..].iter().all(|s| *s == 0.0)));
    }

    #[test]
    fn controller_alone_converges_without_overshoot_storm() {
        let mut c = Controller::default();
        let (mut fill, target, dt, drift) = (0.020, 0.012, 0.01, 300e-6);
        let mut max_c: f64 = 0.0;
        for k in 0..12_000 {
            let corr = c.update(fill, target, dt);
            fill += (drift - corr) * dt;
            if k > 6000 {
                max_c = max_c.max((corr - drift).abs());
            }
        }
        assert!((fill - target).abs() < 1e-4, "{fill}");
        assert!(max_c < 20e-6, "{max_c}");
    }
}
