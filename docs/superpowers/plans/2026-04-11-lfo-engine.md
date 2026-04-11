# LFO Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a BPM-synced LFO engine that binds to user-zone macro slots through a new `LFO:<Name>` binding kind in `ControllerMaps.txt`, reads named waveform configurations from a new `LFOConfig.txt`, drives the macro from 0.0 to 1.0 through the selected waveform, snaps back to the pre-trigger value on stop, and exposes a dedicated inspector panel with type/rate/cycles browsers, amplitude and progress meters, run toggle, save, and delete.

**Architecture:** New text file `LFOConfig.txt` sibling to `ControllerMaps.txt`. A registry array of parsed LFO configs lives in memory (`LFO_Names`, `LFO_Types`, `LFO_Rates`, `LFO_Cycles`). The `LoadControllerMap` parser is extended to recognize `LFO:<Name>` as a prefix token in a `|`-separated binding line and to register a reverse-lookup `LFO_ByMacro[slot] = lfoIdx`. The runtime engine tracks per-slot active LFOs in parallel state arrays, advances them from `On TimerTick`, samples the waveform from elapsed time + BPM, writes the result via `SetMacroValue()`, and snaps back on stop. A new inspector widget block (Prev/Label/Next triples plus two meters and three buttons) binds into existing cycle-browser patterns.

**Tech Stack:** GPScript 5.x, single-file. Verification via `if DebugMode then Trace(...)` statements plus user E2E.

**Spec:** `docs/superpowers/specs/2026-04-11-lfo-looper-timeline-design.md` §2.

---

## File Structure

**Files changed:**
- `Global Rackspace.gpscript` (all code)

**Files created:**
- `examples/LFOConfig.txt` — initial example file with two LFO entries

| Section | Lines | Change |
|---|---|---|
| SECTION 1 / User Configuration | new | Add `LFOConfigFilePath` variable |
| SECTION 5 / GUI Widget Handles | new | Declare the new LFO inspector widgets |
| SECTION 6 / Engine State | new | Add per-slot LFO runtime arrays + registry arrays |
| SECTION 13 / Core Utilities | new function | `LoadLFOConfig()` parser |
| SECTION 13 / Core Utilities | new functions | `SaveLFOConfig()`, `DeleteLFOConfig()` |
| SECTION 13 / Core Utilities | new functions | `LFOTypeName()`, `LFORateName()`, `LFOCyclesName()` enumerators |
| SECTION 13 / Core Utilities | new function | `SampleLFOWaveform(type, phase)` |
| SECTION 17 / Controller Map Engine | ~5927 | Extend `LoadControllerMap` with `LFO:` prefix recognition |
| SECTION 17 / Controller Map Engine | new functions | `StartLFO(slot)`, `StopLFO(slot)`, `TickLFOs()` |
| Timer tick handler | existing | Call `TickLFOs()` each tick |
| Playhead stop handler | existing | Stop all active LFOs on transport stop |
| `SaveControllerMap` / writer | existing | Emit `LFO:<Name>` at position 0 for slots with `LFO_ByMacro[slot] >= 0` |
| SECTION 25-26 / Callbacks | new | Widget callbacks for the LFO inspector block |

---

## Task 1: Create `examples/LFOConfig.txt` seed file

**Files:**
- Create: `examples/LFOConfig.txt`

- [ ] **Step 1: Write the seed file**

Create `examples/LFOConfig.txt` with two example entries:

```
; LFO Configurations
; Same style as ControllerMaps.txt: named sections, ; comments, key = value
; Type: Triangle, TriangleUp, TriangleDown, Sinus, Square, Random
; Rate: 8/1, 4/1, 2/1, 1/1, 1/2, 1/4, 1/8, 1/16, 1/32
; Cycles: -, Infinite, or a positive integer

[LFO:TriSlow]
; Slow triangle sweep, four cycles
Type   = Triangle
Rate   = 1/4
Cycles = 4

[LFO:PadBreath]
; Sinus modulation for pad layers, runs forever
Type   = Sinus
Rate   = 1/1
Cycles = Infinite
```

- [ ] **Step 2: Commit**

```bash
git add examples/LFOConfig.txt
git commit -m "feat(lfo): add LFOConfig.txt example seed file

Two example LFO entries: TriSlow (4-cycle triangle on a 1/4-note
rate) and PadBreath (infinite sinus on a 1/1 rate). Same text style
as ControllerMaps.txt."
```

---

## Task 2: Add LFO registry + runtime state arrays + `LFOConfigFilePath`

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 1 (User Configuration, ~15), SECTION 6 (Engine State, ~325)

- [ ] **Step 1: Add the file path variable in SECTION 1**

Find the SECTION 1 block near line 15. It already contains paths like `ControllerMapFilePath`. Add a new line near those path declarations:

```gpscript
   LFOConfigFilePath : String = UserSnapshotPath + "/LFOConfig.txt"
```

Match the exact pattern of the existing path declarations — if they use a different separator or helper, follow suit.

- [ ] **Step 2: Add the registry and runtime state arrays in SECTION 6**

In SECTION 6 (Engine State & Timers, starts around line 325), add a new block near the top of the section:

```gpscript
   // -------------------------------------------------------------
   // LFO ENGINE STATE
   // -------------------------------------------------------------
   // Registry (one entry per parsed LFO in LFOConfig.txt)
   LFO_Names  : String Array       // e.g. "TriSlow"
   LFO_Types  : Integer Array      // 0..5 : Triangle, TriangleUp, TriangleDown, Sinus, Square, Random
   LFO_Rates  : Integer Array      // 0..8 : 8/1 .. 1/32 (index into rate table)
   LFO_Cycles : Integer Array      // -1 = Infinite, 0 = '-', N > 0 = finite count

   // Per-macro-slot binding (MAX_MACROS = 256 entries)
   LFO_ByMacro : Integer Array     // -1 = no binding, else index into LFO_Names

   // Per-slot runtime state (parallel to LFO_ByMacro)
   LFO_Active      : Boolean Array
   LFO_StartTime   : Double Array
   LFO_PreValue    : Double Array
   LFO_CyclesLeftI : Integer Array  // initial cycles count at trigger, used for completion check
   LFO_LastSample  : Double Array
   LFO_Progress    : Double Array   // 0..1 normalized total progress for V meter

   // Inspector browser cursors
   LFO_SelectedIdx : Integer = 0    // which registry entry is shown in the inspector
   LFO_ManualRun   : Boolean = false // true while BTN_LFO_Run is in the ON state without a macro trigger
```

