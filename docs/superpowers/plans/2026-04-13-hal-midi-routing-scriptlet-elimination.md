# HAL MIDI Output Routing & Scriptlet Elimination — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate Genos2_Control and Genos2_StyleControl scriptlets, route all MIDI output directly from Global Script with configurable per-stream port routing.

**Architecture:** Extend ParseDeviceConfig to parse Route:* and Trigger:* keys. Replace all SetParameter(ExternalArranger/BLK_ArrangerSync, ...) calls with direct SendNowToMidiOutDevice() using route lookup. Move inbound callbacks to DeviceIn_0 handlers. Delete all dead blocks and constants.

**Tech Stack:** GPScript (no external compiler, no TDD — E2E test in Gig Performer at the end)

**Spec:** `docs/superpowers/specs/2026-04-13-hal-midi-routing-scriptlet-elimination-design.md`

**GPScript Rules — EVERY subagent MUST follow:**
- All `var` at function top, before any executable statement
- Every function must be defined BEFORE its callers (forward declaration)
- `For` and `While` need `Do` ... `End`
- No `Result` — use `result` (lowercase)
- No early return — use if/else
- All Double variables initialized with `= 0.0`
- `block` is reserved — don't use as variable name
- No `\u` or `\n` escapes — use `<<< >>>` heredoc constants
- `Returns`-typed functions: capture return value, can't call as statement
- GREP function/variable names before using — never guess API names
- Bump `SCRIPT_VERSION` on every edit

---

## File Map

| File | Action |
|------|--------|
| `Global Rackspace.gpscript` | Modify: var block, ParseDeviceConfig, outbound functions, inbound callbacks, delete dead code |
| `examples/DeviceConfig.txt` | Already updated (Route:* and Trigger:* added in spec commit) |

---

### Task 1: Add Route + Trigger Data Structures to Var Block

**Files:**
- Modify: `Global Rackspace.gpscript` — Var block (lines 13-927)

**Context:** The var block spans lines 13-927. New constants go near the existing device constants (around line 194). New arrays go near existing DEV_* arrays (around line 198). New state variables go near existing Arr_* variables (around line 505).

- [ ] **Step 1: Add route constants after MAX_DEVICES (line 194)**

Insert after `MAX_DEVICES : Integer = 4`:
```gpscript
   // --- HAL Output Route Types ---
   ROUTE_VOLUME     : Integer = 0  // CC7 per-channel volume feedback
   ROUTE_EXPRESSION : Integer = 1  // CC11 crossfader expression floating
   ROUTE_CONTROL    : Integer = 2  // Generic CCs, style triggers, SysEx
   ROUTE_COUNT      : Integer = 3
```

- [ ] **Step 2: Add route and trigger arrays after DEV_MidiOut (line 198)**

Insert after `DEV_MidiOut : String Array`:
```gpscript
   // --- HAL Output Route Table (flat: devIdx * ROUTE_COUNT + routeType -> port name) ---
   DEV_Route : String Array

   // --- Style Trigger Mapping (from DeviceConfig) ---
   DEV_TriggerNote    : Integer Array  // [triggerIdx] -> MIDI note number
   DEV_TriggerName    : String Array   // [triggerIdx] -> config name (for reverse lookup)
   DEV_TriggerCount   : Integer = 0
   DEV_TriggerChannel : Integer = 16   // 1-based, default Ch16
```

- [ ] **Step 3: Add TRIG_START_STOP constant and echo timer near style variables (around line 468)**

Insert near `StyleTriggerResetTimer`:
```gpscript
   // --- Style Trigger Constants (set by parser, -1 = not configured) ---
   TRIG_START_STOP    : Integer = -1
   StyleEchoBlockTimer : Double = 0.0
```

- [ ] **Step 4: Bump SCRIPT_VERSION (line 36)**

Change to next version string reflecting this edit.

- [ ] **Step 5: Commit**
```
feat(hal): add Route and Trigger data structures for MIDI output routing
```

---

### Task 2: Extend ParseDeviceConfig for Route:* and Trigger:* Keys

**Files:**
- Modify: `Global Rackspace.gpscript` — `ParseDeviceConfig` function (starts ~line 1623)

