//! Fonts for the drawing: Arial for the editor's buttons and text, Times New Roman
//! for the score - the faces the Max device asks mgraphics for.
//!
//! On Windows the real ones are read from the system's Fonts folder, so the
//! window looks as it did in Live. Elsewhere, or if a file is missing, Arimo and
//! Tinos are used: metric twins (same advance widths), so text measures the same.
//!
//! Text is drawn as glyph outlines filled by tiny-skia, unhinted, at any size.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use tiny_skia::{FillRule, Paint, Path, PathBuilder, Pixmap, Transform};
use ttf_parser::{Face, GlyphId, OutlineBuilder, Tag};

static ARIMO: &[u8] = include_bytes!("../assets/Arimo-VF.ttf");
static TINOS_R: &[u8] = include_bytes!("../assets/Tinos-Regular.ttf");
static TINOS_B: &[u8] = include_bytes!("../assets/Tinos-Bold.ttf");
static TINOS_I: &[u8] = include_bytes!("../assets/Tinos-Italic.ttf");
static TINOS_BI: &[u8] = include_bytes!("../assets/Tinos-BoldItalic.ttf");

pub struct Font {
    face: Face<'static>,
    upem: f32,
    pub system: bool,
}

pub struct Fonts {
    /// [sans regular, sans bold, sans italic, sans bold italic, serif ...the same]
    faces: Vec<Font>,
    glyphs: Mutex<HashMap<(usize, u16), Option<Path>>>,
}

fn system_font(file: &str) -> Option<&'static [u8]> {
    if !cfg!(windows) {
        return None;
    }
    let dir = std::env::var("WINDIR").unwrap_or_else(|_| "C:\\Windows".into());
    let data = std::fs::read(std::path::Path::new(&dir).join("Fonts").join(file)).ok()?;
    Face::parse(&data, 0).ok()?;
    Some(Box::leak(data.into_boxed_slice()))
}

fn font(system: &str, fallback: &'static [u8], weight: Option<f32>) -> Font {
    let (data, is_system) = match system_font(system) {
        Some(d) => (d, true),
        None => (fallback, false),
    };
    let mut face = Face::parse(data, 0).expect("bundled font");
    if let (false, Some(w)) = (is_system, weight) {
        let _ = face.set_variation(Tag::from_bytes(b"wght"), w);
    }
    let upem = face.units_per_em() as f32;
    Font { face, upem, system: is_system }
}

impl Fonts {
    fn load() -> Fonts {
        let faces = vec![
            font("arial.ttf", ARIMO, Some(400.0)),
            font("arialbd.ttf", ARIMO, Some(700.0)),
            font("ariali.ttf", ARIMO, Some(400.0)),
            font("arialbi.ttf", ARIMO, Some(700.0)),
            font("times.ttf", TINOS_R, None),
            font("timesbd.ttf", TINOS_B, None),
            font("timesi.ttf", TINOS_I, None),
            font("timesbi.ttf", TINOS_BI, None),
        ];
        Fonts { faces, glyphs: Mutex::new(HashMap::new()) }
    }

