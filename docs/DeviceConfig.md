# DeviceConfig Reference

This document covers `DeviceConfig.txt`: hardware device definitions, controls with labels, layer switches, output routing, style triggers, and SysEx song synchronization. For macro slots, ControllerMap binding syntax, overlay triggers, SYSACT roles, and SYS-MODE navigation, see `docs/ControllerMap.md`.

---

## 1. Device Definitions

Each physical MIDI device is declared in a `[DEVICE:<n>]` section in `DeviceConfig.txt`. Devices are indexed starting at 0.

```ini
[DEVICE:0]
Name=Genos2
MidiIn=Digital Keyboard-1
MidiIn:Aux=Genos2 USB MIDI
MidiOut=Digital Keyboard-1
Channel=0
Caps=TRANSPORT_SYNC,SYSEX_TRIGGER,CROSSFADER_TARGETS,JOYSTICK,MIDI_OUT,SYSEX_PROFILES,SYSEX_COMMANDS
```

### Fields

| Field | Required | Description |
|---|---|---|
| `Name` | Yes | Human-readable device name, used in Trace output and display |
| `MidiIn` | Yes | Primary MIDI input port name (must match a Gig Performer MIDI alias) |
| `MidiIn:Aux` | No | Auxiliary MIDI input port for devices with multiple USB endpoints |
| `MidiOut` | Yes | MIDI output port name |
| `Channel` | No | Default MIDI channel for the device (0-based, 0 = omni/all) |
| `Caps` | No | Comma-separated capability flags |

### Capability flags

| Flag | Purpose |
|---|---|
| `TRANSPORT_SYNC` | Device participates in transport start/stop synchronization |
| `SYSEX_TRIGGER` | Device sends/receives SysEx for layer switches and song sync |
| `CROSSFADER_TARGETS` | Device's channels are crossfader expression targets |
| `JOYSTICK` | Device has joystick axes mapped as controls |
| `MIDI_OUT` | Device accepts outbound MIDI (CC feedback, style triggers, SysEx commands) |
| `SYSEX_PROFILES` | Device supports SysEx profile recall (registration memory) |
| `SYSEX_COMMANDS` | Device supports SysEx command dispatch (song select, BPM sync) |

Capability flags are checked at runtime before executing device-specific logic. A device without `JOYSTICK` will never receive SYS-MODE navigation dispatch. A device without `MIDI_OUT` will never receive outbound CC or style trigger messages.

---

## 2. Controls and Labels

### Control definitions

Each physical control is defined in a `[CONTROL:<n>]` section in `DeviceConfig.txt`:

```ini
[CONTROL:4]
Device=0
Label=Enc1
Type=ENCODER
CC=17
Channel=13
```

Controls have **labels** -- free-form strings, unique per device. The ControllerMap references controls by label, not by type or CC number. This decouples the map from physical wiring.

### Control types

| Type | Physical form | Value range |
|---|---|---|
| `FADER` | Slider / linear pot | 0--127 |
| `ENCODER` | Rotary knob (endless) | Relative |
| `BUTTON` | Press / release | 0 / 127 |
| `JOYSTICK` | Directional axis | Range-dependent |
| `PAD` | Velocity-sensitive surface | 0--127 |

### Genos2 layout (19 controls)

- 4 joystick axes: `JoyUp`, `JoyDown`, `JoyLeft`, `JoyRight`
- 6 encoders: `Enc1` through `Enc6`
- 9 faders: `Fader1` through `Fader9`

### Parser resolution

When the ControllerMap parser encounters `DEV0:LAY0:Enc1`:

1. Extract device index (0), layer index (0), label string (`Enc1`).
2. Search DeviceConfig's `CTRL_Label[]` where `CTRL_DevIdx == 0` and `CTRL_Label == "Enc1"`.
3. Resolve to the physical CC number from `CTRL_CC[match]`.
4. Register in the appropriate per-layer reverse lookup array.

