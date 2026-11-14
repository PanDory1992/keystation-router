//! Pure DSP, no Windows and no plugin types, so it is tested on its own (`cargo test` in tests/dsp_only).
//!
//! The capture device (VB-Cable, Realtek...) and the UM2 run on two different clocks. Over minutes they drift apart
//! by a few hundred frames, so the capture side is resampled by a ratio a hair away from 1.0 that keeps the
//! cushion between them (the ring buffer) at its target: too full -> read the input a bit faster, too empty -> slower.

/// Stereo resampler with a variable step (input frames per output frame), cubic Hermite interpolation.
/// Good enough for browser/system audio, and clean for the tiny ratios the drift needs.
pub struct Resampler {
    buf: Vec<[f32; 2]>, // pending input frames; buf[0] is the frame before `pos`'s integer part
    pos: f64,           // read position in `buf`, always >= 1.0 once started
}

impl Default for Resampler {
    fn default() -> Self {
        Self::new()
    }
}

impl Resampler {
    pub fn new() -> Self {
        Resampler { buf: Vec::with_capacity(16384), pos: 1.0 }
    }

    pub fn reset(&mut self) {
        self.buf.clear();
        self.pos = 1.0;
    }

    pub fn push(&mut self, frames: &[[f32; 2]]) {
        if self.buf.is_empty() {
            // a silent frame in front, so the first real frame can be interpolated from both sides
            self.buf.push([0.0, 0.0]);
        }
        self.buf.extend_from_slice(frames);
    }

    /// Produce output frames into `out` with `step` input frames per output frame, as many as the input allows.
    /// Returns how many were written.
    pub fn process(&mut self, step: f64, out: &mut Vec<[f32; 2]>) -> usize {
        let start = out.len();
        // cubic needs buf[i-1], buf[i], buf[i+1], buf[i+2]
        while (self.pos as usize) + 2 < self.buf.len() {
            let i = self.pos as usize;
            let t = (self.pos - i as f64) as f32;
            let (a, b, c, d) = (self.buf[i - 1], self.buf[i], self.buf[i + 1], self.buf[i + 2]);
            let mut f = [0.0f32; 2];
            for ch in 0..2 {
                f[ch] = hermite(a[ch], b[ch], c[ch], d[ch], t);
            }
            out.push(f);
            self.pos += step;
        }
        // drop what is no longer needed, keep one frame before the read position
        let keep_from = (self.pos as usize).saturating_sub(1);
        if keep_from > 0 {
            self.buf.drain(..keep_from);
            self.pos -= keep_from as f64;
        }
        out.len() - start
    }

    /// Input frames waiting (not yet turned into output).
    pub fn pending(&self) -> usize {
        self.buf.len().saturating_sub(self.pos as usize + 1)
    }
}

#[inline]
fn hermite(xm1: f32, x0: f32, x1: f32, x2: f32, t: f32) -> f32 {
    let c = (x1 - xm1) * 0.5;
    let v = x0 - x1;
    let w = c + v;
    let a = w + v + (x2 - x0) * 0.5;
    let b = w + a;
    ((a * t - b) * t + c) * t + x0
}

/// Keeps the ring buffer near its target fill by nudging the resampling step.
/// The fill is smoothed (about half a second), the correction is proportional and capped, so the pitch never
/// moves more than `MAX_CORRECTION` (0.3 % = 5 cents, unnoticeable on browser audio; real drift is ~0.01 %).
pub struct DriftControl {
    pub target: f64,   // frames
    smoothed: f64,
    pub correction: f64, // relative, + = read the input faster
}

pub const MAX_CORRECTION: f64 = 0.003;
const SMOOTHING: f64 = 0.02; // per update (updates every ~5 ms -> ~0.25 s time constant)
const GAIN: f64 = 0.01;      // 100 % too full -> +1 % (then capped)

impl DriftControl {
    pub fn new(target_frames: f64) -> Self {
        DriftControl { target: target_frames, smoothed: target_frames, correction: 0.0 }
    }

    pub fn reset(&mut self, fill: f64) {
        self.smoothed = fill;
        self.correction = 0.0;
    }

