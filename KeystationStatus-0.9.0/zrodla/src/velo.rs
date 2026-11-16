//! 0.8.0: what you play, as it leaves the router (the velocity the instrument really gets).
//!
//! A small thread joins the router's UDP bus (udp_bus.py, 127.0.0.1:47800) and keeps:
//!   - the notes now visible as columns: x = what the key measured (raw), height = what
//!     the router sent (vel), so a column ends on the curve of the touch in use;
//!   - the last HISTORY velocities, for the distribution view.
//! A column fades out in 2 s. A note held by the sustain pedal (or the key) fades as long
//! as a real piano string would sound (`sound_time`); when the dampers fall it goes in 0.3 s.

use serde_json::Value;
use std::collections::VecDeque;
use std::net::UdpSocket;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub const FADE_S: f64 = 2.0;
pub const DAMP_S: f64 = 0.3;
pub const HISTORY: usize = 400;

#[derive(Clone, Debug, PartialEq)]
pub struct Hit {
    pub note: u8,
    pub raw: u8,
    pub vel: u8,
    pub t_on: f64,
    pub held: bool,
    pub sustained: bool,
    pub end: f64,
}

impl Hit {
    /// 1.0 at the attack, 0.0 at `end`.
    pub fn alpha(&self, now: f64) -> f32 {
        let span = (self.end - self.t_on).max(1e-3);
        ((self.end - now) / span).clamp(0.0, 1.0) as f32
    }
}

/// How long a piano note stays audible: long in the bass, short in the treble, longer when loud.
/// T60 of a grand roughly 40 s at A0 falling to ~1.6 s at C8; a soft note drops below hearing sooner.
pub fn sound_time(note: u8, vel: u8) -> f64 {
    let t60 = 40.0 * (-0.037 * (note as f64 - 21.0)).exp();
    (t60 * (0.35 + 0.65 * vel as f64 / 127.0)).clamp(FADE_S, 30.0)
}

#[derive(Default, Debug)]
pub struct Velo {
    pub hits: Vec<Hit>,
    pub history: VecDeque<u8>,
    pub pedal_down: bool,
    /// a sustain pedal event came in: there is a pedal in A37
    pub pedal_seen: bool,
    /// time of the last message from the bus (0 = never)
    pub heard: f64,
}

impl Velo {
    pub fn note_on(&mut self, note: u8, raw: u8, vel: u8, now: f64) {
        for h in self.hits.iter_mut().filter(|h| h.note == note && h.held) {
            h.held = false;
            h.end = h.end.min(now + DAMP_S);          // the same key again: the old sound is cut
        }
        let sustained = self.pedal_down;
        let end = now + if sustained { sound_time(note, vel) } else { FADE_S };
        self.hits.push(Hit { note, raw, vel, t_on: now, held: true, sustained, end });
        self.history.push_back(vel);
        while self.history.len() > HISTORY {
            self.history.pop_front();
        }
    }

    pub fn note_off(&mut self, note: u8, _now: f64) {
        let pedal = self.pedal_down;
        for h in self.hits.iter_mut().filter(|h| h.note == note && h.held) {
            h.held = false;
            if pedal && !h.sustained {
                h.sustained = true;
                h.end = h.end.max(h.t_on + sound_time(h.note, h.vel));
            }
        }
    }

    pub fn pedal(&mut self, down: bool, now: f64) {
        self.pedal_seen = true;
        if down && !self.pedal_down {
            for h in self.hits.iter_mut().filter(|h| h.held && !h.sustained) {
                h.sustained = true;
                h.end = h.end.max(h.t_on + sound_time(h.note, h.vel));
            }
        }
        if !down && self.pedal_down {
            for h in self.hits.iter_mut().filter(|h| h.sustained && !h.held) {
                h.sustained = false;
                h.end = h.end.min(now + DAMP_S);
            }
        }
        self.pedal_down = down;
    }

    pub fn prune(&mut self, now: f64) {
        self.hits.retain(|h| h.end > now);
    }

    /// One bus message (JSON). Only notes played on the keyboard ("src": "keys") count.
    pub fn feed(&mut self, msg: &Value, now: f64) {
        self.heard = now;
        match msg["t"].as_str() {
            Some("note") if msg["src"].as_str().unwrap_or("keys") == "keys" => {
                let n = |k: &str| msg[k].as_u64().unwrap_or(0).min(127) as u8;
                if msg["on"].as_bool().unwrap_or(false) && n("vel") > 0 {
                    self.note_on(n("note"), n("raw"), n("vel"), now);
                } else {
                    self.note_off(n("note"), now);
                }
            }
            Some("pedal") if matches!(msg["cc"].as_u64(), Some(64) | Some(66)) => {
                self.pedal(msg["value"].as_u64().unwrap_or(0) >= 64, now);
            }
            _ => {}
        }
    }
}

/// The bus listener: lives while the editor is open (dropping it says goodbye to the router).
pub struct Listener {
    pub velo: Arc<Mutex<Velo>>,
    stop: Arc<AtomicBool>,
}

