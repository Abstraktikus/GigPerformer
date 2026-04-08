# SYS-MODE 4: TIMELINE — Design Specification

**Date:** 2026-04-08
**Status:** Approved

## Overview

SYS-MODE 4 "TIMELINE" adds a dedicated joystick navigation mode for recording and playing back song part markers and macro events along a millisecond-based timeline. It replaces the existing bar-based timeline recording with a pure ms-based approach, enabling synchronization with external audio sources (e.g. Spotify) that don't share Gig Performer's transport clock.

## Motivation

Musicians listening to external backing tracks cannot rely on GP's bar counter for accurate event positioning. The deviation between GP's transport and an external audio source is not millisecond-level (as with the arranger) but significant. Recording in absolute milliseconds and deferring bar calculation until the full song duration is known solves this problem.

---

## 1. Mode Integration

### SYS-MODE Array

`SysModeNames` expands to 5 entries:

```
["VOICE SELECTOR", "LOOPER CONTROL", "CONTROLLER MAP", "STRIP-CONTROL", "TIMELINE"]
```

`GlobalSystemMode = 4` activates TIMELINE mode.

### Sub-Mode Layer

TIMELINE has an internal sub-mode that acts as a safety layer:

| Variable | Type | Values |
|----------|------|--------|
| `TimelineSubMode` | Integer | 0 = PLAY, 1 = REC |
| `TimelineRecState` | Integer | 0 = Replace, 1 = Overdub, 2 = Discard |

- **PLAY mode:** Ensures `BTN_Record_Replace` and `BTN_Record_Overdub` cannot be active. Safe for navigation.
- **REC mode:** Allows one of the recording modes to be activated.

---

## 2. Joystick Mapping (Device 0 — Genos/Arranger)

| Direction | PLAY Mode | REC Mode |
|-----------|-----------|----------|
| **Up (Y+)** | Toggle → REC | Toggle → PLAY |
| **Down (Y- / CC16)** | CycleGlobalSystemMode | CycleGlobalSystemMode |
| **Left (X-)** | Part Jump back (Preview) | Cycle: Replace → Overdub → Discard |
| **Right (X+)** | Part Jump forward (Preview) | Execute REC_SONGPART |

### Device 1 (MiniLab) — Same Functions

- **Encoder (X-Axis):** Left/Right functions identical to joystick
- **Button (Y-Up):** Up function identical to joystick
- Mode entry via SYSMODE_CYCLE or SYSMODE_SELECT macros (see Section 9)

---

## 3. Sticky SYS-MODE State (All Modes 0–4)

Sustain pedal release no longer resets the SYS-MODE. Applies to all modes, not just TIMELINE.

### State Variables

```gpscript
StickySystemMode : Integer = -1          // -1 = no sticky, 0-4 = remembered mode
StickyTimelineSubMode : Integer = 0      // only for mode 4
StickyTimelineRecState : Integer = 0     // only for mode 4
```

### Behavior

- **Sustain Release:** Store current mode + sub-states in sticky variables, set `SystemModeActive = false`
- **Sustain Press:** If `StickySystemMode >= 0` → restore full state, else normal entry
- **Explicit Mode Change:** (CycleGlobalSystemMode or SYSMODE_SELECT) resets sticky to -1

### REC Continuity

Sustain release during active recording does NOT stop the recording. The ms timer continues. Sustain re-press restores TIMELINE + REC + current RecState seamlessly.

---

## 4. Millisecond-Based Recording Architecture

### Design Decision

All timeline events are recorded as absolute milliseconds since `RecordStartTimeMS`. Bar counts are only calculated after the full song duration is known (END OF SONG signal).

### Recording Arrays

```gpscript
// Working (current session)
Arr_Rec_TimeMS : Double Array    // Absolute ms since RecordStartTimeMS
Arr_Rec_Type   : String Array   // "Marker", "Macro", "Map", "Style"
Arr_Rec_Val    : Integer Array  // Part index, map index, etc.

// Committed (last good state)
Snap_TL_TimeMS : Double Array
Snap_TL_Type   : String Array
Snap_TL_Val    : Integer Array
```

### Recording Flow

