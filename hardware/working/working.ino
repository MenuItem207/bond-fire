#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_NeoMatrix.h>
#include <Adafruit_NeoPixel.h>
#include <FastLED.h>
#include <cstring>

DEFINE_GRADIENT_PALETTE(fire_orange_gp) {
  0,   40,  0,  0,
  80, 120, 20,  0,
 160, 220, 80,  0,
 200, 255, 140, 10,
 255, 255, 200, 20
};

// --- WIFI CONFIGURATION ---
const char* ssid     = "Emmanuel :)";    
const char* password = "onseneggpassword123";  
unsigned int localPort = 4210;

// --- HARDWARE PINS ---
#define PIN_MATRIX_FRONT  5   // Current Matrix
// #define PIN_MATRIX_BACK   25  // <--- UNCOMMENT THIS LATER for 2nd Matrix
#define PIN_RING          18
#define PIN_FAN           4   
#define PIN_MIST          12  

// --- LED RING SETTINGS (Daisy Chained) ---
#define RING1_SIZE 24       // Your first ring
#define RING2_SIZE 35       // <--- UPDATE THIS! (Common sizes: 35, 40, 45, 60)
#define NUM_LEDS_RING (RING1_SIZE + RING2_SIZE) // Automatically adds them up

// --- MIST SETTINGS ---
#define MIST_MIN 150  
#define MIST_IDLE 220
#define MIST_MAX 255

// --- OBJECTS ---
WiFiUDP udp;
char packetBuffer[512]; 

// Matrix 1 (Front)
Adafruit_NeoMatrix matrixFront = Adafruit_NeoMatrix(32, 8, PIN_MATRIX_FRONT,
  NEO_MATRIX_TOP + NEO_MATRIX_LEFT +
  NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG,
  NEO_GRB + NEO_KHZ800);

/* // --- UNCOMMENT THIS BLOCK FOR 2ND MATRIX ---
Adafruit_NeoMatrix matrixBack = Adafruit_NeoMatrix(32, 8, PIN_MATRIX_BACK,
  NEO_MATRIX_TOP + NEO_MATRIX_LEFT +
  NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG,
  NEO_GRB + NEO_KHZ800);
*/

CRGB ringLeds[NUM_LEDS_RING];
CRGBPalette16 firePalette = fire_orange_gp;

enum Mode {
  MODE_IDLE,
  MODE_ACTIVE,
  MODE_PENALTY
};

Mode currentMode = MODE_IDLE;
bool transitionActive = false;
unsigned long transitionUntil = 0;
uint8_t fireHeat[NUM_LEDS_RING];
const uint8_t FIRE_COOLING = 70;
const uint8_t FIRE_SPARKING = 180;

uint8_t scrollCounter = 0;

void startModeTransition(Mode mode);
uint16_t matrixColorForMode(Mode mode);
uint16_t matrixTransitionTextColor(Mode mode);
uint16_t matrixTransitionBackgroundColor(Mode mode);
CRGB ringTransitionColorForMode(Mode mode);
void runFireEffect();

// --- VARIABLES ---
int paxCount = 0;
bool phoneDetected = false;
String scrollingText = "Booting...";
int x = matrixFront.width();

// Animation Vars
int fanSpeed = 60;
int fanDirection = 5;
int mistPower = MIST_IDLE; 
int mistDirection = 5;

