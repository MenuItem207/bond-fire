#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_NeoMatrix.h>
#include <Adafruit_NeoPixel.h>
#include <FastLED.h>

// --- WIFI CONFIGURATION ---
const char* ssid     = "Emmanuel :)";    // Updated: Simpler name is much safer!
const char* password = "onseneggpassword123";  // <--- DOUBLE CHECK THIS!
unsigned int localPort = 4210;

// --- HARDWARE PINS ---
#define PIN_MATRIX  5
#define PIN_RING    18
#define PIN_FAN     4   
#define PIN_MIST    12  

// --- LED SETTINGS ---
#define NUM_LEDS_RING 24

// --- OBJECTS ---
WiFiUDP udp;
char packetBuffer[512]; 

Adafruit_NeoMatrix matrix = Adafruit_NeoMatrix(32, 8, PIN_MATRIX,
  NEO_MATRIX_TOP + NEO_MATRIX_LEFT +
  NEO_MATRIX_COLUMNS + NEO_MATRIX_ZIGZAG,
  NEO_GRB + NEO_KHZ800);

CRGB ringLeds[NUM_LEDS_RING];

// --- VARIABLES ---
int paxCount = 0;
bool phoneDetected = false;
String scrollingText = "Booting...";
int x = matrix.width();

// Animation Vars
int fanSpeed = 60;
int fanDirection = 5;
int mistPower = 150;
int mistDirection = 5;

