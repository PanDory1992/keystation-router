//! Reading the router's live state.
//!
//! The router (pedal_router.py) writes `live.json` next to itself on every change
//! and once a second. The format is versioned (`"v"`) and every field is optional:
//! unknown fields are ignored and missing ones fall back to defaults, so new
//! fields can be added on either side without breaking the other.
//!
//! If `live.json` does not exist yet (older router), `status.json` is read
//! instead: it carries the same state, only refreshed once a second.

use serde_json::Value;
use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

/// After this long without a fresh timestamp the state is shown as stale.
pub const STALE_AFTER_S: f64 = 3.5;
/// How often the editor re-reads the file.
pub const POLL_EVERY: Duration = Duration::from_millis(80);

#[derive(Clone, Debug, Default)]
pub struct LastNote {
    pub note: u8,
    pub raw: u8,
    pub out: u8,
}

#[derive(Clone, Debug, Default)]
pub struct LiveState {
    pub version: u64,
    pub connected: Option<bool>,
    pub pedal_mode: Option<String>,
    pub pedal_value: u8,
    pub una_corda: Option<bool>,
    pub touch: Option<String>,
    pub ones: Option<String>,
    pub last: Option<LastNote>,
    /// Unix time of the router's last write.
    pub updated: f64,
    /// Which file the state came from ("live.json" or "status.json").
    pub source: &'static str,
}

impl LiveState {
    pub fn is_fresh(&self) -> bool {
        self.updated > 0.0 && now_unix() - self.updated < STALE_AFTER_S
    }

    fn from_json(v: &Value, source: &'static str) -> Self {
        let s = |k: &str| v.get(k).and_then(Value::as_str).map(str::to_owned);
        let b = |k: &str| v.get(k).and_then(Value::as_bool);
        let n = |k: &str| v.get(k).and_then(Value::as_f64);
        let last = v.get("last").and_then(|l| {
            Some(LastNote {
                note: l.get("note")?.as_u64()? as u8,
                raw: l.get("raw")?.as_u64()? as u8,
                out: l.get("out")?.as_u64()? as u8,
            })
        });
        LiveState {
            version: v.get("v").and_then(Value::as_u64).unwrap_or(0),
            connected: b("connected"),
            pedal_mode: s("mode"),
            pedal_value: n("pedal").unwrap_or(0.0).clamp(0.0, 127.0) as u8,
            una_corda: b("una_corda"),
            touch: s("touch").or_else(|| s("touch_mode")),
            ones: s("ones").or_else(|| s("ones_mode")),
            last,
            updated: n("updated").unwrap_or(0.0),
            source,
        }
    }
}

fn now_unix() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

fn router_dir() -> PathBuf {
    let base = std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_default();
    base.join("CodexPedalModes")
}

fn read_json(path: &PathBuf) -> Option<Value> {
    // The router replaces the file atomically; a read that races with it simply
    // fails and the next poll picks it up.
    let text = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(text.trim_start_matches('\u{feff}')).ok()
}

/// Polls the router files at most every `POLL_EVERY` and keeps the last good state.
pub struct LiveReader {
    dir: PathBuf,
    last_poll: Option<Instant>,
    pub state: LiveState,
}

impl Default for LiveReader {
    fn default() -> Self {
        LiveReader { dir: router_dir(), last_poll: None, state: LiveState::default() }
    }
}

impl LiveReader {
    pub fn poll(&mut self) {
        if self.last_poll.map_or(false, |t| t.elapsed() < POLL_EVERY) {
            return;
        }
        self.last_poll = Some(Instant::now());
        let live = self.dir.join("live.json");
        if let Some(v) = read_json(&live) {
            self.state = LiveState::from_json(&v, "live.json");
            return;
        }
        if !live.exists() {
            if let Some(v) = read_json(&self.dir.join("status.json")) {
                self.state = LiveState::from_json(&v, "status.json");
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_live_and_ignores_unknown_fields() {
        let v: Value = serde_json::from_str(
            r#"{"v":1,"connected":true,"mode":"sostenuto","pedal":90,"una_corda":true,
                "touch":"heavy","ones":"context","last":{"note":60,"raw":98,"out":67},
                "updated":123.5,"future_field":[1,2,3]}"#,
        )
        .unwrap();
        let s = LiveState::from_json(&v, "live.json");
        assert_eq!(s.version, 1);
        assert_eq!(s.pedal_mode.as_deref(), Some("sostenuto"));
        assert_eq!(s.pedal_value, 90);
        assert_eq!(s.una_corda, Some(true));
        assert_eq!(s.touch.as_deref(), Some("heavy"));
        assert_eq!(s.last.unwrap().out, 67);
    }

    #[test]
    fn falls_back_to_status_json_names() {
        let v: Value = serde_json::from_str(
            r#"{"connected":true,"mode":"sustain","una_corda":false,
                "touch_mode":"acoustic","ones_mode":"ppp","updated":1.0}"#,
        )
        .unwrap();
        let s = LiveState::from_json(&v, "status.json");
        assert_eq!(s.touch.as_deref(), Some("acoustic"));
        assert_eq!(s.ones.as_deref(), Some("ppp"));
        assert_eq!(s.pedal_value, 0);
        assert!(s.last.is_none());
    }
}
