# Plan A: Parser & Data Structures — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the DeviceConfig and ControllerMap parsers to support the unified v2 format with layer system, Default inheritance, per-layer merge, and VST validation.

**Architecture:** Replace `LoadHardwareMap()` + `LoadControllerMap()` with a new unified parser that reads `DeviceConfig_v2.txt` (extended sections) and `ControllerMaps_v2.txt` (unified syntax with `[Map:Default]` inheritance). Internal data structures store per-macro, per-layer bindings with multi-device sources. On song switch: clone Default, merge song delta per-layer. No backward compatibility with v1 format.

**Tech Stack:** GPScript 5.x, INI-style text parsing, Global Rackspace script (~16.8k lines)

**GPScript constraints:** No compiler outside GP, no test framework. All functions must be defined before callers (forward declaration order). All `var` declarations at function top. No early return — use if/else. All Double vars initialized with `= 0.0`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `Global Rackspace.gpscript` | Modify | All parser code, data structures, display |
| `examples/DeviceConfig_v2.txt` | Read-only | Reference config for parsing |
| `examples/ControllerMaps_v2.txt` | Read-only | Reference config for parsing |

All changes are within `Global Rackspace.gpscript`. Section references follow the existing structure (SECTION 1–26).

---

### Task 1: New Data Structures for Layer System

**Location:** SECTION 3 (HAL, ~line 162) and SECTION 8 (Controller Map Data, ~line 650)

Add new global variable declarations to the existing `Var` block.

- [ ] **Step 1: Add Layer System variables to SECTION 3 (~line 210)**

After the existing device/control registry arrays, add:

```gpscript
   // --- LAYER SYSTEM ---
   MAX_LAYERS : Integer = 16
   MAX_SWITCHES : Integer = 8
   MAX_OVERLAY_BINDINGS : Integer = 512

   LayerSwitch_Count : Integer = 0
   LayerSwitch_DevIdx : Integer Array = [-1, -1, -1, -1, -1, -1, -1, -1]
   LayerSwitch_Label : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_Type : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_OnData : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_OffData : String Array = ["", "", "", "", "", "", "", ""]
   LayerSwitch_State : Integer Array = [0, 0, 0, 0, 0, 0, 0, 0]

   LayerMap_Count : Integer = 0
   LayerMap_DevIdx : Integer Array = [-1]
   LayerMap_StateBits : Integer Array = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
   LayerMap_LayerIdx : Integer Array = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

   ActiveLayer : Integer = 0

   Permanent_Count : Integer = 0
   Permanent_DevIdx : Integer Array = [-1, -1, -1, -1]
   Permanent_Source : String Array = ["", "", "", ""]
   Permanent_Function : String Array = ["", "", "", ""]

   Overlay_Count : Integer = 0
   Overlay_DevIdx : Integer Array = [-1, -1, -1, -1]
   Overlay_Layer : Integer Array = [0, 0, 0, 0]
   Overlay_Action : String Array = ["", "", "", ""]
```

- [ ] **Step 2: Add Unified Macro structures to SECTION 8 (~line 700)**

Replace or extend the existing Link_* arrays with the new per-macro, per-layer structure:

```gpscript
   // --- UNIFIED MACRO SYSTEM (v2) ---
   // Source arrays: which hardware controls feed each macro
   MAX_SOURCES_PER_MACRO : Integer = 4
   Mac_SourceCount : Integer Array   // [MAX_MACROS] number of sources
   Mac_SourceDev : Integer Array     // [MAX_MACROS * MAX_SOURCES_PER_MACRO] flat
   Mac_SourceType : String Array     // [MAX_MACROS * MAX_SOURCES_PER_MACRO] BTN/SLD/ENC/JOY
   Mac_SourceCtrl : Integer Array    // [MAX_MACROS * MAX_SOURCES_PER_MACRO] control index

   // Per-layer bindings: flat arrays indexed by (macroIdx * MAX_LAYERS * MAX_BINDINGS_PER_LAYER) + (layerIdx * MAX_BINDINGS_PER_LAYER) + bindingIdx
   MAX_BINDINGS_PER_LAYER : Integer = 8
   Mac_Layer_BindCount : Integer Array   // [MAX_MACROS * MAX_LAYERS]
   Mac_Layer_TargetType : String Array   // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER] VST/CC/KEYWORD/SYSACT/OVERLAY
   Mac_Layer_Target : String Array       // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER] serialized target
   Mac_Layer_RangeMin : Double Array     // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER]
   Mac_Layer_RangeMax : Double Array     // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER]
   Mac_Layer_Channel : Integer Array     // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER] for overlays
   Mac_Layer_VSTIdx : Integer Array      // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER] for VST targets
   Mac_Layer_ParamIdx : Integer Array    // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER] for VST targets
   Mac_Layer_ParamLabel : String Array   // [MAX_MACROS * MAX_LAYERS * MAX_BINDINGS_PER_LAYER] cached names

   // Default map (persistent, cloned on song switch)
   Def_Mac_SourceCount : Integer Array
   Def_Mac_SourceDev : Integer Array
   Def_Mac_SourceType : String Array
   Def_Mac_SourceCtrl : Integer Array
   Def_Mac_Layer_BindCount : Integer Array
   Def_Mac_Layer_TargetType : String Array
   Def_Mac_Layer_Target : String Array
   Def_Mac_Layer_RangeMin : Double Array
   Def_Mac_Layer_RangeMax : Double Array
   Def_Mac_Layer_Channel : Integer Array
   Def_Mac_Layer_VSTIdx : Integer Array
   Def_Mac_Layer_ParamIdx : Integer Array
   Def_Mac_Layer_ParamLabel : String Array

   // VST declarations per map
   MAX_VST_DECL : Integer = 9
   MapVST_Name : String Array       // [MAX_VST_DECL] expected VST name per slot
   MapVST_Valid : Integer Array      // [MAX_VST_DECL] 0=not declared, 1=valid, 2=mismatch, 3=not loaded
   DefMapVST_Name : String Array    // [MAX_VST_DECL] default map VST declarations

   // Reverse lookups (rebuilt on map load)
   Mac_ReverseLookup_CC : Integer Array    // [16 * 128] CC(ch,num) → macroIdx, -1 if none
   Mac_ReverseLookup_SysAct : Integer Array // [MAX_MACROS] macroIdx → sysActionIdx, -1 if none
```

