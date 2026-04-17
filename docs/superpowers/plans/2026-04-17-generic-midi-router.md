# Generic MIDI Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hardcoded MIDI dispatch logic in callbacks with a data-driven generic router that reads from the unified DeviceConfig CONTROL registry.

**Architecture:** Four router entry points (`RouteCCEvent`, `RoutePBEvent`, `RouteNoteEvent`, `RouteSysExEvent`) all look up incoming events in the unified `CTRL_*[]` registry and dispatch by control type. The `[LAYERSWITCH:n]` config section is absorbed into `[CONTROL:n]` with `Type=LAYER_SWITCH`. All callbacks become one-liners. No legacy format support.

**Tech Stack:** GPScript (Gig Performer 5.x), INI-format DeviceConfig

**Spec:** `docs/superpowers/specs/2026-04-17-generic-midi-router-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `Global Rackspace.gpscript` | Modify | New constants, arrays, router functions, parser changes, callback rewrites |
| `examples/DeviceConfig.txt` | Modify | Migrate `[LAYERSWITCH:n]` → `[CONTROL:n]`, add Joystick fields, add StylePulse |
| `docs/DeviceConfig.md` | Modify | Document new control types and fields |
| `docs/ControllerMap.md` | Modify | Update references to layer switch config |

---

### Task 1: Add New Constants and Registry Arrays

**Files:**
- Modify: `Global Rackspace.gpscript:183-244` (constants and registry declarations)

- [ ] **Step 1: Add new type and trigger constants after line 187 (CTYPE_PAD)**

After:
```gpscript
   CTYPE_PAD      : Integer = 4
```

Add:
```gpscript
   CTYPE_LAYER_SWITCH  : Integer = 5
   CTYPE_STYLE_TRIGGER : Integer = 6

   TRIGGER_CC    : Integer = 0
   TRIGGER_SYSEX : Integer = 1
   TRIGGER_NOTE  : Integer = 2

   JOYSTICK_CROSSTALK_MS : Double = 120.0
```

- [ ] **Step 2: Add new CTRL_*[] arrays after line 224 (CTRL_Label)**

After:
```gpscript
   CTRL_Label    : String Array
```

Add:
```gpscript
   CTRL_ThreshHigh : Integer Array
   CTRL_ThreshLow  : Integer Array
   CTRL_Axis       : String Array
   CTRL_Direction  : Integer Array
   CTRL_TriggerType : Integer Array
   CTRL_OnData     : String Array
   CTRL_OffData    : String Array
   CTRL_SwitchIndex : Integer Array
```

- [ ] **Step 3: Add per-device joystick state arrays**

Replace the singleton joystick variables (around line 702):
```gpscript
   Joy_PB_Fired : Integer = 0
   Joy_CC1_Fired, Joy_CC16_Fired : Boolean = false
   Joy_CC16_ArmTime : Double = 0.0  // Cross-talk guard: armed timestamp for CC16 decision window
```

With per-device arrays:
```gpscript
   Joy_XFired     : Integer Array = [0, 0, 0, 0]       // 0/+1/-1 per device
   Joy_YUpFired   : Boolean Array = [false, false, false, false]
   Joy_YDownFired  : Boolean Array = [false, false, false, false]
   Joy_YDownArmTime : Double Array = [0.0, 0.0, 0.0, 0.0]
```

- [ ] **Step 4: Bump SCRIPT_VERSION**

Change line 36:
```gpscript
   SCRIPT_VERSION : String = "2026-04-17.001"
```

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(hal): add MIDI router constants, registry arrays, per-device joystick state"
```

---

### Task 2: Extend Parser for New Control Types and Fields

**Files:**
- Modify: `Global Rackspace.gpscript:1731-1740` (ParseControlType)
- Modify: `Global Rackspace.gpscript:1778-1818` (ParseDeviceConfig array init + CONTROL section)
- Modify: `Global Rackspace.gpscript:1889-1916` (key-value parsing for CONTROL and LAYERSWITCH sections)

- [ ] **Step 1: Extend ParseControlType() to recognize new types**

At line 1731, replace the entire function:
```gpscript
Function ParseControlType(typeStr : String) Returns Integer
   result = CTYPE_FADER
   Select
      typeStr == "FADER"          Do result = CTYPE_FADER
      typeStr == "ENCODER"        Do result = CTYPE_ENCODER
      typeStr == "BUTTON"         Do result = CTYPE_BUTTON
      typeStr == "JOYSTICK"       Do result = CTYPE_JOYSTICK
      typeStr == "PAD"            Do result = CTYPE_PAD
      typeStr == "LAYER_SWITCH"   Do result = CTYPE_LAYER_SWITCH
      typeStr == "STYLE_TRIGGER"  Do result = CTYPE_STYLE_TRIGGER
   End
End
```

- [ ] **Step 2: Add ParseTriggerType() helper after ParseControlType()**

```gpscript
Function ParseTriggerType(trigStr : String) Returns Integer
   result = TRIGGER_CC
   Select
      trigStr == "CC"    Do result = TRIGGER_CC
      trigStr == "SYSEX" Do result = TRIGGER_SYSEX
      trigStr == "NOTE"  Do result = TRIGGER_NOTE
   End
End
```

- [ ] **Step 3: Extend array initialization in ParseDeviceConfig()**

At line 1778-1781, replace:
```gpscript
      CTRL_DevIdx = []; CTRL_Type = []; CTRL_CC = []; CTRL_Channel = []
      CTRL_RangeMin = []; CTRL_RangeMax = []; CTRL_Feedback = []; CTRL_Label = []
      SYSEX_DevIdx = []; SYSEX_Purpose = []; SYSEX_Data = []
      CTRL_Count = 0; SYSEX_Count = 0
```

With:
```gpscript
      CTRL_DevIdx = []; CTRL_Type = []; CTRL_CC = []; CTRL_Channel = []
      CTRL_RangeMin = []; CTRL_RangeMax = []; CTRL_Feedback = []; CTRL_Label = []
      CTRL_ThreshHigh = []; CTRL_ThreshLow = []; CTRL_Axis = []; CTRL_Direction = []
      CTRL_TriggerType = []; CTRL_OnData = []; CTRL_OffData = []; CTRL_SwitchIndex = []
      SYSEX_DevIdx = []; SYSEX_Purpose = []; SYSEX_Data = []
      CTRL_Count = 0; SYSEX_Count = 0
```

- [ ] **Step 4: Extend CONTROL section defaults**

At line 1814-1818, replace:
```gpscript
            currentCtrlIdx = CTRL_Count
            CTRL_DevIdx <-- 0; CTRL_Type <-- CTYPE_FADER; CTRL_CC <-- -1
            CTRL_Channel <-- -1; CTRL_RangeMin <-- 0; CTRL_RangeMax <-- 127
            CTRL_Feedback <-- FB_NONE; CTRL_Label <-- ""
            CTRL_Count = CTRL_Count + 1
```

