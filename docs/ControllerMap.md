# ControllerMap Reference

This document covers the `ControllerMaps.txt` syntax: macro slots, hardware source bindings, overlay trigger zones (OTZ), SYSACT roles, SYS-MODE joystick navigation, Smart Solo, VST validation, timeline recording, and runtime behavior. For hardware device definitions, controls, layers, output routing, style triggers, and SysEx song sync, see `docs/DeviceConfig.md`.

Quick start: read sections **1**, **2**, and **3**. The rest is reference material for specific questions.

---

## 1. The Mental Model

The Global Rackspace exposes **256 macro slots** (`MAX_MACROS = 256`). Slots are split into two regions:

| Slot range (1-based) | Region | Who owns it |
|---|---|---|
| **1 -- 95** | **User zone** -- free for layer system bindings | You (via `ControllerMaps.txt`) |
| **96 -- 255** | **System groups** -- 10 groups of 16 channels each | Hardcoded, not overridable per map |

### System group layout (slots 96--255)

Each group is a contiguous 16-element block -- one slot per channel strip (channels 1--16).

| Group | Slots (1-based) | Purpose |
|---|---|---|
| Looper Triggers | 96 -- 111 | Record / play / overdub per channel |
| Smart Solo | 112 -- 127 | Smart solo toggle per channel |
| Strict Solo | 128 -- 143 | Strict solo toggle per channel |
| User Mute | 144 -- 159 | User mute per channel |
| Velocity Range | 160 -- 175 | Velocity range gate toggle per channel |
| Root / Chord | 176 -- 191 | Chord-mode toggle per channel |
| Octaver | 192 -- 207 | Polyphonic Octave Generator toggle per channel |
| Humanizer | 208 -- 223 | Humanizer toggle per channel |
| Scale Quantizer | 224 -- 239 | Scale quantizer toggle per channel |
| Auto Sustain | 240 -- 255 | Auto-sustain toggle per channel |

**Key rule:** These group slots are wired at startup from the hardcoded `DEF_*_MacroIdx` constants in `Global Rackspace.gpscript` SECTION 2. They are **not overridable per map**. To relocate a group slot, edit the constant array in the script itself.

### Why two regions

Separating user macros (1--95) from system macros (96--255) prevents accidental collisions. The user zone holds all layer-multiplied hardware bindings. The system zone is inert from the user's perspective -- it just works.

---

## 2. The Configuration Files

Two files live alongside the `.gig` file. The former `HardwareMap.txt` is eliminated -- hardware sources are now inline in the ControllerMap.

### `ControllerMaps.txt` -- "What does each macro do, and which hardware input drives it?"

Contains a `[Map:Default]` base section and optional `[Map:<SongName>]` override sections. Each section maps macro slots to hardware sources AND behavioral bindings (VST parameters, CC routings, keywords, SYSACT roles, overlay triggers).

`[Map:Default]` is the base configuration. All song maps inherit from it. A song map only needs to declare differences (deltas). Inheritance works per-layer, per-macro: if a song map does not mention a macro, the entire macro definition comes from Default. If a song map overrides only one layer of a macro, the other layers remain inherited.

### `DeviceConfig.txt` -- "What hardware exists and how is it wired?"

Defines physical devices, their controls with labels, layer switch triggers (as `[CONTROL:n]` entries with `Type=LAYER_SWITCH`), layer-to-bitmask mappings, permanent bindings, output routing, style triggers, and SysEx song sync configuration. Parsed once at startup. See `docs/DeviceConfig.md` for full syntax reference.

### How they interact

- **ControllerMap** references controls by their DeviceConfig **label** (e.g., `Enc1`, `Fader3`), not by type+number. The label is resolved to a physical CC at parse time via DeviceConfig.
- **Song maps** override individual macros or layers from Default. Unspecified elements inherit.
- **Permanent bindings** in DeviceConfig (e.g., CC64 = SYSTEM_TOGGLE) are always active, independent of the loaded ControllerMap.
- If you get a new keyboard with different CC numbers, you edit DeviceConfig once. All ControllerMaps follow because they reference labels, not CC numbers.

---

## 3. ControllerMap Syntax

### Full line syntax