- [ ] **Step 3: Add helper index functions**

In SECTION 13 (Core Utilities, ~line 850), add index calculation helpers:

```gpscript
// Flat index into Mac_Layer_* arrays
Function MacLayerBindIdx(macroIdx : Integer, layerIdx : Integer, bindIdx : Integer) Returns Integer
   var result : Integer
   result = (macroIdx * MAX_LAYERS * MAX_BINDINGS_PER_LAYER) + (layerIdx * MAX_BINDINGS_PER_LAYER) + bindIdx
   Result = result
End

// Flat index into Mac_Layer_BindCount
Function MacLayerIdx(macroIdx : Integer, layerIdx : Integer) Returns Integer
   var result : Integer
   result = (macroIdx * MAX_LAYERS) + layerIdx
   Result = result
End

// Flat index into Mac_Source* arrays
Function MacSourceIdx(macroIdx : Integer, srcIdx : Integer) Returns Integer
   var result : Integer
   result = (macroIdx * MAX_SOURCES_PER_MACRO) + srcIdx
   Result = result
End
```

- [ ] **Step 4: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(data): add layer system and unified macro data structures"
```

---

### Task 2: DeviceConfig v2 Parser — LAYERSWITCH, LAYERMAP, PERMANENT, OVERLAY

**Location:** SECTION 14 (HAL Runtime, ~line 1443), modify `ParseDeviceConfig()` at line 1487

- [ ] **Step 1: Extend ParseDeviceConfig() to parse new sections**

Inside the existing `ParseDeviceConfig()` function (line 1487), after the existing `[SYSEX:*]` parsing block, add parsing for the four new section types. The existing parser uses a line-by-line approach reading from a file with `ReadLineFromFile()` and matching section headers.

Add these parsing blocks after the SYSEX parsing, following the same pattern:

```gpscript
      // --- LAYERSWITCH parsing ---
      elsif Left(trimmedLine, 13) == "[LAYERSWITCH:" then
         currentSection = "LAYERSWITCH"
         sectionIdx = StringToInt(Mid(trimmedLine, 14, Pos("}", trimmedLine) - 14))
         if sectionIdx >= 0 and sectionIdx < MAX_SWITCHES then
            LayerSwitch_Count = Max(LayerSwitch_Count, sectionIdx + 1)
         end

      elsif currentSection == "LAYERSWITCH" then
         eqPos = Pos("=", trimmedLine)
         if eqPos > 0 then
            key = Trim(Left(trimmedLine, eqPos - 1))
            value = Trim(Mid(trimmedLine, eqPos + 1, 999))
            if key == "Device" then
               LayerSwitch_DevIdx[sectionIdx] = StringToInt(value)
            elsif key == "Label" then
               LayerSwitch_Label[sectionIdx] = value
            elsif key == "Type" then
               LayerSwitch_Type[sectionIdx] = value
            elsif key == "OnData" then
               LayerSwitch_OnData[sectionIdx] = value
            elsif key == "OffData" then
               LayerSwitch_OffData[sectionIdx] = value
            end
         end

      // --- LAYERMAP parsing ---
      elsif Left(trimmedLine, 10) == "[LAYERMAP:" then
         currentSection = "LAYERMAP"
         sectionIdx = StringToInt(Mid(trimmedLine, 11, Pos("}", trimmedLine) - 11))
         LayerMap_Count = Max(LayerMap_Count, sectionIdx + 1)

      elsif currentSection == "LAYERMAP" then
         eqPos = Pos("=", trimmedLine)
         if eqPos > 0 then
            key = Trim(Left(trimmedLine, eqPos - 1))
            value = Trim(Mid(trimmedLine, eqPos + 1, 999))
            if Left(key, 6) == "State_" then
               var stateNum : Integer
               stateNum = StringToInt(Mid(key, 7, 999))
               LayerMap_StateBits[stateNum] = stateNum
               LayerMap_LayerIdx[stateNum] = StringToInt(Mid(value, 4, 999))  // "LAY3" → 3
            end
            if key == "Device" then
               LayerMap_DevIdx[sectionIdx] = StringToInt(value)
            end
         end

      // --- PERMANENT parsing ---
      elsif Left(trimmedLine, 11) == "[PERMANENT:" then
         currentSection = "PERMANENT"
         sectionIdx = StringToInt(Mid(trimmedLine, 12, Pos("}", trimmedLine) - 12))
         Permanent_Count = Max(Permanent_Count, sectionIdx + 1)

      elsif currentSection == "PERMANENT" then
         eqPos = Pos("=", trimmedLine)
         if eqPos > 0 then
            key = Trim(Left(trimmedLine, eqPos - 1))
            value = Trim(Mid(trimmedLine, eqPos + 1, 999))
            if key == "Device" then
               Permanent_DevIdx[sectionIdx] = StringToInt(value)
            elsif key == "Source" then
               Permanent_Source[sectionIdx] = value
            elsif key == "Function" then
               Permanent_Function[sectionIdx] = value
            end
         end

      // --- OVERLAY parsing ---
      elsif Left(trimmedLine, 9) == "[OVERLAY:" then
         currentSection = "OVERLAY"
         sectionIdx = StringToInt(Mid(trimmedLine, 10, Pos("}", trimmedLine) - 10))
         Overlay_Count = Max(Overlay_Count, sectionIdx + 1)

      elsif currentSection == "OVERLAY" then
         eqPos = Pos("=", trimmedLine)
         if eqPos > 0 then
            key = Trim(Left(trimmedLine, eqPos - 1))
            value = Trim(Mid(trimmedLine, eqPos + 1, 999))
            if key == "Device" then
               Overlay_DevIdx[sectionIdx] = StringToInt(value)
            elsif key == "Layer" then
               Overlay_Layer[sectionIdx] = StringToInt(value)
            elsif key == "Action" then
               Overlay_Action[sectionIdx] = value
            end
         end