**Context:** The parser reads key=val pairs. Within the `section == "DEVICE"` block, there's a Select statement (around line 1716) handling Name, MidiIn, MidiOut, Channel, Caps. We need to add Route:* and Trigger:* parsing here.

**IMPORTANT:** The Select/Do pattern in GPScript cannot have multi-line blocks. Use if/elsif chains instead for the new parsing.

- [ ] **Step 1: Initialize DEV_Route array in the initialization section before parsing starts**

Find the section where DEV_* arrays are initialized (before the parse loop). Add:
```gpscript
   // Initialize route table: all empty (will fallback to MidiOut after parse)
   For i = 0; i < MAX_DEVICES * ROUTE_COUNT; i = i + 1 Do
      DEV_Route <-- ""
   End
   DEV_TriggerCount = 0
```

- [ ] **Step 2: Add Route: and Trigger: parsing inside the DEVICE section handler**

After the existing Select block for Name/MidiIn/MidiOut/Channel/Caps, add if/elsif logic:

```gpscript
   // --- Route parsing ---
   if CopySubstring(key, 0, 6) == "Route:" then
      var routeStream : String = CopySubstring(key, 6, Length(key) - 6)
      var routeIdx : Integer = -1
      if routeStream == "Volume" then routeIdx = ROUTE_VOLUME
      elsif routeStream == "Expression" then routeIdx = ROUTE_EXPRESSION
      elsif routeStream == "Control" then routeIdx = ROUTE_CONTROL
      end
      if routeIdx >= 0 then
         DEV_Route[currentDevIdx * ROUTE_COUNT + routeIdx] = val
      end
   end

   // --- Trigger parsing ---
   if key == "TriggerChannel" then
      DEV_TriggerChannel = StringToInt(val)
   elsif CopySubstring(key, 0, 8) == "Trigger:" then
      var trigName : String = CopySubstring(key, 8, Length(key) - 8)
      DEV_TriggerNote <-- StringToInt(val)
      DEV_TriggerName <-- trigName
      // Map known constants
      if trigName == "StartStop" then TRIG_START_STOP = DEV_TriggerCount end
      DEV_TriggerCount = DEV_TriggerCount + 1
   end
```

**IMPORTANT:** The `var` declarations for `routeStream`, `routeIdx`, `trigName` MUST be at the top of the enclosing function, NOT inline. Move them to the var block at the top of ParseDeviceConfig.

- [ ] **Step 3: Add fallback initialization after parsing completes**

After the parsing loop ends, before the function returns:
```gpscript
   // Fallback: any empty route falls back to MidiOut
   For d = 0; d < MAX_DEVICES; d = d + 1 Do
      For r = 0; r < ROUTE_COUNT; r = r + 1 Do
         if DEV_Route[d * ROUTE_COUNT + r] == "" then
            DEV_Route[d * ROUTE_COUNT + r] = DEV_MidiOut[d]
         end
      End
   End
```

- [ ] **Step 4: Bump SCRIPT_VERSION**

- [ ] **Step 5: Commit**
```
feat(hal): parse Route:* and Trigger:* keys in ParseDeviceConfig
```

---

### Task 3: Add Lookup Functions + Boot Trace

**Files:**
- Modify: `Global Rackspace.gpscript` — after existing HAL helper functions (GetDeviceMidiOut at line ~1889)

**Context:** These functions must be defined AFTER the arrays they read but BEFORE any function that calls them. Place them right after `GetDeviceMidiOut` / `IsDeviceConnected` / `DeviceHasCap` (around line 1900).

- [ ] **Step 1: Add GetDeviceRoute function**

```gpscript
Function GetDeviceRoute(devIdx : Integer, routeType : Integer) Returns String
   var idx : Integer = devIdx * ROUTE_COUNT + routeType
   if devIdx >= 0 and devIdx < MAX_DEVICES and routeType >= 0 and routeType < ROUTE_COUNT then
      result = DEV_Route[idx]
   end
End
```

- [ ] **Step 2: Add FindTriggerIdxByNote function**

