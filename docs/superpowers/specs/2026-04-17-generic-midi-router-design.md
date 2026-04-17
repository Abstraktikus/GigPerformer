# Generic MIDI Router — Single Source of Truth for All Hardware Input

**Date:** 2026-04-17
**Status:** Approved
**Scope:** Replace all hardcoded MIDI dispatch logic in callbacks with a data-driven generic router that reads from the unified DeviceConfig CONTROL registry.

## Problem

The MIDI callbacks (`On ControlChangeEvent`, `On PitchBendEvent`, `On SysExEvent`) contain hardcoded magic numbers for joystick thresholds (CC1, CC16, 12000, 4000, 100, 20), style feedback detection (CC5), and layer-switch matching. This logic is duplicated across Port A and Port B callbacks. The DeviceConfig defines controls with labels, CC numbers, and ranges, but the callbacks ignore this data entirely — two sources of truth that inevitably diverge.

Additionally, `[LAYERSWITCH:n]` sections exist as a separate data structure parallel to the `[CONTROL:n]` registry, despite both being "things that react to MIDI input."

## Design Principles

1. **One registry:** Every hardware input (fader, encoder, button, joystick axis, layer switch, style trigger) is a `[CONTROL:n]` entry in DeviceConfig
2. **One lookup:** All MIDI callbacks call a router function that looks up the control in `CTRL_*[]` and dispatches by type
3. **Zero magic numbers:** Thresholds, CC numbers, channels, and axis mappings come from the registry
4. **Zero duplication:** Port A and Port B callbacks are identical one-liners
5. **No legacy support:** Old `[LAYERSWITCH:n]` format is removed, not backwards-compatible

## Architecture

### Four Router Entry Points, One Registry

```
On ControlChangeEvent  → RouteCCEvent()      ─┐
On PitchBendEvent      → RoutePBEvent()       ├→ FindControlByCC() → CTRL_*[] → Dispatch
On NoteEvent           → RouteNoteEvent()     ┘
On SysExEvent          → RouteSysExEvent()    ──�� MatchSysEx()     → CTRL_*[] → Dispatch
```

All callbacks become one-liners that pass device index + event data to the appropriate router.

### Router Pipeline (Priority Order)

```
RouteCCEvent(deviceIdx, cc, value, channel, msg)
│
├─ 1. FindControlByCC(deviceIdx, cc, channel) → controlIdx or -1
│
├─ 2. JOYSTICK?       → DispatchJoystick(deviceIdx, controlIdx, value)
│                        ├─ SystemModeActive? → ProcessSystemNavigation()
│                        └─ else → PassThrough
│
├─ 3. LAYER_SWITCH?   → SetLayerSwitchState(switchIdx, on/off)
│                        └─ UpdateActiveLayer()
���
├─ 4. STYLE_TRIGGER?  → DispatchStyleTrigger(controlIdx, value)
│                        └─ EnablePlayhead()
│
├─ 5. FADER/ENCODER/BUTTON? → ProcessHardwareCC(msg)
│                               └─ Macro/Overlay dispatch (existing logic)
│
└─ 6. No match → ProcessHardwareCC(msg) + FeedLooper_CC(msg) + SendNow()
```

`RoutePBEvent` follows the same pipeline with `cc = -1` and PitchBend-specific passthrough (SendNow only, no ProcessHardwareCC).

`RouteNoteEvent` only matches `CTYPE_LAYER_SWITCH` with `TRIGGER_NOTE`; unmatched notes pass through via SendNow.

`RouteSysExEvent` matches `CTYPE_LAYER_SWITCH` with `TRIGGER_SYSEX` via SysEx pattern comparison; unmatched SysEx passes through to existing SysEx processing.

### Two Router Functions for CC vs PitchBend

CC and PitchBend are separate functions (not unified) because their passthrough semantics differ fundamentally:

- **CC passthrough:** `ProcessHardwareCC(msg)` + `FeedLooper_CC(msg)` + `SendNow(device, msg)` — requires `ControlChangeMessage`
- **PB passthrough:** `SendNow(device, msg)` only — requires `PitchBendMessage`

GPScript has no union types. Forcing both into one function would require type workarounds.

## DeviceConfig Changes

### New Control Types

| Type | Integer | Description |
|------|---------|-------------|
| `LAYER_SWITCH` | 5 | Binary toggle trigger (absorbs old `[LAYERSWITCH:n]`) |
| `STYLE_TRIGGER` | 6 | Style feedback pulse detection |

### New Fields for JOYSTICK Controls

| Field | Type | Description |
|-------|------|-------------|
| `ThresholdHigh` | Integer | Value at which "fired" triggers |
| `ThresholdLow` | Integer | Value at which reset (back to rest) triggers |
| `Axis` | String | `X` or `Y` |
| `Direction` | Integer | `+1` or `-1` on the axis |

### New Fields for LAYER_SWITCH Controls

