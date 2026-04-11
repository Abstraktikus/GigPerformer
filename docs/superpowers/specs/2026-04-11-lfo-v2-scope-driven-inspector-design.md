# LFO v2 — Scope-Driven Inspector, Multi-Bind, and Cross-Map Display

**Date:** 2026-04-11
**Supersedes:** the LFO sections (§2, §2.4 widget layout) of
`2026-04-11-lfo-looper-timeline-design.md`. The storage format and
runtime engine from that spec stay; this document replaces the
inspector UX, the binding model, and the widget set.

---

## 1. Overview & Goals

The original LFO design in `2026-04-11-lfo-looper-timeline-design.md`
treated LFOs as a flat global registry addressed by a standalone
`BTN_LFO_Prev/Next` browser. A bound macro had exactly one LFO, and
the inspector cycled through LFO entries independently of which
macro was selected.

Live-performance use revealed two structural mismatches:

1. **One LFO, many targets.** A single LFO (e.g. `"SlowHip80erDream"`)
   is typically attached to several macros across one or more
   Controller Maps at once — not just one. The original "one slot,
   one LFO" mental model forces the user to duplicate entries.

2. **The LFO is a property of the macro, not a first-class browsable
   entity.** The useful question at edit time is "what LFO does
   **this** macro have?", not "let me browse LFOs in the abstract."
   The independent browser added a navigation step for no gain.

### What v2 changes

- **Storage stays flat** in `LFOConfig.txt`. No `ControllerMap` field.
  Name is the only key.
- **A `[LFO:Standard]` entry is honored as a user-customisable draft
  template.** Falls back to hardcoded `Triangle / 1/4 / Infinite` if
  absent.
- **Bindings live entirely in `ControllerMaps.txt`.** The authoritative
  answer to "where is this LFO used?" comes from parsing every
  `[Map:...]` section for `LFO:<Name> |` prefixes. Bootstrap builds a
  reverse index.
- **The inspector is scope-driven.** What it shows is a pure function
  of `LBL_Edit_Scope` — no independent LFO browser. Changing the
  editor scope (existing `BTN_Scope_Prev/Next`) changes which LFO
  the inspector displays.
- **`LBL_LFO_BoundMacro` becomes a scrollable, cross-map display**
  listing every `(Map, Macro)` pair where the currently-shown LFO is
  used. Format mirrors `LBL_LooperConfiguration` /
  `LBL_MIDIConfiguration` / `LBL_ControllerInfo`.
- **A new `BTN_Bind_Macro` button** attaches the currently-displayed
  LFO (real or draft) to the current scope — gated by a user-zone
  whitelist.
- **Smart auto-jump on song load** sends `CurrentEditScope` to the
  first macro that already has an LFO bound, so the inspector opens
  on useful data by default. The old `(All Sliders)` fallback label
  is renamed to `(All User Macros)`.

---

## 2. Storage & Identity

`LFOConfig.txt` stays flat. Identity is the LFO name, period. Multiple
Controller Maps referring to the same name all get the same shape.

```
; LFO Configurations
; Type:   Triangle, TriangleUp, TriangleDown, Sinus, Square, Random
; Rate:   8/1, 4/1, 2/1, 1/1, 1/2, 1/4, 1/8, 1/16, 1/32
; Cycles: -, Infinite, or a positive integer

[LFO:Standard]
; Template used by the draft editor when a scope has no LFO yet.
Type   = Triangle
Rate   = 1/4
Cycles = Infinite

[LFO:SlowHip80erDream]
Type   = Sinus
Rate   = 1/1
Cycles = Infinite
```

### `[LFO:Standard]` as the draft template

When the inspector enters a draft state (scope selected but the scope
has no LFO yet), it populates Type/Rate/Cycles from `[LFO:Standard]`
if present, otherwise from a hardcoded fallback. Users can customise
"what a new LFO looks like" without touching the script. The name
`Standard` is reserved — attempting to Bind a macro while
`LBL_LFO == "Standard"` is not a special case; it just creates the
entry if missing or updates it if present.

### Bindings live in `ControllerMaps.txt`

