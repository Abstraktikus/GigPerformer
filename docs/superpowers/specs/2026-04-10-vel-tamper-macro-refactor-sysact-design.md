# Design: Velocity Range Tamper, Macro Space Renumbering, and System Action Framework

**Date:** 2026-04-10
**Scope:** Three mini-features bundled into a single coordinated change.
**Files touched:** `Note Prozessor.gpscript`, `Global Rackspace.gpscript`

## Context & Motivation

Three independent but architecturally adjacent improvements are packaged together because they all touch the macro space and controller-map machinery in the Global Rackspace:

- **Feature A — Velocity Range Tamper:** A velocity analogue of the existing `BTN_Inject_NP_OctRangeFade`. Hitting narrow velocity windows (`p_MinVel`/`p_MaxVel`) is hard in live performance. The tamper softens the edges inside the range so that notes within the window fade in/out gradually while notes outside the window remain fully gated. Makes difficult ranges musically forgiving.
- **Feature B — Macro Space Renumbering + ControllerInfo Loop Fix + Legacy Group-Keyword Removal:** Three related cleanups in the macro space and map-parser layer. (1) The display loop in `UpdateControllerInfoDisplay()` caps at index 128 while default macro assignments extend to 193 — Octaver (130–145), Humanizer (146–161), Scale Quantizer (162–177), and Auto Sustain (178–193) never appear in `LBL_ControllerInfo`, and two of Root/Chord's channels (128, 129) are silently dropped. (2) `MAX_MACROS = 100` is inconsistent with the same defaults. (3) The 10 channel-indexed group-role keywords (`LOOPER_CH*` through `SUSTAIN_CH*`) are removed from `ControllerMaps.txt` parsing — they now live solely as Init-time defaults, freeing the user to think purely in user-macro slots 1–50 without worrying about which slots do system work. Going forward we reserve macro slots 1–50 (indices 0–49) for the user's own assignments and place all system groups at slot 51+ (indices 50+).
- **Feature C — System Action Framework:** SYSMODE joystick actions (VST scope, preset, looper rec, strip macro toggle, part jump, etc.) currently bypass the macro layer via direct function calls. This means (1) they cannot be triggered by hardware buttons through `ControllerMaps.txt`, only by joystick, and (2) the SYSMODE design is tangled into `ProcessSystemNavigation()`. A clean "virtual role" layer lets any of these actions be bound to any user-macro slot as a role.

All three features share a commitment: **the user thinks in roles and behaviors, not in macro numbers.** The 50 free macros are the user's canvas; everything else is either a built-in group (Looper, Smart Solo, …) or a central system action registry.

---

## Feature A — Velocity Range Tamper

### Template

`GetOctRangeVelocity()` in `Note Prozessor.gpscript:255` is the blueprint. The new function follows the same shape but uses a percentage-based pad instead of a fixed 5-note window.

### Parameter & Widget

| Name | Location | Type | Default | Notes |
|---|---|---|---|---|
| `p_VelRangeFade` | `Note Prozessor.gpscript` Var block, next to `p_MaxVel` | `Parameter 0 .. 1` | `0` | Binary toggle, parallel to `p_OctRangeFade` |
| `VelTamperPadPct` | `Note Prozessor.gpscript` Var block, top-level constant near other helpers | `Double` | `0.10` | User-tunable via script edit. Comment explains semantics: inside-range padding fraction per side. |
| `BTN_Inject_NP_VelTamper` | `Global Rackspace.gpscript` widget declaration block | `Widget` | — | UI button, placed on the Inject panel near the existing `BTN_Inject_NP_VelRange` |
| `Mem_NP_VelRangeFade` | Global Rackspace snapshot RAM, parallel to `Mem_NP_OctRangeFade` | `Integer Array = [0,0,...,0]` (16 elements) | — | Per-channel snapshot slot for save/load |

Reset entries are added in the factory reset block (`Note Prozessor.gpscript:162` area) and in the Global Rackspace channel-strip factory reset (`Global Rackspace.gpscript:1642` area).

### Fade Math

```gpscript
Function GetVelRangeVelocity(vel : Integer) Returns Integer
   var minVel, maxVel, span, pad, dist, distHigh : Integer
   var factor : Double = 1.0
   var res : Integer = vel

   minVel = Round(p_MinVel)
   maxVel = Round(p_MaxVel)
   span = maxVel - minVel

   // Gate: outside range -> suppress (unchanged hard gate)
   if vel < minVel or vel > maxVel then
      res = 0
   else
      // Fader: only when active AND span is wide enough for a meaningful ramp
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

Ramp shape matches `GetOctRangeVelocity`: at `dist == 0` (exactly at the range edge), `factor = 1/(pad+1)`; at `dist == pad-1`, `factor = pad/(pad+1)`; at `dist >= pad`, `factor = 1.0` (no scaling). The floor on `res` at 1 ensures "audible inside, muted outside" — the first inaudible velocity is exactly at `minVel-1` and `maxVel+1`.

**Span gate:** `span >= 20` suppresses the fader for tight ranges (`pad` would be 1, i.e. a 1-note ramp is indistinguishable from the hard gate). Parallel to OctRange's `rangeSpan >= 10` gate.

### Integration Point

Replace the hard-gate block in `Note Prozessor.gpscript:613`:

```gpscript
// BEFORE
if Round(p_VelRangeActive) == 1 and (vel < Round(p_MinVel) or vel > Round(p_MaxVel)) then
    // Out of Range -> Ignorieren!
