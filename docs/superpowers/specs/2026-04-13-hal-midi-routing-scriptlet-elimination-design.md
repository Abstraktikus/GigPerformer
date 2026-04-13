# HAL MIDI Output Routing & Scriptlet Elimination

**Date:** 2026-04-13
**Status:** Approved
**Approach:** Big Bang — no legacy support, no backward compatibility

## Problem

Two Gig Performer scriptlets (`Genos2_Control`, `Genos2_StyleControl`) act as parameter bridges between the Global Rackspace script and the Genos2 hardware. This is unnecessary indirection: the Global Script can address MIDI output devices directly via `SendNowToMidiOutDevice()`.

Additionally, all CC output is hardcoded to `DEV_MidiOut[0]` with no way to route different MIDI streams to different physical ports. The Genos2 requires Volume (CC7) on a separate port from Expression (CC11) and Control CCs due to a suspected USB-MIDI port defect on Port B.

## Goals

1. Eliminate `Genos2_Control` scriptlet (volume/expression parameter bridge)
2. Eliminate `Genos2_StyleControl` scriptlet (style note-pulse triggers)
3. Eliminate all associated GP wiring blocks (`ExternalArranger`, `BLK_ArrangerSync`, dedicated MIDI Out blocks)
4. Add configurable per-stream MIDI output routing in DeviceConfig.txt
5. Add configurable style trigger note mappings in DeviceConfig.txt
6. All MIDI output from Global Script via `SendNowToMidiOutDevice()` with route lookup

## Non-Goals

- NoteProcessor scriptlets (`Note Prozessor.gpscript`) — different purpose, stays
- Audio-Mixer crossfader path — purely GP-internal, unchanged
- ControllerMaps.txt — no changes needed, macro targets unchanged
- Multi-arranger support — single arranger only, but config is extensible

## Available MIDI Output Ports

Verified from GP MIDI settings (see `logs/GigPerformerMIDIPorts.png`):

| Port | Device |
|------|--------|
| `Babyface Midi Port 1` | RME Babyface (DIN MIDI out → Genos2 MIDI-A-In) |
| `Digital Keyboard-1` | Genos2 USB Port A |
| `Digital Keyboard-2` | Genos2 USB Port B (suspected defect, testable after migration) |
| `2-Yamaha AG03MK2-1` | Yamaha AG03 mixer |

## Design

### 1. DeviceConfig.txt: Output Route Table

New `Route:<stream>` keys under each `[DEVICE:]` block. Parsed once at boot. Runtime lookup is a flat array access.

```ini
; Route:Volume     = CC7 per-channel volume feedback to arranger hardware.
;                    Separated because some USB-MIDI devices have port issues;
;                    allows routing volume through an alternate interface
;                    (e.g. DIN MIDI via audio interface).
;
; Route:Expression = CC11 crossfader expression floating.
;                    Sends per-channel expression values to arranger channels
;                    that have crossfader enabled (W_CF_Arranger toggles).
;                    Uses quadratic scaling for smooth response curve.
;
; Route:Control    = All other outbound MIDI: generic CCs from ControllerMap,
;                    style trigger note pulses, SysEx commands.
;                    This is the "default" output path.

Route:Volume=Babyface Midi Port 1
Route:Expression=Digital Keyboard-1
Route:Control=Digital Keyboard-1
```

**Fallback rule:** If a `Route:*` key is missing, it falls back to `MidiOut`. Devices without special routing (e.g. MiniLab3) need no Route lines.

### 2. DeviceConfig.txt: Style Trigger Mapping

New `TriggerChannel` and `Trigger:<name>` keys. Maps logical trigger names to MIDI notes.

```ini
; Style triggers are sent as Note On (vel 127) + Note Off (vel 0) after 50ms pulse
; on TriggerChannel. Another arranger can define different notes or fewer triggers.

TriggerChannel=16
Trigger:TapTempo=13
Trigger:StartStop=14
Trigger:SyncStop=15
Trigger:Intro1=16
Trigger:Intro2=17
Trigger:Intro3=18
Trigger:MainA=20
Trigger:MainB=21
Trigger:MainC=22
Trigger:MainD=23
Trigger:FillDown=24
Trigger:FillUp=25
Trigger:FillSelf=26
Trigger:Break=27
Trigger:Ending1=28
Trigger:Ending2=29
Trigger:Ending3=30
Trigger:SongA=31
Trigger:SongB=32
Trigger:MP1=33
Trigger:MP2=34
Trigger:MP3=35
Trigger:MP4=36
Trigger:MPStop=37
Trigger:Right1=38
Trigger:Right2=39
Trigger:Right3=40
Trigger:Left=41
Trigger:Fade=43
```

