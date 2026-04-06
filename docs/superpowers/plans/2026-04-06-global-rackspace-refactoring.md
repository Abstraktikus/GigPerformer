# Global Rackspace Refactoring & HAL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `Global Rackspace V25.gpscript` into a thematically organized, hardware-neutral `Global Rackspace V26.gpscript` with a capability-based HAL and external device configuration.

**Architecture:** Single-file GPScript refactoring with 26 sections (12 Var, 11 Function, 3 Lifecycle). New HAL layer using parallel arrays and INI-style config file. All ~180 functions reordered by theme while respecting declare-before-use. Hardware-specific code (174 Genos + 34 MiniLab refs) replaced with capability-based dispatch.

**Tech Stack:** GPScript 5.x, Gig Performer Global Rackspace

**Spec:** `docs/superpowers/specs/2026-04-06-global-rackspace-refactoring-design.md`

**Verification note:** GPScript has no CLI compiler or test framework. Verification uses grep-based checks for structural correctness. Final compile-test requires opening the .gpscript in Gig Performer (manual step by the user).

---

## Task 1: Create DeviceConfig.txt

**Files:**
- Create: `DeviceConfig.txt`

- [ ] **Step 1: Write the device configuration file**

```ini
; =============================================================================
; DEVICE CONFIGURATION — Hardware Abstraction Layer
; =============================================================================
; This file defines all connected MIDI devices, their physical controls,
; and SysEx commands. Edit this file to match your hardware setup.
;
; Capabilities: TRANSPORT_SYNC, SYSEX_TRIGGER, CROSSFADER_TARGETS,
;               SYSEX_PROFILES, JOYSTICK, MIDI_OUT, FEEDBACK_CC, SYSEX_COMMANDS
;
; Control Types: FADER, ENCODER, BUTTON, JOYSTICK, PAD
; Feedback: NONE, CC, SYSEX
; =============================================================================

[DEVICE:0]
Name=Genos2
MidiIn=Digital Keyboard-1
MidiOut=Digital Keyboard-1
Channel=0
Caps=TRANSPORT_SYNC,SYSEX_TRIGGER,CROSSFADER_TARGETS,JOYSTICK,MIDI_OUT

[DEVICE:1]
Name=MiniLab3
MidiIn=Minilab3 MIDI
MidiOut=Minilab3 MIDI
Channel=0
Caps=SYSEX_PROFILES,SYSEX_COMMANDS

[CONTROL:0]
Device=0
Label=Joystick Y
Type=JOYSTICK
CC=1
RangeMin=0
RangeMax=127
Feedback=NONE

[CONTROL:1]
Device=0
Label=Joystick X
Type=JOYSTICK
CC=-1
RangeMin=0
RangeMax=16383
Feedback=NONE

[CONTROL:2]
Device=1
Label=Main Encoder
Type=ENCODER
CC=114
RangeMin=0
RangeMax=127
Feedback=SYSEX

[CONTROL:3]
Device=1
Label=Button 1
Type=BUTTON
CC=118
RangeMin=0
RangeMax=1
Feedback=SYSEX

[CONTROL:4]
Device=1
Label=Button 2
Type=BUTTON
CC=115
RangeMin=0
RangeMax=1
Feedback=SYSEX

[SYSEX:0]
Device=1
Purpose=PROFILE_1
Data=F0 00 20 6B 7F 42 02 00 62 01 F7

[SYSEX:1]
Device=1
Purpose=PROFILE_5
Data=F0 00 20 6B 7F 42 02 00 62 05 F7

[SYSEX:2]
Device=1
Purpose=PROFILE_6
Data=F0 00 20 6B 7F 42 02 00 62 06 F7

[SYSEX:3]
Device=1
Purpose=PROFILE_7
Data=F0 00 20 6B 7F 42 02 00 62 07 F7
```

- [ ] **Step 2: Commit**

```bash
git add DeviceConfig.txt
git commit -m "feat(HAL): add DeviceConfig.txt for Genos2 + MiniLab3 setup"
```

---

## Task 2: Create migration guide

**Files:**
- Create: `docs/MIGRATION-V25-to-V26.md`

- [ ] **Step 1: Write the migration guide**

```markdown
# Migration Guide: V25 → V26

## Prerequisites
- Gig Performer 5.x
- Backup your .gigfile before making changes

## Step 1: Wiring Changes (GP Wiring View)

Rename these blocks in the Wiring View:

| Old Name | New Name | Type |
|---|---|---|
| MainMidiIn | DeviceIn_0 | MidiInBlock |
| MiniLab3 | DeviceIn_1 | MidiInBlock |
| Genos2_Control | ExternalArranger | PluginBlock (Scriptlet) |
| BLK_GenosStyle | BLK_ArrangerSync | PluginBlock |

Create these new blocks:

| Name | Type | Notes |
|---|---|---|
| DeviceIn_2 | MidiInBlock | Empty, for future hardware |
| DeviceIn_3 | MidiInBlock | Empty, for future hardware |

## Step 2: File Placement

Place these files in your Snapshots folder (same folder as HardwareMap.txt):
- `DeviceConfig.txt` — edit to match your hardware

## Step 3: Script Replacement

Replace `Global Rackspace V25.gpscript` with `Global Rackspace V26.gpscript` in the Global Rackspace script editor.

## Step 4: Verification

1. Open the script editor — it should compile without errors
2. Check the log window for: `HAL: Device Genos2 connected.`
3. Test basic functions: channel switching, looper, VST browser
4. Test hardware: joystick, encoder, buttons
```

- [ ] **Step 2: Commit**

```bash
git add docs/MIGRATION-V25-to-V26.md
git commit -m "docs: add V25 to V26 migration guide"
```

---

## Task 3: Scaffold V26 — Var Block (Sections 1–12)

**Files:**
- Create: `Global Rackspace V26.gpscript` (copy from V25, then restructure Var block)

This task reorganizes only the `Var` block (lines 1–496 of V25). Functions and callbacks are copied as-is for now and restructured in later tasks.

- [ ] **Step 1: Copy V25 to V26**

```bash
cp "Global Rackspace V25.gpscript" "Global Rackspace V26.gpscript"
```

- [ ] **Step 2: Rewrite the file header and Var block structure**

Replace lines 1–6 (the old header) with:

```
// ============================================================================
// GLOBAL RACKSPACE SCRIPT — UNIVERSAL EDITION V1
// ============================================================================
// Hardware-neutral design with capability-based Hardware Abstraction Layer.
// Configure your devices in DeviceConfig.txt (INI format).
//
// Reference:
//   Language: https://gigperformer.com/docs_5_0/LanguageManual/
//   Functions: https://gigperformer.com/docs_5_0/SystemFunctionList.html
//   Design Spec: docs/superpowers/specs/2026-04-06-global-rackspace-refactoring-design.md
// ============================================================================
```

- [ ] **Step 3: Reorganize the Var block into 12 numbered sections**

Move variable declarations within the Var block to match this structure. No variables are added or removed yet — this is pure reordering within the existing Var block:

