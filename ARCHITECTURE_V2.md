# Bondfire Architecture v2.0 - Master/Slave Migration

**Date:** February 5, 2026  
**Status:** Implementation Ready  
**Author:** Systems Architecture Review

---

## Executive Summary

Migration from "Hybrid Logic" (Python detection + ESP32 effects) to "Master/Slave" architecture where Python owns 100% of logic and ESP32 acts as a pure hardware driver.

**Goals:**
- Eliminate OpenAI dependency and cloud latency
- Enable rich per-person tracking with color analysis
- Create fire-centric experience that scales with crowd size
- Support audio narration and atmospheric sound effects
- Maintain 30fps responsiveness

---

## Architecture Overview

### Python Master (`vision/`)
**Role:** The "Brain"
- YOLOv8 person tracking with persistent IDs
- Dominant shirt color extraction and naming
- State machine evaluation (IDLE → FIRE → PARTY, PHONE override)
- Local prompt generation (state-aware dictionaries)
- Audio orchestration (SFX, music, optional TTS)
- JSON packet assembly and UDP broadcast @ 30fps

**Key Modules:**
- `detector.py` - Main vision loop with tracking
- `color_analysis.py` - RGB extraction, clustering, color naming
- `state_machine.py` - Event-driven state transitions with timers
- `local_prompts.py` - Curated prompt dictionaries
- `audio_manager.py` - Non-blocking audio playback
- `packet_builder.py` - Schema v2.1 serialization

### ESP32 Slave (`hardware/bondfire_v2.ino`)
**Role:** The "Hands"
- Receive UDP packets (ArduinoJson)
- Parse and validate protocol version
- Drive hardware outputs:
  - LED Ring (FastLED): Fire effects, color pulses, party modes
  - LED Matrix (Adafruit_NeoMatrix): Scrolling text
  - Mist atomizer (PWM with safety floor)
  - Fan (PWM with linear scaling)
- Enforce safety limits
- No decision-making logic

---

## State Machine

### State Definitions

| State | Trigger | Exit | Visual | Audio | Hardware |
|-------|---------|------|--------|-------|----------|
| **IDLE** | 0 people for ≥2s | First person | Blue embers, slow breathing | Silence | Mist: 150, Fan: 60 |
| **FIRE** | 1-4 people | Phone OR ≥5 people | Fire intensity scales with count, 15s color pulse, entry flash | Fire crackle (volume scales), ambient music | Mist: 180+(count×15), Fan: 100+(count×30) |
| **PARTY** | ≥5 people for ≥2s | <4 people for 3s | Rainbow cycling through shirt colors, strobing | Party music, celebration SFX | Mist: 255, Fan: 255 |
| **PHONE** | Any phone in ROI | Phone absent ≥2s | Red glitch palette, random pops | Buzzer SFX, snarky TTS | Mist: 150, Fan: 0 |

### Fire Mode Behaviors (Main Mode)

**Intensity Scaling (1-4 people):**
- 1 person: Gentle flicker (25% brightness)
- 2 people: Medium flame (50% brightness)
- 3 people: Strong fire (75% brightness)
- 4 people: Roaring blaze (100% brightness)

**Color Pulse (Every 15s):**
- Collect all active people's shirt colors
- Blend colors using FastLED palette interpolation
- Pulse ring with combined palette over 2-3 seconds
- Return to fire palette

**Entry Flash (New Person Detection):**
- Track new ID assignment from YOLO
- Flash ring with newcomer's shirt color for 3 seconds
- Optional: "Welcome!" TTS narration
- Whoosh SFX

**Fan/Mist Formula:**
```python
fan_pwm = constrain(100 + (people_count * 30), 100, 255)
mist_pwm = constrain(180 + (people_count * 15), 180, 255)
```

---

## JSON Packet Schema v2.1

