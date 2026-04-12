# Layer System, Unified ControllerMap & Smart Solo Enhanced

**Date:** 2026-04-12
**Status:** Design approved
**Scope:** Major architectural change — new layer system, unified ControllerMap syntax (absorbs HardwareMap), enhanced Smart Solo, overlay trigger engine, VST validation, LBL_ControllerInfo redesign

---

## 1. Overview

This design introduces a **hardware layer system** that multiplies the available controls on Device 0 (Genos2) by using configurable binary switches (SysEx, Note, or CC) as mode toggles. Two switches yield 4 layers (2²), giving 6 physical buttons the reach of 24 virtual buttons, and 9 physical sliders the reach of 27 virtual sliders with overlay functions.

Simultaneously, the **ControllerMap format is unified** — the separate `HardwareMap.txt` is eliminated, hardware sources move inline into `ControllerMaps.txt`, and a `[Map:Default]` section provides inheritance so song-specific maps only declare deltas.

**Smart Solo** is enhanced to consider both RECH routing input AND Manual zone (Upper/Lower/None) when deciding which channels to mute.

### Key Principles

- **HAL-agnostic:** Layer switch triggers are configurable per device (SysEx, Note, CC) — not hardcoded to Yamaha Genos2
- **Per-layer inheritance:** Song maps override individual layers independently; unchanged layers inherit from Default
- **Overlay functions are universal:** All system macros (Smart Solo, Strict Solo, Root, Octaver, Mute, Humanize, Scale, Range, Auto Sustain) are available on any control type (button or slider)
- **No backward compatibility:** Big Bang approach — old format files are not supported

---

## 2. DeviceConfig Extensions

### 2.1 LAYERSWITCH — Binary Toggle Triggers

New section defining incoming signals that toggle layer switches.

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

### 2.2 LAYERMAP — Switch Combination to Layer Number

Bitmask mapping: Switch 0 = bit 0, Switch 1 = bit 1, etc. Layer numbers are freely assignable (not tied to bitmask values). Extensible to N switches (2^N states).

```ini
[LAYERMAP:0]
Device=0
State_0=LAY0
State_1=LAY1
State_2=LAY2
State_3=LAY3
```

### 2.3 PERMANENT — Always-Active Bindings

Hardware functions identical across all ControllerMaps. These do not consume user macro slots.

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

### 2.4 OVERLAY — Layer-Level Actions

Actions that fire on layer activation, independent of any specific Macro binding.

```ini
[OVERLAY:0]
Device=0
Layer=3
Action=SYSTEM_TOGGLE_ON
```

Start configuration: Layer 3 (both switches ON) permanently activates SYSTEM_TOGGLE, eliminating the dead-man-switch foot cramp for home practice/sound design.

---

## 3. Unified ControllerMap Syntax

### 3.1 File Format

`ControllerMaps.txt` replaces both the old `ControllerMaps.txt` and `HardwareMap.txt`.

```
[Map:Default]     ← Base configuration, inherited by all song maps
[Map:SongName]    ← Overrides only, per-layer inheritance
```

### 3.2 Line Syntax

```
MacroLine   = "Macro" <idx> "=" [<Sources> ";"] <Bindings>
Sources     = <Source> { "&" <Source> }
Source      = "DEV" <devIdx> ":" ("BTN"|"SLD"|"ENC"|"JOY") <ctrlIdx>
Bindings    = <Binding> { "|" <Binding> }
Binding     = [<LayerPrefix>] <Target> [<Range>]
LayerPrefix = "LAY" <layerIdx> ":"
Target      = <VSTTarget> | <CCTarget> | <KeywordTarget> | <SysActTarget> | <OverlayTarget>
VSTTarget   = "VST" <vstIdx> ["_GRS"] ":" <paramIdx> [":" <label>]
CCTarget    = "Ch" <ch> ":CC" <cc> [":" <label>]
KeywordTarget = "CROSSFADER" | "SCRUBBER" | "VST_SCOPE" | "VST_BROWSE" | ...
SysActTarget  = "SYSACT_" <name>
OverlayTarget = <FuncName> ":CH" <ch>
FuncName    = "SMART_SOLO" | "STRICT_SOLO" | "ROOT" | "OCTAVER"
            | "USER_MUTE" | "HUMANIZE" | "SCALE" | "RANGE" | "AUTO_SUSTAIN"
Range       = "{" <min> "," <max> "}"
```

