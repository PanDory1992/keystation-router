//! The score's life outside the window: the engine, the notes the track plays,
//! the clock, HEAR and saving. Lives as long as the plugin, so notes are written
//! while the editor is closed too; the editor borrows it to draw and to click.

use crate::bus::Bus;
use crate::engine::Engine;
use serde_json::Value;

/// What the audio thread sends.
#[derive(Clone, Copy, Debug)]
pub enum Ev {
    On { pitch: u8, vel: u8, host: f64, free: f64, playing: bool },
    Off { pitch: u8, host: f64, free: f64, playing: bool },
}

/// Where Studio One is.
#[derive(Clone, Copy, Debug, Default)]
pub struct Clock {
    pub host: f64,
    pub free: f64,
    pub playing: bool,
    pub tempo: f64,
    pub num: u32,
    pub den: u32,
}

/// What only the editor window can do.
#[derive(Clone, Debug, PartialEq)]
pub enum Msg {
    /// S / M / L
    Window(u32),
    /// ask where to save, then call `export`
    Export(String, String),
    OpenUrl,
    Rename(String),
}

pub struct Core {
    pub eng: Engine,
    bus: Bus,
    /// messages for the editor
    pub msgs: Vec<Msg>,
    /// the JSON last saved or loaded: what the project holds
    pub saved: String,
    pub error: Option<String>,
}

pub const WINDOWS: [(u32, u32); 3] = [(1000, 640), (1200, 760), (1400, 820)];

impl Core {
    pub fn new() -> Result<Core, String> {
        Ok(Core { eng: Engine::new()?, bus: Bus::new(), msgs: Vec::new(), saved: String::new(), error: None })
    }

    fn note_err(&mut self, r: Result<(), String>) {
        if let Err(e) = r {
            self.error = Some(e);
        }
    }

    pub fn input(&mut self, evs: &[Ev]) {
        if evs.is_empty() {
            return;
        }
        let mut s = String::from("[");
        for ev in evs {
            let (on, pitch, vel, host, free, playing) = match *ev {
                Ev::On { pitch, vel, host, free, playing } => (vel > 0, pitch, vel, host, free, playing),
                Ev::Off { pitch, host, free, playing } => (false, pitch, 0, host, free, playing),
            };
            if self.bus.is_echo(pitch) {
                continue;
            }
            if s.len() > 1 {
                s.push(',');
            }
            s.push_str(&format!("[{},{},{},{:.6},{:.6},{}]", on as u8, pitch, vel, host, free, playing as u8));
        }
        s.push(']');
        if s.len() > 2 {
            let r = self.eng.call::<_, ()>("s1_input", (s,));
            self.note_err(r);
        }
        self.pump();
    }

    pub fn tick(&mut self, c: Clock) {
        let r = self.eng.call::<_, ()>("s1_tick", (c.host, c.free, c.playing as i32, c.tempo, c.num as i32, c.den as i32));
        self.note_err(r);
        self.bus.tick();
        self.pump();
    }

    /// Answers spartito.js's outlet messages: what the brain answered in Live.
    pub fn pump(&mut self) {
        for _ in 0..8 {
            let out: String = match self.eng.call("s1_out", ()) {
                Ok(s) => s,
                Err(e) => {
                    self.error = Some(e);
                    return;
                }
            };
            if out.is_empty() {
                return;
            }
            let Ok(Value::Array(list)) = serde_json::from_str::<Value>(&out) else { return };
            for m in list {
                let word = m[0].as_str().unwrap_or("");
                match word {
                    "audition" => {
                        let hear = self.eng.eval::<i32>("G.opt.hear").unwrap_or(1);
                        if hear != 0 {
                            let n = |i: usize| m[i].as_f64().unwrap_or(0.0);
                            self.bus.play(n(1).clamp(0.0, 127.0) as u8, n(2).clamp(1.0, 127.0) as u8, n(3) as u32);
                        }
                    }
                    "uiparam" => {
                        let name = m[1].as_str().unwrap_or("").to_owned();
                        let v = m[2].as_f64().unwrap_or(0.0);
                        let r = self.eng.call::<_, ()>("s1_param", (name.clone(), v));
                        self.note_err(r);
                        if name == "win" {
                            self.msgs.push(Msg::Window(v.clamp(0.0, 2.0) as u32));
                        }
                    }
                    "exportfmt" => {
                        let fmt = m[1].as_str().unwrap_or("").to_owned();
                        let name: String = self.eng.call("s1_exportName", (fmt.clone(),)).unwrap_or_else(|_| "Spartito".into());
                        self.msgs.push(Msg::Export(fmt, name));
                    }
                    "openurl" => self.msgs.push(Msg::OpenUrl),
                    "s1_rename" => self.msgs.push(Msg::Rename(m[1].as_str().unwrap_or("").to_owned())),
                    _ => {} // "changed": saving looks at the versions; "hello", "capclose": no brain here
                }
            }
        }
    }

