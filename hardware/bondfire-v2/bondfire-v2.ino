/*
 * ===================================================================
 * BOND FIRE - PHASE 3: UDP-Driven Slave Controller (v2.1 Protocol)
 * ===================================================================
 * 
 * System: Master-Slave architecture over WiFi UDP
 * Master: MacBook (Python + YOLOv8) broadcasts state/effects
 * Slave: ESP32 (this sketch) receives packets and drives hardware
 * 
 * Protocol: v2.1 JSON over UDP (port 4210), 30 packets/second
 * Hardware: LED ring (59 LEDs), mist pump (PWM), fan motor (PWM)
 * 
 * Status: Phase 1-2 code migrated + Phase 3 UDP protocol integrated
 * Last Updated: February 6, 2026
 * ===================================================================
 */

// ===== SECTION 1: INCLUDES & CONFIGURATION =====

#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_NeoMatrix.h>
#include <Adafruit_NeoPixel.h>
#include <FastLED.h>
#include <cstring>

// --- WIFI CONFIGURATION ---
const char* ssid     = "Emmanuel :)";
const char* password = "onseneggpassword123";
unsigned int localPort = 4210;

// --- HARDWARE PINS ---
#define PIN_MATRIX_FRONT  5      // Neopixel matrix (32x8)
#define PIN_RING          18     // LED ring (FastLED)
#define PIN_FAN           4      // PWM fan control
#define PIN_MIST          12     // PWM mist atomizer

// --- LED CONFIGURATION ---
#define RING1_SIZE 24            // First ring size
#define RING2_SIZE 35            // Second ring size (daisy-chained)
#define NUM_LEDS_RING (RING1_SIZE + RING2_SIZE)  // Total: 59 LEDs

// --- SAFETY LIMITS ---
#define MIST_MIN 150             // Safety floor (never go below)
#define MIST_IDLE 220            // Safe idle state
#define MIST_MAX 255             // Maximum output

// --- FIRE PALETTE (from working.ino) ---
DEFINE_GRADIENT_PALETTE(fire_orange_gp) {
  0,   40,  0,  0,
  80, 120, 20,  0,
 160, 220, 80,  0,
 200, 255, 140, 10,
 255, 255, 200, 20
};


// ===== SECTION 2: STATE MACHINE ENUMS & STRUCTS (NEW) =====

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
  CRGB palette[4];          // Up to 4 dominant colors
  int palette_size;
};


// ===== SECTION 3: GLOBAL OBJECTS & VARIABLES =====

// Network
WiFiUDP udp;
char packetBuffer[1500];  // Allow larger v2.1 packets without truncation

// Display Objects
Adafruit_NeoMatrix matrixFront = Adafruit_NeoMatrix(32, 8, PIN_MATRIX_FRONT,
  NEO_MATRIX_TOP + NEO_MATRIX_LEFT +
  NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG,
  NEO_GRB + NEO_KHZ800);

// LED Arrays
CRGB ringLeds[NUM_LEDS_RING];
CRGBPalette16 firePalette = fire_orange_gp;

// State Management
StateConfig currentStateConfig;
unsigned long lastWatchdog = 0;
const unsigned long WATCHDOG_TIMEOUT = 5000;  // 5 seconds

// Fire Algorithm (from working.ino)
uint8_t fireHeat[NUM_LEDS_RING];
const uint8_t FIRE_COOLING = 70;
const uint8_t FIRE_SPARKING = 180;

// PWM Breathing Variables (from phase2_fan.ino / phase3_mister.ino)
int fanSpeed = 60;
int fanDirection = 5;
int mistPower = MIST_IDLE;
int mistDirection = 5;

// Matrix Scrolling with Smart Queue System
String scrollingText = "Booting...";  // Currently displayed text
String stateText = "Waiting...";      // Text that SHOULD be displayed for current state
String lastStateText = "";            // Previous state text (to ignore duplicate text)
int scrollX = 32;  // Start at matrix width
uint8_t scrollCounter = 0;
const uint8_t SCROLL_SPEED_NORMAL = 3;  // Every 3 frames (~33ms per pixel)
const uint8_t SCROLL_SPEED_FAST = 1;    // Every frame (~10ms per pixel)
bool isTextFullyVisible = true;  // Track if current text is fully rendered on screen
unsigned long textHoldUntil = 0;  // Hold text on screen for readability
const unsigned long TEXT_HOLD_MS = 0;  // Minimum dwell when fully visible (0 disables pause)
const unsigned long MIN_VISIBLE_BEFORE_FAST_MS = 0;  // Visible time before fast-exit
unsigned long lastPromptAt = 0;  // Track when a prompt was last received
const unsigned long PROMPT_STALE_MS = 2000;  // Allow state fallback if no prompt
bool pendingTextReady = false;  // New text queued from master or state fallback
bool holdAppliedForCurrentText = false;  // Ensure hold happens once per text
bool speedUpToExit = false;  // Speed up when a new prompt is queued
unsigned long visibleSince = 0;  // Track when current text became visible

