# LFO v2 — Scope-Driven Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the LFO subsystem from Plan #3's flat registry + standalone browser to a scope-driven inspector with cross-map multi-bind display, a draft editor backed by `[LFO:Standard]`, and smart auto-jump on song load.

**Architecture:** Single-file change in `Global Rackspace.gpscript`. New runtime state: four parallel reverse-index arrays (`LFO_Usage_*`) built by scanning `ControllerMaps.txt` at bootstrap and after every mutation. New display pipeline: `LFOBind_Lines` populated by `BuildLFOBindLines(lfoIdx)` and paginated through the new `SLD_LFOBoundMacro` scrollbar, mirroring the `LBL_LooperConfiguration` pattern. New inspector state machine with four states (LOCKED/EDIT/DRAFT_STANDARD/DRAFT_FALLBACK) resolved in `RefreshLFOInspector()`. New button `BTN_Bind_Macro` performs create-or-update on the registry plus a ControllerMaps.txt mutation with a user-zone whitelist and a 1-second flash surface on `LBL_LFO_BoundMacro`. Deletes the standalone LFO browser (`BTN_LFO_Prev/Next`) and its state (`LFO_SelectedIdx`, `LFO_ManualRun`).

**Tech Stack:** GPScript 5.x in Gig Performer 5. No test framework — verification is via `if DebugMode then Trace(...)` statements that the user inspects in the GP script console (or via OSC-to-Geisterhand + Clipboard when `CrashDebugMode = true`).

**Spec:** `docs/superpowers/specs/2026-04-11-lfo-v2-scope-driven-inspector-design.md`

