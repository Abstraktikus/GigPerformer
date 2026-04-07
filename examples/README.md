# Examples — Gig Performer Test Data

Example and configuration files used by the Global Rackspace script. Copy these to your `UserSnapshotPath` to get started quickly.

## System Configuration

| File | Purpose |
|------|---------|
| `DeviceConfig.txt` | Hardware Abstraction Layer — defines MIDI devices, controls, SysEx commands |
| `HardwareMap.txt` | Maps physical controls to logical functions |
| `ControllerMaps.txt` | Named controller mapping profiles |
| `VstDatabase.txt` | VST plugin database for voice/patch management |
| `GenosMapping.txt` | Yamaha Genos-specific voice and program mappings |
| `System_Standard.ini` | System default snapshot (fallback values) |

## Songs (for testing song switch)

| Files | Song |
|-------|------|
| `SlowHip80erDream.ini` + `.gpchord` | Full song config with crossfade, chord data |
| `VSTPlayMode.ini` + `.gpchord` | VST-focused song with sync mode settings |

## Test Rig

| File | Purpose |
|------|---------|
| `Test.gig` | Gig Performer file with rackspace for testing the scripts |