No back-reference from `LFOConfig.txt`. The authoritative "who uses
this LFO" answer comes from scanning every `[Map:...]` section for
the `LFO:<Name> |` prefix on macro lines. See §3 for the reverse
index that materialises this at bootstrap.

---

## 3. Bootstrap Reverse-Index & Runtime State

### The index

Four parallel state arrays, all indexed 0..N by binding number:

```gpscript
LFO_Usage_LfoIdx   : Integer Array   // which LFO_Names[] entry
LFO_Usage_MapIdx   : Integer Array   // which CtrlMapList[] entry
LFO_Usage_MacroIdx : Integer Array   // which macro slot (0..49)
LFO_Usage_RawLine  : String Array    // cached raw `Macro<N> = <value>` line
                                     // from ControllerMaps.txt, used by the
                                     // inactive-map display path in §5.
```

All four arrays have identical size, equal to the total binding count
across the entire file. A binding `i` is the tuple
`(LFO_Usage_LfoIdx[i], LFO_Usage_MapIdx[i], LFO_Usage_MacroIdx[i],
LFO_Usage_RawLine[i])`. The raw-line cache is filled during
`BuildLFOUsageIndex()` so that `LBL_LFO_BoundMacro` can render
cross-map bindings without re-reading `ControllerMaps.txt` on every
refresh.

### `BuildLFOUsageIndex()` — the build step

Called during Bootstrap PHASE 5 after `LoadLFOConfig()` completes, and
again after every mutation path that rewrites `ControllerMaps.txt`
(`BTN_LFO_Save`, `BTN_LFO_Delete`, `BTN_Bind_Macro`, explicit user
edits observed via `LoadControllerMap`).

Algorithm:

1. Clear the three `LFO_Usage_*` arrays.
2. Read `ControllerMaps.txt` into a string once (the file is small).
3. Walk every `[Map:<name>]` section. For each `Macro<N> = <value>`
   line:
   - Split `<value>` on `|`. Trim the first entry.
   - If it starts with `LFO:`, extract the name after `LFO:`.
   - Look up `lfoIdx = LFO_Names.indexOf(name)`.
   - If `lfoIdx >= 0`: append the tuple to the three arrays.
   - If `lfoIdx < 0`: orphan — `DebugMode` trace `"LFO:
     orphan binding '<name>' in [<map>] Macro<N>, not in registry"`,
     skip. Don't rewrite the file.
4. Emit a single summary trace with the final binding count.

### Registry vs. runtime state

Two related but distinct states:

| State | Where | Lifetime |
|---|---|---|
| `LFO_Names/Types/Rates/Cycles` | registry, all LFOs ever defined | full session, rebuilt on `LoadLFOConfig` |
| `LFO_Usage_*` (three arrays) | reverse index | rebuilt by `BuildLFOUsageIndex` after any file mutation |
| `LFO_ByMacro[slot]` | per-slot active binding | rebuilt by `LoadControllerMap` — **only the currently-loaded map's bindings** |

The runtime engine (`StartLFO(slot)`, `TickLFOs()`) only looks at
`LFO_ByMacro[]` — it fires LFOs for the currently active map, same as
today. `LFO_Usage_*` is display-only: it drives
`LBL_LFO_BoundMacro`'s scrollable list, which can show bindings from
maps that aren't currently loaded.

### Orphan policy

An LFO entry in `LFOConfig.txt` with zero usage anywhere is valid — it
just isn't firing. Do not garbage-collect. The user may have saved an
LFO and not bound it yet, or may have deleted a bound macro line
outside the editor. No automatic cleanup.

An `LFO:<Name> |` prefix in `ControllerMaps.txt` that references an
unknown name is also tolerated at parse time — the parser strips the
token and the remaining VST/CC links parse normally (same Isolation
rule as SYSACT). The prefix is simply invisible at runtime until the
missing registry entry is added.

---

## 4. Scope-Driven Inspector & Auto-Jump

There is no independent LFO browser. The inspector's content is a
pure function of `CurrentEditScope` and the current state of the
registry and `LFO_ByMacro[]`.

