# Macros, Controller Maps, Hardware Map, and SYSMODE

This document is the user-facing reference for how macros work in the Global Rackspace, how to bind hardware inputs to them, which roles can be assigned through the Controller Map file, and how the SYSMODE joystick navigation layer fits on top. If you're editing `ControllerMaps.txt` or `HardwareMap.txt` by hand and want to know what the parser will accept, this is where to look.

If you just want to get started: read sections **1**, **2**, and **7**. The rest is reference material for specific questions.

---

## 1. The Mental Model

The Global Rackspace exposes **256 macro slots** (`MAX_MACROS = 256`). Slots are split into two conceptual regions:

| Slot range (1-based) | Region | Who owns it |
|---|---|---|
| **1 – 50** | **User zone** — free for anything | You (via `ControllerMaps.txt`) |
| **51 – 210** | **Group roles** — system-reserved | Hardcoded, not overrideable per map |
| **211 – 256** | **Headroom** for future groups | Reserved |

### Group role layout (slots 51–210)

Each group is a 16-element block — one slot per channel strip.

| Group | Slots (1-based) | Purpose |
|---|---|---|
| Looper Triggers | 51 – 66 | Record / play / overdub per channel |
| Smart Solo | 67 – 82 | Smart solo toggle per channel |
| Strict Solo | 83 – 98 | Strict solo toggle per channel |
| User Mute | 99 – 114 | User mute per channel |
| Velocity Range | 115 – 130 | Velocity range gate toggle per channel |
| Root / Chord | 131 – 146 | Chord-mode toggle per channel |
| Octaver | 147 – 162 | Polyphonic Octave Generator toggle per channel |
| Humanizer | 163 – 178 | Humanizer toggle per channel |
| Scale Quantizer | 179 – 194 | Scale quantizer toggle per channel |
| Auto Sustain | 195 – 210 | Auto-sustain toggle per channel |

**Key rule:** these group slots are wired at startup from the hardcoded `DEF_*_MacroIdx` constants in `Global Rackspace.gpscript` SECTION 2. They are **not overridable per map** — if you need to change where Looper channel 1 lives, you edit the `DEF_LOOPER_CH_MacroIdx` array in the script itself, not the Controller Map file.

### Why two regions

Separating user macros from group macros means you never have to worry about accidentally binding a hardware input to "Looper channel 3" because you wanted Macro 52 for a preset knob. If you stay in the 1–50 range for your own work, the system region is inert from your perspective — it just works.

---

## 2. The Two Configuration Files

Two files live alongside the `.gig` file, in the same folder as the rackspace data:

### `ControllerMaps.txt` — "What does each macro slot do?"

Multiple `[Map:<SongName>]` sections, one per song or setup. Each section maps macro slots to **behaviors**: parameter links, direct CC routings, single-role keywords (like `CROSSFADER`), or SYSACT roles.

Switching between sections is per-song — the active section determines what Macro 5 currently triggers. When you edit a song's Controller Map, you're editing how that song's macros behave.

### `HardwareMap.txt` — "Which physical input is each macro slot?"

A single `[Assignment:Standard]` section listing which MIDI channel + CC (or Note) each macro slot is bound to. This is **global** — not per-song. Your foot pedal on CC64 stays Macro 42 across every song in the set.

This is the HAL (Hardware Abstraction Layer) side. It's managed via the rackspace's Learn mode — you rarely edit it by hand. Format is simple:

```
[Assignment:Standard]
; Controller Bindings (Auto-Generated)
Macro1 = Ch13:CC17
Macro2 = Ch13:CC19 | Ch1:CC20
Macro42 = Ch16:CC64
```

Macros can have multiple hardware sources via `|`. Notes are supported via `Ch<n>:Note<n>` instead of `Ch<n>:CC<n>`.

### The separation matters

- Song A and Song B can have totally different Controller Maps (different behaviors for Macro 5) but **share** the same Hardware Map (Macro 5 is always the same button on your pedalboard).
- If you get a new keyboard with different CC numbers, you edit the Hardware Map **once** and all songs follow.

