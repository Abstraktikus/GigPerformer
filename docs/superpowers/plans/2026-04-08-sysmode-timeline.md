# SYS-MODE 4: TIMELINE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SYS-MODE 4 "TIMELINE" with ms-based recording/playback, sticky state for all modes, and SYSMODE macros for MiniLab access.

**Architecture:** All changes are in `Global Rackspace V26.gpscript` (single-file GPScript codebase). New Timeline state/arrays go into Section 2 (variables). New functions go near existing SYS-MODE functions. Existing functions (sustain handler, ProcessSystemNavigation, RecordTimelineEvent, playback loop, persistence) are modified in-place. Since GPScript has no unit test framework, verification uses `Trace()` output and manual inspection.

**Tech Stack:** GPScript 5.x (Pascal-like, runs inside Gig Performer)

**Spec:** `docs/superpowers/specs/2026-04-08-sysmode-timeline-design.md`

---

### Task 1: State Variables & SysModeNames

**Files:**
- Modify: `Global Rackspace V26.gpscript:81` (SysModeNames)
- Modify: `Global Rackspace V26.gpscript:278` (near GlobalSystemMode)
- Modify: `Global Rackspace V26.gpscript:292` (near SystemModeActive)
- Modify: `Global Rackspace V26.gpscript:518-521` (timeline arrays)

- [ ] **Step 1: Expand SysModeNames array**

At line 81, change:
```gpscript
SysModeNames : String Array = ["VOICE SELECTOR", "LOOPER CONTROL", "CONTROLLER MAP", "STRIP-CONTROL"]
```
to:
```gpscript
SysModeNames : String Array = ["VOICE SELECTOR", "LOOPER CONTROL", "CONTROLLER MAP", "STRIP-CONTROL", "TIMELINE"]
```

- [ ] **Step 2: Add Timeline sub-mode and sticky state variables**

After line 292 (`SystemModeActive : Boolean = false`), add:
```gpscript
    // --- TIMELINE SUB-MODE STATE ---
    TimelineSubMode : Integer = 0        // 0 = PLAY, 1 = REC
    TimelineRecState : Integer = 0       // 0 = Replace, 1 = Overdub, 2 = Discard
    TimelineRecActive : Boolean = false  // True while ms timer is running
    TimelineCurrentPartIdx : Integer = 1 // Next part to record (0 = Intro implicit)
    PreviewPartIdx : Integer = 0         // Part Jump preview index

    // --- STICKY SYS-MODE STATE (all modes) ---
    StickySystemMode : Integer = -1          // -1 = no sticky, 0-4 = remembered mode
    StickyTimelineSubMode : Integer = 0
    StickyTimelineRecState : Integer = 0
```

- [ ] **Step 3: Add Timeline timing variables**

After the variables added in Step 2, add:
```gpscript
    // --- TIMELINE TIMING ---
    TimelineCountInTimer : Double = 0.0      // Absolute expiry time for count-in
    RecordStartTimeMS : Double = 0.0         // Set when count-in expires (t=0)
    RecordEndTimeMS : Double = 0.0           // Set at END OF SONG
    PlaybackStartTimeMS : Double = 0.0       // Set when playback begins
    TimelinePlaybackActive : Boolean = false // True during ms-based playback
```

- [ ] **Step 4: Replace timeline arrays with ms-based versions**

At lines 519-521, replace:
```gpscript
    Arr_TL_Type, Arr_Rec_Type : String Array
    Arr_SectionLineIndices, Arr_BarTriggers, Arr_PartAnchors, Arr_TL_Bar, Arr_Rec_Bar, Arr_TL_Val, Arr_Rec_Val, Arr_TL_Offset, Arr_Rec_Offset : Integer Array 
    Arr_TL_Fired : Boolean Array
```
with:
```gpscript
    Arr_TL_Type, Arr_Rec_Type : String Array
    Arr_SectionLineIndices, Arr_BarTriggers, Arr_PartAnchors, Arr_TL_Val, Arr_Rec_Val : Integer Array
    Arr_TL_Bar, Arr_TL_Offset, Arr_Rec_Bar, Arr_Rec_Offset : Integer Array  // Legacy bar arrays (kept for bar calculation)
    Arr_TL_Fired : Boolean Array

    // --- MS-BASED TIMELINE ARRAYS ---
    // Working (current recording session)
    Arr_Rec_TimeMS : Double Array        // Absolute ms since RecordStartTimeMS
    // Committed (last good state = playback source)
    Snap_TL_TimeMS : Double Array
    Snap_TL_Type : String Array
    Snap_TL_Val : Integer Array
    Snap_TL_Fired : Boolean Array
```

