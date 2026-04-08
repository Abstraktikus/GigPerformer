# STRIP-CONTROL Solo/Mute Fix + Live Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix non-functional Solo/Mute toggles in STRIP-CONTROL mode and add automatic restore of live changes when timeline playback finishes.

**Architecture:** 3-layer approach — Configured (widgets/controller map), Live (RAM + NP via STRIP), Restore (reload controller map on playback end). ToggleStripMacro gets mutual exclusion logic and UpdateSoloMuteState() calls. A dirty flag tracks live changes for HUD indication and restore trigger.

**Tech Stack:** GPScript (Gig Performer scripting language)

**Key Reference:** GPScript has no early return — use if/else blocks. Always initialize Double vars with `= 0.0`.

---

### Task 1: Add StripLiveDirty flag variable

**Files:**
- Modify: `Global Rackspace.gpscript:362-363` (Strip variable declarations)

- [ ] **Step 1: Add the dirty flag after existing Strip variables**

At line 363, after `Strip_ChannelIdx`, add the new variable:

```gpscript
   Strip_ChannelIdx : Integer = 0   // Current channel (0-15)
   StripLiveDirty   : Boolean = false // True when STRIP made live changes not reflected in widgets
```

- [ ] **Step 2: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(strip): add StripLiveDirty flag for tracking live changes"
```

---

### Task 2: Fix ToggleStripMacro — Solo mutual exclusion + UpdateSoloMuteState

**Files:**
- Modify: `Global Rackspace.gpscript:9779-9857` (ToggleStripMacro function)

The current code for themes 3 (Smart Solo) and 4 (Strict Solo) only sets RAM arrays but:
1. Does NOT call `UpdateSoloMuteState()` — so the RECH matrix is never updated (no audible effect)
2. Does NOT clear the opposing solo type — both can be active simultaneously (inconsistent with widget handler logic at lines 12439-12461)
3. Does NOT set `StripLiveDirty`

- [ ] **Step 1: Fix Theme 3 (Smart Solo) — add mutual exclusion**

Replace the Theme 3 block (lines 9788-9792):

```gpscript
      Strip_ThemeIdx == 3  Do // Smart Solo
         currentVal = Mem_SoloSmart[ch]
         newVal = 1 - currentVal
         Mem_SoloSmart[ch] = newVal
         if newVal == 1 then Mem_SoloStrict[ch] = 0 end // Mutual exclusion
         paramName = "Smart Solo"
```

- [ ] **Step 2: Fix Theme 4 (Strict Solo) — add mutual exclusion**

Replace the Theme 4 block (lines 9794-9798):

```gpscript
      Strip_ThemeIdx == 4  Do // Strict Solo
         currentVal = Mem_SoloStrict[ch]
         newVal = 1 - currentVal
         Mem_SoloStrict[ch] = newVal
         if newVal == 1 then Mem_SoloSmart[ch] = 0 end // Mutual exclusion
         paramName = "Strict Solo"
```

- [ ] **Step 3: Add UpdateSoloMuteState() and StripLiveDirty to the tail block**

Replace the tail block (lines 9849-9856) — the `if paramName != ""` section:

```gpscript
   if paramName != "" then
      if newVal > 0 then statusStr = "ON" else statusStr = "OFF" end
      OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> Ch " + IntToString(ch + 1) + " | " + paramName + " [" + statusStr + "] <<<", Local_IP, Local_PORT)
      MacroFeedbackTimer = TimeSinceStartup() + 2000.0
      MacroFeedbackLockTimer = TimeSinceStartup() + 2000.0
      Trace("STRIP TOGGLE: Ch " + IntToString(ch + 1) + " | " + paramName + " = " + statusStr)
      StripLiveDirty = true
      UpdateSoloMuteState()
      UpdateMetaColors()
   end
```

Note: `UpdateSoloMuteState()` is called BEFORE `UpdateMetaColors()` because it updates the RECH matrix which MetaColors may depend on. This call is essential for themes 3, 4, and 5 (Solo/Mute) to have any audible effect. For themes 6-11 (NP parameters), the `SetParameter` calls handle the audio side directly, but `UpdateSoloMuteState()` is still safe to call (it recalculates from current RAM state).

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "fix(strip): add mutual exclusion and UpdateSoloMuteState to ToggleStripMacro

Solo/Mute toggles in STRIP-CONTROL mode were non-functional because
UpdateSoloMuteState() was never called (RECH matrix not updated).
Also adds Smart<->Strict mutual exclusion matching widget handler behavior."
```

---

### Task 3: Restore live changes when timeline playback finishes

**Files:**
- Modify: `Global Rackspace.gpscript:14129-14134` (timeline playback stop in timer callback)

When `TimelinePlaybackActive` is set to false after the last event fires, we reload the current controller map to restore the "configured" state. This undoes any STRIP live tweaks.

- [ ] **Step 1: Add restore call at playback finish**

Replace the playback-finish block (lines 14129-14134):

```gpscript
            // Stop playback after last event + 1 second buffer
            if Size(Snap_TL_TimeMS) > 0 then
                if msSinceSongStart > Snap_TL_TimeMS[Size(Snap_TL_TimeMS) - 1] + 1000.0 then
                    TimelinePlaybackActive = false
                    Trace("TIMELINE: Playback finished.")
                    // Restore configured state if STRIP made live changes
                    if StripLiveDirty then
                        LoadControllerMap(CurrentCtrlMapName)
                        StripLiveDirty = false
                        Trace("STRIP: Live changes restored via controller map reload.")
                        OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> STRIP RESTORED <<<", Local_IP, Local_PORT)
                        MacroFeedbackTimer = TimeSinceStartup() + 2000.0
                    end
                end
            end
```

- [ ] **Step 2: Also reset StripLiveDirty on song change**

In the `On Song` callback (line 13181), the system resets record modes early (lines 13197-13199). Add the flag reset right after:

```gpscript
   SetWidgetValue(BTN_Record_Overdub, 0.0)
   SetWidgetValue(BTN_Record_Replace, 0.0)
   RecordMode = 0
   StripLiveDirty = false
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(strip): restore configured state when timeline playback finishes

Reloads current controller map after playback ends if STRIP-CONTROL
made live changes. Also clears dirty flag on song change."
```

---

### Task 4: Verify and manual test

- [ ] **Step 1: Verify code consistency**

Search for all references to ensure no typos or missed connections:
- `StripLiveDirty` should appear in: variable declaration, ToggleStripMacro tail, playback finish, song change
- `UpdateSoloMuteState()` should now appear inside ToggleStripMacro's tail block
- Mutual exclusion lines should be in themes 3 and 4

- [ ] **Step 2: Manual test checklist**

In Gig Performer:
1. Enter STRIP-CONTROL mode (SYS-MODE 3)
2. Navigate to a channel with an active VST
3. Select Smart Solo theme (Theme 3), toggle X-Right → should hear solo effect
4. Switch to Strict Solo theme (Theme 4), toggle X-Right → Smart Solo should auto-clear
5. Start timeline playback → let it finish → verify HUD shows "STRIP RESTORED" and solo state returns to configured baseline
6. Switch songs → verify no stale strip state carries over
