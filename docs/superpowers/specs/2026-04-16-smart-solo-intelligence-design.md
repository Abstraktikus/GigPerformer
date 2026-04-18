# Smart Solo Intelligence Upgrade

**Date:** 2026-04-16
**Status:** Design approved
**Scope:** `ApplySoloOverrides()` + `RestoreSoloOverrides()` in Global Rackspace.gpscript

## Problem

Smart Solo currently only mutes competing channels via `p_SoloMute`. It does not adjust
NoteProcessor parameters that restrict the soloed channel's playability:

- **Keyboard Split** (`p_SplitMin`/`p_SplitMax`) limits the note range — the solo channel
  can't use the full keyboard even though competing channels are muted.
- **Velocity Range** (`p_VelRangeActive`, `p_MinVel`, `p_MaxVel`, `p_VelRangeFade`) filters
  dynamics — soft or hard playing gets swallowed.
- **Keyboard Fades** (`p_FadeIn`/`p_FadeOut`) taper volume at range edges — unnecessary
  when the competing channel is muted.

Strict Solo has the same gap: it mutes all other channels but leaves NP restrictions active
on the soloed channel.

## Design Decision: Option D — No Split Intervention Without Mem_Manual

The system only adjusts keyboard split when the user has explicitly assigned Manual zones
(`Mem_Manual[ch]` = 1 for Upper, 2 for Lower). If `Mem_Manual[ch] == 0` (None), no split
adjustment is made. Rationale: without explicit zone assignment, the system cannot know
*why* a SplitMax < 127 is set — it could be an intentional effect, not a split boundary.

## Design Decision: Restore via Mem_-Arrays (Option A)

The existing `Mem_MinNote[ch]`, `Mem_NP_VelRangeActive[ch]`, etc. arrays — populated at
Song Load — serve as the backup. Solo logic writes directly to the NoteProcessor but
**never** modifies the Mem_-arrays. On deactivation, Mem_-values are written back.
No additional backup arrays needed. No UI toggle — the behavior is automatic.

## Affected NoteProcessor Parameters (8 total)

| Parameter | Mem_-Array | Default |
|---|---|---|
| `p_SplitMin` | `Mem_MinNote[ch]` | 0 (C0) |
| `p_SplitMax` | `Mem_MaxNote[ch]` | 127 (G7) |
| `p_FadeIn` | `Mem_FadeIn[ch]` | 10 |
| `p_FadeOut` | `Mem_FadeOut[ch]` | 10 |
| `p_VelRangeActive` | `Mem_NP_VelRangeActive[ch]` | 0 (off) |
| `p_MinVel` | `Mem_NP_MinVel[ch]` | 0 |
| `p_MaxVel` | `Mem_NP_MaxVel[ch]` | 127 |
| `p_VelRangeFade` | `Mem_NP_VelRangeFade[ch]` | 0 (off) |

## New Variable

```gpscript
Solo_NP_Overridden : Boolean Array = [false x 16]
```

Placed with the other Solo arrays (~line 629). Tracks which channels currently have
NP overrides active so `RestoreSoloOverrides()` knows what to restore.

## New Functions

### RestoreSoloOverrides()

Called **first** in every Phase 4 cycle (clean-slate principle).

```
For ch = 0..15:
   If Solo_NP_Overridden[ch]:
      Write Mem_-values back to NoteProcessor (all 8 parameters)
      Solo_NP_Overridden[ch] = false
```

### ApplySoloOverrides()

Called after RestoreSoloOverrides when any solo is active.

#### Strict Solo

For every channel with `Mem_SoloStrict[ch] == 1`:

```
p_SplitMin       → 0
p_SplitMax       → 127
p_FadeIn         → 0
p_FadeOut        → 0
p_VelRangeActive → 0
p_MinVel         → 0
p_MaxVel         → 127
p_VelRangeFade   → 0
Solo_NP_Overridden[ch] = true
```

Full keyboard, no velocity filter, no fades. The instrument plays alone.

#### Smart Solo

For every channel with `Mem_SoloSmart[ch] == 1`:

**Step 1 — Velocity restrictions removed (always):**

```
p_VelRangeActive → 0
p_MinVel         → 0
p_MaxVel         → 127
p_VelRangeFade   → 0
```

**Step 2 — Split adjustment (only if Mem_Manual[ch] is set):**