**Base:** Built on top of commits `6252dab` → `91cf48d` (Plan #3 LFO v1) + `91d8e53` (TimerTick guard) + `768b14b` (CrashDebugMode) on branch `feat/lfo-looper-bypass`.

---

## File Structure

**Single file modified:** `Global Rackspace.gpscript`

All changes are localized to this file. No new files. Touched sections:

| Section | Change |
|---|---|
| SECTION 5 (GUI Widget Handles) | Add `BTN_Bind_Macro`, `SLD_LFOBoundMacro`. Delete `BTN_LFO_Prev`, `BTN_LFO_Next`. |
| SECTION 6 (Engine State) | Add `LFO_Usage_*` (4 arrays), `LFOBind_Lines`, `LFO_Draft_*` block, `LFOFlashMsg`, `LFOFlashTimer`. Delete `LFO_SelectedIdx`, `LFO_ManualRun`. |
| SECTION 13 (Core Utilities) | New: `BuildLFOUsageIndex`, `BuildLFOBindLines`, `RefreshLFOBoundMacroDisplay`, rewritten `RefreshLFOInspector`. Modify `TickLFOs` for the draft preview branch. |
| Bootstrap PHASE 4 (Init block) | Initialize new state arrays. |
| Bootstrap PHASE 5 (Init block) | Call `BuildLFOUsageIndex()` after `LoadLFOConfig()`. |
| `LoadSongSnapshot` (end) | Auto-jump `CurrentEditScope` to first bound LFO macro. |
| `UpdateEditScopeDisplay` | Rename `(All Sliders)` → `(All User Macros)`. |
| SECTION 25-26 (Callbacks) | Add `BTN_Bind_Macro` callback. Rework `BTN_LFO_Save`, `BTN_LFO_Delete`, `BTN_LFO_Run`. Delete `BTN_LFO_Prev/Next` callbacks. Rework cycle callbacks to operate on `LFO_Draft_*` in DRAFT state. |

---

## Task 1: State declarations and widget cleanup

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 5 (Widget Handles) and SECTION 6 (Engine State)

This task adds all new declarations and removes the Plan #3 declarations that v2 replaces, in one commit so the file compiles consistently at every step afterward.

- [ ] **Step 1: Add new widget declarations in SECTION 5**

Grep for `BTN_LFO_Prev, BTN_LFO_Next` to locate the existing LFO Inspector block (from Plan #3 Task 7). Replace that block with the new widget declarations:

Find:
```gpscript
   // LFO Inspector (new)
   BTN_LFO_Prev, BTN_LFO_Next                                     : Widget
   LBL_LFO, LBL_LFO_BoundMacro                                    : Widget
   BTN_LFO_Type_Prev, BTN_LFO_Type_Next, LBL_LFO_Type             : Widget
   BTN_LFO_Rate_Prev, BTN_LFO_Rate_Next, LBL_LFO_Rate             : Widget
   BTN_LFO_Cycles_Prev, BTN_LFO_Cycles_Next, LBL_LFO_Cycles       : Widget
   METER_LFO_H, METER_LFO_V                                       : Widget
   BTN_LFO_Run, BTN_LFO_Save, BTN_LFO_Delete                      : Widget
```

Replace with:
```gpscript
   // LFO Inspector (v2 — scope-driven)
   LBL_LFO, LBL_LFO_BoundMacro, SLD_LFOBoundMacro                 : Widget
   BTN_LFO_Type_Prev, BTN_LFO_Type_Next, LBL_LFO_Type             : Widget
   BTN_LFO_Rate_Prev, BTN_LFO_Rate_Next, LBL_LFO_Rate             : Widget
   BTN_LFO_Cycles_Prev, BTN_LFO_Cycles_Next, LBL_LFO_Cycles       : Widget
   METER_LFO_H, METER_LFO_V                                       : Widget
   BTN_LFO_Run, BTN_LFO_Save, BTN_LFO_Delete, BTN_Bind_Macro      : Widget
```

Changes:
- Removed: `BTN_LFO_Prev`, `BTN_LFO_Next` (standalone browser gone)
- Added: `SLD_LFOBoundMacro` on the first widget line (scrollbar for the bound-macro list)
- Added: `BTN_Bind_Macro` on the last widget line (new bind action)

- [ ] **Step 2: Add new state declarations in SECTION 6**

Grep for `LFO_ByMacro : Integer Array` to locate the LFO state block from Plan #3 Task 2. Below the existing registry and runtime-state arrays, replace the v1 browser-cursor lines and append the v2 state:

Find:
```gpscript
   // Inspector browser cursors
   LFO_SelectedIdx : Integer = 0    // which registry entry is shown in the inspector
   LFO_ManualRun   : Boolean = false // true while BTN_LFO_Run is in the ON state without a macro trigger
```

Replace with:
```gpscript
   // v2: cross-map reverse index — four parallel arrays, all indexed 0..N
   // by binding number. Rebuilt by BuildLFOUsageIndex() at bootstrap and
   // after every mutation path that rewrites ControllerMaps.txt.
   LFO_Usage_LfoIdx    : Integer Array   // which LFO_Names[] entry
   LFO_Usage_MapIdx    : Integer Array   // which CtrlMapList[] entry
   LFO_Usage_MacroIdx  : Integer Array   // which macro slot (0..49)
   LFO_Usage_RawLine   : String Array    // cached raw `Macro<N> = <value>` line

   // v2: display pipeline — LBL_LFO_BoundMacro is a scrollable list backed
   // by this array and paginated via SLD_LFOBoundMacro. Matches the
   // LooperConfig_Lines / CtrlInfo_Lines pattern.
   LFOBind_Lines : String Array

   // v2: draft state — populated when the inspector is in DRAFT_STANDARD or
   // DRAFT_FALLBACK. Lives only while a no-LFO scope is focused.
   LFO_Draft_Active : Boolean = false
   LFO_Draft_Name   : String  = ""
   LFO_Draft_Type   : Integer = 0   // Triangle
   LFO_Draft_Rate   : Integer = 5   // 1/4
   LFO_Draft_Cycles : Integer = -1  // Infinite

   // v2: draft preview — one global slot for BTN_LFO_Run in DRAFT state.
   // TickLFOs() services this via a dedicated branch. Never persisted.
   LFO_Draft_Running   : Boolean = false
   LFO_Draft_Slot      : Integer = -1
   LFO_Draft_StartTime : Double  = 0.0
   LFO_Draft_PreValue  : Double  = 0.0

   // v2: flash surface for LBL_LFO_BoundMacro — 1-second transient feedback
   // from BTN_Bind_Macro's whitelist check and EDIT-state "already bound"
   // diagnostic.
   LFOFlashMsg   : String = ""
   LFOFlashTimer : Double = 0.0
```

- [ ] **Step 3: Initialize new arrays in Bootstrap PHASE 4**

Grep for `LFO: state arrays initialized` (from Plan #3 Task 2's bootstrap init) to locate the PHASE 4 LFO block. Immediately after the existing `if DebugMode then Trace("LFO: state arrays initialized...")` line, append:

```gpscript
   // v2: reverse index and display state
   LFO_Usage_LfoIdx    = []
   LFO_Usage_MapIdx    = []
   LFO_Usage_MacroIdx  = []
   LFO_Usage_RawLine   = []
   LFOBind_Lines       = []

   LFO_Draft_Active    = false
   LFO_Draft_Name      = ""
   LFO_Draft_Type      = 0
   LFO_Draft_Rate      = 5
   LFO_Draft_Cycles    = -1
   LFO_Draft_Running   = false
   LFO_Draft_Slot      = -1
   LFO_Draft_StartTime = 0.0
   LFO_Draft_PreValue  = 0.0

   LFOFlashMsg   = ""
   LFOFlashTimer = 0.0

   if DebugMode then Trace("LFO v2: reverse index + draft + flash state initialized") end
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): declare reverse-index + draft + flash state

Replaces the LFO v1 browser cursors (LFO_SelectedIdx, LFO_ManualRun)
with the v2 state set:
- Four parallel LFO_Usage_* arrays for the cross-map reverse index
- LFOBind_Lines for the scrollable bound-macro display
- LFO_Draft_* block for the DRAFT_STANDARD / DRAFT_FALLBACK state
- LFO_Draft_Running / Slot / StartTime / PreValue for the BTN_LFO_Run
  draft-preview path
- LFOFlashMsg / LFOFlashTimer for the 1-second transient feedback
  surface on LBL_LFO_BoundMacro

Widget declarations: added BTN_Bind_Macro and SLD_LFOBoundMacro,
removed BTN_LFO_Prev and BTN_LFO_Next. Bootstrap PHASE 4 initializes
all new state to neutral defaults."
```

---

## Task 2: `BuildLFOUsageIndex` and bootstrap wiring

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 13 (Core Utilities) and Bootstrap PHASE 5

- [ ] **Step 1: Add `BuildLFOUsageIndex()` in SECTION 13**

Grep for `Function LoadLFOConfig()` to find the LFO parser block. Add the new function immediately after `LoadLFOConfig()` ends (before `SampleLFOWaveform`):

```gpscript
// ---------------------------------------------------------
// BUILD LFO USAGE INDEX (v2)
// Scans ControllerMaps.txt for every `Macro<N> = LFO:<Name> | ...`
// line across every [Map:...] section and populates the four
// parallel LFO_Usage_* arrays with (lfoIdx, mapIdx, macroIdx,
// rawLine) tuples. Orphan prefixes (LFO name not in registry) are
// DebugMode-traced and skipped.
//
// Called from bootstrap PHASE 5 after LoadLFOConfig, and from every
// BTN_* callback that mutates ControllerMaps.txt.
// ---------------------------------------------------------
Function BuildLFOUsageIndex()
   var content, section, line, mapName, valuePart : String
   var rawLine, lfoName, firstEntry : String
   var sectionStart, sectionEnd, lineStart, lineEnd, eqPos, pipePos : Integer
   var macroSlot, lfoIdx, mapIdx, i, n, bindingCount : Integer
   var lines : String Array

   LFO_Usage_LfoIdx   = []
   LFO_Usage_MapIdx   = []
   LFO_Usage_MacroIdx = []
   LFO_Usage_RawLine  = []
   bindingCount = 0

   if not FileExists(ControllerMapFilePath) then
       if DebugMode then Trace("LFO v2: BuildLFOUsageIndex skipped, ControllerMaps.txt not found") end
   else
       content = LoadStringFromTextFile(ControllerMapFilePath)

       // Walk every [Map:...] header
       sectionStart = IndexOfSubstring(content, "[Map:", false)
       While sectionStart > -1 Do
          // Extract map name from "[Map:<name>]"
          lineEnd = IndexOfSubstring(CopySubstring(content, sectionStart, Length(content) - sectionStart), "]", false)
          if lineEnd < 0 then
              sectionStart = -1
          else
              mapName = CopySubstring(content, sectionStart + 5, lineEnd - 5)

              // Look up mapName in CtrlMapList
              mapIdx = -1
              For i = 0; i < Size(CtrlMapList); i = i + 1 Do
                 if CtrlMapList[i] == mapName then mapIdx = i end
              End

              // Find section body bounds: from end of header line to next [Map: or EOF
              sectionEnd = IndexOfSubstring(CopySubstring(content, sectionStart + lineEnd + 1, Length(content) - (sectionStart + lineEnd + 1)), "[Map:", false)
              if sectionEnd > -1 then
                  section = CopySubstring(content, sectionStart + lineEnd + 1, sectionEnd)
              else
                  section = CopySubstring(content, sectionStart + lineEnd + 1, Length(content) - (sectionStart + lineEnd + 1))
              end

              // Scan every non-comment Macro<N> = line for LFO: prefix
              lines = SplitString(section, NEW_LINE)
              For n = 0; n < Size(lines); n = n + 1 Do
                 line = TrimString(lines[n])
                 if Length(line) > 0 and IndexOfSubstring(line, ";", false) != 0 and IndexOfSubstring(line, "Macro", false) == 0 then
                     eqPos = IndexOfSubstring(line, "=", false)
                     if eqPos > 0 then
                         // Extract macro slot number
                         macroSlot = StringToInt(TrimString(ReplaceString(CopySubstring(line, 0, eqPos), "Macro", "", false))) - 1
                         valuePart = TrimString(CopySubstring(line, eqPos + 1, Length(line) - (eqPos + 1)))

                         // Check if first |-entry starts with LFO:
                         pipePos = IndexOfSubstring(valuePart, "|", false)
                         if pipePos >= 0 then
                             firstEntry = TrimString(CopySubstring(valuePart, 0, pipePos))
                         else
                             firstEntry = valuePart
                         end

                         if IndexOfSubstring(firstEntry, "LFO:", false) == 0 then
                             lfoName = TrimString(ReplaceString(firstEntry, "LFO:", "", false))

                             // Registry lookup
                             lfoIdx = -1
                             For i = 0; i < Size(LFO_Names); i = i + 1 Do
                                if LFO_Names[i] == lfoName then lfoIdx = i end
                             End

                             if lfoIdx < 0 then
                                 if DebugMode then Trace("LFO v2: orphan binding '" + lfoName + "' in [" + mapName + "] Macro" + (macroSlot + 1) + ", not in registry") end
                             elsif macroSlot < 0 or macroSlot >= 50 then
                                 if DebugMode then Trace("LFO v2: binding '" + lfoName + "' in [" + mapName + "] Macro" + (macroSlot + 1) + " outside user zone, skipped") end
                             elsif mapIdx < 0 then
                                 if DebugMode then Trace("LFO v2: binding '" + lfoName + "' in unknown map '" + mapName + "', skipped") end
                             else
                                 LFO_Usage_LfoIdx   <-- lfoIdx
                                 LFO_Usage_MapIdx   <-- mapIdx
                                 LFO_Usage_MacroIdx <-- macroSlot
                                 LFO_Usage_RawLine  <-- line
                                 bindingCount = bindingCount + 1
                             end
                         end
                     end
                 end
              End

              // Advance to next section by chopping the prefix we just consumed
              content = CopySubstring(content, sectionStart + 1, Length(content) - (sectionStart + 1))
              sectionStart = IndexOfSubstring(content, "[Map:", false)
          end
       End
   end

   if DebugMode then Trace("LFO v2: BuildLFOUsageIndex complete, " + bindingCount + " bindings across all maps") end
End
```

- [ ] **Step 2: Call `BuildLFOUsageIndex()` in Bootstrap PHASE 5**

Grep for `LoadLFOConfig()` (should find the call site in bootstrap added by Plan #3 Task 3). Add the new call immediately after it:

Find:
```gpscript
   LoadLFOConfig()   // <- NEW: populate registry after arrays are zeroed
```

Replace with:
```gpscript
   LoadLFOConfig()   // v1: populate registry after arrays are zeroed
   BuildLFOUsageIndex()  // v2: scan ControllerMaps.txt for bindings
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): BuildLFOUsageIndex scans ControllerMaps for bindings

Walks every [Map:...] section in ControllerMaps.txt and every
Macro<N> = ... line inside. When the first |-separated entry starts
with LFO:<Name>, looks up the name in LFO_Names and appends a
(lfoIdx, mapIdx, macroIdx, rawLine) tuple to the four parallel
LFO_Usage_* arrays. Orphans and out-of-zone bindings are
DebugMode-traced and skipped.

Bootstrap PHASE 5 calls BuildLFOUsageIndex right after LoadLFOConfig
so the reverse index is populated before any UI renders."
```

---

## Task 3: `BuildLFOBindLines` and `RefreshLFOBoundMacroDisplay`

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 13 (Core Utilities)

- [ ] **Step 1: Add `BuildLFOBindLines(lfoIdx)` in SECTION 13**

Add immediately after `BuildLFOUsageIndex()`:

```gpscript
// ---------------------------------------------------------
// BUILD LFO BIND LINES (v2)
// Populates LFOBind_Lines with the head-line-only display of every
// binding for a given LFO, grouped by map. Called from
// RefreshLFOInspector() in EDIT state.
//
// For active-map bindings, the head line uses Link_* arrays (the
// same pattern as CtrlInfo_Lines at ~line 3154). For inactive-map
// bindings, the raw Macro<N> = ... line is re-parsed verbatim to
// extract the first target without touching plugin state.
// ---------------------------------------------------------
Function BuildLFOBindLines(lfoIdx : Integer)
   var i, j, mapIdx, macroSlot, firstTargetLink : Integer
   var currentMapIdx : Integer = -1
   var hwStr, headLine, rawLine, valuePart, firstEntry, realName, valStr : String
   var vMin, vMax : Integer
   var eqPos, pipePos, lfoPipePos : Integer
   var sortedBinding : Integer Array
   var b, b2, tmp : Integer

   LFOBind_Lines = []

   if lfoIdx < 0 or lfoIdx >= Size(LFO_Names) then
       // Defensive — caller should not pass invalid index
       if DebugMode then Trace("LFO v2: BuildLFOBindLines called with invalid lfoIdx=" + lfoIdx) end
   else
       LFOBind_Lines <-- "--- LFO BINDINGS: " + LFO_Names[lfoIdx] + " ---"

       // Collect bindings for this LFO, sorted by (mapIdx, macroSlot)
       sortedBinding = []
       For i = 0; i < Size(LFO_Usage_LfoIdx); i = i + 1 Do
          if LFO_Usage_LfoIdx[i] == lfoIdx then sortedBinding <-- i end
       End

       // Bubble-sort by (mapIdx, macroSlot) — binding counts are tiny
       For b = 0; b < Size(sortedBinding); b = b + 1 Do
          For b2 = b + 1; b2 < Size(sortedBinding); b2 = b2 + 1 Do
             if LFO_Usage_MapIdx[sortedBinding[b]] > LFO_Usage_MapIdx[sortedBinding[b2]] then
                 tmp = sortedBinding[b]; sortedBinding[b] = sortedBinding[b2]; sortedBinding[b2] = tmp
             elsif LFO_Usage_MapIdx[sortedBinding[b]] == LFO_Usage_MapIdx[sortedBinding[b2]] then
                 if LFO_Usage_MacroIdx[sortedBinding[b]] > LFO_Usage_MacroIdx[sortedBinding[b2]] then
                     tmp = sortedBinding[b]; sortedBinding[b] = sortedBinding[b2]; sortedBinding[b2] = tmp
                 end
             end
          End
       End

       // Emit grouped head lines
       For i = 0; i < Size(sortedBinding); i = i + 1 Do
          j = sortedBinding[i]
          mapIdx = LFO_Usage_MapIdx[j]
          macroSlot = LFO_Usage_MacroIdx[j]

          if mapIdx != currentMapIdx then
              LFOBind_Lines <-- "[Map: " + CtrlMapList[mapIdx] + "]"
              currentMapIdx = mapIdx
          end

          hwStr = GetAssignedHWString(macroSlot)

          // Active-map vs inactive-map
          if CtrlMapList[mapIdx] == CurrentCtrlMapName then
              // Active map: look up first Link_* for this macro slot
              firstTargetLink = -1
              For b = 0; b < Link_Count; b = b + 1 Do
                 if Link_Active[b] and Link_SourceIdx[b] == macroSlot and firstTargetLink == -1 then
                     firstTargetLink = b
                 end
              End

              if firstTargetLink >= 0 then
                  realName = Link_ExpectedName[firstTargetLink]
                  if realName == "" then realName = "Param " + Link_TargetParam[firstTargetLink] end
                  vMin = Round(Link_MinVal[firstTargetLink] * 100.0)
                  vMax = Round(Link_MaxVal[firstTargetLink] * 100.0)
                  if vMin != 0 or vMax != 100 then valStr = " {" + vMin + "%-" + vMax + "%}" else valStr = "" end
                  headLine = "  Macro " + (macroSlot + 1) + hwStr + ": " + Link_BlockName[firstTargetLink] + ":" + realName + valStr
              else
                  headLine = "  Macro " + (macroSlot + 1) + hwStr + ": (no target)"
              end
          else
              // Inactive map: re-parse raw line, extract first non-LFO |-entry
              rawLine = LFO_Usage_RawLine[j]
              eqPos = IndexOfSubstring(rawLine, "=", false)
              valuePart = ""
              if eqPos >= 0 then
                  valuePart = TrimString(CopySubstring(rawLine, eqPos + 1, Length(rawLine) - (eqPos + 1)))
              end

              // Strip leading LFO:<Name> | prefix
              lfoPipePos = IndexOfSubstring(valuePart, "|", false)
              if lfoPipePos >= 0 then
                  valuePart = TrimString(CopySubstring(valuePart, lfoPipePos + 1, Length(valuePart) - (lfoPipePos + 1)))
              else
                  valuePart = ""
              end

              // Take first |-entry after the LFO prefix
              pipePos = IndexOfSubstring(valuePart, "|", false)
              if pipePos >= 0 then
                  firstEntry = TrimString(CopySubstring(valuePart, 0, pipePos))
              else
                  firstEntry = valuePart
              end

              if firstEntry == "" then
                  headLine = "  Macro " + (macroSlot + 1) + hwStr + ": (no target)"
              else
                  headLine = "  Macro " + (macroSlot + 1) + hwStr + ": " + firstEntry
              end
          end

          LFOBind_Lines <-- headLine
       End

       if DebugMode then Trace("LFO v2: BuildLFOBindLines built " + Size(LFOBind_Lines) + " lines for '" + LFO_Names[lfoIdx] + "'") end
   end
End
```

- [ ] **Step 2: Add `RefreshLFOBoundMacroDisplay()` in SECTION 13**

Add immediately after `BuildLFOBindLines`:

```gpscript
// ---------------------------------------------------------
// REFRESH LFO BOUND MACRO DISPLAY (v2)
// Paginates LFOBind_Lines through SLD_LFOBoundMacro into
// LBL_LFO_BoundMacro. Mirrors RefreshLooperConfigDisplay at ~4043.
// Honors the LFOFlashTimer surface: while the timer is active, the
// LFOFlashMsg is prepended as the first line and the body follows.
// ---------------------------------------------------------
Function RefreshLFOBoundMacroDisplay()
   var scrollVal : Double = GetWidgetValue(SLD_LFOBoundMacro)
   var totalLines, displayLines, maxStart, startIdx, i : Integer
   var finalText : String = ""

   displayLines = 10   // Adjust to the LBL_LFO_BoundMacro widget's line capacity

   // Flash message takes priority
   if LFOFlashTimer > 0.0 and TimeSinceStartup() < LFOFlashTimer then
       finalText = "[" + LFOFlashMsg + "]" + NEW_LINE + NEW_LINE
   elsif LFOFlashTimer > 0.0 then
       // Timer expired — clear the stale state
       LFOFlashTimer = 0.0
       LFOFlashMsg = ""
   end

   totalLines = Size(LFOBind_Lines)
   maxStart = totalLines - displayLines
   if maxStart < 0 then maxStart = 0 end
   startIdx = Round((1.0 - scrollVal) * IntToFloat(maxStart))

   For i = 0; i < displayLines; i = i + 1 Do
      if (startIdx + i) < totalLines then
          finalText = finalText + LFOBind_Lines[startIdx + i] + NEW_LINE
      end
   End

   SetWidgetLabel(LBL_LFO_BoundMacro, finalText)
End
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): BuildLFOBindLines + RefreshLFOBoundMacroDisplay

BuildLFOBindLines(lfoIdx) walks LFO_Usage_* for the given LFO,
groups bindings by map, sorts map-first then macro-first, and emits
a head-line-only list to LFOBind_Lines. Active-map bindings render
via Link_* (same pattern as CtrlInfo_Lines). Inactive-map bindings
re-parse the cached raw line from LFO_Usage_RawLine to extract the
first target without touching plugin state.

RefreshLFOBoundMacroDisplay paginates LFOBind_Lines through
SLD_LFOBoundMacro into LBL_LFO_BoundMacro, matching the
RefreshLooperConfigDisplay pattern. Honors the LFOFlashTimer surface:
while active, LFOFlashMsg is prepended to the display."
```

---

## Task 4: `RefreshLFOInspector` rewrite + draft-mode cycle callbacks

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 13 (rewrite `RefreshLFOInspector`), SECTION 25-26 (rewrite Type/Rate/Cycles callbacks)

- [ ] **Step 1: Replace the Plan #3 `RefreshLFOInspector` in SECTION 13**

Grep for `Function RefreshLFOInspector` — this is the v1 helper added in Plan #3 Task 8. Replace its entire body with the v2 version:

```gpscript
// ---------------------------------------------------------
// REFRESH LFO INSPECTOR (v2)
// Scope-driven state machine. The displayed LFO is a pure function
// of CurrentEditScope and the registry / LFO_ByMacro state.
//
// Four states:
//   LOCKED          — scope is -1 or >= 50 (not a user macro)
//   EDIT            — scope has a real LFO bound (LFO_ByMacro[slot] >= 0)
//   DRAFT_STANDARD  — scope has no LFO, [LFO:Standard] exists
//   DRAFT_FALLBACK  — scope has no LFO, no [LFO:Standard]
// ---------------------------------------------------------
Function RefreshLFOInspector()
   var scopeSlot, lfoIdx, standardIdx, i, boundSlot : Integer
   var inDraft : Boolean = false

   scopeSlot = CurrentEditScope
   lfoIdx = -1

   if scopeSlot < 0 or scopeSlot >= 50 then
       // LOCKED state
       SetWidgetLabel(LBL_LFO, "-")
       SetWidgetLabel(LBL_LFO_Type, "-")
       SetWidgetLabel(LBL_LFO_Rate, "-")
       SetWidgetLabel(LBL_LFO_Cycles, "-")
       LFOBind_Lines = []
       LFOBind_Lines <-- "Only User Macros allowed (scope 1-50)"
       LFO_Draft_Active = false
       SetWidgetValue(METER_LFO_H, 0.0)
       SetWidgetValue(METER_LFO_V, 0.0)
       if DebugMode then Trace("LFO v2: inspector LOCKED (scope=" + scopeSlot + ")") end
   else
       lfoIdx = LFO_ByMacro[scopeSlot]

       if lfoIdx >= 0 then
           // EDIT state
           LFO_Draft_Active = false
           SetWidgetLabel(LBL_LFO, LFO_Names[lfoIdx])
           SetWidgetLabel(LBL_LFO_Type, LFOTypeName(LFO_Types[lfoIdx]))
           SetWidgetLabel(LBL_LFO_Rate, LFORateName(LFO_Rates[lfoIdx]))
           SetWidgetLabel(LBL_LFO_Cycles, LFOCyclesName(LFO_Cycles[lfoIdx]))
           BuildLFOBindLines(lfoIdx)
           if DebugMode then Trace("LFO v2: inspector EDIT (slot=" + (scopeSlot+1) + " lfo='" + LFO_Names[lfoIdx] + "')") end
       else
           // DRAFT state — look for [LFO:Standard] template
           standardIdx = -1
           For i = 0; i < Size(LFO_Names); i = i + 1 Do
              if LFO_Names[i] == "Standard" then standardIdx = i end
           End

           LFO_Draft_Active = true
           LFO_Draft_Name = CurrentSongName

           if standardIdx >= 0 then
               LFO_Draft_Type   = LFO_Types[standardIdx]
               LFO_Draft_Rate   = LFO_Rates[standardIdx]
               LFO_Draft_Cycles = LFO_Cycles[standardIdx]
               if DebugMode then Trace("LFO v2: inspector DRAFT_STANDARD (slot=" + (scopeSlot+1) + " name='" + LFO_Draft_Name + "')") end
           else
               LFO_Draft_Type   = 0    // Triangle
               LFO_Draft_Rate   = 5    // 1/4
               LFO_Draft_Cycles = -1   // Infinite
               if DebugMode then Trace("LFO v2: inspector DRAFT_FALLBACK (slot=" + (scopeSlot+1) + " name='" + LFO_Draft_Name + "')") end
           end

           SetWidgetLabel(LBL_LFO, LFO_Draft_Name)
           SetWidgetLabel(LBL_LFO_Type, LFOTypeName(LFO_Draft_Type))
           SetWidgetLabel(LBL_LFO_Rate, LFORateName(LFO_Draft_Rate))
           SetWidgetLabel(LBL_LFO_Cycles, LFOCyclesName(LFO_Draft_Cycles))

           LFOBind_Lines = []
           LFOBind_Lines <-- "(draft - bind to save)"
       end
   end

   RefreshLFOBoundMacroDisplay()
End
```

**Note on `CurrentSongName`:** this variable is expected to hold the currently-loaded song name (set by `LoadSongSnapshot`). Grep to confirm the exact name — it may be called `CurrentSong`, `ActiveSongName`, or similar. If the project uses a different name, substitute it here. If no such variable exists, derive from `GetCurrentSongName()` if `InSetlistMode()` is true, otherwise use `"Default"`.

- [ ] **Step 2: Rewrite the six LFO cycle callbacks to handle DRAFT vs EDIT**

Grep for `from BTN_LFO_Type_Next` to locate the six cycle callbacks added by Plan #3 Task 8. Replace each with the v2 version that operates on either the registry (EDIT) or the draft (DRAFT).

Replace `BTN_LFO_Type_Next`:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Type_Next
   var t : Integer
   var lfoIdx : Integer
   if val > 0.5 then
       if LFO_Draft_Active then
           t = LFO_Draft_Type + 1
           if t > 5 then t = 0 end
           LFO_Draft_Type = t
       elsif CurrentEditScope >= 0 and CurrentEditScope < 50 then
           lfoIdx = LFO_ByMacro[CurrentEditScope]
           if lfoIdx >= 0 then
               t = LFO_Types[lfoIdx] + 1
               if t > 5 then t = 0 end
               LFO_Types[lfoIdx] = t
           end
       end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Type_Next, 0.0)
   end
End
```

Replace `BTN_LFO_Type_Prev`:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Type_Prev
   var t : Integer
   var lfoIdx : Integer
   if val > 0.5 then
       if LFO_Draft_Active then
           t = LFO_Draft_Type - 1
           if t < 0 then t = 5 end
           LFO_Draft_Type = t
       elsif CurrentEditScope >= 0 and CurrentEditScope < 50 then
           lfoIdx = LFO_ByMacro[CurrentEditScope]
           if lfoIdx >= 0 then
               t = LFO_Types[lfoIdx] - 1
               if t < 0 then t = 5 end
               LFO_Types[lfoIdx] = t
           end
       end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Type_Prev, 0.0)
   end
End
```

Replace `BTN_LFO_Rate_Next`:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Rate_Next
   var r : Integer
   var lfoIdx : Integer
   if val > 0.5 then
       if LFO_Draft_Active then
           r = LFO_Draft_Rate + 1
           if r > 8 then r = 0 end
           LFO_Draft_Rate = r
       elsif CurrentEditScope >= 0 and CurrentEditScope < 50 then
           lfoIdx = LFO_ByMacro[CurrentEditScope]
           if lfoIdx >= 0 then
               r = LFO_Rates[lfoIdx] + 1
               if r > 8 then r = 0 end
               LFO_Rates[lfoIdx] = r
           end
       end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Rate_Next, 0.0)
   end
End
```

Replace `BTN_LFO_Rate_Prev`:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Rate_Prev
   var r : Integer
   var lfoIdx : Integer
   if val > 0.5 then
       if LFO_Draft_Active then
           r = LFO_Draft_Rate - 1
           if r < 0 then r = 8 end
           LFO_Draft_Rate = r
       elsif CurrentEditScope >= 0 and CurrentEditScope < 50 then
           lfoIdx = LFO_ByMacro[CurrentEditScope]
           if lfoIdx >= 0 then
               r = LFO_Rates[lfoIdx] - 1
               if r < 0 then r = 8 end
               LFO_Rates[lfoIdx] = r
           end
       end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Rate_Prev, 0.0)
   end
End
```

Replace `BTN_LFO_Cycles_Next`:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Cycles_Next
   var c : Integer
   var lfoIdx : Integer
   if val > 0.5 then
       if LFO_Draft_Active then
           c = LFO_Draft_Cycles
           if c == -1 then c = 0
           elsif c == 0 then c = 1
           else c = c + 1 end
           LFO_Draft_Cycles = c
       elsif CurrentEditScope >= 0 and CurrentEditScope < 50 then
           lfoIdx = LFO_ByMacro[CurrentEditScope]
           if lfoIdx >= 0 then
               c = LFO_Cycles[lfoIdx]
               if c == -1 then c = 0
               elsif c == 0 then c = 1
               else c = c + 1 end
               LFO_Cycles[lfoIdx] = c
           end
       end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Cycles_Next, 0.0)
   end
End
```

Replace `BTN_LFO_Cycles_Prev`:
```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Cycles_Prev
   var c : Integer
   var lfoIdx : Integer
   if val > 0.5 then
       if LFO_Draft_Active then
           c = LFO_Draft_Cycles
           if c == 0 then c = -1
           elsif c == -1 then c = 16
           elsif c == 1 then c = 0
           else c = c - 1 end
           LFO_Draft_Cycles = c
       elsif CurrentEditScope >= 0 and CurrentEditScope < 50 then
           lfoIdx = LFO_ByMacro[CurrentEditScope]
           if lfoIdx >= 0 then
               c = LFO_Cycles[lfoIdx]
               if c == 0 then c = -1
               elsif c == -1 then c = 16
               elsif c == 1 then c = 0
               else c = c - 1 end
               LFO_Cycles[lfoIdx] = c
           end
       end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Cycles_Prev, 0.0)
   end
