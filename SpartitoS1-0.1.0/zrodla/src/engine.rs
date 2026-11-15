//! QuickJS running assets/spartito-s1.js: prelude.js (Max's objects), Miki's
//! spartito.js as the editor view, glue.js (the parts a brain did in Live).
//! The host functions the prelude expects are defined here first.

use crate::fonts::Fonts;
use rquickjs::function::IntoArgs;
use rquickjs::{Context, FromJs, Function, Runtime};

const JS: &str = include_str!("../assets/spartito-s1.js");

pub struct Engine {
    _rt: Runtime,
    ctx: Context,
}

fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}

fn write(path: &str, data: &[u8]) -> bool {
    let p = std::path::Path::new(path);
    if let Some(dir) = p.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    std::fs::write(p, data).is_ok()
}

impl Engine {
    pub fn new() -> Result<Engine, String> {
        let rt = Runtime::new().map_err(err)?;
        rt.set_memory_limit(1 << 30);
        rt.set_max_stack_size(8 << 20);
        let ctx = Context::full(&rt).map_err(err)?;
        ctx.with(|c| -> Result<(), String> {
            let g = c.globals();
            let f = |e: rquickjs::Error| e.to_string();
            g.set(
                "__s1_measure",
                Function::new(c.clone(), |s: String, fam: String, b: i32, i: i32, size: f64| -> f64 {
                    Fonts::get().measure(&s, Fonts::pick(&fam, b != 0, i != 0), size as f32) as f64
                })
                .map_err(f)?,
            )
            .map_err(f)?;
            g.set("__s1_write_text", Function::new(c.clone(), |p: String, s: String| write(&p, s.as_bytes())).map_err(f)?)
                .map_err(f)?;
            g.set(
                "__s1_write_bytes",
                Function::new(c.clone(), |p: String, b: Vec<i32>| {
                    let bytes: Vec<u8> = b.iter().map(|&x| x as u8).collect();
                    write(&p, &bytes)
                })
                .map_err(f)?,
            )
            .map_err(f)?;
            g.set(
                "__s1_png",
                Function::new(c.clone(), |p: String, w: i32, h: i32, ops: String| -> String {
                    match crate::render::png(&p, w.max(1) as u32, h.max(1) as u32, &ops) {
                        Ok(()) => String::new(),
                        Err(e) => e,
                    }
                })
                .map_err(f)?,
            )
            .map_err(f)?;
            // Max runs its js in sloppy mode (spartito.js assigns `inlets` and `outlets` undeclared)
            let mut o = rquickjs::context::EvalOptions::default();
            o.strict = false;
            o.global = true;
            c.eval_with_options::<(), _>(JS, o).map_err(|e| format!("{e}: {:?}", c.catch()))
        })?;
        Ok(Engine { _rt: rt, ctx })
    }

    /// Calls a global function of the script.
    pub fn call<A, R>(&self, name: &str, args: A) -> Result<R, String>
    where
        A: for<'js> IntoArgs<'js>,
        R: for<'js> FromJs<'js>,
    {
        self.ctx.with(|c| {
            let f: Function = c.globals().get(name).map_err(|e| format!("{name}: {e}"))?;
            f.call::<A, R>(args).map_err(|e| format!("{name}: {e}: {:?}", c.catch()))
        })
    }

    /// Runs a line of script (tests, the preview tool).
    pub fn eval<R>(&self, code: &str) -> Result<R, String>
    where
        R: for<'js> FromJs<'js>,
    {
        self.ctx.with(|c| {
            let mut o = rquickjs::context::EvalOptions::default();
            o.strict = false;
            c.eval_with_options::<R, _>(code, o).map_err(|e| format!("{e}: {:?}", c.catch()))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_editor_paints_and_writes_a_note() {
        let e = Engine::new().unwrap();
        e.call::<_, ()>("canvas", (1200, 760)).unwrap();
        let ops: String = e.call("s1_paint", ()).unwrap();
        let v: serde_json::Value = serde_json::from_str(&ops).unwrap();
        let texts: Vec<&str> = v.as_array().unwrap().iter().filter_map(|o| o["s"].as_str()).collect();
        assert!(texts.contains(&"UNDO") && texts.contains(&"REC") && texts.contains(&"MUSICXML"), "{texts:?}");
        // a click on the treble staff of the empty score writes a quarter note
        e.call::<_, ()>("s1_mouse", ("click", 300, 200, 1, 0)).unwrap();
        e.call::<_, ()>("s1_mouse", ("drag", 300, 200, 0, 0)).unwrap();
        assert_eq!(e.eval::<i32>("G.M.notes.length").unwrap(), 1);
        let out: String = e.call("s1_out", ()).unwrap();
        assert!(out.contains("audition"), "{out}");
    }
}