**Section 1: USER CONFIGURATION** (from current section 1)
- `DebugMode`, `Local_IP`, `Local_PORT`, `UserChordProPath`, `UserSnapshotPath`, `ControllerMapFilePath`, `HardwareMapFilePath`, `VstDatabaseFilePath`
- NEW: `DeviceConfigFilePath : String`

**Section 2: CORE CONSTANTS** (from current section 2)
- `ConfigPrefix`, `ConfigSuffix`, `DefaultPreset`, `NEW_LINE`, `ASCII_LOOKUP`, `FILTER_DEFAULT_VAL`
- `MAX_LINKS`, `MAX_VSTS`, `MAX_MACROS`
- All `DEF_*_MacroIdx` arrays
- `MacroGroup_Names`, `MacroGroup_Anchors`
- All `*_MacroIdx`, `*_CCIdx` engine arrays
- `HumanRoutingMap`, `SECTION_KEYWORDS`, `SyncModeNames`, `UsageCategories`
- `NoteNamesSharp`, `NoteNamesFlat`
- `FilterPresets`, `SysModeNames`

**Section 3: HAL — DEVICE & CONTROL REGISTRY** — see Task 4 (new variables added here)

**Section 4: PLUGIN BLOCKS & HARDWARE HANDLES** (from current section 4, renamed blocks)
- `RECH`, `AudioMixer`, `ExternalArranger` (was `Genos2_Control`), `BLK_VelocityMonitor`, `BLK_ArrangerSync` (was `BLK_GenosStyle`), `SystemActions`
- `DeviceIn_0` (was `MainMidiIn`), `DeviceIn_1` (was `MiniLab3`), `DeviceIn_2`, `DeviceIn_3`, `BLK_VSTControl`
- VST blocks, MidiIn blocks, NoteProcessor blocks, BLK arrays

**Sections 5–12:** Keep content from current sections 5–12, only update section headers to English and add section numbers.

Rename in the Var block:
- `Genos2_Control : PluginBlock` → `ExternalArranger : PluginBlock`
- `MiniLab3 : MidiInBlock` → `DeviceIn_1 : MidiInBlock`
- `MainMidiIn : MidiInBlock` → `DeviceIn_0 : MidiInBlock`
- `BLK_GenosStyle : PluginBlock` → `BLK_ArrangerSync : PluginBlock`
- `IsGenos, IncomingFromGenos` → `IncomingFromArranger : Boolean = false` (remove `IsGenos`)
- `W_CF_Genos` → `W_CF_Arranger`
- `DEF_CF_Genos` → `DEF_CF_Arranger`
- Add: `DeviceIn_2, DeviceIn_3 : MidiInBlock`

- [ ] **Step 4: Verify Var block structure**

```bash
grep -c "SECTION [0-9]" "Global Rackspace V26.gpscript"
# Expected: 12 section headers
grep "Genos2_Control\|BLK_GenosStyle\|MiniLab3.*MidiInBlock\|MainMidiIn.*MidiInBlock" "Global Rackspace V26.gpscript"
# Expected: no matches (all renamed)
```

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(V26): scaffold with reorganized Var block and renamed blocks"
```

---

## Task 4: Add HAL Variables (Var Block Section 3)

**Files:**
- Modify: `Global Rackspace V26.gpscript` (Var block, Section 3)

- [ ] **Step 1: Insert HAL constants and registry arrays into Section 3**

After the Section 3 header, insert:

```
   // --- Capability Flags (bitfield, combinable) ---
   CAP_NONE              : Integer = 0
   CAP_TRANSPORT_SYNC    : Integer = 1
   CAP_SYSEX_TRIGGER     : Integer = 2
   CAP_CROSSFADER_TARGETS: Integer = 4
   CAP_SYSEX_PROFILES    : Integer = 8
   CAP_JOYSTICK          : Integer = 16
   CAP_MIDI_OUT          : Integer = 32
   CAP_FEEDBACK_CC       : Integer = 64
   CAP_SYSEX_COMMANDS    : Integer = 128

   // --- Control Type Constants ---
   CTYPE_FADER    : Integer = 0
   CTYPE_ENCODER  : Integer = 1
   CTYPE_BUTTON   : Integer = 2
   CTYPE_JOYSTICK : Integer = 3
   CTYPE_PAD      : Integer = 4

   // --- Feedback Method Constants ---
   FB_NONE  : Integer = 0
   FB_CC    : Integer = 1
   FB_SYSEX : Integer = 2

   // --- Device Registry (4 slots) ---
   MAX_DEVICES  : Integer = 4
   DEV_Active   : Boolean Array = [false, false, false, false]
   DEV_Name     : String Array  = ["", "", "", ""]
   DEV_MidiIn   : String Array  = ["", "", "", ""]
   DEV_MidiOut  : String Array  = ["", "", "", ""]
   DEV_Channel  : Integer Array = [0, 0, 0, 0]
   DEV_Caps     : Integer Array = [0, 0, 0, 0]
   DEV_BlockIdx : Integer Array = [-1, -1, -1, -1]

   // --- Control Registry (dynamic, filled from config) ---
   MAX_CONTROLS  : Integer = 64
   CTRL_Count    : Integer = 0
   CTRL_DevIdx   : Integer Array
   CTRL_Type     : Integer Array
   CTRL_CC       : Integer Array
   CTRL_Channel  : Integer Array
   CTRL_RangeMin : Integer Array
   CTRL_RangeMax : Integer Array
   CTRL_Feedback : Integer Array
   CTRL_Label    : String Array

   // --- SysEx Command Registry (dynamic, filled from config) ---
   SYSEX_Count   : Integer = 0
   SYSEX_DevIdx  : Integer Array
   SYSEX_Purpose : String Array
   SYSEX_Data    : String Array

   // --- Convenience Indices (set during boot) ---
   arrangerDevIdx   : Integer = -1
   controllerDevIdx : Integer = -1
```

- [ ] **Step 2: Remove old hardware-specific variables**

Remove these lines from wherever they currently appear in the Var block:

```
   GENOS_JOY_Y_UP, GENOS_JOY_Y_DN, GENOS_JOY_X_LEFT, GENOS_JOY_X_RIGHT
   ML3_OutDeviceName, ML3_ENC_CC, ML3_BTN_CC_1, ML3_BTN_CC_2
   ML3_SYSEX_PROFIL_1, ML3_SYSEX_PROFIL_5, ML3_SYSEX_PROFIL_6, ML3_SYSEX_PROFIL_7
   TargetSuffix
   MidiOutDeviceName (keep as local in functions that need it, or derive from HAL)
```

Note: `MidiOutDeviceName` is used in many places. Replace references with `GetDeviceMidiOut(arrangerDevIdx)` in Task 10.

- [ ] **Step 3: Verify**

```bash
grep -c "CAP_\|CTYPE_\|FB_\|DEV_\|CTRL_\|SYSEX_" "Global Rackspace V26.gpscript"
# Expected: ~40+ matches (the new HAL variables)
grep "GENOS_JOY\|ML3_SYSEX_PROFIL\|ML3_ENC_CC\|ML3_BTN_CC\|TargetSuffix" "Global Rackspace V26.gpscript"
# Expected: 0 matches in Var block (may still exist in function bodies — those migrate in Task 10)
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(HAL): add device/control/sysex registry variables, remove hardcoded HW constants"
```

---

## Task 5: Write HAL Runtime Functions (Section 14)

**Files:**
- Modify: `Global Rackspace V26.gpscript` (insert new section after Section 13)

- [ ] **Step 1: Insert Section 14 header and all HAL functions**

Insert after the last function of Section 13 (Core Utilities). The full code for all 13 HAL functions:

```
// ============================================================================
// SECTION 14: HARDWARE ABSTRACTION LAYER — RUNTIME
// ============================================================================