```gpscript
Function FindTriggerIdxByNote(note : Integer) Returns Integer
   var i : Integer
   result = -1
   For i = 0; i < DEV_TriggerCount; i = i + 1 Do
      if DEV_TriggerNote[i] == note then
         result = i
      end
   End
End
```

- [ ] **Step 3: Add boot trace in initialization section (around line 13837)**

After the existing device connection trace, add:
```gpscript
   // Trace parsed routes
   if arrangerDevIdx >= 0 then
      Trace("HAL: Route Volume="    + GetDeviceRoute(arrangerDevIdx, ROUTE_VOLUME))
      Trace("HAL: Route Expression=" + GetDeviceRoute(arrangerDevIdx, ROUTE_EXPRESSION))
      Trace("HAL: Route Control="   + GetDeviceRoute(arrangerDevIdx, ROUTE_CONTROL))
      Trace("HAL: " + IntToString(DEV_TriggerCount) + " style triggers loaded, channel=" + IntToString(DEV_TriggerChannel))
   end
```

- [ ] **Step 4: Bump SCRIPT_VERSION**

- [ ] **Step 5: Commit**
```
feat(hal): add GetDeviceRoute, FindTriggerIdxByNote, boot route trace
```

---

### Task 4: Rewrite Outbound Send Functions

**Files:**
- Modify: `Global Rackspace.gpscript` — functions SendArrangerVolumeFeedback (~line 11221), SendArrangerCrossfaderExpression (~line 11250), TriggerStyleAction (~line 5774), ApplyCrossfade (~line 10174)

**Context:** These functions already exist. The only change is replacing `GetDeviceMidiOut(arrangerDevIdx)` with `GetDeviceRoute(arrangerDevIdx, ROUTE_*)` and rewriting TriggerStyleAction to use direct note pulses instead of SetParameter.

- [ ] **Step 1: Fix SendArrangerVolumeFeedback (line ~11221)**

Replace:
```gpscript
         outDev = GetDeviceMidiOut(arrangerDevIdx)
```
With:
```gpscript
         outDev = GetDeviceRoute(arrangerDevIdx, ROUTE_VOLUME)
```

- [ ] **Step 2: Fix SendArrangerCrossfaderExpression (line ~11250)**

Replace:
```gpscript
         outDev = GetDeviceMidiOut(arrangerDevIdx)
```
With:
```gpscript
         outDev = GetDeviceRoute(arrangerDevIdx, ROUTE_EXPRESSION)
```

- [ ] **Step 3: Rewrite TriggerStyleAction (line ~5774)**

Replace entire function body:
```gpscript
Function TriggerStyleAction(styleId : Integer)
   var route : String
   var note, ch : Integer

   if styleId < 0 or styleId >= DEV_TriggerCount then
      if DebugMode then Trace("STYLE ERROR: Invalid trigger ID (" + IntToString(styleId) + ") ignored! Max is " + IntToString(DEV_TriggerCount - 1)) end
   else
      if arrangerDevIdx < 0 or not IsDeviceConnected(arrangerDevIdx) then
         if DebugMode then Trace("STYLE: No arranger connected, trigger ignored") end
      else
         route = GetDeviceRoute(arrangerDevIdx, ROUTE_CONTROL)
         note = DEV_TriggerNote[styleId]
         ch = DEV_TriggerChannel
         if DebugMode then Trace("STYLE: Triggering " + DEV_TriggerName[styleId] + " (Note " + IntToString(note) + " Ch" + IntToString(ch) + ")") end
         SendNowToMidiOutDevice(route, MakeNoteMessageEx(note, 127, ch))
         SendLaterToMidiOutDevice(route, MakeNoteMessageEx(note, 0, ch), 50)
         StyleEchoBlockTimer = TimeSinceStartup() + 500.0
      end
   end
End
```

**IMPORTANT:** Verify that `SendLaterToMidiOutDevice` exists in GPScript by grepping. If not, use the `Wait(50.0)` + `SendNowToMidiOutDevice` pattern from the original.

- [ ] **Step 4: Fix ApplyCrossfade (line ~10174)**

