"""Panel Keystation (Claude, 15.11.2026): one window on the desktop for the router and its helpers.

  * what runs: router (and the keyboard), Studio One bridge, Trener server, supervisor
  * restart each of them (the same trigger files the supervisor and the router act on:
    restart-router, restart-bridge, restart-trener, restart-nadzorca; the supervisor itself is
    started directly when it is not running)
  * the touch of the keyboard (as the C53 button), and shortcuts: Trener, bus preview, USB check,
    logs, the folder
The window reads the state when it opens, after every action and on "Odśwież"; it does not poll.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parent
PYTHONW = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "pythonw.exe"
NO_WINDOW = 0x08000000
SERVICES = [  # (key, label, script name, trigger file)
    ("router", "Router (klawiatura)", "pedal_router.py", "restart-router"),
    ("bridge", "Most Studio One", "studio_one_bridge.py", "restart-bridge"),
    ("trener", "Serwer Trenera", "trener_serwer.py", "restart-trener"),
    ("nadzorca", "Nadzorca", "keystation_supervisor.py", "restart-nadzorca"),
]
TOUCH = [("light", "Lekkie"), ("acoustic", "Akustyczne"), ("heavy", "Ciężkie"), ("moje", "Moje"), ("moje3", "Moje 3")]


# --- pure helpers (tests: test_panel.py) ------------------------------------------------------------------
def router_state(root: Path = ROOT, now: float | None = None) -> dict:
    """live.json of the router: fresh (written in the last 10 s), keyboard connected, touch."""
    try:
        d = json.loads((root / "live.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"fresh": False}
    age = (now or time.time()) - float(d.get("updated") or 0)
    return {"fresh": age < 10, "age": age, "connected": bool(d.get("connected")), "touch": d.get("touch")}


def write_command(want: dict, root: Path = ROOT) -> Path:
    """A command for the router (same as Keystation Status): written whole, then renamed."""
    cmd = root / "live-cmd.json"
    tmp = root / "live-cmd.json.tmp"
    tmp.write_text(json.dumps({"v": 1, "id": int(time.time() * 1000), "set": want}), encoding="utf-8")
    os.replace(tmp, cmd)
    return cmd


def trigger(name: str, root: Path = ROOT) -> Path:
    f = root / name
    f.write_text("", encoding="utf-8")
    return f


def running_scripts(lines: list[str]) -> set[str]:
    """Which of our scripts appear in the process command lines."""
    low = [x.lower() for x in lines]
    return {key for key, _, script, _ in SERVICES if any(script.lower() in x for x in low)}


# --- the system ---------------------------------------------------------------------------------------------
def process_lines() -> list[str]:
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Select-Object -ExpandProperty CommandLine"],
                             capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW).stdout
    except Exception:
        return []
    return out.splitlines()


def trener_version() -> str | None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:47810/api/now", timeout=1.5) as r:
            return json.loads(r.read() or b"{}").get("version")
    except Exception:
        return None


def start_supervisor() -> None:
    subprocess.Popen([str(PYTHONW), str(ROOT / "keystation_supervisor.py")], cwd=str(ROOT), creationflags=NO_WINDOW)


def open_path(p: Path) -> None:
    os.startfile(str(p))  # noqa: S606 (Windows: opens with the default program)


# --- the window ---------------------------------------------------------------------------------------------
class Panel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Panel Keystation")
        self.resizable(False, False)
        self.configure(padx=14, pady=12)
        style = ttk.Style(self)
        style.configure("H.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Ok.TLabel", foreground="#1f7a3a")
        style.configure("Bad.TLabel", foreground="#b3261e")
        self.rows = {}
        ttk.Label(self, text="Co działa", style="H.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        for i, (key, label, _, _) in enumerate(SERVICES, start=1):
            ttk.Label(self, text=label, width=20).grid(row=i, column=0, sticky="w", pady=2)
            st = ttk.Label(self, text="…", width=34)
            st.grid(row=i, column=1, sticky="w")
            ttk.Button(self, text="Restart", command=lambda k=key: self.restart(k)).grid(row=i, column=2, padx=(8, 0))
            self.rows[key] = st
        ttk.Separator(self).grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(self, text="Czucie klawiatury", style="H.TLabel").grid(row=7, column=0, columnspan=3, sticky="w")
        self.touch = tk.StringVar(value="")
        tf = ttk.Frame(self)
        tf.grid(row=8, column=0, columnspan=3, sticky="w", pady=(2, 0))
        for v, t in TOUCH:
            ttk.Radiobutton(tf, text=t, value=v, variable=self.touch, command=self.set_touch).pack(side="left", padx=(0, 10))
        ttk.Separator(self).grid(row=9, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(self, text="Otwórz", style="H.TLabel").grid(row=10, column=0, columnspan=3, sticky="w")
        of = ttk.Frame(self)
        of.grid(row=11, column=0, columnspan=3, sticky="w", pady=(2, 0))
        for text, fn in [("Trener", lambda: webbrowser.open("http://127.0.0.1:47810/")),
                         ("Szyna: podgląd", lambda: open_path(ROOT / "Szyna - podglad.bat")),
                         ("Sprawdź USB", lambda: open_path(ROOT / "Sprawdz USB klawiatury.bat")),
                         ("Log nadzorcy", lambda: open_path(ROOT / "supervisor.log")),
                         ("Folder", lambda: open_path(ROOT))]:
            ttk.Button(of, text=text, command=fn).pack(side="left", padx=(0, 6))
        bottom = ttk.Frame(self)
        bottom.grid(row=12, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.msg = ttk.Label(bottom, text="")
        self.msg.pack(side="left")
        ttk.Button(bottom, text="Odśwież", command=self.refresh).pack(side="right")
        self.refresh()

    def say(self, text):
        self.msg.configure(text=text)

    def refresh(self):
        self.say("Sprawdzam…")
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        procs = running_scripts(process_lines())
        r = router_state()
        ver = trener_version()
        self.after(0, lambda: self._show(procs, r, ver))

    def _show(self, procs, r, ver):
        def put(key, ok, text):
            self.rows[key].configure(text=text, style="Ok.TLabel" if ok else "Bad.TLabel")
        if "router" in procs and r.get("fresh"):
            put("router", r.get("connected"), "działa, klawiatura podłączona" if r.get("connected") else "działa, klawiatura ODŁĄCZONA")
        else:
            put("router", False, "nie działa" if "router" not in procs else "działa, ale nie odpowiada")
        put("bridge", "bridge" in procs, "działa" if "bridge" in procs else "nie działa")
        put("trener", bool(ver), f"działa, wersja {ver}" if ver else ("proces jest, strona nie odpowiada" if "trener" in procs else "nie działa"))
        put("nadzorca", "nadzorca" in procs, "działa (pilnuje reszty)" if "nadzorca" in procs else "nie działa: Restart go uruchomi")
        self.touch.set(r.get("touch") or "")
        self.say(time.strftime("Stan z %H:%M:%S"))

    def restart(self, key):
        name = dict((k, t) for k, _, _, t in SERVICES)[key]
        if key == "nadzorca" and "nadzorca" not in running_scripts(process_lines()):
            start_supervisor()
            self.say("Uruchamiam nadzorcę…")
        else:
            trigger(name)
            self.say("Restart zlecony…")
        self.after(6000, self.refresh)

    def set_touch(self):
        write_command({"touch": self.touch.get()})
        self.say("Czucie zmienione")
        self.after(1500, self.refresh)


if __name__ == "__main__":
    Panel().mainloop()
