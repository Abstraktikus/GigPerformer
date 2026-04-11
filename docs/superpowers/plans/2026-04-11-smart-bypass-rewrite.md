# Smart-Bypass Rewrite + BTN_Inject_Bypass Semantic Flip — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the bypass bug where manually clicking an input/output channel button with no Song.ini loaded leaves every NoteProcessor and VST bypassed, and unify the rule so the first VST listed in `HumanRoutingMap` activates by default while explicit `BTN_Inject_Bypass_*` configuration takes over per scope.

**Architecture:** Single-file change in `Global Rackspace.gpscript`. A new per-scope state array `Mem_ScopeBypassConfigured[16]` lets `ExecuteSmartBypass()` choose between a **Default Branch** (first routed VST active, rest bypassed) and an **Explicit Branch** (honor `Mem_ManualVSTBypass[]`) independently for each channel. The meaning of `BTN_Inject_Bypass_*` widgets is flipped: lit = VST active, dark = VST bypassed — widget polarity inverted, `HandleInjectBypassClick` polarity inverted, `[MAN OFF]` labels renamed to `[MANUAL]`. Two new call sites (`BTN_Ch*_In` and `BTN_Ch*_Out_*` handlers) trigger `ExecuteSmartBypass()` after RECH / OutputScope writes.