else
    newVel = GetScaledVelocity(rawNote, vel)
    ...
```

becomes:

```gpscript
// AFTER
if Round(p_VelRangeActive) == 1 then
    vel = GetVelRangeVelocity(vel)
end
if vel > 0 then
    newVel = GetScaledVelocity(rawNote, vel)
    ...
```

When `p_VelRangeFade` is 0, `GetVelRangeVelocity()` still performs the hard-gate behavior (returns 0 outside, unchanged inside) — fully backwards-compatible.

### Injection Callbacks (Global Rackspace)

Three new handlers parallel to the existing `BTN_Inject_NP_OctRangeFade` flow around `Global Rackspace.gpscript:12636`:

1. `On WidgetValueChanged(val : Double) from BTN_Inject_NP_VelTamper` → `InjectNPToggle(<slot>, "p_VelRangeFade", val)`
2. Default sync block (snapshot restore) at `Global Rackspace.gpscript:2140` area: `SetWidgetValue(BTN_Inject_NP_VelTamper, 0.0)` when no scope, and `SetWidgetValue(BTN_Inject_NP_VelTamper, IntToFloat(Mem_NP_VelRangeFade[firstScopeIdx]))` when scoped.
3. Snapshot readback path at `Global Rackspace.gpscript:11413` area: `idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_VelRangeFade"); if idx > -1 then Mem_NP_VelRangeFade[i] = Round(GetParameter(BLK_NoteProcessor[i], idx)) end`
4. Snapshot load branch at `Global Rackspace.gpscript:8184` area: `elsif paramType == <new_id> then Mem_NP_VelRangeFade[i] = intVal`

The `<slot>` for `InjectNPToggle` and the `paramType` id for the snapshot load match the next free values in the existing numbering scheme (to be determined during implementation by scanning the existing usages).

---

## Feature B — Macro Space Renumbering + ControllerInfo Loop Fix

### Renumbering

Current (with holes at top):

```
Looper           34–49
Smart Solo       50–65
Strict Solo      66–81
User Mute        82–97
Velocity Range   98–113
Root/Chord      114–129
Octaver         130–145
Humanizer       146–161
Scale Quantizer 162–177
Auto Sustain    178–193
```

New (user reserve 0–49, system groups 50+):

```
Looper          50–65
Smart Solo      66–81
Strict Solo     82–97
User Mute       98–113
Velocity Range 114–129
Root/Chord     130–145
Octaver        146–161
Humanizer      162–177
Scale Quantizer 178–193
Auto Sustain    194–209
```

`MAX_MACROS` goes from `100` → `256` (headroom for future groups beyond Auto Sustain).

### Code Changes

1. **`Global Rackspace.gpscript:43`** `MAX_MACROS : Integer = 100` → `256`.
2. **`Global Rackspace.gpscript:46–55`** Rewrite all `DEF_*_MacroIdx` arrays with the new offsets.
3. **`Global Rackspace.gpscript:59`** `MacroGroup_Anchors` updated: `[-1, 0, 50, 66, 82, 98, 114, 130, 146, 162, 178, 194]`.
4. **`Global Rackspace.gpscript:2867–2876`** Remove the hardcoded anchor-value lookups (`if MacroGroup_Anchors[g] == 82 then idxLooper = g end`, etc.) and replace with a keyed lookup by group name or a direct anchor-constant table. Current code is a smell — an array indexed by a magic number. Proposed: store a parallel `MacroGroup_Keys : String Array = ["GLOBAL", "HW_SLIDERS", "LOOPER", "SMART_SOLO", ...]` and look up by key, or make the display-index search resilient to anchor reordering.

### Loop Bound Fix (the actual ControllerInfo bug)

`Global Rackspace.gpscript:2886`:

```gpscript
// BEFORE
For s = 0; s < 128; s = s + 1 Do
// AFTER
For s = 0; s < MAX_MACROS; s = s + 1 Do
```

With `MAX_MACROS = 256`, all groups through Auto Sustain (max index 209) are covered. Scan cost increases ~2× but runs only on map load/display-refresh, not in the hot MIDI path.

