#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>

// --- CONFIGURATION ---
const char* ssid     = "Emmanuel’s iPhone"; // <--- UPDATE THIS
const char* password = "onseneggpassword123";   // <--- UPDATE THIS
unsigned int localPort = 4210;

// --- OBJECTS ---
WiFiUDP udp;
char packetBuffer[512]; // Buffer to hold incoming packet

// --- VARIABLES ---
int paxCount = 0;
bool phoneDetected = false;
String scrollingText = "Waiting...";

void setup() {
  Serial.begin(115200);
  
  // 1. Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected! IP: ");
  Serial.println(WiFi.localIP());

  // 2. Start Listening
  udp.begin(localPort);
}

void loop() {
  // 1. Check for Data
  int packetSize = udp.parsePacket();
  
  if (packetSize) {
    // Read the packet
    int len = udp.read(packetBuffer, 511);
    packetBuffer[len] = 0; // Null terminate string

    // Parse JSON
    JsonDocument doc; // ArduinoJson v7
    DeserializationError error = deserializeJson(doc, packetBuffer);

    if (!error) {
      // 2. EXTRACT DATA
      paxCount = doc["c"];
      phoneDetected = doc["p"];
      const char* t = doc["t"];
      scrollingText = String(t);

      // Debug Print
      Serial.printf("Pax: %d | Phone: %s | Text: %s\n", 
                    paxCount, 
                    phoneDetected ? "YES" : "NO", 
                    t);
      
      // 3. TRIGGER YOUR HARDWARE FUNCTIONS
      // updateMist(paxCount);
      // updateLEDs(paxCount, phoneDetected);
    }
  }

  // Hardware updates happen here...
}