### 3.3 Binding Rules

- **No LAY prefix** = always active (fires in LAY0 and all other layers)
- **With LAY prefix** = only active when that layer is active
- **No Range** = default `{0.0, 1.0}` for normal bindings, `{1.0, 1.0}` for overlay functions
- **Multi-Device** (`&`) = all sources feed the same macro, last-write-wins on value
- **Isolation Rule** = SYSACT bindings are dropped when mixed with other targets **on the same layer**. The `|` separator between different `LAYn:` entries does NOT trigger the rule — each layer is evaluated independently. Example: `VST1_GRS:49 | LAY3:SYSACT_TRANSPORT_TOGGLE` is valid (different layers). `SYSACT_X | VST1_GRS:49` is invalid (both LAY0, SYSACT dropped).

### 3.4 Range-Based Trigger Logic

| Range | Type | Behavior |
|---|---|---|
| `{1.0,1.0}` | Point Max | Positional: ON at max, OFF when away |
| `{0.0,0.0}` | Point Min | Positional: ON at min, OFF when away |
| `{0.3,0.7}` | Partial | Positional: ON inside range, OFF outside |
| `{0.0,1.0}` | Full Range | Movement-Toggle with **10-second debounce** |

Multiple overlay ranges on the same slider enable multiple layers on one physical control:

```ini
Macro10 = DEV0:SLD3; VST1_GRS:48 | LAY1:SMART_SOLO:CH3{1.0,1.0} | LAY2:OCTAVER:CH3{0.0,0.0} | LAY3:ROOT:CH3{0.5,0.8}
```

### 3.5 Per-Layer Inheritance

Song maps override **per-layer, per-macro**. Unspecified layers inherit from `[Map:Default]`.

| Element in Song-Map | Behavior |
|---|---|
| No `DEV...;` prefix | Source inherited from Default |
| `DEV...;` prefix present | Source completely replaced |
| LAY0 bindings present | LAY0 replaced, other layers inherited |
| `LAYn:...` present | Only that layer replaced, others inherited |
| Macro not listed | Entire macro inherited from Default |

**Example — minimal song map:**

```ini
[Map:SlowHip80erDream]
; Only LAY0 overrides — all layer overlays inherited from Default
Macro1 = DEV0:BTN1; Ch11:CC74{0.0,1.0}
Macro2 = DEV0:BTN2; Ch11:CC71{0.0,1.0}
Macro14 = DEV0:SLD2; VST1_GRS:1:Level (p2){0.000,0.442}

; Targeted layer override (only LAY1 changed, LAY0/LAY2/LAY3 from Default):
; Macro4 = LAY1:ROOT:CH5{1.0,1.0}
```

### 3.6 Multi-Device

Multiple hardware sources feed one macro via `&`:

```ini
Macro15 = DEV0:SLD3 & DEV1:SLD1; VST1_GRS:2{0.0,1.0}
```

Rules:
- Last-write-wins on value (whichever device moves last sets the value)
- Layer overlays are per-macro, not per-source (one overlay state)
- Debounce is per-macro, not per-source
- Source inheritance: no `DEV...;` in song map = inherited; `DEV...;` present = fully replaced

### 3.7 BTN_Capture / BTN_Export_Log

- **Capture** records only LAY0 parameter ranges
- **Export** writes only LAY0 differences from Default
- Layer overlays are never exported (they come from Default)

---

## 4. Smart Solo Enhanced

### Current Logic

Mutes all channels sharing the same RECH input as the soloed channel.

### Enhanced Logic

Mutes all channels sharing **both** the same RECH input **AND** the same Manual zone (`Mem_Manual[]`: 0=None, 1=Upper, 2=Lower).