```

- [ ] **Step 2: Add Trace output for parsed layer config**

At the end of `ParseDeviceConfig()`, add diagnostic output:

```gpscript
   if DebugMode then
      Trace("LAYERSWITCH: " + IntToString(LayerSwitch_Count) + " switches parsed")
      var sw : Integer
      For sw = 0; sw < LayerSwitch_Count; sw = sw + 1
         Trace("  Switch " + IntToString(sw) + ": " + LayerSwitch_Label[sw] + " [" + LayerSwitch_Type[sw] + "]")
      End
      Trace("PERMANENT: " + IntToString(Permanent_Count) + " bindings parsed")
      Trace("OVERLAY: " + IntToString(Overlay_Count) + " actions parsed")
   end
```

- [ ] **Step 3: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(parser): extend ParseDeviceConfig for LAYERSWITCH, LAYERMAP, PERMANENT, OVERLAY"
```

---

### Task 3: Unified ControllerMap Parser — Core Line Parser

**Location:** SECTION 17 (Controller Map Engine, ~line 2817)

Write the new line parser that handles the unified v2 syntax. This function parses a single `MacroN = ...` line into the internal structures.

- [ ] **Step 1: Write ParseMacroSource() helper**

Parses the `DEV0:SLD3 & DEV1:SLD1` source part. Place before the main parser function.

```gpscript
// Parses "DEV0:SLD3 & DEV1:SLD1" into Mac_Source* arrays for the given macroIdx
// Returns the number of sources parsed
Function ParseMacroSource(macroIdx : Integer, sourceStr : String) Returns Integer
   var count, devNum, ctrlNum : Integer; var parts : String; var remaining : String
   var onePart, devPart, typePart : String; var ampPos, colonPos : Integer
   count = 0
   remaining = Trim(sourceStr)

   // Loop through "&"-separated sources
   ampPos = Pos("&", remaining)
   if ampPos < 1 then
      // Single source
      onePart = Trim(remaining)
      remaining = ""
   else
      onePart = Trim(Left(remaining, ampPos - 1))
      remaining = Trim(Mid(remaining, ampPos + 1, 999))
   end

   // Parse first source and continue with remaining
   // Pattern: DEV<n>:<TYPE><n>
   if Left(onePart, 3) == "DEV" then
      colonPos = Pos(":", onePart)
      if colonPos > 0 then
         devNum = StringToInt(Mid(onePart, 4, colonPos - 4))
         typePart = Mid(onePart, colonPos + 1, 3)
         ctrlNum = StringToInt(Mid(onePart, colonPos + 4, 999))
         Mac_SourceDev[MacSourceIdx(macroIdx, count)] = devNum
         Mac_SourceType[MacSourceIdx(macroIdx, count)] = typePart
         Mac_SourceCtrl[MacSourceIdx(macroIdx, count)] = ctrlNum
         count = count + 1
      end
   end

   // Parse remaining sources (if any)
   if Length(remaining) > 0 then
      ampPos = Pos("&", remaining)
      if ampPos < 1 then
         onePart = Trim(remaining)
         remaining = ""
      else
         onePart = Trim(Left(remaining, ampPos - 1))
         remaining = Trim(Mid(remaining, ampPos + 1, 999))
      end
      if Left(onePart, 3) == "DEV" then
         colonPos = Pos(":", onePart)
         if colonPos > 0 then
            devNum = StringToInt(Mid(onePart, 4, colonPos - 4))
            typePart = Mid(onePart, colonPos + 1, 3)
            ctrlNum = StringToInt(Mid(onePart, colonPos + 4, 999))
            Mac_SourceDev[MacSourceIdx(macroIdx, count)] = devNum
            Mac_SourceType[MacSourceIdx(macroIdx, count)] = typePart
            Mac_SourceCtrl[MacSourceIdx(macroIdx, count)] = ctrlNum
            count = count + 1
         end
      end
      // Handle 3rd and 4th source with same pattern if remaining not empty
      if Length(remaining) > 0 then
         onePart = Trim(remaining)
         if Left(onePart, 3) == "DEV" then
            colonPos = Pos(":", onePart)
            if colonPos > 0 then
               devNum = StringToInt(Mid(onePart, 4, colonPos - 4))
               typePart = Mid(onePart, colonPos + 1, 3)
               ctrlNum = StringToInt(Mid(onePart, colonPos + 4, 999))
               Mac_SourceDev[MacSourceIdx(macroIdx, count)] = devNum
               Mac_SourceType[MacSourceIdx(macroIdx, count)] = typePart
               Mac_SourceCtrl[MacSourceIdx(macroIdx, count)] = ctrlNum
               count = count + 1
            end
         end
      end
   end

   Mac_SourceCount[macroIdx] = count
   Result = count
End
```

- [ ] **Step 2: Write ParseSingleBinding() helper**

Parses one binding token like `VST1_GRS:48:Filter Cutoff{0.0,1.0}` or `LAY1:ROOT:CH3{1.0,1.0}` or `CROSSFADER`.