```
Macro<N> = DEV<d>:LAY<l>:<Label> [& DEV<d>:LAY<l>:<Label>] ; <Bindings>
```

- `Macro<N>` -- macro slot index (1--256).
- `DEV<d>:LAY<l>:<Label>` -- hardware source. `d` = device index, `l` = layer index, `Label` = control label from DeviceConfig.
- `&` -- joins multiple hardware sources to one macro (last-write-wins on value).
- `;` -- separates the source declaration from bindings.
- `<Bindings>` -- one or more binding targets separated by `|`.

Every macro declares exactly **one layer** in its source. A physical control on different layers maps to different macros:

```ini
Macro1  = DEV0:LAY0:Enc1; VST1_GRS:48{0.0,1.0}
Macro25 = DEV0:LAY1:Enc1; ROOT:CH1{OTZ,1.0,1.0}
Macro26 = DEV0:LAY2:Enc1; OCTAVER:CH1{OTZ,1.0,1.0}
```

If no `DEV...;` prefix is present in a song map line, the source is inherited from `[Map:Default]`.

### Binding kinds

| Kind | Syntax | Multi-`|` | Purpose |
|---|---|---|---|
| **VST parameter** | `VST<k>_GRS:<paramIdx>[:<label>] [{SPEC}]` | yes (up to 8 bindings) | Route macro to a parameter on the k-th VST slot |
| **Direct CC** | `Ch<c>:CC<n>[:<label>] [{SPEC}]` | yes | Emit a CC message on channel c, number n |
| **Keyword** | See list below | one per role | Bind a fixed global system function |
| **SYSACT role** | `SYSACT_<NAME>` | no (Isolation Rule) | Bind a virtual SYS-MODE action |
| **OTZ overlay** | `<FuncName>:CH<c>{OTZ,SPEC}` | yes | Read-only overlay riding on a base binding |
| **Base overlay** | `<FuncName>:CH<c>{SPEC}` (alone) | yes | Overlay promoted to base (motorized RESET possible) |

The `{SPEC}` suffix is optional; default is `{0.0, 1.0}` (full-range pass-through). See **SPEC tokens** below for keyword syntax (`MAX`, `MIN`, `DIR`, `RESET`).

### SPEC tokens (OTZ Redesign)

A binding's `{...}` suffix is a comma-separated list of tokens:

| Token | Meaning |
|---|---|
| `x,y` (numeric) | `x==y` = **point trigger** at x. `x<y` = **range trigger** in [x, y]. |
| `MAX` | Shorthand for `1.0,1.0` (trigger at full right/up) |
| `MIN` | Shorthand for `0.0,0.0` (trigger at full left/down) |
| `DIR` | **Directional**: each plus-movement = ON, each minus-movement = OFF, with 10s debounce |
| `RESET` | Write hardware value back to 0.5 after fire (only valid on **base** bindings, ignored on OTZ) |
| `OTZ` | Mark binding as **read-only overlay** (must be first token in SPEC) |

### Base vs. OTZ

Each macro line can contain multiple pipe-separated bindings, up to **8 total**:

- **First pipe-entry** (no OTZ prefix) is the **Base binding** — it owns the value and can write back to hardware (`RESET`).
- **Subsequent pipe-entries** with OTZ prefix are **Overlays** — read the base value, trigger ON/OFF transitions, never write.
- **Overlay-alone** (single pipe-entry targeting an overlay function without OTZ, e.g. `SMART_SOLO:CH3{DIR,RESET}`) is **promoted to base** — it owns the value and can use RESET for motorized center-return.

### Trigger modes

| Binding mode | Example | Fire condition |
|---|---|---|
| POINT | `{OTZ,MAX}` or `{OTZ,1.0,1.0}` | Value equals trigger point (±0.02 tolerance) |
| RANGE | `{OTZ,0.4,0.6}` | Value inside [min,max] → ON; outside → OFF |
| DIR | `{OTZ,DIR}` | Value increased from last = ON; decreased = OFF. 10s debounce. |

### Per-control debounce

When any OTZ overlay fires on a physical control, **all** OTZ overlays on that control are blocked for 10 seconds. The base binding continues to accept value changes normally. This prevents double-triggering when a user lingers near a trigger point.