With:
```gpscript
            currentCtrlIdx = CTRL_Count
            CTRL_DevIdx <-- 0; CTRL_Type <-- CTYPE_FADER; CTRL_CC <-- -1
            CTRL_Channel <-- -1; CTRL_RangeMin <-- 0; CTRL_RangeMax <-- 127
            CTRL_Feedback <-- FB_NONE; CTRL_Label <-- ""
            CTRL_ThreshHigh <-- 0; CTRL_ThreshLow <-- 0
            CTRL_Axis <-- ""; CTRL_Direction <-- 0
            CTRL_TriggerType <-- TRIGGER_CC; CTRL_OnData <-- ""; CTRL_OffData <-- ""
            CTRL_SwitchIndex <-- -1
            CTRL_Count = CTRL_Count + 1
```

- [ ] **Step 5: Extend CONTROL key-value parsing**

At line 1889-1899, replace:
```gpscript
               elsif section == "CONTROL" and currentCtrlIdx >= 0 then
                  Select
                     key == "Device"   Do CTRL_DevIdx[currentCtrlIdx] = StringToInt(val)
                     key == "Label"    Do CTRL_Label[currentCtrlIdx] = val
                     key == "Type"     Do CTRL_Type[currentCtrlIdx] = ParseControlType(val)
                     key == "CC"       Do CTRL_CC[currentCtrlIdx] = StringToInt(val)
                     key == "Channel"  Do CTRL_Channel[currentCtrlIdx] = StringToInt(val)
                     key == "RangeMin" Do CTRL_RangeMin[currentCtrlIdx] = StringToInt(val)
                     key == "RangeMax" Do CTRL_RangeMax[currentCtrlIdx] = StringToInt(val)
                     key == "Feedback" Do CTRL_Feedback[currentCtrlIdx] = ParseFeedbackType(val)
                  End
```

With:
```gpscript
               elsif section == "CONTROL" and currentCtrlIdx >= 0 then
                  Select
                     key == "Device"       Do CTRL_DevIdx[currentCtrlIdx] = StringToInt(val)
                     key == "Label"        Do CTRL_Label[currentCtrlIdx] = val
                     key == "Type"         Do CTRL_Type[currentCtrlIdx] = ParseControlType(val)
                     key == "CC"           Do CTRL_CC[currentCtrlIdx] = StringToInt(val)
                     key == "Channel"      Do CTRL_Channel[currentCtrlIdx] = StringToInt(val)
                     key == "RangeMin"     Do CTRL_RangeMin[currentCtrlIdx] = StringToInt(val)
                     key == "RangeMax"     Do CTRL_RangeMax[currentCtrlIdx] = StringToInt(val)
                     key == "Feedback"     Do CTRL_Feedback[currentCtrlIdx] = ParseFeedbackType(val)
                     key == "ThresholdHigh" Do CTRL_ThreshHigh[currentCtrlIdx] = StringToInt(val)
                     key == "ThresholdLow"  Do CTRL_ThreshLow[currentCtrlIdx] = StringToInt(val)
                     key == "Axis"         Do CTRL_Axis[currentCtrlIdx] = val
                     key == "Direction"    Do CTRL_Direction[currentCtrlIdx] = StringToInt(val)
                     key == "TriggerType"  Do CTRL_TriggerType[currentCtrlIdx] = ParseTriggerType(val)
                     key == "OnData"       Do CTRL_OnData[currentCtrlIdx] = val
                     key == "OffData"      Do CTRL_OffData[currentCtrlIdx] = val
                     key == "SwitchIndex"  Do CTRL_SwitchIndex[currentCtrlIdx] = StringToInt(val)
                  End
```

- [ ] **Step 6: Remove `[LAYERSWITCH:n]` section parser**

Remove the section detector (line 1826-1833):
```gpscript
         elsif IndexOfSubstring(line, "[LAYERSWITCH:", false) == 0 then
            section = "LAYERSWITCH"
            currentSwitchIdx = StringToInt(CopySubstring(line, 13, 1))
            if currentSwitchIdx >= 0 and currentSwitchIdx < MAX_SWITCHES then
               if currentSwitchIdx >= LayerSwitch_Count then
                  LayerSwitch_Count = currentSwitchIdx + 1
               end
            end
```

And remove the LAYERSWITCH key-value parsing block (line 1908-1916):
```gpscript
               elsif section == "LAYERSWITCH" and currentSwitchIdx >= 0 and currentSwitchIdx < MAX_SWITCHES then
                  Select
                     key == "Device"   Do LayerSwitch_DevIdx[currentSwitchIdx] = StringToInt(val)
                     key == "Label"    Do LayerSwitch_Label[currentSwitchIdx] = val
                     key == "Type"     Do LayerSwitch_Type[currentSwitchIdx] = val
                     key == "OnData"   Do LayerSwitch_OnData[currentSwitchIdx] = val
                     key == "OffData"  Do LayerSwitch_OffData[currentSwitchIdx] = val
                     key == "Channel"  Do LayerSwitch_Channel[currentSwitchIdx] = StringToInt(val)
                  End
```

- [ ] **Step 7: Build LayerSwitch_State[] from parsed CONTROL entries**

After the parser loop ends (after line 1950, before the Trace output), add logic to populate `LayerSwitch_State[]` and `IgnoreSwitchOffUntil[]` from the registry and count switches:

```gpscript
      // Populate LayerSwitch_State from CONTROL registry
      LayerSwitch_Count = 0
      For i = 0; i < CTRL_Count; i = i + 1 Do
         if CTRL_Type[i] == CTYPE_LAYER_SWITCH and CTRL_SwitchIndex[i] >= 0 then
            if CTRL_SwitchIndex[i] + 1 > LayerSwitch_Count then
               LayerSwitch_Count = CTRL_SwitchIndex[i] + 1
            end
         end
      End
```

- [ ] **Step 8: Update Trace output at end of parser**

Replace lines 1952-1958:
```gpscript
      Trace("HAL: Loaded " + IntToString(CTRL_Count) + " controls, " + IntToString(SYSEX_Count) + " SysEx commands.")
      if LayerSwitch_Count > 0 then
         Trace("HAL: " + IntToString(LayerSwitch_Count) + " layer switches, " + IntToString(Permanent_Count) + " permanent bindings, " + IntToString(Overlay_Count) + " overlay actions")
         For sw = 0; sw < LayerSwitch_Count; sw = sw + 1 Do
            Trace("  Switch " + IntToString(sw) + ": " + LayerSwitch_Label[sw] + " [" + LayerSwitch_Type[sw] + "] OnData=" + LayerSwitch_OnData[sw] + " Ch=" + LayerSwitch_Channel[sw])
         End
      end
```

With:
```gpscript
      Trace("HAL: Loaded " + IntToString(CTRL_Count) + " controls, " + IntToString(SYSEX_Count) + " SysEx commands.")
      Trace("HAL: " + IntToString(LayerSwitch_Count) + " layer switches, " + IntToString(Permanent_Count) + " permanent bindings, " + IntToString(Overlay_Count) + " overlay actions")
      For i = 0; i < CTRL_Count; i = i + 1 Do
         if CTRL_Type[i] == CTYPE_LAYER_SWITCH then
            Trace("  Switch[" + IntToString(CTRL_SwitchIndex[i]) + "]: " + CTRL_Label[i] + " [TriggerType=" + CTRL_TriggerType[i] + "] OnData=" + CTRL_OnData[i])
         end
      End
```

