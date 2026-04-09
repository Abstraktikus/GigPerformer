# Octaver Range & VelocityFader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable range boundaries and velocity fade for octave clone notes in the Note Prozessor, with Learn buttons and snapshot persistence.

**Architecture:** Three new parameters in the scriptlet (`p_OctRangeMin`, `p_OctRangeMax`, `p_OctRangeFade`), a helper function `GetOctRangeVelocity()` integrated into `PlayOutNote`/`StopOutNote`, four new widgets in the Global Rackspace with Learn logic and full snapshot support.

**Tech Stack:** GPScript (Gig Performer 5.x)

**Spec:** `docs/superpowers/specs/2026-04-09-octaver-range-design.md`

---

### Task 1: Add Scriptlet Parameters and Factory Reset

**Files:**
- Modify: `Note Prozessor.gpscript:57` (after `p_OctHigh`)
- Modify: `Note Prozessor.gpscript:137` (Panic trigger)
- Modify: `Note Prozessor.gpscript:155` (Factory Reset)

- [ ] **Step 1: Add three new parameters after `p_OctHigh` (line 57)**

Insert after line 57 (`p_OctHigh : Parameter 0 .. 3 = 0`):

```gpscript
   p_OctRangeMin     : Parameter 0 .. 127 = 0     // Lower boundary for clone notes
   p_OctRangeMax     : Parameter 0 .. 127 = 127   // Upper boundary for clone notes
   p_OctRangeFade    : Parameter 0 .. 1 = 0       // VelocityFader toggle
```

- [ ] **Step 2: Add new params to the Panic trigger (line 137)**

Change line 137 from:
```gpscript
On ParameterValueChanged matching p_Octaver, p_OctLow, p_OctLowOffset, p_OctHigh, p_OctHighOffset, p_OctaverMuteOrig, p_QuantizeActive, p_QuantKey, p_QuantScale
```
To:
```gpscript
On ParameterValueChanged matching p_Octaver, p_OctLow, p_OctLowOffset, p_OctHigh, p_OctHighOffset, p_OctaverMuteOrig, p_OctRangeMin, p_OctRangeMax, p_QuantizeActive, p_QuantKey, p_QuantScale
```

- [ ] **Step 3: Add new params to Factory Reset (line 155)**

Change line 155 from:
```gpscript
      p_Octaver = 0; p_OctLow = 0; p_OctLowOffset = 0; p_OctaverMuteOrig = 0; p_OctHighOffset = 0; p_OctHigh = 0
```
To:
```gpscript
      p_Octaver = 0; p_OctLow = 0; p_OctLowOffset = 0; p_OctaverMuteOrig = 0; p_OctHighOffset = 0; p_OctHigh = 0
      p_OctRangeMin = 0; p_OctRangeMax = 127; p_OctRangeFade = 0
```

- [ ] **Step 4: Verify scriptlet compiles in Gig Performer**

Open the scriptlet editor and press Compile. Expected: no errors, parameter list shows the three new entries.

- [ ] **Step 5: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "feat(np): add p_OctRangeMin, p_OctRangeMax, p_OctRangeFade parameters"
```

---

### Task 2: Implement GetOctRangeVelocity Helper Function

**Files:**
- Modify: `Note Prozessor.gpscript` (insert before `PlayOutNote`, around line 248)

- [ ] **Step 1: Add the helper function before PlayOutNote**

Insert before `// THE OCTAVER ENGINE` comment block (line 248):

