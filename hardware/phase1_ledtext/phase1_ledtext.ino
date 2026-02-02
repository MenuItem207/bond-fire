#include <Adafruit_GFX.h>
#include <Adafruit_NeoMatrix.h>
#include <Adafruit_NeoPixel.h>

#define PIN_MATRIX 5

// --- MATRIX CONFIGURATION ---
// 32 pixels wide, 8 pixels tall
// NEO_MATRIX_TOP + NEO_MATRIX_LEFT + NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG
// ^^^ These settings depend on how your specific panel was manufactured. 
// If text is mirrored or upside down, we just change these words.
Adafruit_NeoMatrix matrix = Adafruit_NeoMatrix(32, 8, PIN_MATRIX,
  NEO_MATRIX_TOP     + NEO_MATRIX_LEFT +
  NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG,
  NEO_GRB            + NEO_KHZ800);

int x    = matrix.width(); // Cursor position
int pass = 0;

void setup() {
  matrix.begin();
  matrix.setTextWrap(false); // Allow text to scroll off screen
  matrix.setBrightness(30);  // Low brightness for safety
  matrix.setTextColor(matrix.Color(255, 0, 0)); // Red Text
}

void loop() {
  matrix.fillScreen(0);    // Clear screen
  matrix.setCursor(x, 0);  // Set cursor at current X position
  matrix.print(F("Hello World"));

  // Determine length of text to know when to reset
  // -6 pixels per character roughly
  if(--x < -70) { 
    x = matrix.width(); // Reset to right side
    
    // Change color each pass for fun
    if(++pass >= 3) pass = 0;
    switch(pass) {
      case 0: matrix.setTextColor(matrix.Color(255, 0, 0)); break; // Red
      case 1: matrix.setTextColor(matrix.Color(0, 255, 0)); break; // Green
      case 2: matrix.setTextColor(matrix.Color(0, 0, 255)); break; // Blue
    }
  }
  
  matrix.show();
  delay(50); // Speed of scroll
}