- [ ] **Step 9: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(hal): extend parser for LAYER_SWITCH, STYLE_TRIGGER, joystick fields"
```

---

### Task 3: Write Router Functions

**Files:**
- Modify: `Global Rackspace.gpscript` — add new functions after `GetControlFeedback()` (line ~2270)

These functions must be defined **before** the callbacks that call them (GPScript forward declaration rule).

- [ ] **Step 1: Extend FindControl() to support channel matching**

Replace existing `FindControl` at line 2254-2260:
```gpscript
Function FindControl(devIdx : Integer, cc : Integer) Returns Integer
   var i : Integer
   result = -1
   For i = 0; i < CTRL_Count; i = i + 1 Do
      if CTRL_DevIdx[i] == devIdx and CTRL_CC[i] == cc then result = i end
   End
End
```

With:
```gpscript
Function FindControl(devIdx : Integer, cc : Integer) Returns Integer
   var i, found : Integer = -1
   For i = 0; i < CTRL_Count; i = i + 1 Do
      if found == -1 and CTRL_DevIdx[i] == devIdx and CTRL_CC[i] == cc then
         found = i
      end
   End
   result = found
End

Function FindControlWithChannel(devIdx : Integer, cc : Integer, channel : Integer) Returns Integer
   var i, found : Integer = -1
   For i = 0; i < CTRL_Count; i = i + 1 Do
      if found == -1 and CTRL_DevIdx[i] == devIdx and CTRL_CC[i] == cc then
         if CTRL_Channel[i] == -1 or CTRL_Channel[i] == channel then
            found = i
         end
      end
   End
   result = found
End
```

- [ ] **Step 2: Write SetLayerSwitchState()**

Add after `FindControlWithChannel`:
```gpscript
Function SetLayerSwitchState(switchIdx : Integer, newState : Integer)
   var j : Integer
   if switchIdx < 0 or switchIdx >= MAX_SWITCHES then
      // Invalid switch index — ignore
   elsif newState == 0 and TimeSinceStartup() < IgnoreSwitchOffUntil[switchIdx] then
      if DebugMode then Trace("LAYERSWITCH " + IntToString(switchIdx) + ": OFF suppressed (cross-talk)") end
   elsif LayerSwitch_State[switchIdx] != newState then
      LayerSwitch_State[switchIdx] = newState
      if newState == 1 then
         For j = 0; j < MAX_SWITCHES; j = j + 1 Do
            if j != switchIdx then IgnoreSwitchOffUntil[j] = TimeSinceStartup() + 200.0 end
         End
      end
      UpdateActiveLayer()
      if DebugMode then
         if newState == 1 then Trace("LAYERSWITCH " + IntToString(switchIdx) + ": ON")
         else Trace("LAYERSWITCH " + IntToString(switchIdx) + ": OFF") end
      end
   end
End
```

- [ ] **Step 3: Write DispatchJoystick()**

```gpscript
Function DispatchJoystick(deviceIdx : Integer, ctrlIdx : Integer, value : Integer)
   var axis : String = CTRL_Axis[ctrlIdx]
   var direction : Integer = CTRL_Direction[ctrlIdx]
   var threshHigh : Integer = CTRL_ThreshHigh[ctrlIdx]
   var threshLow : Integer = CTRL_ThreshLow[ctrlIdx]

   if SystemModeActive then
      if axis == "X" then
         if direction == 1 and value > threshHigh and Joy_XFired[deviceIdx] != 1 then
            Joy_XFired[deviceIdx] = 1; ProcessSystemNavigation(deviceIdx, "X_AXIS", 1)
         elsif direction == -1 and value < threshLow and Joy_XFired[deviceIdx] != -1 then
            Joy_XFired[deviceIdx] = -1; ProcessSystemNavigation(deviceIdx, "X_AXIS", -1)
         elsif direction == 1 and value <= threshHigh then
            Joy_XFired[deviceIdx] = 0
         elsif direction == -1 and value >= threshLow then
            Joy_XFired[deviceIdx] = 0
         end
      elsif axis == "Y" then
         if direction == 1 then
            if value > threshHigh and not Joy_YUpFired[deviceIdx] then
               Joy_YUpFired[deviceIdx] = true; ProcessSystemNavigation(deviceIdx, "Y_AXIS", 1)
            elsif value < threshLow then Joy_YUpFired[deviceIdx] = false end
         elsif direction == -1 then
            if value > threshHigh and Joy_YDownArmTime[deviceIdx] == 0.0 then
               Joy_YDownArmTime[deviceIdx] = TimeSinceStartup()
            end
            if value < threshLow then
               Joy_YDownArmTime[deviceIdx] = 0.0
               Joy_YDownFired[deviceIdx] = false
            end
         end
      end
   end
End
```

- [ ] **Step 4: Write DispatchStyleTrigger()**

```gpscript
Function DispatchStyleTrigger(ctrlIdx : Integer, value : Integer, channel : Integer)
   if channel + 1 == DEV_TriggerChannel and CTRL_CC[ctrlIdx] == GetCCNumber_fromValue(value) then
      // Note: The style trigger check is already channel-filtered by FindControlWithChannel.
      // The actual action: reset hardware pulse and toggle playhead
      if TimeSinceStartup() >= StyleEchoBlockTimer then
         LastHardwarePulseTime = TimeSinceStartup()
         if DebugMode then Trace(">>> STYLE-IN: Hardware CC" + IntToString(CTRL_CC[ctrlIdx]) + " detected") end
         if CurrentSyncMode == 2 or CurrentSyncMode == 3 then
            IsCorrectingPlayhead = false
            EnablePlayhead(not PendingPlayheadState)
         end
      end
   end
End
```

Wait — the style trigger in the original code (line 17110-17119) checks `cc == 5` and `ccChan + 1 == DEV_TriggerChannel`. With the router, the CC matching is done by `FindControlWithChannel()`. The channel in the STYLE_TRIGGER config specifies the trigger channel. Let me simplify:

```gpscript
Function DispatchStyleTrigger(ctrlIdx : Integer)
   if TimeSinceStartup() >= StyleEchoBlockTimer then
      LastHardwarePulseTime = TimeSinceStartup()
      if DebugMode then Trace(">>> STYLE-IN: Hardware CC" + IntToString(CTRL_CC[ctrlIdx]) + " detected (via router)") end
      if CurrentSyncMode == 2 or CurrentSyncMode == 3 then
         IsCorrectingPlayhead = false
         EnablePlayhead(not PendingPlayheadState)
      end
   end
End
```

- [ ] **Step 5: Write RouteCCEvent()**

```gpscript
Function RouteCCEvent(deviceIdx : Integer, cc : Integer, value : Integer, channel : Integer, msg : ControlChangeMessage)
   var ctrlIdx : Integer = FindControlWithChannel(deviceIdx, cc, channel)
   var ctrlType : Integer

   if ctrlIdx > -1 then
      ctrlType = CTRL_Type[ctrlIdx]
      Select
         ctrlType == CTYPE_JOYSTICK      Do DispatchJoystick(deviceIdx, ctrlIdx, value)
         ctrlType == CTYPE_LAYER_SWITCH   Do
            if CTRL_TriggerType[ctrlIdx] == TRIGGER_CC then
               if value > 63 then SetLayerSwitchState(CTRL_SwitchIndex[ctrlIdx], 1)
               else SetLayerSwitchState(CTRL_SwitchIndex[ctrlIdx], 0) end
            end
         ctrlType == CTYPE_STYLE_TRIGGER  Do DispatchStyleTrigger(ctrlIdx)
         ctrlType == CTYPE_FADER or ctrlType == CTYPE_ENCODER or ctrlType == CTYPE_BUTTON or ctrlType == CTYPE_PAD Do
            ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNowToDevice(deviceIdx, msg)
      End
   else
      // No control match — standard passthrough
      ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNowToDevice(deviceIdx, msg)
   end
