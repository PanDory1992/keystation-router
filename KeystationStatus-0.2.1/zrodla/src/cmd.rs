//! Commands from the plugin to the router.
//!
//! The plugin writes `live-cmd.json` (atomically, via a .tmp file) next to the
//! router; the router picks it up within ~40 ms, applies it through the same
//! path as the physical buttons and deletes it. Format (versioned, all fields
//! optional, unknown fields ignored):
//!   {"v":1,"id":<unique>,"set":{"mode":"sostenuto","una_corda":true,
//!                                "touch":"heavy","ones":"ppp"}}

use serde_json::{json, Map, Value};
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Debug)]
pub enum Command {
    PedalMode(&'static str),
    UnaCorda(bool),
    Touch(&'static str),
    Ones(&'static str),
}

impl Command {
    fn apply(&self, set: &mut Map<String, Value>) {
        match self {
            Command::PedalMode(m) => set.insert("mode".into(), json!(m)),
            Command::UnaCorda(on) => set.insert("una_corda".into(), json!(on)),
            Command::Touch(t) => set.insert("touch".into(), json!(t)),
            Command::Ones(o) => set.insert("ones".into(), json!(o)),
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
