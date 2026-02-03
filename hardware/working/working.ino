#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_NeoMatrix.h>
#include <Adafruit_NeoPixel.h>
#include <FastLED.h>

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

// --- VARIABLES ---
int paxCount = 0;
bool phoneDetected = false;
String scrollingText = "Booting...";
int x = matrixFront.width();

// Animation Vars
int fanSpeed = 60;
int fanDirection = 5;
int mistPower = MIST_MIN; 
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
  
  // Start Mist at Floor
  ledcWrite(PIN_MIST, MIST_MIN); 

  // Setup BOTH Rings (FastLED handles the total count)
  FastLED.addLeds<WS2812B, PIN_RING, GRB>(ringLeds, NUM_LEDS_RING);
  FastLED.setBrightness(100);

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
  
  // 1. DETERMINE COLORS & MODES
  uint16_t textColor;
  
  if (phoneDetected) {
    // === STATE: PENALTY ===
    ledcWrite(PIN_MIST, MIST_MIN); 
    ledcWrite(PIN_FAN, 0);        
    
    // Grey/Red Glitch on BOTH RINGS
    fill_solid(ringLeds, NUM_LEDS_RING, CRGB::Grey);
    if(random(0,10) > 8) ringLeds[random(0, NUM_LEDS_RING)] = CRGB::Red; 
    
    textColor = matrixFront.Color(100, 100, 100); // Grey

  } else if (paxCount == 0) {
    // === STATE: IDLE ===
    ledcWrite(PIN_MIST, MIST_MIN);
    runFanBreathing(40, 80);      
    
    // Blue Pulse on BOTH RINGS
    int breath = (millis() / 20) % 255; 
    fill_solid(ringLeds, NUM_LEDS_RING, CRGB(0, 0, map(breath, 0, 255, 20, 100)));
    
    textColor = matrixFront.Color(0, 0, 255); // Blue

  } else {
    // === STATE: ACTIVE ===
    int upperLimit = (paxCount >= 3) ? MIST_MAX : 220;
    runMistBreathing(MIST_MIN, upperLimit); 
    runFanBreathing(100, 255);            
    
    // Fire Effect on BOTH RINGS
    // We loop through ALL LEDs (Ring 1 + Ring 2)
    for(int i = 0; i < NUM_LEDS_RING; i++) {
       if(random(0,10) > 3) {
         int flicker = random(0, 60);
         ringLeds[i] = CRGB(255 - flicker, 100 - flicker, 0); 
       }
    }
    
    if (paxCount >= 5) textColor = matrixFront.Color(255, 0, 255); // Purple
    else textColor = matrixFront.Color(255, 100, 0); // Orange
  }

  // --- UPDATE DISPLAYS ---
  FastLED.show();
  
  // Update Front Matrix
  matrixFront.fillScreen(0);
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

  // Scroll Logic
  if(--x < (int)-(scrollingText.length() * 6)) {
    x = matrixFront.width();
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