1. User enters REC mode (joystick up)
2. Count-in starts via shared `GetCountInDurationMS()`
3. Count-in expires → `RecordStartTimeMS = TimeSinceStartup()`
4. "Intro" begins implicitly at t=0 (no manual marker needed)
5. Each event: `eventTimeMS = TimeSinceStartup() - RecordStartTimeMS`

### REC_SONGPART (Joystick Right in REC Mode)

- Records `("Marker", currentPartIdx)` at current ms position
- `currentPartIdx` starts at 1 (index 0 = Intro, implicit at t=0)
- Part names come from `Arr_SectionNames[]` (loaded from .gpchord file)
- If `Arr_SectionNames` is empty → error feedback: `">>> NO PARTS LOADED <<<"`
- If last part reached → next REC_SONGPART = **END OF SONG**

### END OF SONG

When the last part is reached and the user presses REC_SONGPART again:

1. `RecordEndTimeMS = TimeSinceStartup() - RecordStartTimeMS`
2. Working arrays → Committed arrays (copy)
3. Auto-switch to PLAY mode
4. Bar counts calculated from total duration + GP BPM
5. OSC feedback: `">>> SONG RECORDED <<<"`

### Bar Calculation (Post-Recording)

```
totalDurationMS = RecordEndTimeMS
msPerBar = (60000.0 / BPM) * TimeSignatureNumerator
eventBar = Round(eventMS / msPerBar) + 1
eventOffset = eventMS mod Round(msPerBar)
```

Bar count is stored alongside ms data but only displayed during playback once a real END exists.

---

## 5. Snapshot Model (Committed / Working)

| Snapshot | Set When | Content |
|----------|----------|---------|
| **Committed** | After Song.ini load OR after successful REC (END OF SONG) | Last known-good state |
| **Working** | During active REC/Overdub | Current changes |

### Operations

- **Discard:** Clear Working arrays, Committed remains intact. OSC: `">>> RECORDING DISCARDED <<<"`. Sub-mode stays REC (user can immediately re-record).
- **Successful REC:** Working → Committed (array copy)
- **BTN_SaveConfig:** Committed → Song.ini (persist to disk)

### Commit Triggers (Working → Committed)

Three ways to finalize a recording:

1. **END OF SONG** — last part + REC_SONGPART (auto-switches to PLAY)
2. **Manual PLAY switch** — joystick up while in REC mode
3. **SYS-MODE change** — user leaves TIMELINE mode entirely

---

## 6. Count-In Mechanism

### Shared Function

Both Timeline and Looper use the existing `GetCountInDurationMS()`:

```
Duration = (60000 / BPM) * (TimeSigNumerator * BarsToWait)
Auto-scale: BPM >= 140 → 2 bars instead of 1
```

### Visual Feedback

Reuses the existing LED countdown system (LBL_Subbar_1 through LBL_Subbar_4) and text display ("Wait: -3, -2, -1").

### Timeline-Specific Variables

```gpscript
TimelineCountInTimer : Double = 0.0   // Absolute expiry time (parallel to LoopFreeArmTimer)
RecordStartTimeMS : Double = 0.0      // Set when count-in expires
RecordEndTimeMS : Double = 0.0        // Set at END OF SONG
```

### Purpose

The count-in gives the user time to start the external audio source (Spotify, backing track) in sync with the recording start. The first beat after count-in = t=0 = Intro begins.

---

## 7. Playback

### Start Triggers

| Trigger | Condition |
|---------|-----------|
| **Playhead Start** | GP transport starts → immediate playback |
| **NoteOn Detection** | `BTN_TL_HostSync = ON` + Playhead OFF + notes detected → immediate playback |
| **Count-In** | Manual, shared `GetCountInDurationMS()` for Spotify sync |

### Widget

`BTN_TL_HostSync` — separate from Looper's `BTN_Loop_HostSync`. Timeline syncs to external audio sources; Looper syncs to beat grid. Independent configuration required.

### Playback Loop (TimerTick)