// Special Effects Timers
unsigned long entryFlashUntil = 0;
CRGB entryFlashColor;
float rainbowPhase = 0.0f;
float pulsePhase = 0.0f;
unsigned long celebrationUntil = 0;
const unsigned long CELEBRATION_MS = 1500;

// State Change Transition Effect
DisplayState lastStateRendered = STATE_IDLE;
DisplayState pendingStateColor = STATE_IDLE;  // Pending color change
DisplayState candidateState = STATE_IDLE;  // Candidate state for debouncing
DisplayState lastConfirmedState = STATE_IDLE;  // Last confirmed stable state
unsigned long candidateStateTime = 0;  // When candidate state appeared
const unsigned long STATE_DEBOUNCE_MS = 50;  // 50ms debounce - fast LED response, still glitch-resistant
bool colorTransitionActive = false;
unsigned long colorTransitionStart = 0;
const unsigned long COLOR_TRANSITION_DURATION = 200;  // 200ms smooth color transition
CRGB colorTransitionFrom = CRGB::Black;
CRGB colorTransitionTo = CRGB::Black;


// ===== SECTION 4: ARDUINO LIFECYCLE =====

void setup() {
  Serial.begin(115200);
  unsigned long startWait = millis();
  while (!Serial && millis() - startWait < 3000) { delay(10); }

  Serial.println("\n\n===== BOND FIRE Phase 3 Startup =====");

  // 1. INIT MATRIX
  Serial.println("[INIT] Initializing LED matrix...");
  matrixFront.begin();
  matrixFront.setTextWrap(false);
  matrixFront.setBrightness(35);
  matrixFront.setTextColor(matrixFront.Color(255, 0, 0));
  matrixFront.fillScreen(0);
  matrixFront.setCursor(0, 0);
  matrixFront.print("INIT...");
  matrixFront.show();

  // 2. INIT HARDWARE (PWM Setup)
  Serial.println("[INIT] Initializing PWM for fan and mist...");
  ledcAttach(PIN_FAN, 5000, 8);    // 5kHz, 8-bit
  ledcAttach(PIN_MIST, 1000, 8);   // 1kHz, 8-bit
  ledcWrite(PIN_MIST, MIST_IDLE);
  ledcWrite(PIN_FAN, 60);

  // 3. INIT FASTLED RING
  Serial.println("[INIT] Initializing LED ring...");
  FastLED.addLeds<WS2812B, PIN_RING, GRB>(ringLeds, NUM_LEDS_RING);
  FastLED.setBrightness(100);
  FastLED.clear();
  FastLED.show();
  memset(fireHeat, 0, sizeof(fireHeat));

  // 4. INIT WIFI
  Serial.println("[INIT] Connecting to WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  WiFi.begin(ssid, password);

  int dot = 0;
  int connectAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && connectAttempts < 20) {
    delay(500);
    connectAttempts++;
    matrixFront.fillScreen(0);
    matrixFront.setCursor(0, 0);
    matrixFront.setTextColor(matrixFront.Color(255, 100, 0));
    matrixFront.print("JOINING");
    for (int i = 0; i < dot; i++) {
      matrixFront.drawPixel(25 + i * 2, 7, matrixFront.Color(255, 255, 255));
    }
    matrixFront.show();
    dot = (dot + 1) % 4;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[SUCCESS] WiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());

    matrixFront.fillScreen(0);
    matrixFront.setCursor(0, 0);
    matrixFront.setTextColor(matrixFront.Color(0, 255, 0));
    matrixFront.print("OK!");
    matrixFront.show();
    delay(1000);
  } else {
    Serial.println("\n[WARNING] WiFi connection failed. Continuing anyway...");
    matrixFront.fillScreen(0);
    matrixFront.setCursor(0, 0);
    matrixFront.setTextColor(matrixFront.Color(255, 100, 0));
    matrixFront.print("NO WIFI");
    matrixFront.show();
    delay(2000);
  }

  // 5. INIT UDP
  Serial.println("[INIT] Starting UDP listener on port 4210...");
  udp.begin(localPort);

  // 6. INIT STATE
  scrollingText = "Waiting...";
  currentStateConfig.state = STATE_IDLE;
  currentStateConfig.mist_pwm = MIST_IDLE;
  currentStateConfig.fan_pwm = 60;
  currentStateConfig.fire_intensity = 0.0f;
  currentStateConfig.pulse_active = false;
  currentStateConfig.entry_flash_id = -1;
  currentStateConfig.palette_size = 0;
  lastWatchdog = millis();

  Serial.println("[INIT] Setup complete. Waiting for packets...\n");
}

