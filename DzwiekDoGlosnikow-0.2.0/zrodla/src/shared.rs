//! Stan wspólny dla wątku Studio One (audio), wątku głośników i okna. Wątek audio dotyka tylko atomików.

use std::sync::atomic::{AtomicBool, AtomicI32, AtomicU32, AtomicU64, AtomicU8, Ordering};
use std::sync::Mutex;

#[derive(Clone, Debug, PartialEq)]
pub struct DeviceInfo {
    pub id: String,
    pub name: String,
}

impl DeviceInfo {
    /// Zapisywane w piosence: nazwa (identyfikator zmienia się po przeinstalowaniu sterownika).
    pub fn key(&self) -> String {
        format!("out|{}", self.name)
    }
    /// UM2 trzyma ASIO4ALL na wyłączność; wysyłka do niego przez Windows i tak by nie ruszyła.
    pub fn is_asio_interface(&self) -> bool {
        let n = self.name.to_lowercase();
        n.contains("usb audio codec") || n.contains("um2") || n.contains("u-phoria")
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum State {
    Stopped = 0,
    NoDevice = 1,
    Running = 2,
    Error = 3,
}

pub struct Shared {
    pub stop: AtomicBool,
    pub generation: AtomicU32,
    pub wanted: Mutex<String>,
    pub devices: Mutex<Vec<DeviceInfo>>,
    pub refresh: AtomicBool,
    pub tone: AtomicBool,
    pub reset: AtomicBool,
    pub state: AtomicU8,
    pub state_text: Mutex<String>,
    /// Ramki włożone przez Studio One od startu (wątek głośników rozpoznaje po nim ciszę Studio One).
    pub produced: AtomicU64,
    pub host_rate: AtomicU32,
    /// Ustawienia przekazywane z wtyczki do wątku głośników.
    pub cushion_us: AtomicU32,
    // statystyki (wątek głośników -> okno)
    pub dev_rate: AtomicU32,
    pub dev_channels: AtomicU32,
    pub period_frames: AtomicU32,
    pub low_latency: AtomicBool,
    pub mmcss: AtomicBool,
    pub cushion_now_us: AtomicU32,
    pub plugin_latency_us: AtomicU32,
    pub device_latency_us: AtomicU32,
    pub correction_ppm: AtomicI32,
    pub gaps: AtomicU32,
    pub skips: AtomicU32,
    pub dropped: AtomicU32,
    pub idle: AtomicBool,
    pub peak_bits: AtomicU32,
}

impl Default for Shared {
    fn default() -> Self {
        Shared {
            stop: AtomicBool::new(false),
            generation: AtomicU32::new(0),
            wanted: Mutex::new(String::new()),
            devices: Mutex::new(Vec::new()),
            refresh: AtomicBool::new(true),
            tone: AtomicBool::new(false),
            reset: AtomicBool::new(false),
            state: AtomicU8::new(State::Stopped as u8),
            state_text: Mutex::new(String::new()),
            produced: AtomicU64::new(0),
            host_rate: AtomicU32::new(44_100),
            cushion_us: AtomicU32::new(0),
            dev_rate: AtomicU32::new(0),
            dev_channels: AtomicU32::new(0),
            period_frames: AtomicU32::new(0),
            low_latency: AtomicBool::new(false),
            mmcss: AtomicBool::new(false),
            cushion_now_us: AtomicU32::new(0),
            plugin_latency_us: AtomicU32::new(0),
            device_latency_us: AtomicU32::new(0),
            correction_ppm: AtomicI32::new(0),
            gaps: AtomicU32::new(0),
            skips: AtomicU32::new(0),
            dropped: AtomicU32::new(0),
            idle: AtomicBool::new(false),
            peak_bits: AtomicU32::new(0),
        }
    }
}

impl Shared {
    pub fn set_state(&self, s: State, text: &str) {
        self.state.store(s as u8, Ordering::SeqCst);
        if let Ok(mut t) = self.state_text.lock() {
            *t = text.to_owned();
        }
    }
    pub fn state(&self) -> State {
        match self.state.load(Ordering::SeqCst) {
            1 => State::NoDevice,
            2 => State::Running,
            3 => State::Error,
            _ => State::Stopped,
        }
    }
    pub fn choose(&self, key: &str) {
        if let Ok(mut w) = self.wanted.lock() {
            *w = key.to_owned();
        }
        self.generation.fetch_add(1, Ordering::SeqCst);
    }
    pub fn reset_counters(&self) {
        self.reset.store(true, Ordering::SeqCst);
        self.gaps.store(0, Ordering::Relaxed);
        self.skips.store(0, Ordering::Relaxed);
        self.dropped.store(0, Ordering::Relaxed);
    }
}

/// Domyślne głośniki, gdy nic nie wybrano: analogowe wyjście karty płyty głównej (u Mikiego Geniusy),
/// nigdy UM2. Pierwsze pasujące według kolejności nazw.
pub fn default_device(list: &[DeviceInfo]) -> Option<DeviceInfo> {
    let prefs = ["high definition audio device", "realtek", "głośniki", "speakers"];
    for p in prefs {
        if let Some(d) = list.iter().find(|d| !d.is_asio_interface() && d.name.to_lowercase().contains(p)) {
            return Some(d.clone());
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn d(name: &str) -> DeviceInfo {
        DeviceInfo { id: name.into(), name: name.into() }
    }

    #[test]
    fn default_device_is_the_onboard_output_and_never_the_um2() {
        let list = vec![d("Speakers (USB Audio CODEC)"), d("CABLE Input (VB-Audio Virtual Cable)"), d("Speakers (High Definition Audio Device)")];
        assert_eq!(default_device(&list).unwrap().name, "Speakers (High Definition Audio Device)");
        let only_um2 = vec![d("Głośniki (USB Audio CODEC)")];
        assert!(default_device(&only_um2).is_none());
        let polish = vec![d("Głośniki (Realtek(R) Audio)")];
        assert_eq!(default_device(&polish).unwrap().name, "Głośniki (Realtek(R) Audio)");
    }
}
