# Looper Chain — Timeline Weaving Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Weave the existing Looper chain runtime (`Mem_Loop_Target` + auto-jump at `On BeatChanged`) into the Timeline as read-only "Show" projections, display them in the REC panel with clear visual separation from the recorded Master events, and broadcast a live "next action" countdown to the OSC-UI.

**Architecture:** Pure read-side extension. A new event type `"LoopMaster"` is added to the `Arr_Rec_*` stream to mark manual loop triggers during Timeline REC. A pure `ComputeShowChain()` helper walks `Mem_Loop_Target` from a master's channel to produce a list of projected `(offsetMS, chIdx, action)` tuples. A `ShowProjectionsAllowed()` gate suppresses projections until `RecordedBPM > 0` and `SongDurationBars > 0` (i.e. during Live REC the display stays minimal). `BuildRecDisplayLines()` is extended to insert indented show lines beneath each `LoopMaster`. A new OSC field `/UI/LoopNext` carries a countdown string recomputed on every timer tick.

**Tech Stack:** GPScript 5.x. No new files. Verification via `if DebugMode then Trace(...)` statements plus user E2E.

**Spec:** `docs/superpowers/specs/2026-04-11-lfo-looper-timeline-design.md` §3.

---

## File Structure

**Single file modified:** `Global Rackspace.gpscript`

| Section | Lines | Change |
|---|---|---|
| SECTION 18 / Looper Engine (`TriggerFocusLooperTransport`) | ~8976 | Emit `RecordTimelineEvent("LoopMaster", ...)` when a manual state change fires during Timeline REC |
| SECTION 19 / Timeline Engine | new function | Add `ComputeShowChain()` helper |
| SECTION 19 / Timeline Engine | new function | Add `ShowProjectionsAllowed()` gate |
| SECTION 19 / Timeline Engine (`BuildRecDisplayLines`) | 4941-5005 | Insert indented show lines beneath `LoopMaster` events |
| SECTION 19 / Timeline Engine | new function | Add `ComputeNextLoopShowAction()` for OSC-UI countdown |
| Existing timer tick loop | TBD | Broadcast `/UI/LoopNext` with the countdown text |
| SECTION 13: Core Utilities | new helper | `EncodeLoopMasterVal(chIdx, actionCode)` + `DecodeLoopMasterVal(val)` |

---

## Task 1: Add `LoopMaster` encoding helpers + record the event on manual trigger

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 13 (Core Utilities, add near other small helpers around line 674+) and SECTION 18 / `TriggerFocusLooperTransport`

- [ ] **Step 1: Add two tiny encoding helpers**

Place these near the other Core Utilities functions (SECTION 13). A good landing zone is just after `CheckLatchTimeout()` or before the main sweep of other Utility helpers — any spot that is clearly inside SECTION 13 and compiles in file order. For concreteness, add them at the end of SECTION 13 so they come before any caller.

```gpscript
// ---------------------------------------------------------
// LOOP MASTER EVENT ENCODING
// Timeline stores a looper trigger event as a single Integer val.
// Upper nibble = channel index (0..15), lower nibble = action code:
//   0 = Rec, 1 = Play, 2 = Overdub, 3 = Clear
// Encoding: val = chIdx * 16 + actionCode
// ---------------------------------------------------------
Function EncodeLoopMasterVal(chIdx : Integer, actionCode : Integer) Returns Integer
   result = (chIdx * 16) + actionCode
End

Function DecodeLoopMasterChIdx(val : Integer) Returns Integer
   result = val / 16
End

Function DecodeLoopMasterActionCode(val : Integer) Returns Integer
   result = val % 16
End

Function LoopMasterActionName(actionCode : Integer) Returns String
   if actionCode == 0 then result = "REC"
   elsif actionCode == 1 then result = "PLAY"
   elsif actionCode == 2 then result = "OVR"
   elsif actionCode == 3 then result = "CLR"
   else result = "?" end
End
```

- [ ] **Step 2: Record the master event inside `TriggerFocusLooperTransport`**

Locate `TriggerFocusLooperTransport` at line 8976. At the bottom of the function, inside the `if scopeIsValid` block, just after the `if stateChanged` block that calls `UpdateSoloMuteState()` / `BuildLooperConfigLines()` / `UpdateInjectionLooperTransportUI()`, add the recording hook.

