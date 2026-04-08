# AnchorPlayback Design Spec

**Date:** 2026-04-08
**Status:** Draft
**Author:** Martin + Claude

## Problem

In a live band context, Gig Performer's bar count is unreliable. The guitarist extends a solo, the bassist rushes, the band skips a verse. The ms-based timeline drifts from reality. Currently the only safety net is the SCRUBBER emergency stop — the keyboardist pulls it to zero and takes over manually.

AnchorPlayback solves this by detecting **where we actually are in the song** based on the chords being played, and keeping the timeline anchored to reality.

## What AnchorPlayback Does

AnchorPlayback is a **passive observer** that:

1. Detects part boundaries by matching played root notes against the `.gpchord` chord progression
2. Advances the part display (Prompter) when a new part is recognized
3. Corrects the timeline position (ms) to the recognized part (when `BTN_TimeJump` is active)
4. Strengthens the existing Autopilot fat-finger correction by keeping the timeline position accurate

## What AnchorPlayback Does NOT Do

- No autonomous event triggering (except catching up part-change markers)
- No SCRUBBER emergency stop
- No RegMem commands to the arranger
- No influence when `BTN_MIDIAnchorPlayback == 0`
- Skipped timeline events (Macro, Map, Style, RegMem) stay silent — only Marker events are caught up

## Controls

Three existing buttons (already declared, saved/loaded in config):

| Button | Purpose |
|--------|---------|
| `BTN_MIDIAnchorPlayback` | Master switch — enables/disables AnchorPlayback entirely |
| `BTN_TimeJump` | Allows timeline position correction on detected part change |
| `BTN_Autopilot` | Fat-finger correction for RegMem (existing, benefits from more accurate position) |

All three default to ON (1.0) at system reset.

---

## Component 1: Manual Property (Upper/Lower/None)

### Purpose

Identifies which keyboard manual (hand) plays on each MIDI channel. AnchorPlayback uses the Lower channel (left hand = chord hand) as the primary source for chord detection.

### New Widgets

```gpscript
BTN_Manual_Prev, LBL_Manual, BTN_Manual_Next : Widget
```

Placed directly below `LBL_ChannelUsage` in the Injection panel. Manual is a separate property from ChannelUsage because a channel can be both "Lower" (which hand) AND "Strings" (which sound). "Upper" and "Lower" are removed from the `UsageCategories` array to avoid confusion.

### Enum Values

| Value | Integer | Meaning |
|-------|---------|---------|
| None  | 0       | No manual assignment (default) |
| Upper | 1       | Right hand — melody |
| Lower | 2       | Left hand — chords/accompaniment |

Mutually exclusive per channel: a channel is exactly one of these.

### Storage

- New RAM array: `Mem_Manual : Integer Array` (16 elements, initialized to 0)
- Saved/loaded as part of the Controller Map (Injection section), same pattern as Solo, Mute, etc.
- Widget handlers cycle through 0 → 1 → 2 → 0
- Display names: `ManualNames : String Array = ["None", "Upper", "Lower"]`

### Cached Lookup

```gpscript
AnchorLowerChIdx : Integer = -1   // First channel with Manual = Lower
AnchorUpperChIdx : Integer = -1   // First channel with Manual = Upper
```

Recalculated on:
- Song load
- Controller map load
- Manual widget change

```
Function UpdateAnchorChannels()
    AnchorLowerChIdx = -1; AnchorUpperChIdx = -1
    For i = 0; i < 16; i = i + 1 Do
        if Mem_Manual[i] == 2 and AnchorLowerChIdx == -1 then AnchorLowerChIdx = i end
        if Mem_Manual[i] == 1 and AnchorUpperChIdx == -1 then AnchorUpperChIdx = i end
    End
End
```

---

## Component 2: NoteProcessor V7.5 — Root Output

### Purpose

Every NoteProcessor instance (16x, one per channel) always calculates and exposes the detected root note, regardless of whether Chord-to-Root mode is active.

### New Parameters

```gpscript
// --- 12. ANCHOR OUTPUT (NEW V7.5) ---
p_DetectedRoot  : Parameter 0 .. 11 = 0   // Pitch Class: 0=C, 1=C#, 2=D, ..., 11=B
p_HasNotes      : Parameter 0 .. 1 = 0    // 1 = at least one note is held
```

### Logic Change

Currently, `CalculateRootMath()` is only called inside `UpdateChordLogic()`, which only runs when `p_ChordMode == 1`.

**New behavior:** After every NoteOn/NoteOff (inside the master event handler), always update the output parameters:

```
// After AddHeldNote/RemoveHeldNote, regardless of p_ChordMode:
if Size(heldNotes) > 0 then
    p_HasNotes = 1
    rootResult = CalculateRootMath(lowestNote)
    p_DetectedRoot = rootResult % 12
else
    p_HasNotes = 0
end
```

This runs inside the existing NoteOn/NoteOff branches of `On MidiEvent`. The `CalculateRootMath()` function is lightweight (pitch class sorting + interval check).

### CPU Impact

