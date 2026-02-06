# Audio Assets Setup

## Status: ✅ Complete

All required audio assets have been generated and the audio system is operational.

## Generated Assets

### SFX (vision/assets/sfx/)
- `fire_crackle_loop.wav` - 30s looping fire crackle (volume scales 0.2-1.0)
- `whoosh_entry.wav` - 1s whoosh sound for person entry
- `buzzer_alert.wav` - 0.5s buzzer for alerts
- `party_horn.wav` - 2s celebratory party horn
- `soft_chime.wav` - Short chime for notifications
- `buildup_start.wav` - Rising tone for buildup phase (200→800Hz)
- `buildup_pulse.wav` - Pulsing heartbeat tone during buildup
- `supernova_burst.wav` - Explosion sound for party mode entry

### Music (vision/assets/music/)
- `ambient_chill.wav` - 3min looping ambient drone for FIRE mode
- `party_upbeat.wav` - 3min looping upbeat rhythm for PARTY mode

## Technical Details

### Format
All assets are generated as WAV files (44.1kHz, 16-bit, mono) using sine wave synthesis. These provide:
- **Instant playback** - No external file dependencies
- **Cross-platform compatibility** - Works on all OS
- **Minimal file size** - Compressed WAV format
- **Graceful degradation** - System continues if audio disabled

### Audio Manager Behavior
The audio system (in `vision/src/bond_fire_vision/audio_manager.py`) is non-blocking:
- Runs in a background thread
- Validates assets on startup and warns about missing files
- Continues operating even if some/all audio files are missing
- All failures are caught and logged without stopping the vision system

### Custom Audio (Optional)

To use custom MP3 files instead:

1. **Convert WAV to MP3:**
   ```bash
   cd vision/assets/sfx
   for f in *.wav; do ffmpeg -i "$f" -q:a 5 "${f%.wav}.mp3"; done
   
   cd ../music
   for f in *.wav; do ffmpeg -i "$f" -q:a 5 "${f%.wav}.mp3"; done
   ```

2. **Update asset mappings** in `audio_manager.py`:
   ```python
   ASSET_MAP = {
       "fire_crackle": "sfx/fire_crackle_loop.mp3",  # Change .wav to .mp3
       # ... etc
   }
   ```

3. **Place your audio files** in the respective directories

## System Architecture

```
Vision Master (Python)
    ↓ UDP packets (60/sec)
ESP32 Slave
    ↓ PWM control
Hardware
    ├── LED Ring (59 pixels)
    ├── Matrix Display (32x8)
    ├── Fan PWM
    └── Mist Pump PWM
```

The audio system is decoupled from the vision pipeline:
- No blocking I/O
- Graceful failure modes
- Independent of network/ESP32 communication
- Optional TTS narration support

## Testing

Start the vision system:
```bash
cd vision
python -m bond_fire_vision.cli --camera-index 0
```

The system will:
1. Initialize audio system (or disable if pygame unavailable)
2. Warn about any missing audio files
3. Continue to operate normally with or without audio

## Troubleshooting

**"Audio disabled: pygame.mixer not available"**
- Install: `pip install pygame`

**"Missing audio asset warnings"**
- Normal - system will continue without those sounds
- Optional: Generate custom audio files or run `python create_audio_assets.py`

**Audio playback issues**
- Check system volume settings
- Verify speaker/audio device is enabled
- Audio manager logs all errors to stdout (no audio = silent failure, continues operating)
