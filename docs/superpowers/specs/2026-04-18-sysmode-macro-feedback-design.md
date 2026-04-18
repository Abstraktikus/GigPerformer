# SYS-MODE Feedback Labels — Clean, Persistent, No Chevrons

**Date:** 2026-04-18
**Status:** Implemented (v2026-04-18.004)
**Scope:** `Global Rackspace.gpscript` — feedback routing across all SYS-MODE navigation paths.

## Problem

Joystick navigation inside STRIP-CONTROL (and other SYS-MODEs) felt visually chaotic:
- Every Joystick Left/Right/Up/Down fired a momentary `">>> ... <<<"` overlay in `LBL_SysModeFeedback`, overwriting the base title for a few seconds.
- Chevrons everywhere made the UI feel "wild" and twitchy — especially during live performance.
- Strip-Control toggle feedback also landed in the base-title label, cluttering it.
- Base-title for STRIP-CONTROL tracked `GetDefaultScopeChannel()`, not the actual cursor (`Strip_ChannelIdx`), so Joystick Up had no visible effect on the title.

## Design

### Two-label semantics, made consistent

| Label | Content | Persistence |
|---|---|---|
| `LBL_SysModeFeedback` | Base-title via `SysModeFeedbackTitle()` — mode name + key state | Persistent; only replaced on SYSMODE switch or cursor move. **No momentary overlays, no chevrons.** |
| `LBL_MacroFeedback` | "MakroName [ON/OFF]" or mode-specific action status | Persistent; replaced by the next macro action or SYSMODE switch. **No chevrons.** |

### Key design decisions

1. **INHALT vs DEFAULT (user's framing):** `Strip_ChannelIdx` is the **cursor** (INHALT). `GetDefaultScopeChannel()` is a **fallback** (DEFAULT), used only to initialize the cursor on SYSMODE entry. The base-title now reflects `Strip_ChannelIdx`.
2. **No chevrons anywhere.** Removed globally across all writes to `SetSysModeFeedback`, `SetMacroFeedback`, `SetHeader`, and `ShowVSTOverlay`.
3. **Persistent status.** Macro-feedback does not auto-expire. It stays until the next macro action or SYSMODE switch.
4. **"Nothing to cycle" pattern.** If `CycleStripChannel` can't find another valid OutputScope channel (cursor end = cursor start), show `"Nothing to cycle"` in `LBL_MacroFeedback` for 1.5s, then revert to the sticky cell label. Same pattern reserved for other cycle paths.

## Affected Code

### New helpers (forward-declared before `SysModeFeedbackTitle`)

**`GetStripCellLabel(themeIdx, ch) Returns String`**
Maps a strip grid cell to its current state string: `"Smart Solo [ON]"`, `"Humanizer [OFF]"`, etc. Reads the matching `Mem_*` array per theme index.

**`InitializeSystemModeMacroFeedback()`**
Writes the initial "first cell info" of the current SYSMODE to `LBL_MacroFeedback`. For STRIP-CONTROL, ensures `Strip_ChannelIdx` points to a valid scope channel first (snaps to `GetDefaultScopeChannel()` if not). For other modes: blank for now.

### New variable

**`MacroFeedbackRestoreSticky : Boolean`**
Marks a transient macro-feedback message (e.g., "Nothing to cycle") that should revert to the mode's sticky label on timer expiry, instead of blanking.

### `SysModeFeedbackTitle()` — STRIP-CONTROL branch
Changed from `GetDefaultScopeChannel()` to `Strip_ChannelIdx`. Base-title now follows the cursor.

### `CycleStripTheme(dir)`
Writes `GetStripCellLabel(Strip_ThemeIdx, Strip_ChannelIdx)` to `LBL_MacroFeedback`. Persistent (no timer).

### `CycleStripChannel(dir)`
Captures `startIdx`. If cursor moved: refresh base-title + macro cell label. If not: show `"Nothing to cycle"` transiently (1.5s) with `MacroFeedbackRestoreSticky = true`.

### `ToggleStripMacro()`
Writes `"{ParamName} [{ON/OFF}]"` to `LBL_MacroFeedback`. No chevrons, no timer.

### `CycleGlobalSystemMode()` + `SelectGlobalSystemMode()`
Base-title written chevron-free. `InitializeSystemModeMacroFeedback()` seeds `LBL_MacroFeedback` with the new mode's initial cell info.

### TimerTick macro-feedback expiry (~line 18834)
On expiry:
- If `MacroFeedbackRestoreSticky == true`: write the mode's sticky label back (STRIP-CONTROL → current cell label). Reset the flag.
- Else: blank as before.

### Global chevron removal
Replaced `">>> "` / `" <<<"` / `">> "` / `" <<"` → `""` across the file. Touches all `OSC_SendStringSpecific`, `ShowVSTOverlay`, `SetHeader`, and a handful of debug-trace strings. No functional change — purely cosmetic.

## Out of Scope

- **LBL_VSTConfiguration / LBL_ControllerInfo chevrons:** still contain internal `>>> text` prefixes (e.g. `"    >>> PRESS REPLACE"`). These are in separate overlay systems that Martin did not explicitly scope. Pending a follow-up if he wants those removed too.
- **Per-mode sticky labels for TIMELINE / LOOPER / CONTROLLER-MAP / VOICE-SELECTOR:** `InitializeSystemModeMacroFeedback` currently blanks non-STRIP modes. Each mode will get its own sticky semantics in subsequent passes.
- **"Nothing to cycle" for non-STRIP cycles:** the helper pattern is in place but only wired into `CycleStripChannel` for now. Timeline part-jump, looper target, controller-map cycle: follow-up.

## Test Plan (Live)

1. Enter STRIP-CONTROL. Base-title: `"STRIP-CONTROL: RECH (11)"` (example). No chevrons.
2. Joystick Right (theme cycle forward) → `LBL_MacroFeedback` shows `"Smart Solo [ON]"` or similar. Base stays.
3. Joystick Up (channel cycle forward) → base-title updates to next scope channel. Macro label updates to cell state of new cell.
4. If only one channel in scope: Joystick Up shows `"Nothing to cycle"` for 1.5s, then reverts.
5. Toggle (macro fire) → `LBL_MacroFeedback` shows `"Smart Solo [ON]"`, stays until next action.
6. SYSMODE switch → base-title updates. Macro label reinitializes with new mode's first cell info (STRIP) or blank (others).
