# Plan C: Smart Solo Enhanced, Timeline Recording & VST Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance Smart Solo to consider RECH input + Manual zone, record all overlay toggles to Timeline, and complete VST validation with per-binding blocking.

**Architecture:** Smart Solo enhancement is a surgical change in `UpdateSoloMuteState()` — add a `sameZone` check alongside the existing `sameInput` check. Timeline recording hooks into the existing `RecordTimelineEvent()` call from `ActivateOverlay`/`DeactivateOverlay` (stub placed in Plan B). VST validation was implemented in Plan A's parser; this plan wires it into the execution path.

**Tech Stack:** GPScript 5.x, Global Rackspace script

**Depends on:** Plan A (parser, data structures) and Plan B (runtime engine, overlay dispatcher)

---

### Task 1: Smart Solo Enhanced — RECH + Manual Zone

**Location:** SECTION 21 (Orchestration), modify `UpdateSoloMuteState()` (~line 10189)

- [ ] **Step 1: Modify the Smart Solo block in UpdateSoloMuteState()**

Find the Smart Solo block (around lines 10257-10273). The current logic checks only `sameInput`. Add the `sameZone` check.

Replace the existing Smart Solo block:

```gpscript
      // --- SMART SOLO (Enhanced: RECH input + Manual zone) ---
      var anySmart : Boolean = false
      For outCol = 0; outCol < 16; outCol = outCol + 1
         if Mem_SoloSmart[outCol] == 1 then
            anySmart = true
         end
      End

      if anySmart then
         For outCol = 0; outCol < 16; outCol = outCol + 1
            if Mem_SoloSmart[outCol] == 0 then
               var fedBySameInputAndZone : Boolean = false
               For soloCh = 0; soloCh < 16; soloCh = soloCh + 1
                  if Mem_SoloSmart[soloCh] == 1 and soloCh <> outCol then
                     // Check 1: Same RECH input?
                     var sameInput : Boolean = false
                     For inRow = 0; inRow < 16; inRow = inRow + 1
                        if GetParameter(RECH, (inRow * 16) + outCol) > 0.5
                           and GetParameter(RECH, (inRow * 16) + soloCh) > 0.5 then
                           sameInput = true
                        end
                     End
                     // Check 2: Same Manual zone?
                     var sameZone : Boolean
                     sameZone = (Mem_Manual[outCol] == Mem_Manual[soloCh])
                     // Both must match for muting
                     if sameInput and sameZone then
                        fedBySameInputAndZone = true
                     end
                  end
               End
               if fedBySameInputAndZone then
                  LooperSoloMute[outCol] = true
               end
            end
         End
      end
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(solo): enhanced Smart Solo — RECH input AND Manual zone for mute decision"
```

---

### Task 2: Timeline Recording for Overlay Toggles

**Location:** SECTION 19 (Prompter & Timeline Engine, ~line 5118)

- [ ] **Step 1: Implement RecordTimelineOverlay()**

Replace the stub from Plan B with the actual implementation:

```gpscript
// Records overlay toggle events to the Timeline
Function RecordTimelineOverlay(funcName : String, channel : Integer, state : Integer)
   // Only record if timeline recording is active
   if TimelineRecording then
      var eventData : String
      eventData = "OVERLAY:" + funcName + ":CH" + IntToString(channel) + ":" + IntToString(state)
      RecordTimelineEvent("OVERLAY", eventData)
      if DebugMode then
         Trace("TL_REC: " + eventData)
      end
   end
End
```

- [ ] **Step 2: Add overlay playback to Timeline playback engine**

In the Timeline playback dispatch (wherever `PlaybackTimelineEvent` processes event types), add handling for `OVERLAY` events:

```gpscript
      // --- OVERLAY event playback ---
      elsif eventType == "OVERLAY" then
         // Parse: "OVERLAY:SMART_SOLO:CH3:1"
         var overlayData : String; var funcN : String; var chN, stateN : Integer
         var colonPos1, colonPos2, colonPos3 : Integer
         overlayData = eventPayload
         // Extract funcName
         colonPos1 = Pos(":", overlayData)
         funcN = Left(overlayData, colonPos1 - 1)
         overlayData = Mid(overlayData, colonPos1 + 1, 999)
         // Extract channel (after "CH")
         colonPos2 = Pos(":", overlayData)
         chN = StringToInt(Mid(overlayData, 3, colonPos2 - 3))
         // Extract state
         stateN = StringToInt(Mid(overlayData, colonPos2 + 1, 999))
         if stateN == 1 then
            ActivateOverlay(funcN, chN)
         else
            DeactivateOverlay(funcN, chN)
         end
```

- [ ] **Step 3: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(timeline): record and playback all overlay toggle events"
```

---

### Task 3: VST Validation Wiring in Execution Path

**Location:** SECTION 22, already partially implemented in Plan B's ExecuteHardwareMacro

The VST validation check is already in Plan B's `ExecuteHardwareMacro()`:

```gpscript
if MapVST_Valid[vstIdx] == 1 or MapVST_Valid[vstIdx] == 0 then
   // Execute