### State resolution — `RefreshLFOInspector()`

Called whenever `CurrentEditScope` changes, whenever a mutation path
(`BTN_Bind_Macro`, Save, Delete) completes, and once at the end of
bootstrap.

Pseudo-code:

```
scopeSlot = CurrentEditScope

if scopeSlot < 0 or scopeSlot >= 50:
    state = LOCKED
elsif LFO_ByMacro[scopeSlot] >= 0:
    state = EDIT
    lfoIdx = LFO_ByMacro[scopeSlot]
elsif FindLfoByName("Standard") >= 0:
    state = DRAFT_STANDARD
    draft.Type/Rate/Cycles = registry entry for "Standard"
    draft.name = current song name
else:
    state = DRAFT_FALLBACK
    draft.Type/Rate/Cycles = Triangle / 1/4 / Infinite
    draft.name = current song name
```

### Display states

| State | `LBL_LFO` | Type / Rate / Cycles | `LBL_LFO_BoundMacro` | Enabled buttons |
|---|---|---|---|---|
| **LOCKED** | `—` | `—` | `Only User Macros allowed (scope 1–50)` | none |
| **EDIT** | real name from registry | real values from registry | cross-map binding list (see §5) | Save, Delete, Bind (becomes "Already bound" flash), Run, Type/Rate/Cycles editors |
| **DRAFT_STANDARD** | current song name | copy of `[LFO:Standard]` | `(draft — bind to save)` | Bind, Run (temporary preview), Type/Rate/Cycles editors |
| **DRAFT_FALLBACK** | current song name | `Triangle / 1/4 / Infinite` | `(draft — bind to save)` | Bind, Run (temporary preview), Type/Rate/Cycles editors |

In EDIT state, `BTN_Bind_Macro` is technically still live but its
callback detects that the scope is already bound and flashes
`Already bound (use Save to update)` instead of performing a second
bind. See §6.

### Auto-Jump on Song Load

Two linked changes:

**A. Rename the GLOBAL fallback label**

In `UpdateEditScopeDisplay()` and any other occurrence, replace
`[GLOBAL] (All Sliders)` with `[GLOBAL] (All User Macros)`. Pure
label change, no semantic change — the scope still means "all
user-zone macros, no single edit target."

**B. First-LFO jump at the end of `LoadSongSnapshot`**

After the active Controller Map has been loaded and
`BuildLFOUsageIndex()` has run, iterate macro slots 0..49 in
ascending order. The first slot with `LFO_ByMacro[slot] >= 0` wins:

```
CurrentEditScope = slot
UpdateEditScopeDisplay()
RefreshLFOInspector()
```

If no user-zone slot has an LFO, leave `CurrentEditScope = -1` — the
user lands on `[GLOBAL] (All User Macros)` as the fallback, and the
inspector shows LOCKED state with a hint.

The jump fires **once per song load**. Manual scope changes after
that stick until the next song load.

---

## 5. `LBL_LFO_BoundMacro` Display Format

The label becomes a scrolling list, backed by a new `String Array`
`LFOBind_Lines` and paginated via the new `SLD_LFOBoundMacro`
scrollbar widget. Pagination helper mirrors `RefreshLooperConfigDisplay`
at Global Rackspace.gpscript:4043.

### Head-line-only rule

If a macro drives multiple VST/CC targets, `LFOBind_Lines` emits
**only the first (head) line** — the indented `  -> additional target`
rows from `CtrlInfo_Lines` are collapsed here. Rationale: the binding
list answers "which macros use this LFO", not "what does each macro
do in full detail." The full target tree is available elsewhere
(`LBL_ControllerInfo` / the scope-driven inspector).

### Example layout

```
--- LFO BINDINGS: TriSlow ---
[Map: SlowHip80erDream]
  Macro 5 [CC17]: VST1_GRS:1 Filter Cutoff {0%-50%}
  Macro 10: Ch13:CC7 Volume Triton
[Map: Standard_VST1]
  Macro 7 [CC19]: VST1_GRS:0 Level (p1) {0%-29%}
  Macro 12: VST1_GRS:4 Level (p5)
```

