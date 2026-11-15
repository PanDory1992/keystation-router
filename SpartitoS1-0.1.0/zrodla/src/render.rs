//! Rasterising what spartito.js drew.
//!
//! The ops come from the mgraphics stand-in in prelude.js (the editor window)
//! or from an offscreen MGraphics (the PNG export):
//!   { k: "F", d: path, c: rgba }             fill, non-zero winding
//!   { k: "S", d: path, c: rgba, w: width }   stroke, butt caps, miter joins
//!   { k: "T", x, y, s, size, fam, b, i, c }  text, baseline at (x, y)
//! A path is "M", x, y, "L", x, y, "C", x1, y1, x2, y2, x, y, "Z". tiny-skia
//! anti-aliases like the cairo canvas under mgraphics did.

use crate::fonts::Fonts;
use serde_json::Value;
use tiny_skia::{FillRule, LineCap, LineJoin, Paint, PathBuilder, Pixmap, Stroke, Transform};

fn num(v: &Value) -> f32 {
    v.as_f64().unwrap_or(0.0) as f32
}

fn paint_of(c: &Value) -> Paint<'static> {
    let ch = |i: usize, d: f64| (c[i].as_f64().unwrap_or(d).clamp(0.0, 1.0) * 255.0).round() as u8;
    let mut p = Paint::default();
    p.set_color_rgba8(ch(0, 0.0), ch(1, 0.0), ch(2, 0.0), ch(3, 1.0));
    p.anti_alias = true;
    p
}

pub fn path(d: &[Value]) -> Option<tiny_skia::Path> {
    let mut b = PathBuilder::new();
    let mut i = 0;
    let at = |i: usize| (num(&d[i]), num(&d[i + 1]));
    while i < d.len() {
        match d[i].as_str() {
            Some("M") if i + 2 < d.len() => {
                let (x, y) = at(i + 1);
                b.move_to(x, y);
                i += 3;
            }
            Some("L") if i + 2 < d.len() => {
                let (x, y) = at(i + 1);
                b.line_to(x, y);
                i += 3;
            }
            Some("C") if i + 6 < d.len() => {
                let ((x1, y1), (x2, y2), (x, y)) = (at(i + 1), at(i + 3), at(i + 5));
                b.cubic_to(x1, y1, x2, y2, x, y);
                i += 7;
            }
            Some("Z") => {
                b.close();
                i += 1;
            }
            _ => i += 1,
        }
    }
    b.finish()
}

/// Draws `ops` into `pm`; `tr` maps the drawing's pixels to the pixmap's (the HiDPI scale).
pub fn draw(pm: &mut Pixmap, ops: &[Value], tr: Transform) {
    let fonts = Fonts::get();
    for op in ops {
        let d = || op["d"].as_array().map(|a| a.as_slice()).unwrap_or(&[]);
        match op["k"].as_str() {
            Some("F") => {
                if let Some(p) = path(d()) {
                    pm.fill_path(&p, &paint_of(&op["c"]), FillRule::Winding, tr, None);
                }
            }
            Some("S") => {
                if let Some(p) = path(d()) {
                    let st = Stroke {
                        width: num(&op["w"]).max(0.05),
                        line_cap: LineCap::Butt,
                        line_join: LineJoin::Miter,
                        ..Stroke::default()
                    };
                    pm.stroke_path(&p, &paint_of(&op["c"]), &st, tr, None);
                }
            }
            Some("T") => {
                let s = op["s"].as_str().unwrap_or("");
                if s.is_empty() {
                    continue;
                }
                let face = Fonts::pick(op["fam"].as_str().unwrap_or("Arial"), num(&op["b"]) != 0.0, num(&op["i"]) != 0.0);
                fonts.draw(pm, s, face, num(&op["size"]), num(&op["x"]), num(&op["y"]), &paint_of(&op["c"]), tr);
            }
            _ => {}
        }
    }
}

/// The whole frame of the editor: `w` x `h` points at `scale` pixels per point.
pub fn frame(ops_json: &str, w: f32, h: f32, scale: f32) -> Result<Pixmap, String> {
    let ops: Vec<Value> = serde_json::from_str(ops_json).map_err(|e| e.to_string())?;
    let pw = (w * scale).round().max(1.0) as u32;
    let ph = (h * scale).round().max(1.0) as u32;
    let mut pm = Pixmap::new(pw, ph).ok_or("no pixmap")?;
    draw(&mut pm, &ops, Transform::from_scale(scale, scale));
    Ok(pm)
}

/// The PNG export: white paper under the drawing, as ex_png paints it.
pub fn png(path: &str, w: u32, h: u32, ops_json: &str) -> Result<(), String> {
    let pm = frame(ops_json, w.clamp(1, 16000) as f32, h.clamp(1, 16000) as f32, 1.0)?;
    let data = pm.encode_png().map_err(|e| e.to_string())?;
    std::fs::write(path, data).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_with_a_hole_is_filled_non_zero() {
        // a square with a square hole wound the other way: non-zero leaves the hole empty
        let ops = r#"[{"k":"F","d":["M",0,0,"L",10,0,"L",10,10,"L",0,10,"Z","M",3,3,"L",3,7,"L",7,7,"L",7,3,"Z"],"c":[0,0,0,1]}]"#;
        let pm = frame(ops, 10.0, 10.0, 1.0).unwrap();
        assert_eq!(pm.pixels().iter().filter(|p| p.alpha() > 127).count(), 84);
        // twice the scale: four times the ink
        let pm = frame(ops, 10.0, 10.0, 2.0).unwrap();
        assert_eq!(pm.pixels().iter().filter(|p| p.alpha() > 127).count(), 336);
    }
}
