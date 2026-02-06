# Phase 3 - ESP32 Firmware Implementation Guide

**Status:** Ready for Implementation  
**Estimated Effort:** 4-6 hours  
**Complexity:** Medium  

---

## Overview

The ESP32 firmware (`bondfire_v2.ino`) transforms from a semi-intelligent driver into a **pure reactive slave** that:

1. Receives v2.1 JSON packets over UDP
2. Parses and validates the protocol
3. Maps state/effects to hardware outputs
4. Executes animations locally

**Key Principle:** All decision-making happens in Python. ESP32 only executes.

---

## Architecture

```
┌─────────────────────────────────────┐
│    Python Master (vision/main.py)   │
│  - YOLOv8 tracking                  │
│  - State machine                    │
│  - Local prompts                    │
│  - Packet assembly                  │
└────────────────┬────────────────────┘
                 │ UDP Broadcast
                 │ (port 4210)
                 ▼
         ┌───────────────────┐
         │  ESP32 Slave      │
         │ (bondfire_v2.ino) │
         ├───────────────────┤
         │ • JSON Parser     │ ← Receive packet
         │ • State Handler   │ ← Map state
         │ • Effect Engine   │ ← Animate
         │ • PWM Driver      │ ← Hardware control
         └────────┬──────────┘
                  │
        ┌─────────┼─────────┐
        │         │         │
        ▼         ▼         ▼
     LEDS      MIST       FAN
    (Ring)   (Atomizer)  (PWM)
```

---

## Implementation Phases

### Phase 3.1: Foundation (Network + Parser)

**Goal:** Receive and validate packets

```cpp
#include <ArduinoJson.h>

const size_t PACKET_CAPACITY = JSON_OBJECT_SIZE(15);

void setup() {
    // WiFi connection (existing code)
    udp.begin(localPort);
}

void loop() {
    int packetSize = udp.parsePacket();
    if (!packetSize) return;

    char buffer[512];
    int len = udp.read(buffer, 511);
    buffer[len] = 0;

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, buffer);
    
    if (error) {
        Serial.printf("JSON parse error: %s\n", error.c_str());
        return;
    }

    // Validate protocol version
    int version = doc["version"];
    if (version != 2) {
        Serial.printf("Version mismatch: expected 2, got %d\n", version);
        return;
    }

    handlePacket(doc);
}
```

### Phase 3.2: State Mapping

**Goal:** Map state string to hardware outputs

```cpp
enum DisplayState {
    STATE_IDLE,
    STATE_FIRE,
    STATE_PARTY,
    STATE_PHONE
};

struct StateConfig {
    DisplayState state;
    uint8_t mist_pwm;
    uint8_t fan_pwm;
    float fire_intensity;
    bool pulse_active;
    int entry_flash_id;
};

StateConfig currentStateConfig;

void handlePacket(JsonDocument& doc) {
    const char* stateStr = doc["state"];
    
    if (strcmp(stateStr, "IDLE") == 0) {
        currentStateConfig.state = STATE_IDLE;
    } else if (strcmp(stateStr, "FIRE") == 0) {
        currentStateConfig.state = STATE_FIRE;
    } else if (strcmp(stateStr, "PARTY") == 0) {
        currentStateConfig.state = STATE_PARTY;
    } else if (strcmp(stateStr, "PHONE") == 0) {
        currentStateConfig.state = STATE_PHONE;
    }

    currentStateConfig.mist_pwm = doc["mist_pwm"];
    currentStateConfig.fan_pwm = doc["fan_pwm"];
    currentStateConfig.pulse_active = doc["pulse_active"];
    currentStateConfig.entry_flash_id = doc["entry_flash_id"] | -1;

    // Extract fire intensity from people count if needed
    JsonArray peopleArray = doc["people"];
    int peopleCount = peopleArray.size();
    currentStateConfig.fire_intensity = min(0.25f + (peopleCount - 1) * 0.25f, 1.0f);

    applyStateEffects();
}
```

### Phase 3.3: Color Palette Extraction

**Goal:** Parse palette and apply to LED ring

```cpp
#include <FastLED.h>

#define NUM_LEDS 59  // Adjust to your ring size
CRGB ringLeds[NUM_LEDS];
CRGBPalette16 currentPalette;

void extractPaletteFromPacket(JsonDocument& doc) {
    JsonArray palette = doc["dominant_palette"];
    
    // Palette is flattened [r,g,b,r,g,b,...]
    uint8_t colors[12];  // Max 4 colors
    for (int i = 0; i < min((int)palette.size(), 12); i++) {
        colors[i] = palette[i];
    }

    // Build CRGB array for FastLED blending
    // This will be used in renderEffect()
    storeCurrentPaletteColors(colors, palette.size());
}

void renderFireEffect() {
    // Existing fire algorithm, but modulated by intensity
    float intensity = currentStateConfig.fire_intensity;
    
    for (int i = 0; i < NUM_LEDS; i++) {
        fireHeat[i] = qsub8(fireHeat[i], random8(0, ((FIRE_COOLING * 10) / NUM_LEDS) + 2));
    }

    for (int k = NUM_LEDS - 1; k >= 2; k--) {
        fireHeat[k] = (fireHeat[k - 1] + fireHeat[k - 2] + fireHeat[k - 2]) / 3;
    }

    if (random8() < FIRE_SPARKING * intensity) {  // Sparking scales with intensity
        int sparkIndex = random8((NUM_LEDS / 6) + 2);
        fireHeat[sparkIndex] = qadd8(fireHeat[sparkIndex], random8(160, 255));
    }

    for (int j = 0; j < NUM_LEDS; j++) {
        uint8_t paletteIndex = scale8(fireHeat[j], 240);
        CRGB color = ColorFromPalette(firePalette, paletteIndex, 255 * intensity, LINEARBLEND);
        ringLeds[j] = color;
    }
}
```

