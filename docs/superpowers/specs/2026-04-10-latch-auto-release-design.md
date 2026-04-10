# Design: Chord Latch Auto-Release After Silence

**Date:** 2026-04-10
**Scope:** Tiny follow-up to the latch mode in the Note Prozessor chord engine.
**Files touched:** `Note Prozessor.gpscript`, `Global Rackspace.gpscript`

## Context & Motivation

`BTN_Inject_NP_Hold` drives `p_LatchMode` in the Note Prozessor's chord engine (`Note Prozessor.gpscript:568–572`). When latch is active and the user releases all keys, the currently-emitted chord root keeps playing until a panic, user mute, or explicit re-press stops it. In practice this works "too well" — after a song ends the latched root keeps droning through the silence.

Professional keyboards solve this with either (a) manual release only, (b) a fixed-ms timeout, or (c) a BPM-scaled beat timeout. We're going with the **BPM-scaled beat timeout with a ms fallback**: release the latched root after **4 beats of silence**, falling back to **4000ms** when `GetBPM()` is unavailable.

Four beats at common live tempos:
- 60 BPM → 4000 ms (identical to the fallback, so the fallback feels natural)
- 80 BPM → 3000 ms
- 100 BPM → 2400 ms
- 120 BPM → 2000 ms

Musical feel: a fast song releases faster, a slow song holds longer.

## Architecture

### Where the timer lives: Global Rackspace, not the scriptlet

GPScript scriptlets (like `Note Prozessor.gpscript`) support only `On MidiEvent` and `On ParameterValueChanged` callbacks — no `On BeatChanged`, no `On TimerTick`. The Global Rackspace script has both, and it already sees every hardware Note On through `ProcessHardwareNote(m)` at `Global Rackspace.gpscript:10166`. The timeout logic therefore lives in the Global Rackspace; the scriptlet only exposes a trigger parameter that GR sets when a release is due.

### Single global "last note-on" timestamp

One `Double` value, not 16-per-channel. Rationale: the user's complaint is "song is over, everything silent, latch keeps droning." The triggering condition is "silence everywhere," which a single global timestamp captures exactly. As a side benefit, if the user keeps playing on a different channel while latching another, the shared timer keeps resetting and the latched channel correctly stays held — exactly the desired "don't release while I'm still playing" semantic.

### Polling cadence: once per beat

`On BeatChanged(bar, beat, subbeat)` fires on every musical beat. We piggyback on that instead of introducing a new timer. The check is a handful of comparisons and a conditional loop over 16 channel slots — negligible cost. One beat of latency for the release trigger is inaudible.

### Firing once, not continuously

When the timeout fires, `Latch_LastNoteOnTime` is reset to `0.0`. The check at the top of `CheckLatchTimeout` short-circuits on `Latch_LastNoteOnTime <= 0.0`, so subsequent beats do nothing until a new note-on rearms the timer. This avoids repeatedly firing `p_LatchRelease = 1` on every beat during the silence.

---

## Changes — `Note Prozessor.gpscript`

### New parameter

Add to the Var block, next to `p_LatchMode` (`Note Prozessor.gpscript:32`):

```gpscript
   p_LatchRelease : Parameter 0 .. 1 = 0  // Trigger from GR timer: release latched chord root
```

### New handler

Add a new `On ParameterValueChanged` handler adjacent to the existing panic/mute handlers (around `Note Prozessor.gpscript:126–143`):

```gpscript
On ParameterValueChanged matching p_LatchRelease
   if Round(p_LatchRelease) == 1 then
       if Round(p_ChordMode) == 1 and lastSentRoot != -1 then
           StopOutNote(lastSentRoot, activeChannel)
           lastSentRoot = -1
       end
       p_LatchRelease = 0
   end
End
```

The guard `p_ChordMode == 1 and lastSentRoot != -1` means the handler is a no-op when chord mode is off or when no root is currently emitted. It does NOT check `p_LatchMode` because the intent is "release any currently-held root" — if the user happens to toggle latch off mid-idle, the next firing shouldn't be blocked.

### Factory reset

Add to the Factory Reset block at `Note Prozessor.gpscript:157–159` (next to the other chord-mode resets):

```gpscript
p_ChordMode = 0; p_LatchMode = 0; p_LatchRelease = 0; p_Engine = 0; ...
```

---

## Changes — `Global Rackspace.gpscript`

### New constants (SECTION 2)

Add to the core constants block alongside other tunable values:

```gpscript
   LatchTimeoutBeats       : Double = 4.0      // Auto-release latched chord root after N beats of silence
   LatchTimeoutFallbackMs  : Double = 4000.0   // Used when GetBPM() <= 1.0
```

### New state variable

Add to the module-level state:

```gpscript
   Latch_LastNoteOnTime : Double = 0.0   // TimeSinceStartup of most recent hardware note-on; 0 = disarmed
```

### Update `ProcessHardwareNote`

At the top of `ProcessHardwareNote(m : NoteMessage)` (`Global Rackspace.gpscript:10166` area), before any existing logic, add:

```gpscript
   if IsNoteOn(m) then Latch_LastNoteOnTime = TimeSinceStartup() end
```

