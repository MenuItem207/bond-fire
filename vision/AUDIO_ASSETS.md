# Audio Assets Guide

## Overview
The Bondfire vision system uses audio feedback to enhance the interactive experience. This includes sound effects (SFX), background music, and optional text-to-speech (TTS) narration.

## Directory Structure
```
vision/
└── assets/
    ├── sfx/                    # Sound effects
    │   ├── fire_crackle_loop.mp3
    │   ├── whoosh_entry.mp3
    │   ├── buzzer_alert.mp3
    │   ├── party_horn.mp3
    │   ├── soft_chime.mp3
    │   ├── buildup_start.mp3
    │   ├── buildup_pulse.mp3
    │   └── supernova_burst.mp3
    └── music/                  # Background music tracks
        ├── ambient_chill.mp3
        └── party_upbeat.mp3
```

## Required Assets

### Sound Effects (SFX)

#### 1. `sfx/fire_crackle_loop.mp3`
- **Type**: Looping ambient sound
- **Duration**: 5-10 seconds (seamless loop)
- **Usage**: Background fire crackling sound during FIRE state
- **Volume**: 30% (subtle ambience)
- **Description**: Gentle fire crackling/burning sound to create atmosphere

#### 2. `sfx/whoosh_entry.mp3`
- **Type**: Short impact sound
- **Duration**: 0.5-1 second
- **Usage**: Played when a new person enters the fire
- **Volume**: 80%
- **Description**: Swoosh/whoosh sound to announce new participant

#### 3. `sfx/buzzer_alert.mp3`
- **Type**: Alert/warning sound
- **Duration**: 0.5-1.5 seconds
- **Usage**: Played when phone is detected (PHONE state)
- **Volume**: 80%
- **Description**: Attention-grabbing buzzer or alert tone

#### 4. `sfx/party_horn.mp3`
- **Type**: Celebration sound
- **Duration**: 1-2 seconds
- **Usage**: Played when phone is put away (celebration)
- **Volume**: 80%
- **Description**: Party horn, kazoo, or celebratory sound effect

#### 5. `sfx/soft_chime.mp3`
- **Type**: Gentle notification
- **Duration**: 0.3-0.8 seconds
- **Usage**: Color pulse events (every 15 seconds in FIRE mode)
- **Volume**: 40% (subtle)
- **Description**: Soft bell chime or gentle tone

#### 6. `sfx/buildup_start.mp3`
- **Type**: Riser/tension builder
- **Duration**: 1-2 seconds
- **Usage**: When party buildup begins (5 people detected)
- **Volume**: 90%
- **Description**: Low frequency riser or tension-building sound

#### 7. `sfx/buildup_pulse.mp3`
- **Type**: Pulse/heartbeat sound
- **Duration**: 0.3-0.6 seconds
- **Usage**: During party buildup at 33% and 66% progress
- **Volume**: 70%
- **Description**: Rhythmic pulse or heartbeat sound

#### 8. `sfx/supernova_burst.mp3`
- **Type**: Explosion/burst sound
- **Duration**: 1-3 seconds
- **Usage**: When PARTY state is reached
- **Volume**: 100%
- **Description**: Explosive burst, firework, or supernova sound

### Background Music

#### 1. `music/ambient_chill.mp3`
- **Type**: Looping ambient music
- **Duration**: 2-5 minutes
- **Usage**: Background music during IDLE and FIRE states
- **Volume**: 70%
- **Description**: Calm, chill ambient music with minimal beats
- **Style**: Downtempo, ambient, lo-fi, or meditative

#### 2. `music/party_upbeat.mp3`
- **Type**: Looping dance music
- **Duration**: 2-5 minutes
- **Usage**: Background music during PARTY state
- **Volume**: 100%
- **Description**: Upbeat, energetic party music
- **Style**: EDM, house, disco, or any high-energy dance music

## Setup Instructions

### 1. Create Asset Directories
```bash
cd vision
mkdir -p assets/sfx
mkdir -p assets/music
```

### 2. Add Audio Files
Place your audio files in the appropriate directories with the exact filenames listed above.

**Supported formats**: MP3, WAV, OGG (MP3 recommended for size)

### 3. Test Audio System
Run the vision system with audio enabled:
```bash
bond-fire-vision --camera-index 0 --enable-audio --narration-enabled
```

You should see:
```
Audio system started (volume=0.7).
TTS narration enabled.
```

If assets are missing, you'll see:
```
⚠️  WARNING: Missing audio assets:
  - party_horn: /path/to/vision/assets/sfx/party_horn.mp3
  - ambient_music: /path/to/vision/assets/music/ambient_chill.mp3

Expected assets directory: /path/to/vision/assets
See AUDIO_ASSETS.md for complete asset list and setup instructions.
```

## Finding/Creating Assets