```gpscript
// Parses a single binding token and stores it at the given flat index
// Returns the detected layer index (0 if no LAY prefix, -1 on error)
Function ParseSingleBinding(macroIdx : Integer, token : String, targetLayerIdx : Integer, bindIdx : Integer) Returns Integer
   var trimmed, rest : String; var layerIdx, flatIdx : Integer
   var bracePos, colonPos, colonPos2 : Integer
   var rangeMin, rangeMax : Double; rangeMin = 0.0; rangeMax = 1.0
   var targetType, target, label : String
   var vstIdx, paramIdx, chIdx : Integer

   trimmed = Trim(token)
   layerIdx = targetLayerIdx

   // Check for LAY prefix: "LAY1:..."
   if Left(trimmed, 3) == "LAY" then
      colonPos = Pos(":", trimmed)
      if colonPos > 0 then
         layerIdx = StringToInt(Mid(trimmed, 4, colonPos - 4))
         trimmed = Mid(trimmed, colonPos + 1, 999)
      end
   end

   // Extract range {min,max} if present
   bracePos = Pos("{", trimmed)
   if bracePos > 0 then
      var rangeStr, commaStr : String; var commaPos : Integer
      rangeStr = Mid(trimmed, bracePos + 1, Pos("}", trimmed) - bracePos - 1)
      commaPos = Pos(",", rangeStr)
      if commaPos > 0 then
         rangeMin = StringToDouble(Trim(Left(rangeStr, commaPos - 1)))
         rangeMax = StringToDouble(Trim(Mid(rangeStr, commaPos + 1, 999)))
      end
      trimmed = Trim(Left(trimmed, bracePos - 1))
   end

   flatIdx = MacLayerBindIdx(macroIdx, layerIdx, bindIdx)

   // Classify target type
   if Left(trimmed, 3) == "VST" then
      targetType = "VST"
      // Parse VST<k>[_GRS]:<paramIdx>[:<label>]
      colonPos = Pos(":", trimmed)
      if colonPos > 0 then
         var vstPart : String
         vstPart = Left(trimmed, colonPos - 1)
         rest = Mid(trimmed, colonPos + 1, 999)
         // Extract VST index from "VST1" or "VST1_GRS"
         if Pos("_GRS", vstPart) > 0 then
            vstIdx = StringToInt(Mid(vstPart, 4, Pos("_", vstPart) - 4))
         else
            vstIdx = StringToInt(Mid(vstPart, 4, 999))
         end
         // Parse paramIdx and optional label
         colonPos2 = Pos(":", rest)
         if colonPos2 > 0 then
            paramIdx = StringToInt(Left(rest, colonPos2 - 1))
            label = Mid(rest, colonPos2 + 1, 999)
         else
            paramIdx = StringToInt(rest)
            label = ""
         end
         Mac_Layer_VSTIdx[flatIdx] = vstIdx
         Mac_Layer_ParamIdx[flatIdx] = paramIdx
         Mac_Layer_ParamLabel[flatIdx] = label
      end
      Mac_Layer_Target[flatIdx] = trimmed

   elsif Left(trimmed, 2) == "Ch" and Pos(":CC", trimmed) > 0 then
      targetType = "CC"
      Mac_Layer_Target[flatIdx] = trimmed

   elsif Left(trimmed, 7) == "SYSACT_" then
      targetType = "SYSACT"
      Mac_Layer_Target[flatIdx] = trimmed

   elsif trimmed == "CROSSFADER" or trimmed == "SCRUBBER" or trimmed == "SYSTEM_TOGGLE"
         or trimmed == "VST_SCOPE" or trimmed == "VST_BROWSE"
         or trimmed == "VST_SCOPE_PREV" or trimmed == "VST_SCOPE_NEXT"
         or trimmed == "VST_PREV" or trimmed == "VST_NEXT"
         or trimmed == "SYSMODE_CYCLE" or trimmed == "SYSMODE_SELECT"
         or trimmed == "REC_SONGPART" then
      targetType = "KEYWORD"
      Mac_Layer_Target[flatIdx] = trimmed

   elsif Pos(":CH", trimmed) > 0 then
      // Overlay function: SMART_SOLO:CH3, ROOT:CH11, etc.
      targetType = "OVERLAY"
      colonPos = Pos(":CH", trimmed)
      Mac_Layer_Target[flatIdx] = Left(trimmed, colonPos - 1)  // function name
      Mac_Layer_Channel[flatIdx] = StringToInt(Mid(trimmed, colonPos + 3, 999))

   else
      // Unknown or keyword without standard match (e.g. CHANNEL_BOUND_LFO)
      targetType = "KEYWORD"
      Mac_Layer_Target[flatIdx] = trimmed
   end

   Mac_Layer_TargetType[flatIdx] = targetType
   Mac_Layer_RangeMin[flatIdx] = rangeMin
   Mac_Layer_RangeMax[flatIdx] = rangeMax

   Result = layerIdx
End
```

- [ ] **Step 3: Write ParseMacroLine() — the main line parser**

Parses a complete `MacroN = DEV0:BTN1; VST1_GRS:48 | LAY1:ROOT:CH1{1.0,1.0}` line.

