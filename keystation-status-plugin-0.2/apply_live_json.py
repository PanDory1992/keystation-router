"""Adds live.json to pedal_router.py (06.11.2026): the router writes its state
on every change and once a second, for the "Keystation Status" VST3 plugin.
Idempotent: running it twice changes nothing. Makes a backup first."""
from pathlib import Path
import shutil, sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("pedal_router.py"))
s = p.read_text(encoding="utf-8")
if "LIVE_FILE" in s:
    print("already patched"); sys.exit(0)
shutil.copy2(p, p.with_name("pedal_router.before-live-json-20261106.py"))

def rep(a, b):
    global s
    assert s.count(a) == 1, f"anchor not unique/missing: {a[:50]!r}"
    s = s.replace(a, b)

rep('CAPTURE_FILE = ROOT / "notes.csv"\n',
    'CAPTURE_FILE = ROOT / "notes.csv"\n'
    '# Live state for the DAW plugin "Keystation Status" (06.11): versioned JSON, written\n'
    '# atomically on every change and once a second. Readers must ignore unknown fields.\n'
    'LIVE_FILE = ROOT / "live.json"\n'
    'LIVE_MIN_GAP_S = 0.05\n')

rep("    def capture(message, routed):\n", '''    live_event = threading.Event()
    live_last = {}

    def live_snapshot():
        return {
            "v": 1,
            "connected": midi_in is not None,
            "mode": mapper.mode,
            "pedal": max(mapper.pedal_values),
            "una_corda": bool(mapper.una_corda_values[0]),
            "touch": mapper.touch_mode,
            "ones": "context" if mapper.ones_context else "ppp",
            "last": dict(live_last) or None,
            "updated": time.time(),
        }

    def live_writer():
        tmp = LIVE_FILE.with_name("live.json.tmp")
        while not done.is_set():
            live_event.wait(1.0)
            live_event.clear()
            try:
                tmp.write_text(json.dumps(live_snapshot()), encoding="utf-8")
                os.replace(tmp, LIVE_FILE)
            except OSError:
                pass          # file briefly busy: the next change or tick rewrites it
            time.sleep(LIVE_MIN_GAP_S)

    threading.Thread(target=live_writer, name="live-json", daemon=True).start()

    def capture(message, routed):
''')

rep("            capture(message, routed)\n", '''            capture(message, routed)
            if len(message) >= 3 and message[0] & 0xF0 == 0x90 and message[2] > 0:
                out = next((p[2] for d, p in routed if p[0] & 0xF0 == 0x90 and len(p) >= 3), message[2])
                live_last.update(note=message[1], raw=message[2], out=out)
            live_event.set()
''')
p.write_text(s, encoding="utf-8")
restart = p.with_name("restart-router")
if "RESTART_FILE" in s:
    restart.write_text("live.json patch\n", encoding="ascii")
    print("patched; restart requested")
else:
    print("patched; restart the router by hand")