**Note:** We keep `Arr_TL_Bar`, `Arr_TL_Offset`, `Arr_Rec_Bar`, `Arr_Rec_Offset` for now because other parts of the codebase reference them (e.g. `BuildRecDisplayLines`, `RefreshRecDisplay`). They become secondary storage populated by bar calculation after END OF SONG. The primary recording path uses `Arr_Rec_TimeMS`.

- [ ] **Step 5: Add BTN_TL_HostSync widget declaration**

At line 247, after `BTN_Loop_HostSync, BTN_Loop_CountIn : Widget`, add:
```gpscript
    BTN_TL_HostSync : Widget
```

- [ ] **Step 6: Add SYSMODE macro index variables**

Near line 415 (where `VST_SCOPE_MacroIdx` is declared), add:
```gpscript
    SYSMODE_CYCLE_MacroIdx : Integer = -1; SYSMODE_CYCLE_CCIdx : Integer = -1
    SYSMODE_SELECT_MacroIdx : Integer = -1; SYSMODE_SELECT_CCIdx : Integer = -1
```

- [ ] **Step 7: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): add state variables, ms-based arrays, and widget declarations"
```

---

### Task 2: Sticky SYS-MODE State

**Files:**
- Modify: `Global Rackspace V26.gpscript:9457-9468` (sustain handler in ProcessHardwareCC)
- Modify: `Global Rackspace V26.gpscript:7540-7554` (CycleGlobalSystemMode)

- [ ] **Step 1: Modify sustain handler for sticky state**

At lines 9457-9467, replace the sustain handler block:
```gpscript
    elsif SYSTEM_TOGGLE_CCIdx == cc then
        SystemModeActive = (val > 0.5)
        if SystemModeActive then
            mName = SysModeNames[GlobalSystemMode]
            Trace("SYS-MODE: ON -> " + mName + " (via CC" + cc + ")")
            OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> " + mName + " <<<", Local_IP, Local_PORT)
            MacroFeedbackTimer = TimeSinceStartup() + 2000.0
            MacroFeedbackLockTimer = TimeSinceStartup() + 2000.0
        else
            Trace("SYS-MODE: OFF") 
        end
```
with:
```gpscript
    elsif SYSTEM_TOGGLE_CCIdx == cc then
        if val > 0.5 then
            // SUSTAIN PRESS: Restore sticky state or enter fresh
            SystemModeActive = true
            if StickySystemMode >= 0 then
                GlobalSystemMode = StickySystemMode
                if StickySystemMode == 4 then
                    TimelineSubMode = StickyTimelineSubMode
                    TimelineRecState = StickyTimelineRecState
                end
                Trace("SYS-MODE: RESTORED -> " + SysModeNames[GlobalSystemMode])
            end
            mName = SysModeNames[GlobalSystemMode]
            OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> " + mName + " <<<", Local_IP, Local_PORT)
            MacroFeedbackTimer = TimeSinceStartup() + 2000.0
            MacroFeedbackLockTimer = TimeSinceStartup() + 2000.0
        else
            // SUSTAIN RELEASE: Save sticky state, do NOT stop Timeline recording
            StickySystemMode = GlobalSystemMode
            if GlobalSystemMode == 4 then
                StickyTimelineSubMode = TimelineSubMode
                StickyTimelineRecState = TimelineRecState
            end
            SystemModeActive = false
            Trace("SYS-MODE: OFF (sticky=" + StickySystemMode + ")")
        end
```

- [ ] **Step 2: Reset sticky state on explicit mode change**

At lines 7540-7554, in `CycleGlobalSystemMode()`, after line 7545 (`if GlobalSystemMode > 3 then GlobalSystemMode = 0 end`), change the upper bound and add sticky reset:
```gpscript
Function CycleGlobalSystemMode()
    var modeName : String
    
    StickySystemMode = -1  // Reset sticky on explicit mode change

    GlobalSystemMode = GlobalSystemMode + 1
    if GlobalSystemMode > 4 then GlobalSystemMode = 0 end

    modeName = SysModeNames[GlobalSystemMode]

    Trace("SYS-MODE: Switched to " + modeName)
    OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> SYS-MODE: " + modeName + " <<<", Local_IP, Local_PORT)
    MacroFeedbackTimer = TimeSinceStartup() + 2000.0
    MacroFeedbackLockTimer = TimeSinceStartup() + 2000.0
