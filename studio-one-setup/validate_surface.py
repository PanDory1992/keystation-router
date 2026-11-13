"""Static safety checks for the Keystation Pro 88 Studio One surface."""
from pathlib import Path
import xml.etree.ElementTree as ET

profile = Path(__file__).with_name("KSPro88.universal.surface.xml")
root = ET.parse(profile).getroot()
controls = {c.get("name"): c for c in root.findall("./Controls/Control")}
assert len(controls) == 9 + 24 + 17 + 17 + 5, len(controls)

for element in root.findall("./Mappings//*[@control]"):
    name = element.get("control")
    assert name in controls, f"Undefined control: {name}"

messages = {}
for name, control in controls.items():
    midi = control.find("MidiMessage")
    assert midi is not None, f"No MIDI definition: {name}"
    key = (midi.get("status"), midi.get("address"))
    assert key not in messages, f"Duplicate MIDI message: {key}: {messages[key]} and {name}"
    messages[key] = name

mixer = [m for m in root.findall("./Mappings/DeviceMapping") if m.get("device") == "MixerConsole"]
assert len(mixer) == 1
bank = mixer[0].find("./ScrollBank[@target='AllBank']")
assert bank is not None and bank.get("pagesize") == "8"
strips = bank.findall("Strip")
assert len(strips) == 8
for i, strip in enumerate(strips):
    assert any(e.get("control") == f"fader[{i}]" and e.get("param") == "volume" for e in strip)
    assert any(e.get("control") == f"knob[{i}]" and e.get("param") == "pan" for e in strip)
    assert any(e.get("control") == f"pcReset[{i}]" and e.get("param") == "volume" for e in strip)
    assert controls[f"pcReset[{i}]"].find("MidiMessage").get("address") == f"#{i+8:02X}"

print("OK: XML parses, controls resolve, MIDI messages are unique, and the 8 channel strips align")