void loop() {
  // --- PART A: UDP PACKET RECEIVER ---
  int packetSize = udp.parsePacket();
  if (packetSize) {
    handlePacket();
  }

  // --- PART B: SAFETY WATCHDOG ---
  watchdogCheck();

  // --- PART C: APPLY STATE EFFECTS ---
  applyStateEffects();

  // --- PART D: UPDATE DISPLAYS ---
  updateMatrixDisplay();

  delay(10);  // ~100 fps animation loop for smooth scroll and responsiveness
}


// ===== SECTION 5: V2.1 PROTOCOL HANDLER (NEW) =====

void handlePacket() {
  int len = udp.read(packetBuffer, 1499);
  packetBuffer[len] = 0;

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, packetBuffer);

  if (error) {
    Serial.printf("[UDP ERROR] JSON parse failed: %s\n", error.c_str());
    return;
  }

  // Validate protocol version
  int version = doc["version"] | 0;
  if (version != 2) {
    Serial.printf("[UDP ERROR] Version mismatch: expected 2, got %d\n", version);
    return;
  }

  // Reset watchdog timer
  lastWatchdog = millis();

  // --- Parse State ---
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

  // --- Parse PWM Values ---
  currentStateConfig.mist_pwm = doc["mist_pwm"] | MIST_IDLE;
  currentStateConfig.fan_pwm = doc["fan_pwm"] | 60;

  // --- Parse Auxiliary Flags ---
  currentStateConfig.pulse_active = doc["pulse_active"] | false;
  currentStateConfig.entry_flash_id = doc["entry_flash_id"] | -1;

  // Parse people array for entry flash tracking
  JsonArray peopleArray = doc["people"];
  int peopleCount = peopleArray.size();

  // --- Parse Fire Intensity ---
  // Use intensity from Python master (already calculated with state machine logic)
  float intensity = doc["fire_intensity"] | -1.0f;
  if (intensity < 0.0f) {
    if (peopleCount <= 0) {
      intensity = 0.0f;
    } else if (peopleCount == 1) {
      intensity = 0.35f;
    } else if (peopleCount == 2) {
      intensity = 0.6f;
    } else if (peopleCount == 3) {
      intensity = 0.8f;
    } else {
      intensity = 1.0f;
    }
  }
  currentStateConfig.fire_intensity = constrain(intensity, 0.0f, 1.0f);

  // --- Parse Dominant Palette ---
  JsonArray paletteArray = doc["dominant_palette"];
  currentStateConfig.palette_size = min((int)paletteArray.size() / 3, 4);
  for (int i = 0; i < currentStateConfig.palette_size; i++) {
    uint8_t r = paletteArray[i * 3];
    uint8_t g = paletteArray[i * 3 + 1];
    uint8_t b = paletteArray[i * 3 + 2];
    currentStateConfig.palette[i] = CRGB(r, g, b);
  }

  // --- Parse Prompt Text ---
  const char* prompt = doc["prompt"];
  if (prompt) {
    String nextPrompt = String(prompt);
    lastPromptAt = millis();
    if (nextPrompt != stateText) {
      stateText = nextPrompt;
      pendingTextReady = true;
    }
  }

  // --- Parse Celebration Flag ---
  bool celebration = doc["celebration"] | false;
  if (celebration) {
    celebrationUntil = millis() + CELEBRATION_MS;
  }

  // --- Handle Entry Flash ---
  if (currentStateConfig.entry_flash_id != -1) {
    // Look up person color from people array
    for (JsonObject person : peopleArray) {
      if (person["id"] == currentStateConfig.entry_flash_id) {
        JsonArray colorArray = person["color"];
        if (colorArray.isNull() || colorArray.size() < 3) {
          colorArray = person["shirt_rgb"];
        }
        if (!colorArray.isNull() && colorArray.size() >= 3) {
          entryFlashColor = CRGB(colorArray[0], colorArray[1], colorArray[2]);
          entryFlashUntil = millis() + 3000;  // Flash for 3 seconds
        }
        break;
      }
    }
  }

  // Debug output (optional)
  if (version == 2) {
    Serial.printf("[UDP] State: %s | People: %d | PWM: M=%d F=%d | Fire: %.1f%%\n",
                  stateStr, peopleCount, currentStateConfig.mist_pwm,
                  currentStateConfig.fan_pwm, currentStateConfig.fire_intensity * 100.0f);
  }
}


