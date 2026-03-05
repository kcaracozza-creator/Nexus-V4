/*
 * NEXUS ESP32 LIGHTING ONLY - NO WIFI
 * Simple serial-controlled NeoPixel lighting
 */

#include <Adafruit_NeoPixel.h>

// NeoPixel Configuration
#define RING1_PIN 16
#define RING2_PIN 17
#define LEDS_PER_RING 16

Adafruit_NeoPixel ring1(LEDS_PER_RING, RING1_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel ring2(LEDS_PER_RING, RING2_PIN, NEO_GRB + NEO_KHZ800);

bool lightsOn = false;
uint8_t brightness = 200;
String inputString = "";

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  // Initialize NeoPixels
  ring1.begin();
  ring2.begin();
  ring1.setBrightness(brightness);
  ring2.setBrightness(brightness);
  ring1.clear();
  ring2.clear();
  ring1.show();
  ring2.show();
  
  Serial.println("\n========================================");
  Serial.println("NEXUS LIGHTING CONTROLLER READY");
  Serial.println("========================================");
  Serial.println("Commands:");
  Serial.println("  ON  - Turn lights on");
  Serial.println("  OFF - Turn lights off");
  Serial.println("  B<0-255> - Set brightness (B255)");
  Serial.println("========================================\n");
  
  // Flash green to show ready
  setColor(0, 255, 0);
  delay(200);
  setColor(0, 0, 0);
}

void loop() {
  // Read serial commands
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputString.length() > 0) {
        processCommand(inputString);
        inputString = "";
      }
    } else {
      inputString += c;
    }
  }
}

void processCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  
  Serial.print("CMD: ");
  Serial.println(cmd);
  
  if (cmd == "ON" || cmd == "L1") {
    lightsOn = true;
    setColor(255, 255, 255);
    Serial.println("OK:LIGHTS_ON");
  }
  else if (cmd == "OFF" || cmd == "L0") {
    lightsOn = false;
    setColor(0, 0, 0);
    Serial.println("OK:LIGHTS_OFF");
  }
  else if (cmd.startsWith("B")) {
    int val = cmd.substring(1).toInt();
    if (val >= 0 && val <= 255) {
      brightness = val;
      ring1.setBrightness(brightness);
      ring2.setBrightness(brightness);
      if (lightsOn) {
        setColor(255, 255, 255);
      }
      Serial.print("OK:BRIGHTNESS=");
      Serial.println(val);
    }
  }
  else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}

void setColor(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = ring1.Color(r, g, b);
  for (int i = 0; i < LEDS_PER_RING; i++) {
    ring1.setPixelColor(i, color);
    ring2.setPixelColor(i, color);
  }
  ring1.show();
  ring2.show();
}