void setup() {
  Serial.begin(115200);
  unsigned long startWait = millis();
  while (!Serial && millis() - startWait < 3000) { delay(10); } 

  // 1. INIT MATRICES
  matrixFront.begin();
  matrixFront.setTextWrap(false);
  matrixFront.setBrightness(20);
  matrixFront.setTextColor(matrixFront.Color(255, 0, 0)); 
  
  /* // UNCOMMENT FOR 2ND MATRIX
  matrixBack.begin();
  matrixBack.setTextWrap(false);
  matrixBack.setBrightness(20);
  */

  // Show Init on Front
  matrixFront.fillScreen(0);
  matrixFront.setCursor(0, 0);
  matrixFront.print("INIT...");
  matrixFront.show();

  // 2. INIT HARDWARE
  ledcAttach(PIN_FAN, 5000, 8); 
  ledcAttach(PIN_MIST, 1000, 8); 
  
  // Start Mist with enough output for humidifier
  ledcWrite(PIN_MIST, MIST_IDLE); 

  // Setup BOTH Rings (FastLED handles the total count)
  FastLED.addLeds<WS2812B, PIN_RING, GRB>(ringLeds, NUM_LEDS_RING);
  FastLED.setBrightness(100);
  memset(fireHeat, 0, sizeof(fireHeat));

  // 3. WIFI CONNECTION
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  
  WiFi.begin(ssid, password);
  
  int dot = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    matrixFront.fillScreen(0);
    matrixFront.setCursor(0, 0);
    matrixFront.setTextColor(matrixFront.Color(255, 100, 0)); 
    matrixFront.print("JOINING");
    for(int i=0; i<dot; i++) matrixFront.drawPixel(25+i*2, 7, matrixFront.Color(255, 255, 255));
    matrixFront.show();
    dot = (dot + 1) % 4;
  }

  // 4. CONNECTED
  Serial.println("\nWiFi Connected!");
  Serial.println(WiFi.localIP());
  
  matrixFront.fillScreen(0);
  matrixFront.setCursor(0, 0);
  matrixFront.setTextColor(matrixFront.Color(0, 255, 0)); 
  matrixFront.print("OK!");
  matrixFront.show();
  delay(1000);

  udp.begin(localPort);
  scrollingText = "Waiting...";
  ledcWrite(PIN_MIST, MIST_IDLE);
  mistPower = MIST_IDLE;
}

void loop() {
  // --- UDP RECEIVER ---
  int packetSize = udp.parsePacket();
  if (packetSize) {
    int len = udp.read(packetBuffer, 511);
    packetBuffer[len] = 0; 
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, packetBuffer);
    if (!error) {
      paxCount = doc["c"];
      phoneDetected = doc["p"];
      const char* t = doc["t"];
      scrollingText = String(t);
    }
  }

  // --- HARDWARE LOGIC ---
  Mode newMode;
  if (phoneDetected) newMode = MODE_PENALTY;
  else if (paxCount == 0) newMode = MODE_IDLE;
  else newMode = MODE_ACTIVE;

  if (newMode != currentMode) {
    currentMode = newMode;
    startModeTransition(currentMode);
  }

  if (transitionActive && millis() >= transitionUntil) {
    transitionActive = false;
  }

  uint16_t textColor = matrixColorForMode(currentMode);
  uint16_t backgroundColor = 0;

  switch (currentMode) {
    case MODE_PENALTY:
      ledcWrite(PIN_MIST, MIST_MIN);
      ledcWrite(PIN_FAN, 0);
      fill_solid(ringLeds, NUM_LEDS_RING, CRGB(80, 0, 0));
      if (random8() < 150) {
        ringLeds[random8(NUM_LEDS_RING)] = CRGB(255, 40, 40);
      }
      if (random8() < 45) {
        ringLeds[random8(NUM_LEDS_RING)] = CRGB(255, 120, 120);
      }
      break;
    case MODE_IDLE:
      ledcWrite(PIN_MIST, MIST_IDLE);
      runFanBreathing(40, 80);
      {
        uint8_t glow = beatsin8(9, 30, 160);
        for (int i = 0; i < NUM_LEDS_RING; i++) {
          ringLeds[i] = CHSV(160, 180, glow);
        }
        if (random8() < 35) {
          ringLeds[random8(NUM_LEDS_RING)] = CHSV(160, 20, 255);
        }
      }
      break;
    case MODE_ACTIVE:
      {
        int upperLimit = (paxCount >= 3) ? MIST_MAX : 220;
        runMistBreathing(MIST_MIN, upperLimit);
        runFanBreathing(100, 255);
        runFireEffect();
        if (paxCount >= 5) {
          textColor = matrixFront.Color(255, 200, 120);
        }
      }
      break;
  }

  if (transitionActive && millis() < transitionUntil) {
    fill_solid(ringLeds, NUM_LEDS_RING, ringTransitionColorForMode(currentMode));
    textColor = matrixTransitionTextColor(currentMode);
    backgroundColor = matrixTransitionBackgroundColor(currentMode);
  }

  // --- UPDATE DISPLAYS ---
  FastLED.show();
  
  // Update Front Matrix
  matrixFront.fillScreen(backgroundColor);
  matrixFront.setCursor(x, 0);
  matrixFront.setTextColor(textColor);
  matrixFront.print(scrollingText);
  matrixFront.show();

  /* // UNCOMMENT FOR 2ND MATRIX (Mirrors the Front)
  matrixBack.fillScreen(0);
  matrixBack.setCursor(x, 0); // Use same 'x' to sync scroll
  matrixBack.setTextColor(textColor);
  matrixBack.print(scrollingText);
  matrixBack.show();
  */


  // Scroll Logic (slower scroll)
  if (++scrollCounter >= 3) {
    scrollCounter = 0;
    x--;
    if (x < (int)-(scrollingText.length() * 6)) {
      x = matrixFront.width();
    }
  }

  delay(30);
}