// ===== SECTION 6: STATE DISPATCHER (NEW) =====

void applyStateEffects() {
  FastLED.clear();

  // DEBOUNCE STATE CHANGES: Only recognize state if it persists for 100ms
  // This prevents glitches/noise from flickering the display
  unsigned long now = millis();
  
  if (currentStateConfig.state != candidateState) {
    // New candidate state detected, start debounce timer
    candidateState = currentStateConfig.state;
    candidateStateTime = now;
  } else if (currentStateConfig.state == candidateState && 
             now - candidateStateTime >= STATE_DEBOUNCE_MS &&
             candidateState != lastConfirmedState) {
    // State has been stable for 100ms - COMMIT the state change
    lastConfirmedState = candidateState;
    
    // RING LEDS: React FIRST with smooth color transition
    colorTransitionFrom = colorTransitionTo;  // From current color
    
    // Set target color based on new state
    switch (candidateState) {
      case STATE_IDLE:
        colorTransitionTo = CRGB(0, 100, 150);   // Cool blue
        break;
      case STATE_FIRE:
        colorTransitionTo = CRGB(255, 150, 0);   // Bright orange
        break;
      case STATE_PARTY:
        colorTransitionTo = CRGB(255, 50, 255);  // Bright magenta
        break;
      case STATE_PHONE:
        colorTransitionTo = CRGB(200, 200, 200); // Bright white
        break;
    }
    
    // Start color transition immediately (no delay, smooth 200ms blend)
    colorTransitionActive = true;
    colorTransitionStart = now;
    pendingStateColor = candidateState;
    
    // Determine fallback text ONLY if prompts have gone stale
    if (now - lastPromptAt > PROMPT_STALE_MS) {
      String newStateText = "";
      switch (candidateState) {
        case STATE_IDLE:
          newStateText = "Waiting...";
          break;
        case STATE_FIRE:
          newStateText = "Warming up...";
          break;
        case STATE_PARTY:
          newStateText = "PARTY!";
          break;
        case STATE_PHONE:
          newStateText = "Phone detected";
          break;
      }
      if (newStateText != lastStateText) {
        stateText = newStateText;
        lastStateText = newStateText;
        pendingTextReady = true;
      }
    }
  }

  // Apply color transition if active (smooth subtle blend)
  if (colorTransitionActive) {
    unsigned long elapsed = millis() - colorTransitionStart;
    if (elapsed >= COLOR_TRANSITION_DURATION) {
      colorTransitionActive = false;
      // Fall through to normal rendering
    } else {
      // Subtle smooth transition: blend from old color to new color
      uint8_t progress = (elapsed * 255) / COLOR_TRANSITION_DURATION;
      CRGB transitionColor = blend(colorTransitionFrom, colorTransitionTo, progress);
      fill_solid(ringLeds, NUM_LEDS_RING, transitionColor);
      FastLED.show();
      return;  // Return early - skip state effects during transition
    }
  }

  // Render normal state effects (after transition completes)
  renderStateEffects();

  // Apply PWM outputs
  ledcWrite(PIN_FAN, currentStateConfig.fan_pwm);
  ledcWrite(PIN_MIST, max((uint8_t)MIST_MIN, currentStateConfig.mist_pwm));

  // Commit LED changes
  FastLED.show();
}

/**
 * Render bright flash on state change
 * Transitions from white flash to state color
 */
/**
 * Render normal state effects
 */
