#include <Adafruit_GFX.h>
#include <Adafruit_NeoMatrix.h>
#include <Adafruit_NeoPixel.h>
#include <FastLED.h>

// --- PIN CONFIGURATION ---
#define PIN_MATRIX  5
#define PIN_RING    18
#define PIN_FAN     4   // Fan MOSFET
#define PIN_MIST    12  // Mist MOSFET

// --- SETTINGS ---
#define NUM_LEDS_RING 24

// --- OBJECTS ---
Adafruit_NeoMatrix matrix = Adafruit_NeoMatrix(32, 8, PIN_MATRIX,
  NEO_MATRIX_TOP + NEO_MATRIX_LEFT +
  NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG,
  NEO_GRB + NEO_KHZ800);

CRGB ringLeds[NUM_LEDS_RING];

// --- VARIABLES ---
int x = matrix.width();

// FAN VARIABLES
int fanSpeed = 60;
int fanDirection = 5;

// MIST VARIABLES (New!)
int mistPower = 150;     // Start at the "Safety Floor" (Not 0)
int mistDirection = 5;   // How fast to change mist levels
int minMist = 150;       // SAFETY FLOOR: Keep this above 100 to prevent board reset
int maxMist = 255;       // Max Power

void setup() {
  // 1. Setup Mist (NOW AS PWM)
  // frequency: 1000Hz (Smoother for power delivery), 8-bit resolution
  ledcAttach(PIN_MIST, 1000, 8); 
  ledcWrite(PIN_MIST, 255); // Start Full Blast to wake it up

  // 2. Setup Fan (PWM)
  ledcAttach(PIN_FAN, 5000, 8); 

  // 3. Setup Matrix
  matrix.begin();
  matrix.setTextWrap(false);
  matrix.setBrightness(30);

  // 4. Setup Ring
  FastLED.addLeds<WS2812B, PIN_RING, GRB>(ringLeds, NUM_LEDS_RING);
  FastLED.setBrightness(100);
}

void loop() {
  // --- PART A: MIST MODULATION (Breathing Effect) ---
  // Instead of ON/OFF, we slide the power up and down
  mistPower += mistDirection;
  
  // Bounce between Max and Min (Never 0)
  if (mistPower >= maxMist || mistPower <= minMist) {
    mistDirection = -mistDirection;
  }
  
  // Send power level to Mist Board
  ledcWrite(PIN_MIST, mistPower);


  // --- PART B: FAN BREATHE ---
  // We sync this slightly differently to create a "Natural" random feel
  fanSpeed += fanDirection;
  if (fanSpeed >= 255 || fanSpeed <= 60) fanDirection = -fanDirection;
  ledcWrite(PIN_FAN, fanSpeed);


  // --- PART C: FIRE VISUALS ---
  // Fire intensity matches Mist Power
  int fireBrightness = map(mistPower, minMist, maxMist, 50, 255);
  
  for(int i = 0; i < NUM_LEDS_RING; i++) {
     // Random Flicker logic
     if(random(0,10) > 3) {
       int flicker = random(0, 60);
       ringLeds[i] = CRGB(fireBrightness - flicker, (fireBrightness/3) - flicker, 0); 
     }
  }
  FastLED.show();


  // --- PART D: TEXT ---
  matrix.fillScreen(0);
  matrix.setCursor(x, 0);
  
  // Color changes based on intensity
  if (mistPower > 200) {
     matrix.setTextColor(matrix.Color(255, 100, 0)); // Orange (Hot)
     matrix.print(F("HIGH FLAME"));
  } else {
     matrix.setTextColor(matrix.Color(0, 0, 255));   // Blue (Low)
     matrix.print(F("LOW FLAME"));
  }
  
  if(--x < -80) x = matrix.width();
  matrix.show();

  delay(30);
}