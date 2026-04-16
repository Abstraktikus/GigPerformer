# Label Feedback Redesign: LayerFeedback / MacroFeedback / SysModeFeedback

**Date:** 2026-04-16
**Status:** Approved (v2 — LFO + Looper + ControllerMap additions)
**Scope:** OSC display labels, feedback routing

## Problem

The three feedback labels (`LBL_LayerFeedback`, `LBL_MacroFeedback`, `LBL_SysModeFeedback`) have overlapping responsibilities. Overlay ON/OFF events go to LayerFeedback, but the permanent state is lost after the 2s timer. There is no persistent overview of which SYS-macros, LFOs, or Looper channels are active.

## Design: Three Labels, Three Lifetimes

| Label | Content | Lifetime | Source |
|-------|---------|----------|--------|
| **LBL_LayerFeedback** | Permanent dashboard: Layer, ControllerMap, LFO, Looper, SYS-macro states | **Persistent** (rebuilt on every change) | `RefreshLayerFeedback()` |
| **LBL_MacroFeedback** | Momentary value change of a base macro | **1.5s timer** (then clears) | Fader/knob movement, SYSMODE triggering a base macro |
| **LBL_SysModeFeedback** | Joystick navigation + SYSMODE actions | **2s timer** (then clears or shows mode name) | Joystick, SYSMODE cycle/select, Timeline, Strip |

### Routing Rules

| Event | Target Label |
|-------|-------------|
| Layer switch | LBL_LayerFeedback (rebuild) |
| Overlay ON/OFF (SYS-macro toggle) | LBL_LayerFeedback (rebuild) |
| Song load (all Mem_* change) | LBL_LayerFeedback (rebuild) |
| Solo/Mute state dirty | LBL_LayerFeedback (rebuild) |
| LFO start/stop | LBL_LayerFeedback (rebuild) |
| Looper state change | LBL_LayerFeedback (rebuild via dirty flag) |
| ControllerMap switch | LBL_LayerFeedback (rebuild) |
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

### Display Layout (top to bottom)

**Line 1: Header** (always visible)
```
LAY<n> | <CurrentCtrlMapName>
```

**Line 2: LFO** (only if any LFO_Active[] == true)
```
LFO: M<macro>=<Name> M<macro>=<Name>
```
Macros listed ascending. Data: `LFO_Active[slot]` + `LFO_ByMacro[slot]` -> `LFO_Names[idx]`.

**Line 3: Looper** (only if any Mem_Loop_State[ch] not 0 and not 4)
```
Loop: REC 2 | PLAY 1,4 | DUB 3 | ARM 5
```
Status groups: State 1=REC, 2=PLAY, 3=DUB, 5/6=ARM, 7=WAIT, 8=CIN.
Only groups with active channels shown. Channel numbers ascending.

**Lines 4-5: SYS-Macros** (only if any group active)
Format C1: aligned columns, only active groups as columns, `-` where inactive in row.
```
U: Sol 1,3 | Oct 1,3 | Hum 1
L: Sol 2   | Oct 2   | Hum -
```

### Full Example
```
LAY0 | Diva Lead
LFO: M3=TriSlow M7=SinFast
Loop: REC 2 | PLAY 1,4 | ARM 3
U: Sol 1,3 | Oct 1,3 | Hum 1
L: Sol 2   | Oct 2   | Hum -
```

### Minimal Example (nothing active)
```
LAY0 | Standard
```

### Row Assignment (SYS-Macros)

- **U (Upper):** Channels where `Mem_Manual[ch] == 0` (None) or `Mem_Manual[ch] == 1` (Upper)
- **L (Lower):** Channels where `Mem_Manual[ch] == 2` (Lower)
- If no Lower channels exist, the L row is omitted entirely.

### Group Abbreviations and Order (SYS-Macros)

| Index | Name | Abbrev | Mem_Array |
|-------|------|--------|-----------|
| 3 | Smart Solo | Sol | `Mem_SoloSmart[ch]` |
| 4 | Strict Solo | Str | `Mem_SoloStrict[ch]` |
| 5 | User Mute | Mut | `Mem_UserMute[ch]` |
| 6 | Velocity Range | Rng | `Mem_NP_VelRangeActive[ch]` |
| 7 | Root/Chord | Roo | `Mem_NP_ChordMode[ch]` |
| 8 | Octaver | Oct | `Mem_NP_Octaver[ch]` |
| 9 | Humanizer | Hum | `Mem_NP_HumanizeActive[ch]` |
| 10 | Scale Quantizer | Qnt | `Mem_NP_QuantizeActive[ch]` |
| 11 | Auto Sustain | Sus | `Mem_NP_AutoSustain[ch]` |

### Refresh Strategy

**Direct call** for low-frequency events:
- `ActivateOverlay()` / `DeactivateOverlay()`
- `UpdateActiveLayer()`
- `LoadControllerMap()` (end)
- `StartLFO()` / `StopLFO()` / `HardStopAllLFOs()`
- End of `LoadSongSnapshot()`
- `UpdateSoloMuteState()`

**Dirty flag + TimerTick** for high-frequency Looper state changes:
- `LayerFeedbackDirty : Boolean` — set true wherever `Mem_Loop_State[ch]` is written
- Checked in `On TimerTick`: if dirty and past FaderSafetyTimer, call `RefreshLayerFeedback()` and clear flag
- This avoids calling refresh 50x per tick during Looper math

### Core Function: `RefreshLayerFeedback()`

```
Function RefreshLayerFeedback()
   1. Build header: "LAY" + ActiveLayer + " | " + CurrentCtrlMapName
   2. Build LFO line: scan LFO_Active[0..255], collect "M<slot+1>=<name>"
   3. Build Looper line: scan Mem_Loop_State[0..15], group by state
   4. Build SYS-macro lines:
      a. For each group (9 groups): scan 16 channels, check Mem_*[ch] > 0
      b. Mark visible groups (any channel active globally)
      c. Build U row: for each visible group, list upper/none channels or "-"
      d. Build L row: for each visible group, list lower channels or "-"
   5. Assemble with NEW_LINE between non-empty sections
   6. OSC_SendStringSpecific("/UI/SetLayerFeedback", result, Local_IP, Local_PORT)
End
```

## LBL_MacroFeedback: Momentary Values (1.5s)

No structural change. Timer clears after 1.5s (existing behavior).

## LBL_SysModeFeedback: Navigation (2s)

No structural change. Timer resets to mode name or clears (existing behavior).

## Changes Summary

### New
- `RefreshLayerFeedback()` function
- `LayerFeedbackDirty : Boolean` global
- `SysMacro_Abbrev : String Array` constant

### Modified
- `ActivateOverlay()` — replace OSC + timer with `RefreshLayerFeedback()`
- `DeactivateOverlay()` — same
- `UpdateActiveLayer()` — replace OSC send with `RefreshLayerFeedback()`
- `LoadControllerMap()` end — add `RefreshLayerFeedback()`
- `LoadSongSnapshot()` end — add `RefreshLayerFeedback()`
- `UpdateSoloMuteState()` end — add `RefreshLayerFeedback()`
- `StartLFO()` / `StopLFO()` / `HardStopAllLFOs()` — add `RefreshLayerFeedback()`
- All `Mem_Loop_State[ch] = ...` sites — add `LayerFeedbackDirty = true`
- `On TimerTick` — add dirty-flag check, remove LayerFeedbackTimer block

### Removed
- `LayerFeedbackTimer` (no longer needed)
- `LayerFeedbackStatus` (replaced by reading ActiveLayer directly)