void renderStateEffects() {
  // Always render state-specific effects
  // Fire naturally flickers with intensity scaling, party has rainbow,
  // idle has breathing glow, phone has red glitch
  switch (currentStateConfig.state) {
    case STATE_IDLE:
      renderIdleEffect();
      break;

    case STATE_FIRE:
      renderFireEffect();
      // Pulse effect overlays on fire (triggered by pulse_active from Python)
      if (currentStateConfig.pulse_active) {
        renderPulseEffect();
      }
      break;

    case STATE_PARTY:
      renderPartyEffect();
      break;

    case STATE_PHONE:
      renderPhoneGlitch();
      break;
  }

  // Celebration overlay has highest priority
  if (millis() < celebrationUntil) {
    renderCelebrationEffect();
  } else if (millis() < entryFlashUntil) {
    renderEntryFlash();
  }
}


// ===== SECTION 7: LED ANIMATION EFFECTS (MIGRATED) =====

/**
 * FIRE Effect: Realistic fire with intensity modulation
 * Migrated from working.ino runFireEffect()
 * Now scales with fire_intensity from packet
 * 
 * More people → More sparking and flicker (intensity 0.0-1.0)
 */
void renderFireEffect() {
  float intensity = currentStateConfig.fire_intensity;
  if (intensity < 0.0f) intensity = 0.0f;
  if (intensity > 1.0f) intensity = 1.0f;
  uint8_t brightness = (uint8_t)(70.0f + (185.0f * intensity));

  // Cool down fire
  for (int i = 0; i < NUM_LEDS_RING; i++) {
    uint8_t cool = random8(0, ((FIRE_COOLING * 10) / NUM_LEDS_RING) + 2);
    fireHeat[i] = qsub8(fireHeat[i], cool);
  }

  // Heat drift upward
  for (int k = NUM_LEDS_RING - 1; k >= 2; k--) {
    fireHeat[k] = (fireHeat[k - 1] + fireHeat[k - 2] + fireHeat[k - 2]) / 3;
  }

  // Spark generation (scaled by intensity - more people = more sparks and bigger fire)
  uint8_t sparkingRatio = (uint8_t)(FIRE_SPARKING * currentStateConfig.fire_intensity);
  if (random8() < sparkingRatio) {
    int sparkIndex = random8((NUM_LEDS_RING / 6) + 2);
    fireHeat[sparkIndex] = qadd8(fireHeat[sparkIndex], random8(160, 255));
  }

  // Render colors from palette with flicker
  for (int j = 0; j < NUM_LEDS_RING; j++) {
    uint8_t paletteIndex = scale8(fireHeat[j], 240);
    CRGB color = ColorFromPalette(firePalette, paletteIndex, 255, LINEARBLEND);
    
    // Add random flicker for more realistic fire
    uint8_t flicker = random8(0, 60);
    color.fadeToBlackBy(flicker);
    
    if (random8() < 40) {
      color += CRGB(random8(10, 40), random8(0, 15), 0);
    }
    color.nscale8_video(brightness);
    ringLeds[j] = color;
  }
}

/**
 * IDLE Effect: Blue breathing glow with sparkles
 * Migrated from working.ino MODE_IDLE
 */
void renderIdleEffect() {
  uint8_t glow = beatsin8(9, 30, 160);
  for (int i = 0; i < NUM_LEDS_RING; i++) {
    ringLeds[i] = CHSV(160, 180, glow);
  }
  if (random8() < 35) {
    ringLeds[random8(NUM_LEDS_RING)] = CHSV(160, 20, 255);
  }
}

/**
 * PARTY Effect: Rainbow cycling
 * Inspired by phase3_mister.ino but generalized
 */
void renderPartyEffect() {
  rainbowPhase += 0.05f;
  if (rainbowPhase > 1.0f) rainbowPhase -= 1.0f;

  for (int i = 0; i < NUM_LEDS_RING; i++) {
    float hueFloat = (i / (float)NUM_LEDS_RING + rainbowPhase) * 255.0f;
    ringLeds[i] = CHSV((uint8_t)hueFloat, 255, 255);
  }
}

/**
 * PHONE Glitch: Red penalty effect with random bright pops
 * Migrated from working.ino MODE_PENALTY
 */
void renderPhoneGlitch() {
  fill_solid(ringLeds, NUM_LEDS_RING, CRGB(80, 0, 0));

  if (random8() < 150) {
    ringLeds[random8(NUM_LEDS_RING)] = CRGB(255, 40, 40);
  }
  if (random8() < 45) {
    ringLeds[random8(NUM_LEDS_RING)] = CRGB(255, 120, 120);
  }
}

