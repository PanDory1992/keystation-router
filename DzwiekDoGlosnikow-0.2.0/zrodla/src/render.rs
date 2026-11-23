//! Wątek głośników: otwiera wybrane wyjście Windows w trybie współdzielonym (WASAPI), nigdy przez ASIO.
//!
//! - wątek jest zarejestrowany w MMCSS jako „Pro Audio” (ten sam priorytet, co wątki audio Studio One),
//!   więc obciążony komputer nie spycha go na koniec kolejki;
//! - karta budzi wątek zdarzeniem co okres (bez odpytywania co 2 ms);
//! - jeśli sterownik pozwala (IAudioClient3), okres jest najkrótszy, jaki karta przyjmuje, zwykle 3–5 ms
//!   zamiast domyślnych 10 ms; inaczej zwykły tryb zdarzeń;
//! - po stronie karty trzymamy najwyżej dwa okresy dźwięku, reszta zapasu jest w kolejce wtyczki
//!   pod kontrolą regulatora (patrz engine.rs).
//!
//! Lista urządzeń jest odświeżana w osobnym krótkim wątku, żeby wyliczanie urządzeń nigdy nie zatrzymało
//! odtwarzania.

#[cfg(windows)]
use crate::engine::Engine;
use crate::shared::{default_device, DeviceInfo, Shared, State};
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::{Duration, Instant};

pub struct Worker {
    handle: Option<std::thread::JoinHandle<()>>,
    shared: Arc<Shared>,
}

impl Worker {
    pub fn start(shared: Arc<Shared>, consumer: rtrb::Consumer<f32>) -> Self {
        shared.stop.store(false, Ordering::SeqCst);
        let s = shared.clone();
        let handle = std::thread::Builder::new()
            .name("dzwiek-do-glosnikow".into())
            .spawn(move || run(s, consumer))
            .ok();
        Worker { handle, shared }
    }
}

impl Drop for Worker {
    fn drop(&mut self) {
        self.shared.stop.store(true, Ordering::SeqCst);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
    }
}

#[cfg_attr(not(windows), allow(dead_code))]
fn sleep_or_stop(shared: &Shared, d: Duration) {
    let until = Instant::now() + d;
    while Instant::now() < until && !shared.stop.load(Ordering::SeqCst) {
        std::thread::sleep(Duration::from_millis(20));
    }
}

/// Wybrane urządzenie, a bez wyboru wyjście karty płyty głównej (nigdy UM2).
#[cfg_attr(not(windows), allow(dead_code))]
pub fn pick_device(wanted: &str, list: &[DeviceInfo]) -> Option<DeviceInfo> {
    if !wanted.is_empty() {
        return list.iter().find(|d| d.key() == wanted).cloned();
    }
    default_device(list)
}

#[cfg(not(windows))]
fn run(shared: Arc<Shared>, _consumer: rtrb::Consumer<f32>) {
    shared.set_state(State::Error, "tylko Windows");
}

#[cfg(windows)]
fn run(shared: Arc<Shared>, mut consumer: rtrb::Consumer<f32>) {
    let _ = wasapi::initialize_mta();
    let mmcss = mmcss::Guard::pro_audio();
    shared.mmcss.store(mmcss.is_some(), Ordering::Relaxed);
    let mut lister: Option<std::thread::JoinHandle<()>> = None;
    let mut last_refresh = Instant::now();
    while !shared.stop.load(Ordering::SeqCst) {
        maybe_list(&shared, &mut lister);
        let wanted = shared.wanted.lock().map(|w| w.clone()).unwrap_or_default();
        let list = shared.devices.lock().map(|l| l.clone()).unwrap_or_default();
        let Some(dev) = pick_device(&wanted, &list) else {
            let text = if list.is_empty() {
                "szukam wyjść Windows…"
            } else if wanted.is_empty() {
                "wybierz głośniki z listy"
            } else {
                "wybranych głośników teraz nie ma (odłączone?), czekam"
            };
            shared.set_state(State::NoDevice, text);
            // urządzenie może wrócić (podłączenie, sterownik): lista od nowa co 3 s
            if last_refresh.elapsed() > Duration::from_secs(3) {
                shared.refresh.store(true, Ordering::SeqCst);
                last_refresh = Instant::now();
            }
            sleep_or_stop(&shared, Duration::from_millis(300));
            continue;
        };
        if dev.is_asio_interface() {
            shared.set_state(State::Error, "to UM2: trzyma go ASIO4ALL, wybierz inne wyjście");
            sleep_or_stop(&shared, Duration::from_millis(500));
            continue;
        }
        let generation = shared.generation.load(Ordering::SeqCst);
        if let Err(e) = stream(&shared, &mut consumer, &dev, generation, &mut lister) {
            shared.set_state(State::Error, &format!("{}: {e}", dev.name));
            shared.refresh.store(true, Ordering::SeqCst);
            sleep_or_stop(&shared, Duration::from_secs(1));
        }
    }
    if let Some(h) = lister.take() {
        let _ = h.join();
    }
    shared.set_state(State::Stopped, "");
    drop(mmcss);
}