Remove these three lines at the end of ApplyCrossfade:
```gpscript
   ScriptWrite_ExpectedPrev[P_ARRANGER_CROSSFADER] = ScriptWrite_Expected[P_ARRANGER_CROSSFADER]
   ScriptWrite_Expected[P_ARRANGER_CROSSFADER] = x_val
   SetParameter(ExternalArranger, P_ARRANGER_CROSSFADER, x_val)
```

Replace with:
```gpscript
   SendArrangerCrossfaderExpression(x_val)
```

- [ ] **Step 5: Bump SCRIPT_VERSION**

- [ ] **Step 6: Commit**
```
feat(hal): route Volume/Expression/Control through configurable output ports
```

---

### Task 5: Replace All SetParameter(BLK_ArrangerSync, ...) Calls

**Files:**
- Modify: `Global Rackspace.gpscript` — multiple call sites

**Context:** All `SetParameter(BLK_ArrangerSync, P_STYLE_START_STOP, 1.0)` calls fire a transport toggle on the arranger. Replace with `TriggerStyleAction(TRIG_START_STOP)`. All other BLK_ArrangerSync writes (inside TriggerStyleAction itself) are already handled by Task 4.

**IMPORTANT:** Search for ALL occurrences: `grep "SetParameter(BLK_ArrangerSync"` and handle every one. Known call sites from analysis:

- [ ] **Step 1: Replace transport toggle calls**

At each of these locations, replace `SetParameter(BLK_ArrangerSync, P_STYLE_START_STOP, 1.0)` with `TriggerStyleAction(TRIG_START_STOP)`:

- Line ~8275 (transport echo in sync logic)
- Line ~8304 (FireArrangerTransportEcho function body)
- Line ~13642, 13649, 13659, 13679 (system action contexts)
- Line ~15652 (inside the BLK_ArrangerSync callback — this callback will be deleted in Task 7, but update it now for consistency)
- Line ~16788 (system mode control)
- Line ~17067 (transport stop)
- Line ~17184 (generic style trigger)

Also remove the `StyleTriggerResetTimer = TimeSinceStartup() + 60.0` lines that follow each call — the echo blocking is now handled inside TriggerStyleAction via StyleEchoBlockTimer.

- [ ] **Step 2: Simplify FireArrangerTransportEcho (line ~8303)**

The entire function body becomes:
```gpscript
Function FireArrangerTransportEcho()
   TriggerStyleAction(TRIG_START_STOP)
End
```

- [ ] **Step 3: Grep to verify no SetParameter(BLK_ArrangerSync, ...) calls remain**

- [ ] **Step 4: Bump SCRIPT_VERSION**

- [ ] **Step 5: Commit**
```
refactor(hal): replace all BLK_ArrangerSync SetParameter calls with TriggerStyleAction
```

---

### Task 6: Replace All SetParameter(ExternalArranger, ...) Calls

**Files:**
- Modify: `Global Rackspace.gpscript` — multiple call sites (~19 locations)

**Context:** The ExternalArranger scriptlet has parameters:
- Params 0-15: Genos_Vol_Ch01..16 → send CC7 on channels 1-16
- Params 16-31: CF_Enable_Ch01..16 → internal flags (no MIDI output needed)
- Param 32 (P_ARRANGER_CROSSFADER): Crossfader → send CC11 (already handled in Task 4)

**Strategy for each call site:**
- `SetParameter(ExternalArranger, idx, val)` where idx < 16 → `SendArrangerVolumeFeedback(val, idx + 1)` (idx is 0-based, channel is 1-based)
- `SetParameter(ExternalArranger, P_ARRANGER_FLAGS_START + j, val)` where it writes CF flags → DELETE (W_CF_Arranger widgets are source of truth)
- `SetParameter(ExternalArranger, P_ARRANGER_CROSSFADER, val)` → already replaced in Task 4

- [ ] **Step 1: Grep all SetParameter(ExternalArranger, ...) calls**

Search and categorize each by parameter index.

- [ ] **Step 2: Replace volume writes (param 0-15)**

For each `SetParameter(ExternalArranger, macroOrChannelIdx, val)` that writes to indices 0-15:
- Replace with `SendArrangerVolumeFeedback(val, channelIdx + 1)`
- Pay attention to whether the index is a macroIdx or a channel index — check surrounding context

