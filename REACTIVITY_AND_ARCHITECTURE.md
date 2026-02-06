# Bond Fire Reactivity & Light Architecture Guide

## Summary of Changes Made

### 1. ✅ Increased Bounding Box Detection
- Added **25px margin** to ROI boundary detection in [detector.py](vision/src/bond_fire_vision/detector.py)
- People at edges of ROI now included even if center is slightly outside
- Prevents "lost" detections at frame boundaries

### 2. ✅ Faster Phone Detection
- Phone detection is now **instant (0.0s)**
- No entry hysteresis—phone appears → system reacts immediately
- Exit still requires 2.0s (prevents jitter from brief occlusions)
- Field: `PHONE_ENTRY_DWELL = 0.0`

### 3. ✅ Supernova Build-Up Effect
- New timing constant: `PARTY_ENTRY_BUILDUP = 1.5` seconds
- When ≥5 people detected, system now enters "build-up phase":
  - Waits 2.0s with ≥5 people (PARTY_DWELL)
  - Then 1.5s build-up phase (lights show anticipation)
  - Then full PARTY state (supernova release)
- New field in `StateOutput`: `party_buildup_progress` (0.0 → 1.0)
- See "Build-Up Effects" section below

---

## Architecture: Who Controls the Lights?

### **Answer: Hybrid Master/Slave with Local Decision-Making**

```
┌─────────────────────────────────────────────────────────────────────┐
│ Python Master (Vision Loop @ 30fps)                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. Detects people + extracts shirt colors                          │
│  2. Evaluates state machine (IDLE→FIRE→PARTY→PHONE)                 │
│  3. Generates prompts + audio cues                                  │
│  4. Builds UDP packet with:                                         │
│     • State name (IDLE, FIRE, PARTY, PHONE)                        │
│     • Dominant palette (shirt colors blended)                       │
│     • Party buildup progress (0.0-1.0)                              │
│     • PWM targets (mist, fan)                                       │
│     • Effect flags (pulse_active, entry_flash_id, etc)              │
│  5. Broadcasts @ 30fps                                              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                              UDP Port 4210
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│ ESP32 Slave (Hardware Driver)                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. Receives packet, validates protocol version                     │
│  2. Parses state, colors, buildup_progress, effect flags            │
│  3. LOCAL LOGIC:                                                    │
│     • IDLE state → Idle breathing animation (blue embers)           │
│     • FIRE state → Fire effect, color pulse every 15s, entry flash │
│     • PARTY state → Rainbow strobe + buildup "anticipation" FX      │
│     • PHONE state → Red glitch palette, random strobes              │
│  4. PWM outputs:                                                    │
│     • Mist atomizer: Directly from packet mist_pwm                  │
│     • Fan: Directly from packet fan_pwm                             │
│  5. LED Ring (FastLED):                                             │
│     • Renders state-specific effects using shirt colors             │
│     • Uses dominant_palette array for blending                      │
│  6. LED Matrix:                                                     │
│     • Displays prompt text                                          │
│     • Uses audio_state hint for animation style                     │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### **Key Principle: Python Decides WHAT, ESP32 Decides HOW**

| Aspect                    | Python Master                  | ESP32 Slave              |
| ------------------------- | ------------------------------ | ------------------------ |
| **State Machine**         | ✅ Evaluates (IDLE→FIRE→PARTY)  | ❌ Just receives          |
| **Color Analysis**        | ✅ Extracts shirt colors        | ❌ Just receives RGB      |
| **Prompt Generation**     | ✅ Generates text               | ❌ Just displays it       |
| **Audio Cues**            | ✅ Triggers SFX/music           | ❌ Uses audio_state hint  |
| **LED Effect Rendering**  | ❌ Too heavy for Python         | ✅ Renders in real-time   |
| **Animation Timing**      | ❌ Can't guarantee ms precision | ✅ Hardware PWM timers    |
| **PWM Output**            | ❌ Software PWM too noisy       | ✅ Clean hardware PWM     |
| **Palette Interpolation** | ❌ Expensive every frame        | ✅ Local FastLED blending |

---

## Reactivity Timeline

### **Person Entry (Fast)**

```
0.00s: Person detected by YOLOv8
0.01s: Color extracted, state machine updated
0.03s: UDP packet built and broadcast
0.05s: ESP32 receives packet, entry_flash_id detected
0.08s: Entry flash animation starts (3s duration)
0.10s: Entry TTS/whoosh audio plays

TOTAL: ~100ms from detection to light reaction
```

### **Person Exit (Slow for Stability)**

```
0.00s: Person leaves ROI (no longer detected)
0.00s: State machine note: 1→0 people
2.00s: Still 0 people, IDLE_TIMEOUT expires
2.03s: State change to IDLE broadcast in packet
2.10s: ESP32 switches to IDLE animation (blue breathing)
5.00s: Mist atomizer winds down (ramps to 150)
```

**Why the delay?** 
- Prevents FIRE→IDLE→FIRE flickering when someone briefly exits ROI
- Person gets up, walks to get a drink (5 seconds) → system should stay ready
- Better UX than instant off/on cycling

### **5th Person Arrives (Supernova Build-Up)**

```
0.00s: 5 people detected (first time)
0.01s: State machine: Count ≥ 5 for first time
0.03s: Packet broadcast (still in FIRE state)

2.00s: 5 people sustained for 2.0s
2.05s: PARTY_DWELL timer expires, buildup phase begins
2.08s: party_buildup_progress = 0.0, broadcast packet