### Removal of Legacy Group Keyword Parsing

The 10 channel-indexed group-role keywords are **removed entirely from `ControllerMaps.txt` section parsing**. Their runtime arrays (`LOOPER_CH_MacroIdx[16]`, `SOLO_SMART_MacroIdx[16]`, `SOLO_STRICT_MacroIdx[16]`, `USER_MUTE_MacroIdx[16]`, `VELRANGE_MacroIdx[16]`, `ROOT_MacroIdx[16]`, `OCTAVER_MacroIdx[16]`, `HUMANIZE_MacroIdx[16]`, `QUANTIZE_MacroIdx[16]`, `SUSTAIN_MacroIdx[16]`) and their CC counterparts remain as runtime data structures — but they are now populated **once** at map-reset time from the `DEF_*_MacroIdx` constants and never again mutated by a map-section load.

**Concretely:**

- **Init (map-reset) path unchanged** at `Global Rackspace.gpscript:5720–5729`:
  ```gpscript
  LOOPER_CH_MacroIdx[k] = DEF_LOOPER_CH_MacroIdx[k]; LOOPER_CH_CCIdx[k] = -1
  ...
  ```
  This is the single source of truth for the group-role → macro-slot mapping for the entire session.

- **Parser `elsif` branches deleted** at `Global Rackspace.gpscript:5825–5875`. All 10 blocks (starting with `elsif IndexOfSubstring(valuePart, "LOOPER_CH", false) == 0` through `SUSTAIN_CH`) are removed. If a section line happens to contain one of these keywords, it falls into the `else` branch (normal link parser), which will not recognize the format and will silently discard it. A `Trace` in `DebugMode` can optionally be added to flag these stray lines during cleanup.

- **Save code deleted** at `Global Rackspace.gpscript:3622–3660`. The section of the `SaveControllerMap()` helper that writes `Macro<N> = LOOPER_CH<ch>` etc. lines is removed. The saved map file will no longer emit these keywords. Save path still writes the single-role keywords (`CROSSFADER`, etc.) and normal parameter links exactly as before.

- **Dispatch code unchanged** at `Global Rackspace.gpscript:9571–9581`. The `For i = 0; i < 16; i = i + 1 Do` loop that matches `matchedMacro == LOOPER_CH_MacroIdx[i]` etc. continues to work exactly as today — the only difference is that `LOOPER_CH_MacroIdx[i]` now always equals `DEF_LOOPER_CH_MacroIdx[i]`.

- **Display code unchanged** at `Global Rackspace.gpscript:2897–2930`. The grouped-display scan loop still finds the group macros via the same forward-index match. The rendered entries remain correct because the runtime arrays still hold valid (default) values.

**Consequence the user loses:** The ability to remap group-role → macro-slot assignments per `[Map:<name>]` section. A Looper channel 1 trigger is always at `DEF_LOOPER_CH_MacroIdx[0]` (post-renumbering: macro slot 50) for every section. Confirmed acceptable — the project is pre-production and this capability has not been used.

**Consequence the user keeps:** Per-section binding of individual hardware sources to single-role keywords (`CROSSFADER`, `SCRUBBER`, `SYSTEM_TOGGLE`, `VST_SCOPE`, `VST_PREV`, `VST_NEXT`, `VST_BROWSE`, `SYSMODE_CYCLE`, `SYSMODE_SELECT`, `VST_SCOPE_PREV`, `VST_SCOPE_NEXT`, `REC_SONGPART`). These remain parseable, and the per-section override of which macro slot or CC number triggers each of these is unchanged. That's the whole point of having song-specific sections: different hardware sources for the same global function per song.

### Migration of Existing `ControllerMaps.txt`

**Manual cleanup required.** The project uses a single `ControllerMaps.txt` file containing multiple `[Map:Name]` sections (one per song/setup). Cleanup actions:

1. **Remove all legacy group-keyword lines from every section.** Every `[Map:*]` block must be stripped of any `Macro<N> = LOOPER_CH<ch>`, `SOLO_SMART_CH<ch>`, `SOLO_STRICT_CH<ch>`, `USER_MUTE_CH<ch>`, `VELRANGE_CH<ch>`, `ROOT_CH<ch>`, `OCTAVER_CH<ch>`, `HUMANIZE_CH<ch>`, `QUANTIZE_CH<ch>`, or `SUSTAIN_CH<ch>` lines. After cleanup, these roles work purely from the Init-time defaults.
2. **Normal parameter links are unaffected.** Any `Macro<N> = VST<k>_GRS:<param>` or `Macro<N> = Ch<c>:CC<n>:<label>` lines remain valid, including multi-assigned entries with `|` separators.
3. **Single-role keyword lines are unaffected.** `Macro<N> = CROSSFADER`, `CC<n> = SYSTEM_TOGGLE`, etc. continue to parse and bind normally per section.

