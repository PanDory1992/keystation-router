"""Lets the "Keystation Status" plugin switch modes (06.11.2026).
The plugin writes live-cmd.json; the router applies it through the same path as
the physical buttons (Program Change 2/3/4/9/10/11) and deletes the file.
Idempotent, makes a backup first, requests a router restart."""
from pathlib import Path
import shutil, sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("pedal_router.py"))
s = p.read_text(encoding="utf-8")
if "CMD_FILE" in s:
    print("already patched"); sys.exit(0)
assert "LIVE_FILE" in s, "apply_live_json.py first"
shutil.copy2(p, p.with_name("pedal_router.before-plugin-cmd-20261106.py"))

def rep(a, b):
    global s
    assert s.count(a) == 1, f"anchor not unique/missing: {a[:50]!r}"
    s = s.replace(a, b)

rep('LIVE_MIN_GAP_S = 0.05\n', '''LIVE_MIN_GAP_S = 0.05
# Commands from the plugin (06.11): {"v":1,"id":..,"set":{"mode","una_corda","touch","ones"}}
CMD_FILE = ROOT / "live-cmd.json"
CMD_POLL_S = 0.04
''')

rep("    threading.Thread(target=live_writer, name=\"live-json\", daemon=True).start()\n", '''    threading.Thread(target=live_writer, name="live-json", daemon=True).start()

    def apply_command(want):
        """Same effect as pressing the physical buttons."""
        presses = []
        mode = want.get("mode")
        if mode in PROGRAM_BUTTONS.values() and mode != mapper.mode:
            presses.append(next(k for k, v in PROGRAM_BUTTONS.items() if v == mode))
        una = want.get("una_corda")
        if isinstance(una, bool) and una != bool(mapper.una_corda_values[0]):
            presses.append(UNA_CORDA_BUTTON)
        touch = want.get("touch")
        if touch in TOUCH_BUTTONS.values() and touch != mapper.touch_mode:
            presses.append(next(k for k, v in TOUCH_BUTTONS.items() if v == touch))
        for program in presses:
            dispatch(bytes((0xC0, program)))
        ones = want.get("ones")
        if ones in ("context", "ppp"):
            try:
                ONES_MODE_FILE.write_text(ones, encoding="ascii")
            except OSError:
                pass
            mapper.ones_context = ones == "context"
        logging.info("Plugin command %s -> programs %s", want, presses)
        with io_lock:
            publish_state(midi_in is not None)
        live_event.set()

    def command_watcher():
        while not done.is_set():
            time.sleep(CMD_POLL_S)
            try:
                text = CMD_FILE.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                CMD_FILE.unlink()
            except OSError:
                pass
            try:
                want = json.loads(text).get("set") or {}
                if isinstance(want, dict):
                    apply_command(want)
            except Exception:
                logging.exception("Plugin command rejected: %r", text[:200])

    threading.Thread(target=command_watcher, name="plugin-cmd", daemon=True).start()
''')
p.write_text(s, encoding="utf-8")
p.with_name("restart-router").write_text("plugin command patch\n", encoding="ascii")
print("patched; restart requested")