BUILD-UP PHASE (1.5 seconds):
├─ 2.08s: buildup_progress = 0.0 → ESP32 starts "charging" animation
├─ 2.40s: buildup_progress = 0.33 → Lights intensify
├─ 2.80s: buildup_progress = 0.66 → Fan/mist ramp up
└─ 3.50s: buildup_progress = 1.0 → Ready for explosion

3.58s: PARTY state achieved, party_buildup_progress = 0.0
3.60s: Full supernova animation begins (rainbow strobing, max fan/mist)
```

---

## Build-Up Effects (ESP32 Implementation Guide)

The Python master now sends `party_buildup_progress` during the 1.5-second countdown to party:

### **What ESP32 Should Render**

```cpp
if (state == "FIRE" && party_buildup_progress > 0.0) {
    // Build-up phase active
    
    // Technique 1: Brightness ramp
    brightness = 100 + (party_buildup_progress * 155);  // 100 → 255
    
    // Technique 2: Frequency increase
    // Pulse the colors faster as progress increases
    pulse_speed = 1.0 + (party_buildup_progress * 4.0);  // 1x → 5x speed
    
    // Technique 3: Fan/Mist "spin-up"
    // Ramp hardware harder during buildup
    fan_anticipation = fan_pwm + (party_buildup_progress * 50);
    
    // Technique 4: Color saturation boost
    // Make shirt colors more vivid as buildup progresses
    saturation = 1.0 + (party_buildup_progress * 0.3);  // +30% saturation
    
} else if (state == "PARTY") {
    // Full supernova mode
    // Rainbow cycling, strobing, maximum intensity
}
```

**Example pseudocode for strobe intensity:**
```cpp
// During buildup, gradually increase strobe intensity
float strobe_brightness = 50 + (party_buildup_progress * 205);  // 50→255
float strobe_rate = 2.0 + (party_buildup_progress * 8.0);  // 2→10 Hz

// Ring pulses faster and brighter as buildup progresses
fill_solid(leds, NUM_LEDS, CRGB(
    shirt_rgb[0] * (strobe_brightness / 255),
    shirt_rgb[1] * (strobe_brightness / 255),
    shirt_rgb[2] * (strobe_brightness / 255)
));
```

---

## Timing Reference Table

| Transition             | Python Decision Time | ESP32 React Time | Total Latency       |
| ---------------------- | -------------------- | ---------------- | ------------------- |
| Person enters          | ~30ms (next frame)   | ~50ms (receive)  | **80ms**            |
| Entry flash starts     | —                    | ~80ms            | **80ms**            |
| Person leaves (→IDLE)  | 5.0s + 30ms          | 50ms             | **5.08s**           |
| Phone detected         | ~30ms                | ~50ms            | **80ms** (instant!) |
| Phone released (→FIRE) | 2.0s (dwell) + 30ms  | 50ms             | **2.08s**           |
| Build-up starts        | 2.0s (party dwell)   | 50ms             | **2.05s**           |
| Supernova achieved     | 2.0s + 1.5s build-up | 50ms             | **3.55s**           |

---

## What Packets Actually Contain

Every 33ms (30fps), Python sends this:

```json
{
  "version": 2,
  "state": "FIRE",
  "people": [
    {"id": 1, "bbox": [0.3, 0.2, 0.5, 0.8], "shirt_rgb": [220, 100, 50], "shirt_name": "Orange"},
    {"id": 2, "bbox": [0.6, 0.3, 0.75, 0.85], "shirt_rgb": [50, 100, 220], "shirt_name": "Blue"}
  ],
  "dominant_palette": [220, 100, 50, 50, 100, 220],
  "mist_pwm": 210,
  "fan_pwm": 160,
  "pulse_active": false,
  "entry_flash_id": null,
  "party_buildup_progress": 0.0,
  "prompt": "Two flames dancing—who's braver, bro?",
  "audio_state": "AMBIENT"
}
```

**ESP32 uses:**
- `state` → Pick which animation logic to run
- `people[].shirt_rgb` + `dominant_palette` → Colors for LED effects
- `mist_pwm`, `fan_pwm` → Direct PWM output
- `pulse_active` → Trigger color pulse animation
- `entry_flash_id` → Flash that person's color
- `party_buildup_progress` → Ramp up intensity/strobing
- `prompt` → Scroll on matrix
- `audio_state` → Animation style hint

---

## Summary: Reactivity Profile

| Event                     | Reaction Time               | User Perception                     |
| ------------------------- | --------------------------- | ----------------------------------- |
| **New person enters**     | 80ms                        | Instant! (imperceptible)            |
| **Person waves/moves**    | 30ms per frame              | Smooth real-time tracking           |
| **Phone comes out**       | 80ms                        | Quick red alert                     |
| **5th person arrives**    | 3.55s total                 | Epic 1.5s build-up before fireworks |
| **Person leaves briefly** | No reaction (5s hysteresis) | System stays "hot"                  |
| **Everyone leaves**       | 5.08s total                 | Graceful fade to idle               |

**Bottom line:** Fast entry (80ms), slow exit (5s), epic build-up (1.5s). This is intentional for UX.

---

## Next: Implement in ESP32 Firmware

See [PHASE_3_GUIDE.md](PHASE_3_GUIDE.md) for the full firmware roadmap including:
- JSON parsing with ArduinoJson
- FastLED effect rendering
- Build-up animation state machine
- Safety PWM clamping
- Network error handling
