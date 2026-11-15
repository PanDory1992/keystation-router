"""Keeps the Keystation MIDI services alive (Claude, 01.11.2026).

Started once at logon (Startup folder). Launches and watches:
  * pedal_router.py          -> ports "Keystation Pedal Modes" / "Keystation Control"
  * studio_one_bridge.py     -> port "Codex Studio One Control" (MCP Bridge)
  * trener/trener_serwer.py  -> Trener on port 47810, never exits when idle (10.11: the iMac and the
                                iPhone can always open it, Trener.bat only opens the window)
If any one is missing or stops, it is started again within a few seconds.

Restart without anyone at the PC (15.11.2026, so Claude can deploy on its own): create an empty file
next to this script and within CHECK_S seconds it is acted on and removed:
  restart-trener     the Trener server is stopped and started again (new code, new VERSION)
  restart-bridge     the same for the Studio One bridge
  restart-nadzorca   this supervisor starts a fresh copy of itself and exits (after editing this file);
                     the services keep running and the new copy watches them
(The router has its own: restart-router, handled inside pedal_router.py.)
Every start, stop, exit code and the child's error output go to supervisor.log,
so a failure is never silent again.
"""
import ctypes
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "supervisor.log"
PYTHONW = Path(sys.executable).with_name("pythonw.exe")
SERVICES = {
    "router": ROOT / "pedal_router.py",
    "bridge": Path(r"C:\Users\mikit\.codex\.chatgpt-projects\g-p-6abc34ebd594819193b82e8c4aa00777"
                   r"\output\studio-one-setup\studio_one_bridge.py"),
    "trener": ROOT / "trener" / "trener_serwer.py",
}
ARGS = {"trener": ["--no-idle-exit"]}
CHECK_S = 3
TRIGGERS = {"restart-trener": "trener", "restart-bridge": "bridge", "restart-nadzorca": "supervisor"}
NO_WINDOW = 0x08000000


def log(msg):
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
    except OSError:
        pass


def running_elsewhere(script: Path) -> bool:
    """True if some other process already runs this script (e.g. started by hand)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
             "Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW).stdout
    except Exception:
        return False
    return any(script.name.lower() in line.lower() for line in out.splitlines())


def take_triggers(root: Path = ROOT) -> set:
    """Names asked to restart by a trigger file; the files are removed (each asks once)."""
    asked = set()
    for fname, name in TRIGGERS.items():
        f = root / fname
        if f.exists():
            try:
                f.unlink()
            except OSError:
                continue
            asked.add(name)
    return asked


def stop_outside(script: Path) -> None:
    """End a copy of `script` this supervisor did not start (e.g. Trener.bat)."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
         f"Where-Object {{ $_.CommandLine -like '*{script.name}*' }} | "
         "ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }"],
        capture_output=True, timeout=30, creationflags=NO_WINDOW)


def main():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, "Local\\CodexKeystationSupervisor")
    if not mutex or ctypes.get_last_error() == 183:
        log("already running - exit")
        return
    log(f"START supervisor, python {PYTHONW}")
    procs, backoff, next_try = {}, {k: CHECK_S for k in SERVICES}, {k: 0.0 for k in SERVICES}
    for name, script in SERVICES.items():
        if running_elsewhere(script):
            log(f"{name}: already running (started outside supervisor) - watching only")
            procs[name] = None
    while True:
        asked = take_triggers()
        if "supervisor" in asked:
            log("restart-nadzorca: starting a fresh supervisor, this one exits")
            kernel.CloseHandle(ctypes.c_void_p(mutex))
            subprocess.Popen([str(PYTHONW), str(Path(__file__).resolve())], cwd=str(ROOT), creationflags=NO_WINDOW)
            return
        for name in asked & set(SERVICES):
            p = procs.get(name)
            log(f"restart-{name}: stopping it, it starts again with the code on disk")
            if p is not None and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
            elif name in procs:
                stop_outside(SERVICES[name])
            procs.pop(name, None)
            next_try[name] = 0.0
            backoff[name] = CHECK_S
        for name, script in SERVICES.items():
            p = procs.get(name)
            if name in procs and p is None:
                if time.time() < next_try[name]:
                    continue
                if running_elsewhere(script):
                    next_try[name] = time.time() + 30
                    continue
                log(f"{name}: outside copy is gone")
                procs.pop(name)
                p = None
            if p is not None and p.poll() is None:
                continue
            if p is not None:
                err = (ROOT / f"{name}.stderr.log")
                tail = err.read_text(encoding="utf-8", errors="replace")[-600:] if err.exists() else ""
                log(f"{name}: EXITED code {p.returncode}. stderr tail: {tail.strip()!r}")
                procs.pop(name)
                backoff[name] = min(backoff[name] * 2, 60) if p.returncode else CHECK_S
                next_try[name] = time.time() + backoff[name]
            if time.time() < next_try[name]:
                continue
            if not script.exists():
                log(f"{name}: script missing {script}")
                next_try[name] = time.time() + 60
                continue
            err = open(ROOT / f"{name}.stderr.log", "w", encoding="utf-8")
            procs[name] = subprocess.Popen([str(PYTHONW), str(script), *ARGS.get(name, [])], cwd=str(script.parent),
                                           stdout=subprocess.DEVNULL, stderr=err,
                                           creationflags=NO_WINDOW)
            log(f"{name}: started pid {procs[name].pid}")
        time.sleep(CHECK_S)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"SUPERVISOR CRASH {exc!r}")
        raise