No auto-migrator; the dev is in pre-production and cleans the single file manually.

---

## Feature C — System Action Framework

### Core Principle: Roles, Not Slots

System actions are **roles**, not reserved macro indices. A role exists in an enum; binding it to a hardware input is done by the user assigning it to any of their 50 user macro slots in `ControllerMaps.txt`. Unassigned = not triggerable via hardware. Joystick trigger paths (`ProcessSystemNavigation`) bypass the binding and call the dispatcher directly.

### Registry (SECTION 2: CORE CONSTANTS)

Added directly after `MacroGroup_Anchors` in `Global Rackspace.gpscript`:

```gpscript
// --- SYSTEM ACTIONS (Virtual Role Dispatch) ---
// Central registry: add new system actions here, then add a case to FireSystemAction().
// These are ROLES, not reserved macro slots. They live in the user's 0-49 macro space
// and are assigned via ControllerMaps.txt (e.g. "Macro5 = SYSACT_VST_SCOPE_UP").
// Excluded from Timeline Record/Playback by the Isolation Rule (see below).

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

// RAM: reverse lookup table — index is the macro slot / CC number, value is the
// SysAction index (or -1 if unbound). Using a reverse lookup (not a forward "one
// slot per action" map) preserves the existing channel-injection pattern of the
// codebase, allows natural redundancy (multiple macros can bind to the same role),
// and makes all lookups O(1).
SysAction_ByMacro : Integer Array  // sized MAX_MACROS, all -1 at init
SysAction_ByCC    : Integer Array  // sized 128, all -1 at init
```