/// Odświeżenie listy w osobnym wątku (na żądanie okna albo po błędzie).
#[cfg(windows)]
fn maybe_list(shared: &Arc<Shared>, lister: &mut Option<std::thread::JoinHandle<()>>) {
    if lister.as_ref().is_some_and(|h| h.is_finished()) {
        if let Some(h) = lister.take() {
            let _ = h.join();
        }
    }
    if lister.is_none() && shared.refresh.swap(false, Ordering::SeqCst) {
        let s = shared.clone();
        *lister = std::thread::Builder::new()
            .name("dzwiek-do-glosnikow lista".into())
            .spawn(move || {
                let _ = wasapi::initialize_mta();
                if let Ok(list) = list_devices() {
                    if let Ok(mut l) = s.devices.lock() {
                        *l = list;
                    }
                }
                wasapi::deinitialize();
            })
            .ok();
    }
}

#[cfg(windows)]
fn list_devices() -> Result<Vec<DeviceInfo>, Box<dyn std::error::Error>> {
    use wasapi::{DeviceEnumerator, Direction};
    let en = DeviceEnumerator::new()?;
    let mut out = Vec::new();
    for dev in &en.get_device_collection(Direction::Render)? {
        let dev = dev?;
        out.push(DeviceInfo { id: dev.get_id()?, name: dev.get_friendlyname()? });
    }
    Ok(out)
}

