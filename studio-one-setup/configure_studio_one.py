"""Install native Keystation mappings and a local MIDI transport input."""
from datetime import datetime
from pathlib import Path
import shutil
import uuid
import xml.etree.ElementTree as ET

root = Path.home() / "AppData/Roaming/PreSonus/Studio One 7"
settings = root / "MusicDevices.settings"
backup = Path(__file__).with_name("backups")
backup.mkdir(exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(settings, backup / f"MusicDevices-{stamp}.settings")

ns = {"x": "https://ccl.dev/xml"}
ET.register_namespace("x", ns["x"])
tree = ET.parse(settings)
attrs = tree.find("./Section[@path='MusicDeviceList']/Attributes")
if attrs is None:
    raise RuntimeError("Unexpected Studio One MusicDevices format")

native_model = "{A36EF150-A004-4A1D-B6FD-617101EEE171}"
keyboard = next((e for e in attrs.findall("MusicDeviceDescription")
                 if e.get("receivePortID") == "DirectMusic/Receive/Keystation Pro 88"), None)
if keyboard is None:
    raise RuntimeError("Keystation input not found")
keyboard.set("name", "Keystation Pro 88")
keyboard.set("defaultInput", "1")
model = keyboard.find("UID[@{https://ccl.dev/xml}id='modelID']")
if model is None:
    raise RuntimeError("Keystation model ID not found")
model.set("uid", native_model)

bridge_name = "Codex Studio One Control"
bridge = next((e for e in attrs.findall("MusicDeviceDescription")
               if e.get("receivePortID") == f"DirectMusic/Receive/{bridge_name}"), None)
if bridge is None:
    bridge = ET.SubElement(attrs, "MusicDeviceDescription", {
        "name": bridge_name,
        "receivePortID": f"DirectMusic/Receive/{bridge_name}",
        "midiReceiveMask": "65535",
    })
    ET.SubElement(bridge, "UID", {f"{{{ns['x']}}}id": "modelID", "uid": native_model})
    ET.SubElement(bridge, "UID", {f"{{{ns['x']}}}id": "instanceID", "uid": "{" + str(uuid.uuid4()).upper() + "}"})

tree.write(settings, encoding="UTF-8", xml_declaration=True)
ET.parse(settings)
print(f"Configured native Keystation profile and {bridge_name}; backup: {backup}")