### Free Sound Resources
- **Freesound.org** - Community-sourced sound effects (CC licenses)
- **Incompetech.com** - Royalty-free music by Kevin MacLeod
- **Pixabay Audio** - Free audio library
- **YouTube Audio Library** - Free music and sound effects

### Creating Your Own
- Use tools like Audacity (free) to create/edit sounds
- Record real fire crackling, party sounds, etc.
- Generate synthetic sounds with online tools

### Licensing
Ensure you have proper licenses for any audio you use in the installation. For public exhibitions, use:
- Creative Commons Zero (CC0) - Public domain
- Creative Commons Attribution (CC BY) - Requires credit
- Royalty-free commercial licenses

## Audio Configuration

### Adjusting Volumes
Edit individual volumes in the code:

**In `detector.py`:**
```python
self.audio_manager.play_sfx("party_horn", volume=0.8)  # 80% volume
self.audio_manager.play_sfx("chime", volume=0.4)       # 40% volume
```

**In `audio_manager.py`:**
```python
self.play_sfx("fire_crackle", volume=0.3)  # Ambient crackle
self.play_sfx("party_horn", volume=1.0)     # Celebration
```

### Master Volume
Set master volume at startup:
```bash
bond-fire-vision --audio-volume 0.5  # 50% master volume
```

### Disable Audio
Run without audio:
```bash
bond-fire-vision --camera-index 0  # Audio disabled by default
```

## Text-to-Speech (TTS)

### Requirements
```bash
pip install pyttsx3
```

### Platform-Specific Notes

**macOS**: Uses built-in speech synthesis (works out of the box)

**Linux**: Requires `espeak` or `festival`
```bash
sudo apt-get install espeak
```

**Windows**: Uses SAPI5 voices (built-in)

### TTS Configuration

#### Voice Selection
By default, the system automatically selects a deep male narrator voice for professional-sounding narration. You can override this:

```bash
# Use default deep male narrator (automatic)
bond-fire-vision --enable-audio --narration-enabled

# Use female voice
bond-fire-vision --enable-audio --narration-enabled --tts-voice female

# Use specific voice by name
bond-fire-vision --enable-audio --narration-enabled --tts-voice david
```

#### Available Voices

**macOS**:
- David (default male - deep narrator voice)
- Alex
- Victoria (female)
- Others (Samantha, Moira, Fiona, etc.)

**Windows**:
- Default system voices (typically include male/female options)

**Linux** (with espeak):
- Default voice (install espeak: `sudo apt-get install espeak`)

#### Voice Customization in Code
```python
# In audio_manager.py or detector initialization:
audio_manager = AudioManager(
    narration_enabled=True,
    tts_voice="david"  # or "male", "female", or voice name
)
```

#### TTS Speech Configuration

## Troubleshooting

### "pygame.mixer not available"
```bash
pip install pygame
```

### "Audio asset missing" warnings
- Check that files exist at the specified paths
- Verify filenames match exactly (case-sensitive on Linux/macOS)
- Ensure file formats are supported (MP3, WAV, OGG)

### No sound output
1. Check system audio volume
2. Verify audio device is working: `python -c "import pygame; pygame.mixer.init(); pygame.mixer.music.play()"`
3. Try different audio formats (WAV instead of MP3)
4. Check pygame mixer initialization errors in console

### TTS not working
1. Verify pyttsx3 is installed: `pip list | grep pyttsx3`
2. Test TTS directly:
   ```python
   import pyttsx3
   engine = pyttsx3.init()
   engine.say("Hello world")
   engine.runAndWait()
   ```
3. On Linux, install espeak: `sudo apt-get install espeak`

## Performance Notes

- Audio runs in a background thread to avoid blocking vision processing
- Sound effects are cached after first load for faster playback
- Music uses streaming playback (doesn't load entire file into memory)
- Queue size is limited to 20 commands to prevent memory buildup

## Event Timeline

### Typical Audio Sequence
```
[Person enters]
→ SFX: whoosh_entry.mp3
→ TTS: "Red enters the flame!"

[Fire burns]
→ Music: ambient_chill.mp3 (looping)
→ SFX: fire_crackle_loop.mp3 (looping)

[Every 15 seconds]
→ SFX: soft_chime.mp3

[5 people detected]
→ SFX: buildup_start.mp3
→ Music: ambient_chill.mp3 fades

[Party buildup progresses]
→ SFX: buildup_pulse.mp3 (at 33%, 66%)

[Party state reached]
→ SFX: supernova_burst.mp3
→ Music: party_upbeat.mp3 starts

[Phone detected]
→ Music: stops
→ SFX: buzzer_alert.mp3 (looping)
→ TTS: "Phone detected. Put it away!"

[Phone removed]
→ SFX: party_horn.mp3
→ TTS: "Yes! Welcome back to the fire!"
→ Music: resumes
```