End
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): RefreshLFOInspector state machine + draft-aware cycles

RefreshLFOInspector is now a pure function of CurrentEditScope. Four
states: LOCKED (scope -1 or >=50), EDIT (scope has bound LFO),
DRAFT_STANDARD (no LFO, [LFO:Standard] template), DRAFT_FALLBACK
(no LFO, hardcoded Triangle/1/4/Infinite). Draft state is materialized
in LFO_Draft_* and cleared when leaving draft.

The six LFO_Type/Rate/Cycles_Prev/Next cycle callbacks now operate
on LFO_Draft_* in DRAFT state and on the registry entry in EDIT
state. No file writes from the cycle callbacks — BTN_LFO_Save
persists EDIT changes, BTN_Bind_Macro materialises DRAFT changes."
```

---

## Task 5: Auto-jump and `(All Sliders)` rename

**Files:**
- Modify: `Global Rackspace.gpscript` — `LoadSongSnapshot` (~line 11807 from Plan #3 exploration) and `UpdateEditScopeDisplay` (~line 3217)

- [ ] **Step 1: Rename the GLOBAL fallback label**

Grep for `"Scope: [GLOBAL] (All Sliders)"` to find `UpdateEditScopeDisplay`. Replace the string literal:

Find:
```gpscript
   elsif CurrentEditScope == -1 then
       txt = "Scope: [GLOBAL] (All Sliders)"