| Field | Type | Description |
|-------|------|-------------|
| `TriggerType` | String | `CC`, `SYSEX`, or `NOTE` |
| `OnData` | String | SysEx pattern for ON (SYSEX only) |
| `OffData` | String | SysEx pattern for OFF (SYSEX only) |
| `SwitchIndex` | Integer | Bit position in LAYERMAP bitmask |

### New Fields for STYLE_TRIGGER Controls

| Field | Type | Description |
|-------|------|-------------|
| `TriggerType` | String | `CC` (currently the only option) |
| `Channel` | Integer | MIDI channel to match |

### CC Field Semantics

`CC` has extended meaning depending on context:

| Context | CC means |
|---------|----------|
| FADER/ENCODER/BUTTON | CC number |
| JOYSTICK (CC-based axis) | CC number |
| JOYSTICK (PitchBend axis) | -1 |
| LAYER_SWITCH (TriggerType=CC) | CC number |
| LAYER_SWITCH (TriggerType=NOTE) | Note number |
| LAYER_SWITCH (TriggerType=SYSEX) | -2 (unused, match via OnData/OffData) |
| STYLE_TRIGGER | CC number |

### Example: Full Genos2 Device Config (Controls Section)

```ini
; --- Joystick (4 virtual controls from 2 physical axes) ---

[CONTROL:0]
Device=0
Label=JoyUp
Type=JOYSTICK
CC=1
RangeMin=64
RangeMax=127
ThresholdHigh=100
ThresholdLow=20
Axis=Y
Direction=+1
Feedback=NONE

[CONTROL:1]
Device=0
Label=JoyDown
Type=JOYSTICK
CC=16
RangeMin=0
RangeMax=127
ThresholdHigh=100
ThresholdLow=20
Axis=Y
Direction=-1
Feedback=NONE

[CONTROL:2]
Device=0
Label=JoyLeft
Type=JOYSTICK
CC=-1
RangeMin=0
RangeMax=8191
ThresholdHigh=4000
ThresholdLow=4000
Axis=X
Direction=-1
Feedback=NONE

[CONTROL:3]
Device=0
Label=JoyRight
Type=JOYSTICK
CC=-1
RangeMin=8192
RangeMax=16383
ThresholdHigh=12000
ThresholdLow=12000
Axis=X
Direction=+1
Feedback=NONE

; --- Layer Switches (absorbs old [LAYERSWITCH:n] sections) ---

[CONTROL:20]
Device=0
Label=Harmony
Type=LAYER_SWITCH
TriggerType=SYSEX
OnData=F0 43 10 4C 04 00 0C 40 F7
OffData=F0 43 10 4C 04 00 0C 7F F7
SwitchIndex=0

[CONTROL:21]
Device=0
Label=Talk
Type=LAYER_SWITCH
TriggerType=SYSEX
OnData=F0 43 10 4C 10 00 0B 64 F7
OffData=F0 43 10 4C 10 00 0B 7F F7
SwitchIndex=1

; --- Style Trigger ---

[CONTROL:22]
Device=0
Label=StylePulse
Type=STYLE_TRIGGER
TriggerType=CC
CC=5
Channel=16
Feedback=NONE
```

## CTRL_*[] Registry Arrays

### Existing Arrays (unchanged)

- `CTRL_DevIdx[]` — Device index
- `CTRL_Label[]` — Human-readable label
- `CTRL_CC[]` — CC number / note number / -1 (PB) / -2 (SysEx)
- `CTRL_Type[]` — CTYPE_FADER / ENCODER / BUTTON / JOYSTICK / LAYER_SWITCH / STYLE_TRIGGER
- `CTRL_RangeMin[]`, `CTRL_RangeMax[]` — Value range
- `CTRL_Feedback[]` — Feedback type

### New Arrays

| Array | Type | Default | Used by |
|-------|------|---------|---------|
| `CTRL_ThreshHigh[]` | Integer | 0 | JOYSTICK |
| `CTRL_ThreshLow[]` | Integer | 0 | JOYSTICK |
| `CTRL_Axis[]` | String | "" | JOYSTICK |
| `CTRL_Direction[]` | Integer | 0 | JOYSTICK |
| `CTRL_Channel[]` | Integer | -1 | All (MIDI channel filter) |
| `CTRL_TriggerType[]` | Integer | TRIGGER_CC | LAYER_SWITCH, STYLE_TRIGGER |
| `CTRL_OnData[]` | String | "" | LAYER_SWITCH (SYSEX) |
| `CTRL_OffData[]` | String | "" | LAYER_SWITCH (SYSEX) |
| `CTRL_SwitchIndex[]` | Integer | -1 | LAYER_SWITCH |

### New Constants

```
CTYPE_LAYER_SWITCH  : Integer = 5
CTYPE_STYLE_TRIGGER : Integer = 6

TRIGGER_CC          : Integer = 0
TRIGGER_SYSEX       : Integer = 1
TRIGGER_NOTE        : Integer = 2
```

## Joystick State (Per-Device)

