# Octaver Range & VelocityFader

**Date:** 2026-04-09
**Status:** Draft
**Scope:** Note Prozessor Scriptlet + Global Rackspace Integration

## Problem

The Polyphonic Octave Generator (POG) generates clone notes that can exceed the musically useful range. Notes that are too low become muddy rumble, notes that are too high become shrill. Currently the only guard is `0 <= cloneNote <= 127` — the full MIDI range. There is no way to constrain octave clones to a useful range or fade them out at the edges.

## Solution

Add a configurable Range (min/max) for octave clone notes with optional VelocityFader that softly attenuates clones near the range boundaries. Implementation follows existing patterns: Learn buttons for range capture, label display via `GetLuxusLabel()`, toggle button for the fader.

## 1. Scriptlet Parameters (Note Prozessor)

Three new parameters in the POG section (section 8), inserted after `p_OctHigh`:

```
p_OctRangeMin  : Parameter 0 .. 127 = 0     // Lower boundary for clone notes
p_OctRangeMax  : Parameter 0 .. 127 = 127   // Upper boundary for clone notes
p_OctRangeFade : Parameter 0 .. 1 = 0       // VelocityFader toggle (default OFF)
```

**Defaults:** Range 0-127 (fully open, no clamping). Fader off. Existing behavior is preserved exactly.

**Factory Reset:** All three parameters reset to defaults. Added to the existing reset block alongside other POG parameters.

**Panic trigger:** Changes to `p_OctRangeMin` or `p_OctRangeMax` trigger `ExecutePanic()` — added to the existing `On ParameterValueChanged matching` block that already watches `p_Octaver, p_OctLow, ...`.

## 2. Helper Function: GetOctRangeVelocity

```
Function GetOctRangeVelocity(cloneNote : Integer, vel : Integer) Returns Integer
```

**Processing logic:**

1. **Range gate:** If `cloneNote < Round(p_OctRangeMin)` or `cloneNote > Round(p_OctRangeMax)` → return 0 (note suppressed).
2. **Fader bypass:** If `Round(p_OctRangeFade) == 0` or range span < 10 notes → return `vel` unchanged.
3. **Fade zone calculation** (fix 5 notes at each edge):
   - Lower fade: `cloneNote` in `[RangeMin .. RangeMin+4]` → factor = `(cloneNote - RangeMin + 1) / 6.0`
   - Upper fade: `cloneNote` in `[RangeMax-4 .. RangeMax]` → factor = `(RangeMax - cloneNote + 1) / 6.0`
   - Inside both boundaries: factor = 1.0
4. **Result:** `Round(IntToFloat(vel) * factor)`, minimum 1. Notes outside the range return 0.

**Velocity fade curve (5-note zone):**

| Position from edge | Factor | Example vel=100 |
|--------------------|--------|------------------|
| 0 (at boundary)    | 1/6 = 17% | 17 |
| 1                  | 2/6 = 33% | 33 |
| 2                  | 3/6 = 50% | 50 |
| 3                  | 4/6 = 67% | 67 |
| 4                  | 5/6 = 83% | 83 |
| 5+                 | 100%      | 100 |

**Edge case — Range < 10 notes:** The VelocityFader is logically bypassed (the stored `p_OctRangeFade` value is NOT modified). When the range widens to >= 10 again, the fader automatically re-engages. The widget reflects the stored value, not the effective state.

## 3. Integration into PlayOutNote / StopOutNote

### PlayOutNote

Replace the existing clone-note guard in both the Lower Octaves and Upper Octaves loops:

**Before:**
```
if cloneNote >= 0 and cloneNote <= 127 then
    msg = MakeNoteMessageEx(cloneNote, vel, chan)
```

**After:**
```
var cloneVel : Integer = GetOctRangeVelocity(cloneNote, vel)
if cloneVel > 0 then
    msg = MakeNoteMessageEx(cloneNote, cloneVel, chan)
```

This applies to both the lower octave loop (line ~270) and upper octave loop (line ~285).

### StopOutNote

Same replacement — use dummy velocity to check range membership:

**Before:**
```
if cloneNote >= 0 and cloneNote <= 127 then
    msg = MakeNoteMessageEx(cloneNote, 0, chan)
```