### Build algorithm — `BuildLFOBindLines(lfoIdx)`

Called from `RefreshLFOInspector()`. In DRAFT and LOCKED states, it
writes a single-line placeholder and returns immediately. In EDIT
state:

1. `LFOBind_Lines = []`
2. Emit header: `"--- LFO BINDINGS: " + LFO_Names[lfoIdx] + " ---"`
3. Walk `LFO_Usage_*`, collect all indices where
   `LFO_Usage_LfoIdx[i] == lfoIdx`. Group hits by `LFO_Usage_MapIdx`.
   Sort map groups by map name; within each group, sort macros
   ascending by slot index.
4. For each map group:
   - Emit `"[Map: " + CtrlMapList[mapIdx] + "]"`
   - For each macro in the group, emit the head line (see below).
5. Call `ScrollToLFOBoundMacro()` — auto-scroll logic matching
   `BuildLooperConfigLines` at 4210: centre on the focused binding
   (the one matching `CurrentEditScope` if the active map is
   displayed, otherwise the first entry).

### Head-line format

The line combines `hwStr` (hardware assignment, same
`GetAssignedHWString(macroIdx)` helper used by `CtrlInfo_Lines`) with
the first target of the macro's binding. Two cases:

**Case A — active map.** When the binding belongs to the currently
loaded Controller Map, the first target is available in the existing
`Link_*` arrays. Format matches `CtrlInfo_Lines` at 3154:

```
"  Macro " + (macroIdx+1) + hwStr + ": " + Link_BlockName[idx] + ":" + realName + valStr
```

where `realName = Link_ExpectedName[idx]` (fallback `"Param " +
Link_TargetParam[idx]`) and `valStr` is the `{min%-max%}` range
suffix, same as `CtrlInfo_Lines`.

**Case B — inactive map.** When the binding belongs to a map that
isn't currently loaded, `Link_*` is empty for that map. We re-parse
the raw value string from `ControllerMaps.txt` (cached by
`BuildLFOUsageIndex` in a parallel `LFO_Usage_RawLine : String Array`
alongside the three `Integer Arrays`), strip the leading `LFO:<name>
|`, split on `|`, take the first entry, and emit it verbatim:

```
"  Macro " + (macroIdx+1) + ": " + firstEntry
```

The verbatim form lacks the pretty parameter name resolution because
we can't call `GetPluginInfo` on a plugin that isn't loaded. That's
acceptable — the raw `VST1_GRS:48:Filter Cutoff {0.000, 0.500}` line
from the file is already self-describing.

### Flash surface

`LBL_LFO_BoundMacro` doubles as a short-lived flash-message target
for transient feedback from widget callbacks — specifically
`BTN_Bind_Macro`'s "Only User Macros allowed" warning and the
"Already bound" feedback in EDIT state. Implementation:

```gpscript
LFOFlashMsg   : String = ""
LFOFlashTimer : Double = 0.0
```

When a callback wants to flash, it sets the message and
`LFOFlashTimer = TimeSinceStartup() + 1000.0`, then calls
`RefreshLFOInspector()`. `RefreshLFOInspector()` checks the timer: if
active, it prepends `"[" + LFOFlashMsg + "]"` as the first line of
`LFOBind_Lines` and calls itself from `On TimerTick` at the expiry
moment to clear. Normal content returns after expiry.

---

## 6. Widget Actions & Callbacks

Four interactive buttons govern the LFO lifecycle. Each has a precise
pre-condition and produces a single atomic effect on disk and state.

### `BTN_Bind_Macro` — attach the displayed LFO to the current scope

Callback:

1. **Read context.** `scopeSlot = CurrentEditScope`,
   `mapName = CurrentCtrlMapName`.
2. **Whitelist check.** If `scopeSlot < 0 or scopeSlot >= 50`, flash
   `"Only User Macros allowed (scope 1–50)"` for 1000ms, reset the
   widget to `0.0`, return.
