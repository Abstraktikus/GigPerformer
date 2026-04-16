# Label Feedback Redesign: LayerFeedback / MacroFeedback / SysModeFeedback

**Date:** 2026-04-16
**Status:** Approved
**Scope:** OSC display labels, feedback routing

## Problem

The three feedback labels (`LBL_LayerFeedback`, `LBL_MacroFeedback`, `LBL_SysModeFeedback`) have overlapping responsibilities. Overlay ON/OFF events go to LayerFeedback, but the permanent state is lost after the 2s timer. There is no persistent overview of which SYS-macros are active across channels.

## Design: Three Labels, Three Lifetimes

| Label | Content | Lifetime | Source |
|-------|---------|----------|--------|
| **LBL_LayerFeedback** | Permanent dashboard: Active layer + all SYS-macro states | **Persistent** (always visible, rebuilt on every change) | `RefreshLayerFeedback()` |
| **LBL_MacroFeedback** | Momentary value change of a base macro | **1.5s timer** (then clears) | Fader/knob movement, SYSMODE triggering a base macro |
| **LBL_SysModeFeedback** | Joystick navigation + SYSMODE actions | **2s timer** (then clears or shows mode name) | Joystick, SYSMODE cycle/select, Timeline, Strip |

### Routing Rules

| Event | Target Label |
|-------|-------------|
| Layer switch | LBL_LayerFeedback (rebuild) |
| Overlay ON/OFF (SYS-macro toggle) | LBL_LayerFeedback (rebuild) |
| Song load (all Mem_* change) | LBL_LayerFeedback (rebuild) |
| Solo/Mute state dirty | LBL_LayerFeedback (rebuild) |
| Fader/knob moves a base macro | LBL_MacroFeedback (1.5s) |
| SYSMODE triggers a base macro | LBL_MacroFeedback (1.5s) |
| SYSMODE triggers a SYS-macro (overlay) | LBL_LayerFeedback (rebuild) |
| Joystick navigation | LBL_SysModeFeedback (2s) |
| SYSMODE cycle/select | LBL_SysModeFeedback (2s) |
| Timeline record/play/part | LBL_SysModeFeedback (2s) |
| Strip channel/theme/macro toggle | LBL_SysModeFeedback (2s) |
| ControllerMap switch/restore | LBL_MacroFeedback (2s) |
| Smart Adapt map switch | LBL_MacroFeedback (2s) |
| Scope change | LBL_SysModeFeedback (1.5s) |
| Anchor jump | LBL_MacroFeedback (2s) |

## LBL_LayerFeedback: Persistent Dashboard

### Display Format (C1: Aligned Columns, Only Active Groups)

The dashboard shows the active layer plus a table of all SYS-macro groups that have at least one active channel anywhere (Upper/None or Lower). Groups with zero active channels globally are omitted entirely. Within a visible group, `-` indicates no active channel in that row.

**Example — Smart Solo on Ch1,3 and Octaver on Ch2:**
```
LAY0
U: Sol 1,3 | Oct -
L: Sol -   | Oct 2
```

**Example — Many active:**
```
LAY1
U: Sol 1,3 | Oct 1,3 | Hum 1 | Qnt 3
L: Sol 2   | Oct 2   | Hum 2 | Qnt -
```

**Example — Nothing active:**
```
LAY0
```

### Row Assignment

- **U (Upper):** Channels where `Mem_Manual[ch] == 0` (None) or `Mem_Manual[ch] == 1` (Upper)
- **L (Lower):** Channels where `Mem_Manual[ch] == 2` (Lower)
- If no Lower channels exist, the L row is omitted entirely.

### Channel Sorting

Within each row, channel numbers are listed ascending: `Sol 1,3,7`

### Group Abbreviations and Order

Groups are displayed in MacroGroup_Names order (indices 3-11), using these 3-letter abbreviations:

| MacroGroup_Names Index | Name | Abbreviation | Mem_Array |
|----------------------|------|--------------|-----------|
| 3 | Smart Solo | Sol | `Mem_SoloSmart[ch]` |
| 4 | Strict Solo | Str | `Mem_SoloStrict[ch]` |
| 5 | User Mute | Mut | `Mem_UserMute[ch]` |
| 6 | Velocity Range | Rng | `Mem_NP_VelRangeActive[ch]` |
| 7 | Root/Chord | Roo | `Mem_NP_ChordMode[ch]` |
| 8 | Octaver | Oct | `Mem_NP_Octaver[ch]` |
| 9 | Humanizer | Hum | `Mem_NP_HumanizeActive[ch]` |
| 10 | Scale Quantizer | Qnt | `Mem_NP_QuantizeActive[ch]` |
| 11 | Auto Sustain | Sus | `Mem_NP_AutoSustain[ch]` |

### Core Function: `RefreshLayerFeedback()`

Single function that reads all `Mem_*` arrays and builds the complete dashboard string.