/**
 * PULSE Effect: Color pulse overlay for 15s cycle
 * Uses palette colors from packet
 */
void renderPulseEffect() {
  if (currentStateConfig.palette_size == 0) return;

  pulsePhase += 0.01f;
  if (pulsePhase > 1.0f) pulsePhase = 0.0f;

  uint8_t brightness = (uint8_t)(255.0f * sin(pulsePhase * 3.14159f));

  for (int i = 0; i < NUM_LEDS_RING; i++) {
    int colorIdx = i % currentStateConfig.palette_size;
    CRGB baseColor = currentStateConfig.palette[colorIdx];

    ringLeds[i] = CRGB(
      (baseColor.r * brightness) / 255,
      (baseColor.g * brightness) / 255,
      (baseColor.b * brightness) / 255
    );
  }
}

/**
 * ENTRY FLASH: Highlight new person's color for 3 seconds
 * Triggered when entry_flash_id is set
 */
void renderEntryFlash() {
  uint8_t brightness = 200 + (55 * sin((millis() / 100.0f) * 3.14159f));

  for (int i = 0; i < NUM_LEDS_RING; i++) {
    ringLeds[i] = CRGB(
      (entryFlashColor.r * brightness) / 255,
      (entryFlashColor.g * brightness) / 255,
      (entryFlashColor.b * brightness) / 255
    );
  }
}

/**
 * CELEBRATION: Short rainbow burst overlay
 * Triggered when celebration flag is received
 */
void renderCelebrationEffect() {
  uint8_t beat = beatsin8(12, 80, 255);
  uint8_t baseHue = (millis() / 10) % 255;

  for (int i = 0; i < NUM_LEDS_RING; i++) {
    ringLeds[i] = CHSV(baseHue + (i * 6), 255, beat);
  }
}


// ===== SECTION 8: MATRIX DISPLAY =====

uint16_t matrixColorFromCRGB(const CRGB& color) {
  return matrixFront.Color(color.r, color.g, color.b);
}

CRGB applyTextFlicker(CRGB base, uint8_t minScale, uint8_t maxScale) {
  uint8_t scale = (maxScale < 255)
    ? random8(minScale, (uint8_t)(maxScale + 1))
    : random8(minScale, maxScale);
  base.nscale8_video(scale);
  return base;
}

CRGB getRingSampleColor() {
  if (NUM_LEDS_RING == 0) {
    return CRGB::Black;
  }

  uint16_t idxA = 0;
  uint16_t idxB = NUM_LEDS_RING / 3;
  uint16_t idxC = (NUM_LEDS_RING * 2) / 3;

  CRGB sample = ringLeds[idxA];
  sample += ringLeds[idxB];
  sample += ringLeds[idxC];
  sample.nscale8_video(85); // Average of 3 samples
  return sample;
}

CRGB boostTextReadability(CRGB color, uint8_t minMaxChannel) {
  uint8_t maxChannel = max(color.r, max(color.g, color.b));
  if (maxChannel < 1) {
    return color;
  }
  if (maxChannel < minMaxChannel) {
    uint8_t scale = (uint8_t)((minMaxChannel * 255) / maxChannel);
    color.nscale8_video(scale);
  }
  return color;
}

CRGB getMatrixFireTextColor() {
  uint8_t heat = fireHeat[random8(NUM_LEDS_RING)];
  uint8_t paletteIndex = scale8(heat, 240);
  CRGB color = ColorFromPalette(firePalette, paletteIndex, 255, LINEARBLEND);
  return color;
}

uint16_t getMatrixTextColor() {
  CRGB ringSample = getRingSampleColor();
  CRGB color = CRGB::Black;

  switch (currentStateConfig.state) {
    case STATE_IDLE: {
      uint8_t glow = beatsin8(9, 50, 170);
      color = CHSV(160, 180, glow);
      break;
    }
    case STATE_FIRE:
      color = CRGB(255, 120, 0);
      break;
    case STATE_PARTY: {
      uint8_t hue = (uint8_t)(rainbowPhase * 255.0f);
      color = CHSV(hue, 255, 255);
      break;
    }
    case STATE_PHONE:
      color = CRGB(160, 0, 0);
      break;
  }

  // Subtle match to ring shade without introducing flicker.
  color = blend(color, ringSample, 50);

  // Keep text legible across states.
  color = boostTextReadability(color, 170);

  return matrixColorFromCRGB(color);
}