End
```

Note: `SendNowToDevice` is a helper needed because GPScript's `SendNow` needs a specific block reference. We'll handle this in Task 4 with the callback rewrite. For now the router calls the existing `SendNow` via a dispatcher. Actually, let me check — the current code uses `SendNow(DeviceIn_0_A, m)` with the literal block name. We need a way to dispatch by deviceIdx. Let me revise:

The callbacks will pass the block reference directly. Revised signature:

```gpscript
Function RouteCCEvent(deviceIdx : Integer, cc : Integer, value : Integer, channel : Integer, msg : ControlChangeMessage, deviceBlock : Block)
   var ctrlIdx : Integer = FindControlWithChannel(deviceIdx, cc, channel)
   var ctrlType : Integer

   if ctrlIdx > -1 then
      ctrlType = CTRL_Type[ctrlIdx]
      Select
         ctrlType == CTYPE_JOYSTICK      Do DispatchJoystick(deviceIdx, ctrlIdx, value)
         ctrlType == CTYPE_LAYER_SWITCH   Do
            if CTRL_TriggerType[ctrlIdx] == TRIGGER_CC then
               if value > 63 then SetLayerSwitchState(CTRL_SwitchIndex[ctrlIdx], 1)
               else SetLayerSwitchState(CTRL_SwitchIndex[ctrlIdx], 0) end
            end
         ctrlType == CTYPE_STYLE_TRIGGER  Do DispatchStyleTrigger(ctrlIdx)
         ctrlType == CTYPE_FADER or ctrlType == CTYPE_ENCODER or ctrlType == CTYPE_BUTTON or ctrlType == CTYPE_PAD Do
            ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNow(deviceBlock, msg)
      End
   else
      ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNow(deviceBlock, msg)
   end
End
```

- [ ] **Step 6: Write RoutePBEvent()**

```gpscript
Function RoutePBEvent(deviceIdx : Integer, pbValue : Integer, msg : PitchBendMessage, deviceBlock : Block)
   var ctrlIdx : Integer = FindControlWithChannel(deviceIdx, -1, -1)
   var ctrlType : Integer
   var foundJoystick : Boolean = false
   var i : Integer

   // PitchBend may match multiple JOYSTICK controls (Left + Right).
   // Check all controls for this device with CC == -1.
   For i = 0; i < CTRL_Count; i = i + 1 Do
      if CTRL_DevIdx[i] == deviceIdx and CTRL_CC[i] == -1 and CTRL_Type[i] == CTYPE_JOYSTICK then
         DispatchJoystick(deviceIdx, i, pbValue)
         foundJoystick = true
      end
   End

   if not foundJoystick then
      SendNow(deviceBlock, msg)
   end
End
```

- [ ] **Step 7: Write RouteNoteEvent()**

```gpscript
Function RouteNoteEvent(deviceIdx : Integer, noteNum : Integer, velocity : Integer, channel : Integer, msg : NoteMessage, deviceBlock : Block)
   var i : Integer
   var handledSwitch : Boolean = false

   // Check for LAYER_SWITCH with TriggerType=NOTE
   For i = 0; i < CTRL_Count; i = i + 1 Do
      if CTRL_DevIdx[i] == deviceIdx and CTRL_Type[i] == CTYPE_LAYER_SWITCH and CTRL_TriggerType[i] == TRIGGER_NOTE then
         if CTRL_CC[i] == noteNum and (CTRL_Channel[i] == -1 or CTRL_Channel[i] == channel) then
            if velocity > 0 then SetLayerSwitchState(CTRL_SwitchIndex[i], 1)
            else SetLayerSwitchState(CTRL_SwitchIndex[i], 0) end
            handledSwitch = true
         end
      end
   End

   // Note events always continue through the pipeline (switches don't consume them)
   ProcessHardwareNote(msg)
   FeedLooper_Note(msg)
   SendNow(deviceBlock, msg)
End
```

Note: The note pipeline has additional logic (transport sync, timeline, style triggers, MIDI learn) that is specific to Device 0. This will be handled in Task 4 where the callbacks for Device 0 retain these extra calls after `RouteNoteEvent`.

- [ ] **Step 8: Write RouteSysExEvent()**

```gpscript
Function RouteSysExEvent(deviceIdx : Integer, m : SysexMessage)
   var i, byteIdx : Integer
   var matched : Boolean = false
   var incomingHex, hexByte : String

   // Build hex string from incoming SysEx
   incomingHex = ""
   For byteIdx = 0; byteIdx < SM_Length(m); byteIdx = byteIdx + 1 Do
      if byteIdx > 0 then incomingHex = incomingHex + " " end
      hexByte = IntToHexString(SM_GetValue(m, byteIdx))
      if Length(hexByte) == 1 then hexByte = "0" + hexByte end
      incomingHex = incomingHex + hexByte
   End
   incomingHex = MyToUpper(incomingHex)

   // Match against LAYER_SWITCH controls with TriggerType=SYSEX
   For i = 0; i < CTRL_Count; i = i + 1 Do
      if not matched and CTRL_DevIdx[i] == deviceIdx and CTRL_Type[i] == CTYPE_LAYER_SWITCH and CTRL_TriggerType[i] == TRIGGER_SYSEX then
         if incomingHex == MyToUpper(CTRL_OnData[i]) then
            matched = true
            SetLayerSwitchState(CTRL_SwitchIndex[i], 1)
         elsif incomingHex == MyToUpper(CTRL_OffData[i]) then
            matched = true
            SetLayerSwitchState(CTRL_SwitchIndex[i], 0)
         end
      end
   End

   // SysEx heartbeat detection (Yamaha: byte1 == 0x43)
   if SM_Length(m) >= 6 and SM_GetValue(m, 1) == 0x43 then
      LastHardwarePulseTime = TimeSinceStartup()
   end
End
```

Note: `RouteSysExEvent` handles only layer switches and heartbeat. The remaining SysEx logic (BPM sync, arranger commands, registration changes) stays in the Device 0 Port A `On SysexEvent` callback after the `RouteSysExEvent` call, because that logic is device-specific and complex.

- [ ] **Step 9: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(hal): implement MIDI router functions (CC, PB, Note, SysEx)"
```

---

### Task 4: Rewrite MIDI Callbacks

