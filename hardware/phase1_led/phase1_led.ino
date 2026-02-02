#include <FastLED.h>

// --- PIN CONFIGURATION ---
#define PIN_MATRIX    5     // GPIO 5 for Matrix Data
#define PIN_RING      18    // GPIO 18 for Ring Data

// --- LED COUNTS ---
#define NUM_LEDS_MATRIX 256 // 8x32 Matrix
#define NUM_LEDS_RING   24  // Standard Ring

// --- LED ARRAYS ---
CRGB matrixLeds[NUM_LEDS_MATRIX];
CRGB ringLeds[NUM_LEDS_RING];

void setup() {
  // 1. Setup Matrix
  FastLED.addLeds<WS2812B, PIN_MATRIX, GRB>(matrixLeds, NUM_LEDS_MATRIX);
  
  // 2. Setup Ring
  FastLED.addLeds<WS2812B, PIN_RING, GRB>(ringLeds, NUM_LEDS_RING);
  
  // 3. SAFETY LIMITER
  // Limits total power to 2000mA (2 Amps) to be super safe during testing
  FastLED.setMaxPowerInVoltsAndMilliamps(5, 2000); 
  FastLED.setBrightness(40); // Keep it dim (0-255)
  FastLED.clear();
  FastLED.show();
}

void loop() {
  // --- TEST 1: RGB Check ---
  // Flashes Red, Green, Blue to verify wiring colors are correct
  
  // Red
  fill_solid(matrixLeds, NUM_LEDS_MATRIX, CRGB::Red);
  fill_solid(ringLeds, NUM_LEDS_RING, CRGB::Red);
  FastLED.show();
  delay(500);

  // Green
  fill_solid(matrixLeds, NUM_LEDS_MATRIX, CRGB::Green);
  fill_solid(ringLeds, NUM_LEDS_RING, CRGB::Green);
  FastLED.show();
  delay(500);

  // Blue
  fill_solid(matrixLeds, NUM_LEDS_MATRIX, CRGB::Blue);
  fill_solid(ringLeds, NUM_LEDS_RING, CRGB::Blue);
  FastLED.show();
  delay(500);
  
  // --- TEST 2: The "Snake" (Individual Pixel Check) ---
  // Runs a white dot through every single LED to check for dead pixels
  fill_solid(matrixLeds, NUM_LEDS_MATRIX, CRGB::Black);
  fill_solid(ringLeds, NUM_LEDS_RING, CRGB::Black);
  
  // Run around the Ring
  for(int i = 0; i < NUM_LEDS_RING; i++) {
    ringLeds[i] = CRGB::White;
    FastLED.show();
    delay(20);
    ringLeds[i] = CRGB::Black;
  }
  
  // Run across the Matrix
  // We only do the first 32 pixels to save time in the loop
  for(int i = 0; i < 32; i++) {
    matrixLeds[i] = CRGB::White;
    FastLED.show();
    delay(10);
    matrixLeds[i] = CRGB::Black;
  }
}