```

Replace with:
```gpscript
   elsif CurrentEditScope == -1 then
       txt = "Scope: [GLOBAL] (All User Macros)"
```

- [ ] **Step 2: Add auto-jump at the end of `LoadSongSnapshot`**

Grep for `Function LoadSongSnapshot` to find the function. Scroll to its closing `End`. Immediately before the closing `End`, add the auto-jump block:

Find (near the function's end):
```gpscript
       IsLoadingSnapshot = false
       // ... any final cleanup ...
   Else
       // ... file-not-found handling ...
   End
End
```

Add immediately before `End` of the function, inside the top-level `If FileExists(filePath) Then` branch (i.e. after the snapshot has successfully loaded and before IsLoadingSnapshot is cleared — the exact insertion point is right after `BuildLFOUsageIndex()` would have been called via LoadControllerMap, which itself is called during the snapshot processing loop):

```gpscript
       // v2: smart auto-jump — land on the first macro with an LFO bound
       var jumpSlot : Integer = -1
       var j : Integer
       For j = 0; j < 50; j = j + 1 Do
          if LFO_ByMacro[j] >= 0 and jumpSlot == -1 then jumpSlot = j end
       End
       if jumpSlot >= 0 then
           CurrentEditScope = jumpSlot
           if DebugMode then Trace("LFO v2: auto-jump CurrentEditScope to Macro " + (jumpSlot + 1)) end
       else
           CurrentEditScope = -1
           if DebugMode then Trace("LFO v2: no LFO bindings in this song, scope stays GLOBAL") end
       end
       UpdateEditScopeDisplay()
       RefreshLFOInspector()
