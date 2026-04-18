# Solo & Focus — UserMute Override (Live-Safety)

**Date:** 2026-04-18
**Status:** Design approved
**Scope:** `ApplySoloOverrides()`, `RestoreSoloOverrides()`, `UpdateSoloMuteState()` in `Global Rackspace.gpscript`; one line in the Strip UserMute toggle handler.

## Problem

NoteProcessor firewall (line 671):

```gpscript
if Round(p_SoloMute) == 1 or Round(p_UserMute) == 1 then
   // blocked
```

Any of the two flags silences the channel. The Solo engine and Focus Mode correctly drive `p_SoloMute` via `LooperSoloMute[]`, but neither touches `p_UserMute`. Consequence — live-safety hazard:

1. User mutes channel 11 earlier (`Mem_UserMute[11] = 1`, `p_UserMute[11] = 1`).
2. User activates Strict/Smart Solo on channel 11 (or enters Focus Mode where channel 11 is in scope).
3. `p_SoloMute[11] = 0` is written correctly. But `p_UserMute[11]` stays 1.
4. Channel 11 is **still silent** — it looks like "Solo mutes itself". Catastrophic on stage.

The same gap exists for Focus Mode's "surviving" channels (those the mode decides to keep audible).

## Design Decision

Unify the rule across all muting policies:

> **When any muting policy (Focus / Strict / Smart) is active, every channel the policy keeps *audible* gets `p_UserMute` forced to 0 for the duration of that policy. `Mem_UserMute` is preserved so Restore can put the user's mute back on policy exit.**

This extends the existing Apply/Restore pattern (see `2026-04-16-smart-solo-intelligence-design.md`) by exactly one parameter: `p_UserMute`. No new arrays, no new flags — `Solo_NP_Overridden[ch]` already tracks "this channel has an override to restore".

### Why override, not delete

`Mem_UserMute[ch]` is the user's *intention*. Live playback is a *temporary window*. Overriding the live flag without touching the intention preserves symmetry with the existing NP-override mechanism and lets the Restore path put the user's mute back cleanly once Solo/Focus ends.

### What is NOT extended

Per Martin's rule for live state (2026-04-18 brainstorm):

- **Plugin bypass / VST bypass** — user state, not touched.
- **ControllerMap macros pointing at inactive channels** — misconfiguration, not Solo's job.
- STRIP-Control JoystickUp channel selection already skips bypassed channels via `IsChannelActiveForLooper` — no change needed.

The override stops at `p_UserMute`.

## Affected Code

### `ApplySoloOverrides()` — ~line 11982

Both existing branches (Strict + Smart) gain one parameter write, directly before `Solo_NP_Overridden[ch] = true`:

```gpscript
idx = GetParamIdxByName(BLK_NoteProcessor[ch], "p_UserMute")
if idx > -1 then SetParameter(BLK_NoteProcessor[ch], idx, 0.0) end
```

A new third branch handles Focus-Mode survivors:

```gpscript
elsif isFocusArmed and not LooperSoloMute[ch] then
   // Focus survivor: keep audible despite prior UserMute
   idx = GetParamIdxByName(BLK_NoteProcessor[ch], "p_UserMute")
   if idx > -1 then SetParameter(BLK_NoteProcessor[ch], idx, 0.0) end
   Solo_NP_Overridden[ch] = true
end
```

The Focus branch applies **only** the UserMute override — it does **not** touch split, velocity or fade. Focus Mode is not a Solo; it does not claim "full keyboard freedom". The user's NP configuration stays intact.

`isFocusArmed` is passed as a Boolean parameter from `UpdateSoloMuteState()`.

### `RestoreSoloOverrides()` — ~line 11953

After the existing 8 restore writes, add:

```gpscript
idx = GetParamIdxByName(BLK_NoteProcessor[ch], "p_UserMute")
if idx > -1 then SetParameter(BLK_NoteProcessor[ch], idx, IntToFloat(Mem_UserMute[ch])) end
```

Restore already writes all 8 NP params from `Mem_*` even if only UserMute was overridden. This is a no-op for unchanged values — no harm, keeps the code path singular.

### `UpdateSoloMuteState()` — ~line 12192

The gate for `ApplySoloOverrides()` changes from

```gpscript
if anyStrict or anySmart then
   ApplySoloOverrides()
end
```

to

```gpscript
if isFocusArmed or anyStrict or anySmart then
   ApplySoloOverrides(isFocusArmed)
end
```

`RestoreSoloOverrides()` is still called first (clean slate), same as before.

### Strip UserMute toggle — ~line 13158

Current:

```gpscript
Strip_ThemeIdx == 5  Do // User Mute
   currentVal = Mem_UserMute[ch]
   newVal = 1 - currentVal
   Mem_UserMute[ch] = newVal
   idx = GetParamIdxByName(BLK_NoteProcessor[ch], "p_UserMute")
   if idx > -1 then SetParameter(BLK_NoteProcessor[ch], idx, IntToFloat(newVal)) end
   paramName = "User Mute"
```

Add one line:

```gpscript
   SoloMuteStateDirty = true
```

**Rationale**: If user toggles UserMute via Strip during an active policy, their intention must be stored in `Mem_UserMute` (so Restore on policy exit applies it) — but `p_UserMute` should be re-forced to 0 on the next tick so the live override holds. Without the dirty flag, `ApplySoloOverrides` does not re-run and the user's toggle silences the channel despite active Solo/Focus.

The same signal should eventually be added to Injection-UI and MIDI-CC paths for UserMute. **Deferred — not in this ticket.** Captured in "Follow-up".

## Semantics Table

| Scenario | `Mem_UserMute` | `p_UserMute` during policy | `p_UserMute` after policy exit |
|---|---|---|---|
| UserMuted, then Solo activates on same channel | 1 (unchanged) | 0 (forced) | 1 (restored — user mute back) |
| UserMuted, then Focus activates, channel is survivor | 1 (unchanged) | 0 (forced) | 1 (restored) |
| UserMuted, then Focus activates, channel is NOT survivor | 1 (unchanged) | 1 (unchanged — Focus mutes via p_SoloMute anyway) | 1 |
| Not UserMuted, Solo activates | 0 | 0 (idempotent) | 0 |
| During active Solo, user toggles UserMute on | 1 (written) | 0 (re-forced next tick via dirty flag) | 1 (now applies) |
| During active Solo, user toggles UserMute off | 0 (written) | 0 (idempotent) | 0 |
| Focus + Strict both active, survivor in both | 1 | 0 (Strict branch writes) | 1 |

## Restore Order on Policy Exit

`RestoreSoloOverrides()` runs **first** in every `UpdateSoloMuteState()` cycle (clean slate). On policy exit:

1. `Mem_SoloStrict/Smart` arrays are cleared (or Focus toggles off).
2. Next tick fires (`SoloMuteStateDirty = true`).
3. `UpdateSoloMuteState` computes `anyStrict = false`, `anySmart = false`, `isFocusArmed = false`.
4. `LooperSoloMute[]` stays default (all false).
5. `RestoreSoloOverrides()` walks all channels with `Solo_NP_Overridden[ch] = true` and writes `Mem_*` back — including `Mem_UserMute`.
6. `ApplySoloOverrides()` does **not** run (gate is false).

Result: `p_UserMute` matches `Mem_UserMute` again. User's intention is back in effect.

## Song Load Safety Net

Per existing spec: `RestoreSoloOverrides()` runs during snapshot restore after `Mem_*` arrays are populated. No change needed — the new `p_UserMute` restore line is part of the same loop and benefits from the same ordering.

## Version Bump

Every edit to `Global Rackspace.gpscript` bumps `SCRIPT_VERSION` so the runtime log proves which build GP is running. (Martin's standing rule — feedback_gpscript_script_version_bump.)

## Out of Scope (Parked)

- **Strict/Smart mutual coexistence** ("Befund 2" from the brainstorm). Current code blocks Smart-Solo channels when any Strict-Solo is active. Martin's new definition — "Solo channels of any flavor don't mute each other" — is consistent and feasible but opens follow-up questions about the Smart "shared input+zone" peer logic. Parked until it bites in practice.
- **Injection-UI and MIDI-CC paths for UserMute toggle** — the same `SoloMuteStateDirty = true` signal should be added wherever `Mem_UserMute` / `p_UserMute` gets written. To be audited in a follow-up pass.
- **Bypass/VST activation on Solo** — explicitly declined by Martin: user state, not Solo's job.

## Forward Declaration Order

No change. `RestoreSoloOverrides` and `ApplySoloOverrides` stay where they are (~11953, ~11982). The new Focus branch is added inside the existing `ApplySoloOverrides` function body; its signature grows by one Boolean parameter.

## Documentation

`docs/SoloMuteEngine.md` gets three updates:

1. "Modes → Strict Solo" and "Modes → Smart Solo": add "**UserMute Override**: `p_UserMute → 0` while this mode is active on the channel; `Mem_UserMute` preserved; restored on mode exit."
2. "Modes → Focus Mode": add "**UserMute Override**: survivors (`LooperSoloMute[ch] == false`) get `p_UserMute → 0` while Focus is armed; `Mem_UserMute` preserved; restored on Focus off."
3. "State Storage" table: no change to `Solo_NP_Overridden` row (still "Reset on load"). It now additionally tracks UserMute overrides, but that's internal.