3. **Resolve LFO name.**
   - EDIT state → the scope is already bound; flash
     `"Already bound (use Save to update)"` and return.
   - DRAFT state → the name is always the current song name. `LBL_LFO`
     is a display-only label (GPScript has no inline text input), so
     there is no rename path at bind time. If the user wants a
     different name later, they delete the LFO and re-bind from a
     song that has the desired name — or edit `LFOConfig.txt` and
     `ControllerMaps.txt` by hand.
4. **Create-or-update registry entry.** If an entry with that name
   exists in `LFO_Names`, overwrite its Type/Rate/Cycles with the
   draft values (user is adopting the name with new settings). If
   new, append a fresh entry.
5. **Mutate `ControllerMaps.txt`.** Read the file, find the
   `[Map:<mapName>]` section, locate the
   `Macro<scopeSlot+1> = <value>` line, prepend `LFO:<name> | ` to
   the value part. If the line has no value, create it with only
   `LFO:<name>` (edge case — legal because Bind-then-save can
   add targets later). If a different `LFO:<other> | ` prefix
   already occupies position 0, replace it. Save the file.
6. **Rebuild state.** `SaveLFOConfig()`,
   `LoadControllerMap(mapName)`, `BuildLFOUsageIndex()`,
   `RefreshLFOInspector()`. After the rebuild the inspector finds
   `LFO_ByMacro[scopeSlot] >= 0` and enters EDIT state
   automatically.
7. Reset widget. `DebugMode` trace.

### `BTN_LFO_Save` — persist Type/Rate/Cycles edits

Enabled only in EDIT state.

1. Guard: `if state != EDIT then return`.
2. Write current draft values back into
   `LFO_Types/Rates/Cycles[lfoIdx]`.
3. `SaveLFOConfig()` — serialises the full registry to
   `LFOConfig.txt`.
4. **No mutation of `ControllerMaps.txt`.** Bindings haven't changed,
   only shape.
5. **No `BuildLFOUsageIndex()` rebuild.** The reverse index is
   binding-structured, not shape-structured, and bindings are
   unchanged.
6. `RefreshLFOInspector()` — redraw for consistency, a no-op visually.
7. `DebugMode` trace.

### `BTN_LFO_Delete` — teardown across all maps

Enabled only in EDIT state. The most invasive action.

1. Guard: `if state != EDIT then return`.
2. **Stop any running instance.** Walk `LFO_Active[]`; for every slot
   where `LFO_Active[i] and LFO_ByMacro[i] == lfoIdx`, call
   `StopLFO(i)` (performs the snap-back to the pre-trigger value so
   no parameter is left mid-sweep).
3. **Strip all `LFO:<name> |` prefixes from `ControllerMaps.txt`.**
   Walk every `[Map:...]` section; for each macro line starting
   with `LFO:<name>`, remove the `LFO:<name> | ` prefix. If that
   leaves an empty value, remove the whole `Macro<N> =` line
   (defensive — the whitelist at Bind time should prevent this
   state, but be robust). Save the file.
4. **Remove from registry.** Delete the entry from
   `LFO_Names/Types/Rates/Cycles` by rebuilding the arrays without
   `lfoIdx`. `SaveLFOConfig()`.