---

## 3. Layer System

### Layer switches

Layer switches are defined in DeviceConfig via `[LAYERSWITCH:<n>]` sections. Each switch is a binary toggle triggered by incoming SysEx, Note, or CC messages.

```ini
[LAYERSWITCH:0]
Device=0
Label=Harmony
Type=SYSEX
OnData=F0 43 10 4C 04 00 0C 40 F7
OffData=F0 43 10 4C 04 00 0C 7F F7

[LAYERSWITCH:1]
Device=0
Label=Talk
Type=SYSEX
OnData=F0 43 10 4C 04 00 16 7F F7
OffData=F0 43 10 4C 04 00 16 00 F7
```

Supported trigger types:

| Type | ON condition | OFF condition |
|---|---|---|
| `SYSEX` | Incoming matches `OnData` | Incoming matches `OffData` |
| `NOTE` | Velocity > 0 | Velocity = 0 |
| `CC` | Value > 63 | Value <= 63 |

### Bitmask to layer number

Switch states form a bitmask (Switch 0 = bit 0, Switch 1 = bit 1). The `[LAYERMAP:<n>]` section maps each bitmask state to a layer number:

```ini
[LAYERMAP:0]
Device=0
State_0=LAY0
State_1=LAY1
State_2=LAY2
State_3=LAY3
```

Two switches yield 4 layers (2^2). Extensible to N switches.

### Per-layer reverse lookup

Each macro declares exactly one layer in its source: `DEV0:LAY1:Enc1`. The same physical control on different layers maps to different macros. At runtime, per-layer reverse lookup arrays (`Mac_ReverseLookup_L0` through `Mac_ReverseLookup_L3`) resolve the active layer's physical CC to the correct macro index.

```
ProcessHardwareCC:
  cc = GetCCNumber(m)
  Select ActiveLayer:
    0: macroIdx = Mac_ReverseLookup_L0[cc]
    1: macroIdx = Mac_ReverseLookup_L1[cc]
    ...
  if macroIdx > 0: ExecuteHardwareMacro(macroIdx, val)
```

No layer check is needed inside `ExecuteHardwareMacro` -- the macro was already layer-correctly selected. All bindings on that macro fire unconditionally.

---

## 4. Permanent Bindings

`[PERMANENT]` sections in DeviceConfig define hardware functions that are always active, independent of the loaded ControllerMap. They do not consume user macro slots.

```ini
[PERMANENT:0]
Device=0
Source=CC64
Function=SYSTEM_TOGGLE

[PERMANENT:1]
Device=0
Source=CC11
Function=CROSSFADER
```

These bindings are checked before the ControllerMap reverse lookup in `ProcessHardwareCC`. CC64 always triggers SYSTEM_TOGGLE and CC11 always drives CROSSFADER, regardless of which song map is active.

---

## 5. Output Routing

Output routing controls how the script sends MIDI back to hardware devices. Three named streams separate outbound traffic by purpose, allowing independent port assignments for reliability and latency management.

```ini
Route:Volume=Babyface Midi Port 1
Route:Expression=Digital Keyboard-1
Route:Control=Digital Keyboard-1
```

### Route streams

| Stream | CC/Data | Purpose |
|---|---|---|
| `Route:Volume` | CC7 per-channel | Per-channel volume feedback. Separated to allow DIN MIDI routing when USB ports have reliability issues with high-frequency updates. |
| `Route:Expression` | CC11 per-channel | Crossfader expression output with quadratic scaling. Floats continuously as the crossfader moves -- benefits from a dedicated route to avoid contention. |
| `Route:Control` | All other outbound MIDI | Generic CCs, style trigger note pulses, SysEx commands -- everything that is not volume or expression. |

### Fallback rule

If a route is not declared in DeviceConfig, outbound messages for that stream fall back to the device's `MidiOut` port. This means a minimal DeviceConfig with only `MidiOut` works correctly -- routing is an optional optimization for setups with multiple MIDI interfaces.

