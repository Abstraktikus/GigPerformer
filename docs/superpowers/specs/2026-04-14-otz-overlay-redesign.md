# OTZ / Overlay System — Complete Redesign

**Date:** 2026-04-14
**Status:** Design approved, ready for implementation plan
**Author:** Martin (spec), Claude (elaboration)

---

## 1. Problem Statement

The current OTZ (Overlay Trigger Zone) implementation conflates two distinct concepts:

1. **Base bindings** — own the control's value, write to VST/CC/KEYWORD targets.
2. **Overlays** — should ride *on top of* a base, triggering ON/OFF based on control position, without owning the value.

Current behavior treats overlays as just another binding type, leading to:
- Overlays consuming their own physical control instead of overlaying on existing ones
- No clean distinction between Point / Range / Directional trigger modes
- `{OTZ,1.0,1.0}` style syntax is cryptic; directional hacks via reversed ranges `{OTZ,1.0,0.0}` are undocumented
- Display shows `OCTAVER: 100%` instead of `OCTAVER: ON/OFF`
- No echo protection — GP-written values can rebound and falsely trigger OTZs
- 10s debounce is per-binding instead of per-control

This spec replaces the entire OTZ subsystem with a clean, keyword-based architecture.

## 2. Goals

- **Clear semantic separation** between base bindings (write) and overlays (read-only)
- **Readable syntax** using keywords (`MAX`, `MIN`, `DIR`, `RESET`) instead of numeric hacks
- **Per-control debounce** at 10s for all OTZ overlays on the same physical control
- **Echo protection** prevents GP→HW value writes from falsely triggering OTZs
- **Layer-persistent overlay state** — overlays stay ON/OFF across layer changes
- **Live-state display** in `LBL_ControllerInfo` for debugging
- **Hard migration** — no backward compatibility, old parser removed
- **Testcase-based starter ControllerMap** to validate all features

## 3. Non-Goals

- Preserve existing Default/Song/VST map inheritance logic (UNCHANGED)
- Preserve LFO special-storage-in-active-map behavior (UNCHANGED)
- Persist overlay state across GP restart (runtime-only)
- Modify Looper, Timeline, or other non-OTZ subsystems

---

## 4. Syntax Specification

### 4.1 Pipe-Separated Bindings

```
Macro<N> = DEV<d>:LAY<l>:<Label>; <binding1> | <binding2> | ...
```

- **First pipe-entry without OTZ prefix** = Base binding (owns value)
- **Subsequent pipe-entries with OTZ prefix** = Overlays (read-only)
- **Overlay-alone case**: single overlay target without OTZ prefix = becomes the base (own a value, can RESET)

### 4.2 Target Specification

Each binding is `TARGET{SPEC}` where `SPEC` is a comma-separated list of:

| Form | Meaning |
|------|---------|
| `x,y` (numeric) | Point-trigger if `x==y`, range-trigger if `x<y` |
| `MAX` | Shorthand for `1.0,1.0` (trigger at full right/up) |
| `MIN` | Shorthand for `0.0,0.0` (trigger at full left/down) |
| `DIR` | Directional: plus-movement = ON, minus-movement = OFF, 10s debounce |
| `RESET` | Hardware value-write back to 0.5 after fire (non-OTZ only) |
| `OTZ` | Mark binding as read-only overlay (must be first token in SPEC) |

### 4.3 Examples

```ini
; Simple base
Macro1 = DEV0:LAY0:Slider1; VST1_GRS:48{0.0,1.0}

; Super-Knob (multiple bases, no overlays)
Macro2 = DEV0:LAY0:Slider2; VST1_GRS:49{0.0,1.0} | VST1_GRS:50{0.0,0.5}

; Base + multiple OTZ overlays
Macro3 = DEV0:LAY0:Slider3; VST1_GRS:51{0.0,1.0} | ROOT:CH1{OTZ,MIN} | OCTAVER:CH1{OTZ,MAX} | HUMANIZE:CH1{OTZ,0.4,0.6}

; Base + directional OTZ
Macro4 = DEV0:LAY0:Enc2; VST1_GRS:55{0.0,1.0} | USER_MUTE:CH3{OTZ,DIR}

; Overlay-alone with directional + reset (motorized center-return)
Macro5 = DEV0:LAY0:Enc1; SMART_SOLO:CH3{DIR,RESET}

; Button overlay (range/keywords ignored at runtime — always ON/OFF)
Macro6 = DEV0:LAY0:BTN1; SMART_SOLO:CH4{OTZ,MAX}
```