```
For each channel outCol (0-15):
  If Mem_SoloSmart[outCol] == 0:
    For each soloed channel soloCh:
      sameInput = any RECH row routes to both outCol and soloCh
      sameZone  = Mem_Manual[outCol] == Mem_Manual[soloCh]
      If sameInput AND sameZone:
        LooperSoloMute[outCol] = true
```

### Behavior Matrix

| Solo channel zone | Other channel zone | Result |
|---|---|---|
| Upper | Upper | Muted (same zone) |
| Upper | Lower | **Not muted** (different zone) |
| Upper | None (Arranger) | **Not muted** (Arranger free) |
| None | None | Muted (same zone) |

### User Control

- **No merge + no Manual:** Simple solo (all with same input muted)
- **Merge active:** Broader muting across all merge inputs
- **Manual set:** Restricts muting to same zone only
- **Left hand solo:** Upper channels soloed, Lower + Arranger (None) continue playing

---

## 5. Runtime Architecture

### 5.1 Layer State Machine

```
Global state:
  LayerSwitch_State[MAX_SWITCHES] : Integer    // 0=OFF, 1=ON
  ActiveLayer : Integer = 0                     // from LAYERMAP lookup

On incoming trigger (SysEx/Note/CC):
  1. Match against registered LAYERSWITCH OnData/OffData
  2. Update LayerSwitch_State[matchedIdx]
  3. Compute bitmask: bits = Switch0 | (Switch1 << 1) | ...
  4. Lookup LAYERMAP: ActiveLayer = State_<bits>
  5. Fire OVERLAY actions (e.g., SYSTEM_TOGGLE_ON for LAY3)
  6. Trace + OSC feedback on layer change
```

**New callback required:** `On SysExMessageReceived` — must be registered for all DeviceIn ports.

### 5.2 Layer-Aware Macro Dispatch

```
ExecuteHardwareMacro(macroIdx, value):
  For each binding on macroIdx:
    If binding has no LAY prefix:
      → Always execute (normal function)
    If binding has LAY prefix:
      → Only execute if ActiveLayer == binding.LayerIdx
  Slider value is ALWAYS passed through to normal function,
  regardless of overlay state.
```

### 5.3 Overlay Trigger Engine

```
FireOverlayFunction(funcName, channel, value, rangeMin, rangeMax):
  If rangeMin == 0.0 and rangeMax == 1.0:
    → Movement-Toggle with 10s debounce
  Else:
    → Positional: ON if value in [min,max], OFF otherwise
```

### 5.4 Movement-Toggle Debounce (10 seconds)

```
Per overlay binding:
  Debounce_Active : Boolean
  Debounce_Timer  : Double
  Debounce_State  : Integer (0=OFF, 1=ON)

On movement detected (and debounce not active):
  Toggle state (OFF→ON or ON→OFF)
  Set Debounce_Active = true, record timestamp

In On TimerTick:
  If TimeSinceStartup() - Debounce_Timer > 10.0:
    Debounce_Active = false
```

Slider value always passes through to underlying function regardless of debounce.

### 5.5 ActivateOverlay / DeactivateOverlay

Unified entry point for all overlay functions — calls the same functions as Strip Control UI and widget buttons:

| FuncName | Activate | Deactivate |
|---|---|---|
| `SMART_SOLO` | `Mem_SoloSmart[ch]=1`, clear Strict | `Mem_SoloSmart[ch]=0` |
| `STRICT_SOLO` | `Mem_SoloStrict[ch]=1`, clear Smart | `Mem_SoloStrict[ch]=0` |
| `ROOT` | `SetChordMode(ch, 1)` | `SetChordMode(ch, 0)` |
| `OCTAVER` | `SetOctaverMode(ch, 1)` | `SetOctaverMode(ch, 0)` |
| `USER_MUTE` | `Mem_UserMute[ch]=1` | `Mem_UserMute[ch]=0` |
| `HUMANIZE` | `SetHumanize(ch, 1)` | `SetHumanize(ch, 0)` |
| `SCALE` | `SetScaleQuantizer(ch, 1)` | `SetScaleQuantizer(ch, 0)` |
| `RANGE` | `SetVelocityRange(ch, 1)` | `SetVelocityRange(ch, 0)` |
| `AUTO_SUSTAIN` | `SetAutoSustain(ch, 1)` | `SetAutoSustain(ch, 0)` |

