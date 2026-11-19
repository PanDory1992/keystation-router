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
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

/// After this long without a fresh timestamp the state is shown as stale.
pub const STALE_AFTER_S: f64 = 3.5;
/// How often the editor re-reads the file.
pub const POLL_EVERY: Duration = Duration::from_millis(80);
/// Pause in polling after a click (router applies a command within ~40 ms).
pub const HOLD_AFTER_CLICK: Duration = Duration::from_millis(300);

#[derive(Clone, Debug, Default)]
pub struct LastNote {
    pub note: u8,
    pub raw: u8,
    pub out: u8,
    /// 0.10.0: key from the Mega scanner: time between the two contacts in us
    pub us: Option<u32>,
}

/// 0.10.0 (20.11): keys read by the Arduino Mega scanner, velocity from the grand-piano formula.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Mega {
    pub connected: bool,
    pub curve: String,
    /// (name, anchor us, anchor velocity) in the router's order
    pub curves: Vec<(String, f64, f64)>,
    /// black keys: time divided by this before the formula
    pub black: f64,
    pub minimum: f64,
    pub hires: bool,
}

impl Mega {
    fn from_json(v: Option<&Value>) -> Option<Mega> {
        let v = v?;
        let curves = v
            .get("curves")
            .and_then(Value::as_object)
            .map(|m| {
                m.iter()
                    .filter_map(|(k, c)| {
                        Some((k.clone(), c.get("kotwica_us")?.as_f64()?, c.get("kotwica_velocity")?.as_f64()?))
                    })
                    .collect()
            })
            .unwrap_or_default();
        Some(Mega {
            connected: v.get("connected").and_then(Value::as_bool).unwrap_or(false),
            curve: v.get("curve").and_then(Value::as_str).unwrap_or("").to_owned(),
            curves,
            black: v.get("black").and_then(Value::as_f64).unwrap_or(1.0).max(0.1),
            minimum: v.get("minimum").and_then(Value::as_f64).unwrap_or(1.0),
            hires: v.get("hires").and_then(Value::as_bool).unwrap_or(false),
        })
    }

    /// Velocity the router gives for `us` between the contacts (same formula as mega_input.py).
    pub fn velocity(&self, us: f64, black: bool) -> f64 {
        let (_, au, av) = self.curves.iter().find(|c| c.0 == self.curve).cloned().unwrap_or((String::new(), 6500.0, 100.0));
        let t = (if black { us / self.black } else { us }).max(1.0);
        (av + 25.0 * (au / t).log2()).clamp(self.minimum, 127.0)
    }

    pub fn next_curve(&self) -> String {
        let i = self.curves.iter().position(|c| c.0 == self.curve).map_or(0, |i| i + 1);
        self.curves.get(i % self.curves.len().max(1)).map(|c| c.0.clone()).unwrap_or_default()
    }
}

/// 0.7.0: the last P10 button pressed ("B44".."C60") and when (router's unix time).
#[derive(Clone, Debug, Default)]
pub struct Pressed {
    pub label: String,
    pub t: f64,
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
    /// 0.10.0: the Mega scanner (None = older router)
    pub mega: Option<Mega>,
    /// Half pedal (0.3.0): on/off, CC64 value sent for "down", last physical B17 value.
    pub half_pedal: Option<bool>,
    pub half_depth: u8,
    pub half_knob: Option<u8>,
    /// Debounce filter (0.3.0) and how many bounces it removed since the router started.
    pub debounce: Option<bool>,
    pub bounces: u64,
    /// Sustain release ramp in ms (0.4.0); None = older router that does not report it.
    pub release_ms: Option<u16>,
    /// 0.7.0: last position of every knob and fader ("B10".."B33", "C1".."C9"), 0..127.
    /// Empty until the control is moved (or SNAPSHOT is pressed on the keyboard).
    pub controls: HashMap<String, u8>,
    pub button: Option<Pressed>,
    /// 0.7.0: seconds left of "read positions" (router swallows knob/fader messages, SNAPSHOT is safe).
    pub reading: f32,
    /// 16.11: faders C2..C8 assigned to Studio One channels by name (router fader_assign.py).
    pub faders: Faders,
    /// Unix time of the router's last write.
    pub updated: f64,
    /// Which file the state came from ("live.json" or "status.json").
    pub source: &'static str,
}

/// 16.11: which channel each fader C2..C8 drives, and the C54 assignment in progress.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Faders {
    pub map: HashMap<String, String>,
    /// seconds left after C54: the next fader moved takes `selected`
    pub assigning: f32,
    /// the channel selected in Studio One (from the bridge)
    pub selected: Option<String>,
    /// every channel of the open song, in mixer order (from the bridge)
    pub channels: Vec<String>,
}

