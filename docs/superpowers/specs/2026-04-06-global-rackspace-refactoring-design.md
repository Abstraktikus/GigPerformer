# Global Rackspace Script — Refactoring & HAL Design Spec

**Date:** 2026-04-06
**Status:** Draft
**Scope:** `Global Rackspace V25.gpscript` → `Global Rackspace V26.gpscript`

---

## 1. Goals

1. **Thematic function ordering** respecting GPScript's declare-before-use constraint
2. **English section titles and annotations** — publication-ready, developer-audience style
3. **Hardware-neutral design** via capability-based Hardware Abstraction Layer (HAL)
4. **Consolidated configuration** — all user-configurable values in a dedicated section or external file
5. **No functional changes** — identical runtime behavior when configured with the same hardware

## 2. Constraints

- **Single file:** GPScript allows one script per rackspace; no include/import mechanism
- **Declare before use:** Functions must be declared before their first call (compiler error otherwise)
- **No structs/objects:** HAL data model uses parallel arrays
- **No early return:** Functions use `result` variable; no `return` statement
- **Wiring changes:** Block renames require manual adjustment in GP Wiring View
- **Note Prozessor 7.2.gpscript:** Not modified in this refactoring
- **Genos2_Control V2.gpscript:** Logic migrated into Global Rackspace; scriptlet becomes empty or removed

## 3. File Structure

### Var Block (Sections 1–12)

| Section | Content |
|---------|---------|
| 1. USER CONFIGURATION | Paths, OSC, debug toggle |
| 2. CORE CONSTANTS | MAX_LINKS, MAX_VSTS, ASCII_LOOKUP, string constants |
| 3. HAL — DEVICE & CONTROL REGISTRY | DEV_*, CTRL_*, SYSEX_*, capability flags, 4 generic DeviceIn slots |
| 4. PLUGIN BLOCKS & HARDWARE HANDLES | MidiInBlocks, PluginBlocks, VST arrays |
| 5. GUI WIDGET HANDLES | All Widget declarations |
| 6. ENGINE STATE & TIMERS | Runtime state, flags, timers, watchdogs |
| 7. CHANNEL MEMORY | Per-channel arrays (16 slots) |
| 8. ENGINE DATA — CONTROLLER MAP & ROUTING | Link DB, macro assignments, routing matrix |
| 9. ENGINE DATA — VST DATABASE & REPLACER | Publisher/VST arrays, replace queue |
| 10. ENGINE DATA — LOOPER | Per-channel loop state, timing, events |
| 11. ENGINE DATA — PROMPTER & TIMELINE | Bar/beat tracking, song sections, animations |
| 12. DISPLAY CACHES | Pre-built display line arrays |

### Function Sections (13–23)

Each section may only call functions from the same or earlier sections.

| Section | Content | Approx. functions |
|---------|---------|-------------------|
| 13. CORE UTILITIES | Debug, string, music theory, file, state, overlay helpers | ~84 (leaf) |
| 14. HAL RUNTIME | Config parser, device/control/sysex lookup, capability checks | ~15 (new) |
| 15. MIDI & CHANNEL ENGINE | Channel state, filters, note processor interface, KB split | ~20 |
| 16. DISPLAY ENGINE | All UI refresh/update functions | ~25 |
| 17. CONTROLLER MAP ENGINE | Link DB, macro system, HW mapping, editor, smart adapt | ~30 |
| 18. LOOPER ENGINE | Loop recording, playback, buffer management | ~20 |
| 19. PROMPTER & TIMELINE ENGINE | ChordPro, transport, song text, transpose, scrubber | ~35 |
| 20. VST REPLACER ENGINE | Database, browser, queue, replace execution | ~15 |
| 21. ORCHESTRATION | Solo/mute, smart bypass, crossfader, transport sync | ~15 |
| 22. HARDWARE INPUT PROCESSING | ProcessHardwareCC, ProcessHardwareNote, navigation dispatch | ~5 |
| 23. SONG & SNAPSHOT MANAGEMENT | Load, save, recovery, system reset | ~10 |

