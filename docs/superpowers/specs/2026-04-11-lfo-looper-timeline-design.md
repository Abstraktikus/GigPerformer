# LFO Engine, Looper Chains, and Smart-Bypass Default — Design

**Date:** 2026-04-11
**Scope:** Three intertwined features that together close out all major
Timeline influences and unblock real song configuration work: the LFO
engine, the Looper Chain projection into the Timeline, and a rework of
`ExecuteSmartBypass()` so that manual scope activation does the right
thing without a loaded Song.ini.

---

## 1. Overview & Goals

After this change the Global Rackspace supports:

1. **BPM-synced LFOs bound to user macros**, driving macro values through
   shaped waveforms, with snap-back on stop, named configurations stored
   in a human-readable `LFOConfig.txt`, and a dedicated inspector panel.
2. **Programmed Looper chains** defined per song, where a manual
   master-trigger anchors a sequence of future loop actions that are
   projected into the Timeline display and broadcast to the OSC-UI as a
   countdown to the next action, without polluting the recorded event
   stream.
3. **A unified default Smart-Bypass rule** that, when no explicit user
   override is configured, activates the NoteProcessor of the current
   scope plus exactly the first VST listed in the `HumanRoutingMap` for
   that channel — and cleanly yields to the `BTN_Inject_Bypass_1..3`
   configuration as soon as the user touches it.

The three features share one guiding principle: **single source of
truth.** No parallel dispatchers, no duplicated event streams, no
special-case branches that drift apart over time.

---

## 2. LFO Engine

### 2.1 Storage — `LFOConfig.txt`

A new configuration file, sibling to `ControllerMaps.txt` and
`HardwareMap.txt`, living next to the `.gig` file. Same text style as
the existing configuration files: named sections, `;` comments, `key =
value` pairs.

```
[LFO:TriSlow]
; Slow triangle sweep, four cycles
Type   = Triangle
Rate   = 1/4
Cycles = 4

[LFO:PadBreath]
Type   = Sinus
Rate   = 1/1
Cycles = Infinite
```

**Fields**

| Key | Allowed values |
|---|---|
| `Type` | `Triangle`, `TriangleUp`, `TriangleDown`, `Sinus`, `Square`, `Random` |
| `Rate` | BPM-synced note value: `8/1`, `4/1`, `2/1`, `1/1`, `1/2`, `1/4`, `1/8`, `1/16`, `1/32` |
| `Cycles` | `-` (no LFO), `Infinite`, or a positive integer (`1`, `2`, `3`, …) |

The parser trims whitespace, is case-insensitive on keys, and ignores
unknown keys with a DebugMode trace (forward-compatible for future
extensions). Unknown `Type` or malformed `Rate` → entry skipped with a
DebugMode trace, the name is not registered.

### 2.2 Binding — a fifth kind in `ControllerMaps.txt`

A new binding kind `LFO:<Name>` joins the existing four (VST link, CC
link, single-role keyword, SYSACT). Unlike SYSACT it **does not follow
the Isolation Rule** — it may coexist with VST and CC links in the same
`|`-separated value, but must always occupy position 0:

```
Macro7 = LFO:TriSlow | VST1_GRS:2:Level (p3) {0.000, 0.464} | VST1_GRS:3:Level (p4) {0.000, 0.182} | Ch13:CC7:Volume Triton
```

**Parser rules** (in `LoadControllerMap`):

1. Split the value on `|`. If the first trimmed token starts with `LFO:`,
   extract the name, look it up in the registry loaded from
   `LFOConfig.txt`, and populate `LFO_ByMacro[slot] = lfoIdx`. Continue
   parsing the remaining tokens normally.
2. If the first token is not an `LFO:` tag, parse all tokens as before.
3. If an `LFO:` tag appears at any position other than 0, or a second
   `LFO:` tag appears on the same line, silently discard the later tag
   (**first wins**, with a DebugMode trace). The already-registered LFO
   (if any) stays.
4. **Whitelist check:** an `LFO:` binding is only accepted when
   - the slot index is in the user zone `1..50`, **and**
   - the remaining `|`-separated tokens contain **at least one** VST
     link or Ch:CC link (i.e. a plain parameter target to modulate),
     **and**
   - no SYSACT / Single-Role keyword is present on the line.

   If any check fails, the `LFO:` tag is silently dropped with a
   DebugMode trace; the non-LFO tokens continue through the normal
   parser path.

