//! The window: spartito.js paints it, this file only carries things across.
//!
//!   mouse  -> onclick / ondrag / onidle / onidleout, as Max's [jsui] calls them
//!             (right click = Max's mod2: deletes a note, like ctrl-click)
//!   keys   -> keyasc (Backspace, Delete, 2-7, ".", "-", "+"), as the [key] object did;
//!             Ctrl+Z / Ctrl+Y undo and redo
//!   wheel  -> scrolls the score
//!   picture <- s1_paint's ops, rasterised at the screen's real pixel density,
//!             only when spartito.js asked for a redraw
//! and does what only a window can: resize (S / M / L), ask where to save an
//! export, open the website, name the score.

use crate::core::{Msg, WINDOWS};
use crate::Life;
use nih_plug_egui::egui::{self, Color32, Event, Key, Modifiers, PointerButton, Pos2, Rect, TextureOptions};
use nih_plug_egui::EguiState;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

type Chosen = Arc<Mutex<Vec<(String, Option<PathBuf>)>>>;

#[derive(Default)]
pub struct EditorState {
    tex: Option<egui::TextureHandle>,
    canvas: (i32, i32),
    ppp: f32,
    pressed: bool,
    focused: Option<bool>,
    rename: Option<String>,
    rename_focus: bool,
    /// file dialogs answer here (they run on their own thread)
    chosen: Chosen,
}

pub fn export_dir() -> PathBuf {
    let home = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")).map(PathBuf::from).unwrap_or_default();
    home.join("Documents").join("Spartito")
}

fn ask_where(fmt: String, name: String, chosen: Chosen) {
    std::thread::spawn(move || {
        let dir = export_dir();
        let _ = std::fs::create_dir_all(&dir);
        #[cfg(windows)]
        let path = {
            let ext = name.rsplit('.').next().unwrap_or("").to_owned();
            rfd::FileDialog::new().set_directory(&dir).set_file_name(&name).add_filter(ext.to_uppercase(), &[ext.as_str()]).save_file()
        };
        #[cfg(not(windows))]
        let path = Some(dir.join(&name));
        if let Ok(mut c) = chosen.lock() {
            c.push((fmt, path));
        }
    });
}

fn open(target: &str) {
    #[cfg(windows)]
    let _ = std::process::Command::new("explorer").arg(target).spawn();
    #[cfg(not(windows))]
    let _ = std::process::Command::new("xdg-open").arg(target).spawn();
}

fn mods(m: &Modifiers) -> (i32, i32, i32) {
    ((m.ctrl || m.command) as i32, m.shift as i32, m.alt as i32)
}

