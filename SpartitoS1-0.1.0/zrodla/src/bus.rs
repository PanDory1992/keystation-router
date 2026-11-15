//! HEAR: the note clicked on the staff, played on Miki's piano.
//!
//! The Max device played it through its own track. A VST3 instrument here is
//! silent, so the note goes to the router's UDP bus (udp_bus.py, 127.0.0.1:47800),
//! which plays it on channel 1 through the "Keystation Pedal Modes" port, like
//! Trener does. If the router is not running nothing happens.
//!
//! That port also feeds this track, so the note comes back as input: the core
//! drops a note that matches one sent here a moment ago (see Echo).

use std::net::UdpSocket;
use std::time::{Duration, Instant};

const BUS: &str = "127.0.0.1:47800";
const HELLO_EVERY: Duration = Duration::from_secs(4);
/// a note arriving this soon after we sent the same pitch is our own, coming back
pub const ECHO: Duration = Duration::from_millis(400);

pub struct Bus {
    sock: Option<UdpSocket>,
    hello: Option<Instant>,
    offs: Vec<(Instant, u8)>,
    pub sent: Vec<(u8, Instant)>,
}

impl Bus {
    pub fn new() -> Bus {
        Bus { sock: None, hello: None, offs: Vec::new(), sent: Vec::new() }
    }

    fn send(&mut self, msg: &str) {
        if self.sock.is_none() {
            self.sock = UdpSocket::bind("127.0.0.1:0").ok();
            if let Some(s) = &self.sock {
                let _ = s.set_nonblocking(true);
            }
        }
        if let Some(s) = &self.sock {
            let _ = s.send_to(msg.as_bytes(), BUS);
        }
    }

    pub fn play(&mut self, pitch: u8, vel: u8, ms: u32) {
        let now = Instant::now();
        if self.hello.map_or(true, |t| now - t > HELLO_EVERY) {
            self.send(r#"{"t":"hello","name":"spartito-s1"}"#);
            self.hello = Some(now);
        }
        let pitch = pitch.min(127);
        self.send(&format!(r#"{{"t":"play","midi":[[144,{},{}]]}}"#, pitch, vel.clamp(1, 127)));
        self.offs.push((now + Duration::from_millis(ms.max(30) as u64), pitch));
        self.sent.retain(|s| now - s.1 < ECHO);
        self.sent.push((pitch, now));
    }

    pub fn tick(&mut self) {
        let now = Instant::now();
        let due: Vec<u8> = self.offs.iter().filter(|o| o.0 <= now).map(|o| o.1).collect();
        if !due.is_empty() {
            self.offs.retain(|o| o.0 > now);
            let list: Vec<String> = due.iter().map(|p| format!("[128,{p},0]")).collect();
            self.send(&format!(r#"{{"t":"play","midi":[{}]}}"#, list.join(",")));
            for p in due {
                self.sent.push((p, now));
            }
        }
        // what the router sends back to a listener is not needed here
        if let Some(s) = &self.sock {
            let mut buf = [0u8; 2048];
            while s.recv_from(&mut buf).is_ok() {}
        }
    }

    /// True if `pitch` was just sent by us (it is the echo, not the player).
    pub fn is_echo(&self, pitch: u8) -> bool {
        let now = Instant::now();
        self.sent.iter().any(|s| s.0 == pitch && now - s.1 < ECHO)
    }
}

impl Drop for Bus {
    fn drop(&mut self) {
        if self.hello.is_some() {
            let offs: Vec<String> = self.offs.iter().map(|o| format!("[128,{},0]", o.1)).collect();
            if !offs.is_empty() {
                self.send(&format!(r#"{{"t":"play","midi":[{}]}}"#, offs.join(",")));
            }
            self.send(r#"{"t":"bye"}"#);
        }
    }
}
