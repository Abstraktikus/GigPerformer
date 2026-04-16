# SET Keyword + CC Cache: Initial Values for BLK_VSTControl

**Date:** 2026-04-16
**Status:** Approved
**Scope:** ControllerMap parser, CC routing, hardware sync

## Problem

1. **CC-Targets haben keine Initialwerte.** `SyncArrangerToCurrentMap()` setzt CC-gebundene Macros blind auf 50% (Zeile 4762), weil GP keine API hat um den aktuellen CC-Wert eines Reglers abzufragen.
2. **Script-generierte CCs erreichen das VST nicht.** `DispatchMacro()` sendet CC-Targets nur an `SendNowToMidiOutDevice` (Arranger), nicht an `BLK_VSTControl`. *(Bereits gefixt in dieser Session, Zeile 12361.)*

## Design

### Komponente 1: `SET` Keyword in `{...}` Specs

Erweiterung der bestehenden Binding-Spec-Syntax um ein optionales `SET`-Keyword. Der Initialwert wird beim Laden der ControllerMap sofort angewendet.

#### Syntax

Das Keyword ist ein zusaetzliches Token in den bestehenden `{...}` Specs, komma-separiert wie `OTZ`, `MAX`, `DIR`, `RESET`:

**CC-Target** (Wert in nativen MIDI-Units 0-127):
```
Macro20 = DEV0:LAY1:Enc5; Ch11:CC19 {0.0, 1.0, SET56}
```

**VST-Target** (Wert in GP-Parameter-Units 0.0-1.0):
```
Macro10 = DEV0:LAY0:Fader4; VST1_GRS:0:Level (p1) {0.000, 0.289, SET0.156}
```

**Overlay/Boolean** (ON/OFF):
```
SMART_SOLO:CH1 {OTZ, MAX, SET:ON}
```

#### Parser-Erweiterung

In `ParseSingleBinding()` (Zeile 3909), im bestehenden Token-Loop (Zeile 3930-3973):

Neuer Branch nach den bestehenden Keyword-Checks:
```
elsif IndexOfSubstring(tokStr, "SET", false) == 0 then
   setStr = CopySubstring(tokStr, 3, Length(tokStr) - 3)
   if setStr == ":ON" then setVal = 1.0; hasSet = true
   elsif setStr == ":OFF" then setVal = 0.0; hasSet = true
   else setVal = StringToDouble(setStr); hasSet = true
   end
```

Neue lokale Variablen in `ParseSingleBinding`:
- `hasSet : Boolean` (default false)
- `setVal : Double = 0.0`
- `setStr : String`

#### Storage

Zwei neue globale Arrays (gesized wie bestehende Mac_Layer_* Arrays):
```
Mac_Layer_HasSet : Boolean Array   // [MAX_LAYER_BINDINGS] — false at init
Mac_Layer_SetVal : Double Array    // [MAX_LAYER_BINDINGS] — 0.0 at init
```

`ParseSingleBinding` schreibt via bestehende Set-Helper-Logik in diese Arrays.

#### Ausfuehrung: `ApplyInitialValues()`

Neue Funktion, aufgerufen am Ende von `LoadControllerMap()` nach `RebuildReverseLookups()` und vor `UpdateControllerInfoDisplay()`.

```
Function ApplyInitialValues()
   var macIdx, b, bc, fi, vstIdx, paramIdx, ccCh, ccNum : Integer
   var setVal : Double = 0.0
   var target, targetType : String

   if IsLoadingSnapshot then
      // Guard: waehrend Snapshot-Load keine Plugin-Writes
   else
      For macIdx = 1; macIdx < MAX_MACROS; macIdx = macIdx + 1 Do
         bc = Mac_Layer_BindCount[macIdx]
         For b = 0; b < bc; b = b + 1 Do
            fi = MacLayerBindIdx(macIdx, 0, b)
            if Mac_Layer_HasSet[fi] then
               setVal = Mac_Layer_SetVal[fi]
               targetType = GetMacTargetType(macIdx, b)
               target = GetMacTarget(macIdx, b)

               if targetType == "CC" then
                  // Parse Ch/CC from target string (reuse existing logic)
                  // setVal is raw MIDI 0-127 for CC targets
                  SendNow(BLK_VSTControl, MakeControlChangeMessageEx(ccNum, Round(setVal), ccCh))
                  // Update CC_Cache
                  CC_CacheWrite(ccCh * 128 + ccNum, setVal / 127.0)

               elsif targetType == "VST" then
                  vstIdx = GetMacVSTIdx(macIdx, b)
                  paramIdx = GetMacParamIdx(macIdx, b)
                  if vstIdx >= 1 and vstIdx <= MAX_VSTS then
                     SetParameter(BLK_VST[vstIdx - 1], paramIdx, setVal)
                  end

               elsif targetType == "OVERLAY" then
                  // Fire overlay with SET value
                  ActivateOverlay(target, GetMacChannel(macIdx, b))
               end
            end
         End
      End
   end
End
```

### Komponente 2: CC Cache (Sparse Array)

Globaler Cache fuer alle empfangenen CC-Werte, unabhaengig von Channel.

#### Deklaration