### Wire Format
```json
{
  "version": 2,
  "timestamp": 1738713600.5,
  "fps": 29.8,
  "state": "FIRE",
  "people": [
    {
      "id": 42,
      "bbox": [0.25, 0.3, 0.45, 0.8],
      "shirt_rgb": [220, 85, 45],
      "shirt_name": "Burnt Orange"
    }
  ],
  "phone_detected": false,
  "dominant_palette": [220, 85, 45, 180, 120, 90],
  "prompt": "Two flames dancing—who's braver, bro?",
  "mist_pwm": 210,
  "fan_pwm": 160,
  "pulse_active": false,
  "entry_flash_id": null,
  "audio_state": "AMBIENT"
}
```

### Field Specifications

| Field | Type | Required | Range/Format | Notes |
|-------|------|----------|--------------|-------|
| `version` | integer | ✓ | `2` | Protocol gate; ESP32 rejects if mismatch |
| `timestamp` | float | ✓ | Unix epoch, monotonic | For ordering/interpolation |
| `fps` | float | ✓ | 0.0–60.0 | Diagnostic; actual send rate |
| `state` | string | ✓ | `IDLE`, `FIRE`, `PARTY`, `PHONE` | Current master state |
| `people` | array | ✓ | Max 6 entries | Active tracked people |
| `people[].id` | integer | ✓ | ≥0 | Stable YOLO track ID |
| `people[].bbox` | array | ✓ | 4 floats, 0.0–1.0 | Normalized [x1,y1,x2,y2] |
| `people[].shirt_rgb` | array | ✓ | 3 ints, 0–255 | Dominant color |
| `people[].shirt_name` | string | ✓ | 1–24 chars | Human-readable color |
| `phone_detected` | boolean | ✓ | — | Any phone in ROI |
| `dominant_palette` | array | ✓ | 3–12 ints (RGB tuples) | Up to 4 colors for LED palette |
| `prompt` | string | ✓ | ≤120 chars | Display text |
| `mist_pwm` | integer | ✓ | 0–255 | Suggested mist level |
| `fan_pwm` | integer | ✓ | 0–255 | Suggested fan level |
| `pulse_active` | boolean | ✓ | — | True during 15s color pulse |
| `entry_flash_id` | integer/null | ✓ | Track ID or `null` | Triggers entry flash animation |
| `audio_state` | string | ✓ | `SILENT`, `AMBIENT`, `PARTY`, `ALERT` | Audio context hint |

---

## Audio System

### Architecture
- **Audio Manager Thread:** Non-blocking queue-based worker (similar to OpenAI prompt pattern)
- **Channels:**
  - `SFX`: Fire crackle, whoosh, buzzer, party horn
  - `MUSIC`: Ambient loop, party track
  - `NARRATION`: Optional TTS (pyttsx3 or pre-recorded)
- **Library:** `pygame.mixer` for simplicity (3 channels: music, sfx_primary, sfx_secondary)

### Asset Requirements
```
vision/assets/
├── sfx/
│   ├── fire_crackle_loop.mp3      # 30s loop, volume scales 0.2–1.0
│   ├── whoosh_entry.mp3           # 1s, plays on person entry
│   ├── buzzer_alert.mp3           # 0.5s, phone detected
│   └── party_horn.mp3             # 2s, party mode entry
├── music/
│   ├── ambient_chill.mp3          # 3min loop, FIRE mode
│   └── party_upbeat.mp3           # 3min loop, PARTY mode
└── narration/
    └── (optional TTS output cache)
```

### Trigger Map
| Event | SFX | Music | Narration |
|-------|-----|-------|-----------|
| IDLE entry | — | Stop all | — |
| FIRE entry | Fire crackle (loop) | Ambient (loop) | — |
| New person | Whoosh | — | "Welcome!" (optional) |
| 15s pulse | Soft chime | — | — |
| PARTY entry | Party horn | Party track | "Let's go!" |
| PHONE detect | Buzzer | Stop music | Snarky TTS |
| PHONE exit | — | Resume prior | — |

### Configuration
- `--enable-audio`: Enable audio subsystem
- `--audio-volume`: Master volume (0.0–1.0, default 0.7)
- `--narration-enabled`: Enable TTS prompts
- `--pulse-interval`: Seconds between color pulses (default 15)

---

## Color Analysis