    /// Writes the chosen file; the status bar says how it went.
    pub fn export(&mut self, fmt: &str, path: &str) -> String {
        let r: String = self.eng.call("s1_export", (fmt.to_owned(), path.to_owned())).unwrap_or_else(|e| e);
        self.pump();
        r
    }

    /// The score as JSON when it changed since the last save.
    pub fn save_if_changed(&mut self) -> Option<String> {
        let s: String = self.eng.call("s1_saveIfChanged", ()).ok()?;
        if s.is_empty() || s == self.saved {
            return None;
        }
        self.saved = s.clone();
        Some(s)
    }

    pub fn load(&mut self, json: &str) {
        if json == self.saved {
            return;
        }
        self.saved = json.to_owned();
        if json.is_empty() {
            return;
        }
        let r = self.eng.call::<_, bool>("s1_load", (json.to_owned(),)).map(|_| ());
        self.note_err(r);
    }

    pub fn window(&self) -> u32 {
        self.eng.eval::<i32>("G.opt.win").unwrap_or(1).clamp(0, 2) as u32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn clock(host: f64, free: f64, playing: bool) -> Clock {
        Clock { host, free, playing, tempo: 100.0, num: 4, den: 4 }
    }

    #[test]
    fn played_notes_become_a_take_that_is_saved_and_loaded() {
        let mut c = Core::new().unwrap();
        // transport running, bar 5 of the song
        c.input(&[
            Ev::On { pitch: 60, vel: 90, host: 16.0, free: 0.0, playing: true },
            Ev::Off { pitch: 60, host: 17.0, free: 0.0, playing: true },
            Ev::On { pitch: 64, vel: 80, host: 17.0, free: 0.0, playing: true },
            Ev::Off { pitch: 64, host: 19.0, free: 0.0, playing: true },
        ]);
        c.tick(clock(19.5, 0.0, true));
        c.tick(clock(19.5, 0.0, false));
        assert_eq!(c.eng.eval::<i32>("G.M.notes.length").unwrap(), 2);
        assert_eq!(c.eng.eval::<i32>("br_barOffset()").unwrap(), 4);
        let saved = c.save_if_changed().expect("saved");
        assert!(c.save_if_changed().is_none());
        let mut d = Core::new().unwrap();
        d.load(&saved);
        assert_eq!(d.eng.eval::<String>("JSON.stringify(G.M.notes.map(function(n){return [n.p,n.t,n.d]}))").unwrap(), "[[60,0,1],[64,1,2]]");
        assert!(c.error.is_none() && d.error.is_none(), "{:?} {:?}", c.error, d.error);
    }

    #[test]
    fn the_window_buttons_and_exports_reach_the_editor() {
        let mut c = Core::new().unwrap();
        c.eng.call::<_, ()>("canvas", (1200, 760)).unwrap();
        c.eng.call::<_, ()>("ui_action", ("win_2",)).unwrap();
        c.eng.call::<_, ()>("ui_action", ("x_pdf",)).unwrap();
        c.pump();
        assert_eq!(c.msgs, vec![Msg::Window(2), Msg::Export("pdf".into(), "Spartito.pdf".into())]);
        assert_eq!(c.window(), 2);
        let dir = std::env::temp_dir().join("s1-export-test");
        let r = c.export("midi", dir.join("a").to_str().unwrap());
        assert_eq!(r, "");
        assert!(std::fs::read(dir.join("a.mid")).unwrap().starts_with(b"MThd"));
    }
}