```
CC_CACHE_MAX  : Integer = 256
CC_CacheKey   : Integer Array    // ch*128+cc
CC_CacheVal   : Double Array     // 0.0-1.0 (normalized)
CC_CacheCount : Integer = 0
```

#### Schreib-Funktion

```
Function CC_CacheWrite(cacheKey : Integer, val : Double)
   var i : Integer
   // Update existing entry
   For i = 0; i < CC_CacheCount; i = i + 1 Do
      if CC_CacheKey[i] == cacheKey then
         CC_CacheVal[i] = val
      end
   End
   // Append new entry (if not found and space available)
   if i == CC_CacheCount and CC_CacheCount < CC_CACHE_MAX then
      CC_CacheKey <-- cacheKey
      CC_CacheVal <-- val
      CC_CacheCount = CC_CacheCount + 1
   end
End
```

#### Lese-Funktion

```
Function CC_CacheRead(cacheKey : Integer) Returns Double
   var i : Integer
   For i = 0; i < CC_CacheCount; i = i + 1 Do
      if CC_CacheKey[i] == cacheKey then
         result = CC_CacheVal[i]
      end
   End
   result = -1.0  // Kein Wert bekannt
End
```

#### Schreib-Stellen (On ControlChangeEvent Callbacks)

In **jedem** `On ControlChangeEvent` Callback, **vor** allen Guards und Dispatches:
```
CC_CacheWrite(GetChannel(m) * 128 + GetCCNumber(m), IntToFloat(GetCCValue(m)) / 127.0)
```

Dies stellt sicher, dass CCs auch waehrend `IsLoadingSnapshot` gecacht werden (wichtig fuer RegMem-Werte vom Genos2).

#### Lese-Stelle: `SyncArrangerToCurrentMap()`

Zeile 4762 (die 50%-Regel) ersetzen:

```
if Mac_Layer_TargetType[fi] == "CC" then
   // Parse ch/cc from target string
   cachedVal = CC_CacheRead(ch * 128 + cc)
   if cachedVal >= 0.0 then
      faderVal = cachedVal
   else
      faderVal = 0.5  // Fallback: kein bekannter Wert
   end
end
```

### Prioritaetskette beim Songwechsel

```
On Song()
  1. SysEx an Genos2 (RegMem aktiviert)
  2. Genos2 sendet CCs --> CC_Cache wird gefuellt
     (auch waehrend IsLoadingSnapshot, da Cache VOR Guards schreibt)

200ms spaeter (DelayedLoadTimer):
  3. LoadSongSnapshot()
     --> LoadControllerMap()
         --> ParseSingleBinding() liest SET-Werte
         --> RebuildReverseLookups()
         --> ApplyInitialValues()
             - CC: SendNow(BLK_VSTControl) + CC_Cache ueberschreiben
             - VST: SetParameter() direkt
             - Overlay: ActivateOverlay()

3500ms spaeter (HardwareSyncTimer):
  4. SyncArrangerToCurrentMap()
     - CC-Targets: liest CC_Cache (enthaelt SET-Wert ODER Genos2-RegMem-Wert)
     - VST-Targets: liest GetParameter() wie bisher (korrekt)
```

**Ergebnis:** SET gewinnt immer (ueberschreibt Cache). Ohne SET greift der Genos2-RegMem-Wert. Ohne beides: Fallback 0.5.

### Beruehrte Dateien und Stellen

| Datei | Stelle | Aenderung |
|-------|--------|-----------|
| Global Rackspace.gpscript | Var-Deklarationen (~Zeile 550) | `CC_CacheKey`, `CC_CacheVal`, `CC_CacheCount`, `Mac_Layer_HasSet`, `Mac_Layer_SetVal` |
| Global Rackspace.gpscript | `ParseSingleBinding()` (~3909) | Neuer `SET` Token-Branch + lokale Vars |
| Global Rackspace.gpscript | Neue Funktionen (~nach RebuildReverseLookups) | `CC_CacheWrite()`, `CC_CacheRead()`, `ApplyInitialValues()` |
| Global Rackspace.gpscript | `LoadControllerMap()` (~8265) | Aufruf `ApplyInitialValues()` |
| Global Rackspace.gpscript | `SyncArrangerToCurrentMap()` (~4762) | CC_Cache-Lookup statt 0.5 |
| Global Rackspace.gpscript | Alle `On ControlChangeEvent` Callbacks | `CC_CacheWrite()` als erste Zeile |
| Global Rackspace.gpscript | `Initialization` (~14726) | CC_Cache-Arrays initialisieren |

### Bereits erledigt (diese Session)

- `SendNow(BLK_VSTControl, ...)` in `DispatchMacro()` CC-Pfad (Zeile 12361)
- `SCRIPT_VERSION` Bump auf `2026-04-16.001`

### Einschraenkungen

- CC_Cache hat 256 Slots (sparse). Bei > 256 gleichzeitig aktiven CC-Werten werden neue Eintraege ignoriert. In der Praxis irrelevant.
- `CC_CacheRead` nutzt linear scan (O(n)). Bei < 30 aktiven Eintraegen vernachlaessigbar.
- SET fuer CC erwartet MIDI-native Werte (0-127). SET fuer VST erwartet GP-Parameter-Werte (0.0-1.0). Der Parser unterscheidet anhand des bereits bekannten `targetType`.