- [ ] **Step 3: Delete CF flag writes (params 16-31)**

For each `SetParameter(ExternalArranger, P_ARRANGER_FLAGS_START + j, ...)`:
- Delete the line — W_CF_Arranger widgets already hold this state
- Check if any surrounding logic depends on the write completing

- [ ] **Step 4: Verify P_ARRANGER_CROSSFADER writes are already handled**

The ApplyCrossfade change in Task 4 should cover these. Grep to confirm no others remain.

- [ ] **Step 5: Handle ScriptWrite_Expected/Prev references**

Any `ScriptWrite_Expected[P_ARRANGER_*]` or `ScriptWrite_ExpectedPrev[P_ARRANGER_*]` lines that referenced ExternalArranger echo dedup: DELETE them. The echo dedup moves into SendArrangerVolumeFeedback (Arr_LastSentVol) and SendArrangerCrossfaderExpression (Arr_LastSentExp).

- [ ] **Step 6: Grep to verify no SetParameter(ExternalArranger, ...) calls remain**

- [ ] **Step 7: Bump SCRIPT_VERSION**

- [ ] **Step 8: Commit**
```
refactor(hal): replace all ExternalArranger SetParameter calls with direct MIDI sends
```

---

### Task 7: Migrate Inbound Callbacks

**Files:**
- Modify: `Global Rackspace.gpscript` — callbacks section (~line 15498+)

**Context:** Two callbacks must be eliminated:
1. `On ParameterValueChanged from BLK_ArrangerSync` (line ~15637) — style feedback
2. `On ParameterValueChanged from ExternalArranger` (line ~15498) — arranger fader input

Their logic must move to the existing DeviceIn_0 callbacks.

#### Part A: BLK_ArrangerSync Callback → DeviceIn_0

The callback (line 15637-15682) handles:
- paramIdx 29 (P_STYLE_HW_START): Hardware start flag → transport sync
- paramIdx 44 (Flag_HW_Start): Arranger hardware button
- Timeline recording for style part changes

- [ ] **Step A1: Add style trigger detection in On NoteEvent from DeviceIn_0 (line ~15770)**

Add a section that detects incoming notes on `DEV_TriggerChannel` and handles transport sync:

```gpscript
   // --- Style trigger feedback from arranger ---
   if GetChannel(m) == DEV_TriggerChannel and IsNoteOn(m) then
      if TimeSinceStartup() < StyleEchoBlockTimer then
         // Echo blocked — this is our own pulse bouncing back
      else
         var inNote : Integer = GetNoteNumber(m)
         var inTrigIdx : Integer = FindTriggerIdxByNote(inNote)

         // Transport sync: hardware start/stop button
         if inTrigIdx == TRIG_START_STOP then
            LastHardwarePulseTime = TimeSinceStartup()
            if DebugMode then Trace(">>> STYLE-IN: Hardware Start/Stop detected (Note " + IntToString(inNote) + ")") end

            if CurrentSyncMode == 2 and not IsPlayheadEnabled() then
               Trace("   [X] STYLE-IN: Arranger started in isolation! Sending abort echo...")
               TriggerStyleAction(TRIG_START_STOP)
            elsif CurrentSyncMode == 2 or CurrentSyncMode == 3 then
               IsCorrectingPlayhead = false
               EnablePlayhead(not PendingPlayheadState)
            end
         end

         // Timeline recording for style part changes
         if inTrigIdx >= 0 and inTrigIdx != TRIG_START_STOP then
            if RecordMode > 0 or TimelineRecActive then
               RecordTimelineEvent("Style", inTrigIdx)
            end
         end
      end
   end
```

**IMPORTANT:** The `var inNote, inTrigIdx` must go at the TOP of the On NoteEvent callback's var block.

- [ ] **Step A2: Add CC5 detection in On ControlChangeEvent from DeviceIn_0 (line ~15705)**

