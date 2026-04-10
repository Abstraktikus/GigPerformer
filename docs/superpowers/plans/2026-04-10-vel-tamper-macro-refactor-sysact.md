# Vel Tamper, Macro Space Refactor, and System Action Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three coordinated changes: (A) velocity range edge-fade tamper parallel to the existing OctRangeFade; (B) macro space renumbering (user 1–50, groups 51+), `MAX_MACROS` bump to 256, ControllerInfo display-loop bug fix, and deletion of legacy group-keyword parsing from ControllerMaps; (C) virtual System Action framework with reverse-lookup dispatch, Isolation Rule, and Timeline record exclusion by design.

**Architecture:** Feature A mirrors `GetOctRangeVelocity` with percentage-based padding and a new `p_VelRangeFade` parameter + `BTN_Inject_NP_VelTamper` widget. Feature B renumbers all `DEF_*_MacroIdx` arrays, extends the display scan loop to `MAX_MACROS`, deletes the 10 `LOOPER_CH`/`SMART_SOLO_CH`/etc. parser and save branches — their runtime arrays now live permanently on Init-time defaults. Feature C adds a central `SysAction_Names`/`SysAction_Labels` registry with reverse-lookup arrays `SysAction_ByMacro[MAX_MACROS]` / `SysAction_ByCC[128]`, a `FireSystemAction()` dispatcher, a `SYSACT_` parser branch with the Isolation Rule, and an O(1) `IsSystemActionMacro()` filter that gates Timeline macro recording.

**Tech Stack:** GPScript (Gig Performer 5.x)

**Spec:** `docs/superpowers/specs/2026-04-10-vel-tamper-macro-refactor-sysact-design.md`

---

## Sequencing Rationale

Tasks are ordered so each commit leaves the codebase in a **compilable, runnable state**. Because Feature A is purely additive and stands alone, it goes first (Tasks 1–6). Feature B's renumbering touches many call sites but is a mechanical substitution — doing it before Feature C keeps Feature C's line-number references stable (Tasks 7–14). Feature C is the biggest conceptual change and goes last (Tasks 15–22).

---

## FEATURE A — Velocity Range Tamper

### Task 1: Add Scriptlet Parameter and Tamper Pad Constant

**Files:**
- Modify: `Note Prozessor.gpscript:60` (add `p_VelRangeFade`)
- Modify: `Note Prozessor.gpscript:65` (add `VelTamperPadPct` constant)

- [ ] **Step 1: Add `p_VelRangeFade` parameter in the VELOCITY RANGE block**

Change `Note Prozessor.gpscript:62–65` from:

```gpscript
   // --- 9. VELOCITY RANGE (NEW) ---
   p_VelRangeActive  : Parameter 0 .. 1 = 0
   p_MinVel          : Parameter 0 .. 127 = 0
   p_MaxVel          : Parameter 0 .. 127 = 127
```

To:

```gpscript
   // --- 9. VELOCITY RANGE (NEW) ---
   p_VelRangeActive  : Parameter 0 .. 1 = 0
   p_MinVel          : Parameter 0 .. 127 = 0
   p_MaxVel          : Parameter 0 .. 127 = 127
   p_VelRangeFade    : Parameter 0 .. 1 = 0   // Edge-fade tamper toggle

   // User-tunable pad percentage for Vel Tamper edge-fade (each side of range).
   // Kept out of the UI (user would not adjust live). Edit this value to retune.
   VelTamperPadPct   : Double = 0.10
```

- [ ] **Step 2: Verify scriptlet compiles in Gig Performer**

Open the scriptlet editor and press Compile. Expected: no errors, parameter list shows `p_VelRangeFade` after `p_MaxVel`.

- [ ] **Step 3: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "feat(np): add p_VelRangeFade parameter and VelTamperPadPct constant"
```

---

### Task 2: Implement GetVelRangeVelocity Helper Function

**Files:**
- Modify: `Note Prozessor.gpscript:286` (insert new function after `GetOctRangeVelocity`, before `// THE OCTAVER ENGINE` comment)

- [ ] **Step 1: Insert the helper function after `GetOctRangeVelocity`**

Insert after line 285 (`End` of `GetOctRangeVelocity`), before line 287 (`// THE OCTAVER ENGINE` comment):

```gpscript

// ---------------------------------------------------------
// VELOCITY RANGE: Velocity Gating & Edge Fade (Tamper)
// ---------------------------------------------------------
// Mirrors GetOctRangeVelocity but operates on incoming velocity (not clone-note
// position). Outside [p_MinVel, p_MaxVel]: hard-gated to 0. Inside: when
// p_VelRangeFade is active and span >= 20, velocities within VelTamperPadPct
// (10%) of each edge are linearly scaled down with a floor of 1.
Function GetVelRangeVelocity(vel : Integer) Returns Integer
   var minVel, maxVel, span, pad, dist, distHigh : Integer
   var factor : Double = 1.0
   var res : Integer = vel

   minVel = Round(p_MinVel)
   maxVel = Round(p_MaxVel)
   span = maxVel - minVel

   // Gate: outside range -> suppress (hard gate, unchanged)
   if vel < minVel or vel > maxVel then
      res = 0
   else
      // Tamper: only active when flag set AND span is wide enough for a ramp
      if Round(p_VelRangeFade) == 1 and span >= 20 then
         pad = Round(IntToFloat(span) * VelTamperPadPct)
         if pad < 1 then pad = 1 end

         dist = vel - minVel
         distHigh = maxVel - vel
         if distHigh < dist then dist = distHigh end

         if dist < pad then
            factor = (IntToFloat(dist) + 1.0) / (IntToFloat(pad) + 1.0)
            res = Round(IntToFloat(vel) * factor)
            if res < 1 then res = 1 end
         end
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
git commit -m "feat(np): add GetVelRangeVelocity helper for velocity range tamper"
```

---

### Task 3: Integrate GetVelRangeVelocity into the Master Event Handler

**Files:**
- Modify: `Note Prozessor.gpscript:612–615` (replace VELOCITY RANGE Türsteher)

- [ ] **Step 1: Replace the hard-gate block with the tamper call**

Change `Note Prozessor.gpscript:612–615` from:

```gpscript
             // TÜRSTEHER 3: VELOCITY RANGE (Neu)
             if Round(p_VelRangeActive) == 1 and (vel < Round(p_MinVel) or vel > Round(p_MaxVel)) then
                 // Out of Range -> Ignorieren!
             else
```

To:

```gpscript
             // TÜRSTEHER 3: VELOCITY RANGE (Neu) — now with Tamper (edge-fade)
             if Round(p_VelRangeActive) == 1 then
                 vel = GetVelRangeVelocity(vel)  // returns 0 outside range, scaled inside if fade active
             end
             if vel > 0 then
```

- [ ] **Step 2: Verify scriptlet compiles**

Open the scriptlet editor and press Compile. Expected: no errors.

- [ ] **Step 3: Manual behavior test in Gig Performer**

1. Set `p_VelRangeActive=1`, `p_MinVel=40`, `p_MaxVel=80` (span=40, pad=4), `p_VelRangeFade=0`.
2. Play velocities 39, 40, 50, 80, 81. Expected: 39 silent, 40 plays at 40, 50 plays at 50, 80 plays at 80, 81 silent. (Pure hard-gate, pre-tamper behavior.)
3. Set `p_VelRangeFade=1`.
4. Play velocities 39, 40, 41, 44, 45, 80, 81. Expected: 39 silent, 40 → `Round(40*1/5)=8`, 41 → `Round(41*2/5)=16`, 44 → full 44, 45 → full 45, 80 → `Round(80*1/5)=16`, 81 silent.
5. Set `p_MinVel=50`, `p_MaxVel=65` (span=15, below threshold 20). Play 50–65. Expected: tamper does not apply, all velocities pass unchanged (hard-gate inside range, span<20 suppresses fader).

- [ ] **Step 4: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "feat(np): route vel range through GetVelRangeVelocity for edge fade"
```

---

### Task 4: Add Global Rackspace Widget Declaration and Memory Array

**Files:**
- Modify: `Global Rackspace.gpscript:237` (widget declarations, after `BTN_Inject_NP_VelMinLearn, BTN_Inject_NP_VelMaxLearn`)
- Modify: `Global Rackspace.gpscript:411` (memory arrays, after `Mem_NP_MaxVel`)

- [ ] **Step 1: Add `BTN_Inject_NP_VelTamper` widget declaration**

Change `Global Rackspace.gpscript:237` from:

```gpscript
   BTN_Inject_NP_VelMinLearn, BTN_Inject_NP_VelMaxLearn                          : Widget
```

To:

```gpscript
   BTN_Inject_NP_VelMinLearn, BTN_Inject_NP_VelMaxLearn                          : Widget
   BTN_Inject_NP_VelTamper                                                       : Widget
```

- [ ] **Step 2: Add `Mem_NP_VelRangeFade` memory array**

Change `Global Rackspace.gpscript:411` from:

```gpscript
   Mem_NP_MaxVel          : Integer Array = [127,127,127,127,127,127,127,127,127,127,127,127,127,127,127,127]