// ----------------------------------------------------------------------------
// 14a: Config File Parser
// ----------------------------------------------------------------------------

// Converts a comma-separated capability string to a bitfield integer.
// Example: "TRANSPORT_SYNC,JOYSTICK" → 17
Function ParseCapString(capStr : String) Returns Integer
   var parts : String Array
   var i, caps : Integer
   caps = 0
   parts = SplitString(capStr, ",")
   For i = 0; i < Size(parts); i = i + 1 Do
      Select
         TrimString(parts[i]) == "TRANSPORT_SYNC"      Do caps = caps + CAP_TRANSPORT_SYNC
         TrimString(parts[i]) == "SYSEX_TRIGGER"        Do caps = caps + CAP_SYSEX_TRIGGER
         TrimString(parts[i]) == "CROSSFADER_TARGETS"   Do caps = caps + CAP_CROSSFADER_TARGETS
         TrimString(parts[i]) == "SYSEX_PROFILES"       Do caps = caps + CAP_SYSEX_PROFILES
         TrimString(parts[i]) == "JOYSTICK"             Do caps = caps + CAP_JOYSTICK
         TrimString(parts[i]) == "MIDI_OUT"             Do caps = caps + CAP_MIDI_OUT
         TrimString(parts[i]) == "FEEDBACK_CC"          Do caps = caps + CAP_FEEDBACK_CC
         TrimString(parts[i]) == "SYSEX_COMMANDS"       Do caps = caps + CAP_SYSEX_COMMANDS
      End
   End
   result = caps
End

// Converts a control type string to its integer constant.
Function ParseControlType(typeStr : String) Returns Integer
   result = CTYPE_FADER
   Select
      typeStr == "FADER"    Do result = CTYPE_FADER
      typeStr == "ENCODER"  Do result = CTYPE_ENCODER
      typeStr == "BUTTON"   Do result = CTYPE_BUTTON
      typeStr == "JOYSTICK" Do result = CTYPE_JOYSTICK
      typeStr == "PAD"      Do result = CTYPE_PAD
   End
End

// Converts a feedback method string to its integer constant.
Function ParseFeedbackType(fbStr : String) Returns Integer
   result = FB_NONE
   Select
      fbStr == "NONE"  Do result = FB_NONE
      fbStr == "CC"    Do result = FB_CC
      fbStr == "SYSEX" Do result = FB_SYSEX
   End
End

// Parses DeviceConfig.txt (INI format) and fills DEV_*, CTRL_*, SYSEX_* registries.
Function ParseDeviceConfig()
   var content, line, key, val, section : String
   var lines : String Array
   var i, eqPos, currentDevIdx, currentCtrlIdx, currentSysExIdx : Integer
   
   if not FileExists(DeviceConfigFilePath) then
      Trace("HAL: No DeviceConfig.txt found at " + DeviceConfigFilePath + ". Running in fallback mode.")
   else
      content = LoadStringFromTextFile(DeviceConfigFilePath)
      lines = SplitString(content, NEW_LINE)
      section = ""
      currentDevIdx = -1
      currentCtrlIdx = -1
      currentSysExIdx = -1
      
      // Initialize dynamic arrays
      CTRL_DevIdx = []; CTRL_Type = []; CTRL_CC = []; CTRL_Channel = []
      CTRL_RangeMin = []; CTRL_RangeMax = []; CTRL_Feedback = []; CTRL_Label = []
      SYSEX_DevIdx = []; SYSEX_Purpose = []; SYSEX_Data = []
      CTRL_Count = 0; SYSEX_Count = 0
      
      For i = 0; i < Size(lines); i = i + 1 Do
         line = TrimString(lines[i])
         
         // Skip empty lines and comments
         if Length(line) == 0 then
            // skip
         elsif GetCharAtIndex(line, 0) == ";" then
            // skip comment
            
         // Section headers
         elsif IndexOfSubstring(line, "[DEVICE:", false) == 0 then
            section = "DEVICE"
            currentDevIdx = StringToInt(CopySubstring(line, 8, 1))
            if currentDevIdx >= 0 and currentDevIdx < MAX_DEVICES then
               DEV_Active[currentDevIdx] = true
            end
            
         elsif IndexOfSubstring(line, "[CONTROL:", false) == 0 then
            section = "CONTROL"
            currentCtrlIdx = CTRL_Count
            CTRL_DevIdx <-- 0; CTRL_Type <-- CTYPE_FADER; CTRL_CC <-- -1
            CTRL_Channel <-- -1; CTRL_RangeMin <-- 0; CTRL_RangeMax <-- 127
            CTRL_Feedback <-- FB_NONE; CTRL_Label <-- ""
            CTRL_Count = CTRL_Count + 1
            
         elsif IndexOfSubstring(line, "[SYSEX:", false) == 0 then
            section = "SYSEX"
            currentSysExIdx = SYSEX_Count
            SYSEX_DevIdx <-- 0; SYSEX_Purpose <-- ""; SYSEX_Data <-- ""
            SYSEX_Count = SYSEX_Count + 1
            
         // Key=Value pairs
         else
            eqPos = IndexOfSubstring(line, "=", false)
            if eqPos > 0 then
               key = TrimString(CopySubstring(line, 0, eqPos))
               val = TrimString(CopySubstring(line, eqPos + 1, Length(line) - eqPos - 1))
               
               if section == "DEVICE" and currentDevIdx >= 0 and currentDevIdx < MAX_DEVICES then
                  Select
                     key == "Name"     Do DEV_Name[currentDevIdx] = val
                     key == "MidiIn"   Do DEV_MidiIn[currentDevIdx] = val
                     key == "MidiOut"  Do DEV_MidiOut[currentDevIdx] = val
                     key == "Channel"  Do DEV_Channel[currentDevIdx] = StringToInt(val)
                     key == "Caps"     Do DEV_Caps[currentDevIdx] = ParseCapString(val)
                  End
                  
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
                  
               elsif section == "SYSEX" and currentSysExIdx >= 0 then
                  Select
                     key == "Device"   Do SYSEX_DevIdx[currentSysExIdx] = StringToInt(val)
                     key == "Purpose"  Do SYSEX_Purpose[currentSysExIdx] = val
                     key == "Data"     Do SYSEX_Data[currentSysExIdx] = val
                  End
               end
            end
         end
      End
      
      Trace("HAL: Loaded " + IntToString(CTRL_Count) + " controls, " + IntToString(SYSEX_Count) + " SysEx commands.")
   end
End

// ----------------------------------------------------------------------------
// 14b: Device Lookup
// ----------------------------------------------------------------------------

