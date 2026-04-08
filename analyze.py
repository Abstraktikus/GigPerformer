import re

with open("Global Rackspace V25.gpscript", "r") as f:
    lines = f.readlines()

funcs = {"Wait", "Trace", "DebugCrash", "TraceActiveScope", "GetSnapshotPath", "GetSpaces", "PadInt", "SplitString", "SetChannelState", "GetCountInDurationMS", "UpdateSubbarLEDs", "GetParamIdxByName", "IsNPConfigParam", "CheckBlock", "CaptureFactoryDefaults", "ResetState", "GetFirstActiveScope", "TraceForensicChannelDump", "CycleGlobalSystemMode", "RefreshDiagDisplay", "ScrollToCurrentChannel", "RefreshVstInfoDisplay", "RefreshSafeReplacerUI", "ParkFadersForVST", "RestoreFadersForVST", "GetNoteName", "GetScaleKeyName", "GetScaleTypeName", "GetMusicTheoryString", "GetLuxusLabel", "TraceHardwarePrediction", "UpdateInjectionSplitDisplay", "UpdateInjectionFadeDisplay", "UpdateInjectionFilterDisplay", "UpdateInjectionNPDisplay", "UpdateInjectionTransposeDisplay", "UpdateVstInfoDisplay", "GetPrimaryVSTForChannel", "UpdateUsageLabelDisplay", "UpdateScopeVelocityMeter", "UpdateInjectionSoloDisplay", "UpdateInjectionMuteDisplay", "IsChannelActiveForLooper", "GetActiveLooperScope", "GetLoopActionName", "GetLoopLengthName", "GetLoopOutName", "GetLoopStopName", "RefreshLooperInfoDisplay", "TraceLooperDiagnostic", "RefreshLooperConfigDisplay", "ClearLooperArrays", "GetLoopProgressString", "BuildLooperConfigLines", "UpdateInjectionLooperTransportUI", "TraceTimeDomains", "UpdateInjectionLooperDisplay", "RefreshAllInjectionDisplays", "ExecuteSmartBypass", "AnalyzeChannel", "UpdateMetaColors", "SyncInputFeedback", "Trigger_NotesOff", "CloseLooperBuffer", "ValidateLooperScopeConfig", "CycleChannelScope", "CycleLoopLength", "CycleLoopAction", "RefreshCtrlInfoDisplay", "ShowCtrlOverlay", "CycleLoopTarget", "CycleLoopOutMode", "CycleLoopStopMode", "GetActiveMapSlot", "ScrollToCurrentVST", "SafeLoadPreset", "GetStoredPreset", "InjectKBSplitToggle", "InjectFilterToggle", "InjectTranspose", "InjectUserMuteToggle", "HandleInjectBypassClick", "IsChannelCustom", "IsChannelFactory", "ResetChannelToStandard", "ResetPluginParams", "ResetMidiInParams", "ResetFilterParams", "ArePluginParamsEqual", "AreMidiParamsEqual", "CopyPluginParams", "CopyMidiParams", "GetHardwareLabel", "GetAssignedHWString", "GetLinkNameHelper", "ScrollToCurrentCtrlScope", "BuildRecDisplayLines", "RefreshRecDisplay", "ShowVSTOverlay", "ShowRecOverlay", "ScrollToCurrentTimelineEvent", "GetChannelForVST", "GetStandardCCName", "ExecuteLink", "TriggerMacroFeedback", "UpdateControllerInfoDisplay", "UpdateEditScopeDisplay", "CycleEditScope", "IsBlockNameValid", "AppendLinkEncoded", "CaptureRechBaseline", "UpdateMidiConfigLabel", "UpdateMasterLabels", "UpdateChannelFade", "SaveHardwareMap", "LoadHardwareMap", "AssignHardware", "UnlearnHardware", "ApplyEditorTest", "ProcessMidiLearn", "UpdateSyncLabel", "CycleSyncMode", "CyclePluginPreset", "GetSysexString", "ClickWidget", "GetChordProFile", "UpdateTagInLine", "CalculateEffectiveTranspose", "StartMacroAnimation", "TriggerStyleAction", "UpdatePrompter", "JoinStringArray", "TrimAndClean", "IsDigitsOnly", "ExtractTagValue", "MyToUpper", "HasRealLyrics", "GetNoteIndex", "TransposeNote", "TransposeChordContent", "TransposeLine", "BuildZebraBlocks", "RecordTimelineEvent", "RecalculateTextDisplay", "TriggerNextSongPart", "SyncKBSplitWatchdog", "SyncMatrixToScriptlet", "UpdateCFConfigLabel", "ApplyCrossfade", "SyncRechUI", "TriggerSongTextLoad", "HexCharToInt", "IntToChar", "DecodeSysExName", "SanitizeAndSlugify", "LoadMappingFile", "AppendToMappingFile", "AddNewMapping", "GetBodyFromFile", "GetConfigFromFile", "GetDynamicStandardMap", "ValidateMapping", "ResetHardwareFadersForVST", "LoadControllerMap", "EvaluateSmartAdapt", "ApplyVstFocusBypass", "SyncChannelScopeToVst", "EvaluateAutoSysMode", "UpdateSoloMuteState", "ChangeVstScope", "GetLooperEventCount", "SendProgramChangeToVst", "TriggerVstPresetChange", "TriggerFocusLooperTransport", "RecordLoopEvent", "InjectLooperEvent", "ProcessLooperPlayback", "FeedLooper_Note", "FeedLooper_CC", "GetLoopModeName", "RefreshCtrlMapList", "CycleCtrlMap", "SyncGenosToCurrentMap", "ExecuteHardwareMacro", "ProcessHardwareCC", "AutoSwitchMapOnBypass", "MorphSend", "CaptureSmartRanges", "ExportSmartConfig", "CycleRechPresets", "CycleChannelUsage", "CycleScopeSection", "SetDefaultChannelScope", "ScanGlobalInstruments", "SmartLoadPresetAfterReplace", "BuildFilteredVstList", "SyncBrowserToLoadedPlugin", "FocusBrowserOnCurrentSlot", "RebuildBrowserStateAfterReboot", "AddJobToQueue", "SuperCleanPath", "ContinueActualReplace", "FireActualReplace", "TriggerNextQueueJob", "ExecuteVSTReplace", "GetPathForVst", "DeactivateChannel", "PerformSystemReset", "IsHeaderLine", "IsChordLine", "RemoveInlineComments", "AutoTagSections", "IsTabLine", "IsJunkLine", "CleanChordName", "WeaveChords", "GetEffectiveLength", "GetSmartWrapIndex", "FlushSection", "WashClipboardText", "ExecuteScrub", "CleanAndNormalizeRAM", "AnalyzeStructure", "ResetData", "JumpToRegMemAnchor", "CheckRegMemAutopilot", "FinishRecording", "ParseSongData", "CreateSkeletonFile", "LoadSongText", "LoadVstDatabase", "SaveSongSnapshot", "LoadSongTimeline", "LoadSongSnapshot", "SwitchToSongByName_Safe", "SaveStructureFromClipboard", "RefreshVstArray", "ProcessTopQueueJobResult", "FireGenosTransportEcho", "EvaluateTransportSync", "FireDirectGenosTransport", "PreviewActiveControllerMaps", "InjectNPToggle", "InjectNPStep", "ProcessSystemNavigation", "ProcessHardwareNote"}