5. **Rebuild state.** `LoadControllerMap(CurrentCtrlMapName)` (the
   current scope's `LFO_ByMacro` entry becomes `-1`),
   `BuildLFOUsageIndex()` (reverse index shrinks),
   `RefreshLFOInspector()` (the scope now renders DRAFT state
   because its LFO is gone).
6. `DebugMode` trace with the unbind count across all maps.

### `BTN_LFO_Run` — manual test run, preview mode in DRAFT

Press-and-hold button. Release stops.

- **EDIT state** → press calls `StartLFO(scopeSlot)` targeting the
  existing `LFO_ByMacro[scopeSlot]` binding. Release calls
  `StopLFO(scopeSlot)`. Snap-back to the macro's pre-trigger value.
- **DRAFT state** → press starts a **temporary preview LFO** using
  the draft Type/Rate/Cycles directly, targeting the current scope
  slot. Implementation: a dedicated `LFO_Draft_*` state block (one
  global, since only one draft is ever active) handled by a special
  branch in `TickLFOs()`. Release stops and snaps back. The preview
  is never persisted; it exists only between press and release.

### `BTN_LFO_Type_Prev/Next`, `BTN_LFO_Rate_Prev/Next`, `BTN_LFO_Cycles_Prev/Next`

Cycle the enum, update either the registry entry (EDIT) or the draft
values (DRAFT), call `RefreshLFOInspector()`. No disk writes — Save
persists in EDIT, Bind persists in DRAFT.

### Deleted from Plan #3

- `BTN_LFO_Prev`, `BTN_LFO_Next` — the standalone LFO browser no
  longer exists. Cycling LFOs is achieved by cycling macros via the
  existing `BTN_Scope_Prev/Next`.
- `LFO_SelectedIdx` / `LFO_ManualRun` state vars from Plan #3 Task 2
  — replaced by scope-driven resolution.

---

## 7. Data Structures Summary

```gpscript
// Registry (unchanged from Plan #3 Task 2)
LFO_Names       : String Array
LFO_Types       : Integer Array   // 0..5 — Triangle..Random
LFO_Rates       : Integer Array   // 0..8 — 8/1..1/32
LFO_Cycles      : Integer Array   // -1=Infinite, 0='-', N>0=finite

// Runtime per-slot (unchanged from Plan #3 Task 2)
LFO_ByMacro     : Integer Array   // MAX_MACROS slots, -1 or lfoIdx
LFO_Active      : Boolean Array
LFO_StartTime   : Double Array
LFO_PreValue    : Double Array
LFO_CyclesLeftI : Integer Array
LFO_LastSample  : Double Array
LFO_Progress    : Double Array

// NEW — cross-map reverse index (four parallel arrays)
LFO_Usage_LfoIdx    : Integer Array
LFO_Usage_MapIdx    : Integer Array
LFO_Usage_MacroIdx  : Integer Array
LFO_Usage_RawLine   : String Array   // cached raw ControllerMaps line for inactive-map display

// NEW — draft state (DRAFT_STANDARD and DRAFT_FALLBACK)
LFO_Draft_Active  : Boolean
LFO_Draft_Name    : String
LFO_Draft_Type    : Integer
LFO_Draft_Rate    : Integer
LFO_Draft_Cycles  : Integer
// Preview-LFO additions for BTN_LFO_Run in DRAFT
LFO_Draft_Running : Boolean
LFO_Draft_Slot    : Integer   // which scope slot the preview targets
LFO_Draft_StartTime : Double
LFO_Draft_PreValue : Double

// NEW — flash surface for LBL_LFO_BoundMacro
LFOFlashMsg   : String
LFOFlashTimer : Double

// NEW — display lines array (matches LooperConfig_Lines pattern)
LFOBind_Lines : String Array
```

Widgets:

```gpscript
// KEPT from Plan #3
LBL_LFO                                                        : Widget
BTN_LFO_Type_Prev, BTN_LFO_Type_Next, LBL_LFO_Type             : Widget
BTN_LFO_Rate_Prev, BTN_LFO_Rate_Next, LBL_LFO_Rate             : Widget
BTN_LFO_Cycles_Prev, BTN_LFO_Cycles_Next, LBL_LFO_Cycles       : Widget
METER_LFO_H, METER_LFO_V                                       : Widget
BTN_LFO_Run, BTN_LFO_Save, BTN_LFO_Delete                      : Widget

// NEW
BTN_Bind_Macro                                                 : Widget
LBL_LFO_BoundMacro, SLD_LFOBoundMacro                          : Widget   // was LBL only, now with scrollbar

// DELETED from Plan #3
// BTN_LFO_Prev, BTN_LFO_Next                                  : Widget
```

---

## 8. Migration from Plan #3

Plan #3 parser work (`LoadLFOConfig`, `LoadControllerMap` extension
for `LFO:<Name> |`) stays. Runtime engine (`SampleLFOWaveform`,
`StartLFO`, `StopLFO`, `TickLFOs`) stays. Bootstrap state-array
initialisation stays. These were already implemented in commits
`6252dab`, `5e78bd0`, `e09ec09`, `f3c22db`, `8563c14` on the feature
branch.