```gpscript
// Parses one MacroN = ... line, stores into Mac_* arrays (active or default based on isDefault)
Function ParseMacroLine(line : String, isDefault : Boolean)
   var eqPos, semiPos, pipePos : Integer
   var leftPart, rightPart, sourceStr, bindingsStr : String
   var macroIdx, layerIdx, bindIdx : Integer
   var token : String; var remaining : String
   var hasSource : Boolean = false; var parsedLayer : Integer

   // Parse "MacroN = ..."
   eqPos = Pos("=", line)
   if eqPos < 1 then
      // Skip malformed lines
   else
      leftPart = Trim(Left(line, eqPos - 1))
      rightPart = Trim(Mid(line, eqPos + 1, 999))

      // Extract macro index from "Macro13"
      if Left(leftPart, 5) == "Macro" then
         macroIdx = StringToInt(Mid(leftPart, 6, 999))
      else
         // Not a Macro line (maybe VST declaration), skip
      end

      if macroIdx >= 1 and macroIdx <= MAX_MACROS then
         // Check for DEV source (before ";")
         semiPos = Pos(";", rightPart)
         if semiPos > 0 then
            sourceStr = Trim(Left(rightPart, semiPos - 1))
            bindingsStr = Trim(Mid(rightPart, semiPos + 1, 999))
            hasSource = true
         else
            // No DEV source — just bindings
            bindingsStr = rightPart
         end

         // Parse source if present
         if hasSource then
            var dummy : Integer
            dummy = ParseMacroSource(macroIdx, sourceStr)
         end

         // Parse pipe-separated bindings
         remaining = bindingsStr
         // Track bind counts per layer for this macro
         var layerBindCounts : Integer Array = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
         var hasLayerData : Boolean Array = [false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false]

         pipePos = Pos("|", remaining)
         if pipePos < 1 then
            token = Trim(remaining)
            remaining = ""
         else
            token = Trim(Left(remaining, pipePos - 1))
            remaining = Trim(Mid(remaining, pipePos + 1, 999))
         end

         if Length(token) > 0 then
            // Determine which layer this binding belongs to
            if Left(Trim(token), 3) == "LAY" then
               var detectedLayer : Integer
               detectedLayer = StringToInt(Mid(Trim(token), 4, Pos(":", Trim(token)) - 4))
               parsedLayer = ParseSingleBinding(macroIdx, token, detectedLayer, layerBindCounts[detectedLayer])
               layerBindCounts[detectedLayer] = layerBindCounts[detectedLayer] + 1
               hasLayerData[detectedLayer] = true
            else
               // No LAY prefix = LAY0
               parsedLayer = ParseSingleBinding(macroIdx, token, 0, layerBindCounts[0])
               layerBindCounts[0] = layerBindCounts[0] + 1
               hasLayerData[0] = true
            end
         end

         // Continue parsing remaining tokens
         // (Unrolled loop since GPScript has no while — use sufficient iterations)
         var iteration : Integer
         For iteration = 0; iteration < 20; iteration = iteration + 1
            if Length(remaining) > 0 then
               pipePos = Pos("|", remaining)
               if pipePos < 1 then
                  token = Trim(remaining)
                  remaining = ""
               else
                  token = Trim(Left(remaining, pipePos - 1))
                  remaining = Trim(Mid(remaining, pipePos + 1, 999))
               end
               if Length(token) > 0 then
                  if Left(Trim(token), 3) == "LAY" then
                     var detectedLayer2 : Integer
                     detectedLayer2 = StringToInt(Mid(Trim(token), 4, Pos(":", Trim(token)) - 4))
                     parsedLayer = ParseSingleBinding(macroIdx, token, detectedLayer2, layerBindCounts[detectedLayer2])
                     layerBindCounts[detectedLayer2] = layerBindCounts[detectedLayer2] + 1
                     hasLayerData[detectedLayer2] = true
                  else
                     parsedLayer = ParseSingleBinding(macroIdx, token, 0, layerBindCounts[0])
                     layerBindCounts[0] = layerBindCounts[0] + 1
                     hasLayerData[0] = true
                  end
               end
            end
         End

         // Update bind counts
         var li : Integer
         For li = 0; li < MAX_LAYERS; li = li + 1
            if hasLayerData[li] then
               Mac_Layer_BindCount[MacLayerIdx(macroIdx, li)] = layerBindCounts[li]
            end
         End

         // If storing to default, copy to Def_* arrays
         if isDefault then
            Def_Mac_SourceCount[macroIdx] = Mac_SourceCount[macroIdx]
            var si : Integer
            For si = 0; si < Mac_SourceCount[macroIdx]; si = si + 1
               Def_Mac_SourceDev[MacSourceIdx(macroIdx, si)] = Mac_SourceDev[MacSourceIdx(macroIdx, si)]
               Def_Mac_SourceType[MacSourceIdx(macroIdx, si)] = Mac_SourceType[MacSourceIdx(macroIdx, si)]
               Def_Mac_SourceCtrl[MacSourceIdx(macroIdx, si)] = Mac_SourceCtrl[MacSourceIdx(macroIdx, si)]
            End
            For li = 0; li < MAX_LAYERS; li = li + 1
               Def_Mac_Layer_BindCount[MacLayerIdx(macroIdx, li)] = Mac_Layer_BindCount[MacLayerIdx(macroIdx, li)]
               var bi : Integer
               For bi = 0; bi < layerBindCounts[li]; bi = bi + 1
                  var fi : Integer
                  fi = MacLayerBindIdx(macroIdx, li, bi)
                  Def_Mac_Layer_TargetType[fi] = Mac_Layer_TargetType[fi]
                  Def_Mac_Layer_Target[fi] = Mac_Layer_Target[fi]
                  Def_Mac_Layer_RangeMin[fi] = Mac_Layer_RangeMin[fi]
                  Def_Mac_Layer_RangeMax[fi] = Mac_Layer_RangeMax[fi]
                  Def_Mac_Layer_Channel[fi] = Mac_Layer_Channel[fi]
                  Def_Mac_Layer_VSTIdx[fi] = Mac_Layer_VSTIdx[fi]
                  Def_Mac_Layer_ParamIdx[fi] = Mac_Layer_ParamIdx[fi]
                  Def_Mac_Layer_ParamLabel[fi] = Mac_Layer_ParamLabel[fi]
               End
            End
         end
      end
   end
End
```

- [ ] **Step 4: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(parser): unified macro line parser with source, binding, and layer extraction"
```

---

### Task 4: LoadControllerMapV2() — Default Map + Song Map with Per-Layer Merge

**Location:** SECTION 17, replace `LoadControllerMap()` (~line 6946)

- [ ] **Step 1: Write CloneDefaultToActive() helper**

```gpscript
// Copies all Def_Mac_* arrays into Mac_* (active) arrays
Function CloneDefaultToActive()
   var m, s, l, b, fi : Integer
   For m = 1; m <= MAX_MACROS; m = m + 1
      Mac_SourceCount[m] = Def_Mac_SourceCount[m]
      For s = 0; s < MAX_SOURCES_PER_MACRO; s = s + 1
         Mac_SourceDev[MacSourceIdx(m, s)] = Def_Mac_SourceDev[MacSourceIdx(m, s)]
         Mac_SourceType[MacSourceIdx(m, s)] = Def_Mac_SourceType[MacSourceIdx(m, s)]
         Mac_SourceCtrl[MacSourceIdx(m, s)] = Def_Mac_SourceCtrl[MacSourceIdx(m, s)]
      End
      For l = 0; l < MAX_LAYERS; l = l + 1
         Mac_Layer_BindCount[MacLayerIdx(m, l)] = Def_Mac_Layer_BindCount[MacLayerIdx(m, l)]
         For b = 0; b < MAX_BINDINGS_PER_LAYER; b = b + 1
            fi = MacLayerBindIdx(m, l, b)
            Mac_Layer_TargetType[fi] = Def_Mac_Layer_TargetType[fi]
            Mac_Layer_Target[fi] = Def_Mac_Layer_Target[fi]
            Mac_Layer_RangeMin[fi] = Def_Mac_Layer_RangeMin[fi]
            Mac_Layer_RangeMax[fi] = Def_Mac_Layer_RangeMax[fi]
            Mac_Layer_Channel[fi] = Def_Mac_Layer_Channel[fi]
            Mac_Layer_VSTIdx[fi] = Def_Mac_Layer_VSTIdx[fi]
            Mac_Layer_ParamIdx[fi] = Def_Mac_Layer_ParamIdx[fi]
            Mac_Layer_ParamLabel[fi] = Def_Mac_Layer_ParamLabel[fi]
         End
      End
   End
   // Clone VST declarations
   For m = 0; m < MAX_VST_DECL; m = m + 1
      MapVST_Name[m] = DefMapVST_Name[m]
   End