- `CalculateRootMath()` is O(n^2) where n = number of held notes. Typical n = 3-5 for chords. Negligible.
- Writing two parameters per NoteOn/NoteOff: negligible.
- The Global Rackspace only reads from 1-2 channels, not all 16.

### Factory Reset Addition

```gpscript
p_DetectedRoot = 0; p_HasNotes = 0
```

---

## Component 3: Root Sequence Parser

### Purpose

At song load, extract root pitch classes from `.gpchord` chord notation and store as flat arrays per part.

### Source Data

The `.gpchord` format contains inline chords in square brackets:
```
{label: Chorus}
Jo[Dm]lene, Jo[F]lene, Jo[C]lene, Jo[Dm]lene
```

Already parsed into `Arr_Text_Chords[]` (one string per part) for display. AnchorPlayback needs the same data as pitch class integers.

### Chord-to-Root Mapping

Only the root letter matters. The chord type (m, 7, sus4, dim, etc.) is ignored:

| Letter | Pitch Class |
|--------|-------------|
| C | 0 |
| C# / Db | 1 |
| D | 2 |
| D# / Eb | 3 |
| E | 4 |
| F | 5 |
| F# / Gb | 6 |
| G | 7 |
| G# / Ab | 8 |
| A | 9 |
| A# / Bb | 10 |
| B / H | 11 |

Parsing rule: Read first character after `[`. If followed by `#` → sharpen. If followed by `b` → flatten. Everything else is chord type (ignored).

### Storage (Flat Arrays)

GPScript has no nested arrays. Use flat structure with index pointers:

```gpscript
Arr_PartRootSeq   : Integer Array   // All roots concatenated: [2,5,0,2, 2,5,0, ...]
Arr_PartRootStart : Integer Array   // Start index per part:   [0, 4, 7, ...]
Arr_PartRootLen   : Integer Array   // Root count per part:    [4, 3, ...]
```

Example for a song with Chorus `[Dm][F][C][Dm]` and Verse `[Dm][F][C]`:
- `Arr_PartRootSeq = [2, 5, 0, 2, 2, 5, 0]`
- `Arr_PartRootStart = [0, 4]`
- `Arr_PartRootLen = [4, 3]`

### Duplicate Filtering

Consecutive identical roots are collapsed. `[Dm] [Dm] [F]` becomes `[2, 5]` not `[2, 2, 5]`. Reason: the player may hold Dm for two bars — we only care about the root *changing*.

### When to Parse

During `ParseSongData()` (existing song load function), after the existing chord text extraction. Uses the same `Arr_Text_Chords[]` strings as source.

---

## Component 4: Forward-Only Root Tracker

### Purpose

The core engine. Tracks the played root sequence against the expected progression and detects part boundaries.

### State Variables

```gpscript
AnchorCurrentPartIdx  : Integer = 0     // Which part Anchor thinks is active
AnchorRootCursor      : Integer = 0     // Position in current part's root sequence
AnchorMatchCount      : Integer = 0     // Consecutive matches against NEXT part
AnchorLastRoot        : Integer = -1    // Last detected root (pitch class), -1 = none
```

### Algorithm (runs in Timer callback)

**Gate:** Only runs when `BTN_MIDIAnchorPlayback > 0.5` AND (`AnchorLowerChIdx >= 0` OR `AnchorUpperChIdx >= 0`) AND `Size(Arr_PartRootSeq) > 0`.

**Step 1 — Read root from NoteProcessor:**
```
hasLower = GetParameter(BLK_NoteProcessor[AnchorLowerChIdx], p_HasNotes_Idx) > 0.5
hasUpper = GetParameter(BLK_NoteProcessor[AnchorUpperChIdx], p_HasNotes_Idx) > 0.5

if hasLower then
    currentRoot = Round(GetParameter(BLK_NoteProcessor[AnchorLowerChIdx], p_DetectedRoot_Idx) * 11.0)
elsif hasUpper then
    currentRoot = Round(GetParameter(BLK_NoteProcessor[AnchorUpperChIdx], p_DetectedRoot_Idx) * 11.0)
else
    // No notes held — skip this tick
end
```

Note: Parameters are 0.0-1.0 floats in GP. `p_DetectedRoot` range 0..11 maps to 0.0..1.0. Conversion: `Round(paramVal * 11.0)`.

**Step 2 — Deduplicate:**
If `currentRoot == AnchorLastRoot` → skip (same root as before, no new information).
Otherwise → `AnchorLastRoot = currentRoot`, proceed.

**Step 3 — Track against current part:**
```
expectedIdx = Arr_PartRootStart[AnchorCurrentPartIdx] + AnchorRootCursor
expectedRoot = Arr_PartRootSeq[expectedIdx]

if currentRoot == expectedRoot then
    AnchorRootCursor = AnchorRootCursor + 1
    if AnchorRootCursor >= Arr_PartRootLen[AnchorCurrentPartIdx] then
        AnchorRootCursor = 0  // Wrap — part is repeating (e.g., band loops the chorus)
    end
end
```