impl Faders {
    fn from_json(v: Option<&Value>) -> Faders {
        let Some(v) = v else { return Faders::default() };
        Faders {
            map: v
                .get("map")
                .and_then(Value::as_object)
                .map(|m| m.iter().filter_map(|(k, x)| Some((k.clone(), x.as_str()?.to_owned()))).collect())
                .unwrap_or_default(),
            assigning: v.get("assigning").and_then(Value::as_f64).unwrap_or(0.0).clamp(0.0, 60.0) as f32,
            selected: v.get("selected").and_then(Value::as_str).map(str::to_owned),
            channels: v
                .get("channels")
                .and_then(Value::as_array)
                .map(|a| a.iter().filter_map(|x| x.as_str().map(str::to_owned)).collect())
                .unwrap_or_default(),
        }
    }
}

impl LiveState {
    pub fn is_fresh(&self) -> bool {
        self.updated > 0.0 && now_unix() - self.updated < STALE_AFTER_S
    }

    /// For the layout preview tool (ks-preview): parse a live.json value.
    pub fn from_json_pub(v: &Value) -> Self {
        Self::from_json(v, "live.json")
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
                us: l.get("us").and_then(Value::as_u64).map(|u| u.min(u32::MAX as u64) as u32),
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
            mega: Mega::from_json(v.get("mega")),
            half_pedal: b("half_pedal"),
            half_depth: n("half_depth").unwrap_or(80.0).clamp(1.0, 127.0) as u8,
            half_knob: n("half_knob").map(|v| v.clamp(0.0, 127.0) as u8),
            debounce: b("debounce"),
            bounces: v.get("bounces").and_then(Value::as_u64).unwrap_or(0),
            release_ms: v.get("release_ms").and_then(Value::as_u64).map(|m| m.min(1000) as u16),
            controls: v
                .get("controls")
                .and_then(Value::as_object)
                .map(|m| {
                    m.iter()
                        .filter_map(|(k, x)| Some((k.clone(), x.as_u64()?.min(127) as u8)))
                        .collect()
                })
                .unwrap_or_default(),
            reading: n("reading").unwrap_or(0.0).clamp(0.0, 60.0) as f32,
            button: v.get("button").and_then(|b| {
                Some(Pressed { label: b.get("label")?.as_str()?.to_owned(), t: b.get("t")?.as_f64()? })
            }),
            faders: Faders::from_json(v.get("faders")),
            updated: n("updated").unwrap_or(0.0),
            source,
        }
    }
}

pub fn now_unix() -> f64 {
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
    pub dir: PathBuf,
    last_poll: Option<Instant>,
    /// After a click the shown value is set at once; polling pauses briefly so
    /// an older file cannot flash the previous value back.
    hold_until: Option<Instant>,
    pub state: LiveState,
}

impl Default for LiveReader {
    fn default() -> Self {
        LiveReader { dir: router_dir(), last_poll: None, hold_until: None, state: LiveState::default() }
    }
}

impl LiveReader {
    pub fn optimistic(&mut self, command: &crate::cmd::Command) {
        use crate::cmd::Command::*;
        match command {
            PedalMode(m) => self.state.pedal_mode = Some((*m).to_owned()),
            UnaCorda(on) => self.state.una_corda = Some(*on),
            Touch(t) => self.state.touch = Some((*t).to_owned()),
            MegaCurve(c) => {
                if let Some(m) = self.state.mega.as_mut() {
                    m.curve = c.clone();
                }
            }
            MegaHires(on) => {
                if let Some(m) = self.state.mega.as_mut() {
                    m.hires = *on;
                }
            }
            Ones(o) => self.state.ones = Some((*o).to_owned()),
            HalfPedal(on) => self.state.half_pedal = Some(*on),
            HalfDepth(d) => self.state.half_depth = *d,
            Debounce(on) => self.state.debounce = Some(*on),
            ReleaseMs(ms) => self.state.release_ms = Some(*ms),
            ReadControls => self.state.reading = 6.0,
            Fader(f, ch) => match ch {
                Some(name) => {
                    self.state.faders.map.insert(f.clone(), name.clone());
                }
                None => {
                    self.state.faders.map.remove(f);
                }
            },
        }
        self.hold_until = Some(Instant::now() + HOLD_AFTER_CLICK);
    }