### Echo protection

- **RESET writes** (GP→hardware) trigger a 200ms echo block — incoming CC values during this window do not re-trigger OTZ overlays.
- **LFO-generated values** (via `TickLFOs`) are tagged as echo → OTZ overlays are skipped while LFO modulates the base.

### Keywords

| Keyword | What it does |
|---|---|
| `CROSSFADER` | Global audio / expression balance fader |
| `SCRUBBER` | Timeline scrubber + panic transport stop |
| `SYSTEM_TOGGLE` | Press-and-hold gesture activating System Mode |
| `VST_SCOPE` | Direct VST scope select (rotary encoder, absolute) |
| `VST_SCOPE_PREV` / `VST_SCOPE_NEXT` | Step to previous/next VST scope (button pair) |
| `VST_PREV` / `VST_NEXT` | Step to previous/next VST preset on current scope |
| `VST_BROWSE` | Preset browse encoder |
| `SYSMODE_CYCLE` | Cycle through the 5 SYS-MODE modes |
| `SYSMODE_SELECT` | Absolute SYS-MODE selection (0--4) |
| `REC_SONGPART` | Record: mark next song part (timeline marker) |

### Multi-assignment on one slot

For VST and CC bindings, combine multiple targets with `|`:

```ini
Macro4 = DEV0:LAY0:Enc4; VST1_GRS:48:Cutoff | Ch11:CC18:Phaser{0.0,1.0} | Ch12:CC18:Phaser{0.0,1.0}
```

All three targets fire in parallel when Macro 4 changes.

### Multi-device sources

Multiple hardware sources feed one macro via `&`:

```ini
Macro15 = DEV0:LAY0:Fader3 & DEV1:LAY0:Fader1; VST1_GRS:2{0.0,1.0}
```

Last-write-wins on value. Debounce is per-macro, not per-source.

### Per-layer inheritance rules

| Element in song map | Behavior |
|---|---|
| No `DEV...;` prefix | Source inherited from Default |
| `DEV...;` prefix present | Source completely replaced |
| Macro not listed | Entire macro inherited from Default |

Song maps override per-macro. Unspecified macros and layers remain as defined in `[Map:Default]`.

---

## 4. Overlay Trigger Zones (OTZ)

### Concept

OTZ overlays **ride on top of** a base binding. The base owns the hardware value (writes to the VST); OTZ overlays watch that value and fire ON/OFF transitions at specific points or ranges. OTZ overlays are **read-only** — they never write back to hardware.

**State is layer-persistent**: Once an OTZ triggers ON, it stays ON across layer changes until the user explicitly triggers OFF (by binding an OFF-capable control in any layer referencing the same target channel).

### Example: slider with multiple OTZ overlays

```ini
Macro1 = DEV0:LAY0:Slider1; VST1_GRS:48{0.0,1.0} | ROOT:CH1{OTZ,MIN} | OCTAVER:CH1{OTZ,MAX} | HUMANIZE:CH1{OTZ,0.4,0.6}
```

On Slider1:
- Base binding drives VST1 parameter 48 with full range.
- At value 0.0 (full left) → `ROOT:CH1` fires ON.
- At value 1.0 (full right) → `OCTAVER:CH1` fires ON.
- In range 0.4–0.6 → `HUMANIZE:CH1` is ON, outside → OFF.

### Overlay-alone (promoted to base)

If the only binding is an overlay target without OTZ prefix:

```ini
Macro7 = DEV0:LAY0:Enc1; SMART_SOLO:CH3{DIR,RESET}
```

The overlay **becomes the base** — it owns the hardware value and can use `RESET` for motorized center-return. This is the typical pattern for an endless encoder dedicated to toggling a single overlay.

### Registered overlay functions