```

**Note:** `var jumpSlot : Integer = -1` and `var j : Integer` must be moved to the top of `LoadSongSnapshot` per the GPScript var rule. Grep the function's top `var` block and append `jumpSlot, j : Integer`. If `j` is already declared (likely — it's a common loop var), just add `jumpSlot : Integer` and reuse the existing `j`.

- [ ] **Step 3: Rebuild reverse index after LoadControllerMap inside LoadSongSnapshot**

`LoadControllerMap` is called from within `LoadSongSnapshot` to load the song's assigned map. Because `BuildLFOUsageIndex` depends on the current state of `LFO_ByMacro` (which `LoadControllerMap` populates from the v1 LFO prefix parser in Plan #3 Task 4), we need to rebuild the index after every `LoadControllerMap` call so the auto-jump sees fresh data.

Grep for `LoadControllerMap(targetCtrlMap)` inside `LoadSongSnapshot`. Add immediately after:

```gpscript
   LoadControllerMap(targetCtrlMap)
   BuildLFOUsageIndex()
```

There may be more than one `LoadControllerMap` call inside `LoadSongSnapshot` (e.g. a fallback to `"Standard"`). Add the rebuild call after each.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): auto-jump scope + (All User Macros) rename

At the end of LoadSongSnapshot, after the controller map is loaded
and BuildLFOUsageIndex has run, iterate macro slots 0..49 and set
CurrentEditScope to the first slot with a bound LFO. Falls back to
-1 (GLOBAL) if no slot has an LFO. UpdateEditScopeDisplay and
RefreshLFOInspector are called to sync the display.

UpdateEditScopeDisplay's GLOBAL fallback label is renamed from
'(All Sliders)' to '(All User Macros)' to reflect the actual scope
semantics under the v2 inspector.

BuildLFOUsageIndex is now called after every LoadControllerMap
inside LoadSongSnapshot so the reverse index reflects the newly
loaded map before auto-jump runs."
```

---

## Task 6: `BTN_Bind_Macro` callback and flash mechanism

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 25-26 (new callback)

- [ ] **Step 1: Add the `BTN_Bind_Macro` callback in SECTION 25-26**

Grep for `On WidgetValueChanged(val : Double) from BTN_LFO_Save` to find the v1 LFO callback block. Add the new `BTN_Bind_Macro` callback immediately before it:

```gpscript
On WidgetValueChanged(val : Double) from BTN_Bind_Macro
   var scopeSlot : Integer
   var mapName, lfoName, content, section, newLine, oldLine : String
   var mapSectionStart, mapSectionEnd, lineStart, lineEnd, nlPos : Integer
   var registryIdx, i : Integer
   var saved : Boolean = false
   var searchKey, newValue : String

   if val > 0.5 then
       scopeSlot = CurrentEditScope
       mapName = CurrentCtrlMapName

       // 1. Whitelist check
       if scopeSlot < 0 or scopeSlot >= 50 then
           LFOFlashMsg = "Only User Macros allowed (scope 1-50)"
           LFOFlashTimer = TimeSinceStartup() + 1000.0
           RefreshLFOInspector()
           if DebugMode then Trace("LFO v2: BTN_Bind_Macro rejected, scope " + scopeSlot + " outside user zone") end
           SetWidgetValue(BTN_Bind_Macro, 0.0)
       else
           // 2. Resolve LFO name
           if not LFO_Draft_Active then
               // EDIT state — already bound
               LFOFlashMsg = "Already bound (use Save to update)"
               LFOFlashTimer = TimeSinceStartup() + 1000.0
               RefreshLFOInspector()
               if DebugMode then Trace("LFO v2: BTN_Bind_Macro rejected, scope already bound") end
               SetWidgetValue(BTN_Bind_Macro, 0.0)
           else
               lfoName = LFO_Draft_Name

               // 3. Create-or-update registry entry
               registryIdx = -1
               For i = 0; i < Size(LFO_Names); i = i + 1 Do
                  if LFO_Names[i] == lfoName then registryIdx = i end
               End

               if registryIdx < 0 then
                   LFO_Names  <-- lfoName
                   LFO_Types  <-- LFO_Draft_Type
                   LFO_Rates  <-- LFO_Draft_Rate
                   LFO_Cycles <-- LFO_Draft_Cycles
                   if DebugMode then Trace("LFO v2: created new registry entry '" + lfoName + "'") end
               else
                   LFO_Types[registryIdx]  = LFO_Draft_Type
                   LFO_Rates[registryIdx]  = LFO_Draft_Rate
                   LFO_Cycles[registryIdx] = LFO_Draft_Cycles
                   if DebugMode then Trace("LFO v2: updated existing registry entry '" + lfoName + "'") end
               end

               // 4. Persist registry
               SaveLFOConfig()

               // 5. Mutate ControllerMaps.txt — prepend LFO:<name> | to the target macro line
               if FileExists(ControllerMapFilePath) then
                   content = LoadStringFromTextFile(ControllerMapFilePath)

                   // Find [Map:<mapName>] section
                   searchKey = "[Map:" + mapName + "]"
                   mapSectionStart = IndexOfSubstring(content, searchKey, false)
                   if mapSectionStart < 0 then
                       if DebugMode then Trace("LFO v2: BTN_Bind_Macro: map section '" + mapName + "' not found in ControllerMaps.txt") end
                   else
                       // Find next [Map: or EOF for section end
                       mapSectionEnd = IndexOfSubstring(CopySubstring(content, mapSectionStart + Length(searchKey), Length(content) - (mapSectionStart + Length(searchKey))), "[Map:", false)
                       if mapSectionEnd < 0 then mapSectionEnd = Length(content) - (mapSectionStart + Length(searchKey)) end

                       // Extract section, find Macro<N> = line, mutate, stitch back
                       section = CopySubstring(content, mapSectionStart + Length(searchKey), mapSectionEnd)
                       searchKey = "Macro" + (scopeSlot + 1) + " ="
                       lineStart = IndexOfSubstring(section, searchKey, false)

                       if lineStart >= 0 then
                           // Find end of that line
                           nlPos = IndexOfSubstring(CopySubstring(section, lineStart, Length(section) - lineStart), NEW_LINE, false)
                           if nlPos >= 0 then
                               oldLine = CopySubstring(section, lineStart, nlPos)
                           else
                               oldLine = CopySubstring(section, lineStart, Length(section) - lineStart)
                           end

                           // Extract existing value part after "="
                           lineEnd = IndexOfSubstring(oldLine, "=", false)
                           if lineEnd >= 0 then
                               newValue = TrimString(CopySubstring(oldLine, lineEnd + 1, Length(oldLine) - (lineEnd + 1)))
                               // Prepend LFO:<name> | (unless a prefix is already there — replace it)
                               if IndexOfSubstring(newValue, "LFO:", false) == 0 then
                                   // Strip existing LFO:<other> | prefix
                                   i = IndexOfSubstring(newValue, "|", false)
                                   if i >= 0 then
                                       newValue = TrimString(CopySubstring(newValue, i + 1, Length(newValue) - (i + 1)))
                                   else
                                       newValue = ""
                                   end
                               end
                               if Length(newValue) > 0 then
                                   newLine = searchKey + " LFO:" + lfoName + " | " + newValue
                               else
                                   newLine = searchKey + " LFO:" + lfoName
                               end

                               // Stitch: replace oldLine with newLine in section, then rebuild content
                               section = ReplaceString(section, oldLine, newLine, false)
                               content = CopySubstring(content, 0, mapSectionStart + Length("[Map:" + mapName + "]")) + section + CopySubstring(content, mapSectionStart + Length("[Map:" + mapName + "]") + mapSectionEnd, Length(content) - (mapSectionStart + Length("[Map:" + mapName + "]") + mapSectionEnd))

                               saved = SaveStringToTextFile(ControllerMapFilePath, content)
                               if DebugMode then Trace("LFO v2: wrote LFO:" + lfoName + " prefix to [" + mapName + "] Macro" + (scopeSlot + 1) + " (saved=" + saved + ")") end
                           end
                       else
                           if DebugMode then Trace("LFO v2: BTN_Bind_Macro: Macro" + (scopeSlot + 1) + " not found in section [" + mapName + "]") end
                       end
                   end
               end

               // 6. Rebuild state
               LoadControllerMap(mapName)
               BuildLFOUsageIndex()
               RefreshLFOInspector()

               SetWidgetValue(BTN_Bind_Macro, 0.0)
           end
       end
   end
End
```

- [ ] **Step 2: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): BTN_Bind_Macro callback with whitelist and flash

Callback reads CurrentEditScope + CurrentCtrlMapName, validates that
the scope is a user-zone macro (1-50), and either creates or
updates the registry entry using LFO_Draft_* values. Then rewrites
the target line in ControllerMaps.txt to prepend 'LFO:<Name> | '
(replacing any existing LFO prefix on that line). SaveLFOConfig
persists the registry, LoadControllerMap repopulates LFO_ByMacro,
BuildLFOUsageIndex rebuilds the reverse index, and
RefreshLFOInspector transitions the scope from DRAFT to EDIT.

Whitelist violations (scope -1 or >=50) flash 'Only User Macros
allowed (scope 1-50)' on LBL_LFO_BoundMacro for 1 second.
EDIT-state clicks flash 'Already bound (use Save to update)'."
```

---

## Task 7: `BTN_LFO_Save` rework (narrow) and `BTN_LFO_Delete` rework (cross-map strip)

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 25-26 (rewrite two callbacks)

- [ ] **Step 1: Replace `BTN_LFO_Save`**

Grep for `On WidgetValueChanged(val : Double) from BTN_LFO_Save` — this is the v1 callback from Plan #3 Task 8. Replace the entire callback:

```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Save
   var scopeSlot, lfoIdx : Integer
   if val > 0.5 then
       scopeSlot = CurrentEditScope

       // EDIT state only
       if scopeSlot < 0 or scopeSlot >= 50 or LFO_Draft_Active then
           if DebugMode then Trace("LFO v2: BTN_LFO_Save ignored (not in EDIT state)") end
       else
           lfoIdx = LFO_ByMacro[scopeSlot]
           if lfoIdx < 0 then
               if DebugMode then Trace("LFO v2: BTN_LFO_Save ignored (scope has no LFO)") end
           else
               // Registry already has the current Type/Rate/Cycles from the
               // cycle-callback edits in Task 4. Just persist to disk.
               SaveLFOConfig()
               if DebugMode then Trace("LFO v2: saved registry entry '" + LFO_Names[lfoIdx] + "'") end
           end
       end
       SetWidgetValue(BTN_LFO_Save, 0.0)
   end
End
```

- [ ] **Step 2: Replace `BTN_LFO_Delete`**

Grep for `On WidgetValueChanged(val : Double) from BTN_LFO_Delete` — v1 callback. Replace:

```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Delete
   var scopeSlot, lfoIdx, i, unbindCount : Integer
   var lfoName : String
   var newNames : String Array
   var newTypes, newRates, newCycles : Integer Array
   var content, searchPrefix : String
   var saved : Boolean = false

   if val > 0.5 then
       scopeSlot = CurrentEditScope

       // EDIT state only
       if scopeSlot < 0 or scopeSlot >= 50 or LFO_Draft_Active then
           if DebugMode then Trace("LFO v2: BTN_LFO_Delete ignored (not in EDIT state)") end
       else
           lfoIdx = LFO_ByMacro[scopeSlot]
           if lfoIdx < 0 then
               if DebugMode then Trace("LFO v2: BTN_LFO_Delete ignored (scope has no LFO)") end
           else
               lfoName = LFO_Names[lfoIdx]

               // 1. Stop any running instances of this LFO across all slots
               For i = 0; i < MAX_MACROS; i = i + 1 Do
                  if LFO_Active[i] and LFO_ByMacro[i] == lfoIdx then
                      StopLFO(i)
                  end
               End

               // 2. Strip LFO:<name> | prefix from every matching line in ControllerMaps.txt
               unbindCount = 0
               if FileExists(ControllerMapFilePath) then
                   content = LoadStringFromTextFile(ControllerMapFilePath)

                   // Strip "LFO:<name> | " (with trailing separator)
                   searchPrefix = "LFO:" + lfoName + " | "
                   While IndexOfSubstring(content, searchPrefix, false) >= 0 Do
                       content = ReplaceString(content, searchPrefix, "", false)
                       unbindCount = unbindCount + 1
                   End

                   // Also strip bare "LFO:<name>" (no trailing targets — rare edge case)
                   searchPrefix = "LFO:" + lfoName
                   While IndexOfSubstring(content, "= " + searchPrefix + NEW_LINE, false) >= 0 Do
                       content = ReplaceString(content, "= " + searchPrefix + NEW_LINE, "= " + NEW_LINE, false)
                       unbindCount = unbindCount + 1
                   End

                   saved = SaveStringToTextFile(ControllerMapFilePath, content)
                   if DebugMode then Trace("LFO v2: stripped " + unbindCount + " bindings of '" + lfoName + "' from ControllerMaps.txt (saved=" + saved + ")") end
               end

               // 3. Remove from registry — rebuild arrays without this index
               newNames  = []
               newTypes  = []
               newRates  = []
               newCycles = []
               For i = 0; i < Size(LFO_Names); i = i + 1 Do
                  if i != lfoIdx then
                      newNames  <-- LFO_Names[i]
                      newTypes  <-- LFO_Types[i]
                      newRates  <-- LFO_Rates[i]
                      newCycles <-- LFO_Cycles[i]
                  end
               End
               LFO_Names  = newNames
               LFO_Types  = newTypes
               LFO_Rates  = newRates
               LFO_Cycles = newCycles

               SaveLFOConfig()
               if DebugMode then Trace("LFO v2: removed '" + lfoName + "' from registry, " + Size(LFO_Names) + " entries remain") end

               // 4. Rebuild state — LoadControllerMap updates LFO_ByMacro for the active map
               LoadControllerMap(CurrentCtrlMapName)
               BuildLFOUsageIndex()
               RefreshLFOInspector()
           end
       end
       SetWidgetValue(BTN_LFO_Delete, 0.0)
   end