### Extraction Pipeline
1. **Region Selection:** Use YOLO bbox to crop person region
2. **Torso Isolation:** Sample middle 40% vertically (chest area)
3. **Color Clustering:** k-means (k=3) on non-grayscale pixels
4. **Dominant Selection:** Largest cluster centroid
5. **Naming:** Nearest neighbor lookup in CSS color dictionary + saturation/lightness rules

### Color Name Mapping
- **Base Dictionary:** 140 CSS named colors
- **Fallback Rules:**
  - Low saturation (<30) → "Gray", "White", "Black"
  - High saturation + Hue ranges → "Red", "Orange", "Yellow", "Green", "Cyan", "Blue", "Purple", "Magenta"
- **Examples:**
  - `[220, 85, 45]` → "Burnt Orange"
  - `[50, 150, 200]` → "Steel Blue"
  - `[200, 200, 205]` → "Light Gray"

---

## Prompt System

### Structure
- **State Dictionaries:** Pre-written prompts grouped by state
- **Dynamic Tokens:** `{count}`, `{colors}`, `{name}` for personalization
- **Rotation:** Track last N prompts to avoid repetition
- **Fallbacks:** Generic prompts if dynamic data missing

### Example Prompts

**IDLE:**
- "Social Battery: 0%. I need a spark..."
- "Waiting for brave souls..."
- "The fire sleeps. Wake it up."

**FIRE (1 person):**
- "One spark. But fires need friends."
- "Lone flame detected. Battery: 20%"

**FIRE (2-3 people):**
- "Two flames dancing—who's braver, bro?"
- "Three's a fire. One more for a blaze!"
- "Colors clashing—love it! Keep it going."

**FIRE (4 people):**
- "Almost there! Find one more legend."
- "Four flames roaring. One more for chaos!"

**PARTY (≥5 people):**
- "CRITICAL MASS ACHIEVED! 🔥"
- "FIVE FLAMES = PURE ENERGY!"
- "THIS IS WHAT CONNECTION LOOKS LIKE!"

**PHONE:**
- "Signal interference. Pocket that, bro."
- "Phones kill vibes. Disconnect to connect."
- "Put it away lah, we're here now."

---

## Implementation Roadmap

### Phase 2: Python Master (Current)

**2.1 Core Infrastructure**
- [x] Audit existing code
- [x] Design v2.1 schema
- [ ] Create `color_analysis.py`
- [ ] Create `state_machine.py`
- [ ] Create `local_prompts.py`
- [ ] Create `audio_manager.py`
- [ ] Create `packet_builder.py`

**2.2 Detector Refactor**
- [ ] Switch `model()` → `model.track()` for persistent IDs
- [ ] Integrate color extraction per person
- [ ] Wire state machine into main loop
- [ ] Replace OpenAI with local prompts
- [ ] Add audio manager integration
- [ ] Update packet builder calls

**2.3 CLI Enhancement**
- [ ] Add `--enable-audio`, `--audio-volume`, `--narration-enabled`
- [ ] Add `--pulse-interval` (default 15)
- [ ] Add `--dry-run` with packet logging
- [ ] Remove OpenAI-specific flags (deprecate gracefully)

**2.4 Testing**
- [ ] Unit tests: color naming, state transitions
- [ ] Integration test: mock YOLO outputs → validate packets
- [ ] Manual test: Replay recorded video with tracking visualization

### Phase 3: ESP32 Slave

**3.1 Firmware Rewrite**
- [ ] Create `bondfire_v2.ino`
- [ ] Implement v2.1 JSON parser (version check)
- [ ] Add `pulse_active` animation handler
- [ ] Add `entry_flash_id` flash logic
- [ ] Scale fire effect by `people.length`
- [ ] Implement PARTY mode rainbow cycling
- [ ] Preserve safety floors (mist ≥150)

**3.2 Hardware Testing**
- [ ] Bench test packet ingestion
- [ ] Verify color palette rendering
- [ ] Test pulse/flash timings
- [ ] Load test at 30fps sustained

---

## Safety & Operations

### Python Master
- **Graceful Degradation:**
  - Camera failure → log error, retry with exponential backoff
  - Audio assets missing → disable audio, continue visual operation
  - Network error → log, skip packet, continue loop