```gpscript
msSinceSongStart = TimeSinceStartup() - PlaybackStartTimeMS

for idx = 0; idx < Size(Snap_TL_TimeMS); idx = idx + 1 do
    if Snap_TL_TimeMS[idx] <= msSinceSongStart and not Snap_TL_Fired[idx] then
        FireTimelineEvent(Snap_TL_Type[idx], Snap_TL_Val[idx])
        Snap_TL_Fired[idx] = true
    end
end
```

### Fired Flag Reset

`Snap_TL_Fired[]` is reset at playback start. No bar-boundary reset needed (pure ms comparison).

### Part Jump Preview (PLAY Mode, Joystick Left/Right)

```gpscript
PreviewPartIdx : Integer = 0

Joystick Right → PreviewPartIdx = Min(PreviewPartIdx + 1, Size(Arr_SectionNames) - 1)
Joystick Left  → PreviewPartIdx = Max(PreviewPartIdx - 1, 0)
```

- OSC-UI updates immediately with the song text of the preview part
- Does NOT change playback position
- If `Arr_SectionNames` empty → `">>> NO PARTS LOADED <<<"`
- Reset to 0 on song load and REC start

---

## 8. Error Handling

| Scenario | Behavior |
|----------|----------|
| No parts loaded + Part Jump | `">>> NO PARTS LOADED <<<"` |
| No parts loaded + REC_SONGPART (first press) | Allowed — marks song end directly (single-marker recording, Intro only) |
| No parts loaded + Part Jump after single-marker REC | `">>> NO PARTS LOADED <<<"` |
| PLAY mode + record buttons | Ignored / blocked |
| Sustain release during REC | Recording continues, sticky state preserved |
| Discard | Working arrays cleared, Committed intact, stays in REC |
| END OF SONG | Auto-stop, auto-commit, auto-switch to PLAY |

---

## 9. Macros: SYSMODE_CYCLE and SYSMODE_SELECT

### SYSMODE_CYCLE

Cycling macro analogous to `VST_SCOPE`. Calls `CycleGlobalSystemMode()` — advances through modes 0→1→2→3→4→0.

- Usable from any state (including `SystemModeActive = false`)
- Sets `SystemModeActive = true`
- Resets sticky state

### SYSMODE_SELECT

Direct-access macro with parameter (0–4). Sets `GlobalSystemMode` to the specified value.

- Same activation/sticky behavior as SYSMODE_CYCLE
- OSC feedback: `">>> SYS-MODE: <mode_name> <<<"`
- MiniLab user profile maps pads to specific SYSMODE_SELECT values

---

## 10. Persistence — Song.ini Format

### New [Timeline] Section (ms-based)

```ini
[Timeline]
StartBPM=120.0
TimeSignature=4
TotalDurationMS=360000
Event_1=0, Marker, 0
Event_2=45200, Marker, 1
Event_3=48300, Macro, 2
Event_4=91000, Marker, 2
Event_5=182000, Map, 3
Event_6=360000, Marker, END
```

### Format

- `StartBPM` — GP BPM setting at recording time (for bar calculation)
- `TimeSignature` — beats per bar
- `TotalDurationMS` — only present when END OF SONG was recorded
- `Event_N=<ms>, <Type>, <Value>` — absolute ms, event type, associated value

### Bar Display Section (optional)

```ini
[Timeline_Bars]
Event_1=1, Marker, 0, 0
Event_2=23, Marker, 1, 200
```

Written only after END OF SONG with valid bar calculation. Used for display/export, not for playback.

### No Backward Compatibility

The old bar-based `[Timeline]` format (`Event_N=Bar, Type, Val, OffsetMS`) is no longer supported. All existing song files must be re-recorded.

---

## 11. Deliverables

1. **GPScript changes** — New SYS-MODE 4 in ProcessSystemNavigation, ms-based recording/playback, snapshot model, count-in integration, sticky state for all modes, SYSMODE_CYCLE/SELECT macros, BTN_TL_HostSync widget
2. **Song.ini format** — New `[Timeline]` section with ms-based events
3. **Example files** — Update `SlowHip80erDream.ini` and `VSTPlayMode.ini` to new format
4. **README.md** — Update SYS-MODE description (5 modes), update roadmap, document new features
5. **Memory update** — Update `project_sysmode_requirements.md` with Mode 4 specification