**After:**
```
if GetOctRangeVelocity(cloneNote, 1) > 0 then
    msg = MakeNoteMessageEx(cloneNote, 0, chan)
```

### Original note (non-clone)

The original note (`MuteOrig` logic) is NOT affected by the range — it uses the played pitch, not a generated clone pitch. The range only constrains octave clones.

## 4. Widgets (Global Rackspace)

### New widget declarations

```
BTN_LearnOctRangeMin, BTN_LearnOctRangeMax              : Widget   // Learn buttons
LBL_Inject_NP_OctRange                                  : Widget   // Range display label
BTN_Inject_NP_OctRangeFade                              : Widget   // VelocityFader toggle
```

All handle names are <= 28 characters (within the established 30-char practical limit).

### UI Layout

```
[BTN_LearnOctRangeMin]  [LBL_Inject_NP_OctRange]  [BTN_LearnOctRangeMax]
[BTN_Inject_NP_OctRangeFade]
```

Grouped visually in the Octaver section of the injection panel, analogous to `[BTN_LearnMin] [LBL_Injection_Split] [BTN_LearnMax]`.

### Label display

- Active range: `GetLuxusLabel(rangeMin) + " - " + GetLuxusLabel(rangeMax)` → e.g. "C2 (36) - G6 (91)"
- Default range (0-127) or no active channels: `"-"`

## 5. Learn Logic (Global Rackspace)

### New state variables

```
IsLearningOctRangeMin, IsLearningOctRangeMax : Boolean = false
```

### Mutual exclusion

All four learn modes are mutually exclusive — activating any one deactivates the other three:
- `IsLearningMin` (KB Split Low)
- `IsLearningMax` (KB Split High)
- `IsLearningOctRangeMin` (Octaver Range Low)
- `IsLearningOctRangeMax` (Octaver Range High)

### Widget callbacks

```
On WidgetValueChanged from BTN_LearnOctRangeMin:
    if val > 0.5: activate OctRangeMin learn, deactivate all others
    else: deactivate

On WidgetValueChanged from BTN_LearnOctRangeMax:
    if val > 0.5: activate OctRangeMax learn, deactivate all others
    else: deactivate
```

### Note handler extension

The existing MIDI handler that checks `IsLearningMin / IsLearningMax` is extended:

```
if IsLearningOctRangeMin then
    SetParameter(BLK_NoteProcessor[i], idx_OctRangeMin, paramVal)
elsif IsLearningOctRangeMax then
    SetParameter(BLK_NoteProcessor[i], idx_OctRangeMax, paramVal)
end
```

Writes to all active scope channels. Auto-off after note received (both booleans false, both button widgets to 0.0).

## 6. Snapshot Persistence

### New memory arrays

```
Mem_NP_OctRangeMin  : Double Array = (...)
Mem_NP_OctRangeMax  : Double Array = (...)
Mem_NP_OctRangeFade : Integer Array = (...)
```

### SaveSongSnapshot

Read `p_OctRangeMin`, `p_OctRangeMax`, `p_OctRangeFade` from each channel's Note Processor and store in memory arrays. Serialize to INI as:

```
Ch1_NP_p_OctRangeMin=0.2834646
Ch1_NP_p_OctRangeMax=0.7165354
Ch1_NP_p_OctRangeFade=1.0000000
```

### LoadSongSnapshot

Deserialize from INI, write to memory arrays, push to Note Processor parameters.

## 7. Summary of Changes

| File | Change |
|------|--------|
| **Note Prozessor.gpscript** | 3 new parameters, `GetOctRangeVelocity()` function, modified `PlayOutNote`/`StopOutNote`, factory reset extension, panic trigger extension |
| **Global Rackspace.gpscript** | 4 new widgets, 2 new learn state booleans, learn callbacks, note handler extension, UI update logic, 3 new memory arrays, snapshot load/save extension |

## 8. Non-Goals

- No UI indicator for "fader bypassed due to small range" — the toggle reflects the stored value, not the effective state.
- No range constraint on the original (non-clone) note — only octave clones are affected.
- No per-octave-direction range (same range applies to both lower and upper clones).