End
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): implement sticky SYS-MODE state for all modes"
```

---

### Task 3: SYSMODE_CYCLE and SYSMODE_SELECT Macros

**Files:**
- Modify: `Global Rackspace V26.gpscript:9453-9454` (ProcessHardwareCC macro dispatch area)
- Modify: `Global Rackspace V26.gpscript:2879-2881` (CtrlInfo display area for macro labels)

- [ ] **Step 1: Add SelectGlobalSystemMode function**

Add near `CycleGlobalSystemMode()` (after line ~7554):
```gpscript
Function SelectGlobalSystemMode(targetMode : Integer)
    var modeName : String
    
    if targetMode < 0 or targetMode > 4 then
        Trace("SYSMODE_SELECT: Invalid mode " + targetMode)
        Exit
    end
    
    StickySystemMode = -1  // Reset sticky on explicit mode change
    GlobalSystemMode = targetMode
    SystemModeActive = true
    
    modeName = SysModeNames[GlobalSystemMode]
    Trace("SYS-MODE: Selected " + modeName)
    OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> SYS-MODE: " + modeName + " <<<", Local_IP, Local_PORT)
    MacroFeedbackTimer = TimeSinceStartup() + 2000.0
    MacroFeedbackLockTimer = TimeSinceStartup() + 2000.0
End
```

- [ ] **Step 2: Add macro dispatch in ProcessHardwareCC**

Near lines 9453-9454 (where `VST_SCOPE_CCIdx` is handled), add the SYSMODE macro handlers:
```gpscript
    // --- SYSMODE MACROS ---
    elsif SYSMODE_CYCLE_CCIdx == cc and val > 0.5 then
        CycleGlobalSystemMode()
        SystemModeActive = true
    elsif SYSMODE_SELECT_CCIdx == cc then
        SelectGlobalSystemMode(Round(val * 4.0))  // val 0.0-1.0 maps to mode 0-4
```

- [ ] **Step 3: Add macro label display in CtrlInfo builder**

Near lines 2879-2881 (where VST_SCOPE CtrlInfo line is built), add:
```gpscript
           elsif (not isCC and s == SYSMODE_CYCLE_MacroIdx) or (isCC and s == SYSMODE_CYCLE_CCIdx) then
               CtrlInfo_Lines <-- hwStr + ": >> SYS-MODE Cycle"
           elsif (not isCC and s == SYSMODE_SELECT_MacroIdx) or (isCC and s == SYSMODE_SELECT_CCIdx) then
               CtrlInfo_Lines <-- hwStr + ": >> SYS-MODE Select (0-4)"
```

- [ ] **Step 4: Register macros in the macro name parser**

Find where `VST_SCOPE` is parsed from the controller map (search for `"VST_SCOPE"` string comparison). Add near that block:
```gpscript
    elsif IndexOfSubstring(macroName, "SYSMODE_CYCLE", false) >= 0 then
        SYSMODE_CYCLE_MacroIdx = macroIdx; SYSMODE_CYCLE_CCIdx = ccIdx
    elsif IndexOfSubstring(macroName, "SYSMODE_SELECT", false) >= 0 then
        SYSMODE_SELECT_MacroIdx = macroIdx; SYSMODE_SELECT_CCIdx = ccIdx
```

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): add SYSMODE_CYCLE and SYSMODE_SELECT macros"
```

---

### Task 4: ms-Based RecordTimelineEvent

**Files:**
- Modify: `Global Rackspace V26.gpscript:5299-5333` (RecordTimelineEvent)

- [ ] **Step 1: Rewrite RecordTimelineEvent for ms-based recording**

Replace lines 5299-5333:
```gpscript
Function RecordTimelineEvent(eventType : String, eventVal : Integer)
    var eventTimeMS : Double

    // GUARD: Only record when Timeline REC is active
    if not TimelineRecActive then
        Trace("TIMELINE-REC: Ignored (not active)")
        Exit
    end

    eventTimeMS = TimeSinceStartup() - RecordStartTimeMS

    // Write to working arrays
    Arr_Rec_TimeMS <-- eventTimeMS
    Arr_Rec_Type <-- eventType
    Arr_Rec_Val <-- eventVal
    
    Trace("TIMELINE-REC: " + eventType + " val=" + eventVal + " at " + Round(eventTimeMS) + "ms")
    
    BuildRecDisplayLines()
    RefreshRecDisplay(GetWidgetValue(SLD_CurrentState))
End
```

