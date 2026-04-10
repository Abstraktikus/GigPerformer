# Chord Latch Auto-Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-release a chord-mode latched root note after 4 beats of hardware-note silence (BPM-scaled, with 4000ms fallback), so the latch stops droning after a song ends.

**Architecture:** GPScript scriptlets only support `On MidiEvent` and `On ParameterValueChanged` — no timer or beat callbacks. The Global Rackspace has both `On BeatChanged` and sees every hardware note via `ProcessHardwareNote`. All timing logic therefore lives in GR; the Note Prozessor scriptlet exposes a single `p_LatchRelease` trigger parameter that GR sets when a release is due. A single global "last note-on" timestamp captures the "silence everywhere" condition correctly across multi-channel play.

**Tech Stack:** GPScript (Gig Performer 5.x)

**Spec:** `docs/superpowers/specs/2026-04-10-latch-auto-release-design.md`

---

## Sequencing

Feature A (Note Prozessor) goes first because the new `p_LatchRelease` parameter is the interface GR depends on. Feature B (Global Rackspace) adds the timing infrastructure and hooks that fire the trigger.

Each task leaves the codebase compilable. Between Task 3 (NP parameter + handler committed) and Task 7 (GR fires the trigger), the trigger exists but nothing sets it — that's fine, it stays at 0 and is a no-op.

---

## FEATURE A — Note Prozessor (p_LatchRelease trigger)

### Task 1: Add `p_LatchRelease` parameter

**Files:**
- Modify: `Note Prozessor.gpscript:32` (add `p_LatchRelease` right after `p_LatchMode`)

- [ ] **Step 1: Read the current Var block location**

Run: `Grep pattern "p_LatchMode" path "Note Prozessor.gpscript" -n`
Expected: one match at line 32 showing `   p_LatchMode    : Parameter 0 .. 1 = 0 `

- [ ] **Step 2: Insert the new parameter**

Change `Note Prozessor.gpscript:31–33` from:

```gpscript
   // --- 4. Chord Detection Parameter ---
   p_ChordMode    : Parameter 0 .. 1 = 0 
   p_LatchMode    : Parameter 0 .. 1 = 0 
```

To:

```gpscript
   // --- 4. Chord Detection Parameter ---
   p_ChordMode    : Parameter 0 .. 1 = 0 
   p_LatchMode    : Parameter 0 .. 1 = 0 
   p_LatchRelease : Parameter 0 .. 1 = 0   // Trigger from GR timer: release latched chord root
```

- [ ] **Step 3: Verify by reading lines 28–40**

Read `Note Prozessor.gpscript` lines 28–40 and confirm `p_LatchRelease` appears directly after `p_LatchMode`, with 3-space indentation matching the surrounding lines.

- [ ] **Step 4: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "$(cat <<'EOF'
feat(np): add p_LatchRelease trigger parameter for auto-release

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add `p_LatchRelease` handler

**Files:**
- Modify: `Note Prozessor.gpscript:142` (add new handler after the SoloMute/UserMute handler, before the pitch/quantizer Panic handler at :144)

- [ ] **Step 1: Read the handler area**

Run: Read `Note Prozessor.gpscript` lines 140–148 to confirm the existing structure.

Expected surrounding:
```
On ParameterValueChanged matching p_SoloMute, p_UserMute
   if Round(p_SoloMute) == 1 or Round(p_UserMute) == 1 then ExecutePanic() end
End

// Hänger-Vermeidung: Wenn man aktiv am Pitch oder Quantizer schraubt
On ParameterValueChanged matching p_Octaver, p_OctLow, ...
```

- [ ] **Step 2: Insert the new handler**

Change `Note Prozessor.gpscript:140–144` from:

```gpscript
On ParameterValueChanged matching p_SoloMute, p_UserMute
   if Round(p_SoloMute) == 1 or Round(p_UserMute) == 1 then ExecutePanic() end
End

// Hänger-Vermeidung: Wenn man aktiv am Pitch oder Quantizer schraubt
```

