//! State shared between the capture thread, the audio thread and the editor. Only atomics and short mutexes;
//! the audio thread touches nothing but atomics.

use std::sync::atomic::{AtomicBool, AtomicI32, AtomicU32, AtomicU8, Ordering};
use std::sync::Mutex;

#[derive(Clone, Debug, PartialEq)]
pub struct DeviceInfo {
    pub id: String,
    pub name: String,
    /// true = a playback device, captured by loopback (what plays there)
    pub loopback: bool,
}

impl DeviceInfo {
    /// What is saved with the project: the name (ids change when a driver is reinstalled).
    pub fn key(&self) -> String {
        format!("{}|{}", if self.loopback { "out" } else { "in" }, self.name)
    }
    pub fn label(&self) -> String {
        if self.loopback { format!("Z wyjścia: {}", self.name) } else { format!("Wejście: {}", self.name) }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum State {
    Stopped = 0,
    NoSource = 1,
    Running = 2,
    Error = 3,
}

pub struct Shared {
    pub stop: AtomicBool,
    pub generation: AtomicU32,
    pub wanted: Mutex<String>,
    pub devices: Mutex<Vec<DeviceInfo>>,
    pub state: AtomicU8,
    pub state_text: Mutex<String>,
    pub target_ms: AtomicU32,
    pub fill_frames: AtomicU32,
    pub correction_ppm: AtomicI32,
    pub gaps: AtomicU32,
    pub dropped: AtomicU32,
    pub host_rate: AtomicU32,
    pub peak_bits: AtomicU32,
}

impl Default for Shared {
    fn default() -> Self {
        Shared {
            stop: AtomicBool::new(false),
            generation: AtomicU32::new(0),
            wanted: Mutex::new(String::new()),
            devices: Mutex::new(Vec::new()),
            state: AtomicU8::new(State::Stopped as u8),
            state_text: Mutex::new(String::new()),
            target_ms: AtomicU32::new(60),
            fill_frames: AtomicU32::new(0),
            correction_ppm: AtomicI32::new(0),
            gaps: AtomicU32::new(0),
            dropped: AtomicU32::new(0),
            host_rate: AtomicU32::new(48_000),
            peak_bits: AtomicU32::new(0),
        }
    }
}

impl Shared {
    pub fn set_state(&self, s: State, text: &str) {
        self.state.store(s as u8, Ordering::SeqCst);
        *self.state_text.lock().unwrap() = text.to_owned();
    }
    pub fn state(&self) -> State {
        match self.state.load(Ordering::SeqCst) {
            1 => State::NoSource,
            2 => State::Running,
            3 => State::Error,
            _ => State::Stopped,
        }
    }
    pub fn target_frames(&self, rate: u32) -> f64 {
        self.target_ms.load(Ordering::Relaxed) as f64 * rate as f64 / 1000.0
    }
    pub fn choose(&self, key: &str) {
        *self.wanted.lock().unwrap() = key.to_owned();
        self.generation.fetch_add(1, Ordering::SeqCst);
    }
}