---

## 3. Controller Map Section Syntax

A Controller Map section looks like this:

```
[Map:MySong]
Macro1 = VST1_GRS:48:Filter Cutoff {0.0, 1.0}
Macro2 = Ch13:CC7:Volume
Macro5 = SYSACT_VST_SCOPE_UP
Macro6 = CROSSFADER
Macro10 = VST1_GRS:0:Level (p1) {0.0, 0.289} | VST2_GRS:0:Level (p1) {0.0, 0.289}
CC11 = CROSSFADER
CC64 = SYSTEM_TOGGLE
```

The parser (in `LoadControllerMap`) accepts four kinds of bindings on the right side of `=`, plus two source forms on the left side.

### Source forms (left of `=`)

- `Macro<N>` — refers to macro slot N (1-based). N must be in `1..MAX_MACROS` (1–256).
- `CC<n>` — refers to raw MIDI CC number n on a dedicated CC lane. Only valid for **single-role keywords** and **SYSACT roles**, not for arbitrary parameter links.

### Binding kinds (right of `=`)

| Kind | Syntax | Multi-`|` allowed | Purpose |
|---|---|---|---|
| **VST plugin parameter** | `VST<k>_GRS:<paramIdx>:<label> {min, max}` | ✓ | Route the macro to a parameter on the k-th VST slot |
| **Direct CC routing** | `Ch<c>:CC<n>:<label> {min, max}` | ✓ | Emit a CC message on channel c, number n |
| **Single-role keyword** | `CROSSFADER`, `SCRUBBER`, `SYSTEM_TOGGLE`, `VST_SCOPE`, `VST_SCOPE_PREV`, `VST_SCOPE_NEXT`, `VST_PREV`, `VST_NEXT`, `VST_BROWSE`, `SYSMODE_CYCLE`, `SYSMODE_SELECT`, `REC_SONGPART` | one Macro source + one CC source per role per section | Bind a fixed global system function |
| **SYSACT role** | `SYSACT_<NAME>` | **no** (Isolation Rule) | Bind a virtual SYSMODE action (see section 5) |

The `{min, max}` scaling suffix is optional; default is `{0.0, 1.0}` (pass-through).

### Multi-assignment on one slot

For VST and CC links, you can combine multiple targets with `|`:

```
Macro4 = VST1_GRS:48:Cutoff | Ch11:CC18:Phaser {0.0, 1.0} | Ch12:CC18:Phaser {0.0, 1.0}
```

When Macro 4 is pressed, all three targets fire in parallel. This is handy for "one knob, two instruments playing in unison" setups.

---

## 4. Single-Role Keywords

These are hardcoded global functions. A Controller Map section can bind **one Macro source + one CC source** per keyword (per section). Multiple Macros to the same keyword in one section is not supported — the last one wins.

| Keyword | What it does |
|---|---|
| `CROSSFADER` | Global audio / expression balance fader |
| `SCRUBBER` | Timeline scrubber + panic transport stop |
| `SYSTEM_TOGGLE` | Press-and-hold gesture that activates System Mode (joystick hijack — used to switch into SYSMODE) |
| `VST_SCOPE` | Direct VST scope select (rotary encoder, absolute) |
| `VST_SCOPE_PREV` / `VST_SCOPE_NEXT` | Step to previous/next VST scope (button pair) |
| `VST_PREV` / `VST_NEXT` | Step to previous/next VST preset on the current scope |
| `VST_BROWSE` | Preset browse encoder |
| `SYSMODE_CYCLE` | Cycle through the 5 SYSMODE modes |
| `SYSMODE_SELECT` | Absolute SYSMODE selection (0–4) |
| `REC_SONGPART` | Record: mark next songpart (timeline marker) |

### Per-song rebinding

The whole reason single-role keywords exist is that different songs use different hardware inputs. Song A's foot pedal is CC11; Song B's is CC64. With a single-role keyword you can write:

```
[Map:SongA]
CC11 = CROSSFADER

[Map:SongB]
CC64 = CROSSFADER
```

