# Gig Performer — Global Rackspace Script

A comprehensive GPScript-based live performance system for [Gig Performer 5](https://gigperformer.com), designed for keyboard players who use arranger workstations (Yamaha Genos) alongside VST instruments.

The Global Rackspace script turns Gig Performer into a full-featured live command center — managing songs, sounds, MIDI routing, looping, and hardware control from a single unified interface.

![Song Switch — Full view with setlist, chord sheet, and timeline](images/Song%20Switch.png)

## Features

### Song Management & Chord Display

Load songs from a setlist, display chord sheets with section markers (Intro, Verse, Chorus...), and navigate through song parts in real time. The timeline tracks your position with bar counters and section cues. Chord sheets use the original ChordPro format (`.gpchord`) and can be imported via clipboard — for example from [Ultimate Guitar](https://tabs.ultimate-guitar.com/).

![Song & Timeline — Transport sync, timeline recording, and transpose](images/Song%20&%20TImeline.png)

![Song Display — Chord sheet with section header and bar counter](images/Song%20Display.png)

### Preset Configuration & Voice Selection

Browse and swap VST plugins per layer with a publisher/sound/preset hierarchy. Resident layers (1-2) are protected from accidental replacement. The system reads from a `VstDatabase.txt` to offer organized sound browsing by manufacturer.

![Preset Configuration — Layer browser with publisher, sound, and preset](images/Preset%20Configuration.png)

### Channel Selector & Injection

Select and configure up to 16 MIDI channels individually. The Injection panel controls per-channel parameters: keyboard split, velocity range, fade in/out, MIDI filters, root/transpose, octaver (POG), humanizer, and scale quantizer.

![Channel Selector & Injection — Full channel config with all injection parameters](images/Channel%20Selector%20&%20Injection.png)

![Channel Selector — Compact view with channel analysis](images/Channel%20Selector.png)

![Channel Injection — Detail view of all per-channel parameters](images/Channel%20Injection.png)

### MIDI Looper

A per-channel MIDI looper with configurable action (Play/Overdub/Mute), loop length, target channel routing, output mode (Channel/Global), and stop behavior (Instant/End of Bar/End of Loop). Supports host sync and count-in.

![MIDI Looper with Channel Selector — Loop configuration per channel](images/Channel%20Selector%20&%20Looper.png)

![MIDI Looper — Compact view with all loop parameters](images/Looper.png)

### Crossfade Configuration

A dual-zone crossfader blending VST audio outputs (up to 16 channels) against MIDI expression for the arranger. Allows smooth transitions between VST layers and arranger sounds during live performance.

![Crossfade Configuration — VST audio vs. MIDI expression crossfader](images/Crossfader.png)

### Controller Maps & Scene Morphing

Define named controller maps per song that assign hardware knobs/sliders to VST parameters and MIDI CCs. Includes macro learning, scene morphing with min/max capture, and Smart Adapt for automatic parameter linking.

![Controller Maps — Macro assignments with scene morphing](images/Controller%20Map.png)

### Hardware Abstraction Layer (HAL)

All hardware is configured via `DeviceConfig.txt` — no hardcoded MIDI devices in the script. Supports multiple devices with capability flags (transport sync, SysEx, joystick, crossfader targets, feedback). Switch your entire hardware setup by editing one text file.

### AnchorPlayback — Chord-Based Part Detection

A passive observer that detects where you actually are in a song by matching played root notes against the `.gpchord` chord progression. Solves the fundamental problem of ms-based timelines drifting from reality in a live band context (extended solos, skipped verses, rushed sections).

- **Manual Property** — assign each MIDI channel as Upper (melody hand) or Lower (chord hand); AnchorPlayback reads from the Lower channel
- **Root Sequence Parser** — extracts pitch classes from chord notation (`[Dm]` → 2, `[F#m7]` → 6) with consecutive deduplication
- **Forward-Only Tracker** — matches played roots against the expected progression; 2 consecutive matches trigger a part change
- **Timeline Integration** — updates the prompter display, fires marker events, and optionally corrects the timeline position via TimeJump

Controlled by three buttons: `BTN_MIDIAnchorPlayback` (master switch), `BTN_TimeJump` (allow timeline correction), and `BTN_Autopilot` (fat-finger correction for RegMem).

### SYS-MODE Navigation

A 5-mode system accessible via joystick/sustain pedal:
- **Voice Selector** — browse and load VST sounds
- **Looper Control** — manage MIDI loops per channel  
- **Controller Map** — switch and edit macro assignments
- **Strip-Control** — channel strip parameters
- **Timeline** — record and navigate song sections with ms-based event timing

The Timeline mode features a PLAY/REC sub-mode system: PLAY provides safe navigation with part jump preview (joystick left/right shows upcoming song text in the OSC-UI), while REC enables recording of song part markers and macro events against external audio sources (e.g. Spotify). A shared count-in mechanism synchronizes the recording start. Events are stored as absolute milliseconds, with bar counts calculated after the full song is recorded.

Devices without a joystick (e.g. MiniLab) access SYS-MODEs via `SYSMODE_CYCLE` and `SYSMODE_SELECT` macros.

## Roadmap

Planned features, roughly in order of implementation:

1. **MIDI Recorder & Player** — Record and play back MIDI performances, bar-aligned to the timeline
2. **Overdub Layers** — Stack multiple recording takes on top of each other, building up arrangements layer by layer
3. **Backing Tracks Integration** — Trigger and sync audio backing tracks to the timeline with automatic cue points and transport control
4. **LFO Engine** — Scriptable LFOs linked to Controller Map macros for automated parameter modulation (filter sweeps, tremolo, panning, etc.)

## Requirements

- [Gig Performer 5.x](https://gigperformer.com) (GPScript support required)
- Windows or macOS
- At least one MIDI controller (configured via `DeviceConfig.txt`)
- Optional: Yamaha Genos/Genos2 for arranger integration

## Installation

1. **Clone or download** this repository
2. **Copy example configs** from `examples/` to your Gig Performer user folder:
   - `DeviceConfig.txt` — edit to match your hardware
   - `HardwareMap.txt` — map physical controls to functions
   - `VstDatabase.txt` — register your VST plugins
   - `ControllerMaps.txt` — define controller assignments
   - `GenosMapping.txt` — Genos voice mappings (if applicable)
3. **Open** `examples/Test.gig` in Gig Performer
4. **Paste** the Global Rackspace script (`Global Rackspace.gpscript`) into the Global Rackspace script editor
5. **Paste** the Note Prozessor script (`Note Prozessor 7.5.gpscript`) into the corresponding rackspace
6. **Adjust** `UserSnapshotPath` and `UserChordProPath` in Section 1 of the script to match your file locations
7. **Add songs** as `.ini` + `.gpchord` files (see examples: `SlowHip80erDream`, `VSTPlayMode`)

## File Structure

```
├── Global Rackspace.gpscript   # Main script (current version)
├── Note Prozessor 7.5.gpscript     # Per-rackspace note processing
├── Genos2_Control V2.gpscript      # Genos2 integration script
├── examples/                       # Ready-to-use test data
│   ├── DeviceConfig.txt            # Hardware configuration (INI format)
│   ├── HardwareMap.txt             # Physical control mappings
│   ├── VstDatabase.txt             # VST plugin database
│   ├── ControllerMaps.txt          # Controller map definitions
│   ├── GenosMapping.txt            # Genos voice/program mappings
│   ├── System_Standard.ini         # System default snapshot
│   ├── SlowHip80erDream.ini/.gpchord  # Example song
│   ├── VSTPlayMode.ini/.gpchord       # Example song
│   └── Test.gig                    # Gig Performer test file
├── images/                         # Screenshots of the rackspace UI
└── docs/                           # Design specs and migration notes
```

## Configuration

### DeviceConfig.txt

Define your MIDI devices in INI format with capabilities:

```ini
[Device:Genos]
MidiIn=Genos2 Main
MidiOut=Genos2 Main
Channel=1
Capabilities=TRANSPORT_SYNC, SYSEX_TRIGGER, CROSSFADER_TARGETS, JOYSTICK, MIDI_OUT

[Control:MainFader]
Device=Genos
Type=FADER
CC=7
Feedback=CC
```

### Song Files (.ini)

Each song is a snapshot file with per-channel settings:

```ini
[Snapshot]
Song=MySong.ini
Type=DynamicRef
Global_Crossfade=0.5
ControllerMap=Standard_VST1
```

## Status

> **Work in progress.** This project is under active development and has **not been used on stage yet**. It has only been tested with a **Yamaha Genos2** as the arranger workstation. Other hardware setups may require adjustments to `DeviceConfig.txt` and the HAL configuration. Use at your own risk — contributions and feedback are welcome!

## License

This project is shared for educational purposes. The GPScript code is original work. Gig Performer is a product of [Deskew Technologies](https://gigperformer.com).
