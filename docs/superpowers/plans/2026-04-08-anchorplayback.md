# AnchorPlayback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement passive chord-based part boundary detection that keeps the timeline anchored to the actual live performance.

**Architecture:** NoteProcessor V7.5 exposes detected root via output parameters. Global Rackspace parses root sequences from .gpchord files, runs a forward-only tracker in the timer callback, and triggers part changes + timeline corrections when part boundaries are detected. The existing `ChannelUsage` property ("Upper"/"Lower") determines which channel to read — no new widgets needed.

**Tech Stack:** GPScript (Gig Performer scripting language). No early return — use if/else. Initialize all Double vars with `= 0.0`.

**Spec:** `docs/superpowers/specs/2026-04-08-anchorplayback-design.md`

---

## File Structure

| File | Changes |
|------|---------|
| `Note Prozessor 7.4.gpscript` → rename to `Note Prozessor 7.5.gpscript` | Add `p_DetectedRoot`, `p_HasNotes`, always-on root calculation |
| `Global Rackspace.gpscript` | New variables, root sequence parser, forward-only tracker, ExecuteAnchorPartChange, UpdateAnchorChannels |

---

### Task 1: NoteProcessor V7.5 — Add Root Output Parameters

**Files:**
- Modify: `Note Prozessor 7.4.gpscript` (rename to `Note Prozessor 7.5.gpscript`)

**Context:** The NoteProcessor Scriptlet exists 16 times (one per channel). It already has `CalculateRootMath()` (line 378) and `heldNotes[]` (line 84). Currently root calculation only runs when `p_ChordMode == 1`. We need it to always run and expose the result.

- [ ] **Step 1: Add new output parameters**

After the existing `p_FactoryReset` parameter (line 74), add:

```gpscript
   // --- 12. ANCHOR OUTPUT (NEW V7.5) ---
   p_DetectedRoot  : Parameter 0 .. 11 = 0   // Pitch Class: 0=C, 2=D, 5=F, etc.
   p_HasNotes      : Parameter 0 .. 1 = 0    // 1 = at least one note held
```

- [ ] **Step 2: Add always-on root detection in NoteOn branch**

In the `On MidiEvent` handler (line 549), inside the NoteOn branch, after the existing engine logic block (after line 600, just before the closing `end` of the velocity range check), add the anchor output update:

Find this section (around line 590-601):
```gpscript
                    // PHASE 5: ENGINE LOGIK (Mono, Chord, POG)
                    if Round(p_MonoLowest) == 1 or Round(p_MonoHighest) == 1 then
                        AddMonoNote(transNote, newVel)
                        ProcessMonoLogic(chn)
                    else
                        if Round(p_ChordMode) == 1 then
                           AddHeldNote(transNote); UpdateChordLogic(chn)
                           if Round(p_MuteOriginal) == 0 then PlayOutNote(transNote, newVel, chn) end
                        else 
                           PlayOutNote(transNote, newVel, chn)
                        end
                    end
```

Replace with:

```gpscript
                    // PHASE 5: ENGINE LOGIK (Mono, Chord, POG)
                    if Round(p_MonoLowest) == 1 or Round(p_MonoHighest) == 1 then
                        AddMonoNote(transNote, newVel)
                        ProcessMonoLogic(chn)
                    else
                        if Round(p_ChordMode) == 1 then
                           AddHeldNote(transNote); UpdateChordLogic(chn)
                           if Round(p_MuteOriginal) == 0 then PlayOutNote(transNote, newVel, chn) end
                        else 
                           AddHeldNote(transNote)  // Track for anchor even without ChordMode
                           PlayOutNote(transNote, newVel, chn)
                        end
                    end
                    // ANCHOR: Always update root output
                    p_HasNotes = 1
                    if Size(heldNotes) >= 2 then
                        p_DetectedRoot = CalculateRootMath(transNote) % 12
                    else
                        p_DetectedRoot = transNote % 12
                    end
```

- [ ] **Step 3: Add always-on root detection in NoteOff branch**