You currently have:

```gpscript
       // Update UI and labels once at the end, only if at least 1 channel changed
       if stateChanged then
          UpdateSoloMuteState()
          BuildLooperConfigLines()
          UpdateInjectionLooperTransportUI()
       end
   end // End of scopeIsValid check
End
```

Change it to:

```gpscript
       // Update UI and labels once at the end, only if at least 1 channel changed
       if stateChanged then
          UpdateSoloMuteState()
          BuildLooperConfigLines()
          UpdateInjectionLooperTransportUI()

          // Timeline integration: record a LoopMaster for every scope channel
          // that actually changed state, so the Show-projection path can anchor
          // the chain at replay time. Only records during active Timeline REC.
          if TimelineRecActive then
             For i = 0; i < 16; i = i + 1 Do
                if OutputScope[i] and IsChannelActiveForLooper(i) then
                   if isRecAction then
                      RecordTimelineEvent("LoopMaster", EncodeLoopMasterVal(i, 0))   // 0 = Rec
                      if DebugMode then Trace("LOOPER-TL: LoopMaster REC Ch" + (i+1) + " encoded") end
                   else
                      RecordTimelineEvent("LoopMaster", EncodeLoopMasterVal(i, 1))   // 1 = Play
                      if DebugMode then Trace("LOOPER-TL: LoopMaster PLAY Ch" + (i+1) + " encoded") end
                   end
                end
             End
          end
       end
   end // End of scopeIsValid check
End
```

Note the `var i : Integer` needs to be declared at the top of the function if it isn't already. Look at the function header — if `i` is already in the existing `var i, currentState, newState : Integer` line, you're done; if not, add it.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(looper-tl): record LoopMaster events on manual trigger

Adds EncodeLoopMasterVal / DecodeLoopMasterChIdx /
DecodeLoopMasterActionCode / LoopMasterActionName helpers to pack
channel + action into the Integer val field used by Arr_Rec_*.

TriggerFocusLooperTransport now emits a 'LoopMaster' event via
RecordTimelineEvent() for each scope channel whose state actually
changed during active Timeline REC. Only Rec and Play actions are
distinguished today; Overdub/Clear are future extensions."
```

---

## Task 2: Add `ShowProjectionsAllowed()` gate and `ComputeShowChain()` helper

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 19 (Prompter & Timeline Engine), add new helpers near the existing `BuildRecDisplayLines`

- [ ] **Step 1: Add the gate function**

Add immediately before `BuildRecDisplayLines` (which starts at line 4941):

```gpscript
// ---------------------------------------------------------
// SHOW PROJECTION GATE
// Show-events are computed only when the ms <-> bars conversion is
// reliable — i.e. after a song has been stored (RecordedBPM > 0 and
// SongDurationBars > 0). During live REC we deliberately suppress
// projections so the user never sees a future that tempo-drift could
// invalidate.
// ---------------------------------------------------------
Function ShowProjectionsAllowed() Returns Boolean
   result = (RecordedBPM > 0.0) and (SongDurationBars > 0)
End
```

- [ ] **Step 2: Add `ComputeShowChain()` helper**

Add immediately after `ShowProjectionsAllowed()`:

```gpscript
// ---------------------------------------------------------
// COMPUTE SHOW CHAIN
// Given a master event's starting channel, walk Mem_Loop_Target and
// accumulate offsets in bars (converted to ms on the fly via
// RecordedBPM + GetTimeSigNumerator). Returns three parallel arrays:
// showChain_OffsetMS, showChain_ChIdx, showChain_ActionCode.
// These are module-level arrays rebuilt on every call — callers that
// need them persistently must copy them out before the next call.
//
// N_MAX_CHAIN_DEPTH = 32 caps runaway projection for cyclic chains.
// ---------------------------------------------------------
Function ComputeShowChain(startChIdx : Integer)
   var cursor, next, depth, beatsPerBar : Integer
   var accumMS, msPerBar : Double

   showChain_OffsetMS = []
   showChain_ChIdx = []
   showChain_ActionCode = []

   if not ShowProjectionsAllowed() then
       if DebugMode then Trace("LOOPER-TL: ComputeShowChain skipped (projections not allowed)") end
   else
       beatsPerBar = GetTimeSigNumerator()
       if beatsPerBar <= 0 then beatsPerBar = 4 end
       msPerBar = (60000.0 / RecordedBPM) * IntToFloat(beatsPerBar)

       cursor = startChIdx
       accumMS = 0.0
       depth = 0

       While cursor >= 0 and cursor < 16 and depth < N_MAX_CHAIN_DEPTH Do
          // Add the length of the current channel to the accumulator
          if Mem_Loop_Length[cursor] > 0 then
              accumMS = accumMS + (msPerBar * IntToFloat(Mem_Loop_Length[cursor]))
          end

          next = Mem_Loop_Target[cursor]
          if next < 0 or next >= 16 then
              cursor = -1   // chain ends
          else
              showChain_OffsetMS <-- accumMS
              showChain_ChIdx <-- next
              showChain_ActionCode <-- Mem_Loop_Action[next]
              cursor = next
              depth = depth + 1
          end
       End

       if DebugMode then Trace("LOOPER-TL: ComputeShowChain from Ch" + (startChIdx+1) + " produced " + Size(showChain_OffsetMS) + " entries") end
   end