In the else branch (non-SystemMode), before `ProcessHardwareCC(m)`:
```gpscript
   // Style feedback: CC5 on TriggerChannel = hardware start/stop
   if GetChannel(m) + 1 == DEV_TriggerChannel and GetCCNumber(m) == 5 then
      if TimeSinceStartup() >= StyleEchoBlockTimer then
         LastHardwarePulseTime = TimeSinceStartup()
         if DebugMode then Trace(">>> STYLE-IN: Hardware CC5 detected") end
         if CurrentSyncMode == 2 or CurrentSyncMode == 3 then
            IsCorrectingPlayhead = false
            EnablePlayhead(not PendingPlayheadState)
         end
      end
   end
```

**Note:** `GetChannel()` returns 0-based, `DEV_TriggerChannel` is 1-based.

- [ ] **Step A3: Delete the entire On ParameterValueChanged from BLK_ArrangerSync callback (lines ~15637-15682)**

#### Part B: ExternalArranger Callback → Needs Analysis

The callback (line 15498-15631, ~130 lines) handles:
- Echo deduplication (ScriptWrite_Expected matching)
- HUD feedback for fader movements
- Crossfader widget detection
- Scrubber binding
- Morph slider (SLD_Morph)
- System action dispatch
- Timeline recording
- LFO auto-start gate

**This is the most complex migration.** The incoming fader values from the Genos2 currently flow through the ExternalArranger scriptlet's parameters. After elimination, they'll arrive as CC messages through DeviceIn_0 (if they come via USB) or need a new input path (if they only come via DIN/Babyface).

- [ ] **Step B1: Determine the input path**

Check if the Genos2 volume/fader CCs arrive through DeviceIn_0 (USB) or only through Babyface (DIN). This determines whether we need a new MidiInBlock for Babyface.

If through USB: The logic moves into `On ControlChangeEvent from DeviceIn_0`.
If only through DIN: We need to create a new `DeviceIn_Aux : MidiInBlock` in the var block, wire it to Babyface in GP, and add a new `On ControlChangeEvent from DeviceIn_Aux` callback.

**For this plan, assume USB path (DeviceIn_0).** If E2E test shows volume CCs don't arrive through USB, add a DeviceIn_Aux block.

- [ ] **Step B2: Extract the essential logic from the ExternalArranger callback**

The callback does many things, but most are tied to the ExternalArranger parameter semantics. After elimination:

1. **Echo dedup** → Now handled by Arr_LastSentVol / Arr_LastSentExp in the send functions. Remove.
2. **HUD feedback** → This is the `HudPushArrangerFader(paramIdx, newVal)` call. Needs to be called from ProcessHardwareCC when an arranger fader CC arrives.
3. **Crossfader check** → If incoming CC matches crossfader macro, update SLD_Crossfader. Already handled by ProcessHardwareCC → ExecuteHardwareMacro → CF_MacroIdx check.
4. **Scrubber** → Already handled in ExecuteHardwareMacro SCRUB_MacroIdx check.
5. **Morph slider** → METER write for SLD_Morph. Move into ExecuteHardwareMacro where appropriate.
6. **System actions** → Reverse lookup. Already handled by ProcessHardwareCC path.
7. **Timeline recording** → Already handled in ExecuteHardwareMacro pathway.
8. **LFO auto-start** → Trigger condition. Move into ExecuteHardwareMacro if needed.

**Key insight:** Most of this logic is ALREADY handled by the ProcessHardwareCC → ExecuteHardwareMacro path for the assignable controller CCs. The ExternalArranger callback was a PARALLEL path for the volume faders. After elimination, the volume faders should flow through the same ProcessHardwareCC path.

- [ ] **Step B3: Delete the entire On ParameterValueChanged from ExternalArranger callback (lines ~15498-15631)**

Any logic not covered by ProcessHardwareCC will be caught during E2E testing.

- [ ] **Step B4: Bump SCRIPT_VERSION**

- [ ] **Step B5: Commit**
```
refactor(hal): migrate inbound callbacks from scriptlet blocks to DeviceIn_0
```

---

### Task 8: Fix ExecuteHardwareMacro CC Send + Route Lookup

**Files:**
- Modify: `Global Rackspace.gpscript` — ExecuteHardwareMacro function (~line 11361-11381)