| Function name | Activate | Deactivate |
|---|---|---|
| `SMART_SOLO` | `Mem_SoloSmart[ch]=1`, clear Strict | `Mem_SoloSmart[ch]=0` |
| `STRICT_SOLO` | `Mem_SoloStrict[ch]=1`, clear Smart | `Mem_SoloStrict[ch]=0` |
| `ROOT` | `SetChordMode(ch, 1)` | `SetChordMode(ch, 0)` |
| `OCTAVER` | `SetOctaverMode(ch, 1)` | `SetOctaverMode(ch, 0)` |
| `USER_MUTE` | `Mem_UserMute[ch]=1` | `Mem_UserMute[ch]=0` |
| `HUMANIZE` | `SetHumanize(ch, 1)` | `SetHumanize(ch, 0)` |
| `SCALE` | `SetScaleQuantizer(ch, 1)` | `SetScaleQuantizer(ch, 0)` |
| `RANGE` | `SetVelocityRange(ch, 1)` | `SetVelocityRange(ch, 0)` |
| `AUTO_SUSTAIN` | `SetAutoSustain(ch, 1)` | `SetAutoSustain(ch, 0)` |

Unknown function names combined with OTZ are ignored with a Trace warning. All registered functions route through `ActivateOverlay()` / `DeactivateOverlay()` — the same entry points used by Strip Control UI and widget buttons. Timeline recording captures every transition automatically.

### Button overlays

For NOTE-bound sources (buttons), range/keyword specs are ignored at runtime — press = ON, release = OFF:

```ini
Macro9 = DEV0:LAY0:BTN1; SMART_SOLO:CH4{OTZ,MAX}
```

BTN1 press triggers `SMART_SOLO:CH4` ON, release triggers OFF. The `MAX` keyword is kept for compatibility but has no runtime effect on buttons.

### Display behavior

- **Normal control movement (no OTZ transition):** `LBL_MacroFeedback` shows `"VST_GRS | Gain : 73% | HUMANIZE ON"` (base + currently-active OTZ overlays).
- **OTZ transition event:** `LBL_MacroFeedback` shows just the overlay: `"OCTAVER:CH1 : ON"` (1.5s timer, then cleared).
- **LBL_ControllerInfo:** Active OTZ overlays get a `*` suffix for live-state debugging.

---

## 5. SYSACT Roles (the System Action Framework)

SYSACT roles are virtual actions that can be bound to any user-zone macro slot. There are **20 virtual actions** covering VST navigation, looper control, controller map browsing, strip control, and timeline operations.

### The 20 roles

| # | Name | Label | What it does |
|---|---|---|---|
| 0 | `SYSACT_VST_SCOPE_UP` | VST Scope [Next] | Advance VST scope by one, apply focus bypass |
| 1 | `SYSACT_VST_SCOPE_DOWN` | VST Scope [Prev] | Step back one VST scope |
| 2 | `SYSACT_VST_PRESET_UP` | VST Preset [Next] | Load next preset on current VST scope |
| 3 | `SYSACT_VST_PRESET_DOWN` | VST Preset [Prev] | Load previous preset |
| 4 | `SYSACT_LOOPER_CH_UP` | Looper Channel [Next] | Cycle looper channel scope forward |
| 5 | `SYSACT_LOOPER_CH_DOWN` | Looper Channel [Prev] | Cycle looper channel scope backward |
| 6 | `SYSACT_LOOPER_REC` | Looper Record | Click Loop Record widget (rec/play/overdub) |
| 7 | `SYSACT_LOOPER_CLEAR` | Looper Clear | Click Loop Clear widget for current channel |
| 8 | `SYSACT_CTRLMAP_PREV` | Ctrl Map [Prev Active] | Preview previous active Controller Map |
| 9 | `SYSACT_CTRLMAP_NEXT` | Ctrl Map [Next Active] | Preview next active Controller Map |
| 10 | `SYSACT_CTRLMAP_RESTORE` | Ctrl Map Restore Initial | Reload the song's original Controller Map |
| 11 | `SYSACT_CTRLMAP_CYCLE` | Ctrl Map Cycle | Cycle through all Controller Maps |
| 12 | `SYSACT_STRIP_CH_UP` | Strip Channel [Next] | Cycle Strip Control channel scope forward |
| 13 | `SYSACT_STRIP_CH_DOWN` | Strip Channel [Prev] | Cycle Strip Control channel scope backward |
| 14 | `SYSACT_STRIP_THEME_PREV` | Strip Theme [Prev] | Cycle Strip Control theme backward |
| 15 | `SYSACT_STRIP_THEME_NEXT` | Strip Theme [Next] | Cycle Strip Control theme forward |
| 16 | `SYSACT_STRIP_MACRO_TOGGLE` | Strip Macro Toggle | Toggle macro at current Strip Control position |
| 17 | `SYSACT_TL_PARTJUMP_NEXT` | Timeline Part Jump [Next] | Preview next song part |
| 18 | `SYSACT_TL_PARTJUMP_PREV` | Timeline Part Jump [Prev] | Preview previous song part |
| 19 | `SYSACT_TL_REC_SONGPART` | Timeline Rec Songpart | Mark current position as song part during recording |