End
```

- [ ] **Step 2: Write ValidateMapVSTs() helper**

```gpscript
// Validates declared VSTs against loaded plugins
Function ValidateMapVSTs()
   var v : Integer; var loadedName : String
   For v = 0; v < MAX_VST_DECL; v = v + 1
      if Length(MapVST_Name[v]) > 0 then
         if MapVST_Name[v] == "*" then
            MapVST_Valid[v] = 1  // wildcard = always valid
         else
            loadedName = GetPluginName(BLK_VST[v])
            if Length(loadedName) == 0 then
               MapVST_Valid[v] = 3  // not loaded
            elsif loadedName == MapVST_Name[v] then
               MapVST_Valid[v] = 1  // valid
            else
               MapVST_Valid[v] = 2  // mismatch
            end
         end
      else
         MapVST_Valid[v] = 0  // not declared
      end
   End
End
```

- [ ] **Step 3: Write LoadControllerMapV2() — main entry point**

```gpscript
// Loads controller map: parses [Map:Default] once at startup, then song maps on switch
// On first call (initialization): reads entire file, parses Default, stores to Def_*
// On song switch: clones Default, parses song map as delta with per-layer merge
Function LoadControllerMapV2(mapName : String)
   var filePath, line, trimmedLine, currentMap : String
   var eqPos : Integer; var key, value : String
   var inDefaultMap, inTargetMap, isFirstLoad : Boolean
   var savedEditScope : Integer

   // Preserve CurrentEditScope (known side-effect)
   savedEditScope = CurrentEditScope

   filePath = UserSnapshotPath + "/ControllerMaps_v2.txt"
   
   if mapName == "DEFAULT_INIT" then
      isFirstLoad = true
   else
      isFirstLoad = false
      // Clone default as base
      CloneDefaultToActive()
   end

   // Read file
   if OpenFile(filePath) then
      inDefaultMap = false
      inTargetMap = false
      currentMap = ""

      line = ReadLineFromFile()
      var lineCount : Integer
      For lineCount = 0; lineCount < 10000; lineCount = lineCount + 1
         if Length(line) >= 0 then
            trimmedLine = Trim(line)

            // Skip comments and empty lines
            if Length(trimmedLine) > 0 and Left(trimmedLine, 1) <> ";" then

               // Section header
               if Left(trimmedLine, 1) == "[" then
                  if trimmedLine == "[Map:Default]" then
                     inDefaultMap = true
                     inTargetMap = false
                     currentMap = "Default"
                  elsif Left(trimmedLine, 5) == "[Map:" then
                     currentMap = Mid(trimmedLine, 6, Length(trimmedLine) - 6)
                     inDefaultMap = false
                     if not isFirstLoad and currentMap == mapName then
                        inTargetMap = true
                     else
                        inTargetMap = false
                     end
                  end

               // Content lines
               elsif inDefaultMap and isFirstLoad then
                  // Parse VST declarations
                  if Left(trimmedLine, 3) == "VST" and Pos("=", trimmedLine) > 0 then
                     eqPos = Pos("=", trimmedLine)
                     key = Trim(Left(trimmedLine, eqPos - 1))
                     value = Trim(Mid(trimmedLine, eqPos + 1, 999))
                     if Left(key, 3) == "VST" then
                        var vstDeclIdx : Integer
                        vstDeclIdx = StringToInt(Mid(key, 4, 999))
                        if vstDeclIdx >= 1 and vstDeclIdx <= MAX_VST_DECL then
                           DefMapVST_Name[vstDeclIdx] = value
                        end
                     end
                  // Parse Macro lines
                  elsif Left(trimmedLine, 5) == "Macro" then
                     ParseMacroLine(trimmedLine, true)
                  end

               elsif inTargetMap and not isFirstLoad then
                  // Parse song-specific overrides (delta)
                  if Left(trimmedLine, 3) == "VST" and Pos("=", trimmedLine) > 0 then
                     eqPos = Pos("=", trimmedLine)
                     key = Trim(Left(trimmedLine, eqPos - 1))
                     value = Trim(Mid(trimmedLine, eqPos + 1, 999))
                     if Left(key, 3) == "VST" then
                        var vstDeclIdx2 : Integer
                        vstDeclIdx2 = StringToInt(Mid(key, 4, 999))
                        if vstDeclIdx2 >= 1 and vstDeclIdx2 <= MAX_VST_DECL then
                           MapVST_Name[vstDeclIdx2] = value
                        end
                     end
                  elsif Left(trimmedLine, 5) == "Macro" then
                     // Per-layer merge: ParseMacroLine only overwrites layers it finds
                     ParseMacroLine(trimmedLine, false)
                  end
               end
            end

            line = ReadLineFromFile()
         end
      End
      CloseFile()
   end

   // Validate VSTs
   ValidateMapVSTs()

   // Rebuild reverse lookups
   RebuildReverseLookups()

   // Update display
   UpdateControllerInfoDisplay()

   CurrentCtrlMapName = mapName

   // Restore CurrentEditScope
   CurrentEditScope = savedEditScope