/**
 * Update the LED matrix with scrolling text
 * Migrated from working.ino matrix update logic
 */
void updateMatrixDisplay() {
  // Normal display: smooth scrolling text
  matrixFront.fillScreen(0);
  matrixFront.setCursor(scrollX, 0);

  // Set text color to match ring state and apply fire-like flicker
  matrixFront.setTextColor(getMatrixTextColor());
  matrixFront.print(scrollingText);
  matrixFront.show();

  // TEXT SCROLL: Smart queue-based logic
  // Calculate text width for exit/visibility detection
  int textWidthPixels = scrollingText.length() * 6;  // ~6 pixels per character

  unsigned long now = millis();
  if (pendingTextReady && scrollingText != stateText) {
    speedUpToExit = true;
  }

  if (!speedUpToExit && TEXT_HOLD_MS > 0 && textHoldUntil > 0) {
    if (now < textHoldUntil) {
      return;  // Hold text on screen for readability
    }
    textHoldUntil = 0;
  }

  uint8_t scrollSpeed = speedUpToExit ? SCROLL_SPEED_FAST : SCROLL_SPEED_NORMAL;
  
  if (++scrollCounter >= scrollSpeed) {
    scrollCounter = 0;
    scrollX--;
    
    // PART 1: Check if old text has COMPLETELY exited the screen
    if (scrollX < (int)-(textWidthPixels)) {
      // Current text has completely exited - now switch to stateText
      scrollX = matrixFront.width();  // Reset position to right edge
      scrollingText = stateText;       // Switch to the new text
      if (pendingTextReady) {
        pendingTextReady = false;
      }
      speedUpToExit = false;
      isTextFullyVisible = false;      // Mark new text as entering (not yet fully visible)
      holdAppliedForCurrentText = false;
      textHoldUntil = 0;
      visibleSince = 0;
    }
    
    // PART 2: Track when new text is FULLY visible on screen
    // Text is fully visible when: left edge has entered (scrollX < width) AND right edge hasn't exited yet
    if (scrollingText == stateText && !isTextFullyVisible) {
      // Check if new text is now fully on screen and readable
      int textRightEdge = scrollX + textWidthPixels;
      
      // Text is fully visible when it's entirely within the matrix bounds
      if (scrollX <= 0 && textRightEdge >= matrixFront.width()) {
        // Text is spanning the full width - it's readable but still scrolling
        isTextFullyVisible = true;
      } else if (scrollX < 0 && textRightEdge > 0) {
        // Text is at least partially visible
        isTextFullyVisible = true;
      }
    }

    if (!speedUpToExit && TEXT_HOLD_MS > 0 && isTextFullyVisible && !holdAppliedForCurrentText) {
      if (visibleSince == 0) {
        visibleSince = now;
      }
      textHoldUntil = now + TEXT_HOLD_MS;
      holdAppliedForCurrentText = true;
      return;
    }
    
    // PART 3: Detect when text has COMPLETELY exited on the left
    // This is needed to ensure it fully scrolls off before any new changes
    if (scrollingText == stateText && isTextFullyVisible) {
      int textRightEdge = scrollX + textWidthPixels;
      
      // If text is still visible, keep marking it as fully visible
      if (textRightEdge > 0) {
        isTextFullyVisible = true;
      } else {
        // Text has completely exited the left side
        isTextFullyVisible = false;
      }
    }
  }
}


// ===== SECTION 9: SAFETY & DIAGNOSTICS =====

/**
 * Watchdog Timer: Revert to IDLE if no packet for 5 seconds
 * Prevents ESP32 from acting on stale state
 */
void watchdogCheck() {
  if (millis() - lastWatchdog > WATCHDOG_TIMEOUT) {
    Serial.println("[WATCHDOG] No packet for 5s, reverting to IDLE");
    currentStateConfig.state = STATE_IDLE;
    currentStateConfig.mist_pwm = MIST_IDLE;
    currentStateConfig.fan_pwm = 60;
    currentStateConfig.fire_intensity = 0.0f;
    currentStateConfig.pulse_active = false;
    currentStateConfig.entry_flash_id = -1;
    lastWatchdog = millis();
  }
}


// ===== END OF SKETCH =====
