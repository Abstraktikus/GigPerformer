#!/usr/bin/env python3
"""
Reorders functions in Global Rackspace V26.gpscript into thematic sections.
Respects GPScript's declare-before-use constraint by ordering sections correctly.
"""

import re
import sys

INPUT = "Global Rackspace V26.gpscript"
OUTPUT = "Global Rackspace V26.gpscript"  # overwrite in place

# Section assignments: function_name -> section_number
SECTION_MAP = {
    # SECTION 13: CORE UTILITIES
    # 13a: Debug & Trace
    "Wait": 13, "Trace": 13, "DebugCrash": 13, "TraceActiveScope": 13,
    # 13b: String Utilities
    "SplitString": 13, "TrimAndClean": 13, "JoinStringArray": 13,
    "IsDigitsOnly": 13, "MyToUpper": 13, "GetSpaces": 13, "PadInt": 13,
    "ExtractTagValue": 13, "UpdateTagInLine": 13,
    # 13c: Music Theory Helpers
    "GetNoteName": 13, "GetScaleKeyName": 13, "GetScaleTypeName": 13,
    "GetMusicTheoryString": 13, "GetLuxusLabel": 13, "GetNoteIndex": 13,
    "GetStandardCCName": 13,
    # 13d: File & Path Utilities
    "GetSnapshotPath": 13, "SuperCleanPath": 13, "GetBodyFromFile": 13,
    "GetConfigFromFile": 13, "HexCharToInt": 13, "IntToChar": 13,
    # 13e: State Helpers
    "ResetState": 13, "GetFirstActiveScope": 13, "IsChannelCustom": 13,
    "IsChannelFactory": 13, "IsBlockNameValid": 13, "ClickWidget": 13,
    "GetActiveMapSlot": 13, "GetPrimaryVSTForChannel": 13,
    "IsChannelActiveForLooper": 13, "GetActiveLooperScope": 13,
    # 13f: Overlay & Timer Helpers
    "ShowCtrlOverlay": 13, "ShowVSTOverlay": 13, "ShowRecOverlay": 13,
    "StartMacroAnimation": 13, "GetCountInDurationMS": 13, "SetChannelState": 13,

    # SECTION 14: HAL RUNTIME (already in correct position, keep as-is)
    "ParseCapString": 14, "ParseControlType": 14, "ParseFeedbackType": 14,
    "ParseDeviceConfig": 14, "DeviceHasCap": 14, "GetDeviceIdxByName": 14,
    "GetDeviceMidiOut": 14, "IsDeviceConnected": 14, "FindControl": 14,
    "GetControlType": 14, "GetControlFeedback": 14, "GetDeviceSysEx": 14,
    "SendDeviceSysEx": 14, "MapDevicesToBlocks": 14, "GetDeviceIdxForBlock": 14,

    # SECTION 15: MIDI & CHANNEL ENGINE
    "GetParamIdxByName": 15, "IsNPConfigParam": 15, "CheckBlock": 15,
    "CaptureFactoryDefaults": 15, "ResetChannelToStandard": 15,
    "ResetPluginParams": 15, "ResetMidiInParams": 15, "ResetFilterParams": 15,
    "ArePluginParamsEqual": 15, "AreMidiParamsEqual": 15,
    "CopyPluginParams": 15, "CopyMidiParams": 15,
    "InjectKBSplitToggle": 15, "InjectFilterToggle": 15,
    "InjectTranspose": 15, "InjectUserMuteToggle": 15,
    "InjectNPToggle": 15, "InjectNPStep": 15,
    "HandleInjectBypassClick": 15, "Trigger_NotesOff": 15,
    "SyncKBSplitWatchdog": 15,

    # SECTION 16: DISPLAY ENGINE
    "UpdateSubbarLEDs": 16, "RefreshDiagDisplay": 16, "ScrollToCurrentChannel": 16,
    "RefreshVstInfoDisplay": 16, "RefreshSafeReplacerUI": 16,
    "UpdateInjectionSplitDisplay": 16, "UpdateInjectionFadeDisplay": 16,
    "UpdateInjectionFilterDisplay": 16, "UpdateInjectionNPDisplay": 16,
    "UpdateInjectionTransposeDisplay": 16, "UpdateVstInfoDisplay": 16,
    "UpdateUsageLabelDisplay": 16, "UpdateScopeVelocityMeter": 16,
    "UpdateInjectionSoloDisplay": 16, "UpdateInjectionMuteDisplay": 16,
    "UpdateInjectionLooperTransportUI": 16, "UpdateInjectionLooperDisplay": 16,
    "RefreshAllInjectionDisplays": 16, "UpdateMetaColors": 16,
    "SyncInputFeedback": 16, "TraceForensicChannelDump": 16,
    "TraceHardwarePrediction": 16, "UpdateSyncLabel": 16,
    "UpdateMidiConfigLabel": 16, "UpdateCFConfigLabel": 16,
    "UpdateMasterLabels": 16,

    # SECTION 17: CONTROLLER MAP ENGINE
    "GetHardwareLabel": 17, "GetAssignedHWString": 17, "GetLinkNameHelper": 17,
    "ScrollToCurrentCtrlScope": 17, "RefreshCtrlInfoDisplay": 17,
    "UpdateControllerInfoDisplay": 17, "UpdateEditScopeDisplay": 17,
    "CycleEditScope": 17, "AppendLinkEncoded": 17, "CaptureRechBaseline": 17,
    "ExecuteLink": 17, "TriggerMacroFeedback": 17,
    "SaveHardwareMap": 17, "LoadHardwareMap": 17,
    "AssignHardware": 17, "UnlearnHardware": 17,
    "ApplyEditorTest": 17, "ProcessMidiLearn": 17,
    "MorphSend": 17, "CaptureSmartRanges": 17, "ExportSmartConfig": 17,
    "RefreshCtrlMapList": 17, "LoadControllerMap": 17,
    "EvaluateSmartAdapt": 17, "CycleCtrlMap": 17,
    "SyncGenosToCurrentMap": 17, "AutoSwitchMapOnBypass": 17,
    "PreviewActiveControllerMaps": 17,

    # SECTION 18: LOOPER ENGINE
    "GetLoopActionName": 18, "GetLoopLengthName": 18, "GetLoopOutName": 18,
    "GetLoopStopName": 18, "GetLoopModeName": 18, "GetLoopProgressString": 18,
    "GetLooperEventCount": 18, "RefreshLooperInfoDisplay": 18,
    "RefreshLooperConfigDisplay": 18, "BuildLooperConfigLines": 18,
    "TraceLooperDiagnostic": 18, "ClearLooperArrays": 18,
    "ValidateLooperScopeConfig": 18, "CycleLoopLength": 18,
    "CycleLoopAction": 18, "CycleLoopTarget": 18,
    "CycleLoopOutMode": 18, "CycleLoopStopMode": 18,
    "RecordLoopEvent": 18, "InjectLooperEvent": 18,
    "ProcessLooperPlayback": 18, "FeedLooper_Note": 18,
    "FeedLooper_CC": 18, "TriggerFocusLooperTransport": 18,
    "CloseLooperBuffer": 18,

    # SECTION 19: PROMPTER & TIMELINE ENGINE
    "GetChordProFile": 19, "CalculateEffectiveTranspose": 19,
    "TransposeNote": 19, "TransposeChordContent": 19, "TransposeLine": 19,
    "IsHeaderLine": 19, "IsChordLine": 19, "IsTabLine": 19, "IsJunkLine": 19,
    "HasRealLyrics": 19, "RemoveInlineComments": 19, "CleanChordName": 19,
    "WeaveChords": 19, "GetEffectiveLength": 19, "GetSmartWrapIndex": 19,
    "FlushSection": 19, "AutoTagSections": 19, "WashClipboardText": 19,
    "BuildZebraBlocks": 19, "RecordTimelineEvent": 19,
    "RecalculateTextDisplay": 19, "UpdatePrompter": 19,
    "TriggerNextSongPart": 19, "TriggerStyleAction": 19,
    "BuildRecDisplayLines": 19, "RefreshRecDisplay": 19,
    "ScrollToCurrentTimelineEvent": 19, "ExecuteScrub": 19,
    "TriggerSongTextLoad": 19, "DecodeSysExName": 19,
    "SanitizeAndSlugify": 19, "LoadMappingFile": 19,
    "AppendToMappingFile": 19, "AddNewMapping": 19,
    "GetDynamicStandardMap": 19, "ValidateMapping": 19,
    "FireGenosTransportEcho": 19, "EvaluateTransportSync": 19,
    "FireDirectGenosTransport": 19, "TraceTimeDomains": 19,

    # SECTION 20: VST REPLACER ENGINE
    "ParkFadersForVST": 20, "RestoreFadersForVST": 20,
    "ResetHardwareFadersForVST": 20, "ScrollToCurrentVST": 20,
    "SafeLoadPreset": 20, "GetStoredPreset": 20,
    "CyclePluginPreset": 20, "GetPathForVst": 20,
    "BuildFilteredVstList": 20, "SyncBrowserToLoadedPlugin": 20,
    "FocusBrowserOnCurrentSlot": 20, "RebuildBrowserStateAfterReboot": 20,
    "SmartLoadPresetAfterReplace": 20, "AddJobToQueue": 20,
    "ContinueActualReplace": 20, "FireActualReplace": 20,
    "TriggerNextQueueJob": 20, "ExecuteVSTReplace": 20,
    "SendProgramChangeToVst": 20, "TriggerVstPresetChange": 20,
    "LoadVstDatabase": 20, "RefreshVstArray": 20,
    "GetChannelForVST": 20,

    # SECTION 21: ORCHESTRATION
    "AnalyzeChannel": 21, "ExecuteSmartBypass": 21, "ApplyVstFocusBypass": 21,
    "UpdateSoloMuteState": 21, "ApplyCrossfade": 21, "SyncRechUI": 21,
    "SyncMatrixToScriptlet": 21, "CycleChannelScope": 21,
    "CycleChannelUsage": 21, "CycleScopeSection": 21,
    "CycleRechPresets": 21, "CycleGlobalSystemMode": 21,
    "CycleSyncMode": 21, "SetDefaultChannelScope": 21,
    "SyncChannelScopeToVst": 21, "EvaluateAutoSysMode": 21,
    "ChangeVstScope": 21, "DeactivateChannel": 21,
    "ScanGlobalInstruments": 21, "GetSysexString": 21,
    "UpdateChannelFade": 21,

    # SECTION 22: HARDWARE INPUT PROCESSING
    "ExecuteHardwareMacro": 22, "ProcessHardwareCC": 22,
    "ProcessHardwareNote": 22, "ProcessSystemNavigation": 22,

    # SECTION 23: SONG & SNAPSHOT MANAGEMENT
    "CleanAndNormalizeRAM": 23, "AnalyzeStructure": 23, "ResetData": 23,
    "JumpToRegMemAnchor": 23, "CheckRegMemAutopilot": 23,
    "FinishRecording": 23, "ParseSongData": 23, "CreateSkeletonFile": 23,
    "LoadSongText": 23, "SaveSongSnapshot": 23, "LoadSongTimeline": 23,
    "LoadSongSnapshot": 23, "SwitchToSongByName_Safe": 23,
    "SaveStructureFromClipboard": 23, "ProcessTopQueueJobResult": 23,
    "PerformSystemReset": 23,
}