In the NoteOff branch (around line 605-623), find:

```gpscript
             if Round(p_MonoLowest) == 1 or Round(p_MonoHighest) == 1 then
                 RemoveMonoNote(transNote)
                 ProcessMonoLogic(chn)
             else
                 if Round(p_ChordMode) == 1 then
                    RemoveHeldNote(transNote); UpdateChordLogic(chn)
                    if Round(p_MuteOriginal) == 0 then StopOutNote(transNote, chn) end
                 else 
                    StopOutNote(transNote, chn)
                 end
             end
```

Replace with:

```gpscript
             if Round(p_MonoLowest) == 1 or Round(p_MonoHighest) == 1 then
                 RemoveMonoNote(transNote)
                 ProcessMonoLogic(chn)
             else
                 if Round(p_ChordMode) == 1 then
                    RemoveHeldNote(transNote); UpdateChordLogic(chn)
                    if Round(p_MuteOriginal) == 0 then StopOutNote(transNote, chn) end
                 else 
                    RemoveHeldNote(transNote)  // Track for anchor even without ChordMode
                    StopOutNote(transNote, chn)
                 end
             end
             // ANCHOR: Update root output
             if Size(heldNotes) > 0 then
                 p_HasNotes = 1
                 if Size(heldNotes) >= 2 then
                     var lowNote : Integer = heldNotes[0]
                     var li : Integer
                     for li = 1; li < Size(heldNotes); li = li + 1 do
                         if heldNotes[li] < lowNote then lowNote = heldNotes[li] end
                     end
                     p_DetectedRoot = CalculateRootMath(lowNote) % 12
                 else
                     p_DetectedRoot = heldNotes[0] % 12
                 end
             else
                 p_HasNotes = 0
             end
```

- [ ] **Step 4: Add to Factory Reset**

In the `On ParameterValueChanged matching p_FactoryReset` handler (line 141), add before `ExecutePanic()`:

```gpscript
      p_DetectedRoot = 0; p_HasNotes = 0
```

- [ ] **Step 5: Update version string**

Change line 92:
```gpscript
   SetDisplayMessage("V7.5 - Ultimate Strip (AnchorRoot, VelRange, Quantizer, Humanizer, POG)")
```

- [ ] **Step 6: Commit**

```bash
git add "Note Prozessor 7.4.gpscript"
git commit -m "feat(noteprocessor): V7.5 — add p_DetectedRoot and p_HasNotes output parameters

Always-on root detection via CalculateRootMath(). Exposes pitch class
(0-11) and note-held flag for AnchorPlayback consumption by the
Global Rackspace. AddHeldNote/RemoveHeldNote now also called when
ChordMode is off, so root tracking works in all modes."
```

---

### Task 2: Global Rackspace — Anchor State Variables and UpdateAnchorChannels

**Files:**
- Modify: `Global Rackspace.gpscript`

**Context:** The `ChannelUsage[]` array (line 73) already has "Upper" and "Lower" categories. We don't need new Manual widgets — just scan `ChannelUsage[]` for "Lower"/"Upper" to find the anchor channels.

- [ ] **Step 1: Add anchor state variables**

After the existing timeline state variables (line 314, after `TimelinePlaybackActive`), add:

```gpscript
    // --- ANCHORPLAYBACK STATE ---
    AnchorLowerChIdx      : Integer = -1    // First channel with Usage = "Lower"
    AnchorUpperChIdx      : Integer = -1    // First channel with Usage = "Upper"
    AnchorCurrentPartIdx  : Integer = 0     // Which part Anchor thinks is active
    AnchorRootCursor      : Integer = 0     // Position in current part's root sequence
    AnchorMatchCount      : Integer = 0     // Consecutive matches against NEXT part
    AnchorLastRoot        : Integer = -1    // Last detected root (pitch class), -1 = none
    AnchorDetectedRootIdx : Integer = -1    // Cached param index for p_DetectedRoot
    AnchorHasNotesIdx     : Integer = -1    // Cached param index for p_HasNotes
```

- [ ] **Step 2: Add root sequence arrays**