```gpscript
// ---------------------------------------------------------
// OCTAVER RANGE: Velocity Gating & Edge Fade
// ---------------------------------------------------------
Function GetOctRangeVelocity(cloneNote : Integer, vel : Integer) Returns Integer
   var rangeMin, rangeMax, rangeSpan, dist : Integer
   var factor : Double = 1.0
   var res : Integer = vel
   
   rangeMin = Round(p_OctRangeMin)
   rangeMax = Round(p_OctRangeMax)
   
   // Gate: outside range -> suppress
   if cloneNote < rangeMin or cloneNote > rangeMax then
       res = 0
   else
       // VelocityFader: only when active AND range >= 10 notes
       rangeSpan = rangeMax - rangeMin
       if Round(p_OctRangeFade) == 1 and rangeSpan >= 10 then
           dist = cloneNote - rangeMin
           if dist < 5 then
               factor = (IntToFloat(dist) + 1.0) / 6.0
           else
               dist = rangeMax - cloneNote
               if dist < 5 then
                   factor = (IntToFloat(dist) + 1.0) / 6.0
               end
           end
           res = Round(IntToFloat(vel) * factor)
           if res < 1 then res = 1 end
       end
   end
   
   result = res
End
```

- [ ] **Step 2: Verify scriptlet compiles**

Open the scriptlet editor and press Compile. Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "feat(np): add GetOctRangeVelocity helper for range gating and edge fade"
```

---

### Task 3: Integrate Range Check into PlayOutNote and StopOutNote

**Files:**
- Modify: `Note Prozessor.gpscript:251-300` (PlayOutNote)
- Modify: `Note Prozessor.gpscript:302-346` (StopOutNote)

- [ ] **Step 1: Add `cloneVel` variable to PlayOutNote (line 252)**

Change line 252 from:
```gpscript
   var i, k, cloneNote : Integer
```
To:
```gpscript
   var i, k, cloneNote, cloneVel : Integer
```

- [ ] **Step 2: Replace Lower Octave guard in PlayOutNote (line 270-277)**

Change the lower octave block from:
```gpscript
               cloneNote = note - ((Round(p_OctLowOffset) + i) * 12)
               if cloneNote >= 0 and cloneNote <= 127 then
                   // Subtiler Humanizer: Die Oktaven wackeln alle GANZ LEICHT gegeneinander (fettes Strumming!)
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, vel, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```
To:
```gpscript
               cloneNote = note - ((Round(p_OctLowOffset) + i) * 12)
               cloneVel = GetOctRangeVelocity(cloneNote, vel)
               if cloneVel > 0 then
                   // Subtiler Humanizer: Die Oktaven wackeln alle GANZ LEICHT gegeneinander (fettes Strumming!)
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, cloneVel, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```

- [ ] **Step 3: Replace Upper Octave guard in PlayOutNote (line 285-291)**

Change the upper octave block from:
```gpscript
               cloneNote = note + ((Round(p_OctHighOffset) + i) * 12)
               if cloneNote >= 0 and cloneNote <= 127 then
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, vel, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```
To:
```gpscript
               cloneNote = note + ((Round(p_OctHighOffset) + i) * 12)
               cloneVel = GetOctRangeVelocity(cloneNote, vel)
               if cloneVel > 0 then
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, cloneVel, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```

- [ ] **Step 4: Replace Lower Octave guard in StopOutNote (line 319-325)**

Change from:
```gpscript
               cloneNote = note - ((Round(p_OctLowOffset) + i) * 12)
               if cloneNote >= 0 and cloneNote <= 127 then
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, 0, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```
To:
```gpscript
               cloneNote = note - ((Round(p_OctLowOffset) + i) * 12)
               if GetOctRangeVelocity(cloneNote, 1) > 0 then
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, 0, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```

- [ ] **Step 5: Replace Upper Octave guard in StopOutNote (line 332-338)**

Change from:
```gpscript
               cloneNote = note + ((Round(p_OctHighOffset) + i) * 12)
               if cloneNote >= 0 and cloneNote <= 127 then
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, 0, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```
To:
```gpscript
               cloneNote = note + ((Round(p_OctHighOffset) + i) * 12)
               if GetOctRangeVelocity(cloneNote, 1) > 0 then
                   if Round(p_HumanizeActive) == 1 then delayMS = GetHumanizedDelay(p_HumTimeAmount) end
                   msg = MakeNoteMessageEx(cloneNote, 0, chan)
                   if Round(p_AutoSustain) == 1 then AutoSustainer_Play(Sustainer, msg) 
                   else if delayMS > 0.0 then SendLater(msg, delayMS) else SendNow(msg) end end
               end
