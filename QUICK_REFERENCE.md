# Quick Reference: Build-Up Audio Implementation

## What Was Added

### 1. State Machine Changes
```python
# state_machine.py

PARTY_ENTRY_BUILDUP = 1.5  # New: 1.5 second build-up before full party
PHONE_ENTRY_DWELL = 0.0    # New: Instant phone detection

# StateOutput now includes:
party_buildup_progress: float = 0.0  # 0.0 to 1.0 during build-up
```

### 2. Detector Audio Triggers
```python
# detector.py _send_update() method

# When buildup starts (0.0 → 0.01):
if state_output.party_buildup_progress > 0.0 and not self._party_buildup_started:
    self.audio_manager.play_sfx("buildup_start", volume=0.9)
    self._party_buildup_started = True

# At 33% and 66% milestones:
buildup_step = int(state_output.party_buildup_progress * 3)
if buildup_step > self._last_buildup_step:
    if self.audio_manager and buildup_step in (1, 2):
        self.audio_manager.play_sfx("buildup_pulse", volume=0.7)
    self._last_buildup_step = buildup_step
```

### 3. Packet Builder
```python
# packet_builder.py

def build(..., party_buildup_progress: float = 0.0):
    # Now includes in JSON:
    "party_buildup_progress": 0.0  # Range 0.0-1.0
```

### 4. Audio Assets
```python
# audio_manager.py ASSET_MAP

"buildup_start": "sfx/buildup_start.mp3",    # Charging tone
"buildup_pulse": "sfx/buildup_pulse.mp3",    # Pulsing beeps
"supernova": "sfx/supernova.wav",            # Explosion (optional)
```

## Files Modified

- ✅ `state_machine.py` - Added buildup timer & progress tracking
- ✅ `detector.py` - Added audio trigger logic + ROI margin
- ✅ `packet_builder.py` - Added party_buildup_progress field
- ✅ `audio_manager.py` - Added SFX asset mappings

## Files Created

- ✅ [REACTIVITY_AND_ARCHITECTURE.md](REACTIVITY_AND_ARCHITECTURE.md) - Full timing & LED architecture
- ✅ [PYTHON_IMPLEMENTATION_COMPLETE.md](PYTHON_IMPLEMENTATION_COMPLETE.md) - Complete implementation checklist
- ✅ [BUILD_UP_AUDIO_SUMMARY.md](BUILD_UP_AUDIO_SUMMARY.md) - Audio playback details
- ✅ [generate_test_sfx.py](generate_test_sfx.py) - Test audio generator
- ✅ [packet_listener.py](vision/packet_listener.py) - UDP packet inspector

## Quick Test

```bash
# 1. Generate test audio (optional, uses placeholders)
python generate_test_sfx.py

# 2. Run detector with audio
cd vision
source env/bin/activate
python src/bond_fire_vision/cli.py --enable-audio --camera-index 0

# 3. In another terminal, watch packets
python packet_listener.py --compact
```

When 5+ people gathered:
- 0.0s: Hear "whoosh" (buildup_start)
- 0.5s: Hear "beep-beep" (buildup_pulse)
- 1.0s: Hear "beep-beep" (buildup_pulse)
- 1.5s: Party music explodes!

## Implementation Checklist

- [x] State machine produces `party_buildup_progress` (0.0-1.0)
- [x] Detector triggers `play_sfx("buildup_start")` at 0%
- [x] Detector triggers `play_sfx("buildup_pulse")` at 33% and 66%
- [x] Audio manager has buildup SFX mapped
- [x] Packet builder includes progress field
- [x] UDP packets broadcast @ 30fps with progress
- [x] CLI accepts audio flags
- [x] All Python files compile (✅ verified)

## What's Ready for Testing

✅ **Python Master**: Fully implemented
- Detects state changes
- Calculates build-up progress
- Plays SFX automatically
- Broadcasts packets with progress

⏳ **ESP32 Firmware**: Waiting for implementation
- Parse `party_buildup_progress` field
- Render build-up effects based on 0.0-1.0 value
- See [PHASE_3_GUIDE.md](PHASE_3_GUIDE.md) for details