The registry lives in `Global Rackspace.gpscript` SECTION 2 (`SysAction_Names` / `SysAction_Labels`). Adding a new action: new entry in both arrays, new case in `FireSystemAction()` -- parser and display pick it up automatically.

### Binding syntax

```ini
[Map:MySong]
Macro37 = DEV0:LAY3:Enc1; SYSACT_VST_SCOPE_UP
Macro38 = DEV0:LAY3:Enc2; SYSACT_VST_SCOPE_DOWN
```

Both the joystick path (`ProcessSystemNavigation`) and the hardware-button path (`ExecuteHardwareMacro`) converge on the same `FireSystemAction(actionIdx)` dispatcher. Any joystick action can also be triggered by a bound control with zero code changes.

### The Isolation Rule

> A `SYSACT_*` role binds to a macro slot **only when the binding list is a single entry.** If the line contains a `|` separator mixing SYSACT with other targets, the SYSACT token is silently dropped; the remaining entries are parsed normally.

A macro slot is either exclusively a SYSACT role, or it is not a SYSACT role at all. This prevents ambiguous record/playback semantics and keeps the Timeline filter clean.

**Examples:**

```
Macro5 = DEV0:LAY3:Enc5; SYSACT_VST_SCOPE_UP                         -- bound
Macro5 = DEV0:LAY0:Enc5; SYSACT_VST_SCOPE_UP | VST1_GRS:0:Level      -- SYSACT dropped, VST link active
Macro5 = DEV0:LAY0:Enc5; SYSACT_BOGUS_NAME                           -- unknown action, Trace warning, slot unbound
```

### Timeline recording consequence

If a slot is in `SysAction_ByMacro[]`, `IsSystemActionMacro(paramIdx)` returns true and `RecordTimelineEvent()` is skipped. A multi-assigned slot (where SYSACT was dropped) records as a normal macro event.

---

## 6. SYS-MODE -- The Joystick Navigation Layer

SYS-MODE is a modal state machine. When `SYSTEM_TOGGLE` is active (held, or forced via LAY3 overlay), the hardware joystick axes are hijacked from musical use and become a navigation controller. There are **5 modes**, cycled in order:

| # | Name | Joystick Y axis | Joystick X axis | Button / Encoder |
|---|---|---|---|---|
| 0 | **VOICE SELECTOR** | VST scope +/- | VST preset +/- | Same as axis |
| 1 | **LOOPER CONTROL** | Channel scope +/- | Left=Clear, Right=Rec | Button=Rec |
| 2 | **CONTROLLER MAP** | Up=Restore initial | Prev/Next active map | Button=Cycle all |
| 3 | **STRIP-CONTROL** | Channel scope +/- | Left=Theme prev, Right=Macro toggle | Button=Macro toggle |
| 4 | **TIMELINE** | Toggle PLAY/REC | PLAY: Part jump; REC: Rec songpart (right) / Replace-Overdub-Discard cycle (left) | Same as Y |

### Mode 0 -- VOICE SELECTOR

Quick VST scope and preset navigation. Y+ advances to the next VST slot, Y- goes back. X+ loads the next preset on the focused VST, X- loads the previous. Default "browse sounds" mode.

### Mode 1 -- LOOPER CONTROL

Per-channel looper management. Y selects the channel scope (1--16). X-left clears the current channel's loop, X-right triggers the Record / Play / Overdub state flow. Button = Record (same as X-right).

### Mode 2 -- CONTROLLER MAP

Browse ControllerMap sections at runtime. Y+ restores the song's originally loaded map. X cycles through active maps. Button cycles through all maps.