End
```

- [ ] **Step 4: Write RebuildReverseLookups()**

```gpscript
// Rebuilds CC reverse lookup and SysAction reverse lookup from active Mac_* arrays
Function RebuildReverseLookups()
   var m, b, fi : Integer; var cc, ch : Integer
   
   // Clear reverse lookups
   For m = 0; m < 2048; m = m + 1
      Mac_ReverseLookup_CC[m] = -1
   End
   For m = 0; m < MAX_MACROS; m = m + 1
      Mac_ReverseLookup_SysAct[m] = -1
   End

   // Build from active bindings (LAY0 only for reverse CC lookup)
   For m = 1; m <= MAX_MACROS; m = m + 1
      var bindCount : Integer
      bindCount = Mac_Layer_BindCount[MacLayerIdx(m, 0)]
      For b = 0; b < bindCount; b = b + 1
         fi = MacLayerBindIdx(m, 0, b)
         if Mac_Layer_TargetType[fi] == "SYSACT" then
            // Check isolation rule: SYSACT must be sole binding on LAY0
            if bindCount == 1 then
               var actionIdx : Integer
               actionIdx = SysActIdx(Mid(Mac_Layer_Target[fi], 8, 999))
               if actionIdx >= 0 then
                  Mac_ReverseLookup_SysAct[m] = actionIdx
               end
            end
         end
      End
   End

   // Build source-to-macro CC lookup from Mac_Source* + DeviceConfig
   // Maps (deviceChannel * 128 + ccNumber) → macroIdx
   For m = 1; m <= MAX_MACROS; m = m + 1
      var srcCount : Integer
      srcCount = Mac_SourceCount[m]
      For b = 0; b < srcCount; b = b + 1
         var devIdx, ctrlIdx : Integer; var srcType : String
         devIdx = Mac_SourceDev[MacSourceIdx(m, b)]
         srcType = Mac_SourceType[MacSourceIdx(m, b)]
         ctrlIdx = Mac_SourceCtrl[MacSourceIdx(m, b)]
         // Resolve physical CC from DeviceConfig CONTROL registry
         // This connects the logical DEV0:SLD3 to the physical Ch/CC
         var physCC, physCh : Integer
         physCC = ResolveControlCC(devIdx, srcType, ctrlIdx)
         physCh = ResolveControlChannel(devIdx, srcType, ctrlIdx)
         if physCC >= 0 and physCh >= 0 then
            Mac_ReverseLookup_CC[physCh * 128 + physCC] = m
         end
      End
   End
End
```

- [ ] **Step 5: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(parser): LoadControllerMapV2 with Default inheritance, per-layer merge, VST validation"
```

---

### Task 5: Remove LoadHardwareMap() and Wire Up Initialization

**Location:** SECTION 14 (~line 3577) and Initialization block (~line 13446)

- [ ] **Step 1: Comment out LoadHardwareMap() function body**

At line 3577, replace the body of `LoadHardwareMap()` with a stub that traces the deprecation:

```gpscript
Function LoadHardwareMap()
   // DEPRECATED: Hardware sources are now inline in ControllerMaps_v2.txt
   // This function is kept as stub for call-site compatibility
   if DebugMode then
      Trace("LoadHardwareMap: SKIPPED (v2 unified format)")
   end
End
```

- [ ] **Step 2: Wire up initialization sequence**

In the initialization block (~line 13508), after `ParseDeviceConfig()`:

```gpscript
   // Phase 2b: Parse Default controller map (one-time)
   LoadControllerMapV2("DEFAULT_INIT")
```

And in `On Song` callback (~line 15591), replace the existing `LoadControllerMap(mapName)` call with:

```gpscript
   LoadControllerMapV2(mapName)
```