Function DeviceHasCap(devIdx : Integer, cap : Integer) Returns Boolean
   if devIdx >= 0 and devIdx < MAX_DEVICES and DEV_Active[devIdx] then
      result = (DEV_Caps[devIdx] And cap) > 0
   end
End

Function GetDeviceIdxByName(name : String) Returns Integer
   var i : Integer
   result = -1
   For i = 0; i < MAX_DEVICES; i = i + 1 Do
      if DEV_Active[i] and DEV_Name[i] == name then result = i end
   End
End

Function GetDeviceMidiOut(devIdx : Integer) Returns String
   result = ""
   if devIdx >= 0 and devIdx < MAX_DEVICES then result = DEV_MidiOut[devIdx] end
End

Function IsDeviceConnected(devIdx : Integer) Returns Boolean
   if devIdx >= 0 and devIdx < MAX_DEVICES and DEV_Active[devIdx] and DEV_MidiOut[devIdx] != "" then
      result = MidiOutDeviceExists(DEV_MidiOut[devIdx])
   end
End

// ----------------------------------------------------------------------------
// 14c: Control Lookup
// ----------------------------------------------------------------------------

// Returns the control registry index for a given device and CC, or -1 if not found.
Function FindControl(devIdx : Integer, cc : Integer) Returns Integer
   var i : Integer
   result = -1
   For i = 0; i < CTRL_Count; i = i + 1 Do
      if CTRL_DevIdx[i] == devIdx and CTRL_CC[i] == cc then result = i end
   End
End

Function GetControlType(ctrlIdx : Integer) Returns Integer
   result = -1
   if ctrlIdx >= 0 and ctrlIdx < CTRL_Count then result = CTRL_Type[ctrlIdx] end
End

Function GetControlFeedback(ctrlIdx : Integer) Returns Integer
   result = FB_NONE
   if ctrlIdx >= 0 and ctrlIdx < CTRL_Count then result = CTRL_Feedback[ctrlIdx] end
End

// ----------------------------------------------------------------------------
// 14d: SysEx Lookup & Send
// ----------------------------------------------------------------------------

// Returns the hex string for a device-specific SysEx command, or "" if not found.
Function GetDeviceSysEx(devIdx : Integer, purpose : String) Returns String
   var i : Integer
   result = ""
   For i = 0; i < SYSEX_Count; i = i + 1 Do
      if SYSEX_DevIdx[i] == devIdx and SYSEX_Purpose[i] == purpose then
         result = SYSEX_Data[i]
      end
   End
End

// Sends a registered SysEx command to a device if it is connected.
Function SendDeviceSysEx(devIdx : Integer, purpose : String)
   var data, outDev : String
   if IsDeviceConnected(devIdx) then
      data = GetDeviceSysEx(devIdx, purpose)
      outDev = GetDeviceMidiOut(devIdx)
      if data != "" and outDev != "" then
         SendSysexNowToMidiOutDevice(SM_CreateSysexFromString(data), outDev)
      end
   end
End

// ----------------------------------------------------------------------------
// 14e: Device-to-Block Mapping
// ----------------------------------------------------------------------------

// Maps each active device to its DeviceIn_X MidiInBlock slot.
// Convention: Device N maps to DeviceIn_N (user wires hardware accordingly).
Function MapDevicesToBlocks()
   var i : Integer
   For i = 0; i < MAX_DEVICES; i = i + 1 Do
      DEV_BlockIdx[i] = -1
      if DEV_Active[i] then DEV_BlockIdx[i] = i end
   End
End

// Reverse lookup: returns the device index for a given DeviceIn slot, or -1.
Function GetDeviceIdxForBlock(blockIdx : Integer) Returns Integer
   result = -1
   if blockIdx >= 0 and blockIdx < MAX_DEVICES and DEV_Active[blockIdx] then
      result = blockIdx
   end
End
```

- [ ] **Step 2: Verify HAL function count**

```bash
grep -c "^Function " "Global Rackspace V26.gpscript" | head -1
# Expected: original count (~180) + 16 new HAL functions = ~196
grep "^Function Parse\|^Function Device\|^Function Get\(Device\|Control\)\|^Function IsDevice\|^Function Find\|^Function Send\|^Function Map" "Global Rackspace V26.gpscript"
# Should show all 16 new HAL functions
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(HAL): implement config parser and device/control/sysex lookup functions"
```

---

## Task 6: Reorganize Functions into Thematic Sections (13–23)

**Files:**
- Modify: `Global Rackspace V26.gpscript` (function body, lines ~500–10789)

This is the largest task. Each function must be moved to its assigned section while maintaining declare-before-use order. Within each section, leaf functions come first.

- [ ] **Step 1: Insert section headers**

Add these section headers at the appropriate positions (initially as empty markers, functions will be moved between them):

```
// ============================================================================
// SECTION 13: CORE UTILITIES
// ============================================================================
//   13a: Debug & Trace
//   13b: String Utilities
//   13c: Music Theory Helpers
//   13d: File & Path Utilities
//   13e: State Helpers
//   13f: Overlay & Timer Helpers
// ============================================================================

// ============================================================================
// SECTION 14: HARDWARE ABSTRACTION LAYER — RUNTIME
// ============================================================================
// (Already inserted in Task 5)

// ============================================================================
// SECTION 15: MIDI & CHANNEL ENGINE
// ============================================================================

// ============================================================================
// SECTION 16: DISPLAY ENGINE
// ============================================================================

// ============================================================================
// SECTION 17: CONTROLLER MAP ENGINE
// ============================================================================

// ============================================================================
// SECTION 18: LOOPER ENGINE
// ============================================================================

// ============================================================================
// SECTION 19: PROMPTER & TIMELINE ENGINE
// ============================================================================

// ============================================================================
// SECTION 20: VST REPLACER ENGINE
// ============================================================================

// ============================================================================
// SECTION 21: ORCHESTRATION
// ============================================================================

// ============================================================================
// SECTION 22: HARDWARE INPUT PROCESSING
// ============================================================================

