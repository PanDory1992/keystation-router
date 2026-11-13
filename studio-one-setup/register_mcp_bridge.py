"""Register an additional Studio One control surface without replacing existing devices."""
from datetime import datetime
from pathlib import Path
import os
import shutil
import xml.etree.ElementTree as ET

PROFILE = Path(os.environ['APPDATA']) / 'PreSonus' / 'Studio One 7'
SETTINGS = PROFILE / 'MusicDevices.settings'
BACKUPS = Path(__file__).resolve().parent / 'backups'
MODEL = '{3CF4A272-66FD-48F1-9BBD-D223E971506A}'
INSTANCE = '{A467F432-903C-4DAD-A831-672E530B5397}'
PORT = 'DirectMusic/Receive/Codex Studio One Control'
X = '{https://ccl.dev/xml}'

root = ET.parse(SETTINGS).getroot()
attrs = root.find('./Section[@path="MusicDeviceList"]/Attributes')
if attrs is None:
    raise SystemExit('MusicDeviceList missing; no changes made')
for device in attrs.findall('MusicDeviceDescription'):
    uid = device.find(f'UID[@{X}id="modelID"]')
    if uid is not None and uid.get('uid') == MODEL:
        if device.get('receivePortID') != PORT:
            raise SystemExit('Existing MCP Bridge has a different port; no changes made')
        print('MCP Bridge already registered')
        raise SystemExit(0)

ET.register_namespace('x', 'https://ccl.dev/xml')
entry = ET.SubElement(attrs, 'MusicDeviceDescription', {
    'name': 'MCP Bridge', 'receivePortID': PORT, 'midiReceiveMask': '65535'
})
ET.SubElement(entry, 'UID', {f'{X}id': 'modelID', 'uid': MODEL})
ET.SubElement(entry, 'UID', {f'{X}id': 'instanceID', 'uid': INSTANCE})
BACKUPS.mkdir(parents=True, exist_ok=True)
backup = BACKUPS / f'MusicDevices-before-MCP-{datetime.now():%Y%m%d-%H%M%S}.settings'
shutil.copy2(SETTINGS, backup)
tmp = SETTINGS.with_name(SETTINGS.name + '.tmp')
ET.ElementTree(root).write(tmp, encoding='utf-8', xml_declaration=True)
os.replace(tmp, SETTINGS)
ET.parse(SETTINGS)
print(f'Registered MCP Bridge on {PORT}; backup: {backup}')
