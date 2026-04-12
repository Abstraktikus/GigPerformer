# Plan B: Runtime Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the layer state machine, SysEx incoming handler, layer-aware macro dispatch, overlay trigger engine with range-based and movement-toggle (10s debounce) triggers.

**Architecture:** Layer switches (configured in DeviceConfig) toggle binary states. A bitmask lookup determines the active layer. `ExecuteHardwareMacro` is extended to check the active layer before firing bindings. Overlay functions route through a unified `ActivateOverlay`/`DeactivateOverlay` dispatcher. The 10-second debounce for full-range movement triggers runs in `On TimerTick`.

**Tech Stack:** GPScript 5.x, Global Rackspace script

**Depends on:** Plan A (data structures and parser must be in place)

---

### Task 1: Layer State Machine — UpdateActiveLayer()

**Location:** SECTION 14 (HAL Runtime, ~line 1443)

- [ ] **Step 1: Write UpdateActiveLayer()**

```gpscript
// Computes active layer from switch states via LAYERMAP bitmask
Function UpdateActiveLayer()
   var oldLayer, bits, sw : Integer
   oldLayer = ActiveLayer

   // Compute bitmask from switch states
   bits = 0
   For sw = 0; sw < LayerSwitch_Count; sw = sw + 1
      if LayerSwitch_State[sw] == 1 then
         bits = bits + Power(2, sw)
      end
   End

   // Lookup in LAYERMAP
   if bits < 16 then
      ActiveLayer = LayerMap_LayerIdx[bits]
   else
      ActiveLayer = 0
   end

   // Fire OVERLAY actions on layer change
   if ActiveLayer <> oldLayer then
      if DebugMode then
         Trace("LAYER: " + IntToString(oldLayer) + " -> " + IntToString(ActiveLayer))
      end
      var ov : Integer
      For ov = 0; ov < Overlay_Count; ov = ov + 1
         if Overlay_Layer[ov] == ActiveLayer then
            FireOverlayAction(Overlay_Action[ov])
         end
      End
      // Deactivate overlay actions from the old layer
      For ov = 0; ov < Overlay_Count; ov = ov + 1
         if Overlay_Layer[ov] == oldLayer and Overlay_Layer[ov] <> ActiveLayer then
            DeactivateOverlayAction(Overlay_Action[ov])
         end
      End
   end
End
```

- [ ] **Step 2: Write FireOverlayAction() and DeactivateOverlayAction()**

```gpscript
// Fires a layer-level overlay action (from DeviceConfig OVERLAY section)
Function FireOverlayAction(action : String)
   if action == "SYSTEM_TOGGLE_ON" then
      SystemModeActive = true
      if DebugMode then
         Trace("OVERLAY: SYSTEM_TOGGLE_ON activated")
      end
   end
End

Function DeactivateOverlayAction(action : String)
   if action == "SYSTEM_TOGGLE_ON" then
      SystemModeActive = false
      if DebugMode then
         Trace("OVERLAY: SYSTEM_TOGGLE_ON deactivated")
      end
   end
End
```