…and the crossfader binding follows the active song.

---

## 5. SYSACT Roles (the System Action Framework)

SYSACT roles are a more flexible system than single-role keywords. There are **20 virtual actions** — things like "advance VST scope," "toggle strip macro," "record songpart" — that can be bound to any user-zone macro slot or CC number, and they follow a strict **Isolation Rule**.

### Why not just single-role keywords?

Single-role keywords are limited: one binding per hardware type, fixed set, no per-channel parameterization. SYSACT solves this by giving every virtual SYSMODE action its own named role that can be dispatched from:

1. **The joystick path** — via `ProcessSystemNavigation` in `Global Rackspace.gpscript`
2. **A bound hardware button** — via the macro ParameterValueChanged handler or the CC handler (reverse-lookup into `SysAction_ByMacro` / `SysAction_ByCC`)

Both paths converge on the same `FireSystemAction(actionIdx)` dispatcher. This means any joystick action can also be triggered by a hardware pad or foot switch, with zero code changes — just a binding line in `ControllerMaps.txt`.

### The 20 roles

| # | Name | Human label | What it does |
|---|---|---|---|
| 0 | `SYSACT_VST_SCOPE_UP` | VST Scope [Next] | Advance the current VST scope by one, apply focus bypass |
| 1 | `SYSACT_VST_SCOPE_DOWN` | VST Scope [Prev] | Step back one VST scope, apply focus bypass |
| 2 | `SYSACT_VST_PRESET_UP` | VST Preset [Next] | Load next preset on current VST scope |
| 3 | `SYSACT_VST_PRESET_DOWN` | VST Preset [Prev] | Load previous preset on current VST scope |
| 4 | `SYSACT_LOOPER_CH_UP` | Looper Channel [Next] | Cycle looper channel scope forward |
| 5 | `SYSACT_LOOPER_CH_DOWN` | Looper Channel [Prev] | Cycle looper channel scope backward |
| 6 | `SYSACT_LOOPER_REC` | Looper Record | Click the Loop Record widget (rec/play/overdub flow) |
| 7 | `SYSACT_LOOPER_CLEAR` | Looper Clear | Click the Loop Clear widget for the current channel |
| 8 | `SYSACT_CTRLMAP_PREV` | Ctrl Map [Prev Active] | Preview previous active Controller Map |
| 9 | `SYSACT_CTRLMAP_NEXT` | Ctrl Map [Next Active] | Preview next active Controller Map |
| 10 | `SYSACT_CTRLMAP_RESTORE` | Ctrl Map Restore Initial | Reload the song's originally-assigned Controller Map |
| 11 | `SYSACT_CTRLMAP_CYCLE` | Ctrl Map Cycle | Cycle through all Controller Maps (regardless of active state) |
| 12 | `SYSACT_STRIP_CH_UP` | Strip Channel [Next] | Cycle the Strip Control channel scope forward |
| 13 | `SYSACT_STRIP_CH_DOWN` | Strip Channel [Prev] | Cycle the Strip Control channel scope backward |
| 14 | `SYSACT_STRIP_THEME_PREV` | Strip Theme [Prev] | Cycle Strip Control theme backward (Octaver → Humanizer → …) |
| 15 | `SYSACT_STRIP_THEME_NEXT` | Strip Theme [Next] | Cycle Strip Control theme forward |
| 16 | `SYSACT_STRIP_MACRO_TOGGLE` | Strip Macro Toggle | Toggle the macro at the current Strip Control grid position |
| 17 | `SYSACT_TL_PARTJUMP_NEXT` | Timeline Part Jump [Next] | Preview next song part (Timeline mode, PLAY sub-mode) |
| 18 | `SYSACT_TL_PARTJUMP_PREV` | Timeline Part Jump [Prev] | Preview previous song part |
| 19 | `SYSACT_TL_REC_SONGPART` | Timeline Rec Songpart | Mark the current position as a song part during recording |