- [ ] **Step 3: Initialize the arrays in bootstrap**

In Bootstrap PHASE 4 (where `RoutingMatrix` and similar arrays are built, around line 12128), add:

```gpscript
   LFO_Names = []; LFO_Types = []; LFO_Rates = []; LFO_Cycles = []
   LFO_ByMacro = []; For i_init = 0; i_init < MAX_MACROS; i_init = i_init + 1 Do LFO_ByMacro <-- -1 End
   LFO_Active = []; LFO_StartTime = []; LFO_PreValue = []
   LFO_CyclesLeftI = []; LFO_LastSample = []; LFO_Progress = []
   For i_init = 0; i_init < MAX_MACROS; i_init = i_init + 1 Do
       LFO_Active    <-- false
       LFO_StartTime <-- 0.0
       LFO_PreValue  <-- 0.0
       LFO_CyclesLeftI <-- 0
       LFO_LastSample <-- 0.0
       LFO_Progress  <-- 0.0
   End
   LFO_SelectedIdx = 0
   LFO_ManualRun = false
   if DebugMode then Trace("LFO: state arrays initialized (MAX_MACROS=" + MAX_MACROS + ")") end
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): declare LFO registry + per-slot runtime state

Adds LFOConfigFilePath in SECTION 1 pointing at
UserSnapshotPath/LFOConfig.txt. Declares LFO registry arrays
(Names/Types/Rates/Cycles) and per-macro-slot runtime state arrays
(ByMacro, Active, StartTime, PreValue, CyclesLeftI, LastSample,
Progress) in SECTION 6. Bootstrap PHASE 4 initializes all of them to
neutral values so the first LoadLFOConfig call starts from empty
state."
```

---

## Task 3: `LoadLFOConfig()` parser with enumerators

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 13 (Core Utilities, after other file-loading functions)

- [ ] **Step 1: Add the enumerator helpers**

Pick a landing spot in SECTION 13 that compiles before `LoadLFOConfig` and before `LoadControllerMap` (so the parser can use them too). The safest place is immediately before `LoadMappingFile()` at line 5574.

```gpscript
// ---------------------------------------------------------
// LFO ENUMERATORS
// Forward + reverse lookup between text names and integer indices
// for the three enum fields (Type, Rate, Cycles). These are the
// single source of truth for what values are legal.
// ---------------------------------------------------------

Function LFOTypeIdx(name : String) Returns Integer
   var n : String = TrimString(name)
   if n == "Triangle" then result = 0
   elsif n == "TriangleUp" then result = 1
   elsif n == "TriangleDown" then result = 2
   elsif n == "Sinus" then result = 3
   elsif n == "Square" then result = 4
   elsif n == "Random" then result = 5
   else result = -1 end
End

Function LFOTypeName(idx : Integer) Returns String
   if idx == 0 then result = "Triangle"
   elsif idx == 1 then result = "TriangleUp"
   elsif idx == 2 then result = "TriangleDown"
   elsif idx == 3 then result = "Sinus"
   elsif idx == 4 then result = "Square"
   elsif idx == 5 then result = "Random"
   else result = "?" end
End

Function LFORateIdx(name : String) Returns Integer
   var n : String = TrimString(name)
   if n == "8/1" then result = 0
   elsif n == "4/1" then result = 1
   elsif n == "2/1" then result = 2
   elsif n == "1/1" then result = 3
   elsif n == "1/2" then result = 4
   elsif n == "1/4" then result = 5
   elsif n == "1/8" then result = 6
   elsif n == "1/16" then result = 7
   elsif n == "1/32" then result = 8
   else result = -1 end
End

Function LFORateName(idx : Integer) Returns String
   if idx == 0 then result = "8/1"
   elsif idx == 1 then result = "4/1"
   elsif idx == 2 then result = "2/1"
   elsif idx == 3 then result = "1/1"
   elsif idx == 4 then result = "1/2"
   elsif idx == 5 then result = "1/4"
   elsif idx == 6 then result = "1/8"
   elsif idx == 7 then result = "1/16"
   elsif idx == 8 then result = "1/32"
   else result = "?" end
End

Function LFORateBars(idx : Integer) Returns Double
   // Returns the number of bars per LFO cycle, given a 4/4 time signature.
   // Caller must multiply by GetTimeSigNumerator()/4 if they need exact
   // duration in a non-4/4 song.
   if idx == 0 then result = 8.0
   elsif idx == 1 then result = 4.0
   elsif idx == 2 then result = 2.0
   elsif idx == 3 then result = 1.0
   elsif idx == 4 then result = 0.5
   elsif idx == 5 then result = 0.25
   elsif idx == 6 then result = 0.125
   elsif idx == 7 then result = 0.0625
   elsif idx == 8 then result = 0.03125
   else result = 1.0 end
End

Function LFOCyclesParse(s : String) Returns Integer
   var n : String = TrimString(s)
   if n == "-" or n == "" then result = 0
   elsif n == "Infinite" then result = -1
   else result = StringToInt(n) end
End

Function LFOCyclesName(cycles : Integer) Returns String
   if cycles == 0 then result = "-"
   elsif cycles == -1 then result = "Infinite"
   else result = IntToString(cycles) end
End
```

- [ ] **Step 2: Add `LoadLFOConfig()`**

Immediately after the enumerator helpers:

```gpscript
// ---------------------------------------------------------
// LOAD LFO CONFIG
// Parses LFOConfig.txt into the LFO registry arrays. Silently
// skips malformed sections with a DebugMode trace. Called at
// bootstrap and whenever the file is saved/deleted.
// ---------------------------------------------------------
Function LoadLFOConfig()
   var content, sectionContent, remaining, line, key, val, name : String
   var lines : String Array
   var startPos, endPos, headerLen, i : Integer
   var parsedType, parsedRate, parsedCycles : Integer

   LFO_Names = []
   LFO_Types = []
   LFO_Rates = []
   LFO_Cycles = []

   if not FileExists(LFOConfigFilePath) then
       if DebugMode then Trace("LFO: LFOConfig.txt not found at " + LFOConfigFilePath + " — registry empty") end
   else
       content = LoadStringFromTextFile(LFOConfigFilePath)

       // Walk each "[LFO:Name]" section in order
       startPos = IndexOfSubstring(content, "[LFO:", false)
       While startPos > -1 Do
          // Find the ']' closing the header
          endPos = IndexOfSubstring(CopySubstring(content, startPos, Length(content) - startPos), "]", false)
          if endPos < 0 then
              startPos = -1  // break
          else
              // Extract name between "[LFO:" and "]"
              name = CopySubstring(content, startPos + 5, endPos - 5)
              headerLen = endPos + 1

              // Grab the section body — from after header to the next "[LFO:" or EOF
              remaining = CopySubstring(content, startPos + headerLen, Length(content) - (startPos + headerLen))
              endPos = IndexOfSubstring(remaining, "[LFO:", false)
              if endPos > -1 then
                  sectionContent = CopySubstring(remaining, 0, endPos)
              else
                  sectionContent = remaining
              end

              // Parse the body for Type/Rate/Cycles
              parsedType = -1
              parsedRate = -1
              parsedCycles = 0

              lines = SplitString(sectionContent, NEW_LINE)
              For i = 0; i < Size(lines); i = i + 1 Do
                 line = TrimString(lines[i])
                 if Length(line) > 0 and IndexOfSubstring(line, ";", false) != 0 and IndexOfSubstring(line, "=", false) > -1 then
                     key = TrimString(CopySubstring(line, 0, IndexOfSubstring(line, "=", false)))
                     val = TrimString(CopySubstring(line, IndexOfSubstring(line, "=", false) + 1, Length(line) - (IndexOfSubstring(line, "=", false) + 1)))
                     if key == "Type" then parsedType = LFOTypeIdx(val)
                     elsif key == "Rate" then parsedRate = LFORateIdx(val)
                     elsif key == "Cycles" then parsedCycles = LFOCyclesParse(val)
                     else
                         if DebugMode then Trace("LFO: unknown key '" + key + "' in [LFO:" + name + "]") end
                     end
                 end
              End

              if parsedType < 0 or parsedRate < 0 then
                  if DebugMode then Trace("LFO: [LFO:" + name + "] rejected (malformed Type/Rate)") end
              else
                  LFO_Names <-- name
                  LFO_Types <-- parsedType
                  LFO_Rates <-- parsedRate
                  LFO_Cycles <-- parsedCycles
                  if DebugMode then Trace("LFO: registered '" + name + "' type=" + LFOTypeName(parsedType) + " rate=" + LFORateName(parsedRate) + " cycles=" + LFOCyclesName(parsedCycles)) end
              end

              // Advance to the next section header in the ORIGINAL content
              if endPos > -1 then
                  startPos = (startPos + headerLen) + endPos
                  startPos = IndexOfSubstring(content, "[LFO:", false)
                  // Re-scan from where we were; GPScript doesn't support passing an offset to IndexOfSubstring,
                  // so the simple approach is: chop off the parsed prefix. For a small file this is fine.
                  content = CopySubstring(content, startPos + 1, Length(content) - (startPos + 1))
                  startPos = IndexOfSubstring(content, "[LFO:", false)
              else
                  startPos = -1
              end
          end
       End
   end

   if DebugMode then Trace("LFO: LoadLFOConfig complete, " + Size(LFO_Names) + " entries") end
End
```

**Note on the loop tail:** GPScript's `IndexOfSubstring` doesn't accept an offset, so the parser repeatedly chops the prefix it has already processed. For `LFOConfig.txt` (a handful of entries) this is negligible. The subagent should verify this compiles and parses both example entries from Task 1.

- [ ] **Step 3: Call `LoadLFOConfig()` from bootstrap**

In Bootstrap PHASE 2 / 3 where `LoadHardwareMap()` and `LoadVstDatabase()` are called (around line 12121), add the call right after:

```gpscript
   LoadHardwareMap() // <- Now safely near the top!
   LoadVstDatabase()
   LoadLFOConfig()   // <- NEW
   BuildFilteredVstList()
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): add LoadLFOConfig parser + enumerator helpers

LFOTypeIdx/Name, LFORateIdx/Name, LFORateBars, LFOCyclesParse/Name
are the single source of truth for the three enum fields. These are
used by both the parser and the inspector callbacks.

LoadLFOConfig walks each [LFO:Name] section in LFOConfig.txt,
validates Type + Rate (Cycles defaults to 0 = '-'), appends to the
registry arrays, and skips malformed entries with a DebugMode trace.
Bootstrap PHASE 2/3 calls it right after LoadHardwareMap /
LoadVstDatabase."
```

---

## Task 4: Extend `LoadControllerMap` to recognize `LFO:<Name>`

**Files:**
- Modify: `Global Rackspace.gpscript:5926` (inside the `NORMAL LINKS` else branch of `LoadControllerMap`)

- [ ] **Step 1: Add an LFO reset at the top of `LoadControllerMap`**

Near the top of `LoadControllerMap` (around line 5815, alongside `ResetSysActionBindings()`), add:

```gpscript
   // --- Reset LFO bindings for this map-section load ---
   var lfoReset : Integer
   For lfoReset = 0; lfoReset < MAX_MACROS; lfoReset = lfoReset + 1 Do
       LFO_ByMacro[lfoReset] = -1
   End
```

Make sure `lfoReset` is declared at the top of the function with the other `var` declarations — GPScript rule "all var declarations must be at function top".