void setup() {
  Serial.begin(115200);
  // Wait nicely for serial port to open (good for debugging)
  unsigned long startWait = millis();
  while (!Serial && millis() - startWait < 3000) { delay(10); } 
  
  Serial.println("\n\n=== BONDFIRE SYSTEM START ===");

  // 1. INIT MATRIX (Visual Feedback)
  matrix.begin();
  matrix.setTextWrap(false);
  matrix.setBrightness(20);
  matrix.setTextColor(matrix.Color(255, 0, 0)); 
  matrix.fillScreen(0);
  matrix.setCursor(0, 0);
  matrix.print("SCAN...");
  matrix.show();
  Serial.println("Matrix Initialized.");

  // 2. INIT HARDWARE
  ledcAttach(PIN_FAN, 5000, 8); 
  ledcAttach(PIN_MIST, 1000, 8); 
  FastLED.addLeds<WS2812B, PIN_RING, GRB>(ringLeds, NUM_LEDS_RING);
  FastLED.setBrightness(100);
  Serial.println("Hardware Pins Attached.");

  // 3. DEBUG: SCAN NETWORKS
  // This helps us see EXACTLY what the ESP32 sees
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  Serial.println("\n--- STARTING WIFI SCAN ---");
  int n = WiFi.scanNetworks();
  Serial.println("Scan done");
  
  bool foundTarget = false;

  if (n == 0) {
      Serial.println("No networks found.");
      matrix.fillScreen(0);
      matrix.setCursor(0,0);
      matrix.print("NO WIFI");
      matrix.show();
  } else {
      Serial.print(n);
      Serial.println(" networks found:");
      for (int i = 0; i < n; ++i) {
          // Print SSID and RSSI for each network found
          String currentSSID = WiFi.SSID(i);
          Serial.print(i + 1);
          Serial.print(": ");
          Serial.print(currentSSID);
          Serial.print(" (");
          Serial.print(WiFi.RSSI(i));
          Serial.print(")");
          Serial.println((WiFi.encryptionType(i) == WIFI_AUTH_OPEN)?" ":"*");
          
          if(currentSSID == ssid) foundTarget = true;
          delay(10);
      }
  }
  Serial.println("--- SCAN COMPLETE ---\n");

  if(foundTarget) {
    Serial.println("SUCCESS: Target WiFi found in scan list!");
  } else {
    Serial.println("WARNING: Target WiFi NOT found in scan list.");
    Serial.println("Check: 1. Is Hotspot ON?  2. Is 'Maximize Compatibility' ON?");
  }

  // 4. ATTEMPT CONNECTION
  Serial.print("Attempting to connect to: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int dot = 0;
  // Wait loop
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    
    // Matrix Feedback
    matrix.fillScreen(0);
    matrix.setCursor(0, 0);
    matrix.setTextColor(matrix.Color(255, 100, 0)); 
    matrix.print("JOINING");
    // Draw loading dots
    for(int i=0; i<dot; i++) matrix.drawPixel(25+i*2, 7, matrix.Color(255, 255, 255));
    matrix.show();
    
    dot++;
    if(dot > 3) dot = 0;
    
    // If it takes too long, remind user to check Serial
    if (millis() > 20000 && millis() < 21000) {
       Serial.println("\nSTUCK? Check Serial Monitor for details.");
    }
  }

  // 5. CONNECTED!
  Serial.println("\nWiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  
  matrix.fillScreen(0);
  matrix.setCursor(0, 0);
  matrix.setTextColor(matrix.Color(0, 255, 0)); 
  matrix.print("OK!");
  matrix.show();
  delay(1000);

  udp.begin(localPort);
  scrollingText = "Waiting for Laptop...";
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
      
      // Debug Print every time we get data
      Serial.printf("RX: Pax=%d, Phone=%d, Text=%s\n", paxCount, phoneDetected, t);
    } else {
      Serial.print("JSON Error: ");
      Serial.println(error.c_str());
    }
  }

  // --- HARDWARE UPDATES ---
  if (phoneDetected) {
    // STATE: PENALTY
    ledcWrite(PIN_MIST, 0);       
    ledcWrite(PIN_FAN, 0);        
    fill_solid(ringLeds, NUM_LEDS_RING, CRGB::Grey);
    if(random(0,10) > 8) ringLeds[random(0, NUM_LEDS_RING)] = CRGB::Red; 
    matrix.setTextColor(matrix.Color(100, 100, 100)); 

  } else if (paxCount == 0) {
    // STATE: IDLE
    ledcWrite(PIN_MIST, 0);       
    runFanBreathing(40, 80);      
    int breath = (millis() / 20) % 255; 
    fill_solid(ringLeds, NUM_LEDS_RING, CRGB(0, 0, map(breath, 0, 255, 20, 100)));
    matrix.setTextColor(matrix.Color(0, 0, 255)); 

  } else {
    // STATE: ACTIVE
    int minLimit = 150; 
    int maxLimit = (paxCount >= 3) ? 255 : 200;
    
    runMistBreathing(minLimit, maxLimit); 
    runFanBreathing(100, 255);            
    
    for(int i = 0; i < NUM_LEDS_RING; i++) {
       if(random(0,10) > 3) {
         int flicker = random(0, 60);
         ringLeds[i] = CRGB(255 - flicker, 100 - flicker, 0); 
       }
    }
    
    if (paxCount >= 5) matrix.setTextColor(matrix.Color(255, 0, 255)); 
    else matrix.setTextColor(matrix.Color(255, 100, 0)); 
  }

  FastLED.show();
  
  matrix.fillScreen(0);
  matrix.setCursor(x, 0);
  matrix.print(scrollingText);
  if(--x < (int)-(scrollingText.length() * 6)) {
    x = matrix.width();
  }
  matrix.show();

  delay(30);
}

// --- HELPERS ---
void runFanBreathing(int minS, int maxS) {
  fanSpeed += fanDirection;
  if (fanSpeed >= maxS || fanSpeed <= minS) fanDirection = -fanDirection;
  fanSpeed = constrain(fanSpeed, minS, maxS);
  ledcWrite(PIN_FAN, fanSpeed);
}

void runMistBreathing(int minM, int maxM) {
  mistPower += mistDirection;
  if (mistPower >= maxM || mistPower <= minM) mistDirection = -mistDirection;
  mistPower = constrain(mistPower, minM, maxM);
  ledcWrite(PIN_MIST, mistPower);
}