end
```

This task verifies the validation is complete and adds re-validation on VST bypass changes.

- [ ] **Step 1: Add VST re-validation on bypass state change**

In the existing `On WidgetValueChanged` handler for VST bypass buttons, add a re-validation trigger:

```gpscript
   // After toggling VST bypass:
   ValidateMapVSTs()
   UpdateControllerInfoDisplay()
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(vst): re-validate VST bindings on bypass state change"
```

---

### Task 4: Final SCRIPT_VERSION Bump + Plan Completion

- [ ] **Step 1: Bump SCRIPT_VERSION**

```gpscript
   SCRIPT_VERSION : String = "2026-04-12-C"
```

- [ ] **Step 2: Commit all plans complete**

```
git add "Global Rackspace.gpscript"
git commit -m "feat: complete Plan C — Smart Solo Enhanced, Timeline overlays, VST validation

All three implementation plans (A/B/C) are complete:
- Plan A: Parser & data structures (unified ControllerMap v2)
- Plan B: Runtime engine (layer state machine, overlay triggers, debounce)
- Plan C: Smart Solo Enhanced, Timeline recording, VST validation"
```

---

## E2E Test Plan (after all Plans A+B+C)

### Prerequisites
1. Copy `examples/DeviceConfig_v2.txt` and `examples/ControllerMaps_v2.txt` to the gig file directory
2. Load the gig file in Gig Performer
3. Check GP Script console for parse errors

### Test 1: Parser Verification
- [ ] Open GP, check script console for `LAYERSWITCH: 2 switches parsed`
- [ ] Check `PERMANENT: 2 bindings parsed`
- [ ] Check `OVERLAY: 1 actions parsed`
- [ ] Check LBL_ControllerInfo shows hierarchical display with [Map:Default]

### Test 2: Layer Switching
- [ ] Press Harmony button on Genos2 → console shows `LAYERSWITCH 0 (Harmony): ON`
- [ ] Verify `LAYER: 0 -> 1` trace
- [ ] Press Talk button → `LAYERSWITCH 1 (Talk): ON`, `LAYER: 1 -> 3` (both ON = state 3)
- [ ] Release Talk → `LAYER: 3 -> 1`
- [ ] Release Harmony → `LAYER: 1 -> 0`

### Test 3: Overlay Functions via Buttons
- [ ] Activate LAY1 (Harmony ON)
- [ ] Press BTN1 → should fire ROOT:CH1 ON
- [ ] Release BTN1 → ROOT:CH1 OFF
- [ ] Verify in strip control UI that Root is toggling for CH1

### Test 4: Overlay Functions via Sliders (Movement-Toggle)
- [ ] Activate LAY1 (Harmony ON)
- [ ] Move SLD1 → should fire SMART_SOLO:CH1 ON
- [ ] Verify Smart Solo CH1 is active in strip control
- [ ] Wait 10 seconds
- [ ] Move SLD1 again → SMART_SOLO:CH1 OFF
- [ ] Verify slider value still controls volume throughout

### Test 5: Smart Solo Enhanced
- [ ] Set CH1 = Upper, CH2 = Upper, CH3 = Lower
- [ ] Route both CH1 and CH2 from same RECH input
- [ ] Activate Smart Solo on CH1
- [ ] Verify: CH2 is muted (same input + same zone)
- [ ] Verify: CH3 is NOT muted (same input but different zone)

### Test 6: Song Switch & Inheritance
- [ ] Switch to a song using [Map:Omnisphere]
- [ ] Verify LBL_ControllerInfo shows VST1: Omnisphere [OK]
- [ ] Verify BTN1-5 have Omnisphere-specific VST params
- [ ] Verify LAY1/LAY2 overlays are inherited from Default (not explicitly in Omnisphere map)
- [ ] Switch to a song with unknown VST map → verify [MISMATCH] or [NOT LOADED]

### Test 7: SYSTEM_TOGGLE_ON via Layer 3
- [ ] Activate both Harmony + Talk (LAY3)
- [ ] Verify SYSTEM_TOGGLE is permanently ON (joystick navigation active without foot pedal)
- [ ] Use joystick to navigate SYSMODE
- [ ] Deactivate one switch → LAY3 exits, SYSTEM_TOGGLE returns to foot-pedal-only

### Test 8: Timeline Recording
- [ ] Start Timeline recording
- [ ] Activate/deactivate several overlays (Smart Solo, Root, Octaver)
- [ ] Stop recording
- [ ] Check timeline data contains OVERLAY events
- [ ] Play back timeline → verify overlays replay correctly

### Test 9: Permanent Bindings
- [ ] Verify CC64 (sustain pedal) still activates SYSTEM_TOGGLE in all maps
- [ ] Verify CC11 (expression) still controls CROSSFADER in all maps
- [ ] Verify these work regardless of which song map is loaded

### Test 10: BTN_SmartAdapt
- [ ] Focus on VST scope for Omnisphere
- [ ] Press SmartAdapt button
- [ ] Verify it loads [Map:Omnisphere] (not [Map:Standard_VST1])
- [ ] Check trace output for "SmartAdapt: Searching for [Map:Omnisphere]"