// ============================================================================
// SECTION 23: SONG & SNAPSHOT MANAGEMENT
// ============================================================================
```

- [ ] **Step 2: Move functions to Section 13 (Core Utilities)**

Move these functions (in this order) to Section 13:

**13a: Debug & Trace:**
`Wait`, `Trace`, `DebugCrash`, `TraceActiveScope`

**13b: String Utilities:**
`SplitString`, `TrimAndClean`, `JoinStringArray`, `IsDigitsOnly`, `MyToUpper`, `GetSpaces`, `PadInt`, `ExtractTagValue`, `UpdateTagInLine`

**13c: Music Theory Helpers:**
`GetNoteName`, `GetScaleKeyName`, `GetScaleTypeName`, `GetMusicTheoryString`, `GetLuxusLabel`, `GetNoteIndex`, `GetStandardCCName`

**13d: File & Path Utilities:**
`GetSnapshotPath`, `SuperCleanPath`, `GetBodyFromFile`, `GetConfigFromFile`, `HexCharToInt`, `IntToChar`

**13e: State Helpers:**
`ResetState`, `GetFirstActiveScope`, `IsChannelCustom`, `IsChannelFactory`, `IsBlockNameValid`, `ClickWidget`, `GetActiveMapSlot`, `GetPrimaryVSTForChannel`, `IsChannelActiveForLooper`, `GetActiveLooperScope`

**13f: Overlay & Timer Helpers:**
`ShowCtrlOverlay`, `ShowVSTOverlay`, `ShowRecOverlay`, `StartMacroAnimation`, `GetCountInDurationMS`, `SetChannelState`

- [ ] **Step 3: Move functions to Section 15 (MIDI & Channel Engine)**

`GetParamIdxByName`, `IsNPConfigParam`, `CheckBlock`, `CaptureFactoryDefaults`, `ResetChannelToStandard`, `ResetPluginParams`, `ResetMidiInParams`, `ResetFilterParams`, `ArePluginParamsEqual`, `AreMidiParamsEqual`, `CopyPluginParams`, `CopyMidiParams`, `InjectKBSplitToggle`, `InjectFilterToggle`, `InjectTranspose`, `InjectUserMuteToggle`, `InjectNPToggle`, `InjectNPStep`, `HandleInjectBypassClick`, `Trigger_NotesOff`, `SyncKBSplitWatchdog`

- [ ] **Step 4: Move functions to Section 16 (Display Engine)**

`UpdateSubbarLEDs`, `RefreshDiagDisplay`, `ScrollToCurrentChannel`, `RefreshVstInfoDisplay`, `RefreshSafeReplacerUI`, `UpdateInjectionSplitDisplay`, `UpdateInjectionFadeDisplay`, `UpdateInjectionFilterDisplay`, `UpdateInjectionNPDisplay`, `UpdateInjectionTransposeDisplay`, `UpdateVstInfoDisplay`, `UpdateUsageLabelDisplay`, `UpdateScopeVelocityMeter`, `UpdateInjectionSoloDisplay`, `UpdateInjectionMuteDisplay`, `UpdateInjectionLooperTransportUI`, `UpdateInjectionLooperDisplay`, `RefreshAllInjectionDisplays`, `UpdateMetaColors`, `SyncInputFeedback`, `TraceForensicChannelDump`, `TraceHardwarePrediction`, `UpdateSyncLabel`, `UpdateMidiConfigLabel`, `UpdateCFConfigLabel`, `UpdateMasterLabels`

- [ ] **Step 5: Move functions to Section 17 (Controller Map Engine)**

`GetHardwareLabel`, `GetAssignedHWString`, `GetLinkNameHelper`, `ScrollToCurrentCtrlScope`, `RefreshCtrlInfoDisplay`, `UpdateControllerInfoDisplay`, `UpdateEditScopeDisplay`, `CycleEditScope`, `AppendLinkEncoded`, `CaptureRechBaseline`, `ExecuteLink`, `TriggerMacroFeedback`, `SaveHardwareMap`, `LoadHardwareMap`, `AssignHardware`, `UnlearnHardware`, `ApplyEditorTest`, `ProcessMidiLearn`, `MorphSend`, `CaptureSmartRanges`, `ExportSmartConfig`, `RefreshCtrlMapList`, `LoadControllerMap`, `EvaluateSmartAdapt`, `CycleCtrlMap`, `SyncArrangerToCurrentMap` (renamed from `SyncGenosToCurrentMap`), `AutoSwitchMapOnBypass`, `PreviewActiveControllerMaps`

- [ ] **Step 6: Move functions to Section 18 (Looper Engine)**

`GetLoopActionName`, `GetLoopLengthName`, `GetLoopOutName`, `GetLoopStopName`, `GetLoopModeName`, `GetLoopProgressString`, `GetLooperEventCount`, `RefreshLooperInfoDisplay`, `RefreshLooperConfigDisplay`, `BuildLooperConfigLines`, `TraceLooperDiagnostic`, `ClearLooperArrays`, `ValidateLooperScopeConfig`, `CycleLoopLength`, `CycleLoopAction`, `CycleLoopTarget`, `CycleLoopOutMode`, `CycleLoopStopMode`, `RecordLoopEvent`, `InjectLooperEvent`, `ProcessLooperPlayback`, `FeedLooper_Note`, `FeedLooper_CC`, `TriggerFocusLooperTransport`, `CloseLooperBuffer`

- [ ] **Step 7: Move functions to Section 19 (Prompter & Timeline Engine)**

`GetChordProFile`, `CalculateEffectiveTranspose`, `TransposeNote`, `TransposeChordContent`, `TransposeLine`, `IsHeaderLine`, `IsChordLine`, `IsTabLine`, `IsJunkLine`, `HasRealLyrics`, `RemoveInlineComments`, `CleanChordName`, `WeaveChords`, `GetEffectiveLength`, `GetSmartWrapIndex`, `FlushSection`, `AutoTagSections`, `WashClipboardText`, `BuildZebraBlocks`, `RecordTimelineEvent`, `RecalculateTextDisplay`, `UpdatePrompter`, `TriggerNextSongPart`, `TriggerStyleAction`, `BuildRecDisplayLines`, `RefreshRecDisplay`, `ScrollToCurrentTimelineEvent`, `ExecuteScrub`, `TriggerSongTextLoad`, `DecodeSysExName` (renamed to `DecodeDeviceSysExName`), `SanitizeAndSlugify`, `LoadMappingFile`, `AppendToMappingFile`, `AddNewMapping`, `GetDynamicStandardMap`, `ValidateMapping`, `FireArrangerTransportEcho` (renamed), `EvaluateTransportSync`, `FireDirectArrangerTransport` (renamed), `TraceTimeDomains`

- [ ] **Step 8: Move functions to Section 20 (VST Replacer Engine)**

`ParkFadersForVST`, `RestoreFadersForVST`, `ResetHardwareFadersForVST`, `ScrollToCurrentVST`, `SafeLoadPreset`, `GetStoredPreset`, `CyclePluginPreset`, `GetPathForVst`, `BuildFilteredVstList`, `SyncBrowserToLoadedPlugin`, `FocusBrowserOnCurrentSlot`, `RebuildBrowserStateAfterReboot`, `SmartLoadPresetAfterReplace`, `AddJobToQueue`, `ContinueActualReplace`, `FireActualReplace`, `TriggerNextQueueJob`, `ExecuteVSTReplace`, `SendProgramChangeToVst`, `TriggerVstPresetChange`, `LoadVstDatabase`, `RefreshVstArray`

- [ ] **Step 9: Move functions to Section 21 (Orchestration)**

`AnalyzeChannel`, `ExecuteSmartBypass`, `ApplyVstFocusBypass`, `UpdateSoloMuteState`, `ApplyCrossfade`, `SyncRechUI`, `SyncMatrixToScriptlet`, `CycleChannelScope`, `CycleChannelUsage`, `CycleScopeSection`, `CycleRechPresets`, `CycleGlobalSystemMode`, `CycleSyncMode`, `SetDefaultChannelScope`, `SyncChannelScopeToVst`, `EvaluateAutoSysMode`, `ChangeVstScope`, `DeactivateChannel`, `ScanGlobalInstruments`, `GetSysexString`, `UpdateChannelFade`

- [ ] **Step 10: Move functions to Section 22 (Hardware Input Processing)**

`ExecuteHardwareMacro`, `ProcessHardwareCC`, `ProcessHardwareNote`, `ProcessSystemNavigation`

- [ ] **Step 11: Move functions to Section 23 (Song & Snapshot Management)**

`CleanAndNormalizeRAM`, `AnalyzeStructure`, `ResetData`, `JumpToRegMemAnchor`, `CheckRegMemAutopilot`, `FinishRecording`, `ParseSongData`, `CreateSkeletonFile`, `LoadSongText`, `SaveSongSnapshot`, `LoadSongTimeline`, `LoadSongSnapshot`, `SwitchToSongByName_Safe`, `SaveStructureFromClipboard`, `ProcessTopQueueJobResult`, `PerformSystemReset`

- [ ] **Step 12: Verify no functions are orphaned or duplicated**

```bash
# Count all Function declarations — should match original + 16 new HAL functions
grep -c "^Function " "Global Rackspace V26.gpscript"

