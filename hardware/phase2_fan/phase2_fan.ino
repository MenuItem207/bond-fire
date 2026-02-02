#include <Adafruit_GFX.h>
#include <Adafruit_NeoMatrix.h>
#include <Adafruit_NeoPixel.h>

// --- PIN CONFIG ---
#define PIN_MATRIX  5
#define PIN_RING    18
#define PIN_FAN     4   // <--- UPDATED to the working PIN 4

// --- SETUP OBJECTS ---
Adafruit_NeoMatrix matrix = Adafruit_NeoMatrix(32, 8, PIN_MATRIX,
  NEO_MATRIX_TOP + NEO_MATRIX_LEFT +
  NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG,
  NEO_GRB + NEO_KHZ800);

// --- VARIABLES ---
int x = matrix.width();
int fanSpeed = 60;      // Start at 60 (Fans usually stall below this)
int fanDirection = 5;   // How much to change speed per loop

void setup() {
  // 1. Setup Lights
  matrix.begin();
  matrix.setTextWrap(false);
  matrix.setBrightness(30);
  matrix.setTextColor(matrix.Color(0, 255, 0)); // Green Text

  // 2. Setup Fan (PWM)
  // This sets up Pin 4 to act like a variable speed dial
  // Frequency: 5000Hz, Resolution: 8-bit (0-255)
  ledcAttach(PIN_FAN, 5000, 8); 
}

void loop() {
  // --- PART A: SCROLL TEXT (Phase 1) ---
  matrix.fillScreen(0);
  matrix.setCursor(x, 0);
  matrix.print(F("Breathing..."));
  
  if(--x < -80) {
    x = matrix.width();
  }
  matrix.show();

  // --- PART B: FAN BREATHE (Phase 2) ---
  // Change fan speed
  fanSpeed += fanDirection;

  // Reverse direction at limits (60 to 255)
  if (fanSpeed >= 255 || fanSpeed <= 60) {
    fanDirection = -fanDirection;
  }
  
  // Send Speed to Fan
  ledcWrite(PIN_FAN, fanSpeed);

  delay(30); // Speed of animation
}