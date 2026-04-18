# Solo & Mute Engine

The Solo & Mute Engine controls which channels are audible during live performance.
It operates at the NoteProcessor level (per-channel MIDI filtering) and at the VST
level (plugin bypass). Three solo modes and one mute mode are available, with a
strict priority hierarchy.

## Priority Hierarchy

```
Focus Mode (ABSOLUTE BOSS)
  └─ Strict Solo
       └─ Smart Solo
            └─ User Mute (always applied independently)
```

Only one solo tier is active at a time. Focus Mode overrides both solo types.
User Mute is independent — a channel can be muted regardless of solo state.

## Modes

### Focus Mode (`BTN_Focus_Mode`)

Automatic conflict resolution tied to the active SYS-MODE:

- **LOOPER MODE (1):** Mutes everything not in OutputScope and not currently playing
- **VOICE SELECTOR (0):** Auto-mutes channels sharing RECH inputs with the focused VST

Does not use `Mem_SoloStrict`/`Mem_SoloSmart`. Overrides both.

**UserMute Override (since v2026-04-18.001):**
Survivors — channels where `LooperSoloMute[ch] == false` under an armed Focus — get
`p_UserMute → 0` for the duration of Focus Mode. `Mem_UserMute` is preserved and
restored on Focus off. No NP parameters (split, velocity, fades) are touched —
Focus does not claim "full keyboard freedom", only live-safe audibility.

### Strict Solo (`Mem_SoloStrict[ch]`)

Binary exclusion: only channels with `Mem_SoloStrict[ch] == 1` play. All others are
muted via `p_SoloMute`. Mutually exclusive with Smart Solo on the same channel.

**NP Override (since v2026-04-16.012):**
All NoteProcessor restrictions are lifted on the soloed channel:
- `p_SplitMin → 0`, `p_SplitMax → 127` (full keyboard)
- `p_FadeIn → 0`, `p_FadeOut → 0` (no fades)
- `p_VelRangeActive → 0`, `p_MinVel → 0`, `p_MaxVel → 127`, `p_VelRangeFade → 0`

**UserMute Override (since v2026-04-18.001):**
- `p_UserMute → 0` for the duration of Strict Solo; `Mem_UserMute` preserved and
  restored on Solo off. Live-safety: a soloed channel is unconditionally audible.

The instrument plays alone with full freedom.

### Smart Solo (`Mem_SoloSmart[ch]`)

Intelligent muting: only channels sharing **both** the same RECH input row **and** the
same Manual zone (`Mem_Manual`: 0=None, 1=Upper, 2=Lower) are muted. Channels on
different inputs or different zones continue playing.

**NP Override (since v2026-04-16.012):**

*Velocity — always removed:*
- `p_VelRangeActive → 0`, `p_MinVel → 0`, `p_MaxVel → 127`, `p_VelRangeFade → 0`

*Keyboard Split — only when `Mem_Manual[ch]` is set:*

| Zone | Behavior |
|---|---|
| **None (0)** | No split intervention. Only velocity removed. |
| **Upper (1)** | Searches for the highest `SplitMax` among active (non-muted) Lower channels. Three sub-cases — see below. |
| **Lower (2)** | Split stays. `FadeIn` and `FadeOut` removed. |

**Upper sub-cases (Lower-Grenze search):**

| Condition | SplitMin | SplitMax | FadeIn | FadeOut |
|---|---|---|---|---|
| No active Lower found | 0 | 127 | 0 | 0 |
| Upper SplitMin >= lowerGrenze (no overlap) | lowerGrenze | 127 | 0 | 0 |
| Upper SplitMin < lowerGrenze (intentional overlap) | *unchanged* | 127 | *unchanged* | 0 |

The overlap case preserves the crossfade zone: the Upper's SplitMin and FadeIn stay
intact because the blend into the Lower range is intentional.

**UserMute Override (since v2026-04-18.001):**
- `p_UserMute → 0` for the duration of Smart Solo; `Mem_UserMute` preserved and
  restored on Solo off. Same live-safety rule as Strict.

### User Mute (`Mem_UserMute[ch]`)