- **`Mem_Manual[ch] == 0` (None):** No split intervention. Only velocity removed.

- **`Mem_Manual[ch] == 1` (Upper):**

  1. Find `lowerGrenze`: scan all channels where `Mem_Manual[k] == 2` (Lower) AND
     channel k is NOT muted by p_SoloMute (i.e. `LooperSoloMute[k] == false`).
     Take the **highest** `Mem_MaxNote[k]` found.

  2. Three cases:

     **No active Lower found:**
     ```
     p_SplitMin = 0, p_SplitMax = 127, p_FadeIn = 0, p_FadeOut = 0
     ```
     Full keyboard free.

     **Upper SplitMin >= lowerGrenze** (no overlap — standard split):
     ```
     p_SplitMin = lowerGrenze, p_SplitMax = 127, p_FadeIn = 0, p_FadeOut = 0
     ```
     Upper starts where Lower ends. No fade needed at the boundary.

     **Upper SplitMin < lowerGrenze** (intentional overlap — crossfade zone):
     ```
     p_SplitMin = unchanged, p_SplitMax = 127, p_FadeIn = unchanged, p_FadeOut = 0
     ```
     The overlap and its FadeIn are intentional (smooth blend into Lower).
     Only SplitMax opens to full range and FadeOut is removed (nothing above).

- **`Mem_Manual[ch] == 2` (Lower):**
  ```
  p_SplitMin = unchanged, p_SplitMax = unchanged, p_FadeIn = 0, p_FadeOut = 0
  ```
  Keyboard split stays (user requirement). Only fades removed.

In all Smart Solo cases: `Solo_NP_Overridden[ch] = true`.

## Integration into UpdateSoloMuteState

```
[existing] Phase 1: Gather status (anyStrict, anySmart, looper)
[existing] Phase 2: Focus / Strict / Smart → LooperSoloMute[] berechnen
[existing] Phase 3: p_SoloMute an NoteProcessor schreiben
[NEW]      Phase 4: RestoreSoloOverrides()                    // always: clean slate
                    if anyStrict or anySmart then
                       ApplySoloOverrides(anyStrict, anySmart)
                    end
[existing] Phase 5: ExecuteSmartBypass / ApplyVstFocusBypass / EvaluateSmartAdapt
```

Phase 4 comes **after** p_SoloMute (so we know which Lower channels are muted)
and **before** SmartBypass (so bypass logic sees the correct NP state).

## Forward Declaration Order

Both functions must be defined before `UpdateSoloMuteState()` (~line 11832).
`RestoreSoloOverrides` before `ApplySoloOverrides` (in case Apply ever calls Restore):

```
[existing]  EvaluateAutoSysMode           (~11652)
[existing]  ActivateOverlay / Deactivate  (~11712)
[NEW]       RestoreSoloOverrides
[NEW]       ApplySoloOverrides
[existing]  UpdateSoloMuteState           (~11832)
```

## Safety Net: Song Load

`RestoreSoloOverrides()` is called during the snapshot restore phase, after Mem_-arrays
are populated. This prevents ghost overrides from a previous song leaking into a new one.

## Lower-Grenze Search — Active Lower Definition

A Lower channel contributes to `lowerGrenze` only when:

1. `Mem_Manual[k] == 2` (explicitly marked as Lower)
2. `LooperSoloMute[k] == false` (not muted by the current solo evaluation)

This ensures that if Smart Solo mutes a Lower (because it shares input+zone with the
Upper), its split boundary is ignored — it's not playing, so its range is irrelevant.

## Edge Cases

| Scenario | Behavior |
|---|---|
| Lower with SplitMax = 127 (full keyboard) | Upper SplitMin is always < 127 → overlap rule: Split + FadeIn unchanged |
| Multiple Lowers with different SplitMax | Highest SplitMax wins (most conservative boundary) |
| Smart Solo on a channel with Mem_Manual = 0 | Only velocity removed, no split change |
| Strict→Smart switch on same channel | Mutual exclusion + dirty flag → UpdateSoloMuteState runs fresh → Restore (clean slate) then Apply (new mode) |
| Solo active during Song Load | Safety-net RestoreSoloOverrides clears all overrides before new song state |
| User changes NP param during active Solo | Mem_-array gets updated; on Restore the new value is written back (change persists) |