# Verify section ordering: each section header should appear in ascending order
grep -n "SECTION [0-9]" "Global Rackspace V26.gpscript"

# Spot-check: Section 22 functions should appear AFTER Section 21 functions
grep -n "^Function ExecuteHardwareMacro\|^Function ProcessHardwareCC\|^Function ChangeVstScope\|^Function UpdateSoloMuteState" "Global Rackspace V26.gpscript"
```

- [ ] **Step 13: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "refactor: reorganize all functions into thematic sections 13-23"
```

---

## Task 7: Rename Functions and Variables (Hardware Neutralization)

**Files:**
- Modify: `Global Rackspace V26.gpscript`

- [ ] **Step 1: Rename functions (global search-and-replace)**

Apply these renames across the entire file (function definitions AND all call sites):

| Search | Replace |
|---|---|
| `SyncGenosToCurrentMap` | `SyncArrangerToCurrentMap` |
| `FireGenosTransportEcho` | `FireArrangerTransportEcho` |
| `FireDirectGenosTransport` | `FireDirectArrangerTransport` |
| `DecodeSysExName` | `DecodeDeviceSysExName` |

- [ ] **Step 2: Rename variables (global search-and-replace)**

| Search | Replace |
|---|---|
| `IncomingFromGenos` | `IncomingFromArranger` |
| `W_CF_Genos` | `W_CF_Arranger` |
| `DEF_CF_Genos` | `DEF_CF_Arranger` |

- [ ] **Step 3: Rename block references in code**

| Search | Replace |
|---|---|
| `From MainMidiIn` | `From DeviceIn_0` |
| `From MiniLab3` | `From DeviceIn_1` |
| `Genos2_Control` (in code, not Var) | `ExternalArranger` |
| `BLK_GenosStyle` (in code, not Var) | `BLK_ArrangerSync` |

- [ ] **Step 4: Remove IsGenos flag usage**

Replace all occurrences of `IsGenos` condition checks with `arrangerDevIdx >= 0`:

| Pattern | Replacement |
|---|---|
| `if IsGenos then` | `if arrangerDevIdx >= 0 then` |
| `if not IsGenos then` | `if arrangerDevIdx < 0 then` |
| `IsGenos = true` | (remove — set by HAL boot) |
| `IsGenos = false` | (remove) |

- [ ] **Step 5: Verify no old names remain**

```bash
grep -c "SyncGenosToCurrentMap\|FireGenosTransportEcho\|FireDirectGenosTransport\|DecodeSysExName[^V]" "Global Rackspace V26.gpscript"
# Expected: 0
grep -c "IncomingFromGenos\|W_CF_Genos\|DEF_CF_Genos\|IsGenos[^L]" "Global Rackspace V26.gpscript"
# Expected: 0
grep -c "From MainMidiIn\|From MiniLab3" "Global Rackspace V26.gpscript"
# Expected: 0
```

- [ ] **Step 6: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "refactor: rename all Genos/MiniLab references to hardware-neutral names"
```

---

## Task 8: Replace Hardware-Specific Logic with HAL Calls

**Files:**
- Modify: `Global Rackspace V26.gpscript`

This task replaces hardcoded device checks and SysEx sends with HAL function calls.

- [ ] **Step 1: Replace MidiOutDeviceName usage**

Every occurrence of `MidiOutDeviceName` as a function argument becomes `GetDeviceMidiOut(arrangerDevIdx)`. Example:

Before:
```
SendNowToMidiOutDevice(msg, MidiOutDeviceName)
```
After:
```
if arrangerDevIdx >= 0 then
   SendNowToMidiOutDevice(msg, GetDeviceMidiOut(arrangerDevIdx))
end
```

- [ ] **Step 2: Replace ML3 SysEx sends**

Before:
```
SendSysexNowToMidiOutDevice(SM_CreateSysexFromString(ML3_SYSEX_PROFIL_5), ML3_OutDeviceName)
```
After:
```
SendDeviceSysEx(controllerDevIdx, "PROFILE_5")
```

- [ ] **Step 3: Replace ML3 CC checks**

Before:
```
if GetCCNumber(c) == ML3_ENC_CC then ...
```
After:
```
var ctrlIdx : Integer = FindControl(devIdx, GetCCNumber(c))
if ctrlIdx >= 0 and GetControlType(ctrlIdx) == CTYPE_ENCODER then ...
```

- [ ] **Step 4: Replace Genos joystick threshold checks**

Before:
```
if GetCCValue(c) > GENOS_JOY_Y_UP then ...
```
After — use control registry range values:
```
var ctrlIdx : Integer = FindControl(devIdx, 1) // CC1 = Joystick Y
if ctrlIdx >= 0 then
   // Joystick threshold logic using CTRL_RangeMax[ctrlIdx]
end
```

- [ ] **Step 5: Wrap transport sync in capability guards**

Before:
```
FireArrangerTransportEcho()
```
After:
```
if arrangerDevIdx >= 0 and DeviceHasCap(arrangerDevIdx, CAP_TRANSPORT_SYNC) then
   FireArrangerTransportEcho()
end
```

- [ ] **Step 6: Wrap crossfader logic in capability guards**

Before:
```
// Apply crossfade to Genos channels
For i = 0; i < 16; i = i + 1 Do ...
```
After:
```
if arrangerDevIdx >= 0 and DeviceHasCap(arrangerDevIdx, CAP_CROSSFADER_TARGETS) then
   // Apply crossfade to arranger channels
   For i = 0; i < 16; i = i + 1 Do ...
end
```

- [ ] **Step 7: Add devIdx parameter to ProcessHardwareCC and ProcessHardwareNote**

Change signatures:
```
Function ProcessHardwareCC(devIdx : Integer, m : ControlChangeMessage)
Function ProcessHardwareNote(devIdx : Integer, m : NoteMessage)
```

Update all call sites in callbacks to pass the device index:
```
On ControlChangeEvent(c : ControlChangeMessage) From DeviceIn_0
   ProcessHardwareCC(0, c)
End
On ControlChangeEvent(c : ControlChangeMessage) From DeviceIn_1
   ProcessHardwareCC(1, c)