# Section headers
SECTION_HEADERS = {
    13: """// ============================================================================
// SECTION 13: CORE UTILITIES
// ============================================================================
""",
    14: """// ============================================================================
// SECTION 14: HARDWARE ABSTRACTION LAYER — RUNTIME
// ============================================================================
""",
    15: """// ============================================================================
// SECTION 15: MIDI & CHANNEL ENGINE
// ============================================================================
""",
    16: """// ============================================================================
// SECTION 16: DISPLAY ENGINE
// ============================================================================
""",
    17: """// ============================================================================
// SECTION 17: CONTROLLER MAP ENGINE
// ============================================================================
""",
    18: """// ============================================================================
// SECTION 18: LOOPER ENGINE
// ============================================================================
""",
    19: """// ============================================================================
// SECTION 19: PROMPTER & TIMELINE ENGINE
// ============================================================================
""",
    20: """// ============================================================================
// SECTION 20: VST REPLACER ENGINE
// ============================================================================
""",
    21: """// ============================================================================
// SECTION 21: ORCHESTRATION
// ============================================================================
""",
    22: """// ============================================================================
// SECTION 22: HARDWARE INPUT PROCESSING
// ============================================================================
""",
    23: """// ============================================================================
// SECTION 23: SONG & SNAPSHOT MANAGEMENT
// ============================================================================
""",
}