    /// Feed the current fill (frames in the ring); returns the step to use (input frames per output frame).
    pub fn update(&mut self, fill: f64, base_ratio: f64) -> f64 {
        self.smoothed += SMOOTHING * (fill - self.smoothed);
        let err = (self.smoothed - self.target) / self.target.max(1.0);
        self.correction = (err * GAIN).clamp(-MAX_CORRECTION, MAX_CORRECTION);
        base_ratio * (1.0 + self.correction)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn step_one_passes_signal_through_with_one_frame_delay() {
        let mut r = Resampler::new();
        let input: Vec<[f32; 2]> = (0..100).map(|i| [i as f32, -(i as f32)]).collect();
        r.push(&input);
        let mut out = Vec::new();
        r.process(1.0, &mut out);
        // buf = [0, 0, 1, 2, ...], pos starts at 1 -> first output is input[0]
        assert_eq!(out[0], [0.0, 0.0]);
        assert_eq!(out[10], [10.0, -10.0]);
        assert!(out.len() >= 97);
    }

    #[test]
    fn half_step_interpolates_a_ramp_exactly() {
        let mut r = Resampler::new();
        let input: Vec<[f32; 2]> = (0..50).map(|i| [i as f32, 0.0]).collect();
        r.push(&input);
        let mut out = Vec::new();
        r.process(0.5, &mut out);
        for k in 4..80 {
            assert!((out[k][0] - k as f32 * 0.5).abs() < 1e-4, "k={k} got {}", out[k][0]);
        }
    }

    #[test]
    fn chunked_input_gives_same_output_as_one_block() {
        let input: Vec<[f32; 2]> = (0..1000).map(|i| [((i as f32) * 0.05).sin(), ((i as f32) * 0.03).cos()]).collect();
        let step = 1.0013;
        let mut a = Resampler::new();
        let mut out_a = Vec::new();
        a.push(&input);
        a.process(step, &mut out_a);
        let mut b = Resampler::new();
        let mut out_b = Vec::new();
        for chunk in input.chunks(37) {
            b.push(chunk);
            b.process(step, &mut out_b);
        }
        assert_eq!(out_a.len(), out_b.len());
        for (x, y) in out_a.iter().zip(&out_b) {
            assert!((x[0] - y[0]).abs() < 1e-6 && (x[1] - y[1]).abs() < 1e-6);
        }
    }

    #[test]
    fn output_count_follows_step() {
        let mut r = Resampler::new();
        let mut out = Vec::new();
        let block = vec![[0.1f32, 0.1]; 480];
        for _ in 0..100 {
            r.push(&block);
            r.process(1.002, &mut out);
        }
        let expected = 48000.0 / 1.002;
        assert!((out.len() as f64 - expected).abs() < 5.0, "{}", out.len());
        assert!(r.pending() < 5);
    }

    /// Simulated clocks: the capture device runs 0.02 % fast; the controller must keep the ring near the target
    /// and never touch the cap.
    #[test]
    fn drift_control_holds_the_cushion() {
        let target = 2880.0; // 60 ms at 48 kHz
        let mut dc = DriftControl::new(target);
        let mut r = Resampler::new();
        let mut fill = target;
        let mut out = Vec::new();
        let mut produced_in = 0.0f64;
        let capture_rate = 48000.0 * 1.0002;
        let mut worst = 0.0f64;
        for tick in 0..200_000 {
            // 5 ms ticks: capture delivers its frames, the host consumes 240
            produced_in += capture_rate * 0.005;
            let n = produced_in as usize;
            produced_in -= n as f64;
            r.push(&vec![[0.0, 0.0]; n]);
            let step = dc.update(fill, 1.0);
            out.clear();
            fill += r.process(step, &mut out) as f64;
            fill -= 240.0;
            if tick > 20_000 {
                worst = worst.max((fill - target).abs());
            }
        }
        assert!(worst < target * 0.1, "fill strays {worst} frames");
        assert!(dc.correction.abs() < MAX_CORRECTION * 0.5, "correction {}", dc.correction);
    }
}