### Phase 3.4: Special Effects

#### A. Color Pulse (15-second cycle)

```cpp
unsigned long lastPulseTime = 0;
CRGB pulseColors[4];  // Extracted from packet palette
int numPulseColors = 0;
float pulsePhase = 0.0f;

void renderPulseEffect() {
    if (!currentStateConfig.pulse_active) return;

    // Pulse phase: 0.0 → 1.0 over ~2 seconds, then reset
    pulsePhase += 0.01f;  // Adjust speed here
    if (pulsePhase > 1.0f) pulsePhase = 0.0f;

    uint8_t brightness = (uint8_t)(255.0f * sin(pulsePhase * 3.14159f));

    for (int i = 0; i < NUM_LEDS; i++) {
        int colorIdx = i % numPulseColors;
        ringLeds[i] = CRGB(
            (pulseColors[colorIdx].r * brightness) / 255,
            (pulseColors[colorIdx].g * brightness) / 255,
            (pulseColors[colorIdx].b * brightness) / 255
        );
    }
}
```

#### B. Entry Flash (New Person)

```cpp
unsigned long entryFlashUntil = 0;
CRGB entryFlashColor;

void renderEntryFlash() {
    if (millis() > entryFlashUntil) return;

    // Flash new person's shirt color for 3 seconds
    uint8_t brightness = 200 + (55 * sin((millis() / 100.0f) * 3.14159f));

    for (int i = 0; i < NUM_LEDS; i++) {
        ringLeds[i] = CRGB(
            (entryFlashColor.r * brightness) / 255,
            (entryFlashColor.g * brightness) / 255,
            (entryFlashColor.b * brightness) / 255
        );
    }
}

// Called when entry_flash_id != -1
void startEntryFlash(uint8_t r, uint8_t g, uint8_t b) {
    entryFlashColor = CRGB(r, g, b);
    entryFlashUntil = millis() + 3000;  // 3 seconds
}
```

#### C. Party Mode (Rainbow Cycling)

```cpp
float rainbowPhase = 0.0f;

void renderPartyEffect() {
    rainbowPhase += 0.05f;
    if (rainbowPhase > 1.0f) rainbowPhase -= 1.0f;

    for (int i = 0; i < NUM_LEDS; i++) {
        float hue = (i / (float)NUM_LEDS + rainbowPhase) * 255.0f;
        ringLeds[i] = CHSV((uint8_t)hue, 255, 255);
    }
}
```

#### D. Phone Glitch Penalty

```cpp
void renderPhoneGlitch() {
    // Red base with random bright pops
    fill_solid(ringLeds, NUM_LEDS, CRGB(80, 0, 0));

    if (random8() < 150) {
        ringLeds[random8(NUM_LEDS)] = CRGB(255, 40, 40);
    }
    if (random8() < 45) {
        ringLeds[random8(NUM_LEDS)] = CRGB(255, 120, 120);
    }
}
```

### Phase 3.5: Main Effect Dispatcher

```cpp
unsigned long lastWatchdog = 0;
const unsigned long WATCHDOG_TIMEOUT = 5000;  // 5 seconds

void applyStateEffects() {
    lastWatchdog = millis();  // Reset watchdog

    // Clear all effects
    FastLED.clear();

    // Render based on state
    switch (currentStateConfig.state) {
        case STATE_IDLE:
            renderIdleEffect();
            break;
        
        case STATE_FIRE:
            renderFireEffect();
            if (currentStateConfig.pulse_active) {
                renderPulseEffect();
            }
            if (currentStateConfig.entry_flash_id >= 0) {
                renderEntryFlash();
            }
            break;
        
        case STATE_PARTY:
            renderPartyEffect();
            break;
        
        case STATE_PHONE:
            renderPhoneGlitch();
            break;
    }

    // Update text on matrix
    renderPromptText(doc["prompt"]);

    // Apply PWM outputs
    ledcWrite(PIN_FAN, currentStateConfig.fan_pwm);
    ledcWrite(PIN_MIST, max(MIST_MIN, currentStateConfig.mist_pwm));

    // Commit all changes
    FastLED.show();
}

void watchdogCheck() {
    if (millis() - lastWatchdog > WATCHDOG_TIMEOUT) {
        // No packet received for 5 seconds, go to IDLE
        Serial.println("Watchdog: No packet, reverting to IDLE");
        currentStateConfig.state = STATE_IDLE;
        currentStateConfig.mist_pwm = MIST_IDLE;
        currentStateConfig.fan_pwm = 60;
        applyStateEffects();
    }
}
```