Simple per-channel mute via `p_UserMute` on the NoteProcessor. Independent of solo
state — a channel can be both soloed and muted. Applied directly during snapshot load.

## State Storage

| Array | Type | Size | Persisted to .ini | Restored on Load |
|---|---|---|---|---|
| `Mem_SoloStrict[ch]` | Integer (0/1) | 16 | Yes (delta) | Reset to 0 |
| `Mem_SoloSmart[ch]` | Integer (0/1) | 16 | Yes (delta) | Reset to 0 |
| `Mem_UserMute[ch]` | Integer (0/1) | 16 | Yes (delta) | Reset to 0 |
| `Mem_Manual[ch]` | Integer (0/1/2) | 16 | Yes (delta) | Restored |
| `LooperSoloMute[ch]` | Boolean | 16 | No (transient) | — |
| `Solo_NP_Overridden[ch]` | Boolean | 16 | No (transient) | Reset on load |

Mutual exclusion: activating Strict on a channel forces Smart to 0, and vice versa.
Controlled by `ActivateOverlay()` / `DeactivateOverlay()` and the Strip Control theme
toggles.

## NP Override Restore Mechanism

The `Mem_*` arrays (populated at Song Load) serve as the backup. Solo overrides write
directly to NoteProcessor parameters but **never** modify `Mem_*` arrays. On
deactivation, `RestoreSoloOverrides()` writes `Mem_*` values back — including
`Mem_UserMute`, which is restored alongside the 8 NP params.

```
UpdateSoloMuteState()
  Phase 1: Gather status (anyStrict, anySmart, looper, isFocusArmed)
  Phase 2: Focus / Strict / Smart → LooperSoloMute[] calculated
  Phase 3: p_SoloMute written to NoteProcessors
  Phase 4: RestoreSoloOverrides()              (always — clean slate)
           ApplySoloOverrides(isFocusArmed)    (if isFocusArmed or anyStrict or anySmart)
  Phase 5: ExecuteSmartBypass / ApplyVstFocusBypass / EvaluateSmartAdapt
```

Phase 4 runs **after** p_SoloMute (so Lower mute state is known for the boundary
search) and **before** SmartBypass (so bypass logic sees the correct NP state).
`ApplySoloOverrides` now also runs under Focus Mode — but only to override
`p_UserMute` on Focus survivors, not to touch split/velocity/fades.

## Trigger Flow

```
User action (Strip toggle, Overlay, Button)
  → Mem_SoloStrict/Smart[ch] = 1 or 0
  → SoloMuteStateDirty = true
  → Next TimerTick: UpdateSoloMuteState()
```

## Key Functions

| Function | Location | Purpose |
|---|---|---|
| `UpdateSoloMuteState()` | Section 17 | Master orchestrator — 5 phases |
| `ApplySoloOverrides()` | Section 17 | Sets NP params for Strict/Smart |
| `RestoreSoloOverrides()` | Section 17 | Writes Mem_* back to NoteProcessor |
| `ActivateOverlay(func, ch)` | Section 17 | Sets Mem_Solo*, enforces mutual exclusion |
| `DeactivateOverlay(func, ch)` | Section 17 | Clears Mem_Solo* |
| `ExecuteSmartBypass()` | Section 16 | VST-level bypass based on routing |
| `ApplyVstFocusBypass()` | Section 17 | Focus-mode VST bypass |
| `EvaluateAutoSysMode()` | Section 21 | Auto-selects SYS-MODE (pauses when SystemModeActive) |

## Related: VST Bypass System

Separate from the NoteProcessor muting, the bypass system works at the VST plugin level:

- **ExecuteSmartBypass():** Activates/deactivates VSTs based on RECH routing
- **ApplyVstFocusBypass():** Temporarily bypasses VSTs competing for inputs with the focused VST
- **Mem_ManualVSTBypass[vst]:** Per-VST manual override (Explicit Branch)
- **Mem_ScopeBypassConfigured[ch]:** Tracks if channel entered Explicit Branch
- **Focus_Temp_Bypassed[vst]:** Transient flag for focus-mode bypass (auto-restored on deactivation)