After the existing `Snap_TL_Fired` array declaration (line 557), add:

```gpscript
   // --- ANCHOR ROOT SEQUENCE (parsed from .gpchord) ---
   Arr_PartRootSeq   : Integer Array   // All roots concatenated (pitch classes 0-11)
   Arr_PartRootStart : Integer Array   // Start index in Arr_PartRootSeq per part
   Arr_PartRootLen   : Integer Array   // Number of roots per part
```

- [ ] **Step 3: Add UpdateAnchorChannels function**

Add this function near the existing `CycleChannelUsage()` function (after line 9185):

```gpscript
Function UpdateAnchorChannels()
   var i : Integer
   AnchorLowerChIdx = -1
   AnchorUpperChIdx = -1
   For i = 0; i < 16; i = i + 1 Do
       if ChannelUsage[i] == "Lower" and AnchorLowerChIdx == -1 then AnchorLowerChIdx = i end
       if ChannelUsage[i] == "Upper" and AnchorUpperChIdx == -1 then AnchorUpperChIdx = i end
   End

   // Cache parameter indices (only need to do this once, all NoteProcessors have same layout)
   if AnchorDetectedRootIdx == -1 then
       var probeIdx : Integer = 0
       if AnchorLowerChIdx >= 0 then probeIdx = AnchorLowerChIdx
       elsif AnchorUpperChIdx >= 0 then probeIdx = AnchorUpperChIdx
       end
       AnchorDetectedRootIdx = GetParamIdxByName(BLK_NoteProcessor[probeIdx], "p_DetectedRoot")
       AnchorHasNotesIdx = GetParamIdxByName(BLK_NoteProcessor[probeIdx], "p_HasNotes")
   end

   Trace("ANCHOR: Lower=Ch" + IntToString(AnchorLowerChIdx + 1) + " Upper=Ch" + IntToString(AnchorUpperChIdx + 1))
End
```

- [ ] **Step 4: Call UpdateAnchorChannels from CycleChannelUsage**

In `CycleChannelUsage()` (line 9136), add `UpdateAnchorChannels()` after the existing `UpdateMetaColors()` call at line 9182:

```gpscript
       // 5. UI Updates
       RefreshAllInjectionDisplays()
       UpdateMetaColors()
       UpdateAnchorChannels()
       
   end // Ende vom Zaun
```

- [ ] **Step 5: Call UpdateAnchorChannels from controller map load**

In the controller map load/restore section (around line 11234, after `ChannelUsage[i] = targetUsage[i]` loop), add after the loop's `End` (after line 11235):

```gpscript
            UpdateAnchorChannels()
```

- [ ] **Step 6: Reset anchor state in On Song callback**

In the `On Song` handler (line 13181), after the existing `StripLiveDirty = false` (line 13205), add:

```gpscript
   StripLiveDirty = false
   AnchorCurrentPartIdx = 0
   AnchorRootCursor = 0
   AnchorMatchCount = 0
   AnchorLastRoot = -1
```

- [ ] **Step 7: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(anchor): add state variables, root sequence arrays, and UpdateAnchorChannels

Scans ChannelUsage for Lower/Upper to determine anchor source channels.
Caches NoteProcessor parameter indices for p_DetectedRoot and p_HasNotes.
Resets anchor state on song change."
```

---

### Task 3: Root Sequence Parser — Extract Roots from .gpchord

**Files:**
- Modify: `Global Rackspace.gpscript`

**Context:** During song load, `ParseSongData()` (line 10382) populates `Arr_PartText_Raw[]` with raw text blocks per part. These contain `[Dm]`, `[F]`, `[C]` etc. We need to extract root pitch classes from these blocks.

- [ ] **Step 1: Add ChordNameToRoot helper function**

Add this before `ParseSongData()` (before line 10382):

```gpscript
Function ChordNameToRoot(chordName : String) Returns Integer
   // Extracts root pitch class (0-11) from chord name like "Dm", "F#m7", "Bb"
   // Returns -1 if unparseable
   var root : Integer = -1
   var first, second : String

   if Length(chordName) == 0 then result = -1
   else
       first = CopySubstring(chordName, 0, 1)

       if first == "C" then root = 0
       elsif first == "D" then root = 2
       elsif first == "E" then root = 4
       elsif first == "F" then root = 5
       elsif first == "G" then root = 7
       elsif first == "A" then root = 9
       elsif first == "B" then root = 11
       elsif first == "H" then root = 11
       end

       if root >= 0 and Length(chordName) >= 2 then
           second = CopySubstring(chordName, 1, 1)
           if second == "#" then
               root = root + 1
               if root > 11 then root = 0 end
           elsif second == "b" then
               root = root - 1
               if root < 0 then root = 11 end
           end
       end

       result = root
   end
End
```

- [ ] **Step 2: Add ParsePartRoots function**

Add after `ChordNameToRoot`:

```gpscript
Function ParsePartRoots()
   // Extracts root pitch classes from Arr_PartText_Raw chord notation [Dm], [F], etc.
   // Populates flat arrays: Arr_PartRootSeq, Arr_PartRootStart, Arr_PartRootLen
   var i, j, blockLen, rootPC, lastRoot : Integer
   var block, chordName, c : String
   var inChord : Boolean = false
   var partStart, partCount : Integer

   Arr_PartRootSeq = []; Arr_PartRootStart = []; Arr_PartRootLen = []

   For i = 0; i < Size(Arr_PartText_Raw); i = i + 1 Do
       block = Arr_PartText_Raw[i]
       blockLen = Length(block)
       partStart = Size(Arr_PartRootSeq)
       partCount = 0
       lastRoot = -1
       chordName = ""
       inChord = false

       j = 0
       While j < blockLen Do
           c = CopySubstring(block, j, 1)
           if c == "[" then
               inChord = true
               chordName = ""
           elsif c == "]" then
               inChord = false
               rootPC = ChordNameToRoot(chordName)
               // Deduplicate consecutive identical roots
               if rootPC >= 0 and rootPC != lastRoot then
                   Arr_PartRootSeq <-- rootPC
                   partCount = partCount + 1
                   lastRoot = rootPC
               end
           elsif inChord then
               chordName = chordName + c
           end
           j = j + 1
       End

       Arr_PartRootStart <-- partStart
       Arr_PartRootLen <-- partCount
   End

   Trace("ANCHOR: Parsed " + Size(Arr_PartRootSeq) + " roots across " + Size(Arr_PartRootStart) + " parts.")
End
```

- [ ] **Step 3: Call ParsePartRoots from ParseSongData**

In `ParseSongData()`, after the existing `Arr_SectionNames` population loop ends (around line 10530, search for the end of the While loop that appends to Arr_SectionNames), add:

```gpscript
   ParsePartRoots()
   UpdateAnchorChannels()
```

The exact insertion point: search for where `ParseSongData` ends or where it returns control. Add the call just before the function's `End` statement.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(anchor): parse root pitch classes from .gpchord chord notation

ChordNameToRoot converts chord names (Dm, F#m7, Bb) to pitch classes (0-11).
ParsePartRoots extracts and deduplicates roots per part into flat arrays.
Called at song load after ParseSongData populates Arr_PartText_Raw."
```

---

### Task 4: Forward-Only Root Tracker in Timer Callback

**Files:**
- Modify: `Global Rackspace.gpscript`

**Context:** The timer callback `On TimerTick` (line 13695) runs continuously. The timeline playback block is at line 14125. We add the anchor tracker right after the timeline playback block.

- [ ] **Step 1: Add the tracker function**

Add before the `On TimerTick` callback (before line 13695):