func_lines = {}
for i, line in enumerate(lines):
    m = re.match(r'^Function\s+(\w+)', line)
    if m and m.group(1) in funcs:
        func_lines[m.group(1)] = i

deps = {}
for fname in sorted(funcs):
    if fname not in func_lines:
        deps[fname] = None
        continue
    start = func_lines[fname]
    end = start + 1
    depth = 0
    while end < len(lines):
        s = lines[end].strip()
        if s and not s.startswith('//'):
            if s.startswith(('If ', 'While ', 'For ')):
                depth += 1
            elif s == 'End':
                if depth == 0:
                    break
                depth -= 1
        end += 1
    called = []
    for other in funcs:
        if other == fname:
            continue
        pat = r'\b' + re.escape(other) + r'\s*\('
        for j in range(start + 1, end):
            if re.search(pat, lines[j]):
                called.append(other)
                break
    deps[fname] = sorted(called)

def layer(f, c):
    if f in c:
        return c[f]
    if deps[f] is None:
        c[f] = -1
        return -1
    if not deps[f]:
        c[f] = 0
        return 0
    m = -1
    for d in deps[f]:
        l = layer(d, c)
        if l > m:
            m = l
    c[f] = m + 1
    return m + 1

lc = {}
for f in funcs:
    layer(f, lc)

layers = {}
for f, l in lc.items():
    if l not in layers:
        layers[l] = []
    layers[l].append(f)

for l in sorted(layers.keys()):
    fs = sorted(layers[l])
    if l == -1:
        print(f"NOT_FOUND ({len(fs)}): {fs[:5]}")
    else:
        print(f"LAYER{l} ({len(fs)}): {fs[:8]}")

