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

Every VST on an inactive channel is automatically bypassed. The Smart Bypass engine watches the RECH routing matrix per scope and wakes a plugin only when at least one active input actually routes through it; any plugin that isn't contributing audio goes to sleep. This cuts real-time CPU load dramatically during a live set — typical songs use 2-4 layers out of 10 possible VST slots, so 6-8 plugins are idle at any moment.

The same mechanism enables **Delta-Load**: Gig Performer can keep the full VST library loaded in memory while only the active subset is processing audio. Switching songs becomes a matter of flipping bypass flags rather than loading and unloading plugins, which means sub-100ms song transitions even for large sound libraries. The engine honors explicit per-scope overrides — if you deliberately want a plugin active or bypassed for a specific channel, that wins over the routing-based default.

![Preset Configuration — Layer browser with publisher, sound, and preset](images/Preset%20Configuration.png)

### Channel Selector & Injection

Select and configure up to 16 MIDI channels individually. The Injection panel controls per-channel parameters: keyboard split, velocity range, fade in/out, MIDI filters, root/transpose, octaver (POG) with configurable range and velocity fade, humanizer, and scale quantizer.

![Channel Selector & Injection — Full channel config with all injection parameters](images/Channel%20Selector%20&%20Injection.png)

### MIDI Looper

A per-channel MIDI looper with configurable action (Play/Overdub/Mute), loop length, target channel routing, output mode (Channel/Global), and stop behavior (Instant/End of Bar/End of Loop). Supports host sync and count-in.

![MIDI Looper with Channel Selector — Loop configuration per channel](images/Channel%20Selector%20&%20Looper.png)

### Crossfade Configuration

A dual-zone crossfader blending VST audio outputs (up to 16 channels) against MIDI expression for the arranger. Allows smooth transitions between VST layers and arranger sounds during live performance.

![Crossfade Configuration — VST audio vs. MIDI expression crossfader](images/Crossfader.png)

### Controller Maps & Scene Morphing

Controller Maps use a unified format that combines hardware sources and parameter bindings in one file. A `[Map:Default]` section provides a base configuration; song-specific maps inherit from Default and only override what changes, keeping per-song definitions minimal.

The system supports a **Layer System**: binary switches (SysEx, Note, or CC triggers configured in DeviceConfig) multiply physical controls across layers. Two layer switches on a Genos2 yield 4 layers -- 6 physical encoders become 24 virtual controls, 9 faders become 27. Any control can additionally act as an **Overlay Trigger Zone (OTZ)** -- a position- or movement-based trigger for overlay functions (Smart Solo, Root, Octaver, etc.), so a volume fader simultaneously triggers a solo when pushed past a threshold. Controls are referenced by DeviceConfig labels (e.g., `Enc1`, `Fader3`) rather than raw MIDI values, keeping maps hardware-neutral. Scene morphing with BTN_Capture_Min/Max and Smart Adapt for automatic VST-based map selection remain available on top of this.

![Controller Maps — Macro assignments with scene morphing](images/Controller%20Map.png)

![Controller Map Sections — Macro ranges for Looper, Solo, Mute, Velocity, and Root](images/Controller%20Map%20Sections.png)

### LFO Engine

Scriptable low-frequency oscillators that automate any Controller Map macro — filter sweeps, tremolo, panning, slow pad evolutions, tempo-synced fades. Each LFO is defined once by name (Triangle / Sine / Saw / Square / Random, rate in bars or beats, cycles finite or infinite) and can be bound to any number of macros across any number of controller maps. Bindings are persisted inside `ControllerMaps.txt` via an `LFO:<name> |` prefix on the macro line — the same macro keeps its hardware routing and just gains an LFO modulator on top.

The LFO Inspector is scope-driven: select a macro, see its bound LFO (or draft a new one named after the current song); the `Run` button previews a draft while held, or starts a committed LFO permanently. Tempo-synced via `GetBPM()`, so the LFO rides the song's tempo changes. Echo-deduplication and an emergency kill switch protect against async callback feedback loops that would otherwise choke Gig Performer.

![LFO Inspector — Type, rate, cycles, and bound macro overview](images/Looper.png)

### Hardware Abstraction Layer (HAL)

All hardware is configured via `DeviceConfig.txt` -- no hardcoded MIDI devices in the script. Supports multiple devices with capability flags (transport sync, SysEx, joystick, crossfader targets, feedback), layer switches for multiplying physical controls, and permanent bindings for controls that never change across maps. Switch your entire hardware setup by editing one text file.

### AnchorPlayback — Chord-Based Part Detection

A passive observer that detects where you actually are in a song by matching played root notes against the `.gpchord` chord progression. Solves the fundamental problem of ms-based timelines drifting from reality in a live band context (extended solos, skipped verses, rushed sections).

- **Manual Property** — assign each MIDI channel as Upper (melody hand) or Lower (chord hand); AnchorPlayback reads from the Lower channel
- **Root Sequence Parser** — extracts pitch classes from chord notation (`[Dm]` → 2, `[F#m7]` → 6) with consecutive deduplication
- **Forward-Only Tracker** — matches played roots against the expected progression; 2 consecutive matches trigger a part change
- **Timeline Integration** — updates the prompter display, fires marker events, and optionally corrects the timeline position via TimeJump