```gpscript
Function ProcessAnchorPlayback()
   var currentRoot, nextPartIdx, expectedRoot, nextExpectedRoot : Integer
   var hasLower, hasUpper : Boolean = false
   var srcChIdx : Integer = -1

   // 1. GATE: Feature active? Channels configured? Root data available?
   if GetWidgetValue(BTN_MIDIAnchorPlayback) < 0.5 then // Feature off
   elsif Size(Arr_PartRootSeq) == 0 then // No chord data
   elsif AnchorDetectedRootIdx == -1 then // Parameters not cached
   else
       // 2. READ ROOT from Lower (fallback: Upper)
       if AnchorLowerChIdx >= 0 then
           if GetParameter(BLK_NoteProcessor[AnchorLowerChIdx], AnchorHasNotesIdx) > 0.5 then
               srcChIdx = AnchorLowerChIdx
           end
       end
       if srcChIdx == -1 and AnchorUpperChIdx >= 0 then
           if GetParameter(BLK_NoteProcessor[AnchorUpperChIdx], AnchorHasNotesIdx) > 0.5 then
               srcChIdx = AnchorUpperChIdx
           end
       end

       if srcChIdx >= 0 then
           currentRoot = Round(GetParameter(BLK_NoteProcessor[srcChIdx], AnchorDetectedRootIdx) * 11.0)

           // 3. DEDUPLICATE — same root as last time, no new info
           if currentRoot != AnchorLastRoot then
               AnchorLastRoot = currentRoot

               // 4. TRACK against current part
               if AnchorCurrentPartIdx < Size(Arr_PartRootStart) then
                   if AnchorRootCursor < Arr_PartRootLen[AnchorCurrentPartIdx] then
                       expectedRoot = Arr_PartRootSeq[Arr_PartRootStart[AnchorCurrentPartIdx] + AnchorRootCursor]
                       if currentRoot == expectedRoot then
                           AnchorRootCursor = AnchorRootCursor + 1
                           if AnchorRootCursor >= Arr_PartRootLen[AnchorCurrentPartIdx] then
                               AnchorRootCursor = 0  // Wrap — part is repeating
                           end
                       end
                   end
               end

               // 5. CHECK against next part
               nextPartIdx = AnchorCurrentPartIdx + 1
               if nextPartIdx < Size(Arr_PartRootStart) then
                   if AnchorMatchCount < Arr_PartRootLen[nextPartIdx] then
                       nextExpectedRoot = Arr_PartRootSeq[Arr_PartRootStart[nextPartIdx] + AnchorMatchCount]
                       if currentRoot == nextExpectedRoot then
                           AnchorMatchCount = AnchorMatchCount + 1
                       else
                           AnchorMatchCount = 0  // Reset
                       end
                   end

                   // 6. TRIGGER part change at threshold
                   if AnchorMatchCount >= 2 then
                       AnchorCurrentPartIdx = nextPartIdx
                       AnchorRootCursor = AnchorMatchCount
                       AnchorMatchCount = 0
                       ExecuteAnchorPartChange(AnchorCurrentPartIdx)
                   end
               end
           end
       end
   end
End
```

- [ ] **Step 2: Add ExecuteAnchorPartChange function**

Add right after `ProcessAnchorPlayback`:

```gpscript
Function ExecuteAnchorPartChange(newPartIdx : Integer)
   var i, markerEventIdx : Integer
   var sectionName : String = ""

   if newPartIdx < Size(Arr_SectionNames) then sectionName = Arr_SectionNames[newPartIdx] end

   // 1. ALWAYS: Update prompter display
   PreviewPartIdx = newPartIdx
   UpdatePrompter(false)

   // 2. ALWAYS: Fire Marker event (catch up part-change display)
   if newPartIdx < Size(Arr_SectionNames) then
       OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> ANCHOR: " + sectionName + " <<<", Local_IP, Local_PORT)
       MacroFeedbackTimer = TimeSinceStartup() + 2000.0
   end

   // 3. TIMEJUMP: Correct timeline position if enabled
   if GetWidgetValue(BTN_TimeJump) > 0.5 and TimelinePlaybackActive then
       // Find the Marker event for this part in the timeline
       markerEventIdx = -1
       i = 0
       While i < Size(Snap_TL_Type) and markerEventIdx == -1 Do
           if Snap_TL_Type[i] == "Marker" and Snap_TL_Val[i] == newPartIdx then
               markerEventIdx = i
           end
           i = i + 1
       End

       if markerEventIdx >= 0 then
           // Adjust PlaybackStartTimeMS so msSinceSongStart aligns with the marker's ms
           PlaybackStartTimeMS = TimeSinceStartup() - Snap_TL_TimeMS[markerEventIdx]
           Trace("ANCHOR: TimeJump -> Corrected timeline to " + Round(Snap_TL_TimeMS[markerEventIdx]) + "ms (Part: " + sectionName + ")")
       end
   end

   Trace("ANCHOR: Part change -> " + sectionName + " (idx=" + newPartIdx + ")")
End
```