To:

```gpscript
On ParameterValueChanged matching p_SoloMute, p_UserMute
   if Round(p_SoloMute) == 1 or Round(p_UserMute) == 1 then ExecutePanic() end
End

// Auto-release latched chord root when the GR timer fires the trigger.
// Guard is ChordMode + lastSentRoot only (not LatchMode) so the release
// still fires if the user toggled Latch off while a root was still held.
On ParameterValueChanged matching p_LatchRelease
   if Round(p_LatchRelease) == 1 then
       if Round(p_ChordMode) == 1 and lastSentRoot != -1 then
           StopOutNote(lastSentRoot, activeChannel)
           lastSentRoot = -1
       end
       p_LatchRelease = 0
   end
End

// Hänger-Vermeidung: Wenn man aktiv am Pitch oder Quantizer schraubt
```

- [ ] **Step 3: Verify by reading lines 138–160**

Read `Note Prozessor.gpscript` lines 138–160 and confirm:
- The new handler is present with the full body
- The trailing `End` is there
- The pitch/quantizer comment and its handler still follow
- No stray blank lines or missing `end`

- [ ] **Step 4: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "$(cat <<'EOF'
feat(np): add p_LatchRelease handler to stop latched chord root

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add `p_LatchRelease` to factory reset

**Files:**
- Modify: `Note Prozessor.gpscript:158` (existing factory reset line for chord-mode parameters)

- [ ] **Step 1: Read the factory reset line**

Run: Read `Note Prozessor.gpscript` lines 156–162 to see the current factory reset block.

Expected around line 158:
```gpscript
      p_ChordMode = 0; p_LatchMode = 0; p_Engine = 0; p_MuteOriginal = 0; p_MinKeys = 1; p_OctaveOffset = 0 
```

- [ ] **Step 2: Add `p_LatchRelease = 0` to the reset line**

Change `Note Prozessor.gpscript:158` from:

```gpscript
      p_ChordMode = 0; p_LatchMode = 0; p_Engine = 0; p_MuteOriginal = 0; p_MinKeys = 1; p_OctaveOffset = 0 
```

To:

```gpscript
      p_ChordMode = 0; p_LatchMode = 0; p_LatchRelease = 0; p_Engine = 0; p_MuteOriginal = 0; p_MinKeys = 1; p_OctaveOffset = 0 
```

- [ ] **Step 3: Verify**

Read `Note Prozessor.gpscript` line 158 and confirm `p_LatchRelease = 0` is present between `p_LatchMode = 0` and `p_Engine = 0`.

- [ ] **Step 4: Commit**

```bash
git add "Note Prozessor.gpscript"
git commit -m "$(cat <<'EOF'
feat(np): reset p_LatchRelease in factory reset

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## FEATURE B — Global Rackspace (timer infrastructure)

### Task 4: Add `LatchTimeoutBeats` and `LatchTimeoutFallbackMs` constants

**Files:**
- Modify: `Global Rackspace.gpscript:43` (add new constants right after `MAX_MACROS`)

- [ ] **Step 1: Read the constant block**

Run: Read `Global Rackspace.gpscript` lines 41–46 to see the current constants.

Expected:
```gpscript
   MAX_LINKS : Integer = 512
   MAX_VSTS : Integer = 10
   MAX_MACROS : Integer = 256
   
   // --- Global Default Macro Assignments (start indices for 16-element blocks) ---
```

- [ ] **Step 2: Insert the two new constants**

Change `Global Rackspace.gpscript:43–45` from:

```gpscript
   MAX_MACROS : Integer = 256
   
   // --- Global Default Macro Assignments (start indices for 16-element blocks) ---