```

- [ ] **Step 6: Verify scriptlet compiles and test manually**

Compile the scriptlet. Then test:
1. Set `p_Octaver=1`, `p_OctLow=1`, `p_OctRangeMin=36`, `p_OctRangeMax=96`
2. Play notes near C2 (36) — lower clones below 36 should be silent
3. Play notes near C7 (96) — upper clones above 96 should be silent
4. Enable `p_OctRangeFade=1` — notes near boundaries should fade in/out

- [ ] **Step 7: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "feat(np): integrate OctRange gating into PlayOutNote and StopOutNote"
```

---

### Task 4: Add Widgets and Memory Arrays to Global Rackspace

**Files:**
- Modify: `Global Rackspace.gpscript:226-231` (Widget declarations)
- Modify: `Global Rackspace.gpscript:287` (State booleans)
- Modify: `Global Rackspace.gpscript:414-419` (Memory arrays, after OctHighOffset)

- [ ] **Step 1: Add widget declarations (after line 230, near other Octaver widgets)**

Insert after line 230 (`BTN_Inject_NP_OctHighOff_Down, LBL_Inject_NP_OctHighOffset, BTN_Inject_NP_OctHighOffset_Up`):

```gpscript
   BTN_LearnOctRangeMin, BTN_LearnOctRangeMax                                    : Widget
   LBL_Inject_NP_OctRange                                                        : Widget
   BTN_Inject_NP_OctRangeFade                                                    : Widget
```

- [ ] **Step 2: Add learn state booleans (near line 287, after existing IsLearning booleans)**

Add to the existing boolean line that contains `IsLearningMin, IsLearningMax`:

Change:
```gpscript
   IsBrowsingFavorites, IsLearningMin, IsLearningMax : Boolean = false
```
To:
```gpscript
   IsBrowsingFavorites, IsLearningMin, IsLearningMax : Boolean = false
   IsLearningOctRangeMin, IsLearningOctRangeMax : Boolean = false
```

- [ ] **Step 3: Add memory arrays (after line 419, Mem_NP_OctHighOffset)**

Insert after `Mem_NP_OctHighOffset`:

```gpscript
   Mem_NP_OctRangeMin     : Integer Array = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
   Mem_NP_OctRangeMax     : Integer Array = [127,127,127,127,127,127,127,127,127,127,127,127,127,127,127,127]
   Mem_NP_OctRangeFade    : Integer Array = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add OctRange widgets, state booleans, and memory arrays"
```

---

### Task 5: Add Channel Reset and Snapshot Load for OctRange

**Files:**
- Modify: `Global Rackspace.gpscript:1632` (Channel reset, after OctHighOffset reset)
- Modify: `Global Rackspace.gpscript:11385` (Snapshot load, after OctHighOffset read)

- [ ] **Step 1: Add reset for new params (after line 1632)**

After line 1632 (`Mem_NP_OctHigh[chIdx] = 0; Mem_NP_OctHighOffset[chIdx] = 0`), add:

```gpscript
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_OctRangeMin"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 0.0) end
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_OctRangeMax"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 1.0) end
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_OctRangeFade"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 0.0) end
```

And in the RAM reset block (after line 1652, `Mem_NP_OctHigh[chIdx] = 0; Mem_NP_OctHighOffset[chIdx] = 0`), add:

```gpscript
    Mem_NP_OctRangeMin[chIdx] = 0; Mem_NP_OctRangeMax[chIdx] = 127; Mem_NP_OctRangeFade[chIdx] = 0
```

- [ ] **Step 2: Add snapshot load readback (after line 11385)**

After line 11385 (`idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_OctHighOffset")...`), add:

```gpscript
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_OctRangeMin"); if idx > -1 then Mem_NP_OctRangeMin[i] = Round(GetParameter(BLK_NoteProcessor[i], idx) * 127.0) end
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_OctRangeMax"); if idx > -1 then Mem_NP_OctRangeMax[i] = Round(GetParameter(BLK_NoteProcessor[i], idx) * 127.0) end
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_OctRangeFade"); if idx > -1 then Mem_NP_OctRangeFade[i] = Round(GetParameter(BLK_NoteProcessor[i], idx)) end
```

Note: Snapshot **save** is already handled automatically by the generic delta-save loop (lines 10872-10890) which iterates all NP parameters. The `DEF_NoteProcessor` array is auto-populated from FactoryReset. No save-side changes needed.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add OctRange channel reset and snapshot load readback"
```

---

### Task 6: Add UI Update Logic for OctRange Display

**Files:**
- Modify: `Global Rackspace.gpscript:2122-2127` (UpdateInjectionNPDisplay, offline state)
- Modify: `Global Rackspace.gpscript:2148-2153` (UpdateInjectionNPDisplay, online state)

- [ ] **Step 1: Add offline state (after line 2127, after OctHighOffset "-")**

After line 2127 (`SetWidgetLabel(LBL_Inject_NP_OctHighOffset, "-")`), add:

```gpscript
      SetWidgetLabel(LBL_Inject_NP_OctRange, "-")
      SetWidgetValue(BTN_Inject_NP_OctRangeFade, 0.0)
      SetWidgetValue(BTN_LearnOctRangeMin, 0.0)
      SetWidgetValue(BTN_LearnOctRangeMax, 0.0)
```

- [ ] **Step 2: Add online state (after line 2153, after OctHighOffset display)**

After line 2153 (`SetWidgetLabel(LBL_Inject_NP_OctHighOffset, "Gap " + ...)`), add:

```gpscript
         // --- OCTAVE RANGE ---
         if Mem_NP_OctRangeMin[firstScopeIdx] == 0 and Mem_NP_OctRangeMax[firstScopeIdx] == 127 then
             SetWidgetLabel(LBL_Inject_NP_OctRange, "-")
         else
             SetWidgetLabel(LBL_Inject_NP_OctRange, GetLuxusLabel(Mem_NP_OctRangeMin[firstScopeIdx]) + " - " + GetLuxusLabel(Mem_NP_OctRangeMax[firstScopeIdx]))
         end
         SetWidgetValue(BTN_Inject_NP_OctRangeFade, IntToFloat(Mem_NP_OctRangeFade[firstScopeIdx]))
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add OctRange display in UpdateInjectionNPDisplay"
```

---

### Task 7: Add Learn Logic and Widget Callbacks

**Files:**
- Modify: `Global Rackspace.gpscript:8395` (ProcessMidiLearn function)
- Modify: `Global Rackspace.gpscript:12576-12583` (after existing learn callbacks)

- [ ] **Step 1: Extend ProcessMidiLearn (line 8395)**

Change the function from:
```gpscript
Function ProcessMidiLearn(m : NoteMessage)
   var noteNum, pIdx, vel, i : Integer
   var paramVal : Double = 0.0
   
   // Only respond when learning and the key is pressed
   if (IsLearningMin or IsLearningMax) and IsNoteOn(m) then
```
To:
```gpscript
Function ProcessMidiLearn(m : NoteMessage)
   var noteNum, pIdx, vel, i : Integer
   var paramVal : Double = 0.0
   
   // Only respond when learning and the key is pressed
   if (IsLearningMin or IsLearningMax or IsLearningOctRangeMin or IsLearningOctRangeMax) and IsNoteOn(m) then