def extract_function_name(line):
    """Extract function name from a 'Function ...' line."""
    m = re.match(r'^Function\s+(\w+)\s*\(', line)
    if m:
        return m.group(1)
    # Handle functions without parameters
    m = re.match(r'^Function\s+(\w+)\s*$', line)
    if m:
        return m.group(1)
    return None

def parse_blocks(lines):
    """Parse the file into blocks: var_block, function_blocks, init_block, callback_blocks."""
    var_block = []       # Everything before first Function
    functions = []       # List of (name, section, lines_including_comments)
    init_block = []      # Initialization block
    callback_blocks = [] # Everything after Initialization End
    stray_callbacks = [] # Callbacks found between functions

    i = 0
    n = len(lines)

    # 1. Read until first Function
    while i < n:
        if lines[i].startswith('Function ') or lines[i].startswith('// ====') and i > 500:
            break
        var_block.append(lines[i])
        i += 1

    # 2. Read functions (and collect stray callbacks)
    comment_buffer = []
    while i < n:
        line = lines[i]

        # Check for Initialization
        if line.strip() == 'Initialization':
            break

        # Check for callbacks mixed in with functions
        if line.startswith('On '):
            # This is a stray callback between functions
            cb_lines = comment_buffer[:]
            comment_buffer = []
            cb_lines.append(line)
            i += 1
            while i < n and not (lines[i].startswith('Function ') or lines[i].startswith('On ') or lines[i].strip() == 'Initialization'):
                cb_lines.append(lines[i])
                if lines[i].strip() == 'End' and not lines[i].startswith(' ') and not lines[i].startswith('\t'):
                    i += 1
                    # Grab trailing blank lines
                    while i < n and lines[i].strip() == '':
                        cb_lines.append(lines[i])
                        i += 1
                    break
                i += 1
            stray_callbacks.append(cb_lines)
            continue

        # Check for Function
        if line.startswith('Function '):
            func_name = extract_function_name(line)
            func_lines = comment_buffer[:]
            comment_buffer = []
            func_lines.append(line)
            i += 1

            # Read until we find a top-level End
            depth = 1
            while i < n and depth > 0:
                fline = lines[i]
                func_lines.append(fline)

                stripped = fline.strip()
                # Count nesting (approximate — GPScript uses End for if/while/for/select/function)
                # A top-level End is one that's not indented (or minimally indented)
                if stripped == 'End' and (not fline.startswith('   ') or fline == 'End'):
                    depth -= 1
                    if depth <= 0:
                        i += 1
                        break
                i += 1

            # Grab trailing blank lines
            while i < n and lines[i].strip() == '':
                func_lines.append(lines[i])
                i += 1

            section = SECTION_MAP.get(func_name, 99)
            if section == 99:
                print(f"WARNING: Function '{func_name}' not found in SECTION_MAP, defaulting to 99", file=sys.stderr)
            functions.append((func_name, section, func_lines))
            continue

        # Comments and blank lines between functions
        if line.strip() == '' or line.startswith('//'):
            comment_buffer.append(line)
            i += 1
            continue

        # Anything else - just buffer it
        comment_buffer.append(line)
        i += 1

    # 3. Read Initialization block
    if i < n and lines[i].strip() == 'Initialization':
        init_block = comment_buffer[:]
        comment_buffer = []
        while i < n:
            init_block.append(lines[i])
            if lines[i].strip() == 'End' and not lines[i].startswith(' ') and not lines[i].startswith('\t'):
                i += 1
                while i < n and lines[i].strip() == '':
                    init_block.append(lines[i])
                    i += 1
                break
            i += 1

    # 4. Everything remaining is callbacks
    while i < n:
        callback_blocks.append(lines[i])
        i += 1

    # Add stray callbacks to callback section
    if stray_callbacks:
        for sc in stray_callbacks:
            callback_blocks = sc + callback_blocks

    return var_block, functions, init_block, callback_blocks