- [ ] **Step 3: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(layer): layer state machine with bitmask lookup and overlay actions"
```

---

### Task 2: SysEx Incoming Handler for Layer Switches

**Location:** Extend existing `On SysexEvent` at ~line 15993

- [ ] **Step 1: Add layer switch matching to On SysexEvent**

Inside the existing `On SysexEvent(m : SysexMessage) From DeviceIn_0` handler, after the Yamaha heartbeat check (~line 16006), add layer switch matching:

```gpscript
      // --- LAYER SWITCH MATCHING ---
      var incomingHexFull : String; var byteIdx : Integer
      incomingHexFull = ""
      For byteIdx = 0; byteIdx < msgSize; byteIdx = byteIdx + 1
         if byteIdx > 0 then
            incomingHexFull = incomingHexFull + " "
         end
         incomingHexFull = incomingHexFull + IntToHexString(SM_GetValue(m, byteIdx))
      End
      // Uppercase for comparison
      incomingHexFull = Upper(incomingHexFull)

      var swIdx : Integer
      For swIdx = 0; swIdx < LayerSwitch_Count; swIdx = swIdx + 1
         if LayerSwitch_DevIdx[swIdx] == 0 then  // DeviceIn_0 = Device 0
            if LayerSwitch_Type[swIdx] == "SYSEX" then
               if incomingHexFull == Upper(LayerSwitch_OnData[swIdx]) then
                  LayerSwitch_State[swIdx] = 1
                  UpdateActiveLayer()
                  if DebugMode then
                     Trace("LAYERSWITCH " + IntToString(swIdx) + " (" + LayerSwitch_Label[swIdx] + "): ON")
                  end
               elsif incomingHexFull == Upper(LayerSwitch_OffData[swIdx]) then
                  LayerSwitch_State[swIdx] = 0
                  UpdateActiveLayer()
                  if DebugMode then
                     Trace("LAYERSWITCH " + IntToString(swIdx) + " (" + LayerSwitch_Label[swIdx] + "): OFF")
                  end
               end
            end
         end
      End
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(sysex): incoming SysEx matching for layer switch triggers"
```

---

### Task 3: Overlay Trigger Engine — ActivateOverlay / DeactivateOverlay

**Location:** SECTION 21 (Orchestration, ~line 8918), place before UpdateSoloMuteState()

- [ ] **Step 1: Write ActivateOverlay() and DeactivateOverlay()**

```gpscript
// Unified overlay function dispatcher — same actions as Strip Control UI
Function ActivateOverlay(funcName : String, channel : Integer)
   if funcName == "SMART_SOLO" then
      Mem_SoloSmart[channel] = 1
      Mem_SoloStrict[channel] = 0  // mutual exclusion
      UpdateSoloMuteState()
   elsif funcName == "STRICT_SOLO" then
      Mem_SoloStrict[channel] = 1
      Mem_SoloSmart[channel] = 0  // mutual exclusion
      UpdateSoloMuteState()
   elsif funcName == "USER_MUTE" then
      Mem_UserMute[channel] = 1
      UpdateSoloMuteState()
   elsif funcName == "ROOT" then
      Mem_NP_ChordMode[channel] = 1
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_ChordMode"), 1.0)
   elsif funcName == "OCTAVER" then
      Mem_NP_OctaverMode[channel] = 1
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_OctaverMode"), 1.0)
   elsif funcName == "HUMANIZE" then
      Mem_NP_HumanizerMode[channel] = 1
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_HumanizerMode"), 1.0)
   elsif funcName == "SCALE" then
      Mem_NP_ScaleMode[channel] = 1
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_ScaleMode"), 1.0)
   elsif funcName == "RANGE" then
      Mem_NP_VelRangeActive[channel] = 1
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_VelRangeActive"), 1.0)
   elsif funcName == "AUTO_SUSTAIN" then
      Mem_NP_AutoSustain[channel] = 1
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_AutoSustain"), 1.0)
   end
   // Record to timeline
   RecordTimelineOverlay(funcName, channel, 1)
   if DebugMode then
      Trace("OVERLAY ON: " + funcName + " CH" + IntToString(channel))
   end
End

Function DeactivateOverlay(funcName : String, channel : Integer)
   if funcName == "SMART_SOLO" then
      Mem_SoloSmart[channel] = 0
      UpdateSoloMuteState()
   elsif funcName == "STRICT_SOLO" then
      Mem_SoloStrict[channel] = 0
      UpdateSoloMuteState()
   elsif funcName == "USER_MUTE" then
      Mem_UserMute[channel] = 0
      UpdateSoloMuteState()
   elsif funcName == "ROOT" then
      Mem_NP_ChordMode[channel] = 0
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_ChordMode"), 0.0)
   elsif funcName == "OCTAVER" then
      Mem_NP_OctaverMode[channel] = 0
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_OctaverMode"), 0.0)
   elsif funcName == "HUMANIZE" then
      Mem_NP_HumanizerMode[channel] = 0
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_HumanizerMode"), 0.0)
   elsif funcName == "SCALE" then
      Mem_NP_ScaleMode[channel] = 0
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_ScaleMode"), 0.0)
   elsif funcName == "RANGE" then
      Mem_NP_VelRangeActive[channel] = 0
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_VelRangeActive"), 0.0)
   elsif funcName == "AUTO_SUSTAIN" then
      Mem_NP_AutoSustain[channel] = 0
      SetParameter(BLK_NoteProcessor[channel], GetParamIdxByName(BLK_NoteProcessor[channel], "p_AutoSustain"), 0.0)
   end
   RecordTimelineOverlay(funcName, channel, 0)
   if DebugMode then
      Trace("OVERLAY OFF: " + funcName + " CH" + IntToString(channel))
   end