- [ ] **Step 2: Add the `LFO:` prefix handler inside the NORMAL LINKS branch**

Locate line 5925–5927:

```gpscript
                               // --- NORMAL LINKS ---
                               else
                                   groupParts = SplitString(valuePart, "|")
```

Right after the `groupParts = SplitString(valuePart, "|")` line, before the `For j = 0; ...` loop that processes each entry, add:

```gpscript
                                   // --- LFO PREFIX EXTRACTION ---
                                   // If the first |-entry is "LFO:<Name>", consume it and
                                   // register LFO_ByMacro[sliderIdx] before the normal
                                   // link parser runs on the remaining entries.
                                   var lfoFirstEntry : String = ""
                                   var lfoName : String = ""
                                   var lfoIdx : Integer = -1
                                   var lfoRemaining : String Array
                                   var jj : Integer
                                   if Size(groupParts) > 0 then
                                       lfoFirstEntry = TrimString(groupParts[0])
                                       if IndexOfSubstring(lfoFirstEntry, "LFO:", false) == 0 then
                                           lfoName = TrimString(ReplaceString(lfoFirstEntry, "LFO:", "", false))

                                           // Whitelist: user-zone (1..50), non-CC source, must have remaining targets
                                           if isSrcCC then
                                               if DebugMode then Trace("LFO: rejected on CC source slot " + sliderIdx) end
                                           elsif sliderIdx < 0 or sliderIdx >= 50 then
                                               if DebugMode then Trace("LFO: rejected outside user zone (slot " + sliderIdx + ")") end
                                           elsif Size(groupParts) < 2 then
                                               if DebugMode then Trace("LFO: rejected, no VST/CC target follows LFO:" + lfoName) end
                                           else
                                               // Look up the registry
                                               lfoIdx = -1
                                               For jj = 0; jj < Size(LFO_Names); jj = jj + 1 Do
                                                   if LFO_Names[jj] == lfoName then lfoIdx = jj end
                                               End
                                               if lfoIdx < 0 then
                                                   if DebugMode then Trace("LFO: unknown name '" + lfoName + "' on slot " + sliderIdx) end
                                               else
                                                   LFO_ByMacro[sliderIdx] = lfoIdx
                                                   if DebugMode then Trace("LFO: bound slot " + sliderIdx + " to LFO " + lfoName + " (idx " + lfoIdx + ")") end
                                               end
                                           end

                                           // Strip the LFO entry from groupParts regardless of accept/reject
                                           lfoRemaining = []
                                           For jj = 1; jj < Size(groupParts); jj = jj + 1 Do
                                               lfoRemaining <-- groupParts[jj]
                                           End
                                           groupParts = lfoRemaining
                                       end
                                   end
```

**Declare the new variables** (`lfoFirstEntry`, `lfoName`, `lfoIdx`, `lfoRemaining`, `jj`) at the top of `LoadControllerMap` with the other `var` declarations, per the GPScript rule.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): parse LFO:<Name> prefix in LoadControllerMap

Inside the NORMAL LINKS branch of LoadControllerMap, check whether
the first |-separated entry starts with 'LFO:'. If yes:
- Apply the whitelist (user zone 1..50, Macro source only, at least
  one trailing VST/CC target)
- Look up the name in the registry loaded from LFOConfig.txt
- Write LFO_ByMacro[sliderIdx] = lfoIdx
- Strip the LFO entry from groupParts so the normal link parser sees
  only the remaining targets

LFO rejections are DebugMode-traced and do not block the rest of the
line from parsing normally. LFO_ByMacro is reset at the top of
LoadControllerMap so a map switch flushes previous bindings."
```

---

## Task 5: `SampleLFOWaveform` + `StartLFO` + `StopLFO` + `TickLFOs`

**Files:**
- Modify: `Global Rackspace.gpscript` — new functions in SECTION 17 or SECTION 13

- [ ] **Step 1: Add the waveform sampler**

Landing zone: near the other LFO helpers from Task 3 (before `LoadMappingFile`).

```gpscript
// ---------------------------------------------------------
// SAMPLE LFO WAVEFORM
// Pure function: given a type index 0..5 and a phase 0..1, return
// a sample in 0..1. Used by TickLFOs every tick.
// ---------------------------------------------------------
Function SampleLFOWaveform(typeIdx : Integer, phase : Double) Returns Double
   var p : Double = phase
   if p < 0.0 then p = 0.0 end
   if p > 1.0 then p = p - Floor(p) end

   if typeIdx == 0 then
       // Triangle: 0 -> 1 -> 0 over the cycle
       if p < 0.5 then result = p * 2.0
       else result = 2.0 - (p * 2.0) end
   elsif typeIdx == 1 then
       // TriangleUp: 0 -> 1 linear, snap back at end
       result = p
   elsif typeIdx == 2 then
       // TriangleDown: 1 -> 0 linear, snap back at end
       result = 1.0 - p
   elsif typeIdx == 3 then
       // Sinus: 0 -> 1 -> 0, shifted so phase 0 = value 0
       result = (Sin(p * 2.0 * 3.14159265) + 1.0) / 2.0
   elsif typeIdx == 4 then
       // Square: 0 for first half, 1 for second half
       if p < 0.5 then result = 0.0 else result = 1.0 end
   elsif typeIdx == 5 then
       // Random: new value every tick (Math.random-ish)
       result = Rand()
   else
       result = 0.0
   end
End
```

**Note:** If `Rand()` / `Sin()` aren't GPScript built-ins under those names, replace with the actual names from the GPScript system function list. The memory reference `reference_gpscript_docs.md` may list the correct ones.

- [ ] **Step 2: Add `StartLFO` / `StopLFO` / `TickLFOs`**

```gpscript
// ---------------------------------------------------------
// LFO RUNTIME — start, stop, per-tick advance
// ---------------------------------------------------------