**Save path** (`SaveControllerMap` / matching writer): when the
rackspace writes a Controller Map section back to disk, any slot that
has an `LFO_ByMacro` entry gets the `LFO:<Name>` tag re-emitted at
position 0 of the line. This means round-tripping the file preserves
the binding without the user having to hand-edit.

### 2.3 Runtime semantics

**State per slot** (new global arrays, sized `MAX_MACROS = 256`):

| Array | Type | Meaning |
|---|---|---|
| `LFO_ByMacro[slot]` | Integer | Registry index into the parsed `LFOConfig.txt`, or `-1` |
| `LFO_Active[slot]` | Boolean | True while the LFO is sampling and writing to the macro |
| `LFO_StartTime[slot]` | Double | `TimeSinceStartup()` at trigger moment |
| `LFO_PreValue[slot]` | Double | Macro value at trigger moment, for snap-back |
| `LFO_CyclesLeft[slot]` | Integer | Remaining full-period repetitions; `-1` for Infinite |
| `LFO_LastSample[slot]` | Double | Last written sample, exposed for the meter widgets |
| `LFO_Progress[slot]` | Double | Normalised 0..1 progress through total runtime, for the V-meter |

**Trigger:** whenever a macro slot with `LFO_ByMacro[slot] >= 0` receives
a value update (from hardware, OSC, Timeline playback, or the manual
`BTN_LFO_Run` toggle):

1. Cache the current macro value into `LFO_PreValue[slot]`.
2. Set `LFO_StartTime[slot] = TimeSinceStartup()`.
3. Set `LFO_CyclesLeft[slot]` from the LFO config (or `-1` for Infinite).
4. `LFO_Active[slot] = true`.

**Tick loop:** in `On TimerTick` (runs transport-independent, same hook
as the Latch Auto-Release), iterate all slots with `LFO_Active = true`:

```
for each slot with LFO_Active:
    elapsedMS = TimeSinceStartup() - LFO_StartTime[slot]
    cycleLenMS = (60000 / GetBPM()) * beatsPerBar * rateFactor[lfoType]
    phase = (elapsedMS / cycleLenMS) - floor(elapsedMS / cycleLenMS)
    sample = waveform(type, phase)    // 0.0 .. 1.0
    SetMacroValue(slot, sample)       // existing dispatch path
    LFO_LastSample[slot] = sample
    if Cycles >= 0:
        cyclesDone = floor(elapsedMS / cycleLenMS)
        if cyclesDone >= LFO_CyclesLeft_initial:
            stop_lfo(slot)
```

**Stop:** three exit paths, all converge on a single `StopLFO(slot)`
function:

1. `Cycles` exhausted
2. Transport stop (`Playhead.Stop` observed)
3. Manual `BTN_LFO_Run` toggle to OFF

`StopLFO(slot)` writes `LFO_PreValue[slot]` back to the macro (snap-back),
sets `LFO_Active[slot] = false`, clears the H-meter and parks the
V-meter at 0.

**Not recorded:** LFO-generated macro values are **not** recorded as
Macro events in the Timeline. The trigger moment of the macro itself is
the only Timeline event; during playback the same trigger starts the
LFO again, reproducing the motion faithfully without flooding the event
stream.

**First-wins on double assignment:** if two macro lines in the same
`[Map:<Song>]` section both carry `LFO:`, the first to parse wins.
Already covered by the parser rules above.

### 2.4 Widget layout

A new LFO Inspector panel in the Controller Map tab, alongside the
existing macro assignment area.

| Handle | Widget type | Purpose |
|---|---|---|
| `BTN_LFO_Prev`, `LBL_LFO`, `BTN_LFO_Next` | Browser triple (Cycle) | Step through `LFOConfig.txt` entries by name |
| `LBL_LFO_BoundMacro` | Label | Shows the macro slot this config is bound to (e.g. `Bound: Macro 7`), or `—` |
| `BTN_LFO_Type_Prev`, `LBL_LFO_Type`, `BTN_LFO_Type_Next` | Enum triple | Triangle / Sinus / … |
| `BTN_LFO_Rate_Prev`, `LBL_LFO_Rate`, `BTN_LFO_Rate_Next` | Enum triple | 8/1 … 1/32 |
| `BTN_LFO_Cycles_Prev`, `LBL_LFO_Cycles`, `BTN_LFO_Cycles_Next` | Enum triple | `-`, Infinite, 1..n |
| `METER_LFO_H` | Horizontal meter | **Amplitude** — current sample 0.0..1.0. Shows what the LFO is writing right now. |
| `METER_LFO_V` | Vertical meter | **Time progress** — position within the LFO's total runtime. For finite Cycles a linear ramp from 0 to 1; for Infinite a sawtooth that resets every cycle. |
| `BTN_LFO_Run` | Toggle | Manual start/stop, independent of the macro trigger path |
| `BTN_LFO_Save` | Momentary | Writes the current Type/Rate/Cycles back to `LFOConfig.txt` under the name in `LBL_LFO`. New name → new entry. |
| `BTN_LFO_Delete` | Momentary | Deletes the current entry from `LFOConfig.txt` and strips all `LFO:<Name>` tags from `ControllerMaps.txt` in a single sweep. |

