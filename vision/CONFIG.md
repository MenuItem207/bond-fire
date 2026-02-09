# Bond Fire Vision Configuration Guide

## Overview

The Bond Fire Vision system uses a YAML configuration file (`config.yaml`) to manage all durations, thresholds, and other settings. This allows you to adjust behavior without modifying code.

## Configuration File Location

Place `config.yaml` in the `vision/` directory (same level as this file).

Alternatively, set the `BOND_FIRE_CONFIG` environment variable:
```bash
export BOND_FIRE_CONFIG=/path/to/config.yaml
```

## Configuration Sections

### State Machine (`state_machine`)

Controls phone detection timing:

- **`fire_entry_dwell`** (seconds): Delay before entering FIRE after first person is seen
  - Default: `0.3`
  - Increase to reduce single-frame person flicker

- **`phone_entry_dwell`** (seconds): Delay before recognizing phone entry
  - Default: `0.5`
  - Increase to reduce false positives

- **`phone_exit_dwell`** (seconds): How long phone must be absent before exiting PHONE state
  - Default: `0.5` (0.5 second hysteresis)
  - Prevents flickering when phone briefly leaves frame

- **`frame_rate`** (fps): Frame processing rate
  - Default: `5` fps
  - Used for celebration duration and state timing calculations

### Prompts (`prompts`)

Controls how often prompts change:

- **`normal_cooldown`** (seconds): Minimum time between prompts in non-phone states
  - Default: `8` seconds
  - Higher = less frequent prompt changes

- **`phone_cooldown`** (seconds): Faster cooldown when phone is detected
  - Default: `2` seconds
  - Allows more dynamic responses while phone is present

### Celebration (`celebration`)

Phone exit celebration effect:

- **`duration_frames`**: How many frames to display celebration
  - Default: `10` frames
  - At 5fps = ~2 seconds
  - Formula: `duration_seconds = duration_frames / frame_rate`

### Audio (`audio`)

Audio playback configuration:

- **`master_volume`**: Overall volume (0.0 to 1.0)
  - Default: `0.7`

- **`sfx_volume`**: Sound effects multiplier (0.0 to 1.0)
  - Default: `0.8`

- **`music_volume`**: Background music multiplier (0.0 to 1.0)
  - Default: `0.5`

- **TTS (Text-to-Speech)**:
  - `enabled`: Turn TTS on/off (boolean)
  - `speech_rate`: Speaking speed in WPM
    - Default: `150` (words per minute)
    - Lower = slower/more dramatic, Higher = faster
  - `voice_preference`: List of voices to try in order
    - Default: `[daniel, grandpa, rocko, reed]`
    - macOS will use the first available voice

- **`audio_queue_size`**: Maximum pending audio commands
  - Default: `50`
  - Increase if audio drops out under heavy load

- **`worker_thread_enabled`**: Use background thread for audio
  - Default: `true`
  - Keep enabled for smooth real-time operation

### Vision (`vision`)

Detection thresholds:

- **`confidence_threshold`**: YOLO detection confidence (0.0 to 1.0)
  - Default: `0.5`
  - Higher = fewer false positives, may miss detections
  - Lower = more detections, more false positives

- **`person_class_id`**: COCO dataset class ID for people
  - Default: `0` (correct for YOLO)

- **`phone_class_id`**: COCO dataset class ID for phones
  - Default: `67` (correct for YOLO)

### Debug (`debug`)

Development and troubleshooting:

- **`verbose_logging`**: Print detailed state transitions and timing
  - Default: `false`
  - Enable to diagnose state machine issues

- **`log_prompts`**: Log all generated prompts
  - Default: `false`
  - Enable to see what prompts are being generated

- **`disable_tts`**: Disable speech synthesis
  - Default: `false`
  - Enable to test without audio, or if TTS is causing issues

## Usage in Code

Import and use the config:

```python
from bond_fire_vision.config import get_config

config = get_config()

# Access settings
phone_exit_time = config.state_machine.phone_exit_dwell
prompt_cooldown = config.prompts.normal_cooldown
celebration_frames = config.celebration.duration_frames
tts_rate = config.audio.tts.speech_rate
```

## Example Configurations

### Faster Phone Response
```yaml
prompts:
  phone_cooldown: 1           # Prompt changes every 1 second while phone present
celebration:
  duration_frames: 5          # Shorter celebration (~1 second)
```

### More Conservative Detection
```yaml
state_machine:
  fire_entry_dwell: 0.3       # Require brief person presence before FIRE
  phone_entry_dwell: 0.2      # Wait 200ms before confirming phone detection
  phone_exit_dwell: 1.0       # More stable - require 1 second of absence
vision:
  confidence_threshold: 0.6   # Higher threshold - fewer false positives
```

### Slower, More Dramatic Speech
```yaml
audio:
  tts:
    speech_rate: 100          # Slower narration
```

### Silent Mode (Testing Without Audio)
```yaml
audio:
  master_volume: 0.0
debug:
  disable_tts: true
```

## Environment Variable Override

Set the config path via environment variable:
```bash
export BOND_FIRE_CONFIG=~/.config/bond-fire/config.yaml
python -m bond_fire_vision.cli --camera-index 0
```

## Reloading Configuration

To reload config at runtime:
```python
from bond_fire_vision.config import reload_config

# Reload from same path
config = reload_config()

# Or from a new path
config = reload_config("/path/to/new/config.yaml")
```

## Default Behavior

If `config.yaml` is not found, the system will search in:
1. Path specified by `BOND_FIRE_CONFIG` environment variable
2. `vision/` directory
3. Current working directory

If still not found, you'll get a helpful error message with instructions.