Function StartLFO(slot : Integer)
   var lfoIdx : Integer
   if slot < 0 or slot >= MAX_MACROS then
       // ignore
   else
       lfoIdx = LFO_ByMacro[slot]
       if lfoIdx < 0 then
           // nothing bound
       else
           LFO_PreValue[slot] = GetMacroValue(slot)
           LFO_StartTime[slot] = TimeSinceStartup()
           LFO_CyclesLeftI[slot] = LFO_Cycles[lfoIdx]
           LFO_Active[slot] = true
           LFO_LastSample[slot] = LFO_PreValue[slot]
           LFO_Progress[slot] = 0.0
           if DebugMode then Trace("LFO: StartLFO slot " + slot + " (" + LFO_Names[lfoIdx] + ", preVal=" + LFO_PreValue[slot] + ")") end
       end
   end
End

Function StopLFO(slot : Integer)
   if slot < 0 or slot >= MAX_MACROS then
       // ignore
   elsif not LFO_Active[slot] then
       // nothing to do
   else
       LFO_Active[slot] = false
       SetMacroValue(slot, LFO_PreValue[slot])
       LFO_LastSample[slot] = LFO_PreValue[slot]
       LFO_Progress[slot] = 0.0
       if DebugMode then Trace("LFO: StopLFO slot " + slot + " (snapped back to " + LFO_PreValue[slot] + ")") end
   end
End

Function TickLFOs()
   var slot, lfoIdx, beatsPerBar, cyclesDone : Integer
   var elapsedMS, cycleLenMS, phase, sample, bpm, totalBars, elapsedBars : Double

   bpm = GetBPM()
   if bpm < 1.0 then bpm = 120.0 end
   beatsPerBar = GetTimeSigNumerator()
   if beatsPerBar <= 0 then beatsPerBar = 4 end

   For slot = 0; slot < MAX_MACROS; slot = slot + 1 Do
       if LFO_Active[slot] then
           lfoIdx = LFO_ByMacro[slot]
           if lfoIdx < 0 then
               // binding removed mid-run
               LFO_Active[slot] = false
           else
               elapsedMS = TimeSinceStartup() - LFO_StartTime[slot]
               cycleLenMS = (60000.0 / bpm) * IntToFloat(beatsPerBar) * LFORateBars(LFO_Rates[lfoIdx])
               if cycleLenMS < 1.0 then cycleLenMS = 1.0 end

               phase = (elapsedMS / cycleLenMS) - Floor(elapsedMS / cycleLenMS)
               sample = SampleLFOWaveform(LFO_Types[lfoIdx], phase)
               SetMacroValue(slot, sample)
               LFO_LastSample[slot] = sample

               // Progress meter (V): 0..1 over total runtime
               if LFO_CyclesLeftI[slot] < 0 then
                   // Infinite: sawtooth resets every cycle
                   LFO_Progress[slot] = phase
               else
                   totalBars = LFORateBars(LFO_Rates[lfoIdx]) * IntToFloat(LFO_CyclesLeftI[slot])
                   elapsedBars = (elapsedMS / cycleLenMS) * LFORateBars(LFO_Rates[lfoIdx])
                   if totalBars > 0.0 then LFO_Progress[slot] = elapsedBars / totalBars
                   else LFO_Progress[slot] = 0.0 end
                   if LFO_Progress[slot] > 1.0 then LFO_Progress[slot] = 1.0 end

                   // Completion check
                   cyclesDone = Floor(elapsedMS / cycleLenMS)
                   if cyclesDone >= LFO_CyclesLeftI[slot] then
                       StopLFO(slot)
                   end
               end
           end
       end
   End
End
```

**Note:** `Floor`, `Sin`, `Rand`, `GetMacroValue`, `SetMacroValue` — verify the actual GPScript names via the reference in memory. If `SetMacroValue` isn't the exact name, it's likely `SetParameter(...)` on a dedicated Macros block or a widget. The subagent should trace the existing macro-writing code (e.g. how hardware-bound macros write values) and mirror that pattern.

- [ ] **Step 3: Call `TickLFOs()` from `On TimerTick`**

Find the existing `On TimerTick` callback (likely around line 14500–14700 based on the earlier grep). Add a call to `TickLFOs()` near the top:

```gpscript
On TimerTick
   // ... existing tick logic ...
   TickLFOs()
   // ... rest of existing tick logic ...
End
```

Place it near the other per-tick work. The subagent should grep for `On TimerTick` and pick the handler that already runs every tick (the one that drives Latch Auto-Release and prompter updates).

- [ ] **Step 4: Stop all LFOs on transport stop**

Locate the playhead-stop handler (grep for `TimelinePlaybackActive = false` and `Playhead`). Wherever transport goes from running to stopped, iterate and call `StopLFO(slot)` for every active slot:

```gpscript
   // Stop all active LFOs on transport stop
   var lfoSlot : Integer
   For lfoSlot = 0; lfoSlot < MAX_MACROS; lfoSlot = lfoSlot + 1 Do
       if LFO_Active[lfoSlot] then StopLFO(lfoSlot) end
   End
```

- [ ] **Step 5: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): runtime engine — Start, Stop, SampleLFOWaveform, TickLFOs

SampleLFOWaveform returns a 0..1 sample for a given type + phase,
covering Triangle / TriangleUp / TriangleDown / Sinus / Square /
Random. StartLFO caches the current macro value for snap-back and
records the start time. StopLFO writes the cached value back and
marks the slot inactive. TickLFOs (called once per On TimerTick)
iterates active slots, samples the waveform, writes the result via
SetMacroValue, updates the progress meter value, and invokes
StopLFO on Cycles completion.

Transport-stop path stops every active LFO and restores its
pre-trigger macro value."
```

---

## Task 6: Trigger `StartLFO` when a bound macro is written

**Files:**
- Modify: `Global Rackspace.gpscript` — wherever macros receive values (SECTION 22 / Hardware Input Processing or the existing macro-update dispatcher)

- [ ] **Step 1: Find the macro-write dispatcher**

Grep for `RecordTimelineEvent("Macro"` — that will land on the callback that fires when a macro receives a value. Around line 13319 based on earlier exploration.

- [ ] **Step 2: Inject a `StartLFO(paramIdx)` call**