    pub fn get() -> &'static Fonts {
        static F: OnceLock<Fonts> = OnceLock::new();
        F.get_or_init(Fonts::load)
    }

    /// Which face: mgraphics asks by family name ("Arial", "Times New Roman").
    pub fn pick(family: &str, bold: bool, italic: bool) -> usize {
        let f = family.to_ascii_lowercase();
        let serif = f.contains("times") || f.contains("serif") && !f.contains("sans") || f.contains("tinos");
        (if serif { 4 } else { 0 }) + bold as usize + 2 * italic as usize
    }

    pub fn using_system(&self) -> bool {
        self.faces.iter().all(|f| f.system)
    }

    fn glyph(&self, font: &Font, c: char) -> GlyphId {
        font.face.glyph_index(c).or_else(|| font.face.glyph_index('?')).unwrap_or(GlyphId(0))
    }

    fn advance(&self, font: &Font, g: GlyphId) -> f32 {
        font.face.glyph_hor_advance(g).unwrap_or(0) as f32 / font.upem
    }

    /// Width in pixels of `text` at `size` pixels per em.
    pub fn measure(&self, text: &str, face: usize, size: f32) -> f32 {
        let font = &self.faces[face];
        text.chars().map(|c| self.advance(font, self.glyph(font, c))).sum::<f32>() * size
    }

    /// Fills `text` with its baseline starting at (x, y), in the coordinates of `tr`.
    pub fn draw(&self, pm: &mut Pixmap, text: &str, face: usize, size: f32, x: f32, y: f32, paint: &Paint, tr: Transform) {
        let font = &self.faces[face];
        let mut pen = x;
        let mut cache = match self.glyphs.lock() {
            Ok(c) => c,
            Err(p) => p.into_inner(),
        };
        for c in text.chars() {
            let g = self.glyph(font, c);
            let path = cache.entry((face, g.0)).or_insert_with(|| outline(font, g));
            if let Some(p) = path {
                let t = tr.pre_translate(pen, y).pre_scale(size, size);
                pm.fill_path(p, paint, FillRule::Winding, t, None);
            }
            pen += self.advance(font, g) * size;
        }
    }
}

/// A glyph at 1 pixel per em, y down, origin on the baseline.
fn outline(font: &Font, g: GlyphId) -> Option<Path> {
    struct B(PathBuilder, f32);
    impl OutlineBuilder for B {
        fn move_to(&mut self, x: f32, y: f32) {
            self.0.move_to(x / self.1, -y / self.1)
        }
        fn line_to(&mut self, x: f32, y: f32) {
            self.0.line_to(x / self.1, -y / self.1)
        }
        fn quad_to(&mut self, x1: f32, y1: f32, x: f32, y: f32) {
            self.0.quad_to(x1 / self.1, -y1 / self.1, x / self.1, -y / self.1)
        }
        fn curve_to(&mut self, x1: f32, y1: f32, x2: f32, y2: f32, x: f32, y: f32) {
            self.0.cubic_to(x1 / self.1, -y1 / self.1, x2 / self.1, -y2 / self.1, x / self.1, -y / self.1)
        }
        fn close(&mut self) {
            self.0.close()
        }
    }
    let mut b = B(PathBuilder::new(), font.upem);
    font.face.outline_glyph(g, &mut b)?;
    b.0.finish()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arial_and_times_measure_like_the_real_ones() {
        let f = Fonts::get();
        // Arial Bold: U, N, D = 0.722 em, O = 0.778 em -> "UNDO" at 10 px is 29.44 px; Times bold "4" 26 px is 13 px (advance 0.5 em)
        let w = f.measure("UNDO", Fonts::pick("Arial", true, false), 10.0);
        assert!((w - 29.44).abs() < 0.05, "{w}");
        let w = f.measure("4", Fonts::pick("Times New Roman", true, false), 26.0);
        assert!((w - 13.0).abs() < 0.1, "{w}");
        assert_eq!(Fonts::pick("serif", false, true), 6);
    }

    #[test]
    fn text_puts_ink_where_it_is_asked() {
        let f = Fonts::get();
        let mut pm = Pixmap::new(60, 30).unwrap();
        let mut paint = Paint::default();
        paint.set_color_rgba8(0, 0, 0, 255);
        f.draw(&mut pm, "Hi", 0, 20.0, 5.0, 22.0, &paint, Transform::identity());
        let ink: Vec<(u32, u32)> = (0..30u32)
            .flat_map(|y| (0..60u32).map(move |x| (x, y)))
            .filter(|&(x, y)| pm.pixel(x, y).unwrap().alpha() > 128)
            .collect();
        assert!(ink.len() > 40);
        assert!(ink.iter().all(|&(x, y)| x >= 5 && y <= 22 && y >= 6), "{:?}", ink.first());
    }
}