### Lifecycle Sections (24–26)

| Section | Content |
|---------|---------|
| 24. INITIALIZATION | 7-phase boot sequence |
| 25. WIDGET CALLBACKS | All On WidgetValueChanged handlers |
| 26. MIDI & SYSTEM CALLBACKS | MIDI events, OSC, BeatChanged, Song/Songpart, SystemEvent |

## 4. Hardware Abstraction Layer

### 4.1 Capability Flags (Bitfield)

```
CAP_NONE               = 0
CAP_TRANSPORT_SYNC     = 1     // Device has transport/style sync
CAP_SYSEX_TRIGGER      = 2     // Device sends SysEx we decode as triggers
CAP_CROSSFADER_TARGETS = 4     // Device channels affected by crossfader
CAP_SYSEX_PROFILES     = 8     // Device supports SysEx profile switching
CAP_JOYSTICK           = 16    // Device has X/Y joystick
CAP_MIDI_OUT           = 32    // We can send MIDI (PC, CC) to device
CAP_FEEDBACK_CC        = 64    // Device controls accept CC value echo
CAP_SYSEX_COMMANDS     = 128   // We can send SysEx commands to device
```

### 4.2 Device Registry (4 slots)

```
DEV_Active   : Boolean Array   // Is this slot configured?
DEV_Name     : String Array    // Human-readable name
DEV_MidiIn   : String Array    // MIDI input device name (for block matching)
DEV_MidiOut  : String Array    // MIDI output device name (for SendNowToMidiOutDevice)
DEV_Channel  : Integer Array   // Default MIDI channel
DEV_Caps     : Integer Array   // Capability bitfield
DEV_BlockIdx : Integer Array   // Mapped DeviceIn_X slot index
```

### 4.3 Control Registry (dynamic, up to 64)

```
CTRL_Count    : Integer        // Number of registered controls
CTRL_DevIdx   : Integer Array  // Owning device index
CTRL_Type     : Integer Array  // CTYPE_FADER / ENCODER / BUTTON / JOYSTICK / PAD
CTRL_CC       : Integer Array  // CC number (-1 = PitchBend)
CTRL_Channel  : Integer Array  // MIDI channel (-1 = use device default)
CTRL_RangeMin : Integer Array
CTRL_RangeMax : Integer Array  // 127, 16383, etc.
CTRL_Feedback : Integer Array  // FB_NONE / FB_CC / FB_SYSEX
CTRL_Label    : String Array   // Human-readable label from config
```

### 4.4 SysEx Command Registry (dynamic)

```
SYSEX_Count   : Integer
SYSEX_DevIdx  : Integer Array  // Owning device
SYSEX_Purpose : String Array   // Lookup key (e.g. "PROFILE_1", "VOICE_QUERY")
SYSEX_Data    : String Array   // Hex string (e.g. "F0 00 20 6B 7F 42 02 00 62 01 F7")
```

### 4.5 Config File Format (`DeviceConfig.txt`)

INI-style, parsed by `ParseDeviceConfig()` at boot:

```ini
[DEVICE:0]
Name=Genos2
MidiIn=Digital Keyboard-1
MidiOut=Digital Keyboard-1
Channel=0
Caps=TRANSPORT_SYNC,SYSEX_TRIGGER,CROSSFADER_TARGETS,JOYSTICK,MIDI_OUT

[DEVICE:1]
Name=MiniLab3
MidiIn=Minilab3 MIDI
MidiOut=Minilab3 MIDI
Channel=0
Caps=SYSEX_PROFILES,SYSEX_COMMANDS

[CONTROL:0]
Device=0
Label=Joystick Y
Type=JOYSTICK
CC=1
RangeMax=127
Feedback=NONE

[CONTROL:1]
Device=0
Label=Joystick X
Type=JOYSTICK
CC=-1
RangeMax=16383
Feedback=NONE

[CONTROL:2]
Device=1
Label=Main Encoder
Type=ENCODER
CC=114
RangeMax=127
Feedback=SYSEX

[CONTROL:3]
Device=1
Label=Button 1
Type=BUTTON
CC=118
RangeMax=1
Feedback=SYSEX

[SYSEX:0]
Device=1
Purpose=PROFILE_1
Data=F0 00 20 6B 7F 42 02 00 62 01 F7

[SYSEX:1]
Device=1
Purpose=PROFILE_5
Data=F0 00 20 6B 7F 42 02 00 62 05 F7

[SYSEX:2]
Device=1
Purpose=PROFILE_6
Data=F0 00 20 6B 7F 42 02 00 62 06 F7

[SYSEX:3]
Device=1
Purpose=PROFILE_7
Data=F0 00 20 6B 7F 42 02 00 62 07 F7
```

### 4.6 HAL Runtime Functions (Section 14)

```
ParseDeviceConfig()                                    // Boot: parse INI file
ParseCapString(capStr) → Integer                       // "A,B,C" → bitfield
DeviceHasCap(devIdx, cap) → Boolean                    // Capability check
GetDeviceIdxByName(name) → Integer                     // Lookup by name
GetDeviceMidiOut(devIdx) → String                      // Get output device name
IsDeviceConnected(devIdx) → Boolean                    // Check MidiOutDeviceExists
FindControl(devIdx, cc) → Integer                      // Find control by device + CC
GetControlType(ctrlIdx) → Integer                      // CTYPE_*
GetControlFeedback(ctrlIdx) → Integer                  // FB_*
GetDeviceSysEx(devIdx, purpose) → String               // Lookup SysEx hex string
SendDeviceSysEx(devIdx, purpose)                       // Send SysEx to device
MapDevicesToBlocks()                                   // Boot: map devices to MidiInBlock slots
GetDeviceIdxForBlock(blockIdx) → Integer               // Reverse lookup
```

### 4.7 Convenience Variables (set during Initialization)

```
arrangerDevIdx   : Integer = -1    // First device with CAP_TRANSPORT_SYNC, or -1
controllerDevIdx : Integer = -1    // First device with CAP_SYSEX_COMMANDS, or -1
```

These are set during Initialization by scanning `DEV_Active` in index order. The first matching device wins. Users who need finer control can assign these manually in the config file via a future `[ROLES]` section.

### 4.8 Fallback Behavior

If `DeviceConfig.txt` does not exist:
- All `DEV_Active` remain `false`
- All capability checks return `false`
- No SysEx is sent, no transport sync, no crossfader targets
- System runs as standalone GP setup
- Trace message: `"HAL: No DeviceConfig.txt found. Running in fallback mode."`

## 5. Migration Map

### 5.1 Removed Variables

| Old Variable | Replacement |
|---|---|
| `TargetSuffix` | `DEV_MidiIn[0]` from config |
| `MidiOutDeviceName` | `DEV_MidiOut[arrangerDevIdx]` |
| `ML3_OutDeviceName` | `DEV_MidiOut[controllerDevIdx]` |
| `GENOS_JOY_Y_UP/DN` | `CTRL_RangeMin/Max` for joystick controls |
| `GENOS_JOY_X_LEFT/RIGHT` | `CTRL_RangeMin/Max` for joystick controls |
| `ML3_ENC_CC` | `CTRL_CC` for encoder control |
| `ML3_BTN_CC_1/2` | `CTRL_CC` for button controls |
| `ML3_SYSEX_PROFIL_1/5/6/7` | `SYSEX_Data` registry |
| `IsGenos` | `arrangerDevIdx >= 0` |

### 5.2 Renamed Variables

| Old | New |
|---|---|
| `IncomingFromGenos` | `IncomingFromArranger` |
| `W_CF_Genos` | `W_CF_Arranger` |
| `DEF_CF_Genos` | `DEF_CF_Arranger` |