Immediately after the `RecordTimelineEvent("Macro", paramIdx)` call (or wherever the macro's new value has been committed to the engine), add:

```gpscript
            // LFO trigger: if this macro is bound to an LFO, (re)start it
            if paramIdx >= 0 and paramIdx < MAX_MACROS and LFO_ByMacro[paramIdx] >= 0 then
                StartLFO(paramIdx)
                if DebugMode then Trace("LFO: StartLFO triggered by macro write on slot " + paramIdx) end
            end
```

Adjust `paramIdx` to match the local variable name in the actual handler.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): trigger LFO start on bound macro value write

Whenever a macro slot that has LFO_ByMacro[slot] >= 0 receives a new
value (from hardware, OSC, or Timeline playback), StartLFO(slot) is
called. This reuses the same dispatch point that records the macro
event to the Timeline, so live play, recorded playback, and manual
clicks all trigger the LFO identically."
```

---

## Task 7: Widget declarations + bootstrap registration

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 5 (GUI Widget Handles, ~219)

- [ ] **Step 1: Declare the LFO inspector widgets**

In SECTION 5 (the block of Widget declarations), add near the other Controller Map widgets:

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

**These handles must exist as widgets in the rackspace panel** — GPScript cannot create widgets. The subagent should confirm with the user that the panel layout has been updated before attempting to compile; if the widgets don't exist, the compiler will error.

- [ ] **Step 2: Commit (no code yet)**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): declare inspector widget handles

Declares the new LFO inspector widgets in SECTION 5. Actual widget
instances must be created in the rackspace panel before this commit
compiles — the declaration here is the link from the GPScript side
to the rackspace widget by name."
```

---

## Task 8: Widget callbacks — Prev/Next triples + Save + Delete + Run

**Files:**
- Modify: `Global Rackspace.gpscript` — SECTION 25-26 (Callbacks)

- [ ] **Step 1: Add the inspector update helper**

Placed near the callbacks (or as a utility in SECTION 13):

```gpscript
// ---------------------------------------------------------
// REFRESH LFO INSPECTOR DISPLAY
// Synchronizes the inspector widgets to LFO_SelectedIdx.
// ---------------------------------------------------------
Function RefreshLFOInspector()
   var typeIdx, rateIdx, cycles : Integer
   var boundSlot : Integer = -1
   var i : Integer

   if Size(LFO_Names) == 0 then
       SetWidgetLabel(LBL_LFO, "-")
       SetWidgetLabel(LBL_LFO_Type, "-")
       SetWidgetLabel(LBL_LFO_Rate, "-")
       SetWidgetLabel(LBL_LFO_Cycles, "-")
       SetWidgetLabel(LBL_LFO_BoundMacro, "Bound: -")
   else
       if LFO_SelectedIdx < 0 then LFO_SelectedIdx = 0 end
       if LFO_SelectedIdx >= Size(LFO_Names) then LFO_SelectedIdx = Size(LFO_Names) - 1 end

       typeIdx = LFO_Types[LFO_SelectedIdx]
       rateIdx = LFO_Rates[LFO_SelectedIdx]
       cycles = LFO_Cycles[LFO_SelectedIdx]

       SetWidgetLabel(LBL_LFO, LFO_Names[LFO_SelectedIdx])
       SetWidgetLabel(LBL_LFO_Type, LFOTypeName(typeIdx))
       SetWidgetLabel(LBL_LFO_Rate, LFORateName(rateIdx))
       SetWidgetLabel(LBL_LFO_Cycles, LFOCyclesName(cycles))

       // Find the macro slot bound to this LFO
       For i = 0; i < MAX_MACROS; i = i + 1 Do
           if LFO_ByMacro[i] == LFO_SelectedIdx and boundSlot == -1 then boundSlot = i end
       End
       if boundSlot >= 0 then
           SetWidgetLabel(LBL_LFO_BoundMacro, "Bound: Macro " + (boundSlot + 1))
       else
           SetWidgetLabel(LBL_LFO_BoundMacro, "Bound: -")
       end
   end
End
```

- [ ] **Step 2: Add browser cycle callbacks**

In SECTION 25-26:

```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Next
   if val > 0.5 then
       LFO_SelectedIdx = LFO_SelectedIdx + 1
       if LFO_SelectedIdx >= Size(LFO_Names) then LFO_SelectedIdx = 0 end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Next, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Prev
   if val > 0.5 then
       LFO_SelectedIdx = LFO_SelectedIdx - 1
       if LFO_SelectedIdx < 0 then LFO_SelectedIdx = Size(LFO_Names) - 1 end
       if LFO_SelectedIdx < 0 then LFO_SelectedIdx = 0 end
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Prev, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Type_Next
   if val > 0.5 and Size(LFO_Names) > 0 then
       var t : Integer = LFO_Types[LFO_SelectedIdx] + 1
       if t > 5 then t = 0 end
       LFO_Types[LFO_SelectedIdx] = t
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Type_Next, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Type_Prev
   if val > 0.5 and Size(LFO_Names) > 0 then
       var t : Integer = LFO_Types[LFO_SelectedIdx] - 1
       if t < 0 then t = 5 end
       LFO_Types[LFO_SelectedIdx] = t
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Type_Prev, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Rate_Next
   if val > 0.5 and Size(LFO_Names) > 0 then
       var r : Integer = LFO_Rates[LFO_SelectedIdx] + 1
       if r > 8 then r = 0 end
       LFO_Rates[LFO_SelectedIdx] = r
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Rate_Next, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Rate_Prev
   if val > 0.5 and Size(LFO_Names) > 0 then
       var r : Integer = LFO_Rates[LFO_SelectedIdx] - 1
       if r < 0 then r = 8 end
       LFO_Rates[LFO_SelectedIdx] = r
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Rate_Prev, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Cycles_Next
   if val > 0.5 and Size(LFO_Names) > 0 then
       var c : Integer = LFO_Cycles[LFO_SelectedIdx]
       if c == -1 then c = 0
       elsif c == 0 then c = 1
       else c = c + 1 end
       LFO_Cycles[LFO_SelectedIdx] = c
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Cycles_Next, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Cycles_Prev
   if val > 0.5 and Size(LFO_Names) > 0 then
       var c : Integer = LFO_Cycles[LFO_SelectedIdx]
       if c == 0 then c = -1
       elsif c == -1 then c = 16      // arbitrary cap when decrementing from Infinite
       elsif c == 1 then c = 0
       else c = c - 1 end
       LFO_Cycles[LFO_SelectedIdx] = c
       RefreshLFOInspector()
       SetWidgetValue(BTN_LFO_Cycles_Prev, 0.0)
   end
End
```