**Naming convention matches the existing Prev / Label / Next triples**
used elsewhere in the script (Looper Length, VST Scope, Controller Map
cycle) so the cycle-browser logic from SECTION 17 / 18 can be reused.

### 2.5 Edge cases

- **No `GetBPM()`** (e.g. transport stopped on an empty gig): fallback
  to a fixed 120 BPM for phase calculation, same fallback pattern as
  Latch Auto-Release.
- **Tempo change mid-cycle:** phase is recomputed from `elapsedMS` each
  tick — a tempo jump results in a phase discontinuity, which is
  acceptable for live modulation.
- **Macro deleted mid-run:** if the binding goes away (e.g. Controller
  Map swap), `LFO_Active[slot] = false` immediately, no snap-back call
  to a non-existent target.
- **LFO on a slot that also receives hardware input:** the hardware
  input keeps dispatching and restarts the LFO on each touch (new
  trigger, new snap-back point).

---

## 3. Looper Chain — Timeline Weaving

### 3.1 Chain definition — `Mem_Loop_NextCh`

The Looper already persists `Mem_Loop_Length[ch]` and
`Mem_Loop_Action[ch]` per channel via the Song.ini snapshot. This spec
adds a third parallel array:

```gpscript
Mem_Loop_NextCh : Integer Array  // -1 = chain ends here, 0..15 = successor channel
```

Song.ini gains one new key per looper channel:

```ini
[Snapshot]
Loop_Length_1 = 8
Loop_Action_1 = Overdub
Loop_NextCh_1 = 4
Loop_Length_4 = 8
Loop_Action_4 = Play
Loop_NextCh_4 = -
```

- `-` → no successor, chain ends
- `<k>` (1-based) → after `LoopLengthMS[n]` elapses, trigger channel `k`
  with **its own** `Mem_Loop_Action[k]` value. The action lives at the
  target, never at the anchor.

Chains may share endpoints, fork, or loop back on themselves. A global
`N_MAX_CHAIN_DEPTH = 32` guards against runaway projection when a chain
is cyclic.

### 3.2 Engine — one additional hook

The Looper state machine in SECTION 18 already auto-transitions from
REC → PLAY when `LoopLengthMS[ch]` is reached. The change is a single
additional branch at that exact transition point:

```gpscript
if Mem_Loop_NextCh[ch] >= 0 then
    FireLooperAction(Mem_Loop_NextCh[ch])   // new, reuses existing dispatcher
end
```

`FireLooperAction(targetCh)` is the same entry point that the manual
`SYSACT_LOOPER_REC` click routes through — a single function that
applies `Mem_Loop_Action[targetCh]` to the target channel. Manual clicks
and projected chain transitions flow through exactly one path.

### 3.3 Master vs. Show events — strict separation

The recorded Timeline event stream (`Arr_Rec_Type / Arr_Rec_Val /
Arr_Rec_TimeMS`) gets exactly **one** new event type:

| `Arr_Rec_Type[i]` | `Arr_Rec_Val[i]` | Meaning |
|---|---|---|
| `"LoopMaster"` | `chIdx * 16 + actionCode` | Manual master trigger. `actionCode`: `0` = Rec, `1` = Play, `2` = Overdub, `3` = Clear |

These are the **only** looper-related entries that ever land in
`Arr_Rec_*`. They are recorded in the existing way: when Timeline REC is
active and the user clicks `SYSACT_LOOPER_REC` or `SYSACT_LOOPER_CLEAR`
(or the equivalent hardware macro), `RecordTimelineEvent("LoopMaster",
encodedVal)` is called, with the real ms timestamp relative to
`RecordStartTimeMS`.