This reset runs on every hardware note-on, regardless of whether any channel is actually in latch mode. The cost is one comparison + one assignment per note; irrelevant.

### New function `CheckLatchTimeout`

Place immediately before `On BeatChanged(bar, beat, subbeat)` at `Global Rackspace.gpscript:13722` area:

```gpscript
// ---------------------------------------------------------
// LATCH AUTO-RELEASE (4-beat timeout + ms fallback)
// Called once per beat from On BeatChanged. Fires p_LatchRelease on every
// channel currently in Chord+Latch mode when no hardware note-on has been
// seen for LatchTimeoutBeats at the current BPM. Disarms itself after
// firing so subsequent beats are no-ops until the next note-on.
// ---------------------------------------------------------
Function CheckLatchTimeout()
   var currentBpm, msPerBeat, timeoutMs, idleMs : Double = 0.0
   var i, idx : Integer
   
   if Latch_LastNoteOnTime <= 0.0 then
       // Disarmed — nothing to check until next note-on
   else
       currentBpm = GetBPM()
       if currentBpm > 1.0 then
           msPerBeat = 60000.0 / currentBpm
           timeoutMs = msPerBeat * LatchTimeoutBeats
       else
           timeoutMs = LatchTimeoutFallbackMs
       end
       
       idleMs = TimeSinceStartup() - Latch_LastNoteOnTime
       if idleMs >= timeoutMs then
           For i = 0; i < 16; i = i + 1 Do
               if Mem_NP_ChordMode[i] == 1 and Mem_NP_LatchMode[i] == 1 then
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_LatchRelease")
                   if idx > -1 then SetParameter(BLK_NoteProcessor[i], idx, 1.0) end
               end
           End
           Latch_LastNoteOnTime = 0.0   // Disarm until next note-on
           if DebugMode then Trace("LATCH: auto-release fired after " + Round(idleMs) + "ms idle") end
       end
   end
End
```

### Hook into `On BeatChanged`

At the end of `On BeatChanged(bar, beat, subbeat)` (after all existing beat-driven logic), add:

```gpscript
   CheckLatchTimeout()
```

---

## Unchanged

- `p_AutoSustain` (GP's built-in `AutoSustainer` object) — untouched. Different feature, different use case.
- `p_LatchMode` itself — remains a binary latch toggle. The auto-release is a safety net on top, not a replacement.
- Panic / UserMute / SoloMute / StopSustain / FactoryReset paths — untouched. Manual release still works as before.
- Multi-channel parallel play — handled correctly by the shared global timer (any channel's note-on rearms).

## File Locations & Impact Summary

### `Note Prozessor.gpscript`

| Line area | Change |
|---|---|
| Var block near `p_LatchMode` (~32) | Add `p_LatchRelease : Parameter 0 .. 1 = 0` |
| Handler block (~140) | Add new `On ParameterValueChanged matching p_LatchRelease` handler |
| Factory reset block (~158) | Add `p_LatchRelease = 0` |

Total: ~12 new LOC.

### `Global Rackspace.gpscript`

| Line area | Change |
|---|---|
| SECTION 2 constants (~60) | Add `LatchTimeoutBeats` and `LatchTimeoutFallbackMs` |
| Module state block | Add `Latch_LastNoteOnTime : Double = 0.0` |
| `ProcessHardwareNote()` at `:10166` | Add 1-line note-on timestamp update at top of function |
| New function before `On BeatChanged` (~13720) | Add `CheckLatchTimeout()` function |
| `On BeatChanged` at `:13722` | Add `CheckLatchTimeout()` call at end |

Total: ~30 new LOC.

## Testing Notes

1. **Basic auto-release**
   - Enable Chord mode + Latch mode on a channel.
   - Play a chord, release keys. Expected: root drones on.
   - Wait 4 beats at current BPM. Expected: root stops, `LATCH: auto-release fired after Nms idle` trace appears in DebugMode.

2. **Rearming after release**
   - After the auto-release fires, play another chord. Expected: works normally, new root is held until next release window.

3. **Multi-channel "don't release while I'm still playing"**
   - Enable Chord+Latch on channel 1, play and release a chord (root held).
   - Play continuous notes on channel 2 (different routing/split, or same input routed differently).
   - Expected: channel 1's root stays held indefinitely while notes arrive on channel 2.
   - Stop playing everywhere. Expected: after 4 beats, channel 1's root releases.

4. **BPM scaling**
   - Set BPM to 60. Release window should be ~4000ms.
   - Set BPM to 120. Release window should be ~2000ms.
   - Set BPM to 0 (or a state where GetBPM() returns 0). Release window should be 4000ms (fallback).

5. **Idempotent firing**
   - After auto-release fires, let 10 more beats pass without playing. Expected: no additional release firings (no trace spam). `Latch_LastNoteOnTime` is disarmed.

6. **Factory reset hygiene**
   - Press factory reset on a channel. Expected: `p_LatchRelease = 0`, no runaway state.

7. **Manual release still works**
   - With a latched root held, press Panic or UserMute. Expected: immediate release, same as before.