---

## Hardware Pinout (from working.ino)

```cpp
#define PIN_MATRIX_FRONT  5    // Neopixel matrix
#define PIN_RING          18   // LED ring (FastLED)
#define PIN_FAN           4    // PWM fan
#define PIN_MIST          12   // PWM mist atomizer

// LED ring configuration
#define RING1_SIZE 24          // First ring
#define RING2_SIZE 35          // Second ring
#define NUM_LEDS_RING (RING1_SIZE + RING2_SIZE)

// Safety floors
#define MIST_MIN 150           // Never below this
#define MIST_IDLE 220
#define MIST_MAX 255
```

---

## Packet Consumption Example

```cpp
void handlePacket(JsonDocument& doc) {
    Serial.printf("\n=== Packet Received ===\n");
    Serial.printf("Version: %d\n", (int)doc["version"]);
    Serial.printf("State: %s\n", (const char*)doc["state"]);
    Serial.printf("People: %d\n", doc["people"].size());
    Serial.printf("Phone: %s\n", doc["phone_detected"] ? "YES" : "NO");
    Serial.printf("Pulse: %s\n", doc["pulse_active"] ? "YES" : "NO");
    Serial.printf("Mist PWM: %d\n", (int)doc["mist_pwm"]);
    Serial.printf("Fan PWM: %d\n", (int)doc["fan_pwm"]);
    Serial.printf("Prompt: %s\n", (const char*)doc["prompt"]);

    // Extract people colors if entry flash needed
    if (doc["entry_flash_id"] != -1) {
        JsonArray people = doc["people"];
        for (JsonObject person : people) {
            if ((int)person["id"] == (int)doc["entry_flash_id"]) {
                JsonArray rgb = person["shirt_rgb"];
                startEntryFlash(rgb[0], rgb[1], rgb[2]);
                break;
            }
        }
    }

    // Extract palette colors
    JsonArray palette = doc["dominant_palette"];
    for (int i = 0; i < min((int)palette.size(), 4); i++) {
        // Use palette colors in effects
    }

    // Update state
    updateStateFromPacket(doc);
    applyStateEffects();
}
```

---

## Testing Checklist

- [ ] JSON parsing works with sample packets
- [ ] State transitions trigger correct effects
- [ ] Color palette renders properly
- [ ] Pulse effect animates smoothly
- [ ] Entry flash triggers and expires
- [ ] Party rainbow cycles continuously
- [ ] Phone glitch is visually distinct
- [ ] PWM outputs scale correctly (mist, fan)
- [ ] Matrix text displays prompts
- [ ] Watchdog reverts to IDLE after 5s silence
- [ ] Safety floors enforced (mist ≥150)
- [ ] FPS consistent even with animations

---

## Manual Testing with Python

```bash
# Send test packets to the ESP32
python vision/manual_packet_sender.py --interactive

# Or batch test
python vision/manual_packet_sender.py --preset fire_3_people --repeat 30 --rate 1
python vision/manual_packet_sender.py --preset party --repeat 10
python vision/manual_packet_sender.py --preset phone_penalty --repeat 5
```

---

## Compilation

```bash
# Arduino IDE
1. Open hardware/bondfire_v2.ino
2. Select board: ESP32-WROOM-32
3. Verify: Sketch → Verify
4. Upload: Sketch → Upload
5. Monitor: Tools → Serial Monitor

# Or PlatformIO
pio run -e esp32-wroom-32 -t upload
```

---

## Performance Targets

| Metric             | Target | Measurement                 |
| ------------------ | ------ | --------------------------- |
| JSON parse time    | <50ms  | Using ArduinoJson streaming |
| Effect render time | <10ms  | Per-frame LED calculation   |
| PWM update         | <1ms   | ledcWrite()                 |
| Total loop time    | <100ms | 10+ fps animation headroom  |
| WiFi latency       | <200ms | UDP roundtrip               |

---

## Future Enhancements

- [ ] Gesture detection (accelerometer shake = sparkle)
- [ ] Telemetry reporting (battery, temperature)
- [ ] OTA firmware updates
- [ ] Preset mode selection (offline mode)
- [ ] Animation speed control via HTTP
- [ ] Color calibration tool

---

## References

- **ArduinoJson:** https://arduinojson.org/
- **FastLED:** https://fastled.io/
- **ESP32 PWM:** https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/ledc.html
- **Adafruit_NeoMatrix:** https://github.com/adafruit/Adafruit_NeoMatrix

---

**Ready to implement.** Estimated 4-6 hours for a developer familiar with Arduino/C++.