End
```

- [ ] **Step 3: Declare the required state variables in SECTION 6 or 11**

Find SECTION 11 (Engine Data — Prompter & Timeline, around line 606) and add the new arrays near the existing `Arr_Rec_TimeMS` / `Arr_Rec_Type` declarations:

```gpscript
   // LoopMaster show-projection scratch arrays (rebuilt per call)
   showChain_OffsetMS : Double Array
   showChain_ChIdx    : Integer Array
   showChain_ActionCode : Integer Array

   // Chain projection cap
   N_MAX_CHAIN_DEPTH : Integer = 32
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(looper-tl): add ShowProjectionsAllowed gate + ComputeShowChain

ShowProjectionsAllowed() returns true iff RecordedBPM > 0 AND
SongDurationBars > 0 — i.e. only after a song has been stored. Live
REC is deliberately excluded to avoid displaying projections that
later turn out wrong due to tempo drift.

ComputeShowChain(startChIdx) walks Mem_Loop_Target up to
N_MAX_CHAIN_DEPTH steps, accumulating bar offsets converted to ms via
RecordedBPM + GetTimeSigNumerator, and writes the result to three
module-level scratch arrays (OffsetMS, ChIdx, ActionCode)."
```

---

## Task 3: Extend `BuildRecDisplayLines()` — LoopMaster rendering + indented show lines

**Files:**
- Modify: `Global Rackspace.gpscript:4941-5005`

- [ ] **Step 1: Add a `LoopMaster` branch to the committed-timeline loop**

Inside `BuildRecDisplayLines()`, the first `for` loop iterates over `Snap_TL_*`. Find the `else valStr = "Value: " + Snap_TL_Val[i] end` clause (at ~line 4969) and insert a new branch for `LoopMaster` before the final `else`:

```gpscript
            elsif eType == "LoopMaster" then
                valStr = LoopMasterActionName(DecodeLoopMasterActionCode(Snap_TL_Val[i])) + " Ch" + (DecodeLoopMasterChIdx(Snap_TL_Val[i]) + 1)
```

Immediately after the existing `RecDisplayLines <-- line` line (which appends the main line), insert the show-chain rendering:

```gpscript
            RecDisplayLines <-- line

            // If this is a LoopMaster event, expand its show chain
            if eType == "LoopMaster" then
                var masterChIdx : Integer = DecodeLoopMasterChIdx(Snap_TL_Val[i])
                ComputeShowChain(masterChIdx)
                var k : Integer
                var showMS : Integer
                var showLine, barStr : String
                For k = 0; k < Size(showChain_OffsetMS); k = k + 1 Do
                    showMS = Round(IntToFloat(tms) + showChain_OffsetMS[k])
                    barStr = "+" + IntToString(Round(showChain_OffsetMS[k] / ((60000.0 / RecordedBPM) * IntToFloat(GetTimeSigNumerator())))) + "b"
                    showLine = "  \u21b3 " + barStr + "  " + LoopMasterActionName(showChain_ActionCode[k]) + " Ch" + (showChain_ChIdx[k] + 1) + "  (" + IntToString(showMS) + "ms)"
                    RecDisplayLines <-- showLine
                End
            end