End
```

- [ ] **Step 8: Verify no hardcoded hardware constants remain in function bodies**

```bash
grep -n "ML3_\|GENOS_JOY\|ML3_OutDeviceName\|MidiOutDeviceName" "Global Rackspace V26.gpscript"
# Expected: 0 matches
grep -c "DeviceHasCap\|IsDeviceConnected\|GetDeviceMidiOut\|SendDeviceSysEx\|FindControl" "Global Rackspace V26.gpscript"
# Expected: 20+ matches (HAL calls throughout)
```

- [ ] **Step 9: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(HAL): replace all hardcoded hardware logic with capability-based HAL calls"
```

---

## Task 9: Rewrite Initialization (Section 24)

**Files:**
- Modify: `Global Rackspace V26.gpscript` (Initialization block)

- [ ] **Step 1: Rewrite the Initialization block with 7-phase structure**

Replace the existing Initialization (starting at ~line 10790) with the new 7-phase boot. Key changes:

**Phase 0 (SAFETY LOCK):** Keep as-is from V25.

**Phase 1 (PATHS):** Add DeviceConfigFilePath derivation:
```
if IndexOfSubstring(UserSnapshotPath, "\\", false) > -1 Then
    DeviceConfigFilePath = UserSnapshotPath + "\\DeviceConfig.txt"
else
    DeviceConfigFilePath = UserSnapshotPath + "/DeviceConfig.txt"
end
```

**Phase 2 (HAL BOOTSTRAP):** Replace the old device detection loop with:
```
ParseDeviceConfig()
MapDevicesToBlocks()

arrangerDevIdx = -1
controllerDevIdx = -1
var d : Integer
For d = 0; d < MAX_DEVICES; d = d + 1 Do
   if DEV_Active[d] then
      if arrangerDevIdx < 0 and DeviceHasCap(d, CAP_TRANSPORT_SYNC) then arrangerDevIdx = d end
      if controllerDevIdx < 0 and DeviceHasCap(d, CAP_SYSEX_COMMANDS) then controllerDevIdx = d end
      if IsDeviceConnected(d) then
         Trace("HAL: Device " + DEV_Name[d] + " connected via " + DEV_MidiOut[d])
      else
         Trace("HAL: Device " + DEV_Name[d] + " not found. Features disabled.")
      end
   end
End
```

**Phases 3–7:** Keep logic from V25 but use renamed variables (`DEF_CF_Arranger`, `W_CF_Arranger`, etc.) and remove the old `TargetSuffix` / `ML3_OutDeviceName` detection loops entirely.

- [ ] **Step 2: Verify Initialization compiles structurally**

```bash
grep -c "^Initialization" "Global Rackspace V26.gpscript"
# Expected: 1
grep -c "ParseDeviceConfig\|MapDevicesToBlocks\|arrangerDevIdx" "Global Rackspace V26.gpscript"
# Expected: multiple matches (in Init and in function bodies)
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "feat(HAL): rewrite Initialization with 7-phase boot and HAL bootstrap"
```

---

## Task 10: Migrate Callbacks to Generic Device Slots (Sections 25–26)

**Files:**
- Modify: `Global Rackspace V26.gpscript` (callback section)

- [ ] **Step 1: Update MIDI callbacks to use DeviceIn slots**

Replace all `From MainMidiIn` with `From DeviceIn_0` and `From MiniLab3` with `From DeviceIn_1`. Add callbacks for `DeviceIn_2` and `DeviceIn_3`:

```
// --- Device 0 ---
On NoteEvent(m : NoteMessage) From DeviceIn_0
   ProcessHardwareNote(0, m)
End
On ControlChangeEvent(c : ControlChangeMessage) From DeviceIn_0
   ProcessHardwareCC(0, c)
End

// --- Device 1 ---
On NoteEvent(m : NoteMessage) From DeviceIn_1
   ProcessHardwareNote(1, m)
End
On ControlChangeEvent(c : ControlChangeMessage) From DeviceIn_1
   ProcessHardwareCC(1, c)
End

// --- Device 2 (future) ---
On NoteEvent(m : NoteMessage) From DeviceIn_2
   ProcessHardwareNote(2, m)
End
On ControlChangeEvent(c : ControlChangeMessage) From DeviceIn_2
   ProcessHardwareCC(2, c)
End

// --- Device 3 (future) ---
On NoteEvent(m : NoteMessage) From DeviceIn_3
   ProcessHardwareNote(3, m)
End
On ControlChangeEvent(c : ControlChangeMessage) From DeviceIn_3
   ProcessHardwareCC(3, c)
End
```

- [ ] **Step 2: Update SysEx and PitchBend callbacks similarly**

Ensure all MIDI event types route through the generic device slots.

- [ ] **Step 3: Organize Widget callbacks into subsections**

Add subsection headers matching the spec:
```
// SECTION 25: WIDGET CALLBACKS
//   25.1: Song & System Actions
//   25.2: Timeline & Transport
//   25.3: Preset Configuration
//   25.4: Channel Selector
//   25.5: Injection (Matrix & Routing)
//   25.6: Injection (Keyboard, Filter, Notes & Bypass)
//   25.7: Controller Map Configuration
//   25.8: Looper Configuration
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "refactor: migrate all MIDI callbacks to generic DeviceIn slots"
```

---

## Task 11: Absorb Genos2_Control Scriptlet Logic

**Files:**
- Modify: `Global Rackspace V26.gpscript`
- Modify: `Genos2_Control V2.gpscript` (empty out)

The Genos2_Control scriptlet handles:
1. Crossfader → Expression CC11 send to arranger
2. Volume CC7 catch (arranger → GP parameter scaling)
3. Volume CC7 send (GP parameter → arranger)

This logic moves into Section 21 (Orchestration) with HAL guards.

- [ ] **Step 1: Add arranger volume/expression state arrays to Var block**

In Section 6 (Engine State), add:
```
   // --- Arranger Volume Feedback State ---
   Arr_LastSentVol : Integer Array = [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1]
   Arr_LastSentExp : Integer Array = [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1]
   Arr_EchoBlockTimer : Double Array = [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]
   Arr_AsymmetricMode : Boolean = false
```

- [ ] **Step 2: Add arranger feedback functions to Section 21**