```

To:

```gpscript
   MAX_MACROS : Integer = 256

   // --- Latch auto-release tunables (see docs/superpowers/specs/2026-04-10-latch-auto-release-design.md) ---
   LatchTimeoutBeats       : Double = 4.0      // Auto-release latched chord root after N beats of silence
   LatchTimeoutFallbackMs  : Double = 4000.0   // Used when GetBPM() <= 1.0

   // --- Global Default Macro Assignments (start indices for 16-element blocks) ---
```

- [ ] **Step 3: Verify by reading lines 41–52**

Read `Global Rackspace.gpscript` lines 41–52 and confirm both new `Double` constants are present, correctly initialized, and placed between `MAX_MACROS` and `DEF_LOOPER_CH_MacroIdx`.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "$(cat <<'EOF'
feat(gr): add LatchTimeoutBeats and LatchTimeoutFallbackMs tunables

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Add `Latch_LastNoteOnTime` state variable

**Files:**
- Modify: `Global Rackspace.gpscript:384` (after the existing `HardwareSyncTimer, LastSysExSentTime, PostViewSwitchDelayTimer` line)

- [ ] **Step 1: Read the timer-state block**

Run: Read `Global Rackspace.gpscript` lines 382–390 to see the current state variable block.

Expected:
```gpscript
   StateResetTime : Double = 0.0 
   FaderSafetyTimer : Double = 0.0
   HardwareSyncTimer, LastSysExSentTime, PostViewSwitchDelayTimer : Double = 0.0
   
   LastReceivedBPM : Double = 0.0
```

- [ ] **Step 2: Insert the new state variable**

Change `Global Rackspace.gpscript:384–386` from:

```gpscript
   HardwareSyncTimer, LastSysExSentTime, PostViewSwitchDelayTimer : Double = 0.0
   
   LastReceivedBPM : Double = 0.0
```

To:

```gpscript
   HardwareSyncTimer, LastSysExSentTime, PostViewSwitchDelayTimer : Double = 0.0
   Latch_LastNoteOnTime : Double = 0.0   // TimeSinceStartup of most recent hardware note-on; 0 = disarmed
   
   LastReceivedBPM : Double = 0.0
```

- [ ] **Step 3: Verify**

Read `Global Rackspace.gpscript` lines 382–390 and confirm `Latch_LastNoteOnTime : Double = 0.0` is present with the sentinel comment.

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "$(cat <<'EOF'
feat(gr): add Latch_LastNoteOnTime state variable

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Update `ProcessHardwareNote` to stamp `Latch_LastNoteOnTime`

**Files:**
- Modify: `Global Rackspace.gpscript:10166` (`Function ProcessHardwareNote(m : NoteMessage)`)

- [ ] **Step 1: Read the function header area**

Run: Read `Global Rackspace.gpscript` lines 10166–10175 to see the function start.

Expected:
```gpscript
Function ProcessHardwareNote(m : NoteMessage)
    var chan : Integer = GetChannel(m)
    var noteNum : Integer = GetNoteNumber(m)
    var val : Double = 0.0
    var i : Integer
    
    // 1. LEARN MODE FOR NOTES
    if IsHardwareLearning then
```

- [ ] **Step 2: Insert the timestamp update before the LEARN MODE block**

Change `Global Rackspace.gpscript:10170–10172` from:

```gpscript
    var i : Integer
    
    // 1. LEARN MODE FOR NOTES
```

To:

```gpscript
    var i : Integer

    // Stamp the global last-note-on time for the latch auto-release timer.
    // Runs on every hardware note-on regardless of latch state — cheap.
    if IsNoteOn(m) then Latch_LastNoteOnTime = TimeSinceStartup() end

    // 1. LEARN MODE FOR NOTES
```

- [ ] **Step 3: Verify**

Read `Global Rackspace.gpscript` lines 10166–10180 and confirm:
- The new `if IsNoteOn(m) then Latch_LastNoteOnTime = TimeSinceStartup() end` line is inside the function
- It is placed AFTER the `var` declarations (required by GPScript) and BEFORE the existing `// 1. LEARN MODE FOR NOTES` comment
- The rest of the function is unchanged

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "$(cat <<'EOF'
feat(gr): stamp Latch_LastNoteOnTime on every hardware note-on

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Implement `CheckLatchTimeout` function