```

Note: GPScript's `var` declarations may need to be at function top (per memory rule). If the compiler rejects inline `var`, move `masterChIdx`, `k`, `showMS`, `showLine`, `barStr` declarations to the top of the function along with the existing `i, partIdx, tms : Integer` line:

```gpscript
Function BuildRecDisplayLines()
    var i, partIdx, tms, masterChIdx, k, showMS : Integer
    var line, eType, valStr, showLine, barStr : String
```

Make the analogous change for the second loop (the `Arr_Rec_*` "NEW EVENTS" loop at ~line 4977-5002) — add the same `elsif eType == "LoopMaster"` branch and the same show-chain rendering block directly after the `RecDisplayLines <-- line` line.

- [ ] **Step 2: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(looper-tl): render LoopMaster + indented show chain in REC panel

BuildRecDisplayLines now recognizes the 'LoopMaster' event type,
renders it with the decoded action name and channel number, and
immediately below it inserts one indented line per entry in
ComputeShowChain(). Show lines carry bar offset, action name, target
channel, and absolute ms for quick cross-reference."
```

---

## Task 4: Add `ComputeNextLoopShowAction()` + OSC `/UI/LoopNext` broadcast

**Files:**
- Modify: `Global Rackspace.gpscript` — add helper near `ComputeShowChain`, wire broadcast into existing timer tick

- [ ] **Step 1: Add `ComputeNextLoopShowAction()` helper**

Place it directly after `ComputeShowChain()` in SECTION 19:

```gpscript
// ---------------------------------------------------------
// COMPUTE NEXT LOOP SHOW ACTION
// Walks Snap_TL_* (committed timeline) for the last LoopMaster event
// whose chain has not yet fully elapsed relative to the current
// playhead, runs ComputeShowChain, and returns the earliest future
// show entry as a (countdownMS, chIdx, actionCode) triple exposed via
// module-level scratch variables. countdownMS = -1 means "no active
// chain".
// ---------------------------------------------------------
Function ComputeNextLoopShowAction(playheadMS : Double)
   var i, k, masterChIdx, latestMasterIdx : Integer
   var masterTimeMS, eventAbsMS : Double
   var foundNext : Boolean = false

   nextLoopShow_CountdownMS = -1.0
   nextLoopShow_ChIdx = -1
   nextLoopShow_ActionCode = -1

   if not ShowProjectionsAllowed() then
       // leave the -1 sentinels in place
   else
       // Find the latest LoopMaster event whose timestamp is <= playheadMS
       latestMasterIdx = -1
       For i = 0; i < Size(Snap_TL_TimeMS); i = i + 1 Do
          if Snap_TL_Type[i] == "LoopMaster" and Snap_TL_TimeMS[i] <= playheadMS then
              latestMasterIdx = i
          end
       End

       if latestMasterIdx >= 0 then
          masterChIdx = DecodeLoopMasterChIdx(Snap_TL_Val[latestMasterIdx])
          masterTimeMS = Snap_TL_TimeMS[latestMasterIdx]
          ComputeShowChain(masterChIdx)

          // Find the earliest show entry whose absolute time is > playheadMS
          k = 0
          While k < Size(showChain_OffsetMS) and not foundNext Do
             eventAbsMS = masterTimeMS + showChain_OffsetMS[k]
             if eventAbsMS > playheadMS then
                 nextLoopShow_CountdownMS = eventAbsMS - playheadMS
                 nextLoopShow_ChIdx = showChain_ChIdx[k]
                 nextLoopShow_ActionCode = showChain_ActionCode[k]
                 foundNext = true
             end
             k = k + 1
          End
       end
   end
End
```

- [ ] **Step 2: Declare the scratch state for the next-action result**

In SECTION 11, just after the `showChain_*` arrays from Task 2:

```gpscript
   // Scratch for the next upcoming show action (OSC countdown)
   nextLoopShow_CountdownMS : Double = -1.0
   nextLoopShow_ChIdx : Integer = -1
   nextLoopShow_ActionCode : Integer = -1
```

- [ ] **Step 3: Wire the OSC broadcast into the timer tick**