End

// Stub for timeline recording — implemented in Plan C
Function RecordTimelineOverlay(funcName : String, channel : Integer, state : Integer)
   // Plan C will implement: RecordTimelineEvent("OVERLAY", funcName + ":" + IntToString(channel) + ":" + IntToString(state))
End
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(overlay): unified ActivateOverlay/DeactivateOverlay dispatcher"
```

---

### Task 4: Range-Based Trigger Logic + Debounce

**Location:** SECTION 22 (Hardware Input Processing, ~line 10883)

- [ ] **Step 1: Add debounce state arrays to SECTION 8 variables**

```gpscript
   // Debounce state for full-range movement-toggle overlays
   Debounce_Active : Boolean Array     // [MAX_OVERLAY_BINDINGS] true = within 10s lockout
   Debounce_Timer : Double Array       // [MAX_OVERLAY_BINDINGS] timestamp of last toggle
   Debounce_State : Integer Array      // [MAX_OVERLAY_BINDINGS] 0=OFF, 1=ON
   DEBOUNCE_TIMEOUT : Double = 10.0    // seconds
```

- [ ] **Step 2: Write FireOverlayTrigger() — range-based dispatch**

```gpscript
// Evaluates overlay trigger based on range type and current value
// bindingKey = unique index for debounce state tracking
Function FireOverlayTrigger(funcName : String, channel : Integer, value : Double, rangeMin : Double, rangeMax : Double, bindingKey : Integer)
   if rangeMin == 0.0 and rangeMax == 1.0 then
      // FULL RANGE → Movement-Toggle with 10s debounce
      if not Debounce_Active[bindingKey] then
         if Debounce_State[bindingKey] == 0 then
            ActivateOverlay(funcName, channel)
            Debounce_State[bindingKey] = 1
         else
            DeactivateOverlay(funcName, channel)
            Debounce_State[bindingKey] = 0
         end
         Debounce_Active[bindingKey] = true
         Debounce_Timer[bindingKey] = TimeSinceStartup()
      end
      // Value always passes through (handled by caller)

   else
      // POSITIONAL — ON when value in [min,max], OFF otherwise
      var isInRange : Boolean
      if rangeMin == rangeMax then
         // Point trigger: exact match with small tolerance
         isInRange = (Abs(value - rangeMin) < 0.02)
      else
         isInRange = (value >= rangeMin and value <= rangeMax)
      end
      if isInRange then
         if Debounce_State[bindingKey] == 0 then
            ActivateOverlay(funcName, channel)
            Debounce_State[bindingKey] = 1
         end
      else
         if Debounce_State[bindingKey] == 1 then
            DeactivateOverlay(funcName, channel)
            Debounce_State[bindingKey] = 0
         end
      end
   end
End
```

- [ ] **Step 3: Add debounce timer check to On TimerTick**

In `On TimerTick` (~line 16261), add after existing timer checks:

```gpscript
   // --- Overlay Debounce Timer ---
   var dbIdx : Integer; var now : Double
   now = TimeSinceStartup()
   For dbIdx = 0; dbIdx < MAX_OVERLAY_BINDINGS; dbIdx = dbIdx + 1
      if Debounce_Active[dbIdx] then
         if now - Debounce_Timer[dbIdx] > DEBOUNCE_TIMEOUT then
            Debounce_Active[dbIdx] = false
         end
      end
   End
```

- [ ] **Step 4: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(trigger): range-based overlay triggers with 10s debounce for movement-toggle"
```

---

### Task 5: Layer-Aware ExecuteHardwareMacro