### Mode 3 -- STRIP-CONTROL

A 16-channel x 9-theme grid. Y picks the channel (1--16). X-left cycles the theme (Octaver, Humanizer, Scale Quantizer, Auto Sustain, Looper, Smart Solo, Strict Solo, User Mute, Velocity Range, Root/Chord). X-right or button toggles the macro at the current channel+theme position.

### Mode 4 -- TIMELINE

Song timeline playback and recording.

- **PLAY sub-mode** (default): Y or button toggles to REC. X/encoder jumps through song parts.
- **REC sub-mode**: Y or button commits recording and returns to PLAY. X-right marks the current position as a song part. X-left cycles recording policy: Replace / Overdub / Discard.

Timeline meta-controls (PLAY/REC toggle, recording policy cycle, discard) are deliberately **not** virtualized through SYSACT -- recording the recording controls into the timeline stream would be nonsensical.

### Dispatch

Joystick events land in `On PitchBendEvent` / `On ControllerEvent`, which calls `ProcessSystemNavigation(deviceID, actionType, direction)`. Every virtualizable branch routes through `FireSystemAction(SysActIdx("<NAME>"))` -- the same entry point as hardware-button-bound SYSACT roles.

Joystick axis thresholds (`ThresholdHigh`, `ThresholdLow`) and direction (`+1`/`-1`) are data-driven from the `[CONTROL:n]` entries in DeviceConfig with `Type=JOYSTICK`. They are not hardcoded in the script. See `docs/DeviceConfig.md` -- **Joystick fields** for field reference.

---

## 7. Smart Solo Enhanced

Smart Solo now considers both the **RECH routing input** and the **Manual zone** (Upper / Lower / None) when deciding which channels to mute.

### Logic

```
For each channel outCol (0-15):
  If Mem_SoloSmart[outCol] == 0:
    For each soloed channel soloCh:
      sameInput = any RECH row routes to both outCol and soloCh
      sameZone  = Mem_Manual[outCol] == Mem_Manual[soloCh]
      If sameInput AND sameZone:
        LooperSoloMute[outCol] = true
```

### Behavior matrix

| Solo channel zone | Other channel zone | Result |
|---|---|---|
| Upper | Upper | Muted (same zone) |
| Upper | Lower | **Not muted** (different zone) |
| Upper | None (Arranger) | **Not muted** (Arranger free) |
| None | None | Muted (same zone) |

### Practical effect

Soloing an Upper channel mutes other Upper channels sharing the same input, but Lower channels and Arranger channels (zone = None) continue playing. This allows left-hand solo without silencing the backing.

---

## 8. VST Validation

### Map-level VST declarations

Each map that references VST parameters must declare expected VSTs:

```ini
[Map:SlowHip80erDream]
VST1=Omnisphere
VST3=Triton Extreme
Macro14 = DEV0:LAY0:Fader2; VST1_GRS:1:Level (p2){0.000,0.442}
Macro16 = DEV0:LAY0:Fader4; Ch13:CC7:Volume Triton
```

`[Map:Default]` also declares its expected VSTs. Song maps inherit Default's declarations and can override them.

### Per-binding validation

At map load, each declared VST is compared against the actually loaded plugin (`GetPluginName(BLK_VST[x])`). Results per VST: VALID, MISMATCH, or NOT_LOADED.

| Binding type | VST valid | Behavior |
|---|---|---|
| VST parameter | Yes | Execute normally |
| VST parameter | No | **BLOCKED** -- not executed, warning in display |
| CC routing | -- | Always execute |
| Keyword | -- | Always execute |
| SYSACT role | -- | Always execute |
| Overlay function | -- | Always execute |

Only VST-referencing bindings are affected. All other binding types always execute regardless of VST validation state.

### BTN_SmartAdapt

SmartAdapt reads the plugin name from the current VST scope (`GetPluginName(BLK_VST[CurrentVstScope])`) and searches for a `[Map:<PluginName>]` section. If found, it loads with validation. If not found, the current map stays active with a Trace warning.

---

## 9. Timeline Recording

All overlay toggles are recorded into the Timeline -- no exceptions, no per-function filter. Every `ActivateOverlay()` / `DeactivateOverlay()` call triggers `RecordTimelineEvent()`.

Overlay events are encoded as `OVL_<func>` event type with channel and state (on/off).

If a toggle should not have been recorded, the user can delete it from the Timeline file after the fact. The design principle: live performance equals arrangement -- everything played is captured.

SYSACT-exclusive macros are **not** recorded (filtered by `IsSystemActionMacro()`). Normal macros (VST/CC bindings) are always recorded. The Isolation Rule ensures there is never ambiguity between the two categories.

---

## 10. Troubleshooting

### "My SYSACT binding doesn't fire."

1. Check the line for a `|` separator -- SYSACT roles are dropped from multi-assigned lines per the Isolation Rule.
2. Enable `DebugMode` and look for `SYSACT: Unknown action name` (typo) or `SYSACT: Multi-assigned` (isolation violation).
3. Verify the macro's `DEV<d>:LAY<l>:<Label>` source resolves to a valid control in DeviceConfig.

### "My overlay doesn't fire."

1. Check that the binding uses the `{OTZ,...}` marker (or is the only binding on the macro, to be auto-promoted as base).
2. Verify the function name is one of the 9 registered names (SMART_SOLO, STRICT_SOLO, ROOT, OCTAVER, USER_MUTE, HUMANIZE, SCALE, RANGE, AUTO_SUSTAIN).
3. Check that the macro's source layer matches the currently active layer.
4. For OTZ overlays: another OTZ on the same control may have fired recently → **10-second per-control debounce** blocks further OTZ triggers. Base binding keeps working.
5. For `DIR` mode: the movement direction must exceed ±0.02 threshold from the last-recorded value.
6. For LFO-bound macros: OTZ overlays are suppressed while the LFO modulates the base (echo protection).

### "Song loads the wrong map."

1. Check the snapshot `.ini` file for the `ControllerMap=` value -- this is what determines which map loads with the song.
2. Verify the `[Map:<name>]` section exists in `ControllerMaps.txt` with the exact name (case-sensitive).

### "I edited ControllerMaps.txt and nothing changed."

Make sure you are editing the correct `[Map:<name>]` section. Gig Performer requires a rackspace reload (or snapshot switch) to pick up file changes.

### "VST binding shows BLOCKED in the display."

The map declares a VST (e.g., `VST3=Triton Extreme`) but the actually loaded plugin in that slot does not match. CC bindings, keywords, SYSACT roles, and overlay functions on the same map continue working -- only VST-referencing bindings are blocked.

### "Single-role keyword appears twice in my map -- which wins?"

Last-wins semantics. If both `Macro5` and `Macro8` are bound to `CROSSFADER` in the same section, only `Macro8` takes effect.

---

## Reference -- File Locations

| File | Path | Edited by hand? |
|---|---|---|
| Global Rackspace script | `Global Rackspace.gpscript` | Yes (source) |
| Note Prozessor scriptlet | `Note Prozessor.gpscript` | Yes (source) |
| Controller Maps | `ControllerMaps.txt` (next to gig file) | Yes (primary workflow) |
| Device Config | `DeviceConfig.txt` (next to gig file) | Yes (hardware setup) |
| Rackspace settings | `UserSnapshotPath` folder | No |

## Reference -- Key Specs

- **OTZ/Overlay redesign (keyword syntax, base vs overlay, 8 bindings):** `docs/superpowers/specs/2026-04-14-otz-overlay-redesign.md`
- **Unified ControllerMap, layer system, Smart Solo Enhanced:** `docs/superpowers/specs/2026-04-12-layer-system-unified-controllermap-design.md`
- **Control label reference:** `docs/superpowers/specs/2026-04-12-control-label-reference-design.md`
- **Layer-aware reverse lookup:** `docs/superpowers/specs/2026-04-12-layer-aware-reverse-lookup-design.md`
- **Macro renumbering, SYSACT framework:** `docs/superpowers/specs/2026-04-10-vel-tamper-macro-refactor-sysact-design.md`

## Reference -- Related Documents

- **DeviceConfig Reference:** `docs/DeviceConfig.md` -- hardware devices, controls, layers, output routing, style triggers, SysEx song sync