### 4.4 Parser Rules

- A physical control (DEV:LAY:Label) may appear **only once per layer**. Last definition wins.
- Max **8 bindings** per macro (free mix of base and overlay).
- `RESET` + `OTZ` = parse warning, `RESET` ignored (OTZ can't write back).
- Base binding with `{OTZ,...}` = parse warning, OTZ stripped (first pipe-entry must be base).
- Unknown keyword in braces = parse warning, binding discarded.
- Numeric values outside [0.0, 1.0] = parse warning, clamped.
- **Hard migration**: old numeric directional syntax (`{OTZ,1.0,0.0}`, `{OTZ,0.5,0.5}`) no longer supported. Must be rewritten to `{OTZ,DIR}`.

---

## 5. Data Model

### 5.1 Extended `Mac_Layer_*` Arrays

New per-binding fields:

```gpscript
Mac_Layer_IsOTZ      : Boolean Array  // true = overlay (read-only), false = base
Mac_Layer_Mode       : Integer Array  // MODE_POINT / MODE_RANGE / MODE_DIR
Mac_Layer_HasReset   : Boolean Array  // true if RESET keyword present
```

Mode constants:

```gpscript
MODE_POINT : Integer = 0  // min==max, trigger at exact value
MODE_RANGE : Integer = 1  // min<max, trigger in range
MODE_DIR   : Integer = 2  // directional, plus=ON minus=OFF
```

Existing `Mac_Layer_RangeMin/Max` are used for POINT and RANGE modes, ignored for DIR.

### 5.2 Global Overlay State (Layer-Persistent)

```gpscript
MAX_OVERLAY_FUNCS : Integer = 16  // ROOT, OCTAVER, HUMANIZE, SMART_SOLO, STRICT_SOLO,
                                   // USER_MUTE, SCALE, RANGE, AUTO_SUSTAIN, ...
Overlay_FuncState : Integer Array = [256 zeros]
  // Indexed: funcIdx * 16 + channel
  // Values: 0 = OFF, 1 = ON
```

Total 256 entries = 16 functions × 16 channels. Fits within GPScript 256-element array limit.

**State persists across layer changes** — turning off an overlay requires explicit OFF trigger via a binding (in any layer, must reference same channel).

### 5.3 Per-Control Runtime State

```gpscript
Control_DebounceUntil  : Double Array  // [MAX_LAYER_MACROS] — 10s block after OTZ fire
Control_EchoBlockUntil : Double Array  // [MAX_LAYER_MACROS] — 200ms block after GP→HW write
Control_LastValue      : Double Array  // [MAX_LAYER_MACROS] — for DIR plus/minus detection
```

One timer slot per macro (= one per physical control per layer).

### 5.4 Binding Count Limit

`MAX_BINDINGS_PER_LAYER` raised from **2 → 8**. Total storage: `MAX_LAYER_MACROS × 8 = 800` entries per binding attribute array. Well within GPScript limits.

---

## 6. Parser Changes

### 6.1 `ParseSingleBinding` (line ~3322)

Extended to recognize keywords:

```
For each token in {...}:
   if token == "OTZ": set isOTZ = true (must be first token)
   elif token == "MAX": set mode = MODE_POINT, rangeMin = rangeMax = 1.0
   elif token == "MIN": set mode = MODE_POINT, rangeMin = rangeMax = 0.0
   elif token == "DIR": set mode = MODE_DIR
   elif token == "RESET": set hasReset = true
   elif token is numeric:
      collect into rangeMin/rangeMax
      if rangeMin == rangeMax: mode = MODE_POINT
      elif rangeMin < rangeMax: mode = MODE_RANGE
      else: warn "reversed range"
```

Persist `isOTZ`, `mode`, `hasReset` into `Mac_Layer_*` arrays.

### 6.2 `ParseMacroLine` (line ~3423)

Raise binding loop max from `MAX_BINDINGS_PER_LAYER = 2` to `8`. Detect base-vs-overlay:

```
firstBase = -1  // index of first non-OTZ binding
For each pipe-entry:
   parse into binding
   if not isOTZ and firstBase == -1: firstBase = current_index
   
If no firstBase and there's only one pipe-entry:
   // Overlay-alone case: promote to base
   Mac_Layer_IsOTZ[fi0] = false
```

### 6.3 Reverse Lookup

Unchanged from current (ch * 128 + cc, layer-aware). Linear fallback for ch≥2 stays.

---

## 7. Dispatch Logic

### 7.1 Entry Point

`ProcessHardwareCC` and `ProcessHardwareNote` resolve the macro via reverse lookup, then call:

```gpscript
DispatchMacro(macroIdx, val, isNote, isEcho)
```

`isEcho = true` when `Control_EchoBlockUntil[macroIdx] > TimeSinceStartup()`, OR when called from LFO (see §7.5).

### 7.2 Core Dispatch

```gpscript
Function DispatchMacro(macroIdx, val, isNote, isEcho):
   var otzFired : Boolean = false
   
   For b in 0..Mac_Layer_BindCount[macroIdx]-1:
      fi = MacLayerBindIdx(macroIdx, 0, b)
      
      if Mac_Layer_IsOTZ[fi]:
         // OTZ overlay path
         if isEcho: continue
         if TimeSinceStartup() < Control_DebounceUntil[macroIdx]: continue
         if isNote:
            // Button override: always ON/OFF
            result = FireOverlayDirect(fi, if val > 0 then 1 else 0 end)
         else:
            result = EvaluateOTZ(fi, val, macroIdx)
         if result.fired: otzFired = true
      else:
         // Base binding path
         ExecuteBase(fi, val)
         if Mac_Layer_HasReset[fi] and val != 0.5:
            SendResetToHW(macroIdx, fi)
   End
   
   Control_LastValue[macroIdx] = val
   
   if otzFired:
      // Overlay event already wrote feedback in EvaluateOTZ
      // Skip normal base feedback
   else:
      ShowBaseFeedback(macroIdx, val)
End
```

### 7.3 `EvaluateOTZ`

```gpscript
Function EvaluateOTZ(fi, val, macroIdx) Returns (fired : Boolean):
   funcIdx = FuncIdxFromTarget(Mac_Layer_Target[fi])
   channel = Mac_Layer_Channel[fi]
   stateIdx = funcIdx * 16 + channel
   currentState = Overlay_FuncState[stateIdx]
   var shouldFire : Integer = -1  // -1 = no change
   
   Select Mac_Layer_Mode[fi]:
      MODE_POINT Do
         if Abs(val - Mac_Layer_RangeMin[fi]) < 0.02: shouldFire = 1
         else: shouldFire = 0
      MODE_RANGE Do
         if val >= Mac_Layer_RangeMin[fi] and val <= Mac_Layer_RangeMax[fi]: shouldFire = 1
         else: shouldFire = 0
      MODE_DIR Do
         last = Control_LastValue[macroIdx]
         if val > last + 0.02: shouldFire = 1
         elsif val < last - 0.02: shouldFire = 0
   End
   
   if shouldFire != -1 and shouldFire != currentState:
      FireOverlayDirect(fi, shouldFire)
      Overlay_FuncState[stateIdx] = shouldFire
      Control_DebounceUntil[macroIdx] = TimeSinceStartup() + 10000
      ShowOverlayFeedback(Mac_Layer_Target[fi], Mac_Layer_Channel[fi], shouldFire)
      result.fired = true
   End
End
```

### 7.4 `FireOverlayDirect` and `ExecuteBase`

`FireOverlayDirect(fi, state)` — calls existing `ActivateOverlay` or `DeactivateOverlay` functions based on `Mac_Layer_Target[fi]` and `state`.

`ExecuteBase(fi, val)` — inline portion of current `ExecuteHardwareMacro` that handles VST / CC / KEYWORD / SYSACT dispatch for a single binding. No change to existing target-type handling.

### 7.5 `SendResetToHW`

```gpscript
Function SendResetToHW(macroIdx, fi):
   // Find the physical control's CC + channel from reverse lookup
   devIdx = Mac_SourceDev[MacSourceIdx(macroIdx, 0)]
   label = Mac_SourceLabel[MacSourceIdx(macroIdx, 0)]
   physCC = ResolveControlCC(devIdx, label)
   physCh = ResolveControlChannel(devIdx, label)
   
   SendNow(DeviceOut_0, CreateCC(physCh, physCC, 64))  // 64 = 0.5 of 127
   Control_EchoBlockUntil[macroIdx] = TimeSinceStartup() + 200
End
```

### 7.6 LFO Integration

Current `TickLFOs` calls `ExecuteHardwareMacro(a_idx + 1, a_val)`. This is replaced with:

```gpscript
DispatchMacro(a_idx + 1, a_val, false, true)  // isEcho=true
```

LFO-generated values are treated as echo → OTZs are skipped, base binding receives the value normally. Manual user movement still triggers OTZs.

---

## 8. Display

### 8.1 `LBL_MacroFeedback` — Runtime Status

Two paths, both with 1500ms auto-clear timer:

**Path A — Normal movement (no OTZ state change):**
```
"VST_GRS | Gain : 73%"
"VST_GRS | Gain : 73% | HUMANIZE ON"      ← if HUMANIZE state is ON
"VST_GRS | Gain : 73% | HUMANIZE ON | OCTAVER ON"
```

Built by `ShowBaseFeedback(macroIdx, val)`:
- First Base binding (skip OTZ) formats the "Name | Label : X%" part
- Enumerate remaining bindings on this macro, if `Mac_Layer_IsOTZ[fi]` and `Overlay_FuncState[...] == 1`, append ` | <TARGET> ON`

**Path B — OTZ state change event:**
```
"OCTAVER:CH1 : ON"
"ROOT:CH2 : OFF"
```

Built by `ShowOverlayFeedback(target, channel, state)`. Fires immediately when `EvaluateOTZ` triggers state change. Path B suppresses the subsequent Path A call for the same dispatch (see `otzFired` flag in §7.2).

### 8.2 `LBL_ControllerInfo` — Hierarchical Map Overview

Retains existing hierarchical structure (Macro → bindings). Extended to show OTZ markers, keywords, and live-state.

**Format:**
```
--- MAPPING: Default ---

VST1: Omnisphere  [OK]
VST3: Triton Extreme  [OK]

Macro 1 [Genos2:LAY0:Slider1]:
    -> VST_GRS Gain {0.0,1.0}

Macro 2 [Genos2:LAY0:Slider2]:
    -> VST_GRS Param1 {0.0,1.0}
    -> VST_GRS Param2 {0.0,0.5}

Macro 3 [Genos2:LAY0:Slider3]:
    -> VST_GRS Filter {0.0,1.0}
    -> OTZ OCTAVER:CH1 MAX ★

Macro 6 [Genos2:LAY0:Slider6]:
    -> VST_GRS Res {0.0,1.0}
    -> OTZ ROOT:CH2 MIN
    -> OTZ OCTAVER:CH2 MAX ★
    -> OTZ HUMANIZE:CH2 {0.4,0.6}

Macro 7 [Genos2:LAY0:Enc1]:
    -> SMART_SOLO:CH3 DIR + RESET ★

Macro 8 [Genos2:LAY0:Enc2]:
    -> VST_GRS Gain2 {0.0,1.0}
    -> OTZ USER_MUTE:CH3 DIR
```

**Formatting rules:**

| Element | Format |
|---------|--------|
| Base binding | `-> <target> <label> <range-or-keyword>` |
| OTZ overlay | `-> OTZ <target> <range-or-keyword>` |
| Mode keyword | `MAX` / `MIN` / `DIR` (plain text) |
| Numeric range | `{0.4,0.6}` (existing format) |
| RESET modifier | `+ RESET` suffix |
| DIR + RESET | `DIR + RESET` |
| Active overlay state | `★` suffix (Live-State indicator) |
| Inactive overlay | no suffix |

**Live-State refresh:** `UpdateControllerInfoDisplay()` is called when overlay state changes in `EvaluateOTZ`. Dirty flag pattern (same as existing `SoloMuteStateDirty`) to batch refreshes via TimerTick.

### 8.3 `LBL_LayerFeedback`

Unchanged — continues to show `LAY0` / `LAY1` / `LAY2` / `LAY3` on layer switch.

---

## 9. Edge Cases

### 9.1 Overlay-Alone Promotion

```ini
Macro7 = DEV0:LAY0:Enc1; SMART_SOLO:CH3{DIR,RESET}
```

Parser detects: no pipe-entry without OTZ prefix → first overlay target is promoted to base. `Mac_Layer_IsOTZ[fi] = false`, DIR logic applies, RESET writes hardware value back.

### 9.2 Parser Warnings (Trace only, DebugMode-gated)

- `RESET` + `OTZ` → `"PARSE: RESET ignored on OTZ binding (overlay is read-only)"`
- First binding with `{OTZ,...}` → `"PARSE: first binding can't be OTZ — stripped"`
- Unknown keyword → `"PARSE: unknown keyword '<token>' in binding — discarded"`
- Reversed range (`min > max`) → `"PARSE: reversed range {min,max} — treated as point {min,min}"`
- Values outside [0.0, 1.0] → `"PARSE: value <x> clamped to [0.0, 1.0]"`
- More than 8 pipe-entries → `"PARSE: truncated to 8 bindings (got <N>)"`

### 9.3 Layer-Wechsel

`UpdateActiveLayer()` does NOT touch `Overlay_FuncState[]`. Overlays stay in their current state. Layer-specific actions (`SYSTEM_TOGGLE_ON`) continue to work via existing `FireOverlayAction` / `DeactivateOverlayAction`.

### 9.4 LFO + OTZ

LFO writes via `DispatchMacro(..., isEcho=true)` → OTZs skipped → only base binding receives value. User drag triggers OTZs normally.

### 9.5 Snapshot-Save/Load

Overlay state is runtime-only. Song switch preserves state (no reset); GP restart loses state (accepted).

### 9.6 Multiple Base Bindings (SuperKnob)

All non-OTZ bindings execute in sequence with the same `val`. Display shows only the first base binding's name/label. All overlays display separately.

---

## 10. Migration

**Hard switch:** Old parser is removed entirely. The following old forms no longer work:

| Old | Must become |
|-----|-------------|
| `{OTZ,1.0,0.0}` (directional hack) | `{OTZ,DIR}` |
| `{OTZ,0.5,0.5}` (directional hack) | `{OTZ,DIR}` |
| `{OTZ,0.0,1.0}` (full-range hack) | `{OTZ,DIR}` (or remove if unintended) |

Forms that still work unchanged:
- `{0.0,1.0}` (full-range base) — unchanged
- `{OTZ,1.0,1.0}` (point at max) — still valid, but `{OTZ,MAX}` preferred
- `{OTZ,0.0,0.0}` (point at min) — still valid, but `{OTZ,MIN}` preferred
- `{OTZ,0.4,0.6}` (range) — unchanged

### 10.1 Testcase-Based Starter ControllerMap

`examples/ControllerMaps.txt` is replaced with a **testcase-driven map** covering every feature systematically. Martin will manually rebuild the "real" map from his hardware knowledge after validation.

```ini
[Map:Default]

; ========== BASE-BINDING TESTS ==========
Macro1 = DEV0:LAY0:Slider1; VST1_GRS:48{0.0,1.0}
Macro2 = DEV0:LAY0:Slider2; VST1_GRS:49{0.0,1.0} | VST1_GRS:50{0.0,0.5}

; ========== POINT-TRIGGER TESTS ==========
Macro3 = DEV0:LAY0:Slider3; VST1_GRS:51{0.0,1.0} | OCTAVER:CH1{OTZ,MAX}
Macro4 = DEV0:LAY0:Slider4; VST1_GRS:52{0.0,1.0} | ROOT:CH1{OTZ,MIN}

; ========== RANGE-TRIGGER TESTS ==========
Macro5 = DEV0:LAY0:Slider5; VST1_GRS:53{0.0,1.0} | HUMANIZE:CH1{OTZ,0.4,0.6}

; ========== MULTI-OVERLAY (Debounce) ==========
Macro6 = DEV0:LAY0:Slider6; VST1_GRS:54{0.0,1.0} | ROOT:CH2{OTZ,MIN} | OCTAVER:CH2{OTZ,MAX} | HUMANIZE:CH2{OTZ,0.4,0.6}

; ========== DIR-MODE TESTS ==========
Macro7 = DEV0:LAY0:Enc1; SMART_SOLO:CH3{DIR,RESET}
Macro8 = DEV0:LAY0:Enc2; VST1_GRS:55{0.0,1.0} | USER_MUTE:CH3{OTZ,DIR}

; ========== BUTTON TESTS ==========
Macro9 = DEV0:LAY0:BTN1; SMART_SOLO:CH4{OTZ,MAX}

; ========== LAYER-SCOPE TESTS ==========
Macro10 = DEV0:LAY1:Slider1; VST1_GRS:56{0.0,1.0} | ROOT:CH5{OTZ,MAX}
```

---

## 11. Test Plan

E2E test after implementation:

1. **Boot**: Parser loads without errors, `LayerSwitch_Count` and all `Mac_Layer_BindCount[]` plausible. `LBL_ControllerInfo` shows all macros with correct hierarchy.
2. **Base binding**: Slider1 → VST param reacts, `LBL_MacroFeedback` shows `"VST_GRS | Gain : X%"`.
3. **Super-Knob**: Slider2 → both VST params react simultaneously.
4. **Point MAX**: Slider3 to full right → `"OCTAVER:CH1 : ON"` appears, disappears after 1.5s. `LBL_ControllerInfo` shows `★`.
5. **Point MIN**: Slider3 to 0 → `"OCTAVER:CH1 : OFF"`, `★` disappears.
6. **Range**: Slider5 between 40-60% → HUMANIZE triggers ON, outside → OFF.
7. **Multi-overlay debounce**: Slider6 to MAX → OCTAVER ON + 10s block on Slider6. Within 10s: to MIN → ROOT should NOT fire. After 10s: to MIN → ROOT fires.
8. **DIR + RESET**: Enc1 right → SMART_SOLO ON, Enc physically returns to center (MIDI echo). Left → OFF, back to center.
9. **OTZ DIR**: Enc2 right → USER_MUTE ON (base continues). Left → OFF.
10. **Button overlay**: BTN1 press → `"SMART_SOLO:CH4 : ON"`. Release → OFF.
11. **Layer persistence**: Slider3 MAX (OCTAVER ON), switch to layer 1, back to layer 0 → OCTAVER still ON, `★` still visible.
12. **LFO + OTZ**: LFO on Macro3, LFO modulates through 1.0 → OCTAVER stays OFF (echo protection).
13. **Echo protection after RESET**: Enc1 triggers RESET → immediate incoming CC at 0.5 doesn't re-trigger.
14. **Live-State display**: Enable DebugMode, verify `LBL_ControllerInfo` updates `★` markers in real-time.

---

## 12. Implementation Scope

**In scope:**
- All new Mac_Layer_* arrays
- `ParseSingleBinding` / `ParseMacroLine` updates
- New `DispatchMacro`, `EvaluateOTZ`, `FireOverlayDirect`, `ExecuteBase`, `SendResetToHW` functions
- `ShowBaseFeedback`, `ShowOverlayFeedback` display helpers
- `UpdateControllerInfoDisplay` extension for OTZ hierarchy + Live-State
- LFO integration (pass `isEcho=true`)
- Testcase ControllerMap replacement

**Out of scope:**
- Default/Song/VST map inheritance (unchanged)
- LFO save-in-active-map special logic (unchanged)
- Looper, Timeline, SmartSolo internals (overlays call existing `ActivateOverlay`/`DeactivateOverlay`)
- Persistence of overlay state across GP restart

---

## 13. Risks

- **Hard migration breaks production map**: Accepted — Martin will rebuild manually.
- **Array size limit (256)**: Overlay_FuncState fits (16×16=256). Control_* arrays use MAX_LAYER_MACROS=100, fine.
- **Display refresh overhead**: Live-State `★` updates may flicker. Mitigated via dirty-flag pattern through TimerTick.
- **Echo timing**: 200ms block may be too short for slow MIDI paths. Adjustable constant if needed.