// --- HELPER FUNCTIONS ---
void runFanBreathing(int minS, int maxS) {
  fanSpeed += fanDirection;
  if (fanSpeed >= maxS || fanSpeed <= minS) fanDirection = -fanDirection;
  fanSpeed = constrain(fanSpeed, minS, maxS);
  ledcWrite(PIN_FAN, fanSpeed);
}

void runMistBreathing(int minM, int maxM) {
  mistPower += mistDirection;
  if (mistPower >= maxM || mistPower <= minM) {
    mistDirection = -mistDirection;
  }
  mistPower = constrain(mistPower, MIST_MIN, MIST_MAX);
  ledcWrite(PIN_MIST, mistPower);
}

void startModeTransition(Mode mode) {
  transitionActive = true;
  transitionUntil = millis() + 700;
  // Preload fire heat for active mode so the first frame pops.
  if (mode == MODE_ACTIVE) {
    for (int i = 0; i < NUM_LEDS_RING; i++) {
      fireHeat[i] = random8(120, 200);
    }
  }
}

uint16_t matrixColorForMode(Mode mode) {
  switch (mode) {
    case MODE_PENALTY:
      return matrixFront.Color(255, 80, 80);
    case MODE_ACTIVE:
      return matrixFront.Color(255, 100, 0);
    case MODE_IDLE:
    default:
      return matrixFront.Color(120, 180, 255);
  }
}

uint16_t matrixTransitionTextColor(Mode mode) {
  switch (mode) {
    case MODE_PENALTY:
      return matrixFront.Color(255, 160, 160);
    case MODE_ACTIVE:
      return matrixFront.Color(255, 220, 140);
    case MODE_IDLE:
    default:
      return matrixFront.Color(180, 220, 255);
  }
}

uint16_t matrixTransitionBackgroundColor(Mode mode) {
  switch (mode) {
    case MODE_PENALTY:
      return matrixFront.Color(80, 0, 0);
    case MODE_ACTIVE:
      return matrixFront.Color(70, 20, 0);
    case MODE_IDLE:
    default:
      return matrixFront.Color(10, 20, 50);
  }
}

CRGB ringTransitionColorForMode(Mode mode) {
  switch (mode) {
    case MODE_PENALTY:
      return CRGB(200, 20, 20);
    case MODE_ACTIVE:
      return CRGB(255, 150, 40);
    case MODE_IDLE:
    default:
      return CRGB(40, 70, 160);
  }
}

void runFireEffect() {
  for (int i = 0; i < NUM_LEDS_RING; i++) {
    fireHeat[i] = qsub8(fireHeat[i], random8(0, ((FIRE_COOLING * 10) / NUM_LEDS_RING) + 2));
  }

  for (int k = NUM_LEDS_RING - 1; k >= 2; k--) {
    fireHeat[k] = (fireHeat[k - 1] + fireHeat[k - 2] + fireHeat[k - 2]) / 3;
  }

  if (random8() < FIRE_SPARKING) {
    int sparkIndex = random8((NUM_LEDS_RING / 6) + 2);
    fireHeat[sparkIndex] = qadd8(fireHeat[sparkIndex], random8(160, 255));
  }

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