```

- [ ] **Step 2: Add OctRange learn handling inside ProcessMidiLearn**

After the existing `end` of the `IsLearningMin`/`IsLearningMax` block (around line 8423, after the `End` of the For loop), but BEFORE the Auto-Off section, add a new branch. The full function body should become:

```gpscript
   if (IsLearningMin or IsLearningMax or IsLearningOctRangeMin or IsLearningOctRangeMax) and IsNoteOn(m) then
       
       noteNum = GetNoteNumber(m)
       paramVal = noteNum / 127.0
       
       // INJECTION: Push the value to all selected channels
       For i = 0; i < 16; i = i + 1 Do
          if OutputScope[i] then
             
             if IsLearningMin then
                SetParameter(BLK_NoteProcessor[i], 0, paramVal)
             elsif IsLearningMax then
                SetParameter(BLK_NoteProcessor[i], 1, paramVal)
             elsif IsLearningOctRangeMin then
                pIdx = GetParamIdxByName(BLK_NoteProcessor[i], "p_OctRangeMin")
                if pIdx > -1 then SetParameter(BLK_NoteProcessor[i], pIdx, paramVal) end
                Mem_NP_OctRangeMin[i] = noteNum
             elsif IsLearningOctRangeMax then
                pIdx = GetParamIdxByName(BLK_NoteProcessor[i], "p_OctRangeMax")
                if pIdx > -1 then SetParameter(BLK_NoteProcessor[i], pIdx, paramVal) end
                Mem_NP_OctRangeMax[i] = noteNum
             end
             
             if IsLearningMin or IsLearningMax then
                 UpdateChannelFade(i, 4, 0, 0.0) 
             end
             
             if not IsUpdatingMatrix then Trigger_NotesOff(i + 1) end
          end
       End
       
       // Auto-Off: End ALL learn modes
       IsLearningMin = false
       IsLearningMax = false
       IsLearningOctRangeMin = false
       IsLearningOctRangeMax = false
       SetWidgetValue(BTN_LearnMin, 0.0)
       SetWidgetValue(BTN_LearnMax, 0.0)
       SetWidgetValue(BTN_LearnOctRangeMin, 0.0)
       SetWidgetValue(BTN_LearnOctRangeMax, 0.0)
       
       // Update UI
       UpdateInjectionSplitDisplay()
       UpdateInjectionNPDisplay()
       UpdateMetaColors()
       
       if DebugMode then Trace("LEARN SUCCESS: Injected Note " + noteNum + " to Scope.") end
   end
```

- [ ] **Step 3: Add widget callbacks for Learn buttons (after line 12583)**

After the existing `BTN_LearnMax` callback, add:

```gpscript
On WidgetValueChanged(val : Double) from BTN_LearnOctRangeMin
   if val > 0.5 then
       IsLearningOctRangeMin = true
       IsLearningOctRangeMax = false; IsLearningMin = false; IsLearningMax = false
       SetWidgetValue(BTN_LearnOctRangeMax, 0.0); SetWidgetValue(BTN_LearnMin, 0.0); SetWidgetValue(BTN_LearnMax, 0.0)
   else IsLearningOctRangeMin = false end
End

On WidgetValueChanged(val : Double) from BTN_LearnOctRangeMax
   if val > 0.5 then
       IsLearningOctRangeMax = true
       IsLearningOctRangeMin = false; IsLearningMin = false; IsLearningMax = false
       SetWidgetValue(BTN_LearnOctRangeMin, 0.0); SetWidgetValue(BTN_LearnMin, 0.0); SetWidgetValue(BTN_LearnMax, 0.0)
   else IsLearningOctRangeMax = false end
End
```

- [ ] **Step 4: Add widget callback for OctRangeFade toggle**

After the learn callbacks, add:

```gpscript
On WidgetValueChanged(val : Double) from BTN_Inject_NP_OctRangeFade
   if not IsUpdatingNP then InjectNPToggle(10, "p_OctRangeFade", val) end
