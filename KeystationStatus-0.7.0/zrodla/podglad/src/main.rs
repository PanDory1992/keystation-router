// Renders the plugin's photo view with a fake router state into preview.rgba (for checking the layout).
#[path = "../../ks-status/src/cmd.rs"]
#[allow(dead_code)]
mod cmd;
#[path = "../../ks-status/src/live.rs"]
#[allow(dead_code)]
mod live;
#[path = "../../ks-status/src/photo.rs"]
#[allow(dead_code)]
mod photo;
use eframe::egui;
use std::sync::Arc;

struct App { tex: Option<egui::TextureHandle>, state: live::LiveState, view: photo::View, frames: u32, shot: bool }

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _f: &mut eframe::Frame) {
        egui::CentralPanel::default().frame(egui::Frame::new().fill(egui::Color32::from_rgb(20, 19, 17))).show(ctx, |ui| {
            photo::draw(ui, &self.state, self.tex.as_ref().unwrap(), &mut self.view);
        });
        self.frames += 1;
        if self.frames == 5 && !self.shot { ctx.send_viewport_cmd(egui::ViewportCommand::Screenshot(Default::default())); self.shot = true; }
        let shot = ctx.input(|i| i.raw.events.iter().find_map(|e| if let egui::Event::Screenshot { image, .. } = e { Some(image.clone()) } else { None }));
        if let Some(img) = shot {
            let mut bytes = Vec::new();
            for p in &img.pixels { bytes.extend_from_slice(&[p.r(), p.g(), p.b(), 255]); }
            std::fs::write("preview.rgba", &bytes).unwrap();
            std::fs::write("preview.size", format!("{} {}", img.size[0], img.size[1])).unwrap();
            std::process::exit(0);
        }
        ctx.request_repaint();
    }
}

fn main() {
    let json = r#"{"v":1,"connected":true,"mode":"sustain","pedal":90,"una_corda":false,"touch":"moje3","ones":"context",
        "half_pedal":false,"half_depth":80,"debounce":false,"bounces":0,"release_ms":120,
        "last":{"note":61,"raw":98,"out":81},
        "controls":{"B10":64,"B11":90,"B12":30,"B13":100,"B16":20,"B18":40,"B26":110,"B27":70,"B33":127,"C1":100,"C2":80,"C9":127},
        "button":{"label":"C53","t":NOW},"updated":NOW}"#;
    let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs_f64() + 30.0;
    let v: serde_json::Value = serde_json::from_str(&json.replace("NOW", &now.to_string())).unwrap();
    let state = live::LiveState::from_json_pub(&v);
    let w: f32 = std::env::args().nth(1).and_then(|a| a.parse().ok()).unwrap_or(1098.0);
    let h: f32 = std::env::args().nth(2).and_then(|a| a.parse().ok()).unwrap_or(624.0);
    let opts = eframe::NativeOptions { viewport: egui::ViewportBuilder::default().with_inner_size([w, h]), ..Default::default() };
    eframe::run_native("preview", opts, Box::new(|cc| {
        let ctx = &cc.egui_ctx;
        let mut fonts = egui::FontDefinitions::default();
        fonts.font_data.insert(photo::LCD_FONT.into(), Arc::new(egui::FontData::from_static(include_bytes!("../../ks-status/assets/VT323-Regular.ttf"))));
        fonts.font_data.insert(photo::CAPTION_FONT.into(), Arc::new(egui::FontData::from_static(include_bytes!("../../ks-status/assets/BarlowSemiCondensed-SemiBold.ttf"))));
        fonts.families.insert(egui::FontFamily::Name(photo::LCD_FONT.into()), vec![photo::LCD_FONT.into()]);
        fonts.families.insert(egui::FontFamily::Name(photo::CAPTION_FONT.into()), vec![photo::CAPTION_FONT.into()]);
        ctx.set_fonts(fonts);
        let tex = photo::texture(ctx);
        Ok(Box::new(App { tex, state, view: photo::View::Photo, frames: 0, shot: false }))
    })).unwrap();
}