End
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): BTN_LFO_Save narrow + BTN_LFO_Delete cross-map strip

BTN_LFO_Save is now narrow: it only fires in EDIT state and only
persists the registry via SaveLFOConfig. No more ControllerMaps.txt
mutation — bindings haven't changed, only shape. No reverse-index
rebuild either — the index is binding-oriented, not shape-oriented.

BTN_LFO_Delete performs the full teardown: stops any running
instances (with snap-back via StopLFO), strips every LFO:<name>
prefix from ControllerMaps.txt across all maps, rebuilds the
registry without the deleted entry, persists LFOConfig.txt,
reloads the active Controller Map so LFO_ByMacro is fresh,
rebuilds the reverse index, and refreshes the inspector (which
will now show DRAFT state because the scope's LFO is gone)."
```

---

## Task 8: `BTN_LFO_Run` draft preview and `TickLFOs` draft branch

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 13 (`TickLFOs`) and SECTION 25-26 (`BTN_LFO_Run`)

- [ ] **Step 1: Add the draft-preview branch to `TickLFOs`**

Grep for `Function TickLFOs()` to locate the existing runtime loop. Add a new block at the top of the function, before the main per-slot loop, that handles the single draft-preview LFO:

Find:
```gpscript
Function TickLFOs()
   var slot, lfoIdx, beatsPerBar, cyclesDone : Integer
   var elapsedMS, cycleLenMS, phase, sample, bpm, totalBars, elapsedBars : Double = 0.0

   bpm = GetBPM()
   if bpm < 1.0 then bpm = 120.0 end
   beatsPerBar = GetTimeSigNumerator()
   if beatsPerBar <= 0 then beatsPerBar = 4 end

   For slot = 0; slot < MAX_MACROS; slot = slot + 1 Do
```

Add the draft block immediately before the `For slot = 0; ...` line:

```gpscript
Function TickLFOs()
   var slot, lfoIdx, beatsPerBar, cyclesDone : Integer
   var elapsedMS, cycleLenMS, phase, sample, bpm, totalBars, elapsedBars : Double = 0.0

   bpm = GetBPM()
   if bpm < 1.0 then bpm = 120.0 end
   beatsPerBar = GetTimeSigNumerator()
   if beatsPerBar <= 0 then beatsPerBar = 4 end

   // v2: DRAFT PREVIEW — single global slot driven by BTN_LFO_Run in DRAFT
   if LFO_Draft_Running and LFO_Draft_Slot >= 0 and LFO_Draft_Slot < MAX_MACROS then
       elapsedMS = TimeSinceStartup() - LFO_Draft_StartTime
       cycleLenMS = (60000.0 / bpm) * IntToFloat(beatsPerBar) * LFORateBars(LFO_Draft_Rate)
       if cycleLenMS < 1.0 then cycleLenMS = 1.0 end
       phase = (elapsedMS / cycleLenMS) - Floor(elapsedMS / cycleLenMS)
       sample = SampleLFOWaveform(LFO_Draft_Type, phase)
       SetParameter(ExternalArranger, LFO_Draft_Slot, sample)
       SetWidgetValue(METER_LFO_H, sample)
       SetWidgetValue(METER_LFO_V, phase)
   end

   For slot = 0; slot < MAX_MACROS; slot = slot + 1 Do
```

- [ ] **Step 2: Replace `BTN_LFO_Run`**

Grep for `On WidgetValueChanged(val : Double) from BTN_LFO_Run` — v1 callback. Replace:

```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Run
   var scopeSlot, lfoIdx : Integer

   scopeSlot = CurrentEditScope

   if scopeSlot < 0 or scopeSlot >= 50 then
       // LOCKED — ignore
       SetWidgetValue(BTN_LFO_Run, 0.0)
   else
       if val > 0.5 then
           if LFO_Draft_Active then
               // DRAFT state — start the preview LFO
               LFO_Draft_Slot      = scopeSlot
               LFO_Draft_StartTime = TimeSinceStartup()
               LFO_Draft_PreValue  = GetParameter(ExternalArranger, scopeSlot)
               LFO_Draft_Running   = true
               if DebugMode then Trace("LFO v2: draft preview started on slot " + (scopeSlot + 1)) end
           else
               lfoIdx = LFO_ByMacro[scopeSlot]
               if lfoIdx >= 0 then
                   StartLFO(scopeSlot)
                   if DebugMode then Trace("LFO v2: manual Run on EDIT slot " + (scopeSlot + 1)) end
               end
           end
       else
           // Button released — stop whichever is running
           if LFO_Draft_Running then
               LFO_Draft_Running = false
               SetParameter(ExternalArranger, LFO_Draft_Slot, LFO_Draft_PreValue)
               SetWidgetValue(METER_LFO_H, 0.0)
               SetWidgetValue(METER_LFO_V, 0.0)
               LFO_Draft_Slot = -1
               if DebugMode then Trace("LFO v2: draft preview stopped, snapped back") end
           elsif scopeSlot >= 0 and scopeSlot < 50 then
               lfoIdx = LFO_ByMacro[scopeSlot]
               if lfoIdx >= 0 and LFO_Active[scopeSlot] then
                   StopLFO(scopeSlot)
               end
           end
       end
   end
End
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo-v2): BTN_LFO_Run draft preview + TickLFOs draft branch

TickLFOs gains a new top-of-function block that services the single
global draft-preview LFO when LFO_Draft_Running is true. Uses the
same phase / sample / SetParameter(ExternalArranger) pattern as the
main per-slot loop but reads from LFO_Draft_Type/Rate and targets
LFO_Draft_Slot.

BTN_LFO_Run detects DRAFT vs EDIT state via LFO_Draft_Active. In
DRAFT: press starts the preview by caching the current macro value
into LFO_Draft_PreValue, setting LFO_Draft_Running = true, and
letting TickLFOs drive the parameter. Release restores the cached
value and clears the running state. In EDIT: unchanged v1 behaviour
(StartLFO / StopLFO with normal snap-back)."
```

---

## Task 9: Delete Plan #3 browser callbacks and orphan state

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 25-26 (delete two callbacks)

- [ ] **Step 1: Delete `BTN_LFO_Next` and `BTN_LFO_Prev` callbacks**

Grep for `On WidgetValueChanged(val : Double) from BTN_LFO_Next` and `BTN_LFO_Prev` — these are the standalone browser callbacks from Plan #3 Task 8 and are no longer wired to any widget (the widget declarations were removed in Task 1 of this plan).

Delete both callbacks entirely. Without the widgets declared, the callbacks would fail to compile because `from BTN_LFO_Next` references a non-existent handle.

- [ ] **Step 2: Verify no remaining references**

Run a Grep for `LFO_SelectedIdx` and `LFO_ManualRun`. These were state variables deleted in Task 1 of this plan; any remaining reference would indicate code that wasn't migrated.

Expected: zero matches in `Global Rackspace.gpscript`.

If any match is found, read the context and adapt it to the v2 model — typically the fix is to replace `LFO_SelectedIdx` with `LFO_ByMacro[CurrentEditScope]` and remove any `LFO_ManualRun` gate (BTN_LFO_Run state is now per-draft / per-slot).

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "chore(lfo-v2): delete Plan #3 browser callbacks

BTN_LFO_Next and BTN_LFO_Prev widgets were removed in the v2
inspector redesign (scope-driven, no independent browser). Their
callbacks are dead code and would fail to compile with the widget
handles gone. This commit removes them.

Also verifies that LFO_SelectedIdx and LFO_ManualRun (deleted from
the Var block in Task 1) have no remaining references in the file."
```