**Files:**
- Modify: `Global Rackspace.gpscript:17059-17141` (Device 0 Port A CC + PB)
- Modify: `Global Rackspace.gpscript:17182-17282` (Device 0 Port A Note)
- Modify: `Global Rackspace.gpscript:17291-17429` (Device 0 Port B all)
- Modify: `Global Rackspace.gpscript:17431-17438` (Device 0 Port B SysEx)
- Modify: `Global Rackspace.gpscript:17885-17946` (Device 0 Port A SysEx — layer switch block only)
- Modify: `Global Rackspace.gpscript:17144-17177` (Device 1 CC)
- Modify: `Global Rackspace.gpscript:17460-17477` (Device 2+3 CC)
- Modify: `Global Rackspace.gpscript:18312-18325` (TimerTick cross-talk guard)

This is the largest task. It replaces all hardcoded logic with router calls.

- [ ] **Step 1: Rewrite Device 0 Port A PitchBend callback (line 17059-17073)**

Replace:
```gpscript
On PitchBendEvent(m : PitchBendMessage) from DeviceIn_0_A
    var pbVal : Integer = GetPitchBendValue(m)
    if SystemModeActive then
        // TODO: Read joystick thresholds from control registry
        if pbVal > 12000 and Joy_PB_Fired != 1 then
            Joy_PB_Fired = 1; ProcessSystemNavigation(0, "X_AXIS", 1)
        elsif pbVal < 4000 and Joy_PB_Fired != -1 then
            Joy_PB_Fired = -1; ProcessSystemNavigation(0, "X_AXIS", -1)
        elsif pbVal >= 4000 and pbVal <= 12000 then
            Joy_PB_Fired = 0
        end
    else
        SendNow(DeviceIn_0_A, m)
    end
End
```

With:
```gpscript
On PitchBendEvent(m : PitchBendMessage) from DeviceIn_0_A
    RoutePBEvent(0, GetPitchBendValue(m), m, DeviceIn_0_A)
End
```

- [ ] **Step 2: Rewrite Device 0 Port A ControlChange callback (line 17075-17142)**

Replace the entire callback with:
```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_0_A
    RouteCCEvent(0, GetCCNumber(m), GetCCValue(m), GetChannel(m), m, DeviceIn_0_A)
End
```

This removes:
- Layer switch loop (lines 17082-17107)
- Style feedback CC5 check (lines 17110-17119)
- Joystick CC1/CC16 block (lines 17121-17138)
- Passthrough else-branch (line 17140)

- [ ] **Step 3: Rewrite Device 0 Port A NoteEvent callback (line 17182-17282)**

Replace with:
```gpscript
On NoteEvent(m : NoteMessage) from DeviceIn_0_A
    var chan : Integer = GetChannel(m)
    var inTrigIdx : Integer

    // 0. Route through generic MIDI router (layer switches + passthrough)
    RouteNoteEvent(0, GetNoteNumber(m), GetVelocity(m), chan, m, DeviceIn_0_A)

    // 1. Transport sync (Device 0 specific)
    if DeviceHasCap(0, CAP_TRANSPORT_SYNC) and IsNoteOn(m) and chan >= 9 and chan <= 16 then
        if CurrentSyncMode == 0 and IsPlayheadEnabled() then
             Trace(">>> ON NOTE: [ISOLATED] ArrangerStyle started (Ch " + chan + ") Stoppe GP")
             EnablePlayhead(false)
        elsif CurrentSyncMode == 1 or CurrentSyncMode == 2 or CurrentSyncMode == 3 then
             if StartWatchdogTimer > 0.0 then
                 Trace(">>> ON NOTE: Arranger already running (Ch " + chan + "). Aborting command.")
                 StartWatchdogTimer = 0.0 
             end
             if StopWatchdogTimer > 0.0 and not IsPlayheadEnabled() then
                 Trace(">>> ON NOTE: Arranger still playing (Ch " + chan + ")! Sending stop.")
                 FireDirectArrangerTransport()
                 StopWatchdogTimer = 0.0 
             else
                 LastHardwarePulseTime = TimeSinceStartup()
             end
        end
    end
    
    // 2. Timeline NoteOn-detection playback start
    if IsNoteOn(m) then
        if not TimelinePlaybackActive and not TimelineRecActive and Size(Snap_TL_TimeMS) > 0 then
            if GetWidgetValue(BTN_TL_HostSync) > 0.5 and not IsPlayheadEnabled() then
                StartTimelinePlayback()
            end
        end
    end

    // 3. Style trigger feedback from arranger
    if chan == DEV_TriggerChannel and IsNoteOn(m) then
       if TimeSinceStartup() >= StyleEchoBlockTimer then
          inTrigIdx = FindTriggerIdxByNote(GetNoteNumber(m))
          if inTrigIdx == TRIG_START_STOP then
             LastHardwarePulseTime = TimeSinceStartup()
             if DebugMode then Trace(">>> STYLE-IN: Hardware Start/Stop (Note " + IntToString(GetNoteNumber(m)) + ")") end
             if CurrentSyncMode == 2 and not IsPlayheadEnabled() then
                Trace("   [X] STYLE-IN: Arranger started in isolation! Abort echo...")
                TriggerStyleAction(TRIG_START_STOP)
             elsif CurrentSyncMode == 2 or CurrentSyncMode == 3 then
                IsCorrectingPlayhead = false
                EnablePlayhead(not PendingPlayheadState)
             end
          end
          if inTrigIdx >= 0 and inTrigIdx != TRIG_START_STOP then
             if RecordMode > 0 or TimelineRecActive then
                RecordTimelineEvent("Style", inTrigIdx)
             end
          end
       end
    end

    // 4. Keyboard split learning
    ProcessMidiLearn(m)
End
```

Note: `RouteNoteEvent` already calls `ProcessHardwareNote`, `FeedLooper_Note`, and `SendNow`, so those are removed from the callback. The Device-0-specific transport/timeline/style logic remains in the callback.

- [ ] **Step 4: Rewrite Device 0 Port B PitchBend callback (line 17291-17304)**

Replace:
```gpscript
On PitchBendEvent(m : PitchBendMessage) from DeviceIn_0_B
    var pbVal : Integer = GetPitchBendValue(m)
    if SystemModeActive then
        if pbVal > 12000 and Joy_PB_Fired != 1 then
            Joy_PB_Fired = 1; ProcessSystemNavigation(0, "X_AXIS", 1)
        elsif pbVal < 4000 and Joy_PB_Fired != -1 then
            Joy_PB_Fired = -1; ProcessSystemNavigation(0, "X_AXIS", -1)
        elsif pbVal >= 4000 and pbVal <= 12000 then
            Joy_PB_Fired = 0
        end
    else
        SendNow(DeviceIn_0_B, m)
    end
End
```

With:
```gpscript
On PitchBendEvent(m : PitchBendMessage) from DeviceIn_0_B
    RoutePBEvent(0, GetPitchBendValue(m), m, DeviceIn_0_B)
End
```

- [ ] **Step 5: Rewrite Device 0 Port B ControlChange callback**

Read the current Port B CC callback and replace its joystick/layer-switch logic with:
```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_0_B
    RouteCCEvent(0, GetCCNumber(m), GetCCValue(m), GetChannel(m), m, DeviceIn_0_B)
End
```

Note: Port B currently has CC7 Volume feedback handling (line ~17312). This device-specific logic needs to remain. Check the full callback — if CC7 volume is handled before the generic path, keep it as a pre-router check:

```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_0_B
    var cc : Integer = GetCCNumber(m)
    var val : Integer = GetCCValue(m)
    var ccChan : Integer = GetChannel(m)
    var scaledVol : Double = 0.0

    // --- CC7 Volume feedback from Genos2 (DIN MIDI specific) ---
    if cc == 7 and ccChan >= 0 and ccChan < 16 then
        scaledVol = IntToDouble(val) / 127.0
        Mem_Volume_Genos[ccChan] = scaledVol
        if DebugMode then Trace("GENOS VOL: Ch" + IntToString(ccChan + 1) + " = " + val) end
    else
        RouteCCEvent(0, cc, val, ccChan, m, DeviceIn_0_B)
    end
End
```

The implementer must read the full current Port B CC callback to preserve the CC7 volume logic accurately.

- [ ] **Step 6: Rewrite Device 0 Port B NoteEvent callback**

Replace the current callback (lines ~17359-17429) with:
```gpscript
On NoteEvent(m : NoteMessage) from DeviceIn_0_B
    RouteNoteEvent(0, GetNoteNumber(m), GetVelocity(m), GetChannel(m), m, DeviceIn_0_B)
End
```

- [ ] **Step 7: Rewrite Device 0 Port B SysEx callback (line 17431-17438)**

Replace:
```gpscript
On SysexEvent(m : SysexMessage) From DeviceIn_0_B
   // DIN MIDI SysEx from Genos2 — heartbeat only.
   // LayerSwitch matching is handled exclusively on Port A to avoid
   // duplicate processing (both ports receive the same SysEx bursts).
   if SM_Length(m) >= 6 and SM_GetValue(m, 1) == 0x43 then
       LastHardwarePulseTime = TimeSinceStartup()
   end
End
```

With:
```gpscript
On SysexEvent(m : SysexMessage) From DeviceIn_0_B
   RouteSysExEvent(0, m)
End
```

Note: Since `RouteSysExEvent` includes heartbeat detection AND layer switch matching, the old comment about "Port A only" no longer applies — the `SetLayerSwitchState` cross-talk guard handles duplicate SysEx bursts naturally (the second match within 200ms is suppressed).

- [ ] **Step 8: Remove layer switch block from Device 0 Port A SysEx callback (line 17904-17946)**

In the `On SysexEvent from DeviceIn_0_A` callback, replace the layer switch block (lines 17904-17946) with a single `RouteSysExEvent` call. The remaining SysEx logic (BPM sync, arranger commands, registration) stays.

Replace lines 17898-17946:
```gpscript
      // ---> NEW: THE SYSEX HEARTBEAT <---
      if byte1 == 0x43 then
          LastHardwarePulseTime = TimeSinceStartup()
      end

      // ---> LAYER SWITCH MATCHING <---
      incomingHexFull = ""
      For byteIdx = 0; byteIdx < msgSize; byteIdx = byteIdx + 1 Do
         ...entire layer switch block...
      End
```

With:
```gpscript
      // Generic MIDI router handles heartbeat + layer switches
      RouteSysExEvent(0, m)
```

The variables `incomingHexFull`, `hexByte`, `swIdx`, `guardIdx` can be removed from the callback's var declaration since they're no longer used.

- [ ] **Step 9: Rewrite Device 1 CC callback (line 17144-17177)**

Replace:
```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_1_A
    var cc : Integer = GetCCNumber(m)
    var val : Integer = GetCCValue(m)
    var ch : Integer = GetChannel(m)
    var dir : Integer = 0
    // TODO: Use FindControl/GetControlType from control registry
    var ctrlIdx : Integer = FindControl(1, cc)

    if DebugMode then
        Trace("MINILAB IN: CC " + cc + " | Val: " + val + " | Ch: " + ch)
    end

    if ctrlIdx >= 0 and GetControlType(ctrlIdx) == CTYPE_BUTTON and val > 0 then
        Trace("MINILAB: Button erkannt! Sende an Router...")
        ProcessSystemNavigation(1, "BUTTON", 1)
    elsif ctrlIdx >= 0 and GetControlType(ctrlIdx) == CTYPE_ENCODER then
        if val >= 65 then dir = 1 elsif val <= 63 then dir = -1 end
        if dir != 0 then 
            Trace("MINILAB: Encoder detected! Direction: " + dir)
            ProcessSystemNavigation(1, "ENCODER", dir) 
        end
    else
        ProcessHardwareCC(m); FeedLooper_CC(m); SendNow(DeviceIn_1_A, m) 
    end
End
```

With:
```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_1_A
    RouteCCEvent(1, GetCCNumber(m), GetCCValue(m), GetChannel(m), m, DeviceIn_1_A)
End
```

Note: The existing Device 1 logic (BUTTON → ProcessSystemNavigation, ENCODER → direction detection) must be absorbed into `RouteCCEvent`. The router already dispatches by `CTRL_Type`. For BUTTON and ENCODER types, add dispatch branches in `RouteCCEvent`:

Update the Select in `RouteCCEvent` (from Task 3 Step 5) to handle BUTTON and ENCODER system navigation:

```gpscript
         ctrlType == CTYPE_BUTTON Do
            if value > 0 and SystemModeActive then
               ProcessSystemNavigation(deviceIdx, "BUTTON", 1)
            else
               ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNow(deviceBlock, msg)
            end
         ctrlType == CTYPE_ENCODER Do
            if SystemModeActive then
               var encDir : Integer = 0
               if value >= 65 then encDir = 1 elsif value <= 63 then encDir = -1 end
               if encDir != 0 then ProcessSystemNavigation(deviceIdx, "ENCODER", encDir)
               else ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNow(deviceBlock, msg) end
            else
               ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNow(deviceBlock, msg)
            end
```

Wait — this changes the semantics for Device 0 buttons and encoders. On Device 0, buttons/encoders go through ProcessHardwareCC (macro dispatch), not system navigation. The SystemModeActive check is only relevant when the sustain pedal is held. Let me re-examine...

Actually, `SystemModeActive` is the guard for ALL system navigation, regardless of device. The current Device 1 code always checks `ctrlIdx >= 0 and GetControlType(ctrlIdx) == CTYPE_BUTTON` without a `SystemModeActive` guard — that's because Device 1 (MiniLab) buttons are ALWAYS system nav. But on Device 0, buttons go through ProcessHardwareCC.

This means the BUTTON/ENCODER dispatch can't be in the generic router — it's device-specific behavior. The clean solution: keep BUTTON and ENCODER in the generic `FADER/ENCODER/BUTTON/PAD` passthrough branch of `RouteCCEvent`, and handle Device 1's special behavior in the Device 1 callback.

Revised Device 1 callback:
```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_1_A
    var cc : Integer = GetCCNumber(m)
    var val : Integer = GetCCValue(m)
    var ch : Integer = GetChannel(m)
    var ctrlIdx : Integer = FindControlWithChannel(1, cc, ch)
    var dir : Integer = 0

    if DebugMode then Trace("MINILAB IN: CC " + cc + " | Val: " + val + " | Ch: " + ch) end

    // Device 1 specific: buttons and encoders are system navigation controls
    if ctrlIdx >= 0 and GetControlType(ctrlIdx) == CTYPE_BUTTON and val > 0 then
        ProcessSystemNavigation(1, "BUTTON", 1)
    elsif ctrlIdx >= 0 and GetControlType(ctrlIdx) == CTYPE_ENCODER then
        if val >= 65 then dir = 1 elsif val <= 63 then dir = -1 end
        if dir != 0 then ProcessSystemNavigation(1, "ENCODER", dir) end
    else
        RouteCCEvent(1, cc, val, ch, m, DeviceIn_1_A)
    end
End
```