Followed by `UpdateSoloMuteState()` for Solo/Mute changes.

---

## 6. Parser Architecture

### 6.1 Parse Flow

```
At startup (Initialization):
  1. ParseDeviceConfig()       // + LAYERSWITCH, LAYERMAP, PERMANENT, OVERLAY
  2. ParseDefaultMap()         // [Map:Default] → DefaultMacro[256]

On song switch:
  3. Clone DefaultMacro → ActiveMacro[256]
  4. ParseSongMap(songName)   // [Map:SongName] → Delta
  5. MergePerLayer(ActiveMacro, Delta)
  6. RebuildReverseLookups()  // SysAction_ByMacro[], overlay binding index
  7. ResetDebounceTimers()
```

### 6.2 Internal Structure per Macro Slot

```
Per Macro (1-256):
  Source: DeviceIdx[], SourceType[], CtrlIdx[]   // multi-device
  Per Layer (0..MAX_LAYERS):
    BindCount, Bindings[]                         // {TargetType, Target, RangeMin, RangeMax}
```

### 6.3 Per-Layer Merge

```
MergePerLayer(active, delta):
  For each MacroX in delta:
    If delta has DEV-Source → replace active.Source completely
    For each LayerN (0..MAX_LAYERS):
      If delta has LAYn entries → replace active.LAYn completely
      // No LAYn in delta → Default remains
```

---

## 7. Impact on Existing Systems

| System | Impact |
|---|---|
| **DeviceConfig parser** | Extended: +LAYERSWITCH, +LAYERMAP, +PERMANENT, +OVERLAY |
| **ControllerMap parser** | Complete rewrite: unified syntax, Default inheritance, per-layer merge |
| **HardwareMap parser** | **Removed** |
| **SysEx handler** | **New** `On SysExMessageReceived` callback |
| **ExecuteHardwareMacro** | Layer-aware dispatch + overlay trigger engine |
| **ProcessHardwareCC** | Inline source lookup (replaces HardwareMap lookup) + PERMANENT check |
| **UpdateSoloMuteState** | Enhanced Smart Solo (RECH + Manual zone) |
| **On TimerTick** | +Debounce timer management |
| **Snapshot Load/Save** | No impact — layer state is transient |
| **Timeline Recording** | All overlay toggles ARE recorded (live performance = arrangement) |
| **LBL_ControllerInfo** | Redesign as hierarchical display with VST validation status (see Section 8) |
| **BTN_Capture/Export** | Captures/exports LAY0 only, layer overlays inherited from Default |
| **LoadControllerMap side-effect** | CurrentEditScope capture/restore still required in new parser |

---

## 8. LBL_ControllerInfo — Hierarchical Display

### 8.1 Display Structure

The display uses the existing scroll-slider pattern (`LBL_ControllerInfo` + `SLD_ControllerInfo`) with pre-computed line arrays. Content is organized in sections:

```
--- MAPPING: SlowHip80erDream ---
VST1: Omnisphere                              [OK]
VST3: Triton Extreme                          [NOT LOADED]

Macro 1 [Genos2:BTN1]:
  LAY0: (1 Target)
    -> VST1_GRS:48 Filter Cutoff {0.0,1.0}
  LAY1: ROOT:CH1 {1.0,1.0}
  LAY2: OCTAVER:CH1 {1.0,1.0}
  LAY3: CHANNEL_BOUND_LFO

Macro 6 [Genos2:BTN6]:
  LAY0: (3 Targets)
    -> VST1_GRS:53 Pad Level {0.0,1.0}
    -> Ch11:CC18 Phaser {0.0,1.0}
    -> Ch12:CC18 Phaser {0.0,1.0}
  LAY1: ROOT:CH14 {1.0,1.0}
  LAY2: OCTAVER:CH14 {1.0,1.0}
  LAY3: CROSSFADER

Macro 13 [Genos2:SLD1]:
  LAY0: (1 Target)
    -> VST1_GRS:0 Level (p1) {0.0,1.0}
  LAY1: SMART_SOLO:CH1 {0.0,1.0}
  LAY2: STRICT_SOLO:CH1 {0.0,1.0}

Macro 16 [Genos2:SLD4]:
  LAY0: (1 Target)
    -> Ch13:CC7 Volume Triton

Macro 17 [Genos2:SLD5]:
  LAY0: (1 Target)
    -> VST3_GRS:12 Reverb Send {0.0,1.0}   [BLOCKED: VST3 invalid]

--- CC BINDINGS (Permanent) ---
CC64: SYSTEM_TOGGLE
CC11: CROSSFADER

--- SYSTEM MACRO GROUPS ---
>> Macro 51-66: Looper (Ch 1-16) <<
>> Macro 67-82: Smart Solo (Ch 1-16) <<
>> Macro 83-98: Strict Solo (Ch 1-16) <<
>> Macro 99-114: User Mute (Ch 1-16) <<
...

--- HARDWARE ASSIGNMENTS ---
Macro 1 = Genos2:BTN1
Macro 2 = Genos2:BTN2
...
Macro 51 = Ch8:CC110
Macro 83 = Ch6:CC110
...
```