### 5.3 Renamed Functions

| Old | New |
|---|---|
| `SyncGenosToCurrentMap()` | `SyncArrangerToCurrentMap()` |
| `FireGenosTransportEcho()` | `FireArrangerTransportEcho()` |
| `FireDirectGenosTransport()` | `FireDirectArrangerTransport()` |
| `DecodeSysExName()` | `DecodeDeviceSysExName()` |

### 5.4 Renamed Blocks (requires Wiring changes)

| Old Block | New Block | Action |
|---|---|---|
| `MainMidiIn` | `DeviceIn_0` | Rename in Wiring |
| `MiniLab3` | `DeviceIn_1` | Rename in Wiring |
| `Genos2_Control` | `ExternalArranger` | Rename in Wiring |
| `BLK_GenosStyle` | `BLK_ArrangerSync` | Rename in Wiring |
| — | `DeviceIn_2` | Create new MidiInBlock |
| — | `DeviceIn_3` | Create new MidiInBlock |

### 5.5 Callback Migration

MIDI callbacks change from device-specific to generic slot-based:

```
// Before:
On NoteEvent(m : NoteMessage) From MiniLab3
   ProcessHardwareNote(m)

// After:
On NoteEvent(m : NoteMessage) From DeviceIn_1
   ProcessHardwareNote(1, m)
```

`ProcessHardwareCC` and `ProcessHardwareNote` gain a `devIdx` parameter and use capability-based dispatch instead of device-name checks.

## 6. Comment Style

- **Section headers:** `// ===...` (level 1), `// ---...` (level 2)
- **Function headers:** Only where signature is not self-explanatory; explain purpose, not mechanics
- **Inline comments:** English, concise, only where logic is non-obvious
- **Capability guards:** `// Guard: only execute if [device] supports [capability]`
- **TODOs:** `// TODO(HAL): description` for future work
- **No humor, no emojis** — factual, publication-ready

## 7. Initialization — 7-Phase Boot

| Phase | Purpose |
|---|---|
| 0. SAFETY LOCK | Prevent ghost recordings, lock faders |
| 1. PATHS | Derive all file paths including DeviceConfigFilePath |
| 2. HAL BOOTSTRAP | ParseDeviceConfig, MapDevicesToBlocks, detect connections, set convenience indices |
| 3. SYSTEM DEFAULTS | DEF_RECH, DEF_CF_Audio, DEF_CF_Arranger, factory NP capture |
| 4. ARRAYS & BLOCKS | BLK_MidiIn, BLK_NoteProcessor, BLK_VST, widget arrays, routing matrix |
| 5. DATABASE LOADING | HardwareMap, VstDatabase, MappingFile, CtrlMapList |
| 6. STATE RECOVERY | Queue processing, song snapshot recovery |
| 7. UI SYNC | Display refresh, OSC clear |

## 8. Dependency Rule

Each function section (13–23) may only call functions from the same or earlier sections:

```
Utilities (13) → HAL (14) → Channel (15) → Display (16) → Controller (17)
→ Looper (18) → Prompter (19) → VST Replacer (20) → Orchestration (21)
→ HW Input (22) → Song/Snapshot (23)
```

Within each section, functions are ordered by internal dependency layer (leaf functions first).

## 9. Deliverables

1. **`Global Rackspace V26.gpscript`** — fully refactored script
2. **`DeviceConfig.txt`** — example config for Genos2 + MiniLab3 setup
3. **Migration guide** — wiring changes checklist for the user

## 10. Out of Scope

- No new features added
- No changes to `Note Prozessor 7.2.gpscript`
- `Genos2_Control V2.gpscript` logic absorbed into Global Rackspace (scriptlet may be emptied/removed)
- No new Scriptlets (no Wiring topology changes beyond renames)
- No changes to existing config file formats (HardwareMap.txt, ControllerMaps.txt, VstDatabase.txt)
- No changes to widget labels or user-facing strings