### Runtime behavior

Routes are parsed once at boot during `ParseDeviceConfig()`. At runtime, the lookup from stream name to output port is O(1) via pre-resolved port references. There is no per-message string matching.

---

## 6. Style Triggers

Style triggers send short Note On/Off pulses to control an external arranger's style engine (start/stop, section changes, fills, breaks, tempo tap). They are defined in DeviceConfig alongside the device that receives them.

```ini
TriggerChannel=16
Trigger:TapTempo=13
Trigger:StartStop=14
Trigger:SyncStart=15
Trigger:Intro=16
Trigger:MainA=17
Trigger:MainB=18
Trigger:MainC=19
Trigger:MainD=20
Trigger:FillAB=21
Trigger:FillBA=22
Trigger:FillBC=23
Trigger:FillCB=24
Trigger:FillCD=25
Trigger:FillDC=26
Trigger:FillAA=27
Trigger:FillBB=28
Trigger:FillCC=29
Trigger:FillDD=30
Trigger:BreakA=31
Trigger:BreakB=32
Trigger:BreakC=33
Trigger:BreakD=34
Trigger:EndingA=35
Trigger:EndingB=36
Trigger:EndingC=37
Trigger:EndingD=38
Trigger:FadeInOut=39
Trigger:AccompMute=40
Trigger:BassHold=41
```

### Pulse format

Each trigger is sent as a **Note On** (velocity 127) followed by a **Note Off** (velocity 0) after a 50ms pulse delay on the configured `TriggerChannel`. The note number is the value assigned in the trigger definition (e.g., `Trigger:StartStop=14` sends Note 14).

### Transport sync

Only `Trigger:StartStop` is referenced directly by the transport synchronization logic in the script (via the constant `TRIG_START_STOP`). All other triggers are generic and configurable -- they are not hardcoded to any specific arranger brand. The trigger names (MainA, FillAB, etc.) follow Yamaha convention but the mechanism works with any arranger that accepts note triggers.

### Echo blocking

To prevent feedback loops, outgoing trigger pulses activate a **500ms echo suppression window**. During this window, incoming notes on `TriggerChannel` from the same device are silently discarded. This handles arrangers that echo back the trigger note as part of their style playback.

### Timeline recording

Style part changes (section switches, fills, breaks) are recorded as Timeline events when timeline recording is active. This allows song arrangements built from live style changes to be replayed.

---

## 7. SysEx Song Sync

Bidirectional SysEx communication between Gig Performer and the arranger workstation enables automatic song switching, registration memory recall, and BPM synchronization. Currently implemented for Yamaha Genos2; the SysEx parsing is device-specific but the sync framework is generic.

### Arranger to GP -- Song Select

When a registration or song is selected on the Genos2, it sends a Yamaha SysEx message (`0x43 0x73 0x01`, byte5 = `0x26`) containing the song/registration name as an embedded string.

GP decodes the song name from the SysEx payload and runs a three-stage matching process:

1. **Cache lookup** -- check `GenosMapping.txt` for a previously learned SysEx-to-song mapping. If found, instant match.
2. **Slug-based auto-match** -- normalize the decoded name into a slug and compare against the GP song list (song name + artist fields). Fuzzy matching handles minor naming differences.
3. **Unknown** -- if no match is found, the SysEx is logged with its decoded name but ignored. No song switch occurs.

On a successful match, GP switches to the matched song, loads the associated snapshot, and syncs the controller map. The entire chain (SysEx decode, match, song switch, snapshot load, map reload) completes within a single callback cycle.

**Auto-learning:** The first successful slug-based match is automatically written to `GenosMapping.txt` so future lookups hit the cache directly.

### Arranger to GP -- Registration Memory

The Genos2 sends a SysEx message (byte5 = `0x25`) when a registration memory button (0--9) is pressed. GP decodes the button index and:

- If timeline **recording** is active: calls `RecordTimelineEvent("RegMem", regNumber)` to create an anchor point.
- If timeline **playback** is active: jumps to the corresponding RegMem anchor point in the timeline, synchronizing the song position.
- **FaderSafetyTimer:** Registration switches lock fader input for 800ms to prevent motor-fader ghost writes. The Genos2's motorized faders physically move during registration recall, generating spurious CC messages that would corrupt macro state without this guard.

### Arranger to GP -- BPM Sync

The Genos2 sends tempo SysEx (`0x43 0x7E 0x01`) containing the current tempo as microsecond timing data. GP extracts the BPM value and calls `SetBPM()` if the delta exceeds 0.5 BPM. Small fluctuations are ignored to prevent constant BPM jitter in the display.

### GP to Arranger -- Song Select

When GP switches songs (via setlist navigation or programmatic song change), it can send the corresponding SysEx to trigger the arranger's registration recall. This uses the same `GenosMapping.txt` lookup in reverse: GP song name maps to a cached SysEx payload, which is sent to the arranger's MIDI output port.

### GenosMapping.txt format

```
; SysEx ; DecodedName ; GPSongName
F0 43 73 01 52 26 ... F7 ; SlowHip80erDream ; SlowHip80erDream
```

The file lives in the Snapshots folder (same directory as `.ini` song files). It is auto-created on first successful match and grows incrementally as new songs are learned. Manual editing is supported for correcting mismatches or pre-populating mappings.

---

## 8. Troubleshooting

### "Layer switch doesn't work."

1. Check `DeviceConfig.txt` for the `[LAYERSWITCH:<n>]` section -- verify the `OnData` and `OffData` SysEx signatures match what your hardware actually sends.
2. For NOTE/CC type switches: confirm the correct channel and number.
3. Verify the `[LAYERMAP:<n>]` section maps all bitmask states to layer numbers.
4. Enable `DebugMode` -- layer changes produce Trace output on every switch event.

### "Output routing sends to the wrong port."

1. Verify the port name in `Route:Volume`, `Route:Expression`, or `Route:Control` exactly matches a Gig Performer MIDI alias (case-sensitive).
2. If no route is declared, the fallback is `MidiOut`. Check that `MidiOut` is set correctly in the `[DEVICE]` section.
3. Enable `DebugMode` and look for route resolution messages during boot.

### "Style trigger doesn't fire."

1. Check that `TriggerChannel` is set and the trigger name is spelled correctly.
2. Verify the device has the `MIDI_OUT` capability flag.
3. Confirm the arranger is listening on the correct channel and note number.
4. Check the 500ms echo suppression window -- rapid repeated triggers may be blocked.

### "SysEx song sync doesn't match."

1. Check `GenosMapping.txt` for a cached entry with the wrong GP song name. Delete or correct the line.
2. Enable `DebugMode` -- SysEx decode logs the extracted song name before matching.
3. Verify the GP song name and the decoded SysEx name are close enough for slug matching (punctuation and case are normalized).
4. If the arranger sends a different SysEx format, check that byte5 = `0x26` for song select and `0x25` for registration memory.

### "Faders jump on registration switch."

The FaderSafetyTimer (800ms) should suppress motor-fader ghost writes. If faders still jump, check that the safety timer constant in the script is long enough for your hardware's motor-fader travel time.

---

## Reference -- File Locations

| File | Path | Edited by hand? |
|---|---|---|
| Device Config | `DeviceConfig.txt` (next to gig file) | Yes (hardware setup) |
| Genos Mapping | `GenosMapping.txt` (Snapshots folder) | Auto-generated, manual edits OK |
| Global Rackspace script | `Global Rackspace.gpscript` | Yes (source) |

## Reference -- Related Documents

- **ControllerMap Reference:** `docs/ControllerMap.md` -- macro slots, binding syntax, OTZ, SYSACT, SYS-MODE, Smart Solo, VST validation, timeline recording