def reorder_functions(functions):
    """Reorder functions by section, preserving order within each section based on dependencies."""

    # Within each section, we need to respect declare-before-use.
    # The simplest safe approach: within a section, keep the original relative order
    # (since V25 already compiled, the original order is valid).

    # Sort by section number, stable sort preserves relative order within same section
    # But we need a smarter approach: functions within a section should be ordered
    # so that callees come before callers.

    # For now: stable sort by section number (preserves V25 internal order)
    # This is safe because V25 compiled, so within-section order is already valid.
    return sorted(functions, key=lambda x: x[1])

def main():
    with open(INPUT, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    print(f"Input: {len(lines)} lines", file=sys.stderr)

    var_block, functions, init_block, callback_blocks = parse_blocks(lines)

    print(f"Var block: {len(var_block)} lines", file=sys.stderr)
    print(f"Functions: {len(functions)}", file=sys.stderr)
    print(f"Init block: {len(init_block)} lines", file=sys.stderr)
    print(f"Callbacks: {len(callback_blocks)} lines", file=sys.stderr)

    # Report section assignments
    section_counts = {}
    for name, sec, _ in functions:
        section_counts[sec] = section_counts.get(sec, 0) + 1
    for sec in sorted(section_counts):
        print(f"  Section {sec}: {section_counts[sec]} functions", file=sys.stderr)

    # Check for unmapped functions
    unmapped = [(name, sec) for name, sec, _ in functions if sec == 99]
    if unmapped:
        print(f"\nWARNING: {len(unmapped)} unmapped functions:", file=sys.stderr)
        for name, _ in unmapped:
            print(f"  - {name}", file=sys.stderr)

    # Reorder
    ordered = reorder_functions(functions)

    # Assemble output
    output_lines = var_block[:]

    current_section = -1
    for name, sec, func_lines in ordered:
        if sec != current_section:
            current_section = sec
            if sec in SECTION_HEADERS:
                output_lines.append('')
                output_lines.append(SECTION_HEADERS[sec].rstrip())
                output_lines.append('')
        output_lines.extend(func_lines)

    # Add Initialization
    output_lines.append('')
    output_lines.append('// ============================================================================')
    output_lines.append('// SECTION 24: INITIALIZATION')
    output_lines.append('// ============================================================================')
    output_lines.append('')
    output_lines.extend(init_block)

    # Add Callbacks
    output_lines.append('')
    output_lines.append('// ============================================================================')
    output_lines.append('// SECTION 25-26: CALLBACKS')
    output_lines.append('// ============================================================================')
    output_lines.append('')
    output_lines.extend(callback_blocks)

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"\nOutput: {len(output_lines)} lines written to {OUTPUT}", file=sys.stderr)

if __name__ == '__main__':
    main()
