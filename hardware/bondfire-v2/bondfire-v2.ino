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
char packetBuffer[1024];  // Increased for full v2.1 packets with 6 people

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

// Matrix Scrolling (from working.ino)
String scrollingText = "Booting...";
int scrollX = 32;  // Start at matrix width
uint8_t scrollCounter = 0;

// Special Effects Timers
unsigned long entryFlashUntil = 0;
CRGB entryFlashColor;
float rainbowPhase = 0.0f;
float pulsePhase = 0.0f;


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
  matrixFront.setBrightness(20);
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

  delay(30);  // ~33 fps animation loop
}


// ===== SECTION 5: V2.1 PROTOCOL HANDLER (NEW) =====

void handlePacket() {
  int len = udp.read(packetBuffer, 1023);
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

  // --- Parse Fire Intensity ---
  // Use intensity from Python master (already calculated with state machine logic)
  currentStateConfig.fire_intensity = doc["fire_intensity"] | 0.0f;

  // Parse people array for entry flash tracking
  JsonArray peopleArray = doc["people"];
  int peopleCount = peopleArray.size();

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
    if (nextPrompt != scrollingText) {
      scrollingText = nextPrompt;
      scrollX = matrixFront.width();  // Reset scroll position only on change
    }
  }

  // --- Handle Entry Flash ---
  if (currentStateConfig.entry_flash_id != -1) {
    // Look up person color from people array
    for (JsonObject person : peopleArray) {
      if (person["id"] == currentStateConfig.entry_flash_id) {
        JsonArray colorArray = person["color"];
        if (colorArray.size() >= 3) {
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

  // Render effect based on current state
  switch (currentStateConfig.state) {
    case STATE_IDLE:
      renderIdleEffect();
      break;

    case STATE_FIRE:
      renderFireEffect();
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

  // Handle entry flash overlay (highest priority)
  if (millis() < entryFlashUntil) {
    renderEntryFlash();
  }

  // Apply PWM outputs
  ledcWrite(PIN_FAN, currentStateConfig.fan_pwm);
  ledcWrite(PIN_MIST, max((uint8_t)MIST_MIN, currentStateConfig.mist_pwm));

  // Commit LED changes
  FastLED.show();
}


// ===== SECTION 7: LED ANIMATION EFFECTS (MIGRATED) =====

/**
 * IDLE Effect: Blue breathing glow
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
 * FIRE Effect: Realistic fire with intensity modulation
 * Migrated from working.ino runFireEffect()
 * Now scales with fire_intensity from packet
 */
void renderFireEffect() {
  // Cool down fire
  for (int i = 0; i < NUM_LEDS_RING; i++) {
    uint8_t cool = random8(0, ((FIRE_COOLING * 10) / NUM_LEDS_RING) + 2);
    fireHeat[i] = qsub8(fireHeat[i], cool);
  }

  // Heat drift upward
  for (int k = NUM_LEDS_RING - 1; k >= 2; k--) {
    fireHeat[k] = (fireHeat[k - 1] + fireHeat[k - 2] + fireHeat[k - 2]) / 3;
  }

  // Spark generation (scaled by intensity)
  uint8_t sparkingRatio = (uint8_t)(FIRE_SPARKING * currentStateConfig.fire_intensity);
  if (random8() < sparkingRatio) {
    int sparkIndex = random8((NUM_LEDS_RING / 6) + 2);
    fireHeat[sparkIndex] = qadd8(fireHeat[sparkIndex], random8(160, 255));
  }

  // Render colors from palette
  for (int j = 0; j < NUM_LEDS_RING; j++) {
    uint8_t paletteIndex = scale8(fireHeat[j], 240);
    CRGB color = ColorFromPalette(firePalette, paletteIndex, 255, LINEARBLEND);
    color.fadeToBlackBy(random8(0, 45));
    if (random8() < 40) {
      color += CRGB(random8(10, 40), random8(0, 15), 0);
    }
    ringLeds[j] = color;
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


// ===== SECTION 8: MATRIX DISPLAY =====

/**
 * Update the LED matrix with scrolling text
 * Migrated from working.ino matrix update logic
 */
void updateMatrixDisplay() {
  matrixFront.fillScreen(0);
  matrixFront.setCursor(scrollX, 0);

  // Set text color based on state
  uint16_t textColor = 0;
  switch (currentStateConfig.state) {
    case STATE_IDLE:
      textColor = matrixFront.Color(120, 180, 255);  // Blue
      break;
    case STATE_FIRE:
      textColor = matrixFront.Color(255, 100, 0);   // Orange
      break;
    case STATE_PARTY:
      textColor = matrixFront.Color(255, 0, 255);   // Magenta
      break;
    case STATE_PHONE:
      textColor = matrixFront.Color(200, 200, 200); // Grey
      break;
  }

  matrixFront.setTextColor(textColor);
  matrixFront.print(scrollingText);
  matrixFront.show();

  // Scroll logic (slower: update every 3 frames)
  if (++scrollCounter >= 3) {
    scrollCounter = 0;
    scrollX--;
    if (scrollX < (int)-(scrollingText.length() * 6)) {
      scrollX = matrixFront.width();
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