- **Resource Limits:**
  - Max 6 tracked people (YOLO performance)
  - Packet size <1KB for UDP reliability
  - FPS target 30, tolerate 25–35 range

### ESP32 Slave
- **Safety Floors:**
  - Mist PWM: Never <150 (humidifier protection)
  - Fan PWM: Never >255 (motor protection)
- **Watchdog:**
  - If no packet for 5 seconds → revert to IDLE state
  - WiFi disconnect → show "RECONNECTING" on matrix
- **Validation:**
  - Reject packets if `version != 2`
  - Clamp all PWM values to [0, 255]
  - Cap array lengths to prevent buffer overflow

---

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Packet Rate | 30 fps | Python: `time.monotonic()` delta |
| Detection Latency | <50ms | YOLO inference time |
| Color Extraction | <10ms | Per-person sampling time |
| State Transition | <5ms | State machine evaluation |
| Audio Queue Lag | <100ms | Queue depth monitoring |
| ESP32 Parse Time | <15ms | `millis()` delta in loop |
| LED Refresh | 30 fps | FastLED.show() frequency |

---

## Testing Strategy

### Python Unit Tests
```python
# test_color_analysis.py
def test_color_naming():
    assert get_color_name([220, 85, 45]) == "Burnt Orange"
    assert get_color_name([200, 200, 205]) == "Light Gray"

# test_state_machine.py
def test_fire_to_party_transition():
    sm = StateMachine()
    sm.update(people_count=4)
    assert sm.state == State.FIRE
    sm.update(people_count=5)
    time.sleep(2.1)  # Wait for dwell timer
    sm.update(people_count=5)
    assert sm.state == State.PARTY
```

### Integration Test
```bash
# Record test footage
python vision/main.py --dry-run --record packets.jsonl --camera-index 0

# Replay and validate
python tests/validate_packets.py packets.jsonl
# Checks: schema compliance, FPS consistency, state logic
```

### Manual ESP32 Test
```bash
# Send test packets
python vision/manual_packet_sender.py --schema v2 --preset fire_3_people
python vision/manual_packet_sender.py --preset party
python vision/manual_packet_sender.py --preset phone_penalty
```

---

## Migration Checklist

- [x] Phase 0: Audit complete
- [x] Phase 1: Planning and schema design
- [ ] Phase 2: Python implementation
  - [ ] Core modules (color, state, prompts, audio, packets)
  - [ ] Detector refactor with tracking
  - [ ] CLI updates
  - [ ] Testing suite
- [ ] Phase 3: ESP32 firmware
  - [ ] `bondfire_v2.ino` implementation
  - [ ] Hardware testing
  - [ ] Safety validation
- [ ] Phase 4: Deployment
  - [ ] Audio asset acquisition/creation
  - [ ] Field testing (live event)
  - [ ] Performance tuning
  - [ ] Documentation finalization

---

## Appendix A: Migration from v1

### Breaking Changes
- **Packet Format:** v1 `{"c","p","t"}` → v2.1 (full schema)
- **ESP32 Code:** Complete rewrite required
- **Python Entry Point:** CLI flags changed (OpenAI flags removed)

### Backward Compatibility
- `manual_packet_sender.py` supports both `--schema v1` and `--schema v2`
- Old firmware can remain on dev branch for reference
- New firmware rejects v1 packets (version gate)

### Data Migration
- No persistent data; runtime-only migration
- YOLO track IDs start fresh on each run
- Audio assets are new additions

---

## Appendix B: Future Enhancements

**Phase 4+ Ideas:**
- **Multi-camera fusion:** Track people across multiple angles
- **Gesture detection:** Wave to add sparkle effects
- **Mobile app:** View current state, request prompts
- **Cloud analytics:** Log engagement metrics (optional)
- **RGB strip integration:** Extend LED effects to venue walls
- **Haptic feedback:** Vibration motors in installation base
- **3D fire mapping:** Project fire onto surfaces with depth camera

---

**Document Version:** 1.0  
**Last Updated:** February 5, 2026  
**Next Review:** Post Phase 2 Implementation