- [ ] **Step 2: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): rewrite RecordTimelineEvent for ms-based recording"
```

---

### Task 5: Timeline Count-In & Recording Start

**Files:**
- Modify: `Global Rackspace V26.gpscript:13578-13627` (count-in expiry monitor in TimerTick)

- [ ] **Step 1: Add StartTimelineRecording function**

Add near the other Timeline functions:
```gpscript
Function StartTimelineRecording()
    // Start count-in
    TimelineCountInTimer = TimeSinceStartup() + GetCountInDurationMS()
    TimelineRecActive = false  // Not yet — wait for count-in to expire
    TimelineCurrentPartIdx = 1 // First manual marker = part 1 (Intro is implicit at t=0)
    PreviewPartIdx = 0
    
    // Clear working arrays
    Arr_Rec_TimeMS = []; Arr_Rec_Type = []; Arr_Rec_Val = []
    
    Trace("TIMELINE: Count-in started, expires in " + Round(GetCountInDurationMS()) + "ms")
    OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> TIMELINE: Count-In... <<<", Local_IP, Local_PORT)
    MacroFeedbackTimer = TimeSinceStartup() + GetCountInDurationMS() + 500.0
End
```

- [ ] **Step 2: Add Timeline count-in expiry check in TimerTick**

After line 13627 (end of Looper count-in monitor), add:
```gpscript
        // --- TIMELINE COUNT-IN MONITOR ---
        if TimelineCountInTimer > 0.0 and not TimelineRecActive then
            if TimeSinceStartup() >= TimelineCountInTimer then
                TimelineCountInTimer = 0.0
                TimelineRecActive = true
                RecordStartTimeMS = TimeSinceStartup()
                
                Trace("TIMELINE: Count-in expired. Recording started at " + Round(RecordStartTimeMS) + "ms")
                OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> TIMELINE: REC <<<", Local_IP, Local_PORT)
                MacroFeedbackTimer = TimeSinceStartup() + 2000.0
            end
        end
```

- [ ] **Step 3: Add Timeline count-in to the LED blink engine**

In the global blink engine (around lines 13518-13549), where `maxCountInBeats` is calculated from `LoopFreeArmTimer`, add after the looper loop:
```gpscript
        // Timeline count-in contributes to the same LED display
        if TimelineCountInTimer > 0.0 and not TimelineRecActive then
            msLeft_blink = TimelineCountInTimer - TimeSinceStartup()
            if msLeft_blink > 0.0 then
                remB = Round((msLeft_blink + (msPerBeat / 2.0)) / msPerBeat)
                if remB > maxCountInBeats then maxCountInBeats = remB end
            end
        end
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): add count-in mechanism and recording start"
```

---

### Task 6: ProcessSystemNavigation Mode 4

**Files:**
- Modify: `Global Rackspace V26.gpscript:9666-9681` (after Mode 3 block)

- [ ] **Step 1: Add CommitTimelineRecording helper**

Add near other Timeline functions:
```gpscript
Function CommitTimelineRecording()
    var i : Integer
    
    // Copy Working → Committed
    Snap_TL_TimeMS = []; Snap_TL_Type = []; Snap_TL_Val = []
    for i = 0; i < Size(Arr_Rec_TimeMS); i = i + 1 do
        Snap_TL_TimeMS <-- Arr_Rec_TimeMS[i]
        Snap_TL_Type <-- Arr_Rec_Type[i]
        Snap_TL_Val <-- Arr_Rec_Val[i]
    end
    Snap_TL_Fired = []
    
    TimelineRecActive = false
    TimelineCountInTimer = 0.0
    Trace("TIMELINE: Recording committed. " + Size(Snap_TL_TimeMS) + " events.")
End
```

- [ ] **Step 2: Add DiscardTimelineRecording helper**

```gpscript
Function DiscardTimelineRecording()
    Arr_Rec_TimeMS = []; Arr_Rec_Type = []; Arr_Rec_Val = []
    TimelineRecActive = false
    TimelineCountInTimer = 0.0
    
    Trace("TIMELINE: Recording discarded.")
    OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> RECORDING DISCARDED <<<", Local_IP, Local_PORT)
    MacroFeedbackTimer = TimeSinceStartup() + 2000.0