- [ ] **Step 3: Add Run / Save / Delete callbacks**

```gpscript
On WidgetValueChanged(val : Double) from BTN_LFO_Run
   var i, boundSlot : Integer
   if val > 0.5 then
       // Find a slot bound to the currently-selected LFO and start it
       boundSlot = -1
       For i = 0; i < MAX_MACROS; i = i + 1 Do
           if LFO_ByMacro[i] == LFO_SelectedIdx and boundSlot == -1 then boundSlot = i end
       End
       if boundSlot >= 0 then
           StartLFO(boundSlot)
           if DebugMode then Trace("LFO: manual Run start on slot " + boundSlot) end
       elsif DebugMode then
           Trace("LFO: manual Run ignored (no macro bound to LFO " + LFO_Names[LFO_SelectedIdx] + ")")
       end
   else
       // Button released -> stop all slots for this LFO
       For i = 0; i < MAX_MACROS; i = i + 1 Do
           if LFO_ByMacro[i] == LFO_SelectedIdx and LFO_Active[i] then StopLFO(i) end
       End
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Save
   if val > 0.5 then
       SaveLFOConfig()
       if DebugMode then Trace("LFO: SaveLFOConfig triggered") end
       SetWidgetValue(BTN_LFO_Save, 0.0)
   end
End

On WidgetValueChanged(val : Double) from BTN_LFO_Delete
   var i : Integer
   if val > 0.5 and Size(LFO_Names) > 0 then
       // Strip bindings pointing at this index
       For i = 0; i < MAX_MACROS; i = i + 1 Do
           if LFO_ByMacro[i] == LFO_SelectedIdx then
               if LFO_Active[i] then StopLFO(i) end
               LFO_ByMacro[i] = -1
           end
       End
       // Remove from registry
       LFO_Names = RemoveAt(LFO_Names, LFO_SelectedIdx)
       LFO_Types = RemoveAt(LFO_Types, LFO_SelectedIdx)
       LFO_Rates = RemoveAt(LFO_Rates, LFO_SelectedIdx)
       LFO_Cycles = RemoveAt(LFO_Cycles, LFO_SelectedIdx)
       if LFO_SelectedIdx >= Size(LFO_Names) then LFO_SelectedIdx = Size(LFO_Names) - 1 end
       if LFO_SelectedIdx < 0 then LFO_SelectedIdx = 0 end
       SaveLFOConfig()
       RefreshLFOInspector()
       if DebugMode then Trace("LFO: Delete completed, registry size now " + Size(LFO_Names)) end
       SetWidgetValue(BTN_LFO_Delete, 0.0)
   end
End
```

**Note:** `RemoveAt` may not be a GPScript built-in. If not, replace each call with a manual rebuild loop that copies every index except `LFO_SelectedIdx` into a fresh array.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): widget callbacks — browser cycles, Run, Save, Delete

Prev/Next cycles walk LFO_SelectedIdx (LFO), LFO_Types, LFO_Rates,
and LFO_Cycles. Cycles cycling has a special wrap path ('-' ->
Infinite -> 1 -> 2 -> ...) matching the spec enum.

BTN_LFO_Run starts the LFO on the currently-bound macro slot on
press and stops it on release. BTN_LFO_Save calls SaveLFOConfig.
BTN_LFO_Delete strips bindings pointing at the selected index,
removes it from the registry, and triggers a Save."
```

---

## Task 9: `SaveLFOConfig` + meter update + `ControllerMaps.txt` writer extension

**Files:**
- Modify: `Global Rackspace.gpscript` — near `LoadLFOConfig`, plus the existing ControllerMap save path

- [ ] **Step 1: Add `SaveLFOConfig`**

Immediately after `LoadLFOConfig`:

```gpscript
// ---------------------------------------------------------
// SAVE LFO CONFIG
// Writes the in-memory registry back to LFOConfig.txt. Called from
// BTN_LFO_Save and BTN_LFO_Delete.
// ---------------------------------------------------------
Function SaveLFOConfig()
   var content : String
   var i : Integer
   content = "; LFO Configurations (auto-generated by BTN_LFO_Save)" + NEW_LINE + NEW_LINE
   For i = 0; i < Size(LFO_Names); i = i + 1 Do
       content = content + "[LFO:" + LFO_Names[i] + "]" + NEW_LINE
       content = content + "Type   = " + LFOTypeName(LFO_Types[i]) + NEW_LINE
       content = content + "Rate   = " + LFORateName(LFO_Rates[i]) + NEW_LINE
       content = content + "Cycles = " + LFOCyclesName(LFO_Cycles[i]) + NEW_LINE
       content = content + NEW_LINE
   End
   SaveStringToTextFile(LFOConfigFilePath, content)
   if DebugMode then Trace("LFO: wrote " + Size(LFO_Names) + " entries to " + LFOConfigFilePath) end
End
```

Verify `SaveStringToTextFile` is the correct GPScript built-in; if not, use the same call that `SaveControllerMap` or similar persistence paths use in the existing codebase.

- [ ] **Step 2: Update the meters from `TickLFOs`**

Extend `TickLFOs` from Task 5 with two lines inside the `if LFO_Active[slot]` body after `LFO_LastSample[slot] = sample`:

```gpscript
               SetWidgetValue(METER_LFO_H, LFO_LastSample[slot])
               SetWidgetValue(METER_LFO_V, LFO_Progress[slot])