The registry lives in `Global Rackspace.gpscript` SECTION 2 (`SysAction_Names` / `SysAction_Labels`). Adding a new action is a 3-step change: new entry in both arrays, new case in `FireSystemAction()`, done — parser and display pick it up automatically.

### Binding SYSACT roles

```
[Map:MySong]
Macro5 = SYSACT_VST_SCOPE_UP
Macro6 = SYSACT_VST_SCOPE_DOWN
CC42 = SYSACT_LOOPER_REC
```

After loading, pressing the hardware button assigned to Macro 5 fires `ChangeVstScope(1, -1); ApplyVstFocusBypass()` — exactly the same function the joystick Y+ in SYSMODE 0 calls.

### Multi-binding is natural

Multiple macro slots can bind the **same** SYSACT role — the reverse-lookup table `SysAction_ByMacro[slot]` simply stores the action index at each slot. If you bind both Macro 5 and Macro 88 to `SYSACT_LOOPER_REC`, either macro press triggers the looper record. This matches the channel-injection pattern used elsewhere in the codebase.

---

## 6. The Isolation Rule (cross-cutting)

> A `SYSACT_*` role binds to a macro/CC slot **only when the `valuePart` is a single entry.** If the line contains a `|` separator, the SYSACT_* token is silently dropped; the remaining entries are parsed normally by the VST/CC link parser.

### Why

SYSACT roles are distinct from normal parameter links — they fire an action, not set a value. Allowing them to coexist with VST/CC links on one slot would create ambiguous record/playback semantics and tangle the Timeline filter. The Isolation Rule sidesteps that entirely: a macro slot is either exclusively a SYSACT role, or it isn't a SYSACT role at all.

### Examples

```
Macro5 = SYSACT_VST_SCOPE_UP                          ✓ bound
Macro5 = SYSACT_VST_SCOPE_UP | VST1_GRS:0:Level       ✗ SYSACT dropped, VST1 link active
Macro5 = VST1_GRS:0:Level | SYSACT_VST_SCOPE_UP       ✗ SYSACT dropped, VST1 link active
Macro5 = SYSACT_BOGUS_NAME                            ✗ unknown action, DebugMode trace, slot unbound
```

### Timeline recording consequence

Timeline recording uses the same reverse-lookup to filter out SYSACT-exclusive macros. If a slot is in `SysAction_ByMacro[]`, `IsSystemActionMacro(paramIdx)` returns true and `RecordTimelineEvent("Macro", paramIdx)` is skipped. A multi-assigned slot never enters the reverse-lookup in the first place, so it records as a normal macro event and replays the user's VST/CC link exactly as expected. **No special playback logic needed** — the Isolation Rule does all the work at the parser level.

---

## 7. SYSMODE — The Joystick Navigation Layer

SYSMODE is a modal state machine on top of the rackspace. When you hold `SYSTEM_TOGGLE` (or press `SYSMODE_CYCLE`), the hardware joystick's pitch-bend and modulation axes are "hijacked" away from their normal musical use and become a navigation controller. The current mode determines what the joystick does. There are **5 modes**, cycled in order:

| # | Name | Joystick Y axis | Joystick X axis | Button / Encoder |
|---|---|---|---|---|
| 0 | **VOICE SELECTOR** | VST scope ± | VST preset ± | Same as axis |
| 1 | **LOOPER CONTROL** | Channel scope ± | Left=Clear, Right=Rec | Button=Rec |
| 2 | **CONTROLLER MAP** | Up=Restore initial | Prev/Next active map | Button=Cycle all |
| 3 | **STRIP-CONTROL** | Channel scope ± | Left=Theme prev, Right=Macro toggle | Button=Macro toggle |
| 4 | **TIMELINE** | Toggle PLAY/REC | PLAY: Part jump; REC: Rec songpart (right) / Replace-Overdub-Discard cycle (left) | Same as Y |

### Mode 0 — VOICE SELECTOR

Quick VST scope and preset navigation. Y+ advances to the next VST slot (0→1→2→…), Y- goes back. X+ loads the next preset on the currently-focused VST, X- loads the previous. This is the default "browse sounds" mode.