End
```

- [ ] **Step 5: Extend InjectNPToggle to handle paramType 10 (line 8165)**

After line 8165 (`elsif paramType == 9 then Mem_NP_QuantizeActive[i] = intVal`), add:

```gpscript
         elsif paramType == 10 then Mem_NP_OctRangeFade[i] = intVal
```

- [ ] **Step 6: Verify Global Rackspace compiles**

Compile the Global Rackspace script. Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add OctRange learn logic, widget callbacks, and toggle injection"
```

---

### Task 8: Create Widgets in Gig Performer UI

**Files:**
- Modify: Gig Performer `.gig` file (manual, in the GUI editor)

This task is done manually in Gig Performer's panel designer:

- [ ] **Step 1: Create the four widgets in the Octaver section of the injection panel**

1. `BTN_LearnOctRangeMin` — Button widget, handle: `BTN_LearnOctRangeMin`
2. `LBL_Inject_NP_OctRange` — Label widget, handle: `LBL_Inject_NP_OctRange`
3. `BTN_LearnOctRangeMax` — Button widget, handle: `BTN_LearnOctRangeMax`
4. `BTN_Inject_NP_OctRangeFade` — Button widget (toggle), handle: `BTN_Inject_NP_OctRangeFade`

- [ ] **Step 2: Layout**

Position: `[BTN_LearnOctRangeMin] [LBL_Inject_NP_OctRange] [BTN_LearnOctRangeMax]` in one row, `[BTN_Inject_NP_OctRangeFade]` below. Place near the existing Octaver controls.

- [ ] **Step 3: Verify handles are recognized**

Compile Global Rackspace script. All four widget references should resolve without errors.

- [ ] **Step 4: End-to-end test**

1. Select a channel, click Learn Low, press a key → label updates to show note
2. Click Learn High, press a key → label shows range
3. Toggle OctRangeFade → saved in memory
4. Save snapshot, reload → all values persist
5. Set range to < 10 notes, enable Fade → verify fade is bypassed (full velocity at edges)

---

### Task 9: Update Existing Learn Callbacks for Mutual Exclusion

**Files:**
- Modify: `Global Rackspace.gpscript:12576-12583` (existing BTN_LearnMin/Max callbacks)

- [ ] **Step 1: Extend BTN_LearnMin callback to deactivate OctRange learn**

Change:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LearnMin
   if val > 0.5 then IsLearningMin = true; IsLearningMax = false; SetWidgetValue(BTN_LearnMax, 0.0)
   else IsLearningMin = false end
End
```
To:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LearnMin
   if val > 0.5 then
       IsLearningMin = true
       IsLearningMax = false; IsLearningOctRangeMin = false; IsLearningOctRangeMax = false
       SetWidgetValue(BTN_LearnMax, 0.0); SetWidgetValue(BTN_LearnOctRangeMin, 0.0); SetWidgetValue(BTN_LearnOctRangeMax, 0.0)
   else IsLearningMin = false end
End
```

- [ ] **Step 2: Extend BTN_LearnMax callback to deactivate OctRange learn**

Change:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LearnMax
   if val > 0.5 then IsLearningMax = true; IsLearningMin = false; SetWidgetValue(BTN_LearnMin, 0.0)
   else IsLearningMax = false end
End
```
To:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LearnMax
   if val > 0.5 then
       IsLearningMax = true
       IsLearningMin = false; IsLearningOctRangeMin = false; IsLearningOctRangeMax = false
       SetWidgetValue(BTN_LearnMin, 0.0); SetWidgetValue(BTN_LearnOctRangeMin, 0.0); SetWidgetValue(BTN_LearnOctRangeMax, 0.0)
   else IsLearningMax = false end
End
```

- [ ] **Step 3: Verify mutual exclusion works**

1. Click Learn Min (KB Split) → OctRange learn buttons should be off
2. Click Learn OctRange Low → KB Split learn buttons should be off
3. Only one learn mode active at a time

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "fix(gr): add mutual exclusion between KB Split and OctRange learn modes"
```