**Algorithm:**
```
1. Start with "LAY" + ActiveLayer
2. For each SYS-macro group (index 3..11):
   - Scan all 16 channels: any Mem_*[ch] > 0?
   - If yes globally: mark this group as visible
3. If no groups visible: send "LAY<n>" only, return
4. For visible groups, build two channel lists:
   - upperChannels: channels where Mem_Manual[ch] != 2 AND Mem_*[ch] > 0
   - lowerChannels: channels where Mem_Manual[ch] == 2 AND Mem_*[ch] > 0
5. Build Upper row: "U: " + for each visible group: Abbrev + " " + channel list (or "-") + " | "
6. Build Lower row (only if any Lower channels exist in the song):
   "L: " + for each visible group: Abbrev + " " + channel list (or "-") + " | "
7. Assemble: line1 + newline + line2 (+ optional newline + line3)
8. Send via OSC_SendStringSpecific("/UI/SetLayerFeedback", result, Local_IP, Local_PORT)
```

**No timer.** This is a persistent display. `LayerFeedbackTimer` is no longer used for timeout-based clearing. The label always shows the current state.

### Callers of `RefreshLayerFeedback()`

| Location | Current Code | Change |
|----------|-------------|--------|
| `ActivateOverlay()` | `OSC_SendStringSpecific("/UI/SetLayerFeedback", ...)` + timer | Replace with `RefreshLayerFeedback()` |
| `DeactivateOverlay()` | `OSC_SendStringSpecific("/UI/SetLayerFeedback", ...)` + timer | Replace with `RefreshLayerFeedback()` |
| `UpdateActiveLayer()` | Sets `LayerFeedbackStatus` + OSC send | Replace with `RefreshLayerFeedback()` |
| `LoadSongSnapshot()` end | (implicit via SoloMuteState) | Add explicit `RefreshLayerFeedback()` |
| `UpdateSoloMuteState()` end | (no feedback today) | Add `RefreshLayerFeedback()` |
| `TimerTick` LayerFeedbackTimer block | Resets to `LayerFeedbackStatus` | Remove timer block — display is persistent |

## LBL_MacroFeedback: Momentary Values (1.5s)

No structural change. Continues to show base-macro value changes from:

- `TriggerMacroFeedback()` — fader/knob movement
- `ShowBaseFeedback()` — DispatchMacro base binding path
- `ShowOTZFeedback()` — OTZ overlay path (fires to LBL_MacroFeedback as today)

Timer clears after 1.5s (existing behavior).

**Already correctly routed today:**
- ControllerMap switch messages (">>> SELECT: MapName <<<")
- Smart Adapt messages (">>> AUTO-MAP: PluginName <<<")
- Timeline map changes (">>> TL-MAP: MapName <<<")
- Anchor jumps (">>> ANCHOR: SectionName <<<")

## LBL_SysModeFeedback: Navigation (2s)

No structural change. Continues to show:

- SYSMODE cycle/select (">>> SYS-MODE: VOICE SELECTOR <<<")
- Strip theme/channel navigation (">>> STRIP: Octaver <<<")
- Timeline record/play/part (">>> TIMELINE: REC <<<")
- Scope changes (">>> SCOPE: CHANNEL 3 <<<")
- Looper channel navigation
- ControllerMap restore (">>> MAP: Standard <<<")

Timer resets to `SysModeNames[GlobalSystemMode]` if SystemModeActive, else clears (existing behavior).

## Changes Required

### New Code

1. **`RefreshLayerFeedback()` function** — builds the dashboard string from Mem_* arrays
   - Must be placed after `ActivateOverlay`/`DeactivateOverlay` definitions (forward decl order)
   - OR placed before them and called via a deferred timer pattern
   - Recommended: place it right before `ActivateOverlay` since it only reads Mem_* arrays (no forward dependency)

2. **Group abbreviation array** (constant):
   ```
   SysMacro_Abbrev : String Array = ["Sol","Str","Mut","Rng","Roo","Oct","Hum","Qnt","Sus"]
   ```

### Modified Code

3. **`ActivateOverlay()`** — remove direct OSC send + timer, add `RefreshLayerFeedback()` call
4. **`DeactivateOverlay()`** — same
5. **`UpdateActiveLayer()`** — replace OSC send with `RefreshLayerFeedback()`
6. **End of `LoadSongSnapshot()`** — add `RefreshLayerFeedback()`
7. **`UpdateSoloMuteState()`** — add `RefreshLayerFeedback()` at end
8. **`TimerTick` LayerFeedbackTimer block** — remove (no more timer-based reset)

### Removed

9. **`LayerFeedbackTimer`** — no longer needed (persistent display)
10. **`LayerFeedbackStatus`** — replaced by `RefreshLayerFeedback()` which reads `ActiveLayer` directly

## Not Changed

- `LBL_MacroFeedback` routing and timer (1.5s) — stays as-is
- `LBL_SysModeFeedback` routing and timer (2s) — stays as-is
- `MacroFeedbackLockTimer` — stays as-is
- OTZ feedback paths (ShowOTZFeedback / ShowBaseFeedback) — already go to MacroFeedback correctly