**Show-events are never persisted.** They are computed on demand, as a
pure function of the active master event plus the static
`Mem_Loop_NextCh / Mem_Loop_Length / Mem_Loop_Action` arrays:

```
ComputeShowChain(masterEvent) -> list of (offsetMS, chIdx, action):
    chain = []
    cursor = masterEvent.chIdx
    accumMS = 0
    depth = 0
    while cursor >= 0 and depth < N_MAX_CHAIN_DEPTH:
        accumMS += LoopLengthMS[cursor]
        next = Mem_Loop_NextCh[cursor]
        if next < 0: break
        chain.append((accumMS, next, Mem_Loop_Action[next]))
        cursor = next
        depth += 1
    return chain
```

Show events have no write path. They never enter `Arr_Rec_*`, never
participate in Save, and never get replayed — replay is already handled
by the existing Looper engine which will re-fire the chain naturally
when the master event fires during playback.

### 3.4 Projection — when ms↔bars is possible

`Loop_Length_*` is stored in **bars**, the Timeline records in **ms**.
The show computation needs `LoopLengthMS[ch]` which, during live
playback, is derived from `GetBPM()` and the bars value. The
availability of a stable ms↔bars mapping drives when shows can be
displayed at all:

| State | BPM source | `SongDurationBars` | Show display |
|---|---|---|---|
| Empty Mode, no song loaded | none | none | **no show** |
| Live Timeline REC (transport running) | `GetBPM()` (may drift) | unknown | **no show** (projection deferred) |
| Stop-REC finished, song in memory | `RecordedBPM` | computed at Stop | **shown** |
| Playback of a loaded song | `RecordedBPM` from `.ini` | `SongDurationBars` from `.ini` | **shown** |

The gate condition is simple:

```gpscript
Function ShowProjectionsAllowed() Returns Boolean
    result = (RecordedBPM > 0.0) and (SongDurationBars > 0)
End
```

When `ShowProjectionsAllowed()` is `false`, the Show-chain computation
is skipped entirely and all Show UI elements render as blank. As soon
as it becomes `true` (after Stop-REC or after a song loads), the
display refreshes on the next timer tick and the chain appears.

### 3.5 OSC-UI — countdown to next action

Goal: during a live show the musician can glance at the OSC-UI and see
the next upcoming loop action with a live countdown.

In the existing timer-driven UI refresh path (same tick that updates
the prompter position), after the master-event list is walked:

```
activeMaster = last LoopMaster event whose (event.timeMS + chainDurationMS)
               >= currentPlayheadMS
showChain = ComputeShowChain(activeMaster)
nextShow = first showChain entry with (activeMaster.timeMS + entry.offsetMS) > playheadMS
if nextShow exists:
    countdownMS = (activeMaster.timeMS + nextShow.offsetMS) - playheadMS
    countdownBars = countdownMS / msPerBar
    text = "→ " + actionName(nextShow.action) + " Ch" + (nextShow.chIdx+1)
           + " in " + countdownBars + "b (" + (countdownMS/1000) + "s)"
else:
    text = ""
OSC_SendStringSpecific("/UI/LoopNext", text, Local_IP, Local_PORT)
```

When no chain is active, the field is blanked explicitly so stale
countdowns never linger.

### 3.6 Text display in the REC panel

`BuildRecDisplayLines()` is extended: for each `LoopMaster` event in
`Arr_Rec_*`, the computed show entries are inserted as indented lines
directly beneath the master:

```
T+12.400s  REC   Ch1                ← master (real, persisted)
  ↳ +8b    OVR   Ch4  (+20.400s)    ← show (computed)
  ↳ +16b   PLAY  Ch1  (+28.400s)    ← show
T+45.100s  CLR   Ch4                ← master
```

Show lines are visually set apart with the `↳` prefix and, if the
output surface supports it, a dimmer colour. They do not persist to
disk and do not round-trip through the Save/Load path.

### 3.7 Conflict rules — "kein Durcheinander"

1. **Show is read-only.** No code path writes to `Arr_Rec_*` from the
   show computation.
2. **Master wins on divergence.** If a new manual master trigger occurs
   during playback of an existing chain, the bookkeeping recomputes
   `activeMaster` to the newest one — the old countdown disappears, the
   new chain takes over.
3. **Depth cap.** `N_MAX_CHAIN_DEPTH = 32` bounds the walk. Exceeding
   the cap yields a DebugMode trace and truncates the show at 32 steps.
