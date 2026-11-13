"""Reinstall the verified Studio One surface map after a Studio One update.

Close Studio One first. This script preserves the currently installed map in backups/.
"""
from datetime import datetime
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "KSPro88.universal.surface.xml"
TARGET = Path(r"B:\Program Files\PreSonus\Studio One 7\devices\M-Audio\KeystationPro88\KSPro88.surface.xml")
BACKUPS = ROOT / "backups"

ET.parse(SOURCE)
if not TARGET.parent.is_dir():
    raise SystemExit(f"Studio One 7 device folder not found: {TARGET.parent}")
BACKUPS.mkdir(exist_ok=True)
if TARGET.exists():
    backup = BACKUPS / f"KSPro88-before-reinstall-{datetime.now():%Y%m%d-%H%M%S}.surface.xml"
    shutil.copy2(TARGET, backup)
    print(f"Backup: {backup}")
shutil.copy2(SOURCE, TARGET)
ET.parse(TARGET)
print(f"Installed: {TARGET}")