Controlled by three buttons: `BTN_MIDIAnchorPlayback` (master switch), `BTN_TimeJump` (allow timeline correction), and `BTN_Autopilot` (fat-finger correction for RegMem).

### Smart Solo Enhanced

Smart Solo now considers both RECH input routing and the Manual zone setting (Upper/Lower/None) for each channel. This allows soloing the left hand while the right hand continues playing full accompaniment -- useful for exposing a bass line or pad without cutting the melody layer.

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

## Requirements

- [Gig Performer 5.x](https://gigperformer.com) (GPScript support required)
- Windows or macOS
- At least one MIDI controller (configured via `DeviceConfig.txt`)
- Optional: Yamaha Genos/Genos2 for arranger integration

## Installation

1. **Clone or download** this repository
2. **Copy example configs** from `examples/` to your Gig Performer user folder:
   - `DeviceConfig.txt` -- edit to match your hardware
   - `VstDatabase.txt` -- register your VST plugins
   - `ControllerMaps.txt` -- define controller maps (`[Map:Default]` + song-specific overrides)
   - `GenosMapping.txt` — Genos voice mappings (if applicable)
3. **Open** `examples/Test.gig` in Gig Performer
4. **Paste** the Global Rackspace script (`Global Rackspace.gpscript`) into the Global Rackspace script editor
5. **Paste** the Note Prozessor script (`Note Prozessor.gpscript`) into the corresponding rackspace
6. **Adjust** `UserSnapshotPath` and `UserChordProPath` in Section 1 of the script to match your file locations
7. **Add songs** as `.ini` + `.gpchord` files (see examples: `SlowHip80erDream`, `VSTPlayMode`)

## File Structure

```
├── Global Rackspace.gpscript   # Main script (current version)
├── Local Rackspace.gpscript    # Per-rackspace local script
├── Note Prozessor.gpscript     # Per-rackspace note processing
├── examples/                       # Ready-to-use test data
│   ├── DeviceConfig.txt            # Hardware + layer switches (INI format)
│   ├── VstDatabase.txt             # VST plugin database
│   ├── ControllerMaps.txt          # Controller maps (Default + song overrides)
│   ├── GenosMapping.txt            # Genos voice/program mappings
│   ├── System_Standard.ini         # System default snapshot
│   ├── SlowHip80erDream.ini/.gpchord  # Example song
│   ├── VSTPlayMode.ini/.gpchord       # Example song
│   └── Test.gig                    # Gig Performer test file
├── images/                         # Screenshots of the rackspace UI
└── docs/                           # Reference documentation
    ├── ControllerMap.md            # ControllerMap syntax, OTZ, SYSACT, SYS-MODE
    └── DeviceConfig.md             # Devices, controls, layers, routing, SysEx sync
```

## Configuration

### DeviceConfig.txt

Define your MIDI devices in INI format with capabilities, controls, layer switches, output routing, style triggers, and SysEx song sync. Full reference: `docs/DeviceConfig.md`.

```ini
[DEVICE:0]
Name=Genos2
MidiIn=Digital Keyboard-1
MidiIn:Aux=Genos2 USB MIDI
MidiOut=Digital Keyboard-1
Caps=TRANSPORT_SYNC,SYSEX_TRIGGER,JOYSTICK,MIDI_OUT,SYSEX_COMMANDS

[CONTROL:4]
Device=0
Label=Enc1
Type=ENCODER
CC=16

[LAYERSWITCH:0]
Device=0
Label=Harmony
Type=SYSEX
OnData=F0 43 10 4C 04 00 0C 40 F7
OffData=F0 43 10 4C 04 00 0C 7F F7
```

DeviceConfig also supports **output routing** (separate MIDI ports for volume, expression, and control streams), **style triggers** (note pulses for arranger section changes, fills, and transport), and **SysEx song sync** (bidirectional song switching between GP and the arranger with auto-learning `GenosMapping.txt` cache).

### Song Files (.ini)

Each song is a snapshot file with per-channel settings:

```ini
[Snapshot]
Song=MySong.ini
Type=DynamicRef
Global_Crossfade=0.5
ControllerMap=SlowHip80erDream
```

### ControllerMaps.txt

Maps use a `[Map:Default]` base; song-specific maps inherit from it and only override what changes. Full reference: `docs/ControllerMap.md`.

```ini
[Map:Default]
Macro1 = DEV0:LAY0:Enc1; VST1_GRS:48{0.0,1.0}
Macro2 = DEV0:LAY1:Enc1; ROOT:CH1{OTZ,1.0,1.0}
Macro13 = DEV0:LAY0:Fader1; VST1_GRS:0{0.0,1.0}
Macro22 = DEV0:LAY1:Fader1; VST1_GRS:0{0.0,1.0} | SMART_SOLO:CH1{OTZ,0.0,1.0}

[Map:SlowHip80erDream]
Macro1 = Ch11:CC74{0.0,1.0}
```

## Status

> **Work in progress.** This project is under active development and has **not been used on stage yet**. It has only been tested with a **Yamaha Genos2** as the arranger workstation. Other hardware setups may require adjustments to `DeviceConfig.txt` and the HAL configuration. Use at your own risk — contributions and feedback are welcome!

## License

This project is shared for educational purposes. The GPScript code is original work. Gig Performer is a product of [Deskew Technologies](https://gigperformer.com).