End
```

- [ ] **Step 3: Add ExecuteRecSongpart helper**

```gpscript
Function ExecuteRecSongpart()
    var partName : String
    
    if not TimelineRecActive then
        Trace("TIMELINE: REC_SONGPART ignored (not recording)")
        Exit
    end
    
    // No parts loaded — single-marker recording (marks song end)
    if Size(Arr_SectionNames) == 0 then
        RecordEndTimeMS = TimeSinceStartup() - RecordStartTimeMS
        RecordTimelineEvent("Marker", 0)  // END marker
        CommitTimelineRecording()
        TimelineSubMode = 0  // Auto-switch to PLAY
        OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> SONG RECORDED <<<", Local_IP, Local_PORT)
        MacroFeedbackTimer = TimeSinceStartup() + 2000.0
        Exit
    end
    
    // Last part already recorded — this press = END OF SONG
    if TimelineCurrentPartIdx >= Size(Arr_SectionNames) then
        RecordEndTimeMS = TimeSinceStartup() - RecordStartTimeMS
        RecordTimelineEvent("Marker", TimelineCurrentPartIdx)  // END marker
        CommitTimelineRecording()
        TimelineSubMode = 0  // Auto-switch to PLAY
        OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> SONG RECORDED <<<", Local_IP, Local_PORT)
        MacroFeedbackTimer = TimeSinceStartup() + 2000.0
        Trace("TIMELINE: END OF SONG at " + Round(RecordEndTimeMS) + "ms")
        Exit
    end
    
    // Normal part marker
    partName = Arr_SectionNames[TimelineCurrentPartIdx]
    RecordTimelineEvent("Marker", TimelineCurrentPartIdx)
    
    OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> PART: " + partName + " <<<", Local_IP, Local_PORT)
    MacroFeedbackTimer = TimeSinceStartup() + 2000.0
    
    TimelineCurrentPartIdx = TimelineCurrentPartIdx + 1
    Trace("TIMELINE: Recorded part " + partName + ", next idx=" + TimelineCurrentPartIdx)
End
```

- [ ] **Step 4: Add PartJumpPreview helper**

```gpscript
Function PartJumpPreview(dir : Integer)
    var partName : String
    
    if Size(Arr_SectionNames) == 0 then
        OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> NO PARTS LOADED <<<", Local_IP, Local_PORT)
        MacroFeedbackTimer = TimeSinceStartup() + 2000.0
        Exit
    end
    
    PreviewPartIdx = PreviewPartIdx + dir
    if PreviewPartIdx < 0 then PreviewPartIdx = 0 end
    if PreviewPartIdx >= Size(Arr_SectionNames) then PreviewPartIdx = Size(Arr_SectionNames) - 1 end
    
    partName = Arr_SectionNames[PreviewPartIdx]
    
    // Update OSC-UI with song text for the previewed part
    OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> " + partName + " <<<", Local_IP, Local_PORT)
    MacroFeedbackTimer = TimeSinceStartup() + 2000.0
    
    Trace("TIMELINE: Preview part " + PreviewPartIdx + " = " + partName)
End
```

- [ ] **Step 5: Add Mode 4 case to ProcessSystemNavigation**

After line 9679 (`end` closing Mode 3 block), before the final `end` at line 9680, add:
```gpscript
    // --- 4: TIMELINE (PLAY/REC with sub-mode) ---
    elsif GlobalSystemMode == 4 then
        if actionType == "Y_AXIS" or actionType == "BUTTON" then
            // Toggle PLAY <-> REC
            if TimelineSubMode == 0 then
                // PLAY -> REC
                TimelineSubMode = 1
                TimelineRecState = 0  // Default to Replace
                StartTimelineRecording()
                OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> TIMELINE: REC (Replace) <<<", Local_IP, Local_PORT)
            else
                // REC -> PLAY (commit recording)
                if TimelineRecActive then CommitTimelineRecording() end
                TimelineSubMode = 0
                OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> TIMELINE: PLAY <<<", Local_IP, Local_PORT)
            end
            MacroFeedbackTimer = TimeSinceStartup() + 2000.0
            
        elsif actionType == "X_AXIS" or actionType == "ENCODER" then
            if TimelineSubMode == 0 then
                // PLAY: Part Jump Preview
                PartJumpPreview(dir)
            else
                // REC mode
                if dir == 1 then
                    // Right: Execute REC_SONGPART
                    ExecuteRecSongpart()
                elsif dir == -1 then
                    // Left: Cycle Replace -> Overdub -> Discard
                    TimelineRecState = TimelineRecState + 1
                    if TimelineRecState > 2 then TimelineRecState = 0 end
                    
                    if TimelineRecState == 0 then
                        OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> REC: Replace <<<", Local_IP, Local_PORT)
                    elsif TimelineRecState == 1 then
                        OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> REC: Overdub <<<", Local_IP, Local_PORT)
                    elsif TimelineRecState == 2 then
                        DiscardTimelineRecording()
                    end
                    MacroFeedbackTimer = TimeSinceStartup() + 2000.0
                end
            end
        end
