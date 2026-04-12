# GigPerformer Project — Instructions for Claude

## Project Overview

Live performance system built on Gig Performer with a ~16k-line GPScript Global Rackspace script. Hardware abstraction layer (HAL) for Yamaha Genos2 + Arturia MiniLab3. Features include layer-based controller mapping, overlay trigger engine, smart solo, timeline recording, LFO engine, looper, and arranger integration.

## Workflow Preferences

### Implementation Approach
- **Full risk, no backward compatibility.** When implementing changes: Big Bang. No legacy code, no v1/v2 naming, no migration paths.
- **No interruptions during implementation.** Brainstorm and design first, then implement all plans sequentially without stopping for questions.
- **Subagent-driven development.** Use subagents for implementation tasks. Each subagent gets the full GPScript checklist (see below).
- **E2E test at the end.** GPScript has no external compiler. All testing happens in Gig Performer after all code is written. Bundle implementation, then test.
- **Clean code only.** No legacy stubs, no "kept for reference" functions, no v2 suffixes. Rename and delete immediately.

### Commit Style
- Bump `SCRIPT_VERSION` on every edit to `Global Rackspace.gpscript`
- Frequent, focused commits (one logical change per commit)
- Commit message format: `feat/fix/refactor(scope): description`

## GPScript Compilation Checklist

**MANDATORY: Verify ALL of the following before writing ANY GPScript code.**

### 1. var Declarations
- ALL `var` lines MUST be at the VERY TOP of the function, before ANY executable statement
- No `var` inside `if`, `elsif`, `else`, `For`, `While`, or `Select` blocks
- Multiple `var` lines are OK but must be CONTIGUOUS (no assignments between them)
- Inline init on same line as statement is executable: use `var x : Double = 0.0` in the var block, not `var x : Double; x = 0.0`

### 2. Forward Declarations
- Every function called MUST be defined EARLIER in the file (lower line number)
- **Before adding a call to FunctionX: grep for `Function FunctionX` and verify its line number is LOWER than the caller**
- If circular dependency: use a deferred pattern (dirty flag + TimerTick dispatch, or PendingIdx variable)
- Known deferred patterns in codebase:
  - `SoloMuteStateDirty` — defers `UpdateSoloMuteState()` to TimerTick
  - `PendingSysActionIdx` — defers `FireSystemAction()` to caller after `ExecuteHardwareMacro` returns

### 3. For/While Loops
- Every `For` MUST have `Do`: `For i = 0; i < N; i = i + 1 Do ... End`
- Every `While` MUST have `Do`: `While condition Do ... End`

### 4. API Names — NEVER Guess, Always Grep
- No `GetPluginName()` — use `GetPluginInfo(block, 0)`
- No `Upper()` — use `MyToUpper()` (custom function at line ~1489)
- No `Mod` operator — use `val - (div * divisor)`
- No `Result` — use `result` (lowercase)
- No `Left()`, `Mid()`, `Pos()` — use `CopySubstring()`, `IndexOfSubstring()`
- No `Trim()` — use `TrimString()`
- No `SplitString` delimiter other than what's tested — check existing usage
- **Variable names:** GREP `Mem_NP_` to find the actual array name before using
- **Function names:** GREP `Function <Name>` to verify it exists and is correctly spelled
- **Parameter names (p_*):** GREP `InjectNPToggle` calls to find the real NoteProcessor parameter name
- **Widget names:** GREP the widget declaration in SECTION 5 before using `SetWidgetValue`

### 5. Select/Do Blocks
- No multi-line code blocks inside `Select ... Do` handlers
- If you need `if/end` logic inside a case, use `if/elsif/end` instead of `Select`

### 6. Other GPScript Rules
- No early return — use `if/else` to control flow
- All `Double` variables must be initialized with `= 0.0`
- `block` is a reserved word — do not use as variable name
- String literals: no `\u` or `\n` escapes — use heredoc `<<< >>>` constants (like `NEW_LINE`)
- `Returns`-typed functions cannot be called as statements — capture into a variable

## File Structure

| File | Purpose |
|---|---|
| `Global Rackspace.gpscript` | Main script (~16k lines), 26 sections |
| `Note Prozessor.gpscript` | Per-channel note processing scriptlet |
| `examples/DeviceConfig.txt` | Hardware abstraction config (devices, controls, layer switches) |
| `examples/ControllerMaps.txt` | Unified controller maps with `[Map:Default]` inheritance |
| `docs/superpowers/specs/` | Design specifications |
| `docs/superpowers/plans/` | Implementation plans |
| `docs/MACROS.md` | User-facing macro/controller map reference |

## Section Order in Global Rackspace.gpscript

Functions must respect this order (forward declarations). Key sections:

1. SECTION 1-12: Variables (single `Var` block)
2. SECTION 13: Core Utilities (Trace, Wait, index helpers)
3. SECTION 14: HAL Runtime (ParseDeviceConfig, Layer State Machine, Device Lookup)
4. SECTION 15: MIDI & Channel Engine
5. SECTION 16: Display Engine
6. SECTION 17: Controller Map Engine (Parser, LoadControllerMap, Display)
7. SECTION 18: Looper Engine
8. SECTION 19: Timeline Engine (RecordTimelineEvent, FireTimelineEvent)
9. SECTION 20: VST Replacer
10. SECTION 21: Orchestration (Overlay Engine, UpdateSoloMuteState, SmartBypass)
11. SECTION 22: Hardware Input (FireSystemAction, ExecuteHardwareMacro, ProcessHardwareCC)
12. SECTION 23: Song & Snapshot Management
13. SECTION 25-26: Callbacks (On WidgetValueChanged, On Song, On TimerTick, On SysexEvent)

## Testing

- No external compiler exists for GPScript
- Copy config files to gig file directory, load in GP, check script console
- Look for `SCRIPT VERSION <version> booting` to confirm correct build is running
- Use `Trace()` wrapped in `if DebugMode then` for diagnostics