**What needs to be added on top:**

1. `BuildLFOUsageIndex()` + the four `LFO_Usage_*` arrays.
2. `BuildLFOBindLines(lfoIdx)` + the `LFOBind_Lines` array + the
   pagination helper `ScrollToLFOBoundMacro()`.
3. `RefreshLFOInspector()` rewrite — state resolution logic from §4.
4. `LBL_Edit_Scope` auto-jump in `LoadSongSnapshot`.
5. Rename `(All Sliders)` → `(All User Macros)`.
6. `BTN_Bind_Macro` callback + whitelist flash.
7. `BTN_LFO_Save` rework — narrow scope (registry-only, no file
   rewrite beyond `LFOConfig.txt`).
8. `BTN_LFO_Delete` rework — cross-map strip logic in
   `ControllerMaps.txt`.
9. `BTN_LFO_Run` draft-preview path in `TickLFOs()`.
10. `LFO_Draft_*` state arrays + draft-mode Type/Rate/Cycles callbacks.
11. Flash surface (`LFOFlashMsg`, `LFOFlashTimer`).

**What gets deleted:**

- `BTN_LFO_Prev`, `BTN_LFO_Next` widgets and their callbacks from
  Plan #3 Task 8.
- `LFO_SelectedIdx`, `LFO_ManualRun` state vars from Plan #3 Task 2.
- The `RefreshLFOInspector()` implementation from Plan #3 Task 8 is
  replaced entirely.

---

## 9. Out of scope

- **Rename-in-place.** The LFO name is fixed at creation: it is the
  song name active at the moment `BTN_Bind_Macro` is clicked.
  `LBL_LFO` is a display-only label, so there is no runtime text
  input for name editing. Renaming requires Delete + re-Bind from a
  song whose name matches the desired LFO name, or a manual edit of
  `LFOConfig.txt` + `ControllerMaps.txt`. A future extension could
  add a rename path, but it must atomically rewrite the registry
  and every `ControllerMaps.txt` prefix — significant work for
  marginal gain.
- **Multi-LFO-per-macro.** A macro still has at most one LFO. The
  reverse index supports many-to-many shape in principle, but the
  UX and the runtime engine are one-LFO-per-slot.
- **Cross-session draft persistence.** If the user configures a
  draft (Type/Rate/Cycles + name), then changes scope before
  clicking Bind, the draft is lost. Drafts exist only for the
  duration a scope is focused without a real binding.
- **Orphan cleanup.** Registry entries with zero usage stay.
  `ControllerMaps.txt` prefixes referencing unknown names are
  silently ignored at parse time. Any automatic cleanup would
  destroy user intent.

---

## 10. Build order for the plan

Rough sequencing:

1. `LFO_Usage_*` state declarations + `BuildLFOUsageIndex()` +
   bootstrap call.
2. `LFOBind_Lines` array + `BuildLFOBindLines(lfoIdx)` head-line
   formatter + `RefreshLooperConfigDisplay`-style pagination helper
   `RefreshLFOBoundMacroDisplay()`.
3. `RefreshLFOInspector()` full rewrite with state resolution
   (LOCKED / EDIT / DRAFT_STANDARD / DRAFT_FALLBACK).
4. Auto-jump at end of `LoadSongSnapshot` + `(All Sliders)` →
   `(All User Macros)` label rename.
5. `BTN_Bind_Macro` widget declaration, callback, whitelist, flash
   mechanism (`LFOFlashMsg`, `LFOFlashTimer`).
6. `BTN_LFO_Save` rework to narrow scope (registry only, not
   `ControllerMaps.txt`).
7. `BTN_LFO_Delete` rework with cross-map strip logic.
8. `BTN_LFO_Run` draft-preview path in `TickLFOs()` +
   `LFO_Draft_Running/Slot/StartTime/PreValue` state.
9. Delete `BTN_LFO_Prev/Next` widget declarations and callbacks.
10. Delete `LFO_SelectedIdx` / `LFO_ManualRun` state vars.

Each step is independently testable (trace-only verification per the
project's existing workflow) and each produces a committable
increment.