```

- [ ] **Step 6: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): add Mode 4 to ProcessSystemNavigation with PLAY/REC sub-modes"
```

---

### Task 7: ms-Based Playback

**Files:**
- Modify: `Global Rackspace V26.gpscript:13784-13808` (timeline playback in TimerTick)
- Modify: `Global Rackspace V26.gpscript:13207-13209` (BeatChanged Arr_TL_Fired reset)

- [ ] **Step 1: Add FireTimelineEvent helper**

Add near other Timeline functions:
```gpscript
Function FireTimelineEvent(eventType : String, eventVal : Integer)
    if eventType == "Macro" then
        SetParameter(ExternalArranger, eventVal, 1.0)
    elsif eventType == "Map" then
        if eventVal >= 0 and eventVal < Size(CtrlMapList) then
            Trace("TIMELINE: Auto-Switching Map to -> " + CtrlMapList[eventVal])
            LoadControllerMap(CtrlMapList[eventVal])
            HardwareSyncTimer = TimeSinceStartup() + 400.0
            OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> TL-MAP: " + CtrlMapList[eventVal] + " <<<", Local_IP, Local_PORT)
            MacroFeedbackTimer = TimeSinceStartup() + 2000.0
        end
    elsif eventType == "Style" then
        TriggerStyleAction(eventVal)
    elsif eventType == "Marker" then
        // Update song part display
        if eventVal >= 0 and eventVal < Size(Arr_SectionNames) then
            PreviewPartIdx = eventVal
            Trace("TIMELINE: Part -> " + Arr_SectionNames[eventVal])
        end
    end
End
```

- [ ] **Step 2: Add StartTimelinePlayback function**

```gpscript
Function StartTimelinePlayback()
    var i : Integer
    
    if Size(Snap_TL_TimeMS) == 0 then
        Trace("TIMELINE: No events to play back.")
        Exit
    end
    
    PlaybackStartTimeMS = TimeSinceStartup()
    TimelinePlaybackActive = true
    PreviewPartIdx = 0
    
    // Reset fired flags
    Snap_TL_Fired = []
    for i = 0; i < Size(Snap_TL_TimeMS); i = i + 1 do
        Snap_TL_Fired <-- false
    end
    
    Trace("TIMELINE: Playback started at " + Round(PlaybackStartTimeMS) + "ms, " + Size(Snap_TL_TimeMS) + " events.")
End
```

- [ ] **Step 3: Replace bar-based playback with ms-based in TimerTick**

Replace lines 13784-13808 with:
```gpscript
        // --- TIMELINE PLAYBACK (ms-based) ---
        if TimelinePlaybackActive and not TimelineRecActive then
            msSinceSongStart = TimeSinceStartup() - PlaybackStartTimeMS
            for tl_idx = 0; tl_idx < Size(Snap_TL_TimeMS); tl_idx = tl_idx + 1 do
                if Snap_TL_TimeMS[tl_idx] <= msSinceSongStart and Snap_TL_Fired[tl_idx] == false then
                    FireTimelineEvent(Snap_TL_Type[tl_idx], Snap_TL_Val[tl_idx])
                    Snap_TL_Fired[tl_idx] = true
                end
            end
            
            // Stop playback after last event + 1 second buffer
            if Size(Snap_TL_TimeMS) > 0 then
                if msSinceSongStart > Snap_TL_TimeMS[Size(Snap_TL_TimeMS) - 1] + 1000.0 then
                    TimelinePlaybackActive = false
                    Trace("TIMELINE: Playback finished.")
                end
            end
        end
```