```

This drives the amplitude (H) and progress (V) meters. Because `TickLFOs` runs every slot in the loop, the meters show the last-written slot's state — fine as long as only one LFO is active at a time (the typical case). If multiple LFOs run simultaneously, the meters follow the last one in the iteration order.

- [ ] **Step 3: Extend the ControllerMap writer to emit `LFO:<Name>` at position 0**

Grep for the function that writes `ControllerMaps.txt` (likely `SaveControllerMap` or similar). When it builds each `Macro<N> = ...` line, check whether `LFO_ByMacro[N-1] >= 0`. If yes, prepend `LFO:<Name> | ` to the value part before the existing VST/CC links.

Example patch for the writer loop (exact lines depend on where the writer is):

```gpscript
// Inside the save loop that builds each Macro<N> line:
var lfoPrefix : String = ""
if LFO_ByMacro[slotIdx] >= 0 then
    lfoPrefix = "LFO:" + LFO_Names[LFO_ByMacro[slotIdx]] + " | "
end
line = "Macro" + (slotIdx + 1) + " = " + lfoPrefix + existingValuePart
```

The subagent should locate the exact writer function and adapt the patch to the existing variable names.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(lfo): SaveLFOConfig writer + meter updates + ControllerMap LFO prefix

SaveLFOConfig serializes the in-memory LFO registry back to
LFOConfig.txt with the same text format the parser consumes.

TickLFOs drives METER_LFO_H from LFO_LastSample (amplitude) and
METER_LFO_V from LFO_Progress (time).

SaveControllerMap writer prepends 'LFO:<Name> | ' to every Macro<N>
line whose slot has LFO_ByMacro[slot] >= 0, so round-tripping the
file preserves the binding without hand-editing."
```

---

## Verification (after all tasks)

No automated tests. After all commits, the user opens Gig Performer, copies `examples/LFOConfig.txt` into the user snapshot folder, updates the rackspace panel with the new LFO inspector widgets, and performs the following manual checks.

**A. Compile and cold-boot**

1. Paste the updated `Global Rackspace.gpscript`.
2. Compile — expect no compiler errors.
3. Script console expected traces at boot:
   - `LFO: registered 'TriSlow' type=Triangle rate=1/4 cycles=4`
   - `LFO: registered 'PadBreath' type=Sinus rate=1/1 cycles=Infinite`
   - `LFO: LoadLFOConfig complete, 2 entries`
   - `LFO: state arrays initialized (MAX_MACROS=256)`

**B. Bind an LFO to a macro**

1. Edit `examples/ControllerMaps.txt` and change one user-zone macro line to:
   `Macro10 = LFO:TriSlow | VST1_GRS:2:Level (p3) {0.0, 0.5}`
2. Reload the controller map.
3. Console expected: `LFO: bound slot 9 to LFO TriSlow (idx 0)`.

**C. Trigger the LFO**

1. Move the hardware control mapped to Macro 10.
2. Console expected: `LFO: StartLFO slot 9 (TriSlow, preVal=<X>)` followed by `LFO: StartLFO triggered by macro write on slot 9`.
3. The `VST1_GRS:2:Level` parameter visibly sweeps; `METER_LFO_H` moves in time with the waveform; `METER_LFO_V` ramps slowly from 0 to 1 over the 4 cycles.
4. After 4 cycles, the LFO completes; console expected: `LFO: StopLFO slot 9 (snapped back to <X>)`. The parameter returns to its pre-trigger value.

**D. Manual Run/Stop**

1. In the LFO Inspector, press `BTN_LFO_Run` (hold).
2. The selected LFO starts on its bound macro slot.
3. Release the button; the LFO stops and snaps back.

**E. Save and Delete**

1. In the inspector, cycle through Type / Rate / Cycles on `TriSlow` to new values, then press `BTN_LFO_Save`.
2. Open `LFOConfig.txt` on disk and confirm the values changed.
3. Press `BTN_LFO_Delete` on the second entry `PadBreath`.
4. Console expected: `LFO: Delete completed, registry size now 1`.
5. Reopen `LFOConfig.txt`: `PadBreath` is gone.

**F. Reject paths**

1. Add a test binding `Macro60 = LFO:TriSlow | VST1_GRS:0` (outside user zone).
2. Reload the map.
3. Console expected: `LFO: rejected outside user zone (slot 59)`. Macro 60 still parses the VST link normally; no LFO binding is registered.

---

## Self-Review

**Spec coverage:** §2.1 (LFOConfig.txt storage) — Task 1, Task 3. §2.2 (binding in ControllerMaps.txt) — Task 4. §2.3 (runtime semantics) — Task 5, Task 6. §2.4 (widget layout) — Task 7, Task 8. §2.5 (edge cases) — covered in Task 5 StopLFO (binding removed mid-run), Task 5 transport-stop handler, Task 5 BPM fallback.

**Placeholder scan:** Task 5 Step 1 notes `Rand()` / `Sin()` / `Floor()` need verification against the GPScript reference — this is a real uncertainty, not a placeholder. Task 5 Step 2 notes `GetMacroValue` / `SetMacroValue` similarly. Task 8 Step 3 notes `RemoveAt` may not be a GPScript built-in and provides a fallback instruction. Task 9 Step 1 notes `SaveStringToTextFile` verification. Task 9 Step 3 says "locate the exact writer function" — this is a directed search, not an unspecified placeholder. All code blocks are complete; the subagent has a clear recipe per step.

**Type consistency:** `LFO_ByMacro` is `Integer Array`, indexed by slot 0..MAX_MACROS-1, values -1..registry size. `LFO_Types[idx]` is 0..5, `LFO_Rates[idx]` is 0..8, `LFO_Cycles[idx]` is -1, 0, or >0. `SampleLFOWaveform` takes `typeIdx : Integer` and `phase : Double`, returns `Double`. `StartLFO`/`StopLFO` take `slot : Integer`. `TickLFOs` takes no arguments. `RefreshLFOInspector` takes no arguments. The callback loop variables (`t`, `r`, `c`) are declared inline with `var` inside their callback bodies — if GPScript rejects inline `var`, move each to the top of the callback.