**Location:** SECTION 22, modify `ExecuteHardwareMacro()` (~line 10886)

- [ ] **Step 1: Rewrite ExecuteHardwareMacro for v2 dispatch**

The existing function routes macro value changes to Link_* arrays. The new version routes through the per-layer binding structure.

```gpscript
Function ExecuteHardwareMacro(matchedMacro : Integer, val : Double)
   var l, b, fi, bindingKey : Integer
   var targetType, target, funcName : String
   var rangeMin, rangeMax : Double; rangeMin = 0.0; rangeMax = 0.0
   var vstIdx, paramIdx, channel : Integer

   // Guard: plugin safety during init/snapshot
   if not IsLoadingSnapshot and TimeSinceStartup() > FaderSafetyTimer then

      // Process bindings per layer
      For l = 0; l < MAX_LAYERS; l = l + 1
         var bindCount : Integer
         bindCount = Mac_Layer_BindCount[MacLayerIdx(matchedMacro, l)]
         if bindCount > 0 then
            // Check layer visibility
            var shouldFire : Boolean
            if l == 0 then
               shouldFire = true   // LAY0 always fires
            else
               shouldFire = (ActiveLayer == l)
            end

            if shouldFire then
               For b = 0; b < bindCount; b = b + 1
                  fi = MacLayerBindIdx(matchedMacro, l, b)
                  targetType = Mac_Layer_TargetType[fi]
                  target = Mac_Layer_Target[fi]
                  rangeMin = Mac_Layer_RangeMin[fi]
                  rangeMax = Mac_Layer_RangeMax[fi]

                  if targetType == "VST" then
                     vstIdx = Mac_Layer_VSTIdx[fi]
                     paramIdx = Mac_Layer_ParamIdx[fi]
                     // Check VST validity
                     if vstIdx >= 1 and vstIdx < MAX_VST_DECL then
                        if MapVST_Valid[vstIdx] == 1 or MapVST_Valid[vstIdx] == 0 then
                           // Scale value to range
                           var scaledVal : Double = 0.0
                           scaledVal = rangeMin + (val * (rangeMax - rangeMin))
                           SetParameter(BLK_VST[vstIdx], paramIdx, scaledVal)
                        end
                     end

                  elsif targetType == "CC" then
                     // Parse Ch<c>:CC<n> and send
                     var ccCh, ccNum : Integer
                     ccCh = StringToInt(Mid(target, 3, Pos(":", target) - 3)) - 1
                     ccNum = StringToInt(Mid(target, Pos("CC", target) + 2, 999))
                     var scaledVal2 : Double = 0.0
                     scaledVal2 = rangeMin + (val * (rangeMax - rangeMin))
                     SendNowToMidiOutDevice(DEV_MidiOutHandle[0], MakeControlChangeMessageEx(ccNum, Round(scaledVal2 * 127), ccCh))

                  elsif targetType == "KEYWORD" then
                     // Dispatch to existing keyword handlers
                     ExecuteKeywordBinding(target, val)

                  elsif targetType == "SYSACT" then
                     // Fire system action (only on press, val > 0.5)
                     if val > 0.5 then
                        var actionIdx : Integer
                        actionIdx = SysActIdx(Mid(target, 8, 999))
                        if actionIdx >= 0 then
                           FireSystemAction(actionIdx)
                        end
                     end

                  elsif targetType == "OVERLAY" then
                     funcName = target
                     channel = Mac_Layer_Channel[fi]
                     bindingKey = fi  // Use flat index as debounce key
                     FireOverlayTrigger(funcName, channel, val, rangeMin, rangeMax, bindingKey)
                  end
               End
            end
         end
      End
   end
End
```

- [ ] **Step 2: Write ExecuteKeywordBinding() helper**