#[cfg(windows)]
fn stream(
    shared: &Arc<Shared>,
    consumer: &mut rtrb::Consumer<f32>,
    info: &DeviceInfo,
    generation: u32,
    lister: &mut Option<std::thread::JoinHandle<()>>,
) -> Result<(), Box<dyn std::error::Error>> {
    use wasapi::{DeviceEnumerator, Direction, SampleType, StreamMode, TimingMode, WaveFormat};

    let en = DeviceEnumerator::new()?;
    let device = en.get_device(&info.id)?;
    let mut client = device.get_iaudioclient()?;
    let mix = client.get_mixformat()?;
    let dev_rate = mix.get_samplespersec();
    let mix_float = mix.get_bitspersample() == 32 && matches!(mix.get_subformat(), Ok(SampleType::Float));

    // 1. Najkrótszy okres przez IAudioClient3 (format karty, bez konwersji Windows).
    let mut low_latency = false;
    let mut channels = mix.get_nchannels() as usize;
    let mut period = 0u32;
    if mix_float {
        if let Ok(p) = client.get_shared_mode_engine_period(&mix) {
            if p.min > 0 && client.initialize_shared_audio_stream(&mix, TimingMode::Events, p.min).is_ok() {
                low_latency = true;
                period = p.min;
            }
        }
    }
    // 2. Inaczej zwykły tryb zdarzeń z okresem domyślnym (10 ms); świeży klient, bo nieudana próba go zużywa.
    if !low_latency {
        client = device.get_iaudioclient()?;
        let (def_hns, _min_hns) = client.get_device_period()?;
        let (fmt, autoconvert) = if mix_float {
            (mix.clone(), false)
        } else {
            channels = 2;
            (WaveFormat::new(32, 32, SampleType::Float, dev_rate as usize, 2, None), true)
        };
        client.initialize_client(&fmt, Direction::Render, StreamMode::EventsShared { autoconvert, buffer_duration_hns: 0 }, None)?;
        period = ((def_hns as f64 * dev_rate as f64 / 1e7).round() as u32).max(32);
    }
    let buffer_frames = client.get_buffer_size()?;
    let event = client.set_get_eventhandle()?;
    let render = client.get_audiorenderclient()?;
    if let Ok(session) = client.get_audiosessioncontrol() {
        let _ = session.set_display_name("Studio One: Dźwięk do Głośników");
    }
    let stream_latency_s = client.get_stream_latency().unwrap_or(0) as f64 / 1e7;

    let host_rate = shared.host_rate.load(Ordering::Relaxed).max(1) as f64;
    let mut engine = Engine::new(host_rate, dev_rate as f64, period as usize, channels)?;
    let chunk = engine.chunk();
    let mut out = vec![0.0f32; chunk * channels];
    let mut bytes: Vec<u8> = Vec::with_capacity(out.len() * 4);

    shared.dev_rate.store(dev_rate, Ordering::Relaxed);
    shared.dev_channels.store(channels as u32, Ordering::Relaxed);
    shared.period_frames.store(period, Ordering::Relaxed);
    shared.low_latency.store(low_latency, Ordering::Relaxed);

    // start: jeden okres ciszy, żeby karta miała co grać do pierwszego zdarzenia
    let silence = vec![0u8; chunk * channels * 4];
    render.write_to_device(&silence, None)?;
    client.start_stream()?;
    shared.set_state(State::Running, &info.name);

    let mut base = (0u32, 0u32);
    let result = (|| -> Result<(), Box<dyn std::error::Error>> {
        loop {
            if shared.stop.load(Ordering::SeqCst) || shared.generation.load(Ordering::SeqCst) != generation {
                return Ok(());
            }
            maybe_list(shared, lister);
            if event.wait_for_event(200).is_err() {
                continue; // brak zdarzenia: karta stoi (np. Windows ją uśpił); sprawdzamy stop i czekamy dalej
            }
            if shared.tone.swap(false, Ordering::SeqCst) {
                engine.start_tone();
            }
            let cushion_s = shared.cushion_us.load(Ordering::Relaxed) as f64 / 1e6;
            // po stronie karty najwyżej dwa okresy; po zacięciu dopełniamy do dwóch od razu
            let mut padding = client.get_current_padding()? as usize;
            while padding + chunk <= (2 * chunk).min(buffer_frames as usize) {
                let produced = shared.produced.load(Ordering::Acquire);
                engine.render(consumer, produced, cushion_s, &mut out);
                bytes.clear();
                for s in &out {
                    bytes.extend_from_slice(&s.to_le_bytes());
                }
                render.write_to_device(&bytes, None)?;
                padding += chunk;
            }
            let st = &engine.stats;
            shared.cushion_now_us.store((st.target_s * 1e6) as u32, Ordering::Relaxed);
            shared.plugin_latency_us.store((st.latency_s * 1e6) as u32, Ordering::Relaxed);
            let dev_lat = padding as f64 / dev_rate as f64 + stream_latency_s;
            shared.device_latency_us.store((dev_lat * 1e6) as u32, Ordering::Relaxed);
            shared.correction_ppm.store((st.correction * 1e6).round() as i32, Ordering::Relaxed);
            if shared.reset.swap(false, Ordering::SeqCst) {
                base = (st.gaps, st.skips);
            }
            shared.gaps.store(st.gaps - base.0, Ordering::Relaxed);
            shared.skips.store(st.skips - base.1, Ordering::Relaxed);
            shared.idle.store(st.idle, Ordering::Relaxed);
        }
    })();
    let _ = client.stop_stream();
    result
}

/// Rejestracja wątku w MMCSS („Pro Audio”) i powrót przy końcu.
#[cfg(windows)]
mod mmcss {
    use windows::core::w;
    use windows::Win32::Foundation::HANDLE;
    use windows::Win32::System::Threading::{AvRevertMmThreadCharacteristics, AvSetMmThreadCharacteristicsW};

    pub struct Guard(HANDLE);

    impl Guard {
        pub fn pro_audio() -> Option<Guard> {
            let mut index = 0u32;
            unsafe { AvSetMmThreadCharacteristicsW(w!("Pro Audio"), &mut index) }.ok().map(Guard)
        }
    }

    impl Drop for Guard {
        fn drop(&mut self) {
            unsafe {
                let _ = AvRevertMmThreadCharacteristics(self.0);
            }
        }
    }
}
