//! Renders the editor as the plugin would, without a window: `snap <out.png> [w h scale]`.
//! Plays a little piece in (transport running from bar 3), clicks a few things, paints.
use spartito_s1::core::{Clock, Core, Ev};
use std::time::Instant;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let out = a.get(1).cloned().unwrap_or("snap.png".into());
    let w: f32 = a.get(2).and_then(|s| s.parse().ok()).unwrap_or(1200.0);
    let h: f32 = a.get(3).and_then(|s| s.parse().ok()).unwrap_or(760.0);
    let scale: f32 = a.get(4).and_then(|s| s.parse().ok()).unwrap_or(1.0);
    let t0 = Instant::now();
    let mut c = Core::new().unwrap();
    println!("engine {} ms", t0.elapsed().as_millis());
    c.eng.call::<_, ()>("canvas", (w as i32, h as i32)).unwrap();
    let rh: &[(u8, f64, f64)] = &[(69, 8.0, 1.0), (72, 9.0, 0.5), (70, 9.5, 0.5), (69, 10.0, 0.333), (67, 10.333, 0.333), (65, 10.667, 0.333),
        (67, 11.0, 1.0), (65, 12.0, 1.5), (64, 13.5, 0.5), (62, 14.0, 2.0), (69, 16.0, 0.75), (70, 16.75, 0.25), (72, 17.0, 3.0)];
    let lh: &[(u8, f64, f64)] = &[(41, 8.0, 2.0), (48, 8.0, 2.0), (53, 8.0, 2.0), (46, 10.0, 2.0), (50, 10.0, 2.0), (53, 10.0, 2.0),
        (36, 12.0, 4.0), (43, 12.0, 4.0), (46, 12.0, 4.0), (41, 16.0, 4.0), (48, 16.0, 4.0), (57, 16.0, 4.0)];
    let mut evs: Vec<(f64, Ev)> = Vec::new();
    for &(p, t, d) in rh.iter().chain(lh.iter()) {
        evs.push((t, Ev::On { pitch: p, vel: 80, host: t, free: 0.0, playing: true }));
        evs.push((t + d * 0.98, Ev::Off { pitch: p, host: t + d * 0.98, free: 0.0, playing: true }));
    }
    evs.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let e: Vec<Ev> = evs.iter().map(|x| x.1).collect();
    c.input(&e);
    let clock = |host: f64, playing: bool| Clock { host, free: 0.0, playing, tempo: 84.0, num: 4, den: 4 };
    c.tick(clock(19.0, true));
    std::thread::sleep(std::time::Duration::from_millis(130));
    c.tick(clock(18.5, true));
    let mode = a.get(5).cloned().unwrap_or_default();
    if mode != "rec" {
        c.tick(clock(20.0, false));
        c.eng.eval::<()>("G.M.name = 'Próba: wolna ballada'; G.opt.key = -1; G.optVersion++; md_touch(G.M);").unwrap();
        // hover over the treble staff: the ghost note and the hint
        c.eng.call::<_, ()>("s1_mouse", ("idle", 520.0, 186.0, 0, 0)).unwrap();
    }
    if mode == "select" {
        c.eng.call::<_, ()>("s1_mouse", ("click", 148.0, 160.0, 1, 0)).unwrap();
        c.eng.call::<_, ()>("s1_mouse", ("drag", 148.0, 160.0, 0, 0)).unwrap();
        c.eng.call::<_, ()>("s1_mouse", ("idle", 148.0, 160.0, 0, 0)).unwrap();
    }
    c.pump();
    let t1 = Instant::now();
    let ops: String = c.eng.call("s1_paint", ()).unwrap();
    let t2 = Instant::now();
    let pm = spartito_s1::render::frame(&ops, w, h, scale).unwrap();
    let t3 = Instant::now();
    println!("paint (js) {} ms, raster {} ms, ops {} kB, error {:?}", (t2 - t1).as_millis(), (t3 - t2).as_millis(), ops.len() / 1024, c.error);
    pm.save_png(&out).unwrap();
}
