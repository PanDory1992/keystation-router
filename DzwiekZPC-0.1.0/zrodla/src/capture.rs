//! The capture thread: opens a Windows audio device in SHARED mode (WASAPI), never touching ASIO, resamples it to
//! the host rate with drift control and pushes stereo frames into the lock-free ring the audio thread reads.
//!
//! Sources:
//!   - a capture endpoint, e.g. "CABLE Output (VB-Audio Virtual Cable)" that Firefox plays into;
//!   - loopback of a render endpoint, e.g. the Realtek output, if Firefox plays there.
//! Nothing here runs on the host's audio thread: a slow device or an error only empties the ring (counted as gaps).

use crate::dsp::{DriftControl, Resampler};
use crate::shared::{DeviceInfo, Shared, State};
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::{Duration, Instant};

pub struct Worker {
    handle: Option<std::thread::JoinHandle<()>>,
    shared: Arc<Shared>,
}

impl Worker {
    pub fn start(shared: Arc<Shared>, producer: rtrb::Producer<f32>, host_rate: u32) -> Self {
        shared.stop.store(false, Ordering::SeqCst);
        let s = shared.clone();
        let handle = std::thread::Builder::new()
            .name("dzwiek-z-pc capture".into())
            .spawn(move || run(s, producer, host_rate))
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

#[cfg(not(windows))]
fn run(shared: Arc<Shared>, _producer: rtrb::Producer<f32>, _host_rate: u32) {
    shared.set_state(State::Error, "tylko Windows");
}

#[cfg(windows)]
fn run(shared: Arc<Shared>, mut producer: rtrb::Producer<f32>, host_rate: u32) {
    let _ = wasapi::initialize_mta();
    let mut last_list = Instant::now() - Duration::from_secs(10);
    while !shared.stop.load(Ordering::SeqCst) {
        if last_list.elapsed() > Duration::from_secs(3) {
            if let Ok(list) = list_devices() {
                *shared.devices.lock().unwrap() = list;
            }
            last_list = Instant::now();
        }
        let wanted = pick_source(&shared);
        let Some(dev) = wanted else {
            shared.set_state(State::NoSource, "wybierz źródło");
            sleep_or_stop(&shared, Duration::from_millis(500));
            continue;
        };
        let generation = shared.generation.load(Ordering::SeqCst);
        match stream(&shared, &mut producer, host_rate, &dev, generation) {
            Ok(()) => {} // source changed or stop
            Err(e) => {
                shared.set_state(State::Error, &format!("{}: {e}", dev.name));
                sleep_or_stop(&shared, Duration::from_secs(2));
            }
        }
    }
    shared.set_state(State::Stopped, "");
}

fn sleep_or_stop(shared: &Shared, d: Duration) {
    let until = Instant::now() + d;
    while Instant::now() < until && !shared.stop.load(Ordering::SeqCst) {
        std::thread::sleep(Duration::from_millis(50));
    }
}

/// The chosen device, or by default the first "CABLE Output" capture device.
fn pick_source(shared: &Shared) -> Option<DeviceInfo> {
    let wanted = shared.wanted.lock().unwrap().clone();
    let list = shared.devices.lock().unwrap();
    if !wanted.is_empty() {
        return list.iter().find(|d| d.key() == wanted).cloned();
    }
    list.iter().find(|d| !d.loopback && d.name.to_lowercase().contains("cable output")).cloned()
}

#[cfg(windows)]
fn list_devices() -> Result<Vec<DeviceInfo>, Box<dyn std::error::Error>> {
    use wasapi::{DeviceEnumerator, Direction};
    let en = DeviceEnumerator::new()?;
    let mut out = Vec::new();
    for (dir, loopback) in [(Direction::Capture, false), (Direction::Render, true)] {
        let coll = en.get_device_collection(dir)?;
        for dev in &coll {
            let dev = dev?;
            out.push(DeviceInfo { id: dev.get_id()?, name: dev.get_friendlyname()?, loopback });
        }
    }
    Ok(out)
}

#[cfg(windows)]
fn stream(
    shared: &Shared,
    producer: &mut rtrb::Producer<f32>,
    host_rate: u32,
    info: &DeviceInfo,
    generation: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    use wasapi::{DeviceEnumerator, Direction, SampleType, StreamMode, WaveFormat};
    let en = DeviceEnumerator::new()?;
    let device = en.get_device(&info.id)?;
    let mut client = device.get_iaudioclient()?;
    // Float stereo at the host rate: Windows converts (AUTOCONVERTPCM), so the resampler only fixes the drift.
    let format = WaveFormat::new(32, 32, SampleType::Float, host_rate as usize, 2, None);
    let mode = StreamMode::PollingShared { autoconvert: true, buffer_duration_hns: 1_000_000 }; // 100 ms device buffer
    client.initialize_client(&format, Direction::Capture, mode, None)?;
    let capture = client.get_audiocaptureclient()?;
    client.start_stream()?;
    shared.set_state(State::Running, &info.name);

    let mut resampler = Resampler::new();
    let mut drift = DriftControl::new(shared.target_frames(host_rate));
    let mut raw = vec![0u8; 8 * 48_000]; // up to 1 s per packet
    let mut frames: Vec<[f32; 2]> = Vec::with_capacity(48_000);
    let mut out: Vec<[f32; 2]> = Vec::with_capacity(48_000);
    let mut last_data = Instant::now();
    let capacity = producer.buffer().capacity();
    let mut skipping = false;
    let mut last_list = Instant::now();

    let result = (|| -> Result<(), Box<dyn std::error::Error>> {
        loop {
            if shared.stop.load(Ordering::SeqCst) || shared.generation.load(Ordering::SeqCst) != generation {
                return Ok(());
            }
            frames.clear();
            while let Some(n) = capture.get_next_packet_size()? {
                if n == 0 {
                    break;
                }
                let bytes = n as usize * 8;
                if raw.len() < bytes {
                    raw.resize(bytes, 0);
                }
                let (got, _info) = capture.read_from_device(&mut raw[..bytes])?;
                for k in 0..got as usize {
                    let o = k * 8;
                    let l = f32::from_le_bytes([raw[o], raw[o + 1], raw[o + 2], raw[o + 3]]);
                    let r = f32::from_le_bytes([raw[o + 4], raw[o + 5], raw[o + 6], raw[o + 7]]);
                    frames.push([l, r]);
                }
            }
            let target = shared.target_frames(host_rate);
            drift.target = target;
            let fill = ((capacity - producer.slots()) / 2) as f64;
            if !frames.is_empty() {
                last_data = Instant::now();
            } else if info.loopback && last_data.elapsed() > Duration::from_millis(30) && fill < target * 0.5 {
                // loopback delivers nothing while nothing plays: keep the cushion with silence
                frames.resize((target * 0.25) as usize, [0.0, 0.0]);
            }
            if fill > target * 3.0 {
                // Studio One stopped reading for a while (project loading...): skip new input until the cushion
                // is back to normal, instead of staying that much late
                skipping = true;
            }
            if skipping {
                if fill <= target {
                    skipping = false;
                    resampler.reset();
                    drift.reset(fill);
                } else {
                    shared.dropped.fetch_add(frames.len() as u32, Ordering::Relaxed);
                    frames.clear();
                }
            }
            if !frames.is_empty() {
                resampler.push(&frames);
                let step = drift.update(fill, 1.0);
                out.clear();
                resampler.process(step, &mut out);
                let room = producer.slots() / 2;
                let n = out.len().min(room);
                if n < out.len() {
                    shared.dropped.fetch_add((out.len() - n) as u32, Ordering::Relaxed);
                }
                if let Ok(mut chunk) = producer.write_chunk_uninit(n * 2) {
                    let (a, b) = chunk.as_mut_slices();
                    let mut it = out[..n].iter().flat_map(|f| [f[0], f[1]]);
                    for s in a.iter_mut().chain(b.iter_mut()) {
                        s.write(it.next().unwrap_or(0.0));
                    }
                    unsafe { chunk.commit_all() };
                }
                shared.correction_ppm.store((drift.correction * 1e6) as i32, Ordering::Relaxed);
            }
            shared.fill_frames.store(fill as u32, Ordering::Relaxed);
            if last_list.elapsed() > Duration::from_secs(3) {
                if let Ok(list) = list_devices() {
                    *shared.devices.lock().unwrap() = list;
                }
                last_list = Instant::now();
            }
            std::thread::sleep(Duration::from_millis(4));
        }
    })();
    let _ = client.stop_stream();
    result
}
