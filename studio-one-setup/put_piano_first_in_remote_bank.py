"""Reorder only the saved song's control-surface bank, with an exact backup."""

from datetime import datetime
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile
import re
import zipfile

ROOT = Path(__file__).resolve().parent
SONG = Path.home() / "Documents/Studio One/Songs/2026-10-06 mikit/2026-10-06 mikit.song"
NAME = "Devices/mixerconsole.xml"
PIANO = "{4A744627-8374-4DA5-95DF-687BB3DDAEBD}"
VELCAL = "{DF756ADF-3716-4D3F-BE2A-B878D50F41C6}"
REMOTE = re.compile(rb'(<ChannelShowHidePreset x:id="RemoteBank"[^>]*>\s*<List x:id="visible">)(.*?)(</List>)', re.DOTALL)
UID = re.compile(rb'<UID uid="([^"]+)"\s*/>')


def main():
    running = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq Studio One.exe"], text=True, errors="replace")
    if "Studio One.exe" in running:
        raise SystemExit("Studio One is running; song changes deferred until it exits")
    with zipfile.ZipFile(SONG, "r") as archive:
        data = archive.read(NAME)
        all_names = archive.namelist()
    remote = REMOTE.search(data)
    if remote is None:
        raise SystemExit("RemoteBank missing; no changes made")
    if UID.sub(b"", remote.group(2)).strip():
        raise SystemExit("RemoteBank contains unrecognized data; no changes made")
    order = [uid.decode("ascii") for uid in UID.findall(remote.group(2))]
    if PIANO not in order or VELCAL not in order:
        raise SystemExit(f"Unexpected bank channels: {order}; no changes made")
    # Keep the other channels in their existing order. VelCal has no audio output.
    wanted = [PIANO] + [uid for uid in order if uid not in (PIANO, VELCAL)]
    if order == wanted:
        print("Pianoteq is already first and VelCal is excluded from the remote bank")
        return
    backup = ROOT / "backups" / f"2026-10-06-mikit-before-remote-bank-{datetime.now():%Y%m%d-%H%M%S}.song"
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(SONG, backup)
    linebreak = b"\r\r\n" if b"\r\r\n" in remote.group(2) else (b"\r\n" if b"\r\n" in remote.group(2) else b"\n")
    indent = b"\t\t\t\t"
    inner = linebreak + linebreak.join(indent + b'<UID uid="' + uid.encode("ascii") + b'"/>' for uid in wanted) + linebreak + b"\t\t\t"
    replacement = data[:remote.start(2)] + inner + data[remote.end(2):]
    with NamedTemporaryFile(dir=SONG.parent, suffix=".song", delete=False) as temp:
        temp_name = Path(temp.name)
    try:
        with zipfile.ZipFile(SONG, "r") as source, zipfile.ZipFile(temp_name, "w") as target:
            for info in source.infolist():
                target.writestr(info, replacement if info.filename == NAME else source.read(info.filename))
        with zipfile.ZipFile(temp_name, "r") as check:
            assert check.testzip() is None
            assert check.namelist() == all_names
            check_remote = REMOTE.search(check.read(NAME))
            assert check_remote is not None
            assert [x.decode("ascii") for x in UID.findall(check_remote.group(2))] == wanted
        temp_name.replace(SONG)
    finally:
        temp_name.unlink(missing_ok=True)
    print(f"Pianoteq is now first in RemoteBank. Exact backup: {backup}")


if __name__ == "__main__":
    main()