---

## Verification (after all tasks)

No automated tests. After all commits, load the updated `Global Rackspace.gpscript` into Gig Performer and perform the following checks. Any unexpected trace, compile error, or missing trace is reported back as feedback.

**A. Compile and cold-boot**

1. Paste the updated script.
2. Compile — expect no compiler errors. All new state vars (`LFO_Usage_*`, `LFO_Draft_*`, `LFOFlashMsg`, `LFOFlashTimer`, `LFOBind_Lines`) should resolve. Deleted vars (`LFO_SelectedIdx`, `LFO_ManualRun`) should have zero remaining references.
3. Script console expected at boot:
   - `LFO: registered '<N>' ...` from LoadLFOConfig (Plan #3 Task 3)
   - `LFO v2: reverse index + draft + flash state initialized`
   - `LFO v2: BuildLFOUsageIndex complete, N bindings across all maps`

**B. LOCKED state**

1. After cold-boot, if no LFO bindings exist in any song's Controller Map: `LBL_Edit_Scope` shows `Scope: [GLOBAL] (All User Macros)`, inspector shows LOCKED (all labels `-`).
2. Console: `LFO v2: inspector LOCKED (scope=-1)`

**C. DRAFT_FALLBACK state**

1. With no `[LFO:Standard]` entry in `LFOConfig.txt`, switch `LBL_Edit_Scope` to a user-zone macro that has no LFO bound (use `BTN_Scope_Prev/Next`).
2. Inspector shows: `LBL_LFO = <song name>`, Type = `Triangle`, Rate = `1/4`, Cycles = `Infinite`, `LBL_LFO_BoundMacro = "(draft - bind to save)"`.
3. Console: `LFO v2: inspector DRAFT_FALLBACK (slot=N name='<song>')`

**D. DRAFT_STANDARD state**

1. Create `[LFO:Standard]` entry in `LFOConfig.txt` with custom Type/Rate/Cycles. Reload the script.
2. Switch scope to a no-LFO macro.
3. Inspector shows the Standard template's Type/Rate/Cycles, not the hardcoded fallback.
4. Console: `LFO v2: inspector DRAFT_STANDARD (slot=N name='<song>')`

**E. Bind flow**

1. In DRAFT state with a user-zone scope, click `BTN_Bind_Macro`.
2. Console expected: `LFO v2: created new registry entry '<song>'`, `LFO v2: wrote LFO:<song> prefix to [<map>] Macro<N+1> (saved=true)`, `LFO v2: BuildLFOUsageIndex complete, M bindings`, `LFO v2: inspector EDIT (slot=N lfo='<song>')`.
3. Open `ControllerMaps.txt` — the `Macro<N+1> = ...` line now starts with `LFO:<song> | `.
4. Inspector transitions from DRAFT to EDIT; `LBL_LFO_BoundMacro` shows the binding head line.

**F. Whitelist rejection**

1. In a LOCKED state (scope `-1`), click `BTN_Bind_Macro`.
2. `LBL_LFO_BoundMacro` flashes `"Only User Macros allowed (scope 1-50)"` for ~1 second then reverts.
3. Console: `LFO v2: BTN_Bind_Macro rejected, scope -1 outside user zone`

**G. Cross-map bound-macro display**

1. Bind the same LFO to macros in two different Controller Maps (e.g. bind `[song] TriSlow` to Macro 5 in `Standard_VST1`, then switch to `Standard_VST2` and bind to Macro 7 there).
2. Scope on either bound macro shows `LBL_LFO_BoundMacro` with both bindings grouped by map:
   ```
   --- LFO BINDINGS: <name> ---
   [Map: Standard_VST1]
     Macro 5 ...: ...
   [Map: Standard_VST2]
     Macro 7 ...: ...
   ```

**H. Delete across maps**

1. In EDIT state on the LFO from (G), click `BTN_LFO_Delete`.
2. Console: `LFO v2: stripped 2 bindings of '<name>' from ControllerMaps.txt (saved=true)`, `LFO v2: removed '<name>' from registry`.
3. `ControllerMaps.txt`: the `LFO:<name> | ` prefixes are gone from both macro lines.
4. Inspector reverts to DRAFT state on the current scope.

**I. Auto-jump on song load**

1. Song has bound LFO on Macro 5 (not Macro 1).
2. Load the song.
3. Console: `LFO v2: auto-jump CurrentEditScope to Macro 5`, `LFO v2: inspector EDIT (slot=5 lfo=...)`.
4. `LBL_Edit_Scope` shows `Scope: [Macro 5]`, inspector opens on the bound LFO.

**J. Draft preview run**

1. DRAFT state on a user-zone macro. Hold `BTN_LFO_Run`.
2. Console: `LFO v2: draft preview started on slot N`.
3. `METER_LFO_H` moves with the draft waveform, `METER_LFO_V` ramps with phase.
4. Release the button.
5. Console: `LFO v2: draft preview stopped, snapped back`.
6. Meters return to 0, the target parameter is restored to its pre-run value.

---

## Self-Review

**Spec coverage:**

- §2 (Storage & Identity, `[LFO:Standard]` template) → Task 4 (`RefreshLFOInspector` resolves Standard from registry)
- §3 (Reverse index, `BuildLFOUsageIndex`, runtime state separation) → Tasks 1, 2
- §4 (Scope-driven inspector, four states, auto-jump, label rename) → Tasks 4, 5
- §5 (`LBL_LFO_BoundMacro` head-line-only, grouped-by-map, active/inactive map handling, flash surface) → Tasks 1 (state), 3 (build + display), 6 (flash trigger from Bind)
- §6 (BTN_Bind_Macro, Save narrowing, Delete cross-map strip, Run draft preview) → Tasks 6, 7, 8
- §7 (Data structures summary) → Task 1
- §8 (Migration from Plan #3, deletions) → Task 1 (widget + state), Task 9 (callbacks)

**Placeholder scan:**

- Task 4 Step 1 notes `CurrentSongName` — the subagent needs to verify the actual variable name via Grep. This is a directed search with a concrete fallback (`GetCurrentSongName()` if in setlist, `"Default"` otherwise), not a placeholder.
- Task 5 Step 2 describes the insertion point around `IsLoadingSnapshot = false` — the subagent needs to locate the exact line, which is a directed Grep, not a placeholder.
- No `TBD` / `TODO` / `fill in details` strings in any task.

**Type consistency:**

- `LFO_Usage_LfoIdx`, `LFO_Usage_MapIdx`, `LFO_Usage_MacroIdx` are `Integer Array`; `LFO_Usage_RawLine` is `String Array`. Used consistently across Tasks 2, 3, 6, 7.
- `LFO_Draft_Active : Boolean`, `LFO_Draft_Type/Rate/Cycles : Integer`, `LFO_Draft_Name : String`. Used consistently in Tasks 1, 4, 6, 8.
- `LFO_Draft_Running : Boolean`, `LFO_Draft_Slot : Integer`, `LFO_Draft_StartTime / PreValue : Double`. Used consistently in Task 8.
- `LFOFlashMsg : String`, `LFOFlashTimer : Double`. Used in Tasks 1, 3, 6.
- `LFOBind_Lines : String Array`. Used in Tasks 1, 3, 4.
- `BuildLFOUsageIndex()` takes no arguments, returns void. `BuildLFOBindLines(lfoIdx : Integer)` takes one, returns void. `RefreshLFOBoundMacroDisplay()` takes none, returns void. `RefreshLFOInspector()` takes none, returns void. All match their call sites.
- `CurrentEditScope : Integer` (existing from the codebase). `CurrentCtrlMapName : String` (existing). `CtrlMapList : String Array` (existing). `LFO_Names : String Array` (from Plan #3). `LFO_ByMacro : Integer Array` (from Plan #3). `GetAssignedHWString(Integer) Returns String` (from existing `CtrlInfo_Lines` logic). `Link_*` arrays (existing). All referenced consistently.
- `StopLFO(slot : Integer)` from Plan #3 Task 5 is called in Tasks 7 and 8. Signature matches.
- `SaveLFOConfig()` from Plan #3 Task 9 is called in Tasks 6, 7. Signature matches.
- `SaveStringToTextFile` returns `Boolean` — captured in Tasks 6, 7 per the existing project convention (memory `feedback_gpscript_returns_capture.md`).