⏳ **SFX Audio Files**: Optional
- Use `generate_test_sfx.py` for placeholders
- Or source real MP3s from Freesound, BBC, etc.

## State Machine Timing Reference

```
Event: 5th person arrives + sustained

0.00s ─ Detection
2.00s ─ PARTY_DWELL expires (sustained ≥5 people)
      ├─ party_buildup_progress = 0.0 → 0.01
      └─ play_sfx("buildup_start")

2.50s ─ 33% through build-up (0.5s elapsed of 1.5s)
      ├─ party_buildup_progress = 0.33
      └─ play_sfx("buildup_pulse")

3.00s ─ 66% through build-up (1.0s elapsed)
      ├─ party_buildup_progress = 0.66
      └─ play_sfx("buildup_pulse")

3.55s ─ Build-up complete
      ├─ party_buildup_progress = 1.0
      ├─ state changes to PARTY
      ├─ audio state changes to PARTY
      └─ play_music("party_upbeat")
```

## UDP Packet Example (During Build-Up)

```json
{
  "version": 2,
  "timestamp": 1739043855.123,
  "fps": 29.8,
  "state": "FIRE",
  "people": [
    {"id": 1, "bbox": [0.2, 0.1, 0.4, 0.9], "shirt_rgb": [220, 100, 50], "shirt_name": "Orange"},
    {"id": 2, "bbox": [0.5, 0.2, 0.7, 0.85], "shirt_rgb": [50, 100, 220], "shirt_name": "Blue"},
    {"id": 3, "bbox": [0.3, 0.3, 0.5, 0.9], "shirt_rgb": [220, 220, 50], "shirt_name": "Yellow"},
    {"id": 4, "bbox": [0.6, 0.1, 0.8, 0.8], "shirt_rgb": [220, 50, 100], "shirt_name": "Red"},
    {"id": 5, "bbox": [0.4, 0.4, 0.6, 0.95], "shirt_rgb": [100, 220, 100], "shirt_name": "Green"}
  ],
  "phone_detected": false,
  "dominant_palette": [220, 100, 50, 50, 100, 220, 220, 220, 50, 220, 50, 100],
  "prompt": "FIVE FLAMES = PURE ENERGY!",
  "mist_pwm": 255,
  "fan_pwm": 255,
  "pulse_active": false,
  "entry_flash_id": null,
  "audio_state": "AMBIENT",
  "party_buildup_progress": 0.66
}
```

## Audio Manager API (Used by Detector)

```python
# Initialize (automatic in detector.__init__)
if enable_audio:
    self.audio_manager = AudioManager(
        enabled=True,
        master_volume=0.7,
        narration_enabled=False
    )
    self.audio_manager.start()

# Trigger SFX (non-blocking)
self.audio_manager.play_sfx("buildup_start", volume=0.9)
self.audio_manager.play_sfx("buildup_pulse", volume=0.7)

# Trigger music
self.audio_manager.play_music("party_upbeat", loop=True, volume=1.0)

# Trigger TTS
self.audio_manager.speak("Get ready for the party!")

# Manage state
self.audio_manager.set_state(AudioState.AMBIENT)
```

## Graceful Degradation

If audio files don't exist:
- ✅ No error (logs warning only)
- ✅ Detector continues at 30fps
- ✅ Packets still broadcast with progress
- ✅ ESP32 still receives data
- ✅ LEDs still render effects

Audio is optional enhancement, not critical path.

## Next Steps

1. **Test Current Implementation:**
   ```bash
   python generate_test_sfx.py
   python src/bond_fire_vision/cli.py --enable-audio --camera-index 0
   ```

2. **Verify Build-Up:**
   - Gather 5+ people in ROI
   - Listen for: whoosh → beep-beep → beep-beep → party music

3. **Implement ESP32 Firmware:**
   - See [PHASE_3_GUIDE.md](PHASE_3_GUIDE.md)
   - Parse `party_buildup_progress` field
   - Render LED effects based on progress value

4. **Optional: Get Real Audio:**
   - Replace generated .wav with proper .mp3 files
   - Keep file names consistent (buildup_start.mp3, etc.)

That's it! Python is complete and ready to go. 🚀