Find the `On TimerTick` handler or the equivalent periodic refresh that already drives prompter / REC display updates. One safe landing zone is inside the `RefreshRecDisplay()` call chain or alongside the timer that dispatches to the display. For concreteness: locate the section near line 11990 where `StartTimelinePlayback` is called:

```gpscript
        if not TimelinePlaybackActive and not TimelineRecActive and Size(Snap_TL_TimeMS) > 0 then
            StartTimelinePlayback()
        end
```

This isn't the tick — but it's in the same file region that deals with Timeline playback. The actual per-tick code lives in one of the many `On TimerTick` handlers further down. Run a Grep for `On TimerTick` in `Global Rackspace.gpscript` and pick the one that already computes playhead position from `TimelinePlaybackActive`.

Add this code inside that tick handler, right after the playhead position is updated:

```gpscript
   // OSC-UI: next upcoming loop show action
   if TimelinePlaybackActive then
       ComputeNextLoopShowAction(CurrentPlayheadMS)   // use the tick's computed playhead
       if nextLoopShow_CountdownMS >= 0.0 then
           var countdownBars : Double = nextLoopShow_CountdownMS / ((60000.0 / RecordedBPM) * IntToFloat(GetTimeSigNumerator()))
           var countdownText : String = "-> " + LoopMasterActionName(nextLoopShow_ActionCode) + " Ch" + (nextLoopShow_ChIdx + 1) + " in " + IntToString(Round(countdownBars)) + "b (" + IntToString(Round(nextLoopShow_CountdownMS / 1000.0)) + "s)"
           OSC_SendStringSpecific("/UI/LoopNext", countdownText, Local_IP, Local_PORT)
           if DebugMode then Trace("LOOPER-TL: /UI/LoopNext = " + countdownText) end
       else
           OSC_SendStringSpecific("/UI/LoopNext", "", Local_IP, Local_PORT)
       end
   end
```

Replace `CurrentPlayheadMS` with the correct variable name that the tick handler already uses for the live playhead value. A grep for `TimelinePlaybackActive and` should reveal the surrounding logic.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(looper-tl): broadcast /UI/LoopNext countdown to OSC-UI

ComputeNextLoopShowAction finds the latest LoopMaster event before
the current playhead, runs ComputeShowChain, and selects the earliest
future chain entry. Result is a countdownMS/chIdx/actionCode triple.