**Note:** Declare `msSinceSongStart` as a local variable in the TimerTick scope (Double type) if not already present. Also declare `tl_idx` if needed.

- [ ] **Step 4: Remove bar-based Arr_TL_Fired reset from BeatChanged**

At lines 13207-13209, remove or comment out:
```gpscript
    // --- TIMELINE TRIGGER RESET --- (REMOVED: now ms-based, reset at playback start)
    // for e = 0; e < Size(Arr_TL_Bar); e = e + 1 do
    //      if Arr_TL_Bar[e] == CurrentBar then Arr_TL_Fired[e] = false end
    // end
```

- [ ] **Step 5: Add playback start triggers**

In the NoteOn event handler, add NoteOn-detection trigger for Timeline playback:
```gpscript
    // Timeline NoteOn-detection playback start
    if not TimelinePlaybackActive and not TimelineRecActive and Size(Snap_TL_TimeMS) > 0 then
        if GetWidgetValue(BTN_TL_HostSync) > 0.5 and not IsPlayheadEnabled() then
            StartTimelinePlayback()
        end
    end
```

In the transport start handler (where `IsPerformanceActive` becomes true), add:
```gpscript
    // Timeline auto-start on transport
    if not TimelinePlaybackActive and not TimelineRecActive and Size(Snap_TL_TimeMS) > 0 then
        StartTimelinePlayback()
    end
```

- [ ] **Step 6: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): replace bar-based playback with ms-based system"
```

---

### Task 8: Song.ini Persistence (Load & Save)

**Files:**
- Modify: `Global Rackspace V26.gpscript:10474-10545` (LoadSongTimeline)
- Modify: `Global Rackspace V26.gpscript:10446-10449` (SaveConfig timeline writer)

- [ ] **Step 1: Rewrite LoadSongTimeline for ms-based format**

Replace lines 10474-10545 with:
```gpscript
Function LoadSongTimeline(songFilePath : String)
    var iniPath : String
    var lines, parts, kvParts : String Array
    var line, valStr, eType, key : String
    var i, eVal : Integer
    var eTimeMS : Double
    var inSection : Boolean = false
    
    // Clean out arrays
    Snap_TL_TimeMS = []; Snap_TL_Type = []; Snap_TL_Val = []; Snap_TL_Fired = []
    Arr_Rec_TimeMS = []; Arr_Rec_Type = []; Arr_Rec_Val = []
    RecordEndTimeMS = 0.0
    TimelinePlaybackActive = false
    TimelineRecActive = false
    PreviewPartIdx = 0
    TimelineCurrentPartIdx = 1
    
    iniPath = ReplaceString(songFilePath, ".gpchord", ".ini", false)
    
    if FileExists(iniPath) then
        lines = SplitString(LoadStringFromTextFile(iniPath), NEW_LINE)
        
        for i = 0; i < Size(lines); i = i + 1 do
            line = TrimString(lines[i])
            
            if IndexOfSubstring(line, "[Timeline]", false) == 0 then
                inSection = true
            elsif IndexOfSubstring(line, "[", false) == 0 and line != "[Timeline]" then
                inSection = false
            elsif inSection and IndexOfSubstring(line, "=", false) > 0 then
                
                kvParts = SplitString(line, "=")
                key = TrimString(kvParts[0])
                valStr = TrimString(kvParts[1])
                
                // Parse metadata keys
                if key == "TotalDurationMS" then
                    RecordEndTimeMS = StringToDouble(valStr)
                    
                // Parse event lines: Event_N=<ms>, <Type>, <Value>
                elsif IndexOfSubstring(key, "Event_", false) == 0 then
                    parts = SplitString(valStr, ",")
                    
                    if Size(parts) >= 3 then
                        eTimeMS = StringToDouble(TrimString(parts[0]))
                        eType = TrimString(parts[1])
                        eVal = StringToInt(TrimString(parts[2]))
                        
                        Snap_TL_TimeMS <-- eTimeMS
                        Snap_TL_Type <-- eType
                        Snap_TL_Val <-- eVal
                        Snap_TL_Fired <-- false
                        
                        // Sync bar triggers for Marker events (if bars are calculable)
                        if eType == "Marker" and RecordEndTimeMS > 0.0 then
                            if eVal >= 0 and eVal < Size(Arr_BarTriggers) then
                                Arr_BarTriggers[eVal] = CalculateBarFromMS(eTimeMS)
                            end
                        end
                    end
                end
            end
        end
        Trace("PROMPTER: Timeline loaded. " + Size(Snap_TL_TimeMS) + " events found.")
    else
        Trace("PROMPTER: No INI file found. Timeline is empty.")
    end
    BuildRecDisplayLines()
    RefreshRecDisplay(1.0)