**Name conventions:**

| Category | Defined in | Changeable? |
|----------|-----------|-------------|
| `TRIG_START_STOP` (script constant) | Global Script | No — transport sync logic depends on it |
| `Trigger:StartStop` (config name) | DeviceConfig.txt | Yes — parser maps to script constant |
| `SYSACT_TRANSPORT_TOGGLE` (macro label) | ControllerMaps.txt | Yes — user-facing, freely assignable |

Only `TRIG_START_STOP` is hardcoded in script logic (transport sync, echo guard). All other 28 triggers are generic: `FireStyleTrigger(idx)` sends the pulse, `RecordTimelineEvent("Style", idx)` records it. No script change needed for a different arranger's trigger set.

### 3. Script Data Structures

**New constants:**
```
ROUTE_VOLUME     = 0
ROUTE_EXPRESSION = 1
ROUTE_CONTROL    = 2
ROUTE_COUNT      = 3
```

**New arrays:**
```
DEV_Route          : String Array    ; [devIdx * ROUTE_COUNT + routeType] -> port name
DEV_TriggerNote    : Integer Array   ; [triggerIdx] -> MIDI note number
DEV_TriggerName    : String Array    ; [triggerIdx] -> config name (for reverse lookup)
DEV_TriggerCount   : Integer         ; number of parsed triggers
DEV_TriggerChannel : Integer         ; 1-based channel (e.g. 16)
```

**Size:** `MAX_DEVICES * ROUTE_COUNT` = 4 x 3 = 12 route entries. Max 29 trigger entries. Well within GP's 256-element limit.

**Lookup function:**
```
Function GetDeviceRoute(devIdx : Integer, routeType : Integer) Returns String
    result = DEV_Route[devIdx * ROUTE_COUNT + routeType]
End
```

### 4. Parser Extension (ParseDeviceConfig)

Within the `[DEVICE:]` parsing loop, handle new keys:

- `Route:Volume`, `Route:Expression`, `Route:Control` → store in `DEV_Route[]`
- `TriggerChannel` → store in `DEV_TriggerChannel`
- `Trigger:<name>=<note>` → append to `DEV_TriggerNote[]` / `DEV_TriggerName[]`, increment `DEV_TriggerCount`

After parsing a device block: initialize any missing routes to `DEV_MidiOut[devIdx]` (fallback).

Map `Trigger:StartStop` to the script constant `TRIG_START_STOP` index for transport logic.

### 5. Sende-Pfad: Volume & Expression

**`SendArrangerVolumeFeedback(val, ch)`** — restore from pre-weekend version (commit f60a338), change:
```
; Before:  outDev = GetDeviceMidiOut(arrangerDevIdx)
; After:   outDev = GetDeviceRoute(arrangerDevIdx, ROUTE_VOLUME)
```
Features retained: asymmetric scaling (Yamaha 0-100 vs standard 0-127), dedup via `Arr_LastSentVol[]`, echo-block via `Arr_EchoBlockTimer[]`.

**`SendArrangerCrossfaderExpression(cfVal)`** — restore from pre-weekend version, change:
```
; Before:  outDev = GetDeviceMidiOut(arrangerDevIdx)
; After:   outDev = GetDeviceRoute(arrangerDevIdx, ROUTE_EXPRESSION)
```
Features retained: quadratic scaling `(cfVal * cfVal) * 127`, per-channel W_CF_Arranger enable check, dedup via `Arr_LastSentExp[]`.

**`ApplyCrossfade(x_val)`** — replace `SetParameter(ExternalArranger, P_ARRANGER_CROSSFADER, x_val)` with direct call to `SendArrangerCrossfaderExpression(x_val)`.

### 6. Sende-Pfad: Style Triggers

**`FireStyleTrigger(triggerIdx)`** — rewrite:
```
route = GetDeviceRoute(arrangerDevIdx, ROUTE_CONTROL)
ch = DEV_TriggerChannel
note = DEV_TriggerNote[triggerIdx]
SendNowToMidiOutDevice(route, MakeNoteMessageEx(note, 127, ch))
SendLaterToMidiOutDevice(route, MakeNoteMessageEx(note, 0, ch), 50)
StyleEchoBlockTimer = TimeSinceStartup() + 500.0
```