    pub fn poll(&mut self) {
        if self.hold_until.map_or(false, |t| Instant::now() < t) {
            return;
        }
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
    fn faders_from_the_router() {
        let v: Value = serde_json::from_str(r#"{"v":1,"updated":1,"faders":{"map":{"C2":"Perkusja Bus"},"assigning":4.5,"selected":"FX 1","channels":["FX 1","Main"]}}"#).unwrap();
        let s = LiveState::from_json_pub(&v);
        assert_eq!(s.faders.map.get("C2").map(String::as_str), Some("Perkusja Bus"));
        assert_eq!((s.faders.assigning, s.faders.selected.as_deref(), s.faders.channels.len()), (4.5, Some("FX 1"), 2));
        let old: Value = serde_json::from_str(r#"{"v":1,"updated":1}"#).unwrap();
        assert_eq!(LiveState::from_json_pub(&old).faders, Faders::default());
        let mut r = LiveReader::default();
        r.optimistic(&crate::cmd::Command::Fader("C3".into(), Some("Main".into())));
        assert_eq!(r.state.faders.map.get("C3").map(String::as_str), Some("Main"));
    }

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
        assert_eq!(s.half_pedal, None);
        assert_eq!(s.half_depth, 80);
    }

    #[test]
    fn parses_half_pedal_and_debounce() {
        let v: Value = serde_json::from_str(
            r#"{"v":1,"half_pedal":true,"half_depth":64,"half_knob":64,
                "debounce":true,"bounces":3,"updated":1.0}"#,
        )
        .unwrap();
        let s = LiveState::from_json(&v, "live.json");
        assert_eq!(s.half_pedal, Some(true));
        assert_eq!(s.half_depth, 64);
        assert_eq!(s.half_knob, Some(64));
        assert_eq!(s.debounce, Some(true));
        assert_eq!(s.bounces, 3);
        assert_eq!(s.release_ms, None);
    }

    #[test]
    fn parses_release_ms() {
        let v: Value = serde_json::from_str(r#"{"v":1,"release_ms":250,"updated":1.0}"#).unwrap();
        assert_eq!(LiveState::from_json(&v, "live.json").release_ms, Some(250));
        let v: Value = serde_json::from_str(r#"{"v":1,"release_ms":99999}"#).unwrap();
        assert_eq!(LiveState::from_json(&v, "live.json").release_ms, Some(1000));
    }

    #[test]
    fn parses_controls_and_button() {
        let v: Value = serde_json::from_str(
            r#"{"v":1,"controls":{"B10":64,"C9":127,"B33":300,"bad":"x"},
                "button":{"label":"C53","t":12.5},"updated":1.0}"#,
        )
        .unwrap();
        let s = LiveState::from_json(&v, "live.json");
        assert_eq!(s.controls.get("B10"), Some(&64));
        assert_eq!(s.controls.get("B33"), Some(&127));
        assert_eq!(s.controls.len(), 3);
        let b = s.button.unwrap();
        assert_eq!((b.label.as_str(), b.t), ("C53", 12.5));
        let old: Value = serde_json::from_str(r#"{"v":1,"button":null}"#).unwrap();
        let s = LiveState::from_json(&old, "live.json");
        assert!(s.controls.is_empty() && s.button.is_none());
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

#[cfg(test)]
mod mega_tests {
    use super::*;
    use serde_json::json;

    fn state() -> LiveState {
        LiveState::from_json_pub(&json!({
            "mega": {"connected": true, "curve": "fortepian", "black": 1.28, "minimum": 2, "hires": false,
                     "curves": {"fortepian": {"kotwica_us": 6500, "kotwica_velocity": 100},
                                "fortepian-pelny": {"kotwica_us": 6500, "kotwica_velocity": 120}}},
            "last": {"note": 60, "raw": 69, "out": 69, "us": 15200}
        }))
    }

    #[test]
    fn mega_formula_matches_the_router() {
        let s = state();
        let m = s.mega.as_ref().unwrap();
        assert!((m.velocity(6500.0, false) - 100.0).abs() < 1e-9);
        assert!((m.velocity(13000.0, false) - 75.0).abs() < 1e-9);
        assert!((m.velocity(6500.0 * 1.28, true) - 100.0).abs() < 1e-9);
        assert_eq!(m.velocity(1e7, false), 2.0);
        assert_eq!(m.velocity(10.0, false), 127.0);
        assert_eq!(m.next_curve(), "fortepian-pelny");
        assert_eq!(s.last.as_ref().unwrap().us, Some(15200));
    }

    #[test]
    fn older_router_without_mega() {
        let s = LiveState::from_json_pub(&json!({"touch": "naturalna"}));
        assert!(s.mega.is_none());
    }
}