Joystick state moves from global singletons to per-device arrays, supporting multiple devices with joysticks:

| Array | Type | Description |
|-------|------|-------------|
| `Joy_XFired[]` | Integer | 0 / +1 / -1 per device |
| `Joy_YUpFired[]` | Boolean | Per device |
| `Joy_YDownArmTime[]` | Double | Cross-talk timer per device |
| `Joy_YDownFired[]` | Boolean | Per device |

### Cross-Talk Guard

The 120ms cross-talk timeout remains a code constant (`JOYSTICK_CROSSTALK_MS = 120.0`). It is universal human motor behavior and does not need per-device configuration.

The guard logic in `On TimerTick` iterates over devices with `CAP_JOYSTICK` capability and checks `Joy_YDownArmTime[deviceIdx]`.

## Layer-Switch State

`LayerSwitch_State[]` remains as a separate array indexed by `SwitchIndex`. It is not part of `CTRL_*[]` because it represents runtime state, not configuration.

`SetLayerSwitchState(switchIdx, newState)` centralizes:
- State change detection
- Cross-talk suppression (`IgnoreSwitchOffUntil[]`, 200ms)
- `UpdateActiveLayer()` trigger

The `[LAYERMAP:n]` section and `UpdateActiveLayer()` function remain unchanged.

## Callbacks After Migration

```gpscript
// === DEVICE 0 PORT A ===
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_0_A
    RouteCCEvent(0, GetCCNumber(m), GetCCValue(m), GetChannel(m), m)
End

On PitchBendEvent(m : PitchBendMessage) from DeviceIn_0_A
    RoutePBEvent(0, GetPitchBendValue(m), m)
End

On NoteEvent(m : NoteMessage) from DeviceIn_0_A
    RouteNoteEvent(0, GetNoteNumber(m), GetVelocity(m), GetChannel(m), m)
End

On SysExEvent(m : SysExMessage) from DeviceIn_0_A
    RouteSysExEvent(0, m)
End

// === DEVICE 0 PORT B === (identical, same deviceIdx)
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_0_B
    RouteCCEvent(0, GetCCNumber(m), GetCCValue(m), GetChannel(m), m)
End

On PitchBendEvent(m : PitchBendMessage) from DeviceIn_0_B
    RoutePBEvent(0, GetPitchBendValue(m), m)
End

On NoteEvent(m : NoteMessage) from DeviceIn_0_B
    RouteNoteEvent(0, GetNoteNumber(m), GetVelocity(m), GetChannel(m), m)
End

On SysExEvent(m : SysExMessage) from DeviceIn_0_B
    RouteSysExEvent(0, m)
End
```

## What Is Removed

### Hardcoded Logic in Callbacks
- Layer-switch loop in `On ControlChangeEvent from DeviceIn_0_A` (line ~17082-17107)
- Duplicated layer-switch loop in `DeviceIn_0_B`
- Style feedback CC5 check (line ~17110-17119)
- Joystick CC1/CC16 block (line ~17124-17138)
- Joystick PitchBend block (line ~17063-17069)
- Complete Port A / Port B duplication (lines ~17291-17304, ~17306ff)

### Separate Data Structures
- `LayerSwitch_DevIdx[]`, `LayerSwitch_Type[]`, `LayerSwitch_OnData[]`, `LayerSwitch_OffData[]`, `LayerSwitch_Label[]`, `LayerSwitch_Channel[]`, `LayerSwitch_Count` — absorbed into `CTRL_*[]`
- `ParseLayerSwitch()` function — absorbed into `ParseControl()`

### Global Singletons
- `Joy_PB_Fired`, `Joy_CC1_Fired`, `Joy_CC16_Fired`, `Joy_CC16_ArmTime` — replaced by per-device arrays

### Config Format
- `[LAYERSWITCH:n]` section type — replaced by `[CONTROL:n]` with `Type=LAYER_SWITCH`

## What Remains Unchanged

- `ProcessHardwareCC()` internals — already data-driven via ControllerMap
- `ProcessSystemNavigation()` — SYS-MODE logic, not part of routing
- `UpdateActiveLayer()` — consumes `LayerSwitch_State[]`, unchanged
- `[LAYERMAP:n]` config section — separate abstraction (state combination → layer selection)
- `FeedLooper_CC()` — called from CC passthrough path
- Cross-talk timeout value (120ms) — human motor constant

## Performance

No performance impact. `FindControlByCC()` loops ~20-30 integer comparisons (<0.01ms). The existing `ProcessHardwareCC()` already loops over 210+ macros per CC event. The bottleneck is always the action after dispatch (SetParameter, widget updates), never the dispatch decision.

## Related Documents

- `docs/DeviceConfig.md` — Device configuration reference (needs update)
- `docs/ControllerMap.md` ��� ControllerMap syntax reference
- `docs/superpowers/specs/2026-04-06-global-rackspace-refactoring-design.md` — Original HAL architecture
- `docs/superpowers/specs/2026-04-12-control-label-reference-design.md` — Control label reference
