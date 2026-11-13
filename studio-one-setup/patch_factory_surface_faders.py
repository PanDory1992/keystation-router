"""Adapt the existing PreSonus Keystation profile without changing device identity."""

from datetime import datetime
from pathlib import Path
import re
import shutil
import os

ROOT = Path(__file__).resolve().parent
SURFACE = Path("B:/Program Files/PreSonus/Studio One 7/devices/M-Audio/KeystationPro88/KSPro88.surface.xml")
CCS = (72, 73, 91, 93, 74, 71, 5, 84)
OLD = (75, 76, 77, 78, 79, 80, 81, 82)
PREVIOUS = (73, 72, 91, 93, 74, 71, 5, 84)
KNOBS = (10, 2, 12, 13, 75, 76, 92, 95)
OLD_KNOBS = (85, 86, 87, 88, 89, 90, 102, 103)


def main():
    original = SURFACE.read_bytes()
    updated = original
    for index, (old, previous, new) in enumerate(zip(OLD, PREVIOUS, CCS)):
        pattern = rb'(<Control name="fader\[' + str(index).encode() + rb'\]"[^>]*>\s*<MidiMessage status="Controller" address=")#[0-9A-Fa-f]{2}("/>)'
        match = re.search(pattern, updated)
        if match is None:
            raise SystemExit(f"Missing fader[{index}] definition; no changes made")
        current = updated[match.start(1) + len(match.group(1)):match.end(2) - len(match.group(2))]
        if current not in (f"#{old:02X}".encode(), f"#{previous:02X}".encode(), f"#{new:02X}".encode()):
            raise SystemExit(f"Unexpected fader[{index}] CC {current!r}; no changes made")
        updated = updated[:match.start()] + match.group(1) + f"#{new:02X}".encode() + match.group(2) + updated[match.end():]
    for index, (old, new) in enumerate(zip(OLD_KNOBS, KNOBS)):
        pattern = rb'(<Control name="knob\[' + str(index).encode() + rb'\]"[^>]*>\s*<MidiMessage status="Controller" address=")#[0-9A-Fa-f]{2}("/>)'
        match = re.search(pattern, updated)
        if match is None:
            raise SystemExit(f"Missing knob[{index}] definition; no changes made")
        current = updated[match.end(1):match.start(2)]
        if current not in (f"#{old:02X}".encode(), f"#{new:02X}".encode()):
            raise SystemExit(f"Unexpected knob[{index}] CC {current!r}; no changes made")
        updated = updated[:match.start()] + match.group(1) + f"#{new:02X}".encode() + match.group(2) + updated[match.end():]
    if updated == original:
        print("Already patched")
        return
    backup = ROOT / "backups" / f"KSPro88-factory-before-CC-patch-{datetime.now():%Y%m%d-%H%M%S}.surface.xml"
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(SURFACE, backup)
    temp = SURFACE.with_suffix(".surface.xml.tmp")
    try:
        temp.write_bytes(updated)
        os.replace(temp, SURFACE)
    finally:
        temp.unlink(missing_ok=True)
    assert SURFACE.read_bytes() == updated
    print(f"Patched eight faders and eight mixer knobs; exact backup: {backup}")


if __name__ == "__main__":
    main()