```
// Sends a volume CC7 value to the arranger device on the given channel.
// Respects asymmetric scaling mode and echo blocking.
Function SendArrangerVolumeFeedback(val : Double, ch : Integer)
   var midiValToSend : Integer
   var outDev : String
   
   if arrangerDevIdx < 0 or not IsDeviceConnected(arrangerDevIdx) then
      // No arranger connected — skip
   else
      if TimeSinceStartup() < Arr_EchoBlockTimer[ch] then
         // Echo blocked — skip
      else
         outDev = GetDeviceMidiOut(arrangerDevIdx)
         if Arr_AsymmetricMode then
            midiValToSend = Round(val * 100.0)
            if midiValToSend > 100 then midiValToSend = 100 end
         else
            midiValToSend = Round(val * 127.0)
            if midiValToSend > 127 then midiValToSend = 127 end
         end
         if ch >= 1 and ch <= 16 then
            if Arr_LastSentVol[ch] != midiValToSend then
               SendNowToMidiOutDevice(MakeControlChangeMessageEx(7, midiValToSend, ch), outDev)
               Arr_LastSentVol[ch] = midiValToSend
            end
         end
      end
   end
End

// Sends crossfader expression CC11 to arranger channels that have crossfader enabled.
Function SendArrangerCrossfaderExpression(cfVal : Double)
   var i, expVal : Integer
   var outDev : String
   
   if arrangerDevIdx < 0 or not DeviceHasCap(arrangerDevIdx, CAP_CROSSFADER_TARGETS) then
      // No arranger or no crossfader targets — skip
   else
      if not IsDeviceConnected(arrangerDevIdx) then
         // Not connected — skip
      else
         outDev = GetDeviceMidiOut(arrangerDevIdx)
         expVal = Round((cfVal * cfVal) * 127.0)
         For i = 0; i < 16; i = i + 1 Do
            if GetWidgetValue(W_CF_Arranger[i]) > 0.5 then
               if Arr_LastSentExp[i + 1] != expVal then
                  SendNowToMidiOutDevice(MakeControlChangeMessageEx(11, expVal, i + 1), outDev)
                  Arr_LastSentExp[i + 1] = expVal
               end
            end
         End
      end
   end
End
```

- [ ] **Step 3: Handle incoming CC7 in ProcessHardwareCC**

In `ProcessHardwareCC`, add a handler for CC7 from the arranger device:
```
// Arranger volume catch: scale incoming CC7 and update fader parameter
if devIdx == arrangerDevIdx and GetCCNumber(m) == 7 then
   var ch : Integer = GetChannel(m)
   var rawVal : Integer = GetCCValue(m)
   var scaledVal : Double
   if Arr_AsymmetricMode then
      if rawVal >= 100 then scaledVal = 1.0 else scaledVal = IntToFloat(rawVal) / 100.0 end
   else
      scaledVal = IntToFloat(rawVal) / 127.0
   end
   Arr_EchoBlockTimer[ch] = TimeSinceStartup() + 200.0
   Arr_LastSentVol[ch] = rawVal
   // Update the corresponding mixer parameter
   if ch >= 1 and ch <= 16 and (ch - 1) < Size(Mixer_Vol_Params) then
      SetParameter(ExternalArranger, Mixer_Vol_Params[ch - 1], scaledVal)
   end
end
```

- [ ] **Step 4: Empty out the old scriptlet**

Replace `Genos2_Control V2.gpscript` content with:
```
// Genos2_Control — DEPRECATED
// Logic has been absorbed into Global Rackspace V26 (HAL layer).
// This scriptlet can be removed from the wiring once migration is complete.
```

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace V26.gpscript" "Genos2_Control V2.gpscript"
git commit -m "feat(HAL): absorb Genos2_Control scriptlet into Global Rackspace"
```

---

## Task 12: Translate All Comments to English

**Files:**
- Modify: `Global Rackspace V26.gpscript`

- [ ] **Step 1: Translate all German section headers, function comments, and inline comments**

Systematic pass through the entire file. Key patterns to find and translate:

```bash
# Find German comments to translate
grep -n "// .*[äöüÄÖÜß]\|Anpassbar\|Erkennung\|Wert\|Bereich\|Setzt\|Aktuell\|Sicher\|Schalter\|Speicher" "Global Rackspace V26.gpscript"
```

Common translations:
| German | English |
|---|---|
| Anpassbare Werte | Configurable values |
| Separator Erkennung | Separator detection |
| Verhindert String-Overhead | Avoids string allocation overhead |
| Todes-Schleife erkannt | Infinite loop detected |
| NOTBREMSE | Emergency kill switch |
| Wir setzen erst alles auf | Initialize all to |
| Automatisch anhängen | Automatically append |
| Sicherheits-Schalter | Safety switch |
| Reihenfolge frei wählbar | Display order is configurable |

- [ ] **Step 2: Remove humor and emoji from trace messages**

```
"!!! NOTBREMSE: Todes-Schleife erkannt!" → "EMERGENCY: Infinite loop detected."
"🔴 REC OVERDUB ARMED" → "REC OVERDUB ARMED"
"⬛ REC OVERDUB OFF" → "REC OVERDUB OFF"
```

- [ ] **Step 3: Remove dead/commented-out code**

Search for commented-out code blocks and remove them (they exist in git history):
```bash
grep -n "^   //" "Global Rackspace V26.gpscript" | grep -i "legacy\|unused\|old\|hack\|todo\|fixme"
```

- [ ] **Step 4: Verify no German comments remain**

```bash
grep -c "[äöüÄÖÜß]" "Global Rackspace V26.gpscript"
# Expected: 0 (no German special characters in comments)
# Note: String constants with German text in user-facing labels are OK to keep
```

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace V26.gpscript"
git commit -m "docs: translate all comments to English, remove dead code"
```

---

## Task 13: Final Verification

**Files:**
- Read: `Global Rackspace V26.gpscript`

- [ ] **Step 1: Structural verification**

```bash
# Total function count (original ~180 + 16 HAL = ~196)
grep -c "^Function " "Global Rackspace V26.gpscript"

# Section headers present and ordered
grep -n "^// SECTION [0-9]" "Global Rackspace V26.gpscript"

# No remaining Genos/MiniLab hardcoded references
grep -c "Genos\|GENOS\|genos\|MiniLab\|MINILAB\|Minilab\|ML3_" "Global Rackspace V26.gpscript"
# Expected: 0 in code. Some may remain in DeviceConfig.txt references or Trace messages — that is acceptable.

# HAL functions present
grep "^Function.*Device\|^Function.*Control\|^Function.*SysEx\|^Function Parse" "Global Rackspace V26.gpscript"

# Initialization has 7 phases
grep "PHASE [0-7]" "Global Rackspace V26.gpscript"

# All 4 DeviceIn callbacks exist
grep "From DeviceIn_" "Global Rackspace V26.gpscript"
```

- [ ] **Step 2: Dependency order spot-check**

Verify that no function calls a function declared later in the file:

```bash
# Section 14 functions should appear BEFORE Section 15 functions
grep -n "^Function DeviceHasCap\|^Function GetParamIdxByName" "Global Rackspace V26.gpscript"
# DeviceHasCap line number must be < GetParamIdxByName line number

# Section 22 functions should appear AFTER Section 21 functions
grep -n "^Function ProcessHardwareCC\|^Function UpdateSoloMuteState" "Global Rackspace V26.gpscript"
# UpdateSoloMuteState line number must be < ProcessHardwareCC line number
```

- [ ] **Step 3: Line count comparison**

```bash
wc -l "Global Rackspace V25.gpscript" "Global Rackspace V26.gpscript"
# V26 should be similar to V25 (~13190) + ~200 (HAL functions) + ~50 (new headers) - ~100 (removed dead code)
# Expected: ~13300-13500 lines
```

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: complete Global Rackspace V26 — HAL, thematic ordering, hardware-neutral"
```

- [ ] **Step 5: User manual compile test**

**Action for the user:** Open `Global Rackspace V26.gpscript` in the Gig Performer script editor and verify it compiles without errors. Check the log window for HAL boot messages.