**Step 4 — Check against next part:**
```
nextPartIdx = AnchorCurrentPartIdx + 1
if nextPartIdx < Size(Arr_PartRootStart) then
    nextExpectedRoot = Arr_PartRootSeq[Arr_PartRootStart[nextPartIdx] + AnchorMatchCount]
    if currentRoot == nextExpectedRoot then
        AnchorMatchCount = AnchorMatchCount + 1
    else
        AnchorMatchCount = 0  // Reset — not the next part after all
    end
end
```

**Step 5 — Trigger part change:**
```
if AnchorMatchCount >= 2 then
    AnchorCurrentPartIdx = nextPartIdx
    AnchorRootCursor = AnchorMatchCount  // We're already N roots into the new part
    AnchorMatchCount = 0
    ExecuteAnchorPartChange(AnchorCurrentPartIdx)
end
```

### Threshold: N = 2

Two consecutive root matches against the next part trigger a change. Rationale:
- At typical tempo (120 BPM, 4/4), one chord per bar = ~2 seconds per root change
- N=2 means ~4 seconds detection delay — fast enough for live use
- N=1 would cause false positives (single matching root is too common)
- N=3 would mean 6+ seconds delay — too slow for tight arrangements

### Edge Cases

| Case | Behavior |
|------|----------|
| Last part (no next) | Tracker stays passive, only cursor tracking |
| Identical root sequences (Verse 1 = Verse 2) | Forward-only: always advance to next part, never jump back |
| Band repeats a part (loops chorus) | Cursor wraps to 0, no part change triggered |
| No chords in `.gpchord` for a part | `Arr_PartRootLen[i] == 0` → skip tracking for that part, rely on RegMem/Timeline |

### Reset

On song change, all state variables reset to initial values (0, 0, 0, -1).

---

## Component 5: Timeline Integration

### ExecuteAnchorPartChange()

Called when the Forward-Only Tracker detects a part boundary.

```
Function ExecuteAnchorPartChange(newPartIdx : Integer)
```

**Always (when `BTN_MIDIAnchorPlayback` active):**
1. Update prompter display: `PreviewPartIdx = newPartIdx`
2. Call `UpdatePrompter(false)`
3. Fire the Marker event for the new part (catch up part-change display)
4. HUD feedback: `">>> ANCHOR: [SectionName] <<<"`
5. Trace log: `"ANCHOR: Part change detected -> [SectionName]"`

**When `BTN_TimeJump` active:**
6. Find the timeline event for this part's Marker in `Snap_TL_TimeMS[]`
7. Adjust `PlaybackStartTimeMS` so that `TimeSinceStartup() - PlaybackStartTimeMS` equals the marker's ms value
8. This makes the timeline "jump" to the correct position — future events fire at the right time
9. Events between old and new position remain with `Snap_TL_Fired = false` if not yet fired, but are NOT retroactively fired (they stay silent). Exception: Marker events are caught up (step 3).
10. SCRUBBER slider position is governed by the timeline — no direct manipulation

**When `BTN_Autopilot` active:**
- No additional code needed. `CheckRegMemAutopilot()` already compares pressed RegMem against expected RegMem based on timeline position. Since AnchorPlayback keeps the timeline position accurate, Autopilot automatically benefits.

---

## Data Flow Summary

```
[Genos2 Keyboard]
       |
       v
[MIDI NoteOn/Off on Lower channel]
       |
       v
[NoteProcessor Scriptlet (per channel)]
  - heldNotes[] updated
  - CalculateRootMath() called
  - p_DetectedRoot written (Pitch Class 0-11)
  - p_HasNotes written (0 or 1)
       |
       v
[Global Rackspace Timer Callback]
  - Gate: BTN_MIDIAnchorPlayback active?
  - Read p_DetectedRoot from Lower (fallback: Upper)
  - Forward-Only Tracker:
    - Track cursor in current part
    - Match against next part's root sequence
    - 2 consecutive matches → part change
       |
       v
[ExecuteAnchorPartChange()]
  - Update Prompter display
  - Fire Marker event
  - If BTN_TimeJump: correct timeline ms position
  - HUD feedback
```

---

## File Changes Summary

| File | Changes |
|------|---------|
| `Note Prozessor 7.4.gpscript` → **V7.5** | Add `p_DetectedRoot`, `p_HasNotes`, always call `CalculateRootMath()`, update factory reset |
| `Global Rackspace.gpscript` | New widgets (BTN_Manual_Prev/LBL_Manual/BTN_Manual_Next), Mem_Manual[16], ManualNames, remove Upper/Lower from UsageCategories, new arrays (PartRootSeq/Start/Len, Anchor state), UpdateAnchorChannels, root sequence parser, Forward-Only Tracker, ExecuteAnchorPartChange() |

---

## Out of Scope

- Chord type detection (only root pitch class matters)
- Intra-part position correction (only part boundaries)
- Backward jumps (always forward-only)
- Autonomous event triggering beyond part markers
- Visual indicator for AnchorPlayback confidence/state (future enhancement)