This keeps Device 1's system navigation logic in the callback (because it's device-specific behavior, not generic routing) while using the router for everything else.

- [ ] **Step 10: Rewrite Device 2+3 CC callbacks (line 17460-17473)**

Replace:
```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_2_A
    ProcessHardwareCC(m); FeedLooper_CC(m); SendNow(DeviceIn_2_A, m)
End

On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_3_A
    ProcessHardwareCC(m); FeedLooper_CC(m); SendNow(DeviceIn_3_A, m)
End
```

With:
```gpscript
On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_2_A
    RouteCCEvent(2, GetCCNumber(m), GetCCValue(m), GetChannel(m), m, DeviceIn_2_A)
End

On ControlChangeEvent(m : ControlChangeMessage) from DeviceIn_3_A
    RouteCCEvent(3, GetCCNumber(m), GetCCValue(m), GetChannel(m), m, DeviceIn_3_A)
End
```

- [ ] **Step 11: Update TimerTick cross-talk guard (line 18312-18325)**

Replace:
```gpscript
   // 0. JOYSTICK CROSS-TALK GUARD (CC16 vs PitchBend: dominant axis wins after 120ms)
   if Joy_CC16_ArmTime > 0.0 and not Joy_CC16_Fired then
       if TimeSinceStartup() - Joy_CC16_ArmTime >= 120.0 then
           if Joy_PB_Fired == 0 and not Joy_CC1_Fired then
               if DebugMode then Trace(">>> SYSMODE-DIAG [D] CYCLE via CC16 timer (120ms, PB+CC1 quiet) in TimerTick") end
               Joy_CC16_Fired = true
               CycleGlobalSystemMode()
           else
               if DebugMode then Trace(">>> SYSMODE-DIAG [D-BLOCKED] CC16 suppressed (PB_Fired=" + Joy_PB_Fired + " CC1_Fired=" + Joy_CC1_Fired + ") cross-talk") end
           end
           Joy_CC16_ArmTime = 0.0  // Decision made, clear window
       end
   end
```

With:
```gpscript
   // 0. JOYSTICK CROSS-TALK GUARD (per-device, dominant axis wins after 120ms)
   var jtDev : Integer
   For jtDev = 0; jtDev < MAX_DEVICES; jtDev = jtDev + 1 Do
      if Joy_YDownArmTime[jtDev] > 0.0 and not Joy_YDownFired[jtDev] then
          if TimeSinceStartup() - Joy_YDownArmTime[jtDev] >= JOYSTICK_CROSSTALK_MS then
              if Joy_XFired[jtDev] == 0 and not Joy_YUpFired[jtDev] then
                  if DebugMode then Trace(">>> SYSMODE-DIAG [D] CYCLE via Y-Down timer (" + JOYSTICK_CROSSTALK_MS + "ms, X+Y quiet) Dev" + jtDev) end
                  Joy_YDownFired[jtDev] = true
                  CycleGlobalSystemMode()
              else
                  if DebugMode then Trace(">>> SYSMODE-DIAG [D-BLOCKED] Y-Down suppressed (XFired=" + Joy_XFired[jtDev] + " YUp=" + Joy_YUpFired[jtDev] + ") cross-talk Dev" + jtDev) end
              end
              Joy_YDownArmTime[jtDev] = 0.0
          end
      end
   End
```

- [ ] **Step 12: Remove dead LayerSwitch_* variable declarations**

Remove from line 232-244:
```gpscript
   // --- Layer Switch Registry (dynamic, filled from DeviceConfig v2) ---
   MAX_SWITCHES : Integer = 8
   LayerSwitch_Count : Integer = 0
   LayerSwitch_DevIdx : Integer Array = [-1, -1, -1, -1, -1, -1, -1, -1]
   LayerSwitch_Label : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_Type : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_OnData : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_OffData : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_Channel : Integer Array = [-1, -1, -1, -1, -1, -1, -1, -1]  // -1 = any channel
```

Keep (still needed by SetLayerSwitchState and UpdateActiveLayer):
```gpscript
   MAX_SWITCHES : Integer = 8
   LayerSwitch_Count : Integer = 0
   LayerSwitch_State : Integer Array = [0, 0, 0, 0, 0, 0, 0, 0]
   IgnoreSwitchOffUntil : Double Array = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

- [ ] **Step 13: Bump SCRIPT_VERSION**

```gpscript
   SCRIPT_VERSION : String = "2026-04-17.002"
```

- [ ] **Step 14: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(hal): rewrite all MIDI callbacks to use generic router

Eliminates hardcoded joystick thresholds, layer-switch loops,
and style-trigger detection from callbacks. Port A/B duplication
removed. All dispatch is data-driven from CTRL_*[] registry."
```

---

### Task 5: Migrate DeviceConfig File

**Files:**
- Modify: `examples/DeviceConfig.txt:95-131` (joystick controls + layer switches)

- [ ] **Step 1: Add joystick fields to existing CONTROL entries**

Replace lines 95-131:
```ini
; --- Genos2 Joystick (4 virtual controls from 2 physical axes) ---

[CONTROL:0]
Device=0
Label=JoyUp
Type=JOYSTICK
CC=1
RangeMin=64
RangeMax=127
Feedback=NONE

[CONTROL:1]
Device=0
Label=JoyDown
Type=JOYSTICK
CC=16
RangeMin=0
RangeMax=127
Feedback=NONE

[CONTROL:2]
Device=0
Label=JoyLeft
Type=JOYSTICK
CC=-1
RangeMin=0
RangeMax=8191
Feedback=NONE

[CONTROL:3]
Device=0
Label=JoyRight
Type=JOYSTICK
CC=-1
RangeMin=8192
RangeMax=16383
Feedback=NONE
```

With:
```ini
; --- Genos2 Joystick (4 virtual controls from 2 physical axes) ---

[CONTROL:0]
Device=0
Label=JoyUp
Type=JOYSTICK
CC=1
RangeMin=64
RangeMax=127
ThresholdHigh=100
ThresholdLow=20
Axis=Y
Direction=+1
Feedback=NONE

[CONTROL:1]
Device=0
Label=JoyDown
Type=JOYSTICK
CC=16
RangeMin=0
RangeMax=127
ThresholdHigh=100
ThresholdLow=20
Axis=Y
Direction=-1
Feedback=NONE

[CONTROL:2]
Device=0
Label=JoyLeft
Type=JOYSTICK
CC=-1
RangeMin=0
RangeMax=8191
ThresholdHigh=4000
ThresholdLow=4000
Axis=X
Direction=-1
Feedback=NONE

[CONTROL:3]
Device=0
Label=JoyRight
Type=JOYSTICK
CC=-1
RangeMin=8192
RangeMax=16383
ThresholdHigh=12000
ThresholdLow=12000
Axis=X
Direction=+1
Feedback=NONE
```