```

To:

```gpscript
   Mem_NP_MaxVel          : Integer Array = [127,127,127,127,127,127,127,127,127,127,127,127,127,127,127,127]
   Mem_NP_VelRangeFade    : Integer Array = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
```

- [ ] **Step 3: Verify Global Rackspace script compiles**

In the Global Rackspace script editor, press Compile. Expected: no errors, `BTN_Inject_NP_VelTamper` and `Mem_NP_VelRangeFade` both resolve.

- [ ] **Step 4: Create the UI widget in the Rackspace**

In the Global Rackspace editor, add a momentary-toggle button adjacent to `BTN_Inject_NP_VelRange`. Set its widget handle name to `BTN_Inject_NP_VelTamper`. Save the rackspace.

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): declare BTN_Inject_NP_VelTamper widget and Mem_NP_VelRangeFade"
```

---

### Task 5: Wire VelTamper into Factory Reset, Sync, and Snapshot Paths

**Files:**
- Modify: `Global Rackspace.gpscript:1644` (factory reset SetParameter)
- Modify: `Global Rackspace.gpscript:1664` (factory reset Mem write)
- Modify: `Global Rackspace.gpscript:2147` (offline / no-scope sync)
- Modify: `Global Rackspace.gpscript:2191` (online / scoped sync)
- Modify: `Global Rackspace.gpscript:8184` (InjectNPToggle case)
- Modify: `Global Rackspace.gpscript:11417` (snapshot readback)

- [ ] **Step 1: Add `p_VelRangeFade` reset in channel-strip factory reset**

Change `Global Rackspace.gpscript:1644–1646` from:

```gpscript
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_VelRangeActive"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 0.0) end
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_MinVel"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 0.0) end
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_MaxVel"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 1.0) end
```

To:

```gpscript
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_VelRangeActive"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 0.0) end
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_MinVel"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 0.0) end
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_MaxVel"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 1.0) end
    idx = GetParamIdxByName(BLK_NoteProcessor[chIdx], "p_VelRangeFade"); if idx > -1 then SetParameter(BLK_NoteProcessor[chIdx], idx, 0.0) end
```

- [ ] **Step 2: Reset `Mem_NP_VelRangeFade` in channel-strip factory reset**

Change `Global Rackspace.gpscript:1664` from:

```gpscript
    Mem_NP_VelRangeActive[chIdx] = 0; Mem_NP_MinVel[chIdx] = 0; Mem_NP_MaxVel[chIdx] = 127
```

To:

```gpscript
    Mem_NP_VelRangeActive[chIdx] = 0; Mem_NP_MinVel[chIdx] = 0; Mem_NP_MaxVel[chIdx] = 127; Mem_NP_VelRangeFade[chIdx] = 0
```

- [ ] **Step 3: Add offline (no-scope) sync for the new widget**

Change `Global Rackspace.gpscript:2145–2147` from:

```gpscript
      SetWidgetValue(BTN_Inject_NP_VelRange, 0.0)
      SetWidgetLabel(LBL_Inject_NP_VelMin, "-")
      SetWidgetLabel(LBL_Inject_NP_VelMax, "-")
```

To:

```gpscript
      SetWidgetValue(BTN_Inject_NP_VelRange, 0.0)
      SetWidgetLabel(LBL_Inject_NP_VelMin, "-")
      SetWidgetLabel(LBL_Inject_NP_VelMax, "-")
      SetWidgetValue(BTN_Inject_NP_VelTamper, 0.0)
```

- [ ] **Step 4: Add online (scoped) sync for the new widget**

Change `Global Rackspace.gpscript:2189–2191` from:

```gpscript
      SetWidgetValue(BTN_Inject_NP_VelRange, IntToFloat(Mem_NP_VelRangeActive[firstScopeIdx]))
      SetWidgetLabel(LBL_Inject_NP_VelMin, IntToString(Mem_NP_MinVel[firstScopeIdx]))
      SetWidgetLabel(LBL_Inject_NP_VelMax, IntToString(Mem_NP_MaxVel[firstScopeIdx]))
```

To:

```gpscript
      SetWidgetValue(BTN_Inject_NP_VelRange, IntToFloat(Mem_NP_VelRangeActive[firstScopeIdx]))
      SetWidgetLabel(LBL_Inject_NP_VelMin, IntToString(Mem_NP_MinVel[firstScopeIdx]))
      SetWidgetLabel(LBL_Inject_NP_VelMax, IntToString(Mem_NP_MaxVel[firstScopeIdx]))
      SetWidgetValue(BTN_Inject_NP_VelTamper, IntToFloat(Mem_NP_VelRangeFade[firstScopeIdx]))
```

- [ ] **Step 5: Add new paramType case in InjectNPToggle**

Change `Global Rackspace.gpscript:8183–8185` from:

```gpscript
         elsif paramType == 9 then Mem_NP_QuantizeActive[i] = intVal
         elsif paramType == 10 then Mem_NP_OctRangeFade[i] = intVal
         end
```

To:

```gpscript
         elsif paramType == 9 then Mem_NP_QuantizeActive[i] = intVal
         elsif paramType == 10 then Mem_NP_OctRangeFade[i] = intVal
         elsif paramType == 11 then Mem_NP_VelRangeFade[i] = intVal
         end
```

(Note: slot 11 in `InjectNPToggle` is free. `InjectNPStep` uses slot 11 for QuantScale — different function, no conflict.)

- [ ] **Step 6: Add snapshot readback for `p_VelRangeFade`**

Change `Global Rackspace.gpscript:11415–11417` from:

```gpscript
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_VelRangeActive"); if idx > -1 then Mem_NP_VelRangeActive[i] = Round(GetParameter(BLK_NoteProcessor[i], idx)) end
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_MinVel"); if idx > -1 then Mem_NP_MinVel[i] = Round(GetParameter(BLK_NoteProcessor[i], idx) * 127.0) end
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_MaxVel"); if idx > -1 then Mem_NP_MaxVel[i] = Round(GetParameter(BLK_NoteProcessor[i], idx) * 127.0) end
```

To:

```gpscript
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_VelRangeActive"); if idx > -1 then Mem_NP_VelRangeActive[i] = Round(GetParameter(BLK_NoteProcessor[i], idx)) end
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_MinVel"); if idx > -1 then Mem_NP_MinVel[i] = Round(GetParameter(BLK_NoteProcessor[i], idx) * 127.0) end
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_MaxVel"); if idx > -1 then Mem_NP_MaxVel[i] = Round(GetParameter(BLK_NoteProcessor[i], idx) * 127.0) end
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_VelRangeFade"); if idx > -1 then Mem_NP_VelRangeFade[i] = Round(GetParameter(BLK_NoteProcessor[i], idx)) end
```

- [ ] **Step 7: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): wire p_VelRangeFade into reset, sync, InjectNPToggle, and snapshot readback"
```

---

### Task 6: Add BTN_Inject_NP_VelTamper Callback Handler

**Files:**
- Modify: `Global Rackspace.gpscript:12785` (after `BTN_Inject_NP_VelRange` callback)

- [ ] **Step 1: Insert the VelTamper toggle callback**

Change `Global Rackspace.gpscript:12784–12786` from:

```gpscript
On WidgetValueChanged(val : Double) from BTN_Inject_NP_VelRange
   if not IsUpdatingNP then InjectNPToggle(7, "p_VelRangeActive", val) end 
End
```

To:

```gpscript
On WidgetValueChanged(val : Double) from BTN_Inject_NP_VelRange
   if not IsUpdatingNP then InjectNPToggle(7, "p_VelRangeActive", val) end 
End
On WidgetValueChanged(val : Double) from BTN_Inject_NP_VelTamper
   if not IsUpdatingNP then InjectNPToggle(11, "p_VelRangeFade", val) end
End
```

- [ ] **Step 2: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 3: Manual end-to-end test**

1. Select one channel strip as the edit scope.
2. Activate `BTN_Inject_NP_VelRange`, set `LBL_Inject_NP_VelMin = 40`, `LBL_Inject_NP_VelMax = 80`.
3. Press `BTN_Inject_NP_VelTamper`. Verify: the widget toggles on, the channel-strip's `p_VelRangeFade` parameter goes to 1.0 in the NP scriptlet parameter browser.
4. Play velocities 40, 44, 80 on MIDI input. Observe that 40 and 80 come out softened (roughly 1/5 of input), 44 plays at full.
5. Toggle off — behavior returns to hard-gate.
6. Save & reload a snapshot containing the active tamper. Verify `BTN_Inject_NP_VelTamper` reflects the stored state.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add BTN_Inject_NP_VelTamper toggle callback"
```

---

## FEATURE B — Macro Space Renumbering, ControllerInfo Fix, Legacy Group Removal

### Task 7: Bump MAX_MACROS and Renumber DEF_*_MacroIdx Arrays