All existing `SetParameter(BLK_ArrangerSync, styleId, 1.0/0.0)` calls become `FireStyleTrigger(triggerIdx)`.

### 7. Sende-Pfad: Generic CCs (ControllerMap)

**`ExecuteHardwareMacro`** CC branch — change:
```
; Before:  SendNowToMidiOutDevice(DEV_MidiOut[0], ...)
; After:   SendNowToMidiOutDevice(GetDeviceRoute(arrangerDevIdx, ROUTE_CONTROL), ...)
```

### 8. Empfangs-Pfad: Style Feedback (replaces On ParameterValueChanged from BLK_ArrangerSync)

Transport detection moves into existing DeviceIn_0 callbacks:

| Signal | Callback | Action |
|--------|----------|--------|
| Note 14 On, Ch16 | `On NoteEvent from DeviceIn_0` | Set transport flag, fire sync logic (SyncMode 1-5) |
| CC5, Ch16 | `On ControlChangeEvent from DeviceIn_0` | Set transport flag |
| Realtime 0xFA/0xFB/0xFC | Appropriate DeviceIn_0 callback (verified: GP passes these through) | Set transport flag |

Echo guard: incoming style events on `DEV_TriggerChannel` are ignored when `TimeSinceStartup() < StyleEchoBlockTimer`.

Timeline recording: `RecordTimelineEvent("Style", triggerIdx)` — reverse-lookup from note number via `DEV_TriggerNote[]` to get the triggerIdx.

### 9. Deletion Inventory

**Delete from Global Rackspace script:**

| Item | Action |
|------|--------|
| `BLK_ArrangerSync : PluginBlock` declaration | Delete |
| `ExternalArranger` block declaration | Delete |
| All `SetParameter(BLK_ArrangerSync, ...)` calls | Replace with `FireStyleTrigger()` |
| All `SetParameter(ExternalArranger, ...)` calls | Replace with direct MIDI send via route lookup |
| `On ParameterValueChanged from BLK_ArrangerSync` callback | Delete — logic moves to DeviceIn_0 callbacks |
| `P_STYLE_START_STOP`, `P_STYLE_HW_START` constants | Delete — replaced by config-driven trigger lookup |
| All `P_ARRANGER_*` constants | Delete — no more parameter bridge |

**Delete from Gig Performer manually (wiring blocks):**

| Block | Type |
|-------|------|
| `ExternalArranger` | Scriptlet block (contains Genos2_Control code) |
| `BLK_ArrangerSync` | Scriptlet block (contains Genos2_StyleControl code) |
| `MidiOutGn2P1` | MIDI Out block (was Expression-only output) |
| MIDI Out (Babyface Midi Port 1) | MIDI Out block (was Volume-only output) |

**Keep and extend:**

| Item | Change |
|------|--------|
| `DeviceIn_0` (Digital Keyboard-1) | Gets style-receive logic in existing callbacks |
| `ParseDeviceConfig` | Learns `Route:*` and `Trigger:*` keys |
| `SendArrangerVolumeFeedback()` | Route lookup via `ROUTE_VOLUME` |
| `SendArrangerCrossfaderExpression()` | Route lookup via `ROUTE_EXPRESSION` |
| `ApplyCrossfade()` | Calls `SendArrangerCrossfaderExpression()` directly |
| `FireStyleTrigger()` | Direct note-pulse via `ROUTE_CONTROL` |

## Testing

1. Copy updated `DeviceConfig.txt` to gig file directory
2. Delete scriptlet blocks and MIDI Out blocks in GP wiring view
3. Load gig, check script console for `SCRIPT VERSION <version> booting`
4. Verify boot log shows parsed routes: `HAL: Route Volume=Babyface Midi Port 1`, etc.
5. Verify boot log shows parsed triggers: `HAL: 29 style triggers loaded, channel=16`
6. Test each stream:
   - Volume: move a volume-bound fader → verify CC7 arrives at Genos2 via Babyface DIN
   - Expression: move crossfader → verify CC11 arrives at Genos2 via Digital Keyboard-1
   - Control: move a CC-bound knob → verify CC arrives at Genos2
   - Style: trigger a style action → verify note pulse on Ch16
7. Test echo blocking: trigger style from Genos2 hardware → verify no feedback loop
8. Test `Digital Keyboard-2`: change `Route:Volume=Digital Keyboard-2` → verify if port works