impl Listener {
    pub fn start() -> Listener {
        let velo = Arc::new(Mutex::new(Velo::default()));
        let stop = Arc::new(AtomicBool::new(false));
        let (v, s) = (velo.clone(), stop.clone());
        std::thread::spawn(move || {
            let Ok(sock) = UdpSocket::bind("127.0.0.1:0") else { return };
            let _ = sock.set_read_timeout(Some(Duration::from_millis(400)));
            let bus = "127.0.0.1:47800";
            let mut hello = Instant::now() - Duration::from_secs(10);
            let mut buf = [0u8; 8192];
            while !s.load(Ordering::Relaxed) {
                if hello.elapsed() > Duration::from_secs(4) {
                    let _ = sock.send_to(br#"{"t":"hello","name":"keystation-status"}"#, bus);
                    hello = Instant::now();
                }
                if let Ok((n, _)) = sock.recv_from(&mut buf) {
                    if let Ok(msg) = serde_json::from_slice::<Value>(&buf[..n]) {
                        if let Ok(mut g) = v.lock() {
                            g.feed(&msg, crate::live::now_unix());
                        }
                    }
                }
            }
            let _ = sock.send_to(br#"{"t":"bye"}"#, bus);
        });
        Listener { velo, stop }
    }
}

impl Drop for Listener {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
    }
}

/// The router's curve for a touch: (white keys, black keys), 128 values each.
pub struct Curves {
    touch: String,
    stamp: Option<std::time::SystemTime>,
    pub white: Vec<u8>,
    pub black: Vec<u8>,
}

impl Default for Curves {
    fn default() -> Self {
        Curves { touch: String::new(), stamp: None, white: Vec::new(), black: Vec::new() }
    }
}

impl Curves {
    /// Reads velocity-map.<touch>.json (or velocity-map.json) when the touch or the file changed.
    pub fn update(&mut self, dir: &Path, touch: Option<&str>) {
        let name = touch.unwrap_or("");
        let mut path = dir.join(format!("velocity-map.{name}.json"));
        if name.is_empty() || !path.exists() {
            path = dir.join("velocity-map.json");
        }
        let stamp = std::fs::metadata(&path).and_then(|m| m.modified()).ok();
        if self.touch == name && self.stamp == stamp && !self.white.is_empty() {
            return;
        }
        self.touch = name.to_owned();
        self.stamp = stamp;
        let v: Value = std::fs::read_to_string(&path).ok().and_then(|t| serde_json::from_str(&t).ok()).unwrap_or(Value::Null);
        let arr = |k: &str| -> Vec<u8> {
            v[k].as_array().map(|a| a.iter().map(|x| x.as_u64().unwrap_or(0).min(127) as u8).collect()).unwrap_or_default()
        };
        self.white = arr("white");
        self.black = arr("black");
        if self.white.len() != 128 {
            self.white = (0..128u8).collect();                // no file: show the straight line
        }
        if self.black.len() != 128 {
            self.black = self.white.clone();
        }
    }
}

/// Distribution of velocities in `bins` equal steps over 1..127.
pub fn histogram(history: &VecDeque<u8>, bins: usize) -> Vec<u32> {
    let mut h = vec![0u32; bins];
    for &v in history {
        let i = ((v.max(1) as usize - 1) * bins / 127).min(bins - 1);
        h[i] += 1;
    }
    h
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn plain_notes_fade_in_two_seconds_and_history_is_kept() {
        let mut v = Velo::default();
        v.feed(&json!({"t":"note","on":true,"note":60,"raw":90,"vel":80,"src":"keys"}), 10.0);
        v.feed(&json!({"t":"note","on":true,"note":62,"raw":90,"vel":70,"src":"trener"}), 10.0);
        v.feed(&json!({"t":"note","on":false,"note":60,"raw":0,"vel":0,"src":"keys"}), 10.5);
        assert_eq!(v.hits.len(), 1);
        assert_eq!(v.hits[0].end, 12.0);
        assert!((v.hits[0].alpha(11.0) - 0.5).abs() < 1e-6);
        v.prune(12.1);
        assert!(v.hits.is_empty());
        assert_eq!(v.history, [80]);
    }

    #[test]
    fn the_pedal_keeps_notes_sounding_and_the_dampers_cut_them() {
        let mut v = Velo::default();
        v.note_on(36, 100, 100, 0.0);                                  // a low C, loud
        v.feed(&json!({"t":"pedal","pedal":"sustain","cc":64,"value":127}), 0.2);
        v.note_off(36, 0.5);
        let long = sound_time(36, 100);
        assert!(long > 15.0, "{long}");
        assert_eq!(v.hits[0].end, long);
        v.note_on(96, 60, 60, 1.0);                                    // a high soft note under the pedal
        assert!(v.hits[1].sustained && v.hits[1].end - 1.0 < 4.0);
        v.feed(&json!({"t":"pedal","pedal":"sustain","cc":64,"value":0}), 3.0);
        assert!((v.hits[0].end - 3.3).abs() < 1e-9);                   // released key: dampers fall
        assert!(v.hits[1].held && (v.hits[1].end - 3.0).abs() < 1e-9);   // still held: its own (short) sound, not cut
        assert!(v.pedal_seen);
    }

    #[test]
    fn histogram_and_sound_time() {
        let h: VecDeque<u8> = [1, 2, 64, 127, 127].into_iter().collect();
        assert_eq!(histogram(&h, 4), vec![2, 1, 0, 2]);
        assert!(sound_time(21, 127) > sound_time(60, 127));
        assert!(sound_time(60, 127) > sound_time(60, 20));
        assert_eq!(sound_time(108, 10), FADE_S);
    }
}
