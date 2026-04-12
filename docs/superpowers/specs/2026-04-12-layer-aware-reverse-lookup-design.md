# Layer-Aware Reverse Lookup — Design Spec

**Date:** 2026-04-12
**Status:** Design approved
**Scope:** Fix layer remapping architecture — Layer in Source syntax, OTZ marker, per-layer reverse lookup

---

## 1. Problem

The current implementation puts the layer in the **binding** (`LAY1:ROOT:CH1`). The physical control always maps to the same macro, and the active layer filters which binding fires. 

The correct model: the Layer Switch **remaps physical controls to different macros**. The same physical slider triggers different macros depending on the active layer.

## 2. Syntax Changes

### 2.1 Layer in Source

```
Old: DEV0:SLD1          (no layer awareness)
New: DEV0:LAY1:SLD1     (layer is part of the source)
```

Every macro declares exactly one layer. No implicit "all layers". Macros active on multiple layers are repeated:

```ini
Macro7 = DEV0:LAY0:BTN7; SCRUBBER
Macro43 = DEV0:LAY1:BTN7; SCRUBBER
Macro44 = DEV0:LAY2:BTN7; SCRUBBER
Macro45 = DEV0:LAY3:BTN7; SCRUBBER
```

### 2.2 OTZ Marker (Overlay Trigger Zone)

```
{0.0,1.0}          = Normal value-passthrough with scaling range
{OTZ,1.0,1.0}      = Overlay: ON at max, OFF when away (positional)
{OTZ,0.0,0.0}      = Overlay: ON at min, OFF when away (positional)
{OTZ,0.5,0.8}      = Overlay: IN zone = ON, OUT = OFF (positional)
{OTZ,0.0,1.0}      = Overlay: Movement-Toggle + 10s debounce
```

Only registered overlay functions are accepted with OTZ. Unknown names are ignored with Trace warning.

### 2.3 No LAY Prefix in Bindings

Bindings no longer have `LAY1:` prefixes. All bindings on a macro line fire when that macro is triggered (the layer selection already happened at the source/lookup level).

## 3. Per-Layer Reverse Lookup

### 3.1 Data Structures

```
Mac_SourceLayer[51]         — layer index per macro (0-3)
Mac_ReverseLookup_L0[256]   — CC → macroIdx for LAY0
Mac_ReverseLookup_L1[256]   — CC → macroIdx for LAY1
Mac_ReverseLookup_L2[256]   — CC → macroIdx for LAY2
Mac_ReverseLookup_L3[256]   — CC → macroIdx for LAY3
```

All arrays under 256 elements (GP hard limit).

### 3.2 Dispatch

```
ProcessHardwareCC:
  cc = GetCCNumber(m)
  Select ActiveLayer:
    0: macroIdx = Mac_ReverseLookup_L0[cc]
    1: macroIdx = Mac_ReverseLookup_L1[cc]
    2: macroIdx = Mac_ReverseLookup_L2[cc]
    3: macroIdx = Mac_ReverseLookup_L3[cc]
  if macroIdx > 0: ExecuteHardwareMacro(macroIdx, val)
```

### 3.3 ExecuteHardwareMacro Simplified

No layer check needed — the macro was already layer-correctly selected. All bindings fire:
- Normal targets (VST, CC, KEYWORD, SYSACT): execute directly
- OTZ targets: route through FireOverlayTrigger

## 4. Start Configuration

Channel mapping: BTN/SLD 1=CH1, 2=CH2, 3=CH3, 4=CH11, 5=CH12, 6=CH14

### Buttons (6 physical, 4 layers = 24 macros)

| Phys | LAY0 | LAY1 | LAY2 | LAY3 |
|---|---|---|---|---|
| BTN1 | VST1_GRS:48 | ROOT:CH1 | OCTAVER:CH1 | CHANNEL_BOUND_LFO |
| BTN2 | VST1_GRS:49 | ROOT:CH2 | OCTAVER:CH2 | SYSACT_TRANSPORT_TOGGLE |
| BTN3 | VST1_GRS:50 | ROOT:CH3 | OCTAVER:CH3 | VST_SCOPE |
| BTN4 | VST1_GRS:51 | ROOT:CH11 | OCTAVER:CH11 | VST_BROWSE |
| BTN5 | VST1_GRS:52 | ROOT:CH12 | OCTAVER:CH12 | SCRUBBER |
| BTN6 | VST1_GRS:53 | ROOT:CH14 | OCTAVER:CH14 | CROSSFADER |

### System Buttons (BTN7-12, all layers)

BTN7=SCRUBBER, BTN8=SYSACT_VST_SCOPE_DOWN, BTN9=SYSACT_VST_SCOPE_UP, BTN10=SYSACT_VST_PRESET_DOWN, BTN11=SYSACT_VST_PRESET_UP, BTN12=SYSACT_TL_REC_SONGPART — repeated on all 4 layers.

### Sliders (9 physical, 3 layers with overlays)

| Phys | LAY0 | LAY1 (+ overlay) | LAY2 (+ overlay) |
|---|---|---|---|
| SLD1 | VST1_GRS:0 | VST1_GRS:0 + SMART_SOLO:CH1 | VST1_GRS:0 + STRICT_SOLO:CH1 |
| SLD2 | VST1_GRS:1 | VST1_GRS:1 + SMART_SOLO:CH2 | VST1_GRS:1 + STRICT_SOLO:CH2 |
| SLD3 | VST1_GRS:2 | VST1_GRS:2 + SMART_SOLO:CH3 | VST1_GRS:2 + STRICT_SOLO:CH3 |
| SLD4 | VST1_GRS:3 | VST1_GRS:3 + SMART_SOLO:CH11 | VST1_GRS:3 + STRICT_SOLO:CH11 |
| SLD5 | VST1_GRS:4 | VST1_GRS:4 + SMART_SOLO:CH12 | VST1_GRS:4 + STRICT_SOLO:CH12 |
| SLD6 | VST1_GRS:5 | VST1_GRS:5 + SMART_SOLO:CH14 | VST1_GRS:5 + STRICT_SOLO:CH14 |
| SLD7 | VST1_GRS:6 | VST1_GRS:6 | VST1_GRS:6 |
| SLD8 | Ch12:CC7 V_Lab | Ch12:CC7 V_Lab | Ch12:CC7 V_Lab |
| SLD9 | Ch13:CC7 Triton | Ch13:CC7 Triton | Ch13:CC7 Triton |

## 5. Code Changes

| Component | Change |
|---|---|
| ParseMacroSource | Parse `DEV0:LAY1:SLD3` — extract layer |
| ParseSingleBinding | Recognize `{OTZ,...}` → targetType=OVERLAY |
| Mac_SourceLayer[] | NEW array: layer per macro |
| Mac_ReverseLookup_L0-L3[] | Replace single lookup with 4 per-layer arrays |
| RebuildReverseLookups | Build 4 arrays based on Mac_SourceLayer |
| ProcessHardwareCC | Select ActiveLayer → correct lookup array |
| ProcessHardwareNote | Same pattern |
| ExecuteHardwareMacro | Remove layer check (no longer needed) |
| InitMacroArrays | Init 5 new arrays (SourceLayer + 4 lookups) |
| ControllerMaps.txt | Full rewrite with new syntax |
