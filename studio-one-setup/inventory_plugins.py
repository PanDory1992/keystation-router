"""Export every Studio One-scanned instrument/effect from its local cache."""
from collections import Counter
from pathlib import Path
import csv
import xml.etree.ElementTree as ET

source = Path.home() / "AppData/Roaming/PreSonus/Studio One 7/x64/Plugins-en.settings"
dest = Path(__file__).with_name("studio-one-plugins.csv")
tree = ET.parse(source)
rows = []
for section in tree.findall("Section"):
    version = section.find("./Attributes/Version")
    vendor = version.get("vendor", "") if version is not None else ""
    for cls in section.findall("./Attributes/List/ClassDescription"):
        category = cls.get("category", "")
        if category not in ("AudioSynth", "AudioEffect"):
            continue
        rows.append({
            "category": "Instrument" if category == "AudioSynth" else "Effect",
            "name": cls.get("name", ""),
            "vendor": vendor,
            "format_or_folder": cls.get("subCategory", ""),
            "scanner_path": section.get("path", ""),
            "class_id": cls.get("classID", ""),
        })
rows.sort(key=lambda r: (r["category"], r["vendor"].lower(), r["name"].lower()))
with dest.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"{len(rows)} scanned instruments/effects -> {dest}")
print(Counter(r["category"] for r in rows))
for vendor, count in Counter(r["vendor"] for r in rows).most_common():
    print(f"{vendor}: {count}")