**Files:**
- Modify: `Global Rackspace.gpscript:43` (`MAX_MACROS`)
- Modify: `Global Rackspace.gpscript:46–55` (all `DEF_*_MacroIdx` arrays)
- Modify: `Global Rackspace.gpscript:59` (`MacroGroup_Anchors`)

- [ ] **Step 1: Bump `MAX_MACROS`**

Change `Global Rackspace.gpscript:43` from:

```gpscript
   MAX_MACROS : Integer = 100
```

To:

```gpscript
   MAX_MACROS : Integer = 256
```

- [ ] **Step 2: Renumber all DEF_*_MacroIdx arrays (shift by +16, new base 50)**

Change `Global Rackspace.gpscript:46–55` from:

```gpscript
   DEF_LOOPER_CH_MacroIdx   : Integer Array = [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]
   DEF_SOLO_SMART_MacroIdx  : Integer Array = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]  
   DEF_SOLO_STRICT_MacroIdx : Integer Array = [66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81]
   DEF_USER_MUTE_MacroIdx   : Integer Array = [82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97] 
   DEF_VELRANGE_MacroIdx    : Integer Array = [98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113]
   DEF_ROOT_MacroIdx        : Integer Array = [114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129]
   DEF_OCTAVER_MacroIdx     : Integer Array = [130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145]
   DEF_HUMANIZE_MacroIdx    : Integer Array = [146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161]
   DEF_QUANTIZE_MacroIdx    : Integer Array = [162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177]
   DEF_SUSTAIN_MacroIdx     : Integer Array = [178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193]
```

To:

```gpscript
   DEF_LOOPER_CH_MacroIdx   : Integer Array = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]
   DEF_SOLO_SMART_MacroIdx  : Integer Array = [66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81]
   DEF_SOLO_STRICT_MacroIdx : Integer Array = [82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97]
   DEF_USER_MUTE_MacroIdx   : Integer Array = [98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113]
   DEF_VELRANGE_MacroIdx    : Integer Array = [114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129]
   DEF_ROOT_MacroIdx        : Integer Array = [130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145]
   DEF_OCTAVER_MacroIdx     : Integer Array = [146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161]
   DEF_HUMANIZE_MacroIdx    : Integer Array = [162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177]
   DEF_QUANTIZE_MacroIdx    : Integer Array = [178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193]
   DEF_SUSTAIN_MacroIdx     : Integer Array = [194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209]
```

- [ ] **Step 3: Update `MacroGroup_Anchors` to match new base positions**

Change `Global Rackspace.gpscript:59` from:

```gpscript
   MacroGroup_Anchors : Integer Array = [-1,             0,                  34,       50,           66,            82,          98,               114,          130,       146,         162,               178]
```

To:

```gpscript
   MacroGroup_Anchors : Integer Array = [-1,             0,                  50,       66,           82,            98,          114,              130,          146,       162,         178,               194]
```