### 8.2 Display Rules

| Element | Rendering |
|---|---|
| **Header** | Map name, no active layer indicator |
| **VST status** | One line per declared VST: name + `[OK]` / `[NOT LOADED]` / `[MISMATCH]` |
| **DEV source** | Device name from DeviceConfig (e.g., "Genos2" not "DEV0") |
| **LAY0** | `(N Targets)` header, each target as indented `->` sub-line |
| **LAY1-N** | Single line: function, channel, range |
| **Parameter names** | Read from VST at runtime, stored in map (as today) |
| **Blocked bindings** | `[BLOCKED: VSTx invalid]` suffix on affected targets |
| **Section order** | User Macros → CC Bindings → SYS Macro Groups → HW Assignments |
| **HW Assignments** | Separate section at bottom for BTN_ScopeSection navigation/learning |

### 8.3 BTN_ScopeSection Navigation

`BTN_ScopeSection_Prev` / `BTN_ScopeSection_Next` continue to navigate through the Hardware Assignments section for hardware learning (e.g., training functions onto pads). This section is always present, even though hardware sources are now inline in the macro definitions.

---

## 9. VST Validation & Map Naming

### 9.1 Map Naming Convention

Maps are named after their target VST, not the slot number:

```
Old: [Map:Standard_VST1]     → slot-based, fragile
New: [Map:Omnisphere]         → VST-based, self-documenting
```

### 9.2 VST Declaration in Maps

Each map that references VST parameters must declare expected VSTs:

```ini
[Map:Omnisphere]
VST1=Omnisphere
Macro1 = VST1_GRS:48
Macro14 = VST1_GRS:0

[Map:SlowHip80erDream]
VST1=Omnisphere
VST3=Triton Extreme
Macro14 = VST1_GRS:1:Level (p2){0.000,0.442}
Macro16 = Ch13:CC7:Volume Triton
```

The `[Map:Default]` also declares its expected VSTs. Song maps inherit Default's VST declarations and can override them.

### 9.3 Validation at Map Load

```
On map load:
  1. Parse VST declarations (VST1=Omnisphere, VST3=Triton Extreme)
  2. For each declared VSTx:
     Compare with GetPluginName(BLK_VST[x])
  3. Result per VSTx: VALID / MISMATCH / NOT_LOADED
  4. Store validation result for display and execution
```

### 9.4 Execution with Partial Validity

Per-binding granularity — only VST-referencing bindings are affected:

| Binding type | VST valid | Behavior |
|---|---|---|
| VST parameter | Yes | Execute normally |
| VST parameter | No | **BLOCKED** — not executed, warning in display |
| CC routing | — | Always execute |
| Keyword (CROSSFADER, etc.) | — | Always execute |
| SYSACT role | — | Always execute |
| Overlay function | — | Always execute |

If **no** VST bindings are valid, all VST macros are blocked but CC/Keyword/SYSACT/Overlay bindings continue working.

### 9.5 BTN_SmartAdapt — New Logic