**Files:**
- Modify: `Global Rackspace.gpscript:13720` (insert new function in the blank line right before `On BeatChanged`)

- [ ] **Step 1: Read the area right before `On BeatChanged`**

Run: Read `Global Rackspace.gpscript` lines 13715–13730 to see the insertion point.

Expected:
```gpscript
            CurrentTriggerSource = "NONE"
        end
    end
End

On BeatChanged(bar : Integer, beat : Integer, subbeat : Integer)
   var e, ch, beatsPerBar : Integer
```

Note: The `End` at line 13720 closes the preceding function (some audio/looper handler), and `On BeatChanged` starts at 13722.

- [ ] **Step 2: Insert `CheckLatchTimeout()` between the preceding function and `On BeatChanged`**

Change `Global Rackspace.gpscript:13719–13722` from:

```gpscript
    end
End

On BeatChanged(bar : Integer, beat : Integer, subbeat : Integer)
```

To:

```gpscript
    end
End

// ---------------------------------------------------------
// LATCH AUTO-RELEASE (4-beat timeout + ms fallback)
// Called once per beat from On BeatChanged. Fires p_LatchRelease on every
// channel currently in Chord+Latch mode when no hardware note-on has been
// seen for LatchTimeoutBeats at the current BPM. Disarms itself after
// firing so subsequent beats are no-ops until the next note-on.
// ---------------------------------------------------------
Function CheckLatchTimeout()
   var currentBpm, msPerBeat, timeoutMs, idleMs : Double = 0.0
   var i, idx : Integer

   if Latch_LastNoteOnTime <= 0.0 then
       // Disarmed — nothing to check until next note-on
   else
       currentBpm = GetBPM()
       if currentBpm > 1.0 then
           msPerBeat = 60000.0 / currentBpm
           timeoutMs = msPerBeat * LatchTimeoutBeats
       else
           timeoutMs = LatchTimeoutFallbackMs
       end

       idleMs = TimeSinceStartup() - Latch_LastNoteOnTime
       if idleMs >= timeoutMs then
           For i = 0; i < 16; i = i + 1 Do
               if Mem_NP_ChordMode[i] == 1 and Mem_NP_LatchMode[i] == 1 then
                   idx = GetParamIdxByName(BLK_NoteProcessor[i], "p_LatchRelease")
                   if idx > -1 then SetParameter(BLK_NoteProcessor[i], idx, 1.0) end
               end
           End
           Latch_LastNoteOnTime = 0.0   // Disarm until next note-on
           if DebugMode then Trace("LATCH: auto-release fired after " + Round(idleMs) + "ms idle") end
       end
   end
End

On BeatChanged(bar : Integer, beat : Integer, subbeat : Integer)
```

- [ ] **Step 3: Verify**

Read `Global Rackspace.gpscript` lines 13718–13760 and confirm:
- The new `CheckLatchTimeout` function is syntactically complete (`Function ... End` pair)
- All `var` declarations at the top of the function
- The `if/else/end` chain balances
- `For/End` loop balances
- `On BeatChanged` still immediately follows the new function

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "$(cat <<'EOF'
feat(gr): add CheckLatchTimeout function for beat-driven auto-release

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Hook `CheckLatchTimeout()` into `On BeatChanged`

**Files:**
- Modify: `Global Rackspace.gpscript` — the final lines of the `On BeatChanged` body, just before its closing `End`

- [ ] **Step 1: Find the end of `On BeatChanged`**

Run: Grep `On BeatChanged` in `Global Rackspace.gpscript` with `-n` to find the start, then Read the function body to find its closing `End`. Post-Task-7 line numbers: `On BeatChanged` starts at ~13763 (shifted by the 41-line insertion in Task 7). The closing `End` is approximately 136 lines later.