**Context:** The CC send at line ~11380 uses `DEV_MidiOut[0]` hardcoded. Replace with route lookup.

- [ ] **Step 1: Replace hardcoded MIDI out**

Find line ~11380:
```gpscript
       SendNowToMidiOutDevice(DEV_MidiOut[0], MakeControlChangeMessageEx(ccNum, Round(scaledCC * 127.0), ccCh))
```

Replace with:
```gpscript
       SendNowToMidiOutDevice(GetDeviceRoute(arrangerDevIdx, ROUTE_CONTROL), MakeControlChangeMessageEx(ccNum, Round(scaledCC * 127.0), ccCh))
```

- [ ] **Step 2: Check for any other hardcoded DEV_MidiOut[0] references**

Grep for `DEV_MidiOut\[0\]` and fix any remaining occurrences to use appropriate route lookup.

- [ ] **Step 3: Bump SCRIPT_VERSION**

- [ ] **Step 4: Commit**
```
fix(hal): route ExecuteHardwareMacro CC sends through ROUTE_CONTROL
```

---

### Task 9: Delete Dead Code + Block Declarations

**Files:**
- Modify: `Global Rackspace.gpscript` — var block and throughout

**Context:** With all call sites migrated, remove the now-unused declarations.

- [ ] **Step 1: Delete block declarations from var block**

Remove these lines:
```gpscript
   ExternalArranger : PluginBlock       // line ~263
   BLK_ArrangerSync : PluginBlock       // line ~265
```

- [ ] **Step 2: Delete parameter constants from var block**

Remove:
```gpscript
   P_ARRANGER_FLAGS_START : Integer = 16   // line ~498
   P_ARRANGER_CROSSFADER : Integer = 32    // line ~499
   P_STYLE_START_STOP : Integer = 1        // line ~500
   P_STYLE_HW_START : Integer = 29         // line ~501
```

- [ ] **Step 3: Clean up ScriptWrite_Expected references**

Search for any remaining `ScriptWrite_Expected[P_ARRANGER_` or `ScriptWrite_ExpectedPrev[P_ARRANGER_` references. Delete them.

- [ ] **Step 4: Grep for any remaining references to ExternalArranger or BLK_ArrangerSync**

Fix or delete any remaining references. If a reference is in a comment, delete the comment.

- [ ] **Step 5: Verify compile-readiness**

- Do a final grep for `ExternalArranger` — should return 0 results
- Do a final grep for `BLK_ArrangerSync` — should return 0 results
- Do a final grep for `P_ARRANGER_` — should return 0 results
- Do a final grep for `P_STYLE_` — should return 0 results

- [ ] **Step 6: Bump SCRIPT_VERSION to final version**

- [ ] **Step 7: Commit**
```
refactor(hal): delete ExternalArranger, BLK_ArrangerSync and all dead constants
```

---

## Post-Implementation: Manual Steps in Gig Performer

These cannot be automated — the user must do them in the GP GUI:

1. Open Global Rackspace wiring view
2. Delete block: `ExternalArranger` (scriptlet)
3. Delete block: `BLK_ArrangerSync` (scriptlet)
4. Delete block: `MidiOutGn2P1` (MIDI Out)
5. Delete block: MIDI Out connected to `Babyface Midi Port 1` (if dedicated volume output block)
6. Save the gig file
7. Reload and check script console for `SCRIPT VERSION <version> booting`

## E2E Test Plan

1. **Boot verification:** Console shows parsed routes + trigger count
2. **Volume routing:** Move a volume-bound fader → CC7 arrives at Genos2 via Babyface DIN
3. **Expression routing:** Move crossfader → CC11 arrives at Genos2 via Digital Keyboard-1
4. **Control routing:** Move a CC-bound encoder → CC arrives at Genos2
5. **Style triggers:** Fire a style action → note pulse on Ch16 reaches Genos2
6. **Echo blocking:** Start style from Genos2 hardware → no feedback loop
7. **Transport sync:** Test all SyncModes (1-5) with hardware start/stop
8. **Timeline:** Record a style trigger → verify RecordTimelineEvent fires
9. **Port test:** Change `Route:Volume=Digital Keyboard-2` → verify if port works