### Mode 1 — LOOPER CONTROL

Per-channel looper management. Y selects which channel scope the looper operates on (1–16). X-left clears the current channel's loop, X-right triggers the Record → Play → Overdub state flow. Button press alone = Record (same as X-right).

### Mode 2 — CONTROLLER MAP

Browse Controller Map sections at runtime. Y+ jumps back to the song's originally-loaded map (useful after you've browsed around and want to reset). X cycles through **active** maps (the ones relevant to the current VST set). Button cycles through **all** maps regardless of active state.

### Mode 3 — STRIP-CONTROL

A 16-channel × 9-theme grid. Y picks the channel (1–16), X-left cycles the theme (Octaver → Humanizer → Scale Quantizer → Auto Sustain → Looper → Smart Solo → Strict Solo → User Mute → Velocity Range → Root/Chord → …). X-right or button press toggles the macro at the current channel+theme grid position.

### Mode 4 — TIMELINE

Song timeline playback and recording.

- **PLAY sub-mode** (default): Y or button toggles to REC. X/encoder jumps through song parts (preview before committing).
- **REC sub-mode**: Y or button commits recording and returns to PLAY. X-right marks the current position as a song part (`REC_SONGPART`). X-left cycles through the three recording policies: **Replace** → **Overdub** → **Discard** (back to Replace).

Timeline meta-controls (the PLAY/REC toggle itself, the recording policy cycle, the discard action) are deliberately **not virtualized through SYSACT** — they are the recording controls, and recording them into the timeline stream would be nonsense.

### How the dispatch works

Joystick events (pitch-bend beyond threshold on one of the hardware device ins) land in `On PitchBendEvent` in the Global Rackspace, which calls `ProcessSystemNavigation(deviceID, actionType, direction)`. That function is a pure router:

```gpscript
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

Every virtualizable branch routes through `FireSystemAction(SysActIdx("<NAME>"))` — the same entry point that a hardware-button-bound SYSACT role uses. Single source of truth, zero code duplication.

---

## 8. Velocity Range Tamper (a related live-forgiveness feature)

Not strictly a macro topic, but part of the same "live-play forgiveness" family as the Latch Auto-Release. The Note Prozessor's **Velocity Range** gates incoming notes to a `[p_MinVel, p_MaxVel]` window — everything outside is silent. Useful for velocity-sensitive instrument layering, but the hard edges are musically unforgiving.

The **Tamper** feature (`BTN_Inject_NP_VelTamper` → `p_VelRangeFade`) softens those edges: within 10% of each side of the range (configurable via `VelTamperPadPct` in the Note Prozessor scriptlet), velocities are linearly scaled down toward zero. The first inaudible velocity is exactly at `p_MinVel - 1` and `p_MaxVel + 1`. Activated per-channel via the Inject panel.

For the full spec, see `docs/superpowers/specs/2026-04-10-vel-tamper-macro-refactor-sysact-design.md`.

---

## 9. Chord Latch Auto-Release

When the Note Prozessor's **Chord Mode** is combined with **Latch Mode** (`BTN_Inject_NP_Hold` → `p_LatchMode`), the detected root note stays held after you release the keys. Historically this was too permanent — the root kept droning even after the song ended.

Now a **beat-scaled auto-release** fires after `LatchTimeoutBeats = 4` beats of complete note-on silence (BPM-aware) or `LatchTimeoutFallbackMs = 4000` milliseconds when `GetBPM()` is unavailable. Both tunables live in `Global Rackspace.gpscript` SECTION 2.

The check runs inside `On TimerTick` (not `On BeatChanged`, because `BeatChanged` doesn't fire when the transport is stopped, which is exactly when the release is needed). `ProcessHardwareNote` stamps the global `Latch_LastNoteOnTime` on every incoming hardware note-on; the timer checks idle-time-since-stamp against the BPM-scaled window and fires `p_LatchRelease = 1` on every channel in Chord+Latch mode when the threshold is crossed.

For the full spec, see `docs/superpowers/specs/2026-04-10-latch-auto-release-design.md`.

---

## 10. Troubleshooting

### "My SYSACT binding doesn't fire."

1. Check the line for a `|` separator — SYSACT roles are dropped from multi-assigned lines per the Isolation Rule.
2. Enable `DebugMode` and look for `SYSACT: Unknown action name '<X>'` (typo in the role name) or `SYSACT: Multi-assigned valuePart - SYSACT role ignored on slot <N>`.
3. Verify the macro slot is actually bound to a hardware input in `HardwareMap.txt`. The Controller Map says "what happens when Macro 5 fires"; the Hardware Map says "which button is Macro 5."

### "Looper button does nothing."

The looper trigger macros live at fixed slots 51–66 (default). Make sure your hardware button is mapped to one of those slots in `HardwareMap.txt`, not to a user-zone slot.

### "Latch auto-release never fires."

1. Is `On TimerTick` running? It should be — it's transport-independent. Check Gig Performer's script console for any errors.
2. Enable `DebugMode` and look for `LATCH: auto-release fired after Nms idle`. If you don't see it, the `Latch_LastNoteOnTime` stamp probably isn't being updated — check that `ProcessHardwareNote` is actually receiving your note-ons (only `DeviceIn_0..3` are wired).
3. Is `Mem_NP_ChordMode[channel]` and `Mem_NP_LatchMode[channel]` both 1? The check in `CheckLatchTimeout` gates on both.
4. If `GetBPM()` returns something weird (e.g., 0 during a song switch), the 4000ms fallback should still fire. If not, something else is wrong.

### "I edited `ControllerMaps.txt` and nothing changed."

Make sure you're editing the right section (the `[Map:<name>]` that's currently active for the loaded song). Gig Performer may also need a rackspace reload to pick up the new file contents.

### "I see a group keyword in my file that doesn't work anymore."

Legacy keywords like `LOOPER_CH1`, `SOLO_SMART_CH3`, `USER_MUTE_CH2`, `VELRANGE_CH1`, etc. were removed from the parser. If they're still in your file, they silently fall into the normal-link branch and get discarded. Group roles are now purely hardcoded at their default slot positions — you can't override them per map. Just delete those lines from your Controller Map sections; the groups still work at their defaults.

### "Single-role keyword appears twice in my map — which wins?"

For single-role keywords (`CROSSFADER`, `SCRUBBER`, etc.), the parser uses last-wins semantics: if you have both `Macro5 = CROSSFADER` and `Macro8 = CROSSFADER` in the same section, only `Macro8` takes effect (the later assignment overwrites). If you need the crossfader on two hardware inputs, use one Macro binding + one CC binding instead:

```
Macro5 = CROSSFADER
CC11 = CROSSFADER
```

Both will work because they populate different slots (`CF_MacroIdx` and `CF_CCIdx`).

---

## Reference — File Locations

| File | Path | Owner | Edited by hand? |
|---|---|---|---|
| Global Rackspace script | `Global Rackspace.gpscript` | You / repo | Usually yes (it's source) |
| Note Prozessor scriptlet | `Note Prozessor.gpscript` | You / repo | Yes (it's source) |
| Controller Maps | `ControllerMaps.txt` (next to gig file) | You | Yes (hand-edit is the intended workflow) |
| Hardware Map | `HardwareMap.txt` (next to gig file) | Auto-generated by Learn mode | Rarely |
| Rackspace settings | `UserSnapshotPath` folder | Gig Performer | No |

## Reference — Key Specs for Deeper Dives

- **Macro space renumbering, SysAction framework, legacy keyword removal:** `docs/superpowers/specs/2026-04-10-vel-tamper-macro-refactor-sysact-design.md`
- **Velocity Range Tamper:** same file (Feature A)
- **Chord Latch Auto-Release:** `docs/superpowers/specs/2026-04-10-latch-auto-release-design.md`
- **Implementation plans** for both: `docs/superpowers/plans/2026-04-10-*.md`