Alternative: Grep for `TraceTimeDomains` — it's the last distinctive line inside `On BeatChanged` before the closing `End`.

- [ ] **Step 2: Insert the call right before `On BeatChanged`'s closing `End`**

Find this block inside `On BeatChanged` (the exact last few lines before its `End`):

```gpscript
   // ---> TIME DOMAIN TRACE <---
   if beat == 1 and subbeat == 0 then
       if DebugMode then TraceTimeDomains() end
   end
End
```

Change to:

```gpscript
   // ---> TIME DOMAIN TRACE <---
   if beat == 1 and subbeat == 0 then
       if DebugMode then TraceTimeDomains() end
   end

   // Latch auto-release check (once per beat). No-op if disarmed.
   CheckLatchTimeout()
End
```

- [ ] **Step 3: Verify**

Read the last 10 lines of `On BeatChanged` (grep for `CheckLatchTimeout` to locate) and confirm:
- The call is the last statement inside `On BeatChanged`
- It is BEFORE the `End` that closes `On BeatChanged`
- No stray characters or duplicate `End` keywords

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "$(cat <<'EOF'
feat(gr): hook CheckLatchTimeout into On BeatChanged

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Manual Verification (after all 8 tasks land)

These tests must be performed by the user in Gig Performer. They are documented here for completeness; they cannot be executed from this environment.

### Test 1: Basic auto-release at known BPM

1. Set GP transport BPM to 120.
2. Enable Chord mode and Latch mode on channel 1 (`BTN_Inject_NP_Root` and `BTN_Inject_NP_Hold`).
3. Play a 3-note chord on the hardware keyboard. Release the keys.
4. Expected: the emitted root note keeps playing.
5. Wait 4 beats at 120 BPM = 2000 ms.
6. Expected: the root note stops. If `DebugMode` is on, the trace log shows `LATCH: auto-release fired after ~2000ms idle`.

### Test 2: Rearm after release

1. Continuing from Test 1 (after the auto-release fired).
2. Play another chord on the same channel, release.
3. Expected: new root note is held and follows the same 4-beat release window.

### Test 3: Multi-channel "don't release while playing elsewhere"

1. Enable Chord+Latch on channel 1. Play and release a chord. Root is held.
2. Continuously play notes on a different MIDI channel / split / keyboard area (routed to channel 2, no chord mode).
3. Expected: channel 1's latched root stays held as long as any hardware note is active anywhere (every note-on resets `Latch_LastNoteOnTime`).
4. Stop playing everywhere.
5. Expected: after 4 beats of full silence, channel 1's root releases.

### Test 4: BPM scaling

1. Set BPM = 60. Play+latch a chord. Expected release after ~4000 ms.
2. Set BPM = 240. Play+latch a chord. Expected release after ~1000 ms.

### Test 5: Fallback when BPM unavailable

1. Set GP transport to a state where `GetBPM()` returns 0 (e.g., unplugged arranger, or explicitly disabled).
2. Play+latch a chord.
3. Expected: release after ~4000 ms (the fallback constant).

### Test 6: Idempotent firing

1. After a release fires in Test 1, let the GP transport keep running for 20 more beats without touching the keyboard.
2. Expected: no additional `LATCH: auto-release fired` traces (`Latch_LastNoteOnTime` is disarmed at 0.0 until the next note-on).

### Test 7: Factory reset hygiene

1. With a latched root currently held, trigger the factory reset on the channel (`p_FactoryReset = 1` or via the Reset button in Gig Performer).
2. Expected: latched root stops, `p_LatchRelease` stays at 0, no residual state.

### Test 8: Manual release paths unchanged

1. With a latched root held, press Panic, UserMute, or SoloMute.
2. Expected: immediate release, identical behavior to before this plan (manual paths are unchanged).