4. **No projection when `ShowProjectionsAllowed()` is false.** During
   Live REC this means the user sees exactly what they recorded, never
   a future projection that could later turn out wrong due to tempo
   drift.

### 3.8 What is not in this feature

- **No recording of chain transitions as separate events.** The chain
  is an engine-side automation; only the master anchor is persisted.
- **No multi-stream chain composition.** A master event belongs to
  exactly one chain; overlapping chains on different channels display
  independently and the countdown always picks the nearest future entry
  across all active chains.
- **No chain editor GUI.** The chain is authored by the existing Looper
  widgets (`BTN_LoopLength`, `BTN_LoopAction`, plus a new
  `BTN_LoopNextCh_Prev/Next` browser triple per channel scope that
  writes `Mem_Loop_NextCh[focusCh]`).

---

## 4. Smart-Bypass — unified default rule

### 4.1 The bug

`Global Rackspace.gpscript:12652`, the `BTN_Ch1_In..BTN_Ch16_In`
handler, writes the RECH matrix cells for the current OutputScope but
never calls `ExecuteSmartBypass()`. When no Song.ini is loaded and
every channel + VST is in the default "everything bypassed" state,
clicking an input button routes signal but leaves every NoteProcessor
and VST asleep. The user's expectation is the opposite: manually
selecting an input for a scope should wake that scope's NoteProcessor
and — by default — exactly the first VST listed in `HumanRoutingMap`
for that channel.

### 4.2 The rule, unified

`ExecuteSmartBypass()` is rewritten so that its behaviour is the same
at every call site. It has two internal branches:

1. **Explicit-Override Branch.** If any VST, for which at least one
   scope channel currently has active RECH input and which is listed in
   the `HumanRoutingMap` for that channel, has a non-zero
   `Mem_ManualVSTBypass[i]` entry, the routine respects the explicit
   configuration: every routed VST is activated unless
   `Mem_ManualVSTBypass[i]` vetoes it (this is today's logic).
2. **Default Branch.** Otherwise, for every channel with an active RECH
   input: activate its NoteProcessor, activate **only the first VST**
   listed in `HumanRoutingMap[ch]`, leave every other routed VST
   bypassed.

Channels with no active RECH input have their NoteProcessor put back to
sleep in both branches, as today.

The branch check scans once per call:

```gpscript
Function HasExplicitBypassOverride() Returns Boolean
    var ch, i, vstIdx, activeIn : Integer
    var routeParts : String Array
    result = false
    For ch = 0; ch < 16; ch = ch + 1 Do
        activeIn = 0
        For i = 0; i < 16; i = i + 1 Do
            if GetParameter(RECH, (i*16) + ch) > 0.5 then activeIn = activeIn + 1 end
        End
        if activeIn > 0 then
            routeParts = SplitString(HumanRoutingMap[ch], ",")
            For i = 0; i < Size(routeParts); i = i + 1 Do
                vstIdx = StringToInt(TrimString(routeParts[i])) - 1
                if vstIdx >= 0 and vstIdx < MAX_VSTS and Mem_ManualVSTBypass[vstIdx] then
                    result = true
                end
            End
        end
    End
End
```

### 4.3 Call sites

All existing `ExecuteSmartBypass()` call sites are preserved:

- `HandleInjectBypassClick` — after the user toggles a `BTN_Inject_Bypass_1..3`
- Song-Load path — after `LoadSongSnapshot` restores the matrix
- Reset / ResetToFactory path — after wiping `Mem_ManualVSTBypass`

**Two new call sites** (the bug fix proper):

- `BTN_Ch1_In..BTN_Ch16_In` handler at ~12652, immediately after
  `SyncInputFeedback()`.
- `BTN_Ch1_Out_*..BTN_Ch16_Out_*` handler at ~12668, immediately after
  `ScrollToCurrentChannel()`.

### 4.4 Walk-through

- User on an empty gig clicks `BTN_Ch5_In` while `BTN_Ch5_Out_*` is
  active. RECH row 5 gets a `1.0`. `ExecuteSmartBypass()` runs, finds
  no `Mem_ManualVSTBypass` on any routed VST, takes the Default Branch,
  wakes `NoteProcessor[4]` and the first VST of `HumanRoutingMap[4]`.
  The user can play immediately.
- Song-Load with a Song.ini that persists explicit bypass flags restores
  those flags into `Mem_ManualVSTBypass` before `ExecuteSmartBypass()`
  runs, so the Explicit-Override Branch takes over.
- Song-Load of a "blank" song (no bypass flags persisted) → Default
  Branch → minimal running state.
- Reset clears `Mem_ManualVSTBypass` → Default Branch on the next tick.

### 4.5 Open question — `BTN_Inject_Bypass_*` button semantics

The current `HandleInjectBypassClick` writes `Mem_ManualVSTBypass[i] =
true` when a button goes ON, meaning a lit button represents "I am
forcing this VST off" (shown in the channel analysis as `[MAN OFF]`).
Under the new Default Branch this creates a UX dead end: if
`HumanRoutingMap[ch] = "5,6"` and the Default Branch wakes only VST 5,
the user has no way to activate VST 6 from the Inject panel — clicking
`BTN_Inject_Bypass_2` would force VST 6 off, which it already is.

Two candidate resolutions:

1. **Flip the button semantic to "VST is active"**. Lit button = VST
   active, dark button = VST bypassed. The Default Branch would paint
   button 1 lit and buttons 2/3 dark on entry. Clicking button 2 would
   set `Mem_ManualVSTBypass` such that the Explicit-Override Branch
   activates both VST 5 and VST 6. This matches the "sofern keiner der
   Button aktiv ist [...] ansonsten gilt die Konfiguration"
   formulation if "aktiv" is read as "user has explicitly touched it"
   rather than literal widget lit/dark state. Visible semantic flip of
   an existing widget — worth being deliberate about.

2. **Make the button tri-state**. States: `default` (dark, follows the
   branch logic), `force active` (lit green), `force bypass` (lit red).
   More expressive but adds a click dimension and needs a colour in the
   widget library that supports three visuals.

3. **Introduce a separate `BTN_Inject_Activate_*` row** next to the
   existing bypass row, so the two intents (activate extra / force
   bypass) live on separate widgets. Low ambiguity, but adds three
   widgets to an already dense panel.

**This needs to be resolved before the Smart-Bypass rewrite is
implemented.** Recommendation: option 1 (semantic flip) — least UI
churn, cleanest mental model, and the "[MAN OFF]" label in the analysis
display can simply be renamed to "[MANUAL]" or removed.

### 4.6 Nested-effect check

### 4.5 Nested-effect check

- The `IsLoadingSnapshot` guard at the top of the input handler already
  prevents the fix from firing during snapshot restoration.
- `IsUpdatingMatrix`, `IsUpdatingBypassUI` shields are unchanged and
  apply equally to the rewritten function.
- Performance: the rewritten routine is still O(16 × 16) matrix scan +
  O(MAX_VSTS) plugin state calls. One extra call per input/output click
  is negligible.

---

## 5. Out of scope (not in this design)

- LFO sample-value recording to the Timeline (explicitly rejected as
  event-stream pollution).
- Chain composition beyond `N_MAX_CHAIN_DEPTH = 32` steps.
- Multi-LFO per macro (first wins; second is dropped at parse time).
- LFO on CC-only bindings if the whitelist later loosens — today LFO
  requires at least one VST or Ch:CC link to modulate.
- A dedicated chain editor dialog; chains are authored from the
  existing Looper widgets plus a new `Mem_Loop_NextCh` browser triple.
- Tempo-drift smoothing for LFO phase (accepted as a phase
  discontinuity).

---

## 6. Build order

Rough sequencing for the implementation plan that will follow from
this spec:

1. **Resolve the `BTN_Inject_Bypass_*` semantic question (4.5).** Must
   happen before step 2 — the rewrite direction depends on it.
2. **Bypass rewrite.** Enables basic usability without a Song.ini and
   unblocks manual testing of everything else.
3. **Looper `Mem_Loop_NextCh` storage + engine hook.** Adds the Song.ini
   field, the engine branch, and the basic round-trip. No UI yet.
4. **Looper Show computation + REC panel display.** Adds the
   `ComputeShowChain` function and the indented text rendering. Still
   no OSC.
5. **Looper OSC-UI countdown.** Wire the countdown into the tick loop
   and the `/UI/LoopNext` OSC path.
6. **LFO parser + `LFOConfig.txt` loader.** Pure data, no runtime.
7. **LFO runtime engine.** Hook into `On TimerTick`, implement
   waveforms, snap-back, meters, stop paths.
8. **LFO inspector widgets.** The Prev/Label/Next triples, Save,
   Delete, Run, the two meters.

Each step is independently testable and each adds a small vertical
slice of functionality.