```
Old: SmartAdapt → search [Map:Standard_VST<currentSlot>]
New: SmartAdapt → GetPluginName(BLK_VST[CurrentVstScope])
     → search [Map:<PluginName>]
     → Found: Load with validation
     → Not found: Stay on current map, Trace warning
```

---

## 10. Timeline Recording

### All Overlay Toggles Are Recorded

Every overlay toggle (Smart Solo, Strict Solo, Root, Octaver, User Mute, Humanize, Scale, Range, Auto Sustain) is recorded in the Timeline. This is live performance — everything played is part of the arrangement.

If the user does not want a specific toggle recorded, they either:
- Don't play it during recording
- Delete it from the Timeline file afterwards

No per-function recording filter. No `IsRecordableOverlay()` check. Every `ActivateOverlay()` / `DeactivateOverlay()` call triggers `RecordTimelineEvent()`.

---

## 11. Start Configuration (Test Setup)

### Layer Switch Assignment

| Switch State | Harmony | Talk | Layer | Purpose |
|---|---|---|---|---|
| 0 (0b00) | OFF | OFF | LAY0 | Normal operation |
| 1 (0b01) | ON | OFF | LAY1 | Root + Smart Solo |
| 2 (0b10) | OFF | ON | LAY2 | Octaver + Strict Solo |
| 3 (0b11) | ON | ON | LAY3 | SYSTEM_TOGGLE_ON + system shortcuts |

### Default Button Assignments (from [Map:Default])

| Phys. Button | LAY0 | LAY1 | LAY2 | LAY3 |
|---|---|---|---|---|
| BTN1 | VST1_GRS:48 | ROOT:CH1 | OCTAVER:CH1 | CHANNEL_BOUND_LFO |
| BTN2 | VST1_GRS:49 | ROOT:CH2 | OCTAVER:CH2 | SYSACT_TRANSPORT_TOGGLE |
| BTN3 | VST1_GRS:50 | ROOT:CH3 | OCTAVER:CH3 | VST_SCOPE |
| BTN4 | VST1_GRS:51 | ROOT:CH11 | OCTAVER:CH11 | VST_BROWSE |
| BTN5 | VST1_GRS:52 | ROOT:CH12 | OCTAVER:CH12 | SCRUBBER |
| BTN6 | VST1_GRS:53 | ROOT:CH14 | OCTAVER:CH14 | CROSSFADER |
| BTN7-12 | System (SCRUBBER, SYSACT_VST_*, REC) | — | — | — |

### Default Slider Overlays (from [Map:Default])

| Phys. Slider | LAY0 | LAY1 | LAY2 |
|---|---|---|---|
| SLD1 | VST1_GRS:0 | SMART_SOLO:CH1 | STRICT_SOLO:CH1 |
| SLD2 | VST1_GRS:1 | SMART_SOLO:CH2 | STRICT_SOLO:CH2 |
| SLD3 | VST1_GRS:2 | SMART_SOLO:CH3 | STRICT_SOLO:CH3 |
| SLD4 | VST1_GRS:3 | SMART_SOLO:CH11 | STRICT_SOLO:CH11 |
| SLD5 | VST1_GRS:4 | SMART_SOLO:CH12 | STRICT_SOLO:CH12 |
| SLD6 | VST1_GRS:5 | SMART_SOLO:CH14 | STRICT_SOLO:CH14 |
| SLD7-9 | VST/Volume | — | — |

### Default Channel Map

BTN/SLD 1→CH1, 2→CH2, 3→CH3, 4→CH11, 5→CH12, 6→CH14

---

## 12. Example Files

See `examples/DeviceConfig_v2.txt` and `examples/ControllerMaps_v2.txt` for the complete reference configuration.

---

## 13. Open Items

- **LAYERSWITCH SysEx signatures:** Exact OnData/OffData for Harmony and Talk to be validated on running hardware
- **CHANNEL_BOUND_LFO / SYSACT_TRANSPORT_TOGGLE:** New system actions, implementation details TBD
- **Generic VST maps (VST4-9):** Use `VST<n>=*` wildcard — semantics TBD (match any VST in that slot, or skip validation?)