The timer tick computes a human-readable countdown string ('-> OVR
Ch4 in 3b (4s)') and broadcasts it on /UI/LoopNext. When no chain is
active the field is cleared explicitly."
```

---

## Task 5: Handle `LoopMaster` in the `Arr_Rec_*` clear / save / commit paths

**Files:**
- Modify: `Global Rackspace.gpscript` — `RecordTimelineEvent` (~5424), Arr_Rec_* save path (~7690-7730), Arr_Rec_* clear paths (~7694, 11074, 12023, 12394, 12424), the Snap_TL_* Bar array handling (~10547)

- [ ] **Step 1: Verify `RecordTimelineEvent` accepts arbitrary event types**

Read lines 5424-5443. The function already writes whatever string you pass as `eventType` to `Arr_Rec_Type` without validation. No change needed — `"LoopMaster"` is just another type string.

- [ ] **Step 2: Check the Snap_TL_* save path**

Around line 7690–7730, the save path copies `Arr_Rec_Type` to `Snap_TL_Type` in a loop. That loop is type-agnostic and already carries any string, so `"LoopMaster"` events flow through unchanged. No code change required — just verify the lines and read them during subagent execution to confirm no filtering is applied.

- [ ] **Step 3: Check the Snap_TL_Bar computation**

At line 10547 the save path writes `Arr_TL_Bar <-- Arr_Rec_Bar[i]` etc. Since `LoopMaster` events carry real ms timestamps, they get proper bar numbers via the same conversion as other events. Confirm no filtering exists by reading around lines 10540-10560.

- [ ] **Step 4: Add a compact DebugMode trace on each affected path**

To make the subagent's and your own cross-check easier, add one trace at the top of the save loop:

Locate the save loop near line 7700 that starts with:

```gpscript
            Snap_TL_Type <-- Arr_Rec_Type[i]
            Snap_TL_Val <-- Arr_Rec_Val[i]
```

Add immediately after the closing `End` of that loop:

```gpscript
            if DebugMode then
               var lmCount : Integer = 0
               var idx : Integer
               For idx = 0; idx < Size(Snap_TL_Type); idx = idx + 1 Do
                   if Snap_TL_Type[idx] == "LoopMaster" then lmCount = lmCount + 1 end
               End
               Trace("LOOPER-TL: snapshot now contains " + lmCount + " LoopMaster events")
            end
```

This lets the E2E verification see how many LoopMaster events survived the save.

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "chore(looper-tl): trace LoopMaster counts through the Snap_TL save path

Adds a DebugMode trace after the Arr_Rec -> Snap_TL copy loop so the
E2E test can confirm that 'LoopMaster' events survive the timeline
commit unchanged. No behavioural change; the existing save path is
already type-agnostic."
```

---

## Verification (after all tasks)

No automated tests. After all commits, the user opens Gig Performer, reloads the rackspace with the updated script, and performs the following manual checks.

**A. Compile and cold-boot**

1. Paste the updated `Global Rackspace.gpscript`.
2. Compile — expect no compiler errors.

**B. Record a simple chain**

1. Load a song with `RecordedBPM > 0` and `SongDurationBars > 0`.
2. Set `Mem_Loop_Length[0] = 8`, `Mem_Loop_Action[0] = 1` (Play), `Mem_Loop_Target[0] = 3` (target Ch4) via the existing Looper widgets.
3. Set `Mem_Loop_Length[3] = 8`, `Mem_Loop_Action[3] = 0` (no further chain), `Mem_Loop_Target[3] = -1`.
4. Enable Timeline REC and manually trigger Loop Rec for Ch1.
5. Console expected:
   - `LOOPER-TL: LoopMaster REC Ch1 encoded`
   - `TIMELINE-REC: LoopMaster val=0 at Nms`
6. Stop Timeline REC.

**C. Check the REC panel display**

1. Scroll the REC display with `SLD_CurrentState`.
2. Expect to see a line like `12400ms | REC Ch1` followed by an indented `↳ +8b  PLAY Ch4  (20400ms)`.

**D. Check the OSC countdown**

1. Start Timeline Playback.
2. As the playhead approaches the LoopMaster timestamp, the OSC-UI `/UI/LoopNext` field stays empty.
3. The moment the playhead passes the LoopMaster, the field populates with `-> PLAY Ch4 in 8b (Ns)`.
4. As the playhead advances, the countdown decreases.
5. When the show entry's absolute time is reached, the field clears or shows the next entry (if any).

**E. Check the gate**

1. Load an empty gig (no song, `RecordedBPM == 0`).
2. Trigger Loop Rec and observe: no show lines appear (even though the event is recorded), and `/UI/LoopNext` stays empty.
3. Console expected: `LOOPER-TL: ComputeShowChain skipped (projections not allowed)`.

---

## Self-Review

**Spec coverage:** §3.1 (chain definition) — no code, just confirmation that `Mem_Loop_Target` already exists. §3.2 (engine hook) — no code, already implemented pre-existing. §3.3 (Master vs Show separation) — Task 1 (encoding + recording). §3.4 (projection gate) — Task 2 (`ShowProjectionsAllowed`). §3.5 (OSC countdown) — Task 4. §3.6 (REC panel text) — Task 3. §3.7 (conflict rules) — covered implicitly by the read-only Show design and the chain depth cap in Task 2.

**Placeholder scan:** Task 4 Step 3 contains "run a Grep to find the tick handler" which is an exploration step, not a placeholder. The actual code block is complete. Task 5 Steps 1–3 are verification steps, not placeholder stubs — they ask the subagent to confirm pre-existing behaviour, which is correct for GPScript's reality.

**Type consistency:** `LoopMasterActionName(Integer)` returns `String`, called in Tasks 3 and 4. `DecodeLoopMasterChIdx / DecodeLoopMasterActionCode` return `Integer`, match their call sites. `ShowProjectionsAllowed()` returns `Boolean`, used in `ComputeShowChain` and `ComputeNextLoopShowAction`. `showChain_OffsetMS` is `Double Array`, `showChain_ChIdx` and `showChain_ActionCode` are `Integer Array` — consistent across the two helpers. `nextLoopShow_CountdownMS` is `Double`, the other two `Integer` — consistent with the OSC broadcast code.
