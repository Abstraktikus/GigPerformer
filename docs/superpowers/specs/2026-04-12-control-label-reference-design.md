# Control Label Reference — Design Spec

**Date:** 2026-04-12
**Status:** Design approved
**Scope:** Replace BTN/SLD/ENC type+number in ControllerMap with DeviceConfig Label reference

---

## 1. Problem

The ControllerMap syntax `DEV0:LAY1:BTN1` puts the control TYPE in the ControllerMap. This duplicates info from DeviceConfig, forces the user to know control types, and misrepresents the Genos2 (which has encoders, not buttons).

## 2. Solution

ControllerMap references controls by their **Label** from DeviceConfig. The Label is a free-form string, unique per device.

```
Old: Macro1 = DEV0:LAY0:BTN1; VST1_GRS:48{0.0,1.0}
New: Macro1 = DEV0:LAY0:Enc1; VST1_GRS:48{0.0,1.0}
```

## 3. Control Types

| Type | Physical | Value Range |
|---|---|---|
| `FADER` | Slider/linear | 0-127 |
| `ENCODER` | Rotary knob (endless) | Relative |
| `BUTTON` | Press/release | 0/127 |
| `JOYSTICK` | Axis (directional) | Range-dependent |
| `PAD` | Velocity-sensitive | 0-127 |

## 4. Genos2 Control Layout (19 controls)

```ini
[CONTROL:0]  Device=0, Label=JoyUp,    Type=JOYSTICK, CC=1,  RangeMin=64, RangeMax=127
[CONTROL:1]  Device=0, Label=JoyDown,  Type=JOYSTICK, CC=1,  RangeMin=0,  RangeMax=63
[CONTROL:2]  Device=0, Label=JoyLeft,  Type=JOYSTICK, CC=-1, RangeMin=0,  RangeMax=8191
[CONTROL:3]  Device=0, Label=JoyRight, Type=JOYSTICK, CC=-1, RangeMin=8192, RangeMax=16383
[CONTROL:4]  Device=0, Label=Enc1,     Type=ENCODER,  CC=...
[CONTROL:5]  Device=0, Label=Enc2,     Type=ENCODER,  CC=...
[CONTROL:6]  Device=0, Label=Enc3,     Type=ENCODER,  CC=...
[CONTROL:7]  Device=0, Label=Enc4,     Type=ENCODER,  CC=...
[CONTROL:8]  Device=0, Label=Enc5,     Type=ENCODER,  CC=...
[CONTROL:9]  Device=0, Label=Enc6,     Type=ENCODER,  CC=...
[CONTROL:10] Device=0, Label=Fader1,   Type=FADER,    CC=...
[CONTROL:11] Device=0, Label=Fader2,   Type=FADER,    CC=...
[CONTROL:12] Device=0, Label=Fader3,   Type=FADER,    CC=...
[CONTROL:13] Device=0, Label=Fader4,   Type=FADER,    CC=...
[CONTROL:14] Device=0, Label=Fader5,   Type=FADER,    CC=...
[CONTROL:15] Device=0, Label=Fader6,   Type=FADER,    CC=...
[CONTROL:16] Device=0, Label=Fader7,   Type=FADER,    CC=...
[CONTROL:17] Device=0, Label=Fader8,   Type=FADER,    CC=...
[CONTROL:18] Device=0, Label=Fader9,   Type=FADER,    CC=...
```

9 Assignable Buttons exist but are currently Genos-internal (not mapped to GP).

## 5. Parser Resolution

```
ControllerMap line: "DEV0:LAY0:Enc1"
  1. devIdx = 0
  2. layer = 0
  3. label = "Enc1"
  4. Search CTRL_Label[] where CTRL_DevIdx == devIdx and CTRL_Label == label
  5. Found → CTRL_CC[match] = physical CC
  6. Register in Mac_ReverseLookup_L0[physCC] = macroIdx
```

## 6. Code Changes

| Component | Change |
|---|---|
| `ParseMacroSource` | Parse label string instead of type+number |
| `ResolveControlCC` | Match by label instead of type+index |
| `ResolveControlChannel` | Match by label instead of type+index |
| `Mac_SourceType[]` | Rename to `Mac_SourceLabel[]` (String) |
| `Def_Mac_SourceType[]` | Rename to `Def_Mac_SourceLabel[]` |
| `UpdateControllerInfoDisplay` | Show label in source description |
| `CloneDefaultToActive` | Copy label instead of type |
| `examples/ControllerMaps.txt` | All BTN→Enc, SLD→Fader |
| `examples/DeviceConfig.txt` | Ensure all controls have meaningful labels |

## 7. What does NOT change

- Layer system (LAY in source, per-layer lookup)
- OTZ marker
- Overlay engine
- Everything downstream of ExecuteHardwareMacro
- RebuildReverseLookups (uses ResolveControlCC which is updated)
- InitMacroArrays (array sizes unchanged)