/// One editor frame.
pub fn frame(ctx: &egui::Context, st: &mut EditorState, life: &Life, egui_state: &EguiState) {
    let screen = ctx.screen_rect();
    let ppp = ctx.pixels_per_point();
    let (w, h) = (screen.width().round() as i32, screen.height().round() as i32);
    let events = ctx.input(|i| i.events.clone());
    let renaming = st.rename.is_some();

    // ---- notes and the clock through the core; mouse and keys into spartito.js
    life.service();
    let picture = life.with(|c| {
        let e = &c.eng;
        let mut r = Ok(());
        if (w, h) != st.canvas {
            r = r.and(e.call::<_, ()>("canvas", (w, h)));
            st.canvas = (w, h);
        }
        for ev in &events {
            match ev {
                Event::WindowFocused(f) => {
                    if st.focused != Some(*f) {
                        st.focused = Some(*f);
                        r = r.and(e.call::<_, ()>("focus", (*f as i32,)));
                    }
                }
                Event::PointerMoved(p) if !renaming => {
                    let (x, y) = (p.x as f64, p.y as f64);
                    r = r.and(if st.pressed {
                        e.call::<_, ()>("s1_mouse", ("drag", x, y, 1, 0))
                    } else {
                        e.call::<_, ()>("s1_mouse", ("idle", x, y, 0, 0))
                    });
                }
                Event::PointerButton { pos, button, pressed, modifiers } if !renaming => {
                    let (x, y) = (pos.x as f64, pos.y as f64);
                    let (m1, sh, alt) = mods(modifiers);
                    if *pressed && matches!(button, PointerButton::Primary | PointerButton::Secondary) {
                        if st.focused.is_none() {
                            st.focused = Some(true);
                            r = r.and(e.call::<_, ()>("focus", (1,)));
                        }
                        let right = (*button == PointerButton::Secondary) as i32;
                        st.pressed = true;
                        r = r.and(e.call::<_, ()>("s1_mouse", ("click", x, y, 1, m1 | sh << 1 | alt << 2 | right << 3)));
                    } else if !*pressed && st.pressed {
                        st.pressed = false;
                        r = r.and(e.call::<_, ()>("s1_mouse", ("drag", x, y, 0, m1 | sh << 1 | alt << 2)));
                    }
                }
                Event::PointerGone if !st.pressed => r = r.and(e.call::<_, ()>("onidleout", ())),
                Event::MouseWheel { unit, delta, .. } => {
                    let dy = match unit {
                        egui::MouseWheelUnit::Point => delta.y,
                        egui::MouseWheelUnit::Line => delta.y * 40.0,
                        egui::MouseWheelUnit::Page => delta.y * h as f32 * 0.9,
                    };
                    r = r.and(e.call::<_, ()>("s1_wheel", (dy as f64,)));
                }
                Event::Key { key, pressed: true, modifiers, .. } if !renaming => {
                    let ctrl = modifiers.ctrl || modifiers.command;
                    r = r.and(match key {
                        Key::Backspace => e.call::<_, ()>("keyasc", (8,)),
                        Key::Delete => e.call::<_, ()>("keyasc", (127,)),
                        Key::Z if ctrl && modifiers.shift => e.call::<_, ()>("ui_action", ("redo",)),
                        Key::Z if ctrl => e.call::<_, ()>("ui_action", ("undo",)),
                        Key::Y if ctrl => e.call::<_, ()>("ui_action", ("redo",)),
                        _ => Ok(()),
                    });
                }
                Event::Text(t) if !renaming => {
                    for ch in t.chars().filter(|c| "234567.-+=".contains(*c)) {
                        r = r.and(e.call::<_, ()>("keyasc", (ch as i32,)));
                    }
                }
                _ => {}
            }
        }
        if let Err(err) = r {
            c.error = Some(err);
        }
        c.pump();

        // ---- what only the window can do
        for m in std::mem::take(&mut c.msgs) {
            match m {
                Msg::Window(i) => egui_state.set_requested_size(WINDOWS[i.min(2) as usize]),
                Msg::Export(fmt, name) => ask_where(fmt, name, st.chosen.clone()),
                Msg::OpenUrl => open("http://www.remodevicocomposer.eu"),
                Msg::Rename(name) => {
                    st.rename = Some(name);
                    st.rename_focus = true;
                }
            }
        }
        let done = st.chosen.lock().map(|mut c| std::mem::take(&mut *c)).unwrap_or_default();
        for (fmt, path) in done {
            if let Some(p) = path {
                c.export(&fmt, &p.to_string_lossy());
            }
        }

        // ---- the picture, when spartito.js asked for one
        let due = st.tex.is_none() || st.ppp != ppp || c.eng.call::<_, i32>("s1_dirty", ()).unwrap_or(1) != 0;
        if due {
            st.ppp = ppp;
            match c.eng.call::<_, String>("s1_paint", ()) {
                Ok(ops) => Some(ops),
                Err(e) => {
                    c.error = Some(e);
                    None
                }
            }
        } else {
            None
        }
    });

    if let Some(Some(ops)) = picture {
        if let Ok(pm) = crate::render::frame(&ops, w as f32, h as f32, ppp) {
            let img = egui::ColorImage::from_rgba_premultiplied([pm.width() as usize, pm.height() as usize], pm.data());
            match &mut st.tex {
                Some(t) => t.set(img, TextureOptions::NEAREST),
                None => st.tex = Some(ctx.load_texture("spartito-s1", img, TextureOptions::NEAREST)),
            }
        }
    }

    // ---- on screen
    egui::CentralPanel::default().frame(egui::Frame::NONE.fill(Color32::from_rgb(40, 41, 43))).show(ctx, |ui| {
        if let Some(t) = &st.tex {
            let size = egui::vec2(t.size()[0] as f32 / ppp, t.size()[1] as f32 / ppp);
            let uv = Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0));
            ui.painter().image(t.id(), Rect::from_min_size(Pos2::ZERO, size), uv, Color32::WHITE);
        }
    });
    let start_error = life.start_error.lock().ok().and_then(|e| e.clone());
    let run_error = life.with(|c| c.error.clone()).flatten();
    if let Some(e) = start_error.or(run_error) {
        egui::Area::new(egui::Id::new("s1-error")).fixed_pos(Pos2::new(8.0, screen.height() - 60.0)).show(ctx, |ui| {
            ui.colored_label(Color32::from_rgb(255, 120, 80), format!("Spartito: {e}"));
        });
    }

    // ---- naming the score (a click on the title in the status bar)
    if let Some(name) = st.rename.as_mut() {
        let mut close = None;
        egui::Area::new(egui::Id::new("s1-rename")).fixed_pos(Pos2::new(8.0, screen.height() - 62.0)).show(ctx, |ui| {
            egui::Frame::popup(ui.style()).show(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.label("Title of the score");
                    let r = ui.add(egui::TextEdit::singleline(name).desired_width(320.0));
                    if st.rename_focus {
                        r.request_focus();
                        st.rename_focus = false;
                    }
                    if ui.button("OK").clicked() || (r.lost_focus() && ui.input(|i| i.key_pressed(Key::Enter))) {
                        close = Some(true);
                    }
                    if ui.button("Cancel").clicked() || ui.input(|i| i.key_pressed(Key::Escape)) {
                        close = Some(false);
                    }
                });
            });
        });
        if let Some(ok) = close {
            if ok {
                let n = name.clone();
                life.with(|c| {
                    let _ = c.eng.call::<_, ()>("s1_setName", (n,));
                });
            }
            st.rename = None;
        }
    }
    ctx.request_repaint_after(std::time::Duration::from_millis(40));
}
