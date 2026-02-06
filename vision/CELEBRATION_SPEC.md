# Phone Exit Celebration Specification

## Overview
When a phone is detected and then removed, the system triggers a celebration to reward the user for putting their phone away.

## Timing & Flow

### Detection Timeline
```
0.0s  → Phone detected
      → PHONE state activated
      → Phone warning prompts display

...   → User puts phone away

0.0s  → Phone no longer detected
0.5s  → Phone exit timer completes (PHONE_EXIT_DWELL)
      → State returns to previous state (FIRE/PARTY/IDLE)
      → celebration flag = True

0.5s-1.5s → Celebration active (5 frames @ ~5fps)
          → Single celebration prompt displayed
          → Party horn SFX plays
          → celebration flag sent in packet

1.5s+ → Celebration ends
      → Returns to normal prompts
      → celebration flag = False
```

## Software Implementation

### Vision System (Python)
- **State Machine**: Sets `phone_just_exited=True` for one frame when phone exit timer completes
- **Detector**: 
  - Stores celebration prompt once (doesn't toggle between prompts)
  - Displays celebration for 5 frames (~1 second)
  - Plays party horn sound effect
  - Speaks celebration prompt via TTS (if enabled)
  - Sends `celebration=True` in UDP packet

### Celebration Prompts
Random selection from:
- "🎉 YES! WELCOME BACK TO THE FIRE!"
- "✨ SMART CHOICE! LET'S BURN!"
- "🔥 ATTENTION RESTORED. FIRE APPROVED!"
- "🌟 NOW WE'RE TALKING!"
- "💫 CONNECTION RESTORED. WITH THE FIRE!"
- "🎊 THAT'S WHAT WE NEEDED!"
- "👏 YOU DID IT! THE FIRE CELEBRATES YOU!"

## Hardware Implementation (Arduino/ESP32)

### Packet Field
```json
{
  "celebration": true,  // True for ~1 second after phone exit
  "state": "FIRE",      // Returns to previous state
  "prompt": "🎉 YES! WELCOME BACK TO THE FIRE!",
  "mist_pwm": 180,      // Normal state values
  "fan_pwm": 130
}
```

### Recommended Visual Effects

#### Option 1: Rainbow Pulse (Recommended)
- Duration: 1 second
- Effect: Cycle through rainbow colors on LED strip
- Speed: Fast rainbow chase or strobe
- Brightness: 100% during celebration, then fade to normal

#### Option 2: Bright Flash Sequence
- Duration: 1 second
- Effect: 3-5 rapid bright white flashes
- Flame: Temporarily boost mist + fan PWM (e.g., +50 PWM for 200ms bursts)
- Then return to normal state PWM values

#### Option 3: Sparkle Effect
- Duration: 1 second
- Effect: Random LED sparkles in white/gold
- Frequency: High (50+ sparkles/second)
- Combined with normal flame operation

### Implementation Pseudocode
```cpp
// In main Arduino loop when receiving packet:
if (packet.celebration && !celebration_active) {
    // Start celebration
    celebration_active = true;
    celebration_start = millis();
    celebration_effect = RAINBOW_PULSE; // or FLASH_SEQUENCE or SPARKLE
}

if (celebration_active) {
    unsigned long elapsed = millis() - celebration_start;
    
    if (elapsed < 1000) {  // 1 second celebration
        // Execute celebration effect
        switch (celebration_effect) {
            case RAINBOW_PULSE:
                drawRainbowPulse(elapsed);
                break;
            case FLASH_SEQUENCE:
                drawFlashSequence(elapsed);
                break;
            case SPARKLE:
                drawSparkleEffect(elapsed);
                break;
        }
    } else {
        // Celebration over, return to normal
        celebration_active = false;
    }
} else {
    // Normal state-based lighting
    drawStateBasedLighting(packet.state, packet.dominant_palette);
}
```

### Audio Coordination
- Vision system plays party horn sound (0.8 volume)
- Hardware can optionally trigger additional audio feedback
- TTS narration speaks celebration prompt (if enabled)

## Testing Checklist
- [ ] Phone detected → PHONE prompts show
- [ ] Phone removed → 0.5s delay → celebration triggers
- [ ] Single celebration prompt displays (doesn't toggle)
- [ ] Celebration lasts ~1 second (5 frames)
- [ ] Party horn plays at celebration start
- [ ] Packet `celebration=true` sent for ~1 second
- [ ] After celebration → returns to normal state prompts
- [ ] Hardware shows celebration visual effect (if implemented)

## Configuration

### Tunable Parameters
```python
# state_machine.py
PHONE_EXIT_DWELL = 0.5  # Seconds without phone to trigger celebration

# detector.py
_celebration_frames_remaining = 5  # Frames to show celebration (~1 sec @ 5fps)

# local_prompts.py
PHONE_EXIT_PROMPTS = [...]  # List of celebration messages
```

## Design Notes
- **Fast response**: 0.5s exit dwell for immediate gratification
- **Visible duration**: 5 frames ensures celebration is noticed
- **Single prompt**: Stored once to avoid distracting toggles
- **Hardware flexibility**: Celebration flag allows custom effects without changing vision system
