//! Commands from the plugin to the router.
//!
//! The plugin writes `live-cmd.json` (atomically, via a .tmp file) next to the
//! router; the router picks it up within ~40 ms, applies it through the same
//! path as the physical buttons and deletes it. Format (versioned, all fields
//! optional, unknown fields ignored):
//!   {"v":1,"id":<unique>,"set":{"mode":"sostenuto","una_corda":true,
//!                                "touch":"heavy","ones":"ppp",
//!                                "half_pedal":true,"half_depth":80,"debounce":true,
//!                                "release_ms":120,"read_controls":true,
//!                                "fader":{"C3":"Bas Bus"}}}

use serde_json::{json, Map, Value};
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Debug)]
pub enum Command {
    PedalMode(&'static str),
    UnaCorda(bool),
    Touch(&'static str),
    Ones(&'static str),
    HalfPedal(bool),
    HalfDepth(u8),
    Debounce(bool),
    /// 0.4.0: how long the sustain pedal takes to fall when you let go (soft damper landing).
    ReleaseMs(u16),
    /// 0.7.0: for a few seconds the router only reads knob/fader positions (press SNAPSHOT on the keyboard).
    ReadControls,
    /// 16.11: fader C2..C8 -> a Studio One channel by name (None = unassigned).
    Fader(String, Option<String>),
    /// 0.10.0: the Mega's piano curve ("fortepian", "fortepian-pelny").
    MegaCurve(String),
    /// 0.10.0: high-resolution velocity (CC88 before each Mega note) on/off.
    MegaHires(bool),
}

impl Command {
    fn apply(&self, set: &mut Map<String, Value>) {
        match self {
            Command::PedalMode(m) => set.insert("mode".into(), json!(m)),
            Command::UnaCorda(on) => set.insert("una_corda".into(), json!(on)),
            Command::Touch(t) => set.insert("touch".into(), json!(t)),
            Command::Ones(o) => set.insert("ones".into(), json!(o)),
            Command::HalfPedal(on) => set.insert("half_pedal".into(), json!(on)),
            Command::HalfDepth(d) => set.insert("half_depth".into(), json!(d)),
            Command::Debounce(on) => set.insert("debounce".into(), json!(on)),
            Command::ReleaseMs(ms) => set.insert("release_ms".into(), json!(ms)),
            Command::ReadControls => set.insert("read_controls".into(), json!(true)),
            Command::Fader(f, ch) => set.insert("fader".into(), json!({ f.as_str(): ch })),
            Command::MegaCurve(c) => set.insert("mega_curve".into(), json!(c)),
            Command::MegaHires(on) => set.insert("mega_hires".into(), json!(on)),
        };
    }
}

pub fn send(dir: &PathBuf, command: &Command) -> std::io::Result<()> {
    let mut set = Map::new();
    command.apply(&mut set);
    let id = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_micros()).unwrap_or(0);
    let body = json!({"v": 1, "id": id.to_string(), "set": set});
    let tmp = dir.join("live-cmd.json.tmp");
    std::fs::write(&tmp, body.to_string())?;
    std::fs::rename(&tmp, dir.join("live-cmd.json"))
}
