# Bondfire Audio Assets

## Required Files

### SFX (vision/assets/sfx/)
- `fire_crackle_loop.mp3` - 30s looping fire crackle (volume scales 0.2-1.0)
- `whoosh_entry.mp3` - 1s whoosh sound for person entry
- `buzzer_alert.mp3` - 0.5s buzzer for phone detection
- `party_horn.mp3` - 2s party horn for party mode entry
- `soft_chime.mp3` - Short chime for 15s color pulse

### Music (vision/assets/music/)
- `ambient_chill.mp3` - 3min looping ambient track for FIRE mode
- `party_upbeat.mp3` - 3min looping upbeat track for PARTY mode

## Sourcing Audio

### Free SFX Resources
- **Freesound.org** - Community-uploaded sound effects (CC licenses)
- **Zapsplat.com** - Free SFX library (attribution required)
- **Sonniss.com** - Game audio bundles (free)

### Free Music Resources
- **Incompetech.com** - Royalty-free music by Kevin MacLeod
- **Bensound.com** - Free music tracks (attribution)
- **Purple Planet** - Free music for projects

### TTS (Built-in)
- Uses `pyttsx3` for offline text-to-speech
- No external files needed for narration

## Testing Without Assets

The audio manager will gracefully degrade if files are missing:
- Missing SFX: Logs warning, continues without sound
- Missing music: Runs silently
- No pygame: Disables entire audio subsystem

## Placeholder Creation

To create empty asset structure for testing:

```python
from bond_fire_vision.audio_manager import create_placeholder_assets
from pathlib import Path

create_placeholder_assets(Path("vision/assets"))
```

## Installation

Audio playback requires pygame:

```bash
pip install pygame pyttsx3
```

On macOS, pyttsx3 uses the system TTS engine (no additional setup).
On Linux, install espeak: `sudo apt-get install espeak`