- [ ] **Step 3: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(init): wire LoadControllerMapV2 into startup and song switch, deprecate LoadHardwareMap"
```

---

### Task 6: LBL_ControllerInfo Hierarchical Display

**Location:** SECTION 17, replace `UpdateControllerInfoDisplay()` (~line 3090)

- [ ] **Step 1: Rewrite UpdateControllerInfoDisplay()**

Replace the existing function with the new hierarchical format:

```gpscript
Function UpdateControllerInfoDisplay()
   var lineIdx, m, l, b, fi, v : Integer
   var devName, srcDesc, layerLabel : String
   lineIdx = 0

   // Header
   CtrlInfo_Lines[lineIdx] = "--- MAPPING: " + CurrentCtrlMapName + " ---"
   lineIdx = lineIdx + 1

   // VST validation status
   For v = 1; v < MAX_VST_DECL; v = v + 1
      if MapVST_Valid[v] > 0 then
         var statusStr : String
         if MapVST_Valid[v] == 1 then
            statusStr = "[OK]"
         elsif MapVST_Valid[v] == 2 then
            statusStr = "[MISMATCH]"
         elsif MapVST_Valid[v] == 3 then
            statusStr = "[NOT LOADED]"
         else
            statusStr = ""
         end
         CtrlInfo_Lines[lineIdx] = "VST" + IntToString(v) + ": " + MapVST_Name[v] + "  " + statusStr
         lineIdx = lineIdx + 1
      end
   End
   CtrlInfo_Lines[lineIdx] = ""
   lineIdx = lineIdx + 1

   // User Macros (1-50) with hierarchy
   For m = 1; m <= 50; m = m + 1
      // Check if macro has any bindings
      var hasAny : Boolean = false
      For l = 0; l < MAX_LAYERS; l = l + 1
         if Mac_Layer_BindCount[MacLayerIdx(m, l)] > 0 then
            hasAny = true
         end
      End
      if hasAny or Mac_SourceCount[m] > 0 then
         // Source description
         if Mac_SourceCount[m] > 0 then
            var devIdx : Integer
            devIdx = Mac_SourceDev[MacSourceIdx(m, 0)]
            devName = DEV_Name[devIdx]
            srcDesc = devName + ":" + Mac_SourceType[MacSourceIdx(m, 0)] + IntToString(Mac_SourceCtrl[MacSourceIdx(m, 0)])
         else
            srcDesc = "?"
         end
         CtrlInfo_Lines[lineIdx] = "Macro " + IntToString(m) + " [" + srcDesc + "]:"
         lineIdx = lineIdx + 1

         // LAY0: show as "(N Targets)" with sub-lines
         var lay0Count : Integer
         lay0Count = Mac_Layer_BindCount[MacLayerIdx(m, 0)]
         if lay0Count > 0 then
            CtrlInfo_Lines[lineIdx] = "  LAY0: (" + IntToString(lay0Count) + " Target" + IIFs(lay0Count > 1, "s", "") + ")"
            lineIdx = lineIdx + 1
            For b = 0; b < lay0Count; b = b + 1
               fi = MacLayerBindIdx(m, 0, b)
               var targetDesc : String
               targetDesc = Mac_Layer_Target[fi]
               if Length(Mac_Layer_ParamLabel[fi]) > 0 then
                  targetDesc = targetDesc + " " + Mac_Layer_ParamLabel[fi]
               end
               if Mac_Layer_RangeMin[fi] <> 0.0 or Mac_Layer_RangeMax[fi] <> 1.0 then
                  targetDesc = targetDesc + " {" + DoubleToString(Mac_Layer_RangeMin[fi], 1) + "," + DoubleToString(Mac_Layer_RangeMax[fi], 1) + "}"
               end
               // Check VST validity
               if Mac_Layer_TargetType[fi] == "VST" then
                  var vstV : Integer
                  vstV = Mac_Layer_VSTIdx[fi]
                  if vstV >= 1 and vstV < MAX_VST_DECL then
                     if MapVST_Valid[vstV] > 1 then
                        targetDesc = targetDesc + "  [BLOCKED: VST" + IntToString(vstV) + " invalid]"
                     end
                  end
               end
               CtrlInfo_Lines[lineIdx] = "    -> " + targetDesc
               lineIdx = lineIdx + 1
            End
         end

         // LAY1-N: single line each
         For l = 1; l < MAX_LAYERS; l = l + 1
            var layBindCount : Integer
            layBindCount = Mac_Layer_BindCount[MacLayerIdx(m, l)]
            if layBindCount > 0 then
               fi = MacLayerBindIdx(m, l, 0)
               var overlayDesc : String
               overlayDesc = Mac_Layer_Target[fi]
               if Mac_Layer_TargetType[fi] == "OVERLAY" then
                  overlayDesc = overlayDesc + ":CH" + IntToString(Mac_Layer_Channel[fi])
               end
               if Mac_Layer_RangeMin[fi] <> 0.0 or Mac_Layer_RangeMax[fi] <> 1.0 then
                  overlayDesc = overlayDesc + " {" + DoubleToString(Mac_Layer_RangeMin[fi], 1) + "," + DoubleToString(Mac_Layer_RangeMax[fi], 1) + "}"
               end
               CtrlInfo_Lines[lineIdx] = "  LAY" + IntToString(l) + ": " + overlayDesc
               lineIdx = lineIdx + 1
            end
         End
      end
   End

   // CC Bindings (Permanent)
   CtrlInfo_Lines[lineIdx] = ""
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = "--- CC BINDINGS (Permanent) ---"
   lineIdx = lineIdx + 1
   var p : Integer
   For p = 0; p < Permanent_Count; p = p + 1
      CtrlInfo_Lines[lineIdx] = Permanent_Source[p] + ": " + Permanent_Function[p]
      lineIdx = lineIdx + 1
   End

   // System Macro Groups
   CtrlInfo_Lines[lineIdx] = ""
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = "--- SYSTEM MACRO GROUPS ---"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 51-66: Looper (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 67-82: Smart Solo (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 83-98: Strict Solo (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 99-114: User Mute (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 115-130: Velocity Range (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 131-146: Root/Chord (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 147-162: Octaver (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 163-178: Humanizer (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 179-194: Scale Quantizer (Ch 1-16) <<"
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = ">> Macro 195-210: Auto Sustain (Ch 1-16) <<"
   lineIdx = lineIdx + 1

   // Hardware Assignments
   CtrlInfo_Lines[lineIdx] = ""
   lineIdx = lineIdx + 1
   CtrlInfo_Lines[lineIdx] = "--- HARDWARE ASSIGNMENTS ---"
   lineIdx = lineIdx + 1
   For m = 1; m <= MAX_MACROS; m = m + 1
      if Mac_SourceCount[m] > 0 then
         var devIdx2 : Integer; var hwDesc : String
         devIdx2 = Mac_SourceDev[MacSourceIdx(m, 0)]
         hwDesc = DEV_Name[devIdx2] + ":" + Mac_SourceType[MacSourceIdx(m, 0)] + IntToString(Mac_SourceCtrl[MacSourceIdx(m, 0)])
         if Mac_SourceCount[m] > 1 then
            var s2 : Integer
            For s2 = 1; s2 < Mac_SourceCount[m]; s2 = s2 + 1
               devIdx2 = Mac_SourceDev[MacSourceIdx(m, s2)]
               hwDesc = hwDesc + " & " + DEV_Name[devIdx2] + ":" + Mac_SourceType[MacSourceIdx(m, s2)] + IntToString(Mac_SourceCtrl[MacSourceIdx(m, s2)])
            End
         end
         CtrlInfo_Lines[lineIdx] = "Macro " + IntToString(m) + " = " + hwDesc
         lineIdx = lineIdx + 1
      end
   End

   // Fill remaining lines
   For m = lineIdx; m < 300; m = m + 1
      CtrlInfo_Lines[m] = ""
   End

   CtrlInfo_LineCount = lineIdx
   RefreshCtrlInfoDisplay()
End
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(display): hierarchical LBL_ControllerInfo with VST status and layer breakdown"
```

---

### Task 7: BTN_SmartAdapt — VST-Name Based Map Lookup

**Location:** Wherever `BTN_SmartAdapt` handler is (~SECTION 25-26 callbacks)

- [ ] **Step 1: Update SmartAdapt handler**

Find the existing `On WidgetValueChanged` handler for `BTN_SmartAdapt` and update the map lookup logic:

```gpscript
   // Old: mapName = "Standard_VST" + IntToString(CurrentVstScope + 1)
   // New: lookup by VST plugin name
   var pluginName : String
   pluginName = GetPluginName(BLK_VST[CurrentVstScope])
   if Length(pluginName) > 0 then
      // Search for [Map:<pluginName>] in the file
      var foundMap : Boolean = false
      // Check if map exists by attempting to load — LoadControllerMapV2 handles "not found"
      LoadControllerMapV2(pluginName)
      if DebugMode then
         Trace("SmartAdapt: Searching for [Map:" + pluginName + "]")
      end
   end
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "feat(smartadapt): VST-name based map lookup instead of slot number"
```

---

### Task 8: Bump SCRIPT_VERSION

- [ ] **Step 1: Bump SCRIPT_VERSION in SECTION 1**

```gpscript
   SCRIPT_VERSION : String = "2026-04-12-A"
```

- [ ] **Step 2: Commit**

```
git add "Global Rackspace.gpscript"
git commit -m "chore: bump SCRIPT_VERSION for Plan A completion"
```