Initialization (placed in the script's `Initialization` block or in map-reset):

```gpscript
var i : Integer
For i = 0; i < MAX_MACROS; i = i + 1 Do SysAction_ByMacro <-- -1 End
For i = 0; i < 128; i = i + 1 Do SysAction_ByCC <-- -1 End
```

Total: **20 roles.** Adding a new one in the future requires only (a) a new entry in both name/label arrays and (b) a new case in `FireSystemAction()`. The reverse-lookup tables don't need resizing because they are sized by MAX_MACROS / 128, not by the action count. The parser and display logic automatically pick up the new entry.

### FireSystemAction() Dispatcher

New function, placed near `ProcessSystemNavigation()` in `Global Rackspace.gpscript`:

```gpscript
Function FireSystemAction(actionIdx : Integer)
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
End
```

`RestoreInitialControllerMap()` is a small helper extracted from the existing `GlobalSystemMode == 2 … Y_AXIS == 1` branch to avoid duplicating the `LoadControllerMap(ExpectedMapName)` + OSC feedback code.

**Note:** `CycleStripTheme(+1)` does not exist in the current codebase — `CycleStripTheme()` only takes `-1`. Implementation adds the `+1` direction, wrapping in the opposite direction through the same list.

### ProcessSystemNavigation Refactoring

Each direct function call is replaced with `FireSystemAction(<idx>)`, using a small helper that looks up the index from the name:

```gpscript
Function SysActIdx(name : String) Returns Integer
   var i, res : Integer
   res = -1
   For i = 0; i < Size(SysAction_Names); i = i + 1 Do
      if SysAction_Names[i] == name then res = i end
   End
   result = res
End
```

Example refactoring of the VOICE SELECTOR branch at `:9972`:

```gpscript
// BEFORE
if GlobalSystemMode == 0 then
   if actionType == "Y_AXIS" then
      ChangeVstScope(dir, -1)
      ApplyVstFocusBypass()
   elsif actionType == "X_AXIS" then
      TriggerVstPresetChange(dir)
   ...
// AFTER
if GlobalSystemMode == 0 then
   if actionType == "Y_AXIS" then
      if dir > 0 then FireSystemAction(SysActIdx("VST_SCOPE_UP"))
      else FireSystemAction(SysActIdx("VST_SCOPE_DOWN")) end
   elsif actionType == "X_AXIS" then
      if dir > 0 then FireSystemAction(SysActIdx("VST_PRESET_UP"))
      else FireSystemAction(SysActIdx("VST_PRESET_DOWN")) end
   ...
```

The same pattern applies to modes 1–4. Timeline mode's meta-controls (`StartTimelineRecording`, `CommitTimelineRecording`, `DiscardTimelineRecording`, `TimelineSubMode` toggle, `TimelineRecState` cycling) are **not** virtualized — they are the recording controls themselves and must stay direct.

For performance, `SysActIdx()` lookups in `ProcessSystemNavigation` can be cached at startup into integer constants if desired, but with only 20 entries and one call per joystick edge, straight-line search is fine.

### Hardware Trigger Path (ParameterValueChanged Handler)

When a hardware button bound via a `[Map:*]` section fires its macro, the existing `On GlobalRackspaceParameterValueChanged` handler (`Global Rackspace.gpscript:13201` area) checks the reverse-lookup table and dispatches if bound:

```gpscript
// Inside the existing ParameterValueChanged handler, before other macro processing.
// Reverse-lookup is O(1) — no iteration needed.
if newVal > 0.5 and paramIdx >= 0 and paramIdx < MAX_MACROS then
   if SysAction_ByMacro[paramIdx] > -1 then
      FireSystemAction(SysAction_ByMacro[paramIdx])
   end
end
```

Analogous dispatch for CC-side bindings happens in the MIDI CC event handler (wherever the existing single-role CC dispatch lives — e.g. near `CF_CCIdx` / `SCRUB_CCIdx` checks), extended with the same one-line lookup against `SysAction_ByCC[ccNum]`.

This is the bridge from hardware → role → dispatcher. Joystick path reaches `FireSystemAction` via `ProcessSystemNavigation`. Hardware path reaches it via the macro handler (or the CC handler). Both converge in one place.

### Parser Extension (Map Load)

Inside the existing `LoadControllerMap()` logic in `Global Rackspace.gpscript:5824` area, insert a SYSACT branch **in the position formerly occupied by the deleted group-keyword branches** (which have been removed per Feature B). The branch sets the reverse-lookup table:

```gpscript
// --- SYSTEM ACTION (Isolation Rule: exclusive valuePart only) ---
elsif IndexOfSubstring(valuePart, "SYSACT_", false) == 0 then
   // Bind only if this is the ONLY entry on the line (no '|' separator).
   // Multi-assigned lines (e.g. "SYSACT_FOO | VST1:0") silently drop the SYSACT part
   // and fall through to the normal link parser for the remaining entries.
   if IndexOfSubstring(valuePart, "|", false) == -1 then
      var actionName : String = TrimString(ReplaceString(valuePart, "SYSACT_", "", false))
      var actIdx : Integer = -1
      var a : Integer
      For a = 0; a < Size(SysAction_Names); a = a + 1 Do
         if SysAction_Names[a] == actionName then actIdx = a end
      End
      if actIdx > -1 then
         // Reverse-lookup write: multiple macro slots may bind the same action.
         // Each slot has exactly one action due to the Isolation Rule, so this
         // is a simple direct assignment with no duplicate detection needed.
         if isSrcCC then SysAction_ByCC[sliderIdx] = actIdx
         else SysAction_ByMacro[sliderIdx] = actIdx end
      elsif DebugMode then
         Trace("SYSACT: Unknown action name '" + actionName + "'")
      end
   elsif DebugMode then
      Trace("SYSACT: Multi-assigned valuePart - SYSACT role ignored on slot " + sliderIdx)
   end
```

Map reset at `:5724` area resets `SysAction_ByMacro[]` and `SysAction_ByCC[]` to all `-1` before re-parsing a section (same pattern as the group-role arrays' default-restore).

### Display Integration (LBL_ControllerInfo)

`MacroGroup_Names` gets a new entry `"System Actions"` appended at the end, and `MacroGroup_Anchors` gets a sentinel value. Since system actions don't reserve macro indices, they don't fit the existing anchor-based Grp_Min/Grp_Max pattern; they need a separate rendering branch.

Approach: after the existing grouped-entries loop in `UpdateControllerInfoDisplay()` at `:3016`, add a dedicated system-actions block. Because the lookup is reversed (macro slot → action), the display walks all macro slots grouped by action index:

```gpscript
// --- SYSTEM ACTIONS DISPLAY ---
// Walk the reverse-lookup tables and render bindings grouped by action.
// Multiple macro slots or CC numbers can bind the same action (redundancy).
var sysActHas : Boolean = false
var a, m, c : Integer
For m = 0; m < MAX_MACROS; m = m + 1 Do
   if SysAction_ByMacro[m] > -1 then sysActHas = true end
End
if not sysActHas then
   For c = 0; c < 128; c = c + 1 Do
      if SysAction_ByCC[c] > -1 then sysActHas = true end
   End
end

if sysActHas then
   CtrlInfo_Lines <-- ""
   CtrlInfo_Lines <-- ">> System Actions (Virtual Roles) <<"
   For a = 0; a < Size(SysAction_Names); a = a + 1 Do
      // All macro slots bound to this action
      For m = 0; m < MAX_MACROS; m = m + 1 Do
         if SysAction_ByMacro[m] == a then
            CtrlInfo_Lines <-- "  Macro " + (m + 1) + GetAssignedHWString(m) + ": " + SysAction_Labels[a]
         end
      End
      // All CC numbers bound to this action
      For c = 0; c < 128; c = c + 1 Do
         if SysAction_ByCC[c] == a then
            CtrlInfo_Lines <-- "  " + GetStandardCCName(c) + " [CC" + c + "]: " + SysAction_Labels[a]
         end
      End
   End
end
```

Additionally, the main scan loop (the one processing indices 0..MAX_MACROS) needs to skip macros that are bound to system actions — otherwise a system-action-bound macro would show up twice (once as a raw "Macro N:" entry, once inside the System Actions block). Add an early-continue check inside the scan loop:

```gpscript
// Inside For s = 0; s < MAX_MACROS; s = s + 1 Do ...
// ... after the isGroupedDisp check, before the CROSSFADER etc branches:
var isSysAction : Boolean = false
if not isCC and s >= 0 and s < MAX_MACROS then
   if SysAction_ByMacro[s] > -1 then isSysAction = true end
elsif isCC and s >= 0 and s < 128 then
   if SysAction_ByCC[s] > -1 then isSysAction = true end
end
if isSysAction then
   // intentionally empty - handled in the System Actions block below
elsif isGroupedDisp then
   ...
```

---

## The SYSACT_* Isolation Rule

Scoped to the new `SYSACT_*` keyword family only. Does not touch legacy keywords (they are either removed — group roles — or unchanged — single-role keywords).

### The Rule

> A `SYSACT_*` keyword binds to a macro/CC slot **only if it is the single entry on that slot's valuePart**. If the valuePart contains a `|` separator (multi-assignment), the `SYSACT_*` entry is silently dropped; the remaining entries (VST links, direct CC routings) are parsed normally by the fall-through link parser.

### Why This Rule Makes Everything Else Simple

- **Parser:** Only a `|`-free line reaches the SYSACT binding code. No conditional fallbacks, no backtracking.
- **Record filter:** `IsSystemActionMacro(paramIdx)` is an O(1) lookup against `SysAction_ByMacro[paramIdx]`. Because multi-assigned slots never have their `SysAction_ByMacro` entry set, the filter is exact — a macro is either exclusively a system role (skip recording) or it isn't (record normally).
- **Playback:** Multi-assigned macros record as plain `"Macro"` events and replay through the existing `SetParameter(ExternalArranger, eventVal, 1.0)` path. Exclusively-bound system-action macros never enter the event stream in the first place, so there's nothing to exclude at playback time.
- **User mental model:** "If I want a slot to be a pure system action, I give it only that role. If I want it to fire normal links AND have them recorded/replayed, I give it those links — and the system role is suppressed on that slot." One rule covers all cases.

### Redundant Bindings (Same Role, Multiple Slots)

**Naturally supported by the reverse-lookup design.** If the user writes:

```
Macro3  = SYSACT_LOOPER_REC
Macro88 = SYSACT_LOOPER_REC
```

…both `SysAction_ByMacro[2]` and `SysAction_ByMacro[87]` are set to the `LOOPER_REC` action index. Pressing either macro fires `FireSystemAction(LOOPER_REC)`. This mirrors the channel-injection pattern used elsewhere in the codebase — the data structure is designed around the binding direction (slot → role), not the inverse. There is no first-wins/last-wins conflict because each slot has at most one role.

### Legacy Group Keywords Not Parsed

The channel-indexed group-role keywords (`LOOPER_CH*`, `SOLO_SMART_CH*`, `SOLO_STRICT_CH*`, `USER_MUTE_CH*`, `VELRANGE_CH*`, `ROOT_CH*`, `OCTAVER_CH*`, `HUMANIZE_CH*`, `QUANTIZE_CH*`, `SUSTAIN_CH*`) are **no longer recognized by the parser** — see Feature B's "Removal of Legacy Group Keyword Parsing" section. Their runtime arrays hold Init-time defaults permanently.

### Legacy Single-Role Keywords Unchanged

`CROSSFADER`, `SCRUBBER`, `SYSTEM_TOGGLE`, `VST_SCOPE`, `VST_PREV`, `VST_NEXT`, `VST_BROWSE`, `SYSMODE_CYCLE`, `SYSMODE_SELECT`, `VST_SCOPE_PREV`, `VST_SCOPE_NEXT`, and `REC_SONGPART` retain their **current** parser behavior: one Macro slot + one CC slot per role per section, forward-indexed, last-wins if the same role is assigned twice on the same hardware side within a section. This is existing behavior and not touched by this spec.

---

## Timeline Recording Integration

Single change in `Global Rackspace.gpscript:13201` area:

```gpscript
// BEFORE
if (RecordMode > 0 or TimelineRecActive) and IsPerformanceActive then
   if newVal == 1.0 then
      RecordTimelineEvent("Macro", paramIdx)
   end
end

// AFTER
if (RecordMode > 0 or TimelineRecActive) and IsPerformanceActive then
   if newVal == 1.0 and not IsSystemActionMacro(paramIdx) then
      RecordTimelineEvent("Macro", paramIdx)
   end
end
```

And the helper, placed near the other timeline helpers. Thanks to the reverse-lookup design, this is a straight O(1) array access:

```gpscript
Function IsSystemActionMacro(paramIdx : Integer) Returns Boolean
   var res : Boolean = false
   if paramIdx >= 0 and paramIdx < MAX_MACROS then
      res = SysAction_ByMacro[paramIdx] > -1
   end
   result = res
End
```

Playback (`FireTimelineEvent()` in `:7754`) needs **no changes** — system-action macros never enter the recorded event stream in the first place.

---

## File Locations & Impact Summary

### `Note Prozessor.gpscript`

| Line area | Change |
|---|---|
| Var block near `p_OctRangeFade` (~60) | Add `p_VelRangeFade : Parameter 0 .. 1 = 0` |
| Var block helpers (~85) | Add `VelTamperPadPct : Double = 0.10` with comment |
| Factory reset block (~162) | Add `p_VelRangeFade = 0` |
| New function after `GetOctRangeVelocity` (~285) | Add `GetVelRangeVelocity()` |
| Master event handler (~613) | Replace hard-gate vel check with `GetVelRangeVelocity()` call |

Total: ~35 new LOC, 3 modified LOC.

### `Global Rackspace.gpscript`

| Line area | Change |
|---|---|
| `:43` | `MAX_MACROS : Integer = 256` |
| `:46–55` | Renumber all `DEF_*_MacroIdx` arrays (start at 50) |
| `:59` | Update `MacroGroup_Anchors` |
| After `MacroGroup_Anchors` | Insert SysAction registry (`SysAction_Names`, `SysAction_Labels`, reverse-lookup `SysAction_ByMacro[MAX_MACROS]`, `SysAction_ByCC[128]`) |
| Widget declaration block (~235) | Add `BTN_Inject_NP_VelTamper : Widget` |
| Mem block (~426) | Add `Mem_NP_VelRangeFade : Integer Array = [0,...,0]` |
| `:1642` area | Reset `p_VelRangeFade` and `Mem_NP_VelRangeFade` in channel-strip factory reset |
| `:2140–2191` area | Add `SetWidgetValue(BTN_Inject_NP_VelTamper, ...)` in default / scoped sync |
| `:2867–2876` | Refactor hardcoded anchor-value lookups |
| `:2886` | Loop bound `s < 128` → `s < MAX_MACROS` |
| `:3016` area | Add System Actions display block (reverse-lookup walk) after existing grouped-entries loop |
| Main scan loop inside `:2882–3013` | Add `isSysAction` early-skip check against `SysAction_ByMacro` / `SysAction_ByCC` |
| `:3622–3660` area | **DELETE** all save-code lines that emit legacy group-role keywords (`LOOPER_CH<ch>`, `SOLO_SMART_CH<ch>`, …). The single-role keyword and normal-link save paths remain untouched. |
| `:5724` area (map reset) | Reset `SysAction_ByMacro[]` (MAX_MACROS entries) and `SysAction_ByCC[]` (128 entries) to -1. Leave the existing `LOOPER_CH_MacroIdx` / `SOLO_SMART_MacroIdx` / etc. default-restore lines as they are — those are the new permanent source of truth. |
| `:5825–5875` area (map parser) | **DELETE** all 10 `elsif IndexOfSubstring(valuePart, "LOOPER_CH", ...)` through `SUSTAIN_CH` branches. Replace with a single SYSACT_ branch with the Isolation Rule check. |
| `:8184` area (snapshot load) | Add `paramType` branch for `Mem_NP_VelRangeFade` |
| `:9969` `ProcessSystemNavigation` | Refactor each direct call to `FireSystemAction(SysActIdx("..."))` |
| New function near `ProcessSystemNavigation` | `Function FireSystemAction(actionIdx : Integer)`, `Function SysActIdx(name : String) Returns Integer`, `Function RestoreInitialControllerMap()` |
| `:11413` area (snapshot readback) | Add `Mem_NP_VelRangeFade[i]` readback |
| `:12636` area | Add `On WidgetValueChanged from BTN_Inject_NP_VelTamper` callback |
| `:13201` area (Timeline record) | Add `not IsSystemActionMacro(paramIdx)` guard + `IsSystemActionMacro()` helper |
| `:13201` area (macro handler, hardware trigger) | Insert SYSACT lookup + `FireSystemAction()` dispatch before existing macro processing |

Total: ~200 LOC touched, mostly refactoring existing code plus the new framework.

---

## Testing Notes

### Feature A (Vel Tamper)

1. Set a narrow range (`p_MinVel=40`, `p_MaxVel=80`, span=40, pad=4).
2. Activate `BTN_Inject_NP_VelTamper`.
3. Play notes at velocities 39, 40, 41, 43, 44, 79, 80, 81. Expect: 39 and 81 → silent (hard gate). 40 → vel ~1/5·40 = 8. 44 → full 44. 80 → vel ~1/5·80 = 16.
4. Deactivate tamper, confirm hard-gate behavior returns (40 plays at 40, 81 silent).
5. Test span=19 (below threshold): tamper toggle has no effect. Span=20: pad=2, ramp active at edges.

### Feature B (Renumbering + Loop Fix + Legacy Group Removal)

1. Fresh startup, load a `[Map:*]` section. Observe `LBL_ControllerInfo` lists all 10 group entries (Looper through Auto Sustain) at their new default positions (Looper 51–66, …, Auto Sustain 195–210 in 1-based display).
2. Assign a normal VST link to Macro 5 via a section. Confirm it appears at the correct position in the list.
3. Verify `ScrollToCurrentCtrlScope` still jumps correctly when selecting different edit scopes.
4. Write a legacy-format line (`Macro80 = LOOPER_CH1`) into a test section and load it. Expect: line is silently dropped (or logged in DebugMode); the runtime `LOOPER_CH_MacroIdx[0]` stays at its Init-time default (macro slot 50). The Looper continues to work via the default slot.
5. Save a map section and confirm the output file contains **no** `LOOPER_CH*`, `SOLO_SMART_CH*`, etc. lines. Normal links and single-role keywords are written as before.
6. Legacy group-role dispatch smoke-test: press a hardware button bound (via the HardwareMap file) to macro 50. Looper channel 1 should fire. Same for Smart Solo at slot 66, etc.

### Feature C (System Action Framework)

1. `Macro5 = SYSACT_VST_SCOPE_UP` in a test section. Bind a hardware button to Macro 5 via the HardwareMap file. Load the section, press button → VST scope advances. Confirm the entry appears in LBL_ControllerInfo under "System Actions".
2. `Macro6 = SYSACT_VST_SCOPE_UP | VST1:0` (multi-assignment). Load the section. Expected outcome: `SysAction_ByMacro[5]` stays `-1` (Isolation Rule dropped the SYSACT part), `VST1:0` link active. Press Macro 6 → only VST1:0 is affected; VST scope does NOT change. DebugMode trace: "SYSACT: Multi-assigned valuePart - SYSACT role ignored on slot 5".
3. Record a timeline while pressing both Macro 5 and Macro 6. Stop recording. Inspect `Snap_TL_*` arrays: Macro 5 must NOT appear. Macro 6 MUST appear.
4. Play back the timeline. Macro 6's event fires normally (via `SetParameter`). VST scope is NOT touched during playback (no SYSACT event in the stream).
5. Joystick SYS-MODE 0 Y_AXIS+ → VST scope advances via `ProcessSystemNavigation → FireSystemAction`. Same outcome as the hardware button test. Confirm no double-firing when both joystick and hardware button trigger the same action.
6. **Redundant binding test**: `Macro3 = SYSACT_LOOPER_REC` AND `Macro88 = SYSACT_LOOPER_REC` in the same section. Both `SysAction_ByMacro[2]` and `SysAction_ByMacro[87]` get set to the LOOPER_REC action index. Pressing EITHER macro fires the action. Both appear in LBL_ControllerInfo under "Looper Record".
7. Strip Theme Next/Prev: both directions work via joystick (requires the new `CycleStripTheme(+1)` branch).
8. Ctrl Map Restore: bind a button to `SYSACT_CTRLMAP_RESTORE`, press → initial map restored, OSC feedback shown.
9. CC-side binding: `CC42 = SYSACT_LOOPER_REC`. Send CC42 from hardware → LOOPER_REC fires. Displayed in LBL_ControllerInfo.
10. **Record filter edge case**: Only the `SysAction_ByMacro[paramIdx] > -1` exclusive check determines timeline exclusion. A multi-assigned slot (`SysAction_ByMacro[x] == -1`) records normally, even if the user intended a system action there.

---

## Open Questions (for Implementation Time)

1. The exact numeric slot for `InjectNPToggle` in Feature A's callback (parallel to slot 10 used by OctRangeFade) and the `paramType` id for snapshot load need to be determined by scanning the existing numbering during implementation.
2. Refactoring of the hardcoded anchor-value lookups in `:2867–2876` — the cleanest approach (keyed lookup by group name vs. direct constant table) should be confirmed when touching that code.
3. Widget placement of `BTN_Inject_NP_VelTamper` on the Gig Performer UI panel: visually adjacent to `BTN_Inject_NP_VelRange` (user confirmation during implementation, not a spec concern).