- [ ] **Step 3: Call ProcessAnchorPlayback from TimerTick**

In the `On TimerTick` callback, after the timeline playback block (after the `StripLiveDirty` restore block ending around line 14149), add:

```gpscript
        // --- ANCHORPLAYBACK (chord-based part tracking) ---
        ProcessAnchorPlayback()
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(anchor): implement forward-only root tracker and timeline integration

ProcessAnchorPlayback reads detected root from NoteProcessor, tracks
against current part's root sequence, detects boundary when 2 consecutive
roots match the next part. ExecuteAnchorPartChange updates prompter,
fires marker event, and optionally corrects timeline position via TimeJump."
```

---

### Task 5: Verification and Integration Test

**Files:**
- Read: `Global Rackspace.gpscript`, `Note Prozessor 7.4.gpscript`

- [ ] **Step 1: Verify NoteProcessor parameter declarations**

Search `Note Prozessor 7.4.gpscript` for `p_DetectedRoot` and `p_HasNotes`:
- Should appear in: variable declaration, NoteOn branch, NoteOff branch, factory reset
- `CalculateRootMath` should be called in both NoteOn and NoteOff when ChordMode is off

- [ ] **Step 2: Verify Global Rackspace variables**

Search `Global Rackspace.gpscript` for:
- `AnchorLowerChIdx` — should appear in: declaration, UpdateAnchorChannels, ProcessAnchorPlayback, On Song reset
- `Arr_PartRootSeq` — should appear in: declaration, ParsePartRoots, ProcessAnchorPlayback
- `AnchorMatchCount` — should appear in: declaration, ProcessAnchorPlayback, On Song reset

- [ ] **Step 3: Verify function call chain**

Trace the call chain:
1. Song load → `ParseSongData()` → `ParsePartRoots()` → `UpdateAnchorChannels()` ✓
2. Controller map load → `UpdateAnchorChannels()` ✓
3. Channel usage change → `CycleChannelUsage()` → `UpdateAnchorChannels()` ✓
4. Timer tick → `ProcessAnchorPlayback()` → `ExecuteAnchorPartChange()` ✓
5. Song change → reset all anchor state ✓

- [ ] **Step 4: Verify edge cases in code**

Check:
- `ProcessAnchorPlayback` gates on `BTN_MIDIAnchorPlayback`, `Size(Arr_PartRootSeq) > 0`, and `AnchorDetectedRootIdx != -1`
- Last part (no next) → `nextPartIdx < Size(Arr_PartRootStart)` prevents out-of-bounds
- Empty chord data for a part → `Arr_PartRootLen[i] == 0` → cursor stays at 0, no tracking
- `AnchorRootCursor` wraps when reaching end of part (repeating section)

- [ ] **Step 5: Manual test checklist**

In Gig Performer:
1. Load a song with `.gpchord` file containing sections with different chord progressions
2. Set one channel to Usage = "Lower"
3. Enable `BTN_MIDIAnchorPlayback`
4. Play the chord progression on the Lower channel
5. Verify: Prompter advances to next part when the chord sequence matches
6. Verify: HUD shows ">>> ANCHOR: [SectionName] <<<"
7. Enable `BTN_TimeJump` + start timeline playback → verify timeline position corrects on part change
8. Disable `BTN_MIDIAnchorPlayback` → verify no anchor processing occurs
9. Switch songs → verify anchor state resets cleanly