**Tech Stack:** GPScript 5.x (Gig Performer's built-in scripting language). No test framework — verification is via `if DebugMode then Trace(...)` statements that the user inspects in Gig Performer's script console after compile + load.

**Spec:** `docs/superpowers/specs/2026-04-11-lfo-looper-timeline-design.md` §4.

---

## File Structure

**Single file modified:** `Global Rackspace.gpscript`

All changes are localized to this file. No new files. Touched sections:

| Section | Lines | Change |
|---|---|---|
| SECTION 7 (Channel Memory) | ~446 | Add `Mem_ScopeBypassConfigured` declaration |
| SECTION 13 / Display Engine | ~2340 | Rename `[MAN OFF]` → `[MANUAL]` |
| SECTION 13 / Display Engine | ~2366-2370 | Flip widget polarity in `UpdateUsageLabelDisplay` |
| SECTION 18 / Looper Engine (misfiled, actually Smart Bypass) | 7867-7927 | Rewrite `ExecuteSmartBypass()` body |
| SECTION 15 / MIDI & Channel Engine | 7938-7980 | Rewrite `HandleInjectBypassClick()` polarity |
| SECTION 21 / Orchestration (AnalyzeChannel) | ~8056 | Rename `[MAN OFF]` → `[MANUAL]` |
| Bootstrap | ~12162 | Initialize `Mem_ScopeBypassConfigured` array |
| SECTION 25-26 / Callbacks | ~12652 | Add `ExecuteSmartBypass()` call after `SyncInputFeedback()` |
| SECTION 25-26 / Callbacks | ~12682 | Add `ExecuteSmartBypass()` call after `ScrollToCurrentChannel()` |
| Reset / Snapshot-Load paths | TBD (Task 6) | Clear `Mem_ScopeBypassConfigured` |

---

## Task 1: Add `Mem_ScopeBypassConfigured` state and bootstrap init

**Files:**
- Modify: `Global Rackspace.gpscript:446` (declaration in SECTION 7)
- Modify: `Global Rackspace.gpscript:~12162` (bootstrap init loop)

- [ ] **Step 1: Add the declaration in SECTION 7 (Channel Memory)**

Locate the line at approximately 446:

```gpscript
   Mem_ManualVSTBypass    : Boolean Array = [false, false, false, false, false, false, false, false, false, false]
```

Add the new array declaration immediately after it:

```gpscript
   Mem_ManualVSTBypass    : Boolean Array = [false, false, false, false, false, false, false, false, false, false]
   Mem_ScopeBypassConfigured : Boolean Array = [false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false]
```

Note the size — 16 entries, one per channel (not per VST).

- [ ] **Step 2: Initialize the array in the bootstrap loop**

Locate the existing per-channel init loop at approximately line 12162 in the Bootstrap:

```gpscript
   For i = 0; i < 16; i = i + 1 Do
      Mem_MinNote <-- 0.0
      Mem_MaxNote <-- 1.0
      Mem_FadeIn <-- 0
      Mem_FadeOut <-- 0
      Mem_NP_ChordMode <-- 0
```

Since `Mem_ScopeBypassConfigured` is declared with a literal initializer already, no bootstrap re-push is needed. Instead, add a separate reset loop right after the existing Mem_ loop to guarantee a clean state after any hot-reload:

```gpscript
   For i = 0; i < 16; i = i + 1 Do
      Mem_ScopeBypassConfigured[i] = false
   End
```

Place it immediately after the closing `End` of the main Mem_ init loop (after the line with `Mem_NP_OctHighOffset <-- 0`).

- [ ] **Step 3: Add DebugMode trace at init**

Immediately after the reset loop:

```gpscript
   if DebugMode then Trace("BYPASS: Mem_ScopeBypassConfigured initialized (all 16 channels = false)") end
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "feat(bypass): add Mem_ScopeBypassConfigured per-scope state array

Introduces a 16-element Boolean array that tracks, per channel scope,
whether the user has explicitly configured bypass state via the
BTN_Inject_Bypass_* widgets. False = Default Branch (first routed VST
active), true = Explicit Branch (honor Mem_ManualVSTBypass).

Bootstrap initializes all entries to false for a clean Default state."
```

---

## Task 2: Rewrite `ExecuteSmartBypass()` with per-scope two-branch logic

**Files:**
- Modify: `Global Rackspace.gpscript:7867-7927`

- [ ] **Step 1: Replace the entire `ExecuteSmartBypass()` function body**

The existing function spans lines 7867 to 7927 (everything from `Function ExecuteSmartBypass()` through the closing `End`). Replace it with:

```gpscript
// ---------------------------------------------------------
// REALTIME SMART BYPASS — per-scope two-branch logic
//
// Per channel with active RECH input, decide independently:
//   Mem_ScopeBypassConfigured[ch] = true  -> Explicit Branch:
//      honor Mem_ManualVSTBypass[] for every routed VST of this scope
//   Mem_ScopeBypassConfigured[ch] = false -> Default Branch:
//      activate only the first routed VST of HumanRoutingMap[ch],
//      bypass the rest
//
// Contributions from all active scopes are merged with OR logic:
// a VST is ultimately active iff at least one scope contributes
// "active" for it. This matches the pre-existing behaviour where
// any-routed-scope-needs-it wakes a VST.
// ---------------------------------------------------------
Function ExecuteSmartBypass()
   var ch, i, p, activeInputs, vstIdx : Integer
   var routeParts : String Array
   var vstShouldBeActive : Boolean Array = [false, false, false, false, false, false, false, false, false, false]

   // 1. Per channel: gather routing contributions
   For ch = 0; ch < 16; ch = ch + 1 Do
       activeInputs = 0
       For i = 0; i < 16; i = i + 1 Do
          if GetParameter(RECH, (i * 16) + ch) > 0.5 then activeInputs = activeInputs + 1 end
       End

       if activeInputs > 0 then
           // Channel is in use -> NoteProcessor on
           if IsPluginBypassed(BLK_NoteProcessor[ch]) then
               SetPluginBypassed(BLK_NoteProcessor[ch], false)
               if DebugMode then Trace("BYPASS: NP ch" + (ch+1) + " woken (active inputs=" + activeInputs + ")") end
           end

           routeParts = SplitString(HumanRoutingMap[ch], ",")

           if Mem_ScopeBypassConfigured[ch] then
               // EXPLICIT BRANCH: honor Mem_ManualVSTBypass for each routed VST
               For p = 0; p < Size(routeParts); p = p + 1 Do
                   vstIdx = StringToInt(TrimString(routeParts[p])) - 1
                   if vstIdx >= 0 and vstIdx < MAX_VSTS then
                       if not Mem_ManualVSTBypass[vstIdx] then
                           vstShouldBeActive[vstIdx] = true
                       end
                   end
               End
           else
               // DEFAULT BRANCH: first routed VST active, rest stay at their current contribution
               if Size(routeParts) > 0 then
                   vstIdx = StringToInt(TrimString(routeParts[0])) - 1
                   if vstIdx >= 0 and vstIdx < MAX_VSTS then
                       vstShouldBeActive[vstIdx] = true
                   end
               end
           end
       else
           // Channel NOT in use -> NoteProcessor sleep
           if not IsPluginBypassed(BLK_NoteProcessor[ch]) then
               SetPluginBypassed(BLK_NoteProcessor[ch], true)
               if DebugMode then Trace("BYPASS: NP ch" + (ch+1) + " parked (no active inputs)") end
           end
       end
   End

   // 2. Apply merged decisions to the plugin bypass states
   For i = 0; i < MAX_VSTS; i = i + 1 Do
       if vstShouldBeActive[i] then
           if IsPluginBypassed(BLK_VST[i]) then
               SetPluginBypassed(BLK_VST[i], false)
               RestoreFadersForVST(i)
               if DebugMode then Trace("BYPASS: VST " + (i+1) + " woken (merged OR across scopes)") end
           end
       else
           if not IsPluginBypassed(BLK_VST[i]) then
               ParkFadersForVST(i)
               SetPluginBypassed(BLK_VST[i], true)
               if DebugMode then Trace("BYPASS: VST " + (i+1) + " parked (no scope needs it)") end
           end
       end
   End

   UpdateVstInfoDisplay()
   UpdateUsageLabelDisplay()
End
```

- [ ] **Step 2: Verify the function signature still matches all call sites**

No signature changes — the function is still `Function ExecuteSmartBypass()` with no parameters and no return. All existing call sites remain valid.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(bypass): rewrite ExecuteSmartBypass with per-scope branches

Replaces the pre-existing 'activate everything routed, honor manual
bypass veto' logic with a per-scope Default/Explicit branch decision:
- Default Branch (Mem_ScopeBypassConfigured[ch]=false):
    first routed VST of HumanRoutingMap[ch] contributes 'active'
- Explicit Branch (Mem_ScopeBypassConfigured[ch]=true):
    every routed VST contributes per Mem_ManualVSTBypass[vstIdx]

Contributions from all active scopes are merged with OR to match the
today-behaviour of 'any-routed-scope-wakes-the-VST'. DebugMode traces
at every state transition for post-hoc verification."
```

---

## Task 3: Rewrite `HandleInjectBypassClick()` with flipped polarity + scope flag

**Files:**
- Modify: `Global Rackspace.gpscript:7938-7980`

- [ ] **Step 1: Replace the entire `HandleInjectBypassClick()` function body**

Locate the function at line 7938. Replace the entire function (through its closing `End`) with:

```gpscript
Function HandleInjectBypassClick(btnIdx : Integer, val : Double)
    var i, count, firstScopeIdx, targetVstIdx : Integer

    // GPScript-compliant guard:
    if not IsUpdatingBypassUI then

        firstScopeIdx = GetFirstActiveScope()

        if firstScopeIdx > -1 then
            count = 0
            targetVstIdx = -1

            // Which VST belongs to this button?
            if Size(RoutingMatrix) == 160 then
                i = 0
                While i < MAX_VSTS and targetVstIdx == -1 Do
                    if RoutingMatrix[(i * 16) + firstScopeIdx] == true then
                        if count == btnIdx then
                            targetVstIdx = i
                        end
                        count = count + 1
                    end
                    i = i + 1
                End
            end

            // Write value to RAM and execute
            if targetVstIdx > -1 then

                // FLIP TO EXPLICIT BRANCH for this scope on the very first click
                if not Mem_ScopeBypassConfigured[firstScopeIdx] then
                    Mem_ScopeBypassConfigured[firstScopeIdx] = true
                    if DebugMode then Trace("BYPASS: scope ch" + (firstScopeIdx+1) + " switched to Explicit Branch (first click)") end
                end

                // NEW POLARITY: lit button (val > 0.5) = VST active = Mem_ManualVSTBypass = false
                if val > 0.5 then
                    Mem_ManualVSTBypass[targetVstIdx] = false  // Button LIT = VST active
                    if DebugMode then Trace("BYPASS: VST " + (targetVstIdx+1) + " set ACTIVE via button " + (btnIdx+1)) end
                else
                    Mem_ManualVSTBypass[targetVstIdx] = true   // Button DARK = VST bypassed
                    if DebugMode then Trace("BYPASS: VST " + (targetVstIdx+1) + " set BYPASSED via button " + (btnIdx+1)) end
                end

                // Force immediate re-evaluation
                ExecuteSmartBypass()
            end
        end

    end // End of guard block
End
```

- [ ] **Step 2: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(bypass): flip HandleInjectBypassClick polarity

BTN_Inject_Bypass_* now means 'VST is active' (lit = active, dark =
bypassed). Clicking a dark button writes Mem_ManualVSTBypass=false
(activate); clicking a lit button writes true (bypass).

First click on any button of a scope atomically sets
Mem_ScopeBypassConfigured[firstScopeIdx] = true, switching that scope
from Default Branch to Explicit Branch for all subsequent
ExecuteSmartBypass calls."
```

---

## Task 4: Flip widget polarity in `UpdateUsageLabelDisplay` + rename `[MAN OFF]`

**Files:**
- Modify: `Global Rackspace.gpscript:2340` (rename label)
- Modify: `Global Rackspace.gpscript:2366-2370` (flip widget sync)
- Modify: `Global Rackspace.gpscript:8056` (rename label)

- [ ] **Step 1: Flip the widget sync polarity in `UpdateUsageLabelDisplay`**

At line 2366 you currently have:

```gpscript
              if Mem_ManualVSTBypass[assignedVSTs[i]] == true then
                  SetWidgetValue(W_Inject_Bypass[i], 1.0) 
              else
                  SetWidgetValue(W_Inject_Bypass[i], 0.0) 
              end
```

Replace with:

```gpscript
              // NEW POLARITY: lit (1.0) = VST active, dark (0.0) = VST bypassed
              if Mem_ManualVSTBypass[assignedVSTs[i]] == true then
                  SetWidgetValue(W_Inject_Bypass[i], 0.0)  // bypassed -> dark
              else
                  SetWidgetValue(W_Inject_Bypass[i], 1.0)  // active -> lit
              end
```

- [ ] **Step 2: Rename `[MAN OFF]` to `[MANUAL]` in `UpdateUsageLabelDisplay`**

At line 2340 you currently have:

```gpscript
                      if Mem_ManualVSTBypass[vstIdx] then 
                          bypassStr = " [MAN OFF]" // Manual override indicator
                      elsif IsPluginBypassed(BLK_VST[vstIdx]) then 
                          bypassStr = " [Bypassed]" 
                      else 
                          bypassStr = " [Active]" 
                      end
```

Replace the `[MAN OFF]` string with `[MANUAL]`:

```gpscript
                      if Mem_ManualVSTBypass[vstIdx] then 
                          bypassStr = " [MANUAL]" // Explicit user-set bypass
                      elsif IsPluginBypassed(BLK_VST[vstIdx]) then 
                          bypassStr = " [Bypassed]" 
                      else 
                          bypassStr = " [Active]" 
                      end
```

- [ ] **Step 3: Rename `[MAN OFF]` in `AnalyzeChannel` (second occurrence)**

At line 8056 you currently have:

```gpscript
                   if Mem_ManualVSTBypass[vstIdx] then bypassStr = " [MAN OFF]"
                   elsif IsPluginBypassed(BLK_VST[vstIdx]) then bypassStr = " [Bypassed]"
                   else bypassStr = " [Active]" end
```

Replace with:

```gpscript
                   if Mem_ManualVSTBypass[vstIdx] then bypassStr = " [MANUAL]"
                   elsif IsPluginBypassed(BLK_VST[vstIdx]) then bypassStr = " [Bypassed]"
                   else bypassStr = " [Active]" end
```

- [ ] **Step 4: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "refactor(bypass): flip widget polarity and rename [MAN OFF] label

UpdateUsageLabelDisplay now paints BTN_Inject_Bypass_* lit when the
VST is active and dark when it's bypassed, matching the new semantic.
The '[MAN OFF]' suffix in the VST routing display becomes '[MANUAL]'
in both UpdateUsageLabelDisplay and AnalyzeChannel."
```

---

## Task 5: Add `ExecuteSmartBypass()` call sites on input and output button handlers

**Files:**
- Modify: `Global Rackspace.gpscript:~12663` (input handler)
- Modify: `Global Rackspace.gpscript:~12682` (output handler)

- [ ] **Step 1: Add the call in the input-button handler**

Locate the handler at line 12652 and its body at 12663. You currently have:

```gpscript
On WidgetValueChanged(w : Widget, inputIdx : Integer, val : Double) from BTN_Ch1_In, BTN_Ch2_In, BTN_Ch3_In, BTN_Ch4_In, BTN_Ch5_In, BTN_Ch6_In, BTN_Ch7_In, BTN_Ch8_In, BTN_Ch9_In, BTN_Ch10_In, BTN_Ch11_In, BTN_Ch12_In, BTN_Ch13_In, BTN_Ch14_In, BTN_Ch15_In, BTN_Ch16_In
   var outIdx, paramIdx : Integer
   if TimeSinceStartup() > InputSyncTimer and not IsLoadingSnapshot then
       if val < 0.1 or val > 0.9 then
           SetWidgetLabel(LBL_MidiConfig, "Custom (Unsaved)")
           For outIdx = 0; outIdx < 16; outIdx = outIdx + 1 Do
              if OutputScope[outIdx] then
                  paramIdx = (inputIdx * 16) + outIdx
                  if val > 0.5 then SetParameter(RECH, paramIdx, 1.0) else SetParameter(RECH, paramIdx, 0.0) end
              end
           End
           UpdateMidiConfigLabel(); UpdateMetaColors(); SyncInputFeedback()
       end
   end
End
```

Add the `ExecuteSmartBypass()` call plus a trace after `SyncInputFeedback()`:

```gpscript
           UpdateMidiConfigLabel(); UpdateMetaColors(); SyncInputFeedback()
           if DebugMode then Trace("BYPASS: BTN_ChX_In click -> ExecuteSmartBypass (inputIdx=" + (inputIdx+1) + " val=" + val + ")") end
           ExecuteSmartBypass()
```

- [ ] **Step 2: Add the call in the output-button handler**

Locate the handler at line 12668 and its body at 12682. You currently have:

```gpscript
   var chIdx : Integer 
   chIdx = index % 16 
   
   if TimeSinceStartup() > OutputSyncTimer then
       if val > 0.5 then OutputScope[chIdx] = true else OutputScope[chIdx] = false end
       UpdateMetaColors(); SyncInputFeedback(); UpdateUsageLabelDisplay()
       RefreshAllInjectionDisplays(); ScrollToCurrentChannel()
   end
End
```

Add the `ExecuteSmartBypass()` call plus a trace after `ScrollToCurrentChannel()`:

```gpscript
   if TimeSinceStartup() > OutputSyncTimer then
       if val > 0.5 then OutputScope[chIdx] = true else OutputScope[chIdx] = false end
       UpdateMetaColors(); SyncInputFeedback(); UpdateUsageLabelDisplay()
       RefreshAllInjectionDisplays(); ScrollToCurrentChannel()
       if DebugMode then Trace("BYPASS: BTN_ChX_Out_* click -> ExecuteSmartBypass (chIdx=" + (chIdx+1) + " val=" + val + ")") end
       ExecuteSmartBypass()
   end
End
```

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "fix(bypass): call ExecuteSmartBypass after input/output button clicks

Closes the pre-existing bug where manually routing a channel with no
Song.ini loaded left every NoteProcessor and VST bypassed. Both the
BTN_ChX_In and BTN_ChX_Out_* handlers now trigger
ExecuteSmartBypass() after their RECH/OutputScope writes so the
default rule kicks in immediately."
```

---

## Task 6: Clear `Mem_ScopeBypassConfigured` on all reset/snapshot-reset paths

**Files:**
- Modify: `Global Rackspace.gpscript` — find all reset sites via Grep

- [ ] **Step 1: Locate reset sites**

Run a Grep for `Mem_ManualVSTBypass` — every place that zeroes this array is a candidate place to also zero `Mem_ScopeBypassConfigured`. Expected candidates:
- `LoadSongSnapshot` / the Song-Load path (resets per-song state)
- `ResetToFactory` / `DEF_RECH` reset path around line 11207
- Bootstrap PHASE 5 (already covered in Task 1 Step 2)

Each reset site that writes `Mem_ManualVSTBypass[i] = false` in a loop should gain a parallel loop clearing `Mem_ScopeBypassConfigured[ch] = false`.

- [ ] **Step 2: Apply the clear at each found site**

For every site that contains a loop like:

```gpscript
For i = 0; i < MAX_VSTS; i = i + 1 Do
    Mem_ManualVSTBypass[i] = false
End
```

Add immediately after (or alongside) it:

```gpscript
For i = 0; i < 16; i = i + 1 Do
    Mem_ScopeBypassConfigured[i] = false
End
if DebugMode then Trace("BYPASS: Mem_ScopeBypassConfigured cleared on reset path") end
```

If a reset site does NOT currently clear `Mem_ManualVSTBypass` but does reset other matrix state (e.g. `DEF_RECH` reset), add both clears there so the state is coherent after reset.

- [ ] **Step 3: Commit**

```bash
git add "Global Rackspace.gpscript"
git commit -m "fix(bypass): clear Mem_ScopeBypassConfigured on all reset paths

Keeps the per-scope Explicit/Default state coherent after Song-Load,
ResetToFactory, and any other path that zeroes Mem_ManualVSTBypass.
After a reset, every scope is back in Default Branch until the user
touches a BTN_Inject_Bypass_* button again."
```

---

## Task 7: Commit the spec update that already exists in working tree

**Files:**
- Modify: `docs/superpowers/specs/2026-04-11-lfo-looper-timeline-design.md` (already edited in-session)

- [ ] **Step 1: Verify the spec has the per-scope refinement**

Run: `git diff docs/superpowers/specs/2026-04-11-lfo-looper-timeline-design.md`

Expected: §4.2 now describes `Mem_ScopeBypassConfigured` and per-scope branch decisions; §4.5 describes the first-touch behaviour where the handler atomically sets `Mem_ScopeBypassConfigured[firstScopeIdx]`.

- [ ] **Step 2: Commit the spec update**

```bash
git add docs/superpowers/specs/2026-04-11-lfo-looper-timeline-design.md
git commit -m "docs(specs): refine bypass rule to per-scope Explicit/Default branching

§4.2 switches from a global HasExplicitBypassOverride check to a
per-channel Mem_ScopeBypassConfigured flag, so one scope can be in
Explicit while another stays in Default. §4.5 describes the atomic
first-touch transition in HandleInjectBypassClick. Matches the
Plan-1 implementation."
```

---

## Verification (after all tasks)

No automated tests. After all commits, the user opens Gig Performer with `examples/Test.gig`, reloads the rackspace with the updated script, and performs the following manual checks. Any unexpected trace, compile error, or missing trace is reported back as feedback.

**A. Compile and cold-boot**

1. Paste the updated `Global Rackspace.gpscript` into the rackspace script editor.
2. Compile — expect no compiler errors.
3. Open the script console — expect `BYPASS: Mem_ScopeBypassConfigured initialized (all 16 channels = false)` on bootstrap.

**B. Default Branch on empty gig**

1. With no Song.ini loaded, click `BTN_Ch5_In` while `BTN_Ch5_Out_*` is active.
2. Console expected traces (order may vary):
   - `BYPASS: BTN_ChX_In click -> ExecuteSmartBypass (inputIdx=5 ...)`
   - `BYPASS: NP ch5 woken (active inputs=1)`
   - `BYPASS: VST N woken (merged OR across scopes)` — where N is the first VST in `HumanRoutingMap[4]` (for the example map, VST 5 → index 4)
3. Play a note on Ch5 input → should be heard through the first routed VST.

**C. Explicit Branch transition**

1. With the scope activated from (B), click `BTN_Inject_Bypass_2` (the button for the second routed VST).
2. Console expected:
   - `BYPASS: scope ch5 switched to Explicit Branch (first click)`
   - `BYPASS: VST M set ACTIVE via button 2` (where M is the second routed VST index)
   - `BYPASS: VST M woken (merged OR across scopes)`
3. The second routed VST should now be audible alongside the first.

**D. Polarity check**

1. Click `BTN_Inject_Bypass_2` a second time (dark it).
2. Console expected: `BYPASS: VST M set BYPASSED via button 2` → `BYPASS: VST M parked (no scope needs it)`.
3. The second VST goes silent.

**E. Reset path**

1. Switch to a different song or trigger a reset.
2. Console expected: `BYPASS: Mem_ScopeBypassConfigured cleared on reset path`.
3. Next input click on a fresh scope → back to Default Branch traces.

---

## Self-Review

**Spec coverage:** §4.1 (the bug) — Task 5. §4.2 (unified rule / per-scope branch) — Tasks 1, 2. §4.3 (call sites) — Task 5. §4.4 (walk-through) — covered by verification section. §4.5 (semantic flip) — Tasks 3, 4. §4.6 (nested-effect check) — not an implementation item, handled in task narrative.

**Placeholder scan:** Task 6 contains "find all reset sites via Grep" which is an explicit exploration step rather than a placeholder. All code blocks are complete.

**Type consistency:** `Mem_ScopeBypassConfigured` is 16 entries (per channel), `Mem_ManualVSTBypass` is 10 entries (per VST). The new function body indexes them correctly: `ch` loop `0..15` reads `Mem_ScopeBypassConfigured[ch]`; per-routed-VST loop reads `Mem_ManualVSTBypass[vstIdx]`. `RestoreFadersForVST` / `ParkFadersForVST` are existing helpers used by the old implementation at lines 7904 / 7913 / 7918. `GetFirstActiveScope()` is an existing helper at ~line 7945. `IsUpdatingBypassUI` shield is pre-existing. `SplitString`, `TrimString`, `StringToInt` are standard GPScript primitives already used in the Bootstrap.