- [ ] **Step 2: Convert [LAYERSWITCH:n] sections to [CONTROL:n] entries**

Find the existing `[LAYERSWITCH:0]` and `[LAYERSWITCH:1]` sections and the `[LAYERMAP:0]` section. Remove the LAYERSWITCH sections entirely and add new CONTROL entries. The LAYERMAP section stays unchanged.

Add after the last encoder/fader control (before LAYERMAP):
```ini
; --- Layer Switches (formerly [LAYERSWITCH:n] sections) ---

[CONTROL:20]
Device=0
Label=Harmony
Type=LAYER_SWITCH
TriggerType=SYSEX
OnData=F0 43 10 4C 04 00 0C 40 F7
OffData=F0 43 10 4C 04 00 0C 7F F7
SwitchIndex=0

[CONTROL:21]
Device=0
Label=Talk
Type=LAYER_SWITCH
TriggerType=SYSEX
OnData=F0 43 10 4C 10 00 0B 64 F7
OffData=F0 43 10 4C 10 00 0B 7F F7
SwitchIndex=1

; --- Style Trigger ---

[CONTROL:22]
Device=0
Label=StylePulse
Type=STYLE_TRIGGER
TriggerType=CC
CC=5
Channel=16
Feedback=NONE
```

- [ ] **Step 3: Commit**

```bash
git add "examples/DeviceConfig.txt"
git commit -m "feat(config): migrate DeviceConfig to unified CONTROL registry

- Joystick controls get ThresholdHigh/Low, Axis, Direction fields
- [LAYERSWITCH:n] sections replaced by [CONTROL:n] Type=LAYER_SWITCH
- Style trigger added as [CONTROL:22] Type=STYLE_TRIGGER"
```

---

### Task 6: Update Documentation

**Files:**
- Modify: `docs/DeviceConfig.md`
- Modify: `docs/ControllerMap.md`

- [ ] **Step 1: Update docs/DeviceConfig.md**

Add the new control types to the control types table:

```markdown
| `LAYER_SWITCH` | Binary toggle trigger | On/Off |
| `STYLE_TRIGGER` | Style feedback pulse | CC value |
```

Add a new section documenting the JOYSTICK fields (ThresholdHigh, ThresholdLow, Axis, Direction).

Add a section explaining that `[LAYERSWITCH:n]` sections are replaced by `[CONTROL:n]` with `Type=LAYER_SWITCH`.

Document the `TriggerType`, `OnData`, `OffData`, `SwitchIndex` fields.

- [ ] **Step 2: Update docs/ControllerMap.md**

Update any references to `[LAYERSWITCH:n]` format to point to the new `[CONTROL:n]` format.

Update the "Joystick events" section (line ~352) to explain that joystick thresholds are now data-driven from DeviceConfig.

- [ ] **Step 3: Commit**

```bash
git add docs/DeviceConfig.md docs/ControllerMap.md
git commit -m "docs: update DeviceConfig and ControllerMap for generic MIDI router"
```

---

### Task 7: Verify RoutePBEvent Passthrough for Non-SystemMode

**Important edge case:** When `SystemModeActive` is false and PitchBend arrives, the current code does `SendNow(DeviceIn_0_A, m)`. In the new `RoutePBEvent`, the `DispatchJoystick` function only processes when `SystemModeActive` is true. When it's false, the PitchBend should pass through.

- [ ] **Step 1: Add passthrough to DispatchJoystick for non-SystemMode**

Update `DispatchJoystick` (from Task 3 Step 3) — the current version only has the `if SystemModeActive then` block. Add an else clause that signals passthrough is needed. Since GPScript can't return multiple values, the simplest approach is to NOT call DispatchJoystick when SystemModeActive is false.

Update `RoutePBEvent` to check SystemModeActive:

```gpscript
Function RoutePBEvent(deviceIdx : Integer, pbValue : Integer, msg : PitchBendMessage, deviceBlock : Block)
   var i : Integer
   var foundJoystick : Boolean = false

   if SystemModeActive then
      // Route to joystick controls
      For i = 0; i < CTRL_Count; i = i + 1 Do
         if CTRL_DevIdx[i] == deviceIdx and CTRL_CC[i] == -1 and CTRL_Type[i] == CTYPE_JOYSTICK then
            DispatchJoystick(deviceIdx, i, pbValue)
            foundJoystick = true
         end
      End
   end

   if not foundJoystick then
      SendNow(deviceBlock, msg)
   end
End
```

Similarly update `RouteCCEvent` — when a JOYSTICK control is matched but `SystemModeActive` is false, the CC should pass through:

```gpscript
         ctrlType == CTYPE_JOYSTICK      Do
            if SystemModeActive then DispatchJoystick(deviceIdx, ctrlIdx, value)
            else ProcessHardwareCC(msg); FeedLooper_CC(msg); SendNow(deviceBlock, msg) end
```

- [ ] **Step 2: Bump SCRIPT_VERSION**

```gpscript
   SCRIPT_VERSION : String = "2026-04-17.003"
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "fix(hal): joystick CC/PB passthrough when SystemMode inactive"
```

---

### Task 8: End-to-End Verification

- [ ] **Step 1: Verify parser loads new fields**

Grep for the Trace output in the GP log after loading. Expected:
```
HAL: Loaded 23 controls, N SysEx commands.
HAL: 2 layer switches, ...
  Switch[0]: Harmony [TriggerType=1] OnData=F0 43 10 4C 04 00 0C 40 F7
  Switch[1]: Talk [TriggerType=1] OnData=F0 43 10 4C 10 00 0B 64 F7
```

- [ ] **Step 2: Verify joystick navigation**

With sustain pedal held (SystemModeActive=true):
1. Move joystick UP → should fire Y_AXIS +1 (CC1 > 100)
2. Move joystick DOWN → should arm Y-Down, after 120ms fire CycleGlobalSystemMode (CC16 > 100)
3. Move joystick LEFT → should fire X_AXIS -1 (PB < 4000)
4. Move joystick RIGHT → should fire X_AXIS +1 (PB > 12000)
5. Release sustain → joystick events should pass through (no system navigation)

- [ ] **Step 3: Verify layer switches**

1. Trigger Harmony SysEx ON → Layer should switch
2. Trigger Talk SysEx ON → Layer should switch
3. Rapid switching → cross-talk guard should suppress phantom OFF within 200ms

- [ ] **Step 4: Verify style trigger**

1. Send CC5 on TriggerChannel → should detect as hardware start/stop
2. Check transport sync modes 2/3 respond correctly

- [ ] **Step 5: Verify CC passthrough**

1. Move faders → ProcessHardwareCC should receive events, macro dispatch works
2. Turn encoders → ControllerMap overlay dispatch works
3. Verify Device 1 (MiniLab) buttons and encoders still trigger system navigation

- [ ] **Step 6: Verify Port A/B equivalence**

1. Send same CC event on Port A and Port B → same result
2. Send same PitchBend on Port A and Port B → same result
3. SysEx layer switch on Port B → should work (previously Port A only)

- [ ] **Step 7: Final commit with version bump**

```bash
git add "Global Rackspace.gpscript"
git commit -m "chore: bump SCRIPT_VERSION after generic MIDI router verification"
```