```gpscript
// Dispatches single-role keyword bindings
Function ExecuteKeywordBinding(keyword : String, val : Double)
   if keyword == "CROSSFADER" then
      SetWidgetValue(SLD_Crossfader, val)
   elsif keyword == "SCRUBBER" then
      if val > 0.5 then
         // Scrubber press
         SetWidgetValue(SLD_Scrubber, val)
      end
   elsif keyword == "VST_SCOPE" then
      // Absolute VST scope from encoder value
      var scopeIdx : Integer
      scopeIdx = Round(val * (MAX_VST_SCOPE - 1))
      ChangeVstScope(scopeIdx, 0)
   elsif keyword == "VST_BROWSE" then
      SetWidgetValue(SLD_VSTBrowse, val)
   elsif keyword == "VST_SCOPE_PREV" then
      if val > 0.5 then
         ChangeVstScope(-1, -1)
      end
   elsif keyword == "VST_SCOPE_NEXT" then
      if val > 0.5 then
         ChangeVstScope(1, -1)
      end
   elsif keyword == "VST_PREV" then
      if val > 0.5 then
         ChangeVstPreset(-1)
      end
   elsif keyword == "VST_NEXT" then
      if val > 0.5 then
         ChangeVstPreset(1)
      end
   elsif keyword == "SYSMODE_CYCLE" then
      if val > 0.5 then
         CycleGlobalSystemMode()
      end
   elsif keyword == "REC_SONGPART" then
      if val > 0.5 then
         RecordSongPart()
      end
   elsif keyword == "SYSTEM_TOGGLE" then
      if val > 0.5 then
         SystemModeActive = true
      else
         SystemModeActive = false
      end
   end
End
```

- [ ] **Step 3: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(dispatch): layer-aware ExecuteHardwareMacro with VST validation and overlay triggers"
```

---

### Task 6: ProcessHardwareCC — Unified Source Lookup

**Location:** SECTION 22, modify `ProcessHardwareCC()` (~line 11299)

- [ ] **Step 1: Update ProcessHardwareCC for unified source lookup**

Replace the HardwareMap-based lookup with the new reverse lookup from Mac_ReverseLookup_CC:

```gpscript
Function ProcessHardwareCC(m : ControlChangeMessage)
   var ccNum, ccCh : Integer; var val : Double = 0.0
   ccNum = GetCCNumber(m)
   ccCh = GetChannel(m)
   val = GetCCValue(m) / 127.0

   // 1. Check PERMANENT bindings first
   var perm : Integer
   For perm = 0; perm < Permanent_Count; perm = perm + 1
      if Permanent_Source[perm] == "CC" + IntToString(ccNum) then
         ExecuteKeywordBinding(Permanent_Function[perm], val)
      end
   End

   // 2. Check LAYERSWITCH CC triggers
   var swIdx : Integer
   For swIdx = 0; swIdx < LayerSwitch_Count; swIdx = swIdx + 1
      if LayerSwitch_Type[swIdx] == "CC" then
         // Parse CC number from source config and match
         // (Implementation depends on how CC layer switches store their CC reference)
         // For now: check if this CC matches the configured CC
      end
   End

   // 3. Reverse lookup: CC → Macro
   var lookupIdx, macroIdx : Integer
   lookupIdx = ccCh * 128 + ccNum
   if lookupIdx >= 0 and lookupIdx < 2048 then
      macroIdx = Mac_ReverseLookup_CC[lookupIdx]
      if macroIdx > 0 then
         ExecuteHardwareMacro(macroIdx, val)
      end
   end
End
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(input): ProcessHardwareCC with unified reverse lookup and PERMANENT bindings"
```

---

### Task 7: Reset Debounce on Song Switch

**Location:** SECTION 17, inside LoadControllerMapV2()

- [ ] **Step 1: Add debounce reset to LoadControllerMapV2()**

After `RebuildReverseLookups()` in `LoadControllerMapV2()`:

```gpscript
   // Reset debounce timers
   var dbIdx : Integer
   For dbIdx = 0; dbIdx < MAX_OVERLAY_BINDINGS; dbIdx = dbIdx + 1
      Debounce_Active[dbIdx] = false
      Debounce_Timer[dbIdx] = 0.0
      Debounce_State[dbIdx] = 0
   End
```

- [ ] **Step 2: Bump SCRIPT_VERSION**

```gpscript
   SCRIPT_VERSION : String = "2026-04-12-B"
```

- [ ] **Step 3: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(runtime): debounce reset on song switch, bump SCRIPT_VERSION for Plan B"
```