End
```

- [ ] **Step 2: Add CalculateBarFromMS helper**

```gpscript
Function CalculateBarFromMS(timeMS : Double) Returns Integer
    var msPerBar : Double
    var bpm : Double = GetBPM()
    var timeSig : Integer = GetTimeSigNumerator()
    
    if bpm < 1.0 then bpm = 120.0 end
    if timeSig <= 0 then timeSig = 4 end
    
    msPerBar = (60000.0 / bpm) * IntToFloat(timeSig)
    
    if msPerBar <= 0.0 then result = 1
    else result = Round(timeMS / msPerBar) + 1
    end
End
```

- [ ] **Step 3: Rewrite SaveConfig timeline writer**

Replace lines 10446-10449 with:
```gpscript
       // 6. APPEND TIMELINE
       content = content + NEW_LINE + "[Timeline]" + NEW_LINE
       if GetBPM() > 0.0 then
           content = content + "StartBPM=" + GetBPM() + NEW_LINE
       end
       content = content + "TimeSignature=" + GetTimeSigNumerator() + NEW_LINE
       if RecordEndTimeMS > 0.0 then
           content = content + "TotalDurationMS=" + Round(RecordEndTimeMS) + NEW_LINE
       end
       for i = 0; i < Size(Snap_TL_TimeMS); i = i + 1 do
           content = content + "Event_" + (i+1) + "=" + Round(Snap_TL_TimeMS[i]) + ", " + Snap_TL_Type[i] + ", " + Snap_TL_Val[i] + NEW_LINE
       end
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(timeline): rewrite Song.ini persistence for ms-based format"
```

---

### Task 9: Verification & Cleanup

**Files:**
- Modify: `Global Rackspace V26.gpscript` (various cleanup)

- [ ] **Step 1: Search for remaining references to old bar-based arrays**

Search for all uses of `Arr_TL_Bar`, `Arr_TL_Offset`, `Arr_Rec_Bar`, `Arr_Rec_Offset` and verify they are either:
- Removed (if only used by the old playback/recording path)
- Updated to use the new ms-based arrays
- Kept as secondary storage for bar calculation display

Key locations to check:
- `BuildRecDisplayLines()` — may reference `Arr_Rec_Bar`/`Arr_Rec_Offset`. Update to show `Arr_Rec_TimeMS` instead.
- `RefreshRecDisplay()` — same check
- Any sorting logic (old bubble sort at lines ~10062-10074) — update or remove if no longer needed

- [ ] **Step 2: Update BuildRecDisplayLines for ms-based display**

Find `BuildRecDisplayLines` and update it to display ms values from `Arr_Rec_TimeMS` instead of bar/offset values. Format example: `"45200ms Marker: Verse 1"` instead of `"Bar 23 + 200ms: Marker 1"`.

- [ ] **Step 3: Verify CycleGlobalSystemMode cycles through 5 modes**

Confirm the function now has `if GlobalSystemMode > 4 then GlobalSystemMode = 0 end` (changed in Task 2).

- [ ] **Step 4: Verify all OSC feedback strings are consistent**

Grep for `">>> TIMELINE"` and `">>> REC"` and `">>> PLAY"` to ensure consistent formatting with the existing pattern `">>> LABEL <<<"`

- [ ] **Step 5: Commit final cleanup**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "fix(timeline): update display functions and clean up old bar-based references"
```

---

### Task 10: Push & Final Verification

- [ ] **Step 1: Verify README.md is up to date**

README was already updated in the spec commit. Verify it shows 5 SYS-MODEs and the updated roadmap (Timeline removed from roadmap, described in features).

- [ ] **Step 2: Verify example .ini files**

Confirm `examples/SlowHip80erDream.ini` and `examples/VSTPlayMode.ini` have the new `[Timeline]` format with `StartBPM` and `TimeSignature` keys (already updated in spec commit).

- [ ] **Step 3: Review full diff**

```bash
git log --oneline -10
git diff HEAD~9..HEAD --stat
```

Verify all changes are accounted for and no unintended modifications were made.

- [ ] **Step 4: Push to remote**

Only if user requests it:
```bash
git push
```