- [ ] **Step 4: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors. (The script will still behave incorrectly at this point for anchor-based operations because of the hardcoded magic numbers at :2867-2876; that's the next task.)

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(gr): bump MAX_MACROS to 256 and renumber group defaults to start at 50"
```

---

### Task 8: Update Hardcoded Anchor Lookups in UpdateControllerInfoDisplay

**Files:**
- Modify: `Global Rackspace.gpscript:2866–2877` (the `MacroGroup_Anchors[g] == N` lookup block)

- [ ] **Step 1: Update magic-number anchors to match the new layout**

Change `Global Rackspace.gpscript:2866–2877` from:

```gpscript
   // 2. Where are the groups in the current sort order?
   For g = 0; g < Grp_Count; g = g + 1 Do
       if MacroGroup_Anchors[g] == 82  then idxLooper = g end
       if MacroGroup_Anchors[g] == 34  then idxSmart = g end
       if MacroGroup_Anchors[g] == 50  then idxStrict = g end
       if MacroGroup_Anchors[g] == 66  then idxMute = g end
       if MacroGroup_Anchors[g] == 98  then idxVel = g end
       if MacroGroup_Anchors[g] == 114 then idxRoot = g end
       if MacroGroup_Anchors[g] == 130 then idxOct = g end
       if MacroGroup_Anchors[g] == 146 then idxHum = g end
       if MacroGroup_Anchors[g] == 162 then idxQuant = g end
       if MacroGroup_Anchors[g] == 178 then idxSus = g end
   End
```

To:

```gpscript
   // 2. Where are the groups in the current sort order?
   // Anchor values MUST match MacroGroup_Anchors at :59 exactly.
   For g = 0; g < Grp_Count; g = g + 1 Do
       if MacroGroup_Anchors[g] == 50  then idxLooper = g end
       if MacroGroup_Anchors[g] == 66  then idxSmart = g end
       if MacroGroup_Anchors[g] == 82  then idxStrict = g end
       if MacroGroup_Anchors[g] == 98  then idxMute = g end
       if MacroGroup_Anchors[g] == 114 then idxVel = g end
       if MacroGroup_Anchors[g] == 130 then idxRoot = g end
       if MacroGroup_Anchors[g] == 146 then idxOct = g end
       if MacroGroup_Anchors[g] == 162 then idxHum = g end
       if MacroGroup_Anchors[g] == 178 then idxQuant = g end
       if MacroGroup_Anchors[g] == 194 then idxSus = g end
   End
```

- [ ] **Step 2: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(gr): update hardcoded anchor-value lookups to renumbered base"
```

---

### Task 9: Fix ControllerInfo Display Loop Bound

**Files:**
- Modify: `Global Rackspace.gpscript:2886` (display scan loop)

- [ ] **Step 1: Extend the scan loop to cover all macros**

Change `Global Rackspace.gpscript:2886` from:

```gpscript
       For s = 0; s < 128; s = s + 1 Do
```

To:

```gpscript
       For s = 0; s < MAX_MACROS; s = s + 1 Do
```

- [ ] **Step 2: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 3: Manual display smoke test**

1. Restart the Rackspace. Observe `LBL_ControllerInfo`.
2. Expected: the grouped entries at the bottom of the list now show all 10 groups — Looper (Macro 51–66), Smart Solo (67–82), Strict Solo (83–98), User Mute (99–114), Velocity Range (115–130), Root/Chord (131–146), Octaver (147–162), Humanizer (163–178), Scale Quantizer (179–194), Auto Sustain (195–210).

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "fix(gr): extend UpdateControllerInfoDisplay scan loop to MAX_MACROS"
```

---

### Task 10: Delete Legacy Group-Keyword Save Code

**Files:**
- Modify: `Global Rackspace.gpscript:3622–3660` (SaveControllerMap branches for group keywords)

- [ ] **Step 1: Read the current save section to identify the exact block to delete**

Read `Global Rackspace.gpscript` from line 3615 to 3670 and identify the block that writes `LOOPER_CH`, `SOLO_SMART_CH`, `SOLO_STRICT_CH`, `USER_MUTE_CH`, `VELRANGE_CH`, `ROOT_CH`, `OCTAVER_CH`, `HUMANIZE_CH`, `QUANTIZE_CH`, `SUSTAIN_CH` lines to the output. The existing lookup code at `:3622–3633` finds which channel (if any) owns the current slider; the emit code at `:3638–3658` writes the corresponding `<KEYWORD>_CH<n>` line.

- [ ] **Step 2: Delete the lookup block (inner `For chIdx` loop for group-channel detection)**

Remove the channel-detection block that assigns `looperChFound`, `smartSoloChFound`, `strictSoloChFound`, `userMuteChFound`, `velRangeChFound`, `rootChFound`, `octChFound`, `humChFound`, `quantChFound`, `susChFound`. Keep any non-group-channel detection intact.

- [ ] **Step 3: Delete the emit block for group channels**

Remove all `if isCC or s != DEF_*_MacroIdx[...ChFound] then newBlock = newBlock + line + " = LOOPER_CH"` / `SOLO_SMART_CH` / `SOLO_STRICT_CH` / `USER_MUTE_CH` / `VELRANGE_CH` / `ROOT_CH` / `OCTAVER_CH` / `HUMANIZE_CH` / `QUANTIZE_CH` / `SUSTAIN_CH` blocks. Keep all other emit branches (normal links, single-role keywords like `CROSSFADER`, `SCRUBBER`, etc.).

- [ ] **Step 4: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors. Any `*ChFound` variables that were declared at the top of the function and are no longer used must also be removed to avoid unused-var warnings.

- [ ] **Step 5: Manual save test**

1. Load a `[Map:*]` section that uses the default layout.
2. Trigger a save of the controller map (through whatever UI path normally saves it).
3. Open `ControllerMaps.txt` and inspect the section. Expected: no `LOOPER_CH*`, `SOLO_SMART_CH*`, `SOLO_STRICT_CH*`, `USER_MUTE_CH*`, `VELRANGE_CH*`, `ROOT_CH*`, `OCTAVER_CH*`, `HUMANIZE_CH*`, `QUANTIZE_CH*`, or `SUSTAIN_CH*` lines in the saved output.
4. Normal VST links and single-role keywords (`CROSSFADER`, `SCRUBBER`, etc.) remain present.

- [ ] **Step 6: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(gr): stop emitting legacy group-keyword lines in SaveControllerMap"
```

---

### Task 11: Delete Legacy Group-Keyword Parser Branches

**Files:**
- Modify: `Global Rackspace.gpscript:5825–5875` (all 10 `elsif IndexOfSubstring(valuePart, ..._CH, false) == 0` branches)

- [ ] **Step 1: Delete the 10 group-keyword parser branches**

Delete lines `5824–5876` entirely (the `// --- GROUP MACROS ---` comment and all 10 `elsif IndexOfSubstring(valuePart, "XXX_CH", false) == 0` branches). Leave the `// --- NORMAL LINKS ---` `else` branch at `:5877` intact.

Exact text to delete (copy-paste match):

```gpscript
                               // --- GROUP MACROS ---
                                elsif IndexOfSubstring(valuePart, "LOOPER_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "LOOPER_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then LOOPER_CH_CCIdx[chNum] = sliderIdx else LOOPER_CH_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "SOLO_STRICT_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "SOLO_STRICT_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then SOLO_STRICT_CCIdx[chNum] = sliderIdx else SOLO_STRICT_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "SOLO_SMART_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "SOLO_SMART_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then SOLO_SMART_CCIdx[chNum] = sliderIdx else SOLO_SMART_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "USER_MUTE_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "USER_MUTE_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then USER_MUTE_CCIdx[chNum] = sliderIdx else USER_MUTE_MacroIdx[chNum] = sliderIdx end
                                    end

                                elsif IndexOfSubstring(valuePart, "VELRANGE_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "VELRANGE_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then VELRANGE_CCIdx[chNum] = sliderIdx else VELRANGE_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "ROOT_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "ROOT_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then ROOT_CCIdx[chNum] = sliderIdx else ROOT_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "OCTAVER_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "OCTAVER_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then OCTAVER_CCIdx[chNum] = sliderIdx else OCTAVER_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "HUMANIZE_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "HUMANIZE_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then HUMANIZE_CCIdx[chNum] = sliderIdx else HUMANIZE_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "QUANTIZE_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "QUANTIZE_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then QUANTIZE_CCIdx[chNum] = sliderIdx else QUANTIZE_MacroIdx[chNum] = sliderIdx end
                                    end
                                elsif IndexOfSubstring(valuePart, "SUSTAIN_CH", false) == 0 then
                                    chNum = StringToInt(ReplaceString(valuePart, "SUSTAIN_CH", "", false)) - 1
                                    if chNum >= 0 and chNum < 16 then
                                        if isSrcCC then SUSTAIN_CCIdx[chNum] = sliderIdx else SUSTAIN_MacroIdx[chNum] = sliderIdx end
                                    end
```

After the deletion, the parser should transition directly from the `SCRUBBER` branch at `:5821–5822` to the `// --- NORMAL LINKS ---` `else` branch that was at `:5877`. The `SCRUBBER` branch `end` line is followed directly by the `else` line.

- [ ] **Step 2: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors. The `chNum` variable declaration used by these branches may now be unused — if the compiler warns, leave it alone (other branches may still use it, or it's declared at the top of the function for general use).

- [ ] **Step 3: Verify runtime arrays retain Init defaults after a map load**

1. Restart the Rackspace.
2. Inspect `LOOPER_CH_MacroIdx[0]` via a one-shot Trace. Expected value: 50 (the new default from `DEF_LOOPER_CH_MacroIdx[0]`).
3. Load a `[Map:*]` section that contains a stray `Macro80 = LOOPER_CH1` line (insert this manually into `ControllerMaps.txt` for the test section).
4. Inspect `LOOPER_CH_MacroIdx[0]` again. Expected: still 50 (the parser no longer mutates the array; the stray line was silently ignored because the `else` branch treats it as an unrecognized link format).

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(gr): delete legacy group-keyword parser branches in LoadControllerMap"
```

---

### Task 12: Clean Up ControllerMaps.txt Manually

**Files:**
- Modify: `ControllerMaps.txt` (user-level cleanup, not tracked in git commit)

- [ ] **Step 1: Open `ControllerMaps.txt` and identify stray legacy lines**

Search the file for any lines matching these patterns and remove them from every `[Map:*]` section:

```
LOOPER_CH1 .. LOOPER_CH16
SOLO_SMART_CH1 .. SOLO_SMART_CH16
SOLO_STRICT_CH1 .. SOLO_STRICT_CH16
USER_MUTE_CH1 .. USER_MUTE_CH16
VELRANGE_CH1 .. VELRANGE_CH16
ROOT_CH1 .. ROOT_CH16
OCTAVER_CH1 .. OCTAVER_CH16
HUMANIZE_CH1 .. HUMANIZE_CH16
QUANTIZE_CH1 .. QUANTIZE_CH16
SUSTAIN_CH1 .. SUSTAIN_CH16
```

- [ ] **Step 2: Do NOT touch**

- Normal link lines (`Macro<N> = VST<k>_GRS:<param>`, `Macro<N> = Ch<c>:CC<n>:<label>`)
- Single-role keyword lines (`CROSSFADER`, `SCRUBBER`, `SYSTEM_TOGGLE`, `VST_SCOPE`, `VST_PREV`, `VST_NEXT`, `VST_BROWSE`, `SYSMODE_CYCLE`, `SYSMODE_SELECT`, `VST_SCOPE_PREV`, `VST_SCOPE_NEXT`, `REC_SONGPART`)
- Section headers (`[Map:Name]`)

- [ ] **Step 3: Reload all sections to verify**

Cycle through every `[Map:*]` section via the map-switch UI. Expected: no errors, `LBL_ControllerInfo` shows the group entries at the new default positions for every section.

- [ ] **Step 4: Commit (if `ControllerMaps.txt` is git-tracked)**

```bash
git add "ControllerMaps.txt"
git commit -m "chore: strip legacy group-keyword lines from ControllerMaps sections"
```

If the file is in `.gitignore`, skip this step — the cleanup is local-only.

---

### Task 13: Regression Smoke Test for Feature B

**Files:**
- None (manual test)

- [ ] **Step 1: Legacy group dispatch still works**

1. Identify the hardware macro bound (via HardwareMap) to macro slot 50.
2. Press it. Expected: Looper channel 1 toggles (because `LOOPER_CH_MacroIdx[0] == 50`).
3. Repeat for slot 66 (Smart Solo channel 1), slot 82 (Strict Solo channel 1), slot 98 (User Mute channel 1), slot 114 (Velocity Range channel 1).

- [ ] **Step 2: Display shows all groups**

Observe `LBL_ControllerInfo`. Expected: all 10 grouped entries visible, in the order defined by `MacroGroup_Names`: Looper, Smart Solo, Strict Solo, User Mute, Velocity Range, Root/Chord, Octaver, Humanizer, Scale Quantizer, Auto Sustain.

- [ ] **Step 3: Scope jump still works**

Use whatever UI jumps to a group scope (e.g. SYS-MODE CONTROLLER MAP navigation). Confirm that `ScrollToCurrentCtrlScope` scrolls correctly to the Looper, Smart Solo, Strict Solo, and User Mute sections.

- [ ] **Step 4: No commit required (pure test)**

---

### Task 14: Spec Hand-Off Checkpoint

**Files:**
- None

- [ ] **Step 1: Pause and verify Feature B is fully landed before starting Feature C**

At this point the codebase should:
- Compile cleanly
- Show all 10 group entries in `LBL_ControllerInfo`
- Handle joystick SYS-MODE actions exactly as before (via direct function calls in `ProcessSystemNavigation`)
- Silently ignore any legacy `LOOPER_CH*` / etc. lines in `ControllerMaps.txt` sections
- Not emit legacy group-keyword lines when saving a map

If any of the above is broken, fix before proceeding. Feature C assumes a clean Feature B base.

---

## FEATURE C — System Action Framework

### Task 15: Add SysAction Registry to Core Constants

**Files:**
- Modify: `Global Rackspace.gpscript:60` (after `MacroGroup_Anchors`)

- [ ] **Step 1: Insert the SysAction registry block**

Insert after line 59 (`MacroGroup_Anchors : Integer Array = [...]`), before line 61 or wherever the next block begins:

```gpscript

   // --- SYSTEM ACTIONS (Virtual Role Dispatch) ---
   // Central registry: add new system actions here, then add a case to FireSystemAction().
   // These are ROLES, not reserved macro slots. They live in the user's 0-49 macro space
   // and are assigned via ControllerMaps.txt (e.g. "Macro5 = SYSACT_VST_SCOPE_UP").
   // Excluded from Timeline Record/Playback by the Isolation Rule.
   SysAction_Names : String Array = [
      "VST_SCOPE_UP",       "VST_SCOPE_DOWN",
      "VST_PRESET_UP",      "VST_PRESET_DOWN",
      "LOOPER_CH_UP",       "LOOPER_CH_DOWN",
      "LOOPER_REC",         "LOOPER_CLEAR",
      "CTRLMAP_PREV",       "CTRLMAP_NEXT",
      "CTRLMAP_RESTORE",    "CTRLMAP_CYCLE",
      "STRIP_CH_UP",        "STRIP_CH_DOWN",
      "STRIP_THEME_PREV",   "STRIP_THEME_NEXT",
      "STRIP_MACRO_TOGGLE",
      "TL_PARTJUMP_NEXT",   "TL_PARTJUMP_PREV",
      "TL_REC_SONGPART"
   ]

   // Human-readable labels for LBL_ControllerInfo display
   SysAction_Labels : String Array = [
      "VST Scope [Next]",        "VST Scope [Prev]",
      "VST Preset [Next]",       "VST Preset [Prev]",
      "Looper Channel [Next]",   "Looper Channel [Prev]",
      "Looper Record",           "Looper Clear",
      "Ctrl Map [Prev Active]",  "Ctrl Map [Next Active]",
      "Ctrl Map Restore Initial","Ctrl Map Cycle",
      "Strip Channel [Next]",    "Strip Channel [Prev]",
      "Strip Theme [Prev]",      "Strip Theme [Next]",
      "Strip Macro Toggle",
      "Timeline Part Jump [Next]","Timeline Part Jump [Prev]",
      "Timeline Rec Songpart"
   ]

   // Reverse lookup tables: index is the macro slot / CC number, value is the
   // SysAction index (-1 = unbound). Sized by MAX_MACROS and 128 — NOT by the
   // action count — so adding new actions never requires resizing these.
   SysAction_ByMacro : Integer Array
   SysAction_ByCC    : Integer Array
```

- [ ] **Step 2: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add SysAction registry and reverse-lookup arrays"
```

---

### Task 16: Initialize SysAction Arrays and Add Helper Functions

**Files:**
- Modify: the Rackspace `Initialization` block (search for `Initialization` near the top of the script's execution section — typically after declarations)
- Modify: `Global Rackspace.gpscript` near `ProcessSystemNavigation()` at `:9969` (add helpers before it)

- [ ] **Step 1: Find the Rackspace Initialization block**

Run: Grep for `^Initialization` in `Global Rackspace.gpscript` with `-n` to get the line number. Remember this line for Step 2.

- [ ] **Step 2: Append SysAction array initialization to the `Initialization` block**

Inside the `Initialization` block (before its `End`), add:

```gpscript
   // --- SYSTEM ACTION REVERSE-LOOKUP ARRAYS ---
   var sysActInitIdx : Integer
   For sysActInitIdx = 0; sysActInitIdx < MAX_MACROS; sysActInitIdx = sysActInitIdx + 1 Do
      SysAction_ByMacro <-- -1
   End
   For sysActInitIdx = 0; sysActInitIdx < 128; sysActInitIdx = sysActInitIdx + 1 Do
      SysAction_ByCC <-- -1
   End
```

- [ ] **Step 3: Insert `SysActIdx()`, `ResetSysActionBindings()`, and `IsSystemActionMacro()` helpers**

Insert before `Function ProcessSystemNavigation` at `:9969`:

```gpscript
// ---------------------------------------------------------
// SYSTEM ACTION HELPERS
// ---------------------------------------------------------
Function SysActIdx(name : String) Returns Integer
   var i, res : Integer
   res = -1
   For i = 0; i < Size(SysAction_Names); i = i + 1 Do
      if SysAction_Names[i] == name then res = i end
   End
   result = res
End

Function ResetSysActionBindings()
   var i : Integer
   For i = 0; i < MAX_MACROS; i = i + 1 Do SysAction_ByMacro[i] = -1 End
   For i = 0; i < 128; i = i + 1 Do SysAction_ByCC[i] = -1 End
End

Function IsSystemActionMacro(paramIdx : Integer) Returns Boolean
   var res : Boolean = false
   if paramIdx >= 0 and paramIdx < MAX_MACROS then
      res = SysAction_ByMacro[paramIdx] > -1
   end
   result = res
End

```

- [ ] **Step 4: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): initialize SysAction reverse-lookup arrays and add helpers"
```

---

### Task 17: Implement FireSystemAction Dispatcher

**Files:**
- Modify: `Global Rackspace.gpscript` insert before `ProcessSystemNavigation` at `:9969` (after the helpers added in Task 16)

- [ ] **Step 1: Add `RestoreInitialControllerMap` helper**

Before `FireSystemAction`, add:

```gpscript
// Helper: restore the song-specified controller map (used by SYSACT_CTRLMAP_RESTORE
// and by the existing joystick Y+ path in ProcessSystemNavigation).
Function RestoreInitialControllerMap()
   if ExpectedMapName != "" and ExpectedMapName != "-" then
      LoadControllerMap(ExpectedMapName)
      HardwareSyncTimer = TimeSinceStartup() + 2000.0
      OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> MAP: " + ExpectedMapName + " <<<", Local_IP, Local_PORT)
      MacroFeedbackTimer = TimeSinceStartup() + 2000.0
      MacroFeedbackLockTimer = TimeSinceStartup() + 2000.0
   end
End

```

- [ ] **Step 2: Insert `FireSystemAction` dispatcher**

Right after `RestoreInitialControllerMap`, insert:

```gpscript
// ---------------------------------------------------------
// SYSTEM ACTION DISPATCHER
// Single entry point for all virtualized SYSMODE actions. Called from
// (a) ProcessSystemNavigation (joystick path) and
// (b) the macro ParameterValueChanged handler (hardware-button path).
// ---------------------------------------------------------
Function FireSystemAction(actionIdx : Integer)
   if actionIdx < 0 or actionIdx >= Size(SysAction_Names) then
      if DebugMode then Trace("SYSACT: Invalid actionIdx " + actionIdx) end
   else
      if DebugMode then Trace("SYSACT: Fire " + SysAction_Names[actionIdx]) end

      Select
         SysAction_Names[actionIdx] == "VST_SCOPE_UP"       Do ChangeVstScope(1, -1);  ApplyVstFocusBypass()
         SysAction_Names[actionIdx] == "VST_SCOPE_DOWN"     Do ChangeVstScope(-1, -1); ApplyVstFocusBypass()
         SysAction_Names[actionIdx] == "VST_PRESET_UP"      Do TriggerVstPresetChange(1)
         SysAction_Names[actionIdx] == "VST_PRESET_DOWN"    Do TriggerVstPresetChange(-1)
         SysAction_Names[actionIdx] == "LOOPER_CH_UP"       Do CycleChannelScope(1)
         SysAction_Names[actionIdx] == "LOOPER_CH_DOWN"     Do CycleChannelScope(-1)
         SysAction_Names[actionIdx] == "LOOPER_REC"         Do ClickWidget(BTN_Loop_Rec)
         SysAction_Names[actionIdx] == "LOOPER_CLEAR"       Do ClickWidget(BTN_Loop_Clear)
         SysAction_Names[actionIdx] == "CTRLMAP_PREV"       Do PreviewActiveControllerMaps(-1)
         SysAction_Names[actionIdx] == "CTRLMAP_NEXT"       Do PreviewActiveControllerMaps(1)
         SysAction_Names[actionIdx] == "CTRLMAP_RESTORE"    Do RestoreInitialControllerMap()
         SysAction_Names[actionIdx] == "CTRLMAP_CYCLE"      Do CycleCtrlMap(1)
         SysAction_Names[actionIdx] == "STRIP_CH_UP"        Do CycleStripChannel(1)
         SysAction_Names[actionIdx] == "STRIP_CH_DOWN"      Do CycleStripChannel(-1)
         SysAction_Names[actionIdx] == "STRIP_THEME_PREV"   Do CycleStripTheme(-1)
         SysAction_Names[actionIdx] == "STRIP_THEME_NEXT"   Do CycleStripTheme(1)
         SysAction_Names[actionIdx] == "STRIP_MACRO_TOGGLE" Do ToggleStripMacro()
         SysAction_Names[actionIdx] == "TL_PARTJUMP_NEXT"   Do PartJumpPreview(1)
         SysAction_Names[actionIdx] == "TL_PARTJUMP_PREV"   Do PartJumpPreview(-1)
         SysAction_Names[actionIdx] == "TL_REC_SONGPART"    Do ExecuteRecSongpart()
      End
   end
End

```

- [ ] **Step 3: Verify Global Rackspace script compiles**

Press Compile. Expected: errors about `CycleStripTheme` not accepting `+1` direction (the existing function only implements `-1`). Fix this in Task 18 — for now the compile error is expected and will be resolved by Task 18's changes.

Actually, to keep the commit bisectable and the code compilable at every step: temporarily substitute `CycleStripTheme(1)` with a `Trace("STRIP_THEME_NEXT not yet implemented")` so the script compiles:

```gpscript
         SysAction_Names[actionIdx] == "STRIP_THEME_NEXT"   Do Trace("SYSACT: STRIP_THEME_NEXT pending Task 18")
```

This placeholder will be replaced in Task 18.

- [ ] **Step 4: Verify Global Rackspace script compiles with the placeholder**

Press Compile. Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add FireSystemAction dispatcher and RestoreInitialControllerMap helper"
```

---

### Task 18: Extend CycleStripTheme to Support Direction Parameter

**Files:**
- Modify: `Global Rackspace.gpscript:9847` area (existing `CycleStripTheme` function)
- Modify: `Global Rackspace.gpscript` FireSystemAction dispatcher (replace placeholder from Task 17)

- [ ] **Step 1: Find and read the current `CycleStripTheme` implementation**

Read `Global Rackspace.gpscript:9830–9860` to see the current signature and body of `CycleStripTheme`.

- [ ] **Step 2: Extend `CycleStripTheme` to accept a direction parameter**

Assuming the current function is:

```gpscript
Function CycleStripTheme(dir : Integer)
   Strip_ThemeIdx = Strip_ThemeIdx + dir
   if Strip_ThemeIdx < 3 then Strip_ThemeIdx = Size(MacroGroup_Names) - 1
   elsif Strip_ThemeIdx >= Size(MacroGroup_Names) then Strip_ThemeIdx = 3 end
   ...
End
```

— if it already takes a `dir` argument, the `+1` direction works out-of-the-box, because the wrap logic is already bidirectional. Verify by tracing the function: does it reference `dir` anywhere, or does it hardcode decrement? If it hardcodes `Strip_ThemeIdx = Strip_ThemeIdx - 1`, replace with `Strip_ThemeIdx = Strip_ThemeIdx + dir` and ensure both wrap conditions work.

If changes are needed, apply them.

- [ ] **Step 3: Replace the Task 17 placeholder in FireSystemAction**

Change:

```gpscript
         SysAction_Names[actionIdx] == "STRIP_THEME_NEXT"   Do Trace("SYSACT: STRIP_THEME_NEXT pending Task 18")
```

To:

```gpscript
         SysAction_Names[actionIdx] == "STRIP_THEME_NEXT"   Do CycleStripTheme(1)
```

- [ ] **Step 4: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 5: Manual joystick test**

1. Enter SYS-MODE 3 (STRIP-CONTROL).
2. Joystick X-left → Strip Theme should cycle backwards (existing behavior).
3. Directly call `CycleStripTheme(1)` via a diagnostic Trace path OR wait until Task 19 (joystick refactor) wires a real test path. For now, confirm the code compiles.

- [ ] **Step 6: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): extend CycleStripTheme to support bidirectional theme cycling"
```

---

### Task 19: Refactor ProcessSystemNavigation to Use FireSystemAction

**Files:**
- Modify: `Global Rackspace.gpscript:9971–10083` (entire `ProcessSystemNavigation` function body)

- [ ] **Step 1: Refactor SYS-MODE 0 (VOICE SELECTOR) branch**

Change `Global Rackspace.gpscript:9971–9986` from:

```gpscript
    // --- 0: VOICE SELECTOR ---
    if GlobalSystemMode == 0 then 
        // ARRANGER JOYSTICK
        if actionType == "Y_AXIS" then
            ChangeVstScope(dir, -1)
            ApplyVstFocusBypass() // Apply focus bypass immediately
        elsif actionType == "X_AXIS" then
            TriggerVstPresetChange(dir)
            
        // MINILAB 3
        elsif actionType == "BUTTON" then
            ChangeVstScope(dir, -1) // BUTTON = switch VST scope
            ApplyVstFocusBypass() 
        elsif actionType == "ENCODER" then
            TriggerVstPresetChange(dir) // Wheel = cycle presets
        end
```

To:

```gpscript
    // --- 0: VOICE SELECTOR ---
    if GlobalSystemMode == 0 then
        if actionType == "Y_AXIS" or actionType == "BUTTON" then
            if dir > 0 then FireSystemAction(SysActIdx("VST_SCOPE_UP"))
            else FireSystemAction(SysActIdx("VST_SCOPE_DOWN")) end
        elsif actionType == "X_AXIS" or actionType == "ENCODER" then
            if dir > 0 then FireSystemAction(SysActIdx("VST_PRESET_UP"))
            else FireSystemAction(SysActIdx("VST_PRESET_DOWN")) end
        end
```

- [ ] **Step 2: Refactor SYS-MODE 1 (LOOPER CONTROL) branch**

Change `Global Rackspace.gpscript:9988–10000` from:

```gpscript
    // --- 1: LOOPER CONTROL ---
    elsif GlobalSystemMode == 1 then
        if actionType == "Y_AXIS" then
            CycleChannelScope(dir)           // Y-Up = select channel (1-16)
        elsif actionType == "X_AXIS" then
            if dir == -1 then ClickWidget(BTN_Loop_Clear)   // X-Left full = clear channel
            elsif dir == 1 then ClickWidget(BTN_Loop_Rec)   // X-Right = Record/Play/Overdub flow
            end
        elsif actionType == "ENCODER" then
            CycleChannelScope(dir)           // Wheel = switch channels
        elsif actionType == "BUTTON" then
            ClickWidget(BTN_Loop_Rec)        // Button = Rec/Play/Dub
        end
```

To:

```gpscript
    // --- 1: LOOPER CONTROL ---
    elsif GlobalSystemMode == 1 then
        if actionType == "Y_AXIS" or actionType == "ENCODER" then
            if dir > 0 then FireSystemAction(SysActIdx("LOOPER_CH_UP"))
            else FireSystemAction(SysActIdx("LOOPER_CH_DOWN")) end
        elsif actionType == "X_AXIS" then
            if dir == -1 then FireSystemAction(SysActIdx("LOOPER_CLEAR"))
            elsif dir == 1 then FireSystemAction(SysActIdx("LOOPER_REC")) end
        elsif actionType == "BUTTON" then
            FireSystemAction(SysActIdx("LOOPER_REC"))
        end
```

- [ ] **Step 3: Refactor SYS-MODE 2 (CONTROLLER MAP) branch**

Change `Global Rackspace.gpscript:10002–10021` from:

```gpscript
    // --- 2: CONTROLLER MAP ---
    elsif GlobalSystemMode == 2 then
        if actionType == "Y_AXIS" then
            if dir == 1 then
                // Y-Up = return to initial song-loaded controller map
                if ExpectedMapName != "" and ExpectedMapName != "-" then
                    LoadControllerMap(ExpectedMapName)
                    HardwareSyncTimer = TimeSinceStartup() + 2000.0
                    OSC_SendStringSpecific("/UI/SetMacroFeedback", ">>> MAP: " + ExpectedMapName + " <<<", Local_IP, Local_PORT)
                    MacroFeedbackTimer = TimeSinceStartup() + 2000.0
                    MacroFeedbackLockTimer = TimeSinceStartup() + 2000.0
                end
            end
        elsif actionType == "X_AXIS" then
            PreviewActiveControllerMaps(dir) // X-Left/Right = browse active VST maps
        elsif actionType == "ENCODER" then
            PreviewActiveControllerMaps(dir) // Wheel = browse maps
        elsif actionType == "BUTTON" then
            CycleCtrlMap(dir)                // Button = cycle all maps
        end
```

To:

```gpscript
    // --- 2: CONTROLLER MAP ---
    elsif GlobalSystemMode == 2 then
        if actionType == "Y_AXIS" then
            if dir == 1 then FireSystemAction(SysActIdx("CTRLMAP_RESTORE")) end
        elsif actionType == "X_AXIS" or actionType == "ENCODER" then
            if dir > 0 then FireSystemAction(SysActIdx("CTRLMAP_NEXT"))
            else FireSystemAction(SysActIdx("CTRLMAP_PREV")) end
        elsif actionType == "BUTTON" then
            FireSystemAction(SysActIdx("CTRLMAP_CYCLE"))
        end
```

- [ ] **Step 4: Refactor SYS-MODE 3 (STRIP-CONTROL) branch**

Change `Global Rackspace.gpscript:10023–10037` from:

```gpscript
    // --- 3: STRIP-CONTROL (Grid: Channel x Theme) ---
    elsif GlobalSystemMode == 3 then
        if actionType == "Y_AXIS" then
            CycleStripChannel(dir)           // Y-Up/Down = select channel (like Looper)
        elsif actionType == "X_AXIS" then
            if dir == -1 then
                CycleStripTheme(-1)          // X-Left = prev theme (Octaver -> Humanizer -> ...)
            elsif dir == 1 then
                ToggleStripMacro()           // X-Right = toggle macro at grid position
            end
        elsif actionType == "ENCODER" then
            CycleStripChannel(dir)           // Wheel = switch channels (like Looper)
        elsif actionType == "BUTTON" then
            ToggleStripMacro()               // Button = toggle macro at grid position
        end
```

To:

```gpscript
    // --- 3: STRIP-CONTROL (Grid: Channel x Theme) ---
    elsif GlobalSystemMode == 3 then
        if actionType == "Y_AXIS" or actionType == "ENCODER" then
            if dir > 0 then FireSystemAction(SysActIdx("STRIP_CH_UP"))
            else FireSystemAction(SysActIdx("STRIP_CH_DOWN")) end
        elsif actionType == "X_AXIS" then
            if dir == -1 then FireSystemAction(SysActIdx("STRIP_THEME_PREV"))
            elsif dir == 1 then FireSystemAction(SysActIdx("STRIP_MACRO_TOGGLE")) end
        elsif actionType == "BUTTON" then
            FireSystemAction(SysActIdx("STRIP_MACRO_TOGGLE"))
        end
```

(Note: the original only had Theme Prev on joystick. Theme Next is added as a role but not wired to a joystick gesture here; it's only reachable via a bound macro. That's fine — the role framework is the main goal.)

- [ ] **Step 5: Refactor SYS-MODE 4 (TIMELINE) branch — only the virtualizable parts**

Change `Global Rackspace.gpscript:10057–10081` from:

```gpscript
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
                    ...
```

To:

```gpscript
        elsif actionType == "X_AXIS" or actionType == "ENCODER" then
            if TimelineSubMode == 0 then
                // PLAY: Part Jump Preview — virtualized so hardware buttons can trigger it
                if dir > 0 then FireSystemAction(SysActIdx("TL_PARTJUMP_NEXT"))
                else FireSystemAction(SysActIdx("TL_PARTJUMP_PREV")) end
            else
                // REC mode — meta-controls stay direct (not virtualized)
                if dir == 1 then
                    FireSystemAction(SysActIdx("TL_REC_SONGPART"))
                elsif dir == -1 then
                    // Left: Cycle Replace -> Overdub -> Discard (meta, stays direct)
                    ...
```

(Keep the `TimelineRecState` cycling logic at `:10068–10079` exactly as-is; it's a meta-control for the recording process itself and must not be virtualized — recording its own state changes would be nonsense.)

- [ ] **Step 6: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors. All symbols referenced (`ChangeVstScope`, `ApplyVstFocusBypass`, `TriggerVstPresetChange`, `CycleChannelScope`, `ClickWidget`, `BTN_Loop_Rec`, `BTN_Loop_Clear`, `PreviewActiveControllerMaps`, `CycleCtrlMap`, `CycleStripChannel`, `CycleStripTheme`, `ToggleStripMacro`, `PartJumpPreview`, `ExecuteRecSongpart`) are called inside `FireSystemAction()` and must exist at `FireSystemAction` compile time.

- [ ] **Step 7: Joystick regression test**

1. Enter SYS-MODE 0. Joystick Y+ → VST scope advances. Y- → reverses. X+ → next preset. X- → prev preset. All via `FireSystemAction` now.
2. Enter SYS-MODE 1. Joystick Y up/down → channel scope cycles. X+ → loop rec. X- → loop clear. Button → loop rec.
3. Enter SYS-MODE 2. Y+ → map restored. X+ → next map. X- → prev map. Button → cycle all maps.
4. Enter SYS-MODE 3. Y up/down → strip channel cycle. X- → theme prev. X+ → strip macro toggle. Button → strip macro toggle.
5. Enter SYS-MODE 4. Part jump still works in PLAY sub-mode. REC state cycling still works in REC sub-mode. PLAY↔REC toggle still works.

- [ ] **Step 8: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(gr): route ProcessSystemNavigation actions through FireSystemAction"
```

---

### Task 20: Add SYSACT_ Parser Branch to LoadControllerMap

**Files:**
- Modify: `Global Rackspace.gpscript:5724` area (map reset — reset SysAction arrays)
- Modify: `Global Rackspace.gpscript:5822` area (parser — insert SYSACT_ branch)

- [ ] **Step 1: Reset SysAction arrays in the map-reset path**

Find the map-reset block around `:5724` (where `LOOPER_CH_MacroIdx[k] = DEF_LOOPER_CH_MacroIdx[k]` etc. runs). Immediately after that `For k` loop (post-`End`), add:

```gpscript
   // --- Reset SysAction reverse-lookup tables for this map-section load ---
   ResetSysActionBindings()
```

- [ ] **Step 2: Insert the SYSACT_ parser branch**

After the `SCRUBBER` branch (`Global Rackspace.gpscript:5821–5822`) and before the `// --- NORMAL LINKS ---` `else` branch (which, post-Task 11, directly follows), insert:

```gpscript
                               elsif valuePart == "SCRUBBER" then
                                   if isSrcCC then SCRUB_CCIdx = sliderIdx else SCRUB_MacroIdx = sliderIdx end

                               // --- SYSTEM ACTION (Isolation Rule: single-entry valuePart only) ---
                               elsif IndexOfSubstring(valuePart, "SYSACT_", false) == 0 then
                                   if IndexOfSubstring(valuePart, "|", false) == -1 then
                                       var actionName : String = TrimString(ReplaceString(valuePart, "SYSACT_", "", false))
                                       var sysActParseIdx : Integer = SysActIdx(actionName)
                                       if sysActParseIdx > -1 then
                                           if isSrcCC then SysAction_ByCC[sliderIdx] = sysActParseIdx
                                           else SysAction_ByMacro[sliderIdx] = sysActParseIdx end
                                       elsif DebugMode then
                                           Trace("SYSACT: Unknown action name '" + actionName + "' on slot " + sliderIdx)
                                       end
                                   elsif DebugMode then
                                       Trace("SYSACT: Multi-assigned valuePart - SYSACT role ignored on slot " + sliderIdx)
                                   end

                               // --- NORMAL LINKS ---
                               else
```

(Note on variable declaration: GPScript requires `var` at function top level. If the enclosing function rejects nested `var` declarations, hoist `actionName` and `sysActParseIdx` to the function's top var block. The exact placement depends on how the existing parser function is structured — read the top of the function before inserting.)

- [ ] **Step 3: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors. If GPScript complains about nested var declarations, move `actionName : String` and `sysActParseIdx : Integer` to the function's top-level var block.

- [ ] **Step 4: Manual parser test**

1. Add `Macro5 = SYSACT_LOOPER_REC` to a test section in `ControllerMaps.txt`.
2. Load the section.
3. Verify via Trace: `SysAction_ByMacro[4]` should equal `SysActIdx("LOOPER_REC")` (i.e. 6 with the current registry).
4. Test the Isolation Rule: change the line to `Macro5 = SYSACT_LOOPER_REC | VST1_GRS:0`. Reload. Verify `SysAction_ByMacro[4] == -1` (parser dropped the SYSACT part) and `Trace` shows the "Multi-assigned valuePart" message in DebugMode.
5. Test unknown action: `Macro5 = SYSACT_NONEXISTENT_ACTION`. Reload. Verify `SysAction_ByMacro[4] == -1` and the "Unknown action name" Trace appears.

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): add SYSACT_ parser branch with Isolation Rule"
```

---

### Task 21: Dispatch SysActions from Macro/CC Hardware Triggers, Gate Timeline Recording

**Files:**
- Modify: `Global Rackspace.gpscript:13201` area (macro `ParameterValueChanged` handler)
- Modify: the CC event handler for single-role dispatch (search for `CF_CCIdx` usage to find it)

- [ ] **Step 1: Read the current macro ParameterValueChanged handler for context**

Read `Global Rackspace.gpscript:13195–13210` to see the existing structure of the Timeline recording block.

- [ ] **Step 2: Insert SysAction dispatch before the Timeline recording block**

Change `Global Rackspace.gpscript:13200–13205` from:

```gpscript
       // TIMELINE RECORDING FOR MACROS (SWITCHES ONLY)
       if (RecordMode > 0 or TimelineRecActive) and IsPerformanceActive then
           if newVal == 1.0 then
               RecordTimelineEvent("Macro", paramIdx)
           end
       end
```

To:

```gpscript
       // SYSTEM ACTION DISPATCH (hardware-macro path)
       // Reverse-lookup is O(1); Isolation Rule guarantees exclusivity.
       if newVal > 0.5 and paramIdx >= 0 and paramIdx < MAX_MACROS then
           if SysAction_ByMacro[paramIdx] > -1 then
               FireSystemAction(SysAction_ByMacro[paramIdx])
           end
       end

       // TIMELINE RECORDING FOR MACROS (SWITCHES ONLY)
       // System-action macros are excluded by design — their behavior should not
       // be recorded/replayed through the Timeline (see Isolation Rule).
       if (RecordMode > 0 or TimelineRecActive) and IsPerformanceActive then
           if newVal == 1.0 and not IsSystemActionMacro(paramIdx) then
               RecordTimelineEvent("Macro", paramIdx)
           end
       end
```

- [ ] **Step 3: Find the CC hardware dispatch site**

Run: Grep for `CF_CCIdx` in `Global Rackspace.gpscript` with `-n` and identify the MIDI CC event handler that dispatches `CROSSFADER`, `SCRUBBER`, etc. CC bindings. Note the line number.

- [ ] **Step 4: Add SysAction CC dispatch in that handler**

In the MIDI CC handler identified in Step 3, near the existing `if ccNum == CF_CCIdx` / `if ccNum == SCRUB_CCIdx` checks, add (at a sensible point — ideally before the first legacy check so SysAction takes precedence if both happen to match, though Isolation Rule prevents that by construction):

```gpscript
   // SYSTEM ACTION CC DISPATCH (hardware-CC path)
   if ccNum >= 0 and ccNum < 128 and SysAction_ByCC[ccNum] > -1 then
      // Only fire on press edge (CC value > 64, a standard momentary threshold)
      if ccVal > 64 then FireSystemAction(SysAction_ByCC[ccNum]) end
   end
```

(Use whatever variable names the local handler uses for CC number and value. If the handler lives in an `On ControlChangeEvent` block, `GetCCNumber(m)` and `GetCCValue(m)` are typical.)

- [ ] **Step 5: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors.

- [ ] **Step 6: End-to-end hardware trigger test**

1. Insert `Macro5 = SYSACT_VST_SCOPE_UP` into a test section. Bind macro 5 to a hardware button via HardwareMap (if not already bound). Load the section.
2. Press the hardware button → VST scope advances via `FireSystemAction → ChangeVstScope(1, -1)`. No double-fire.
3. Insert `CC42 = SYSACT_LOOPER_REC` into the section. Send CC42 from hardware with value > 64.
4. Expected: Looper record toggles.

- [ ] **Step 7: Timeline record gating test**

1. Section contains `Macro5 = SYSACT_VST_SCOPE_UP` (exclusive) and `Macro6 = VST1_GRS:0 | SYSACT_VST_SCOPE_UP` (multi-assigned; SYSACT dropped by parser).
2. Load section, start timeline recording.
3. Press hardware button for Macro 5 and Macro 6 during recording.
4. Stop recording, inspect `Snap_TL_*` arrays.
5. Expected: entries for Macro 6 present (it's a normal VST link from the parser's POV). Entries for Macro 5 absent (gated by `IsSystemActionMacro`).
6. Play back. VST scope does NOT advance on Macro 5's timeline event (because there is none). Macro 6's event fires `SetParameter(ExternalArranger, 5, 1.0)` which triggers the VST1_GRS link.

- [ ] **Step 8: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): dispatch SysActions from hw triggers and gate Timeline recording"
```

---

### Task 22: Add System Actions Block to LBL_ControllerInfo Display

**Files:**
- Modify: `Global Rackspace.gpscript:2882` area (main scan loop, add `isSysAction` early-skip)
- Modify: `Global Rackspace.gpscript:3018` area (dynamic grouped entries, append System Actions block)

- [ ] **Step 1: Read the current scan loop and grouped-entries block for context**

Read `Global Rackspace.gpscript:2882–3030` to see the exact structure.

- [ ] **Step 2: Add `isSysAction` early-skip check inside the scan loop**

Inside the main `For s = 0; s < MAX_MACROS; s = s + 1 Do` loop (the one fixed in Task 9), after the `isGroupedDisp` detection but before the CROSSFADER/SCRUBBER/... branches (around line 2935 where `if isGroupedDisp then ... elsif (not isCC and s == CF_MacroIdx) ...`), insert:

```gpscript
           // --- SYSTEM ACTION SKIP (rendered separately below) ---
           var isSysActionSlot : Boolean = false
           if not isCC and s >= 0 and s < MAX_MACROS then
              if SysAction_ByMacro[s] > -1 then isSysActionSlot = true end
           elsif isCC and s >= 0 and s < 128 then
              if SysAction_ByCC[s] > -1 then isSysActionSlot = true end
           end

           if isSysActionSlot then
              // handled in the System Actions block at the bottom of this function
           elsif isGroupedDisp then
               // Intentionally left empty! The dynamic grouped entry is built below.
```

(The existing `if isGroupedDisp then ... end` block becomes `elsif isGroupedDisp then ... end` — chain it after the `if isSysActionSlot`. Preserve everything that was inside the original `if isGroupedDisp` branch.)

- [ ] **Step 3: Add the System Actions display block**

Immediately after the dynamic grouped-entries `For g = 0; g < Grp_Count` loop ends at approximately `:3027`, insert:

```gpscript
   // --- SYSTEM ACTIONS DISPLAY ---
   // Walk the reverse-lookup tables and render bindings grouped by action.
   var sysActHasAny : Boolean = false
   var sysActDispAct, sysActDispMac, sysActDispCC : Integer
   For sysActDispMac = 0; sysActDispMac < MAX_MACROS; sysActDispMac = sysActDispMac + 1 Do
      if SysAction_ByMacro[sysActDispMac] > -1 then sysActHasAny = true end
   End
   if not sysActHasAny then
      For sysActDispCC = 0; sysActDispCC < 128; sysActDispCC = sysActDispCC + 1 Do
         if SysAction_ByCC[sysActDispCC] > -1 then sysActHasAny = true end
      End
   end

   if sysActHasAny then
      CtrlInfo_Lines <-- ""
      CtrlInfo_Lines <-- ">> System Actions (Virtual Roles) <<"
      For sysActDispAct = 0; sysActDispAct < Size(SysAction_Names); sysActDispAct = sysActDispAct + 1 Do
         // All macro slots bound to this action
         For sysActDispMac = 0; sysActDispMac < MAX_MACROS; sysActDispMac = sysActDispMac + 1 Do
            if SysAction_ByMacro[sysActDispMac] == sysActDispAct then
               CtrlInfo_Lines <-- "  Macro " + (sysActDispMac + 1) + GetAssignedHWString(sysActDispMac) + ": " + SysAction_Labels[sysActDispAct]
            end
         End
         // All CC numbers bound to this action
         For sysActDispCC = 0; sysActDispCC < 128; sysActDispCC = sysActDispCC + 1 Do
            if SysAction_ByCC[sysActDispCC] == sysActDispAct then
               CtrlInfo_Lines <-- "  " + GetStandardCCName(sysActDispCC) + " [CC" + sysActDispCC + "]: " + SysAction_Labels[sysActDispAct]
            end
         End
      End
   end
```

(If GPScript requires all `var` declarations at function top, hoist `sysActHasAny`, `sysActDispAct`, `sysActDispMac`, `sysActDispCC`, and `isSysActionSlot` to the function's top var block.)

- [ ] **Step 4: Verify Global Rackspace script compiles**

Press Compile. Expected: no errors. If nested `var` declarations fail, hoist all new vars to the function's top-level var block.

- [ ] **Step 5: Manual display test**

1. Insert `Macro5 = SYSACT_VST_SCOPE_UP`, `Macro6 = SYSACT_LOOPER_REC`, `CC42 = SYSACT_LOOPER_REC` (redundant binding) into a test section.
2. Load the section.
3. Observe `LBL_ControllerInfo`. Expected:
   - No raw "Macro 5:" or "Macro 6:" entries in the normal-link area (the `isSysActionSlot` skip hides them)
   - A new `>> System Actions (Virtual Roles) <<` block at the bottom with three lines:
     - `Macro 5 [<hardware>]: VST Scope [Next]`
     - `Macro 6 [<hardware>]: Looper Record`
     - `Standard CC Name [CC42]: Looper Record`
4. Test redundancy: press both Macro 6 and send CC42 → Looper Rec fires twice (idempotent since it's `ClickWidget`).

- [ ] **Step 6: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(gr): render System Actions block in LBL_ControllerInfo with reverse-lookup walk"
```

---

### Task 23: Final End-to-End Verification

**Files:**
- None (manual)

- [ ] **Step 1: Feature A complete path**

1. Restart rackspace.
2. Activate Vel Range on a channel, set a narrow range, toggle Vel Tamper.
3. Play at edge velocities. Confirm fade behavior.
4. Save and reload a snapshot. Confirm Vel Tamper state restores.

- [ ] **Step 2: Feature B complete path**

1. `LBL_ControllerInfo` shows all 10 groups including Octaver, Humanizer, Scale Quantizer, Auto Sustain (previously invisible).
2. Joystick in all 5 SYS-MODEs works identically to pre-refactor.
3. Save a map section — no `LOOPER_CH*` etc. lines emitted.
4. Load a section with stray legacy lines — they're silently ignored.

- [ ] **Step 3: Feature C complete path**

1. `Macro5 = SYSACT_VST_SCOPE_UP` works via hardware button. Displays under "System Actions".
2. Multi-assigned `Macro6 = VST1_GRS:0 | SYSACT_VST_SCOPE_UP` drops SYSACT part and works as normal link. Does NOT display under "System Actions".
3. Timeline record/playback: exclusive SysAct macros excluded; multi-assigned macros record as normal.
4. Joystick SYS-MODE actions still work (they now go through `FireSystemAction`).
5. Redundant bindings work: two macros → same SysAction → both trigger it.
6. `SYSACT_CTRLMAP_RESTORE` bound to a hardware button → restores initial controller map.
7. Strip Theme Next via `SYSACT_STRIP_THEME_NEXT` bound to a hardware button → cycles forward.

- [ ] **Step 4: No compile errors anywhere**

Full project compile check on both `Note Prozessor.gpscript` and `Global Rackspace.gpscript`.

- [ ] **Step 5: Final commit marker**

```bash
git commit --allow-empty -m "chore: vel tamper + macro refactor + sysact framework landed"
```
