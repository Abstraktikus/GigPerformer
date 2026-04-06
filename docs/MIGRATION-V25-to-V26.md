# Migration Guide: V25 → V26

## Prerequisites
- Gig Performer 5.x
- Backup your .gigfile before making changes

## Step 1: Wiring Changes (GP Wiring View)

Rename these blocks in the Wiring View:

| Old Name | New Name | Type |
|---|---|---|
| MainMidiIn | DeviceIn_0 | MidiInBlock |
| MiniLab3 | DeviceIn_1 | MidiInBlock |
| Genos2_Control | ExternalArranger | PluginBlock (Scriptlet) |
| BLK_GenosStyle | BLK_ArrangerSync | PluginBlock |

Create these new blocks:

| Name | Type | Notes |
|---|---|---|
| DeviceIn_2 | MidiInBlock | Empty, for future hardware |
| DeviceIn_3 | MidiInBlock | Empty, for future hardware |

## Step 2: File Placement

Place these files in your Snapshots folder (same folder as HardwareMap.txt):
- `DeviceConfig.txt` — edit to match your hardware

## Step 3: Script Replacement

Replace `Global Rackspace V25.gpscript` with `Global Rackspace V26.gpscript` in the Global Rackspace script editor.

## Step 4: Verification

1. Open the script editor — it should compile without errors
2. Check the log window for: `HAL: Device Genos2 connected.`
3. Test basic functions: channel switching, looper, VST browser
4. Test hardware: joystick, encoder, buttons
