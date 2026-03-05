/*
 * NEXUS LIGHTING CONTROLLER - Arduino Uno
 * Simple NeoPixel control via serial commands
 * 
 * Hardware:
 * - Arduino Uno (COM5)
 * - 2x NeoPixel Ring (16 LEDs each) OR single strip
 * - 5V Power Supply (3A+ for 32 LEDs)
 * 
 * Connections:
 * - NeoPixel Data → Arduino Pin 6
 * - NeoPixel 5V → External 5V PSU
 * - NeoPixel GND → Common Ground (Arduino + PSU)
 * 
 * Commands (115200 baud):
 * - ON / L1      - Turn lights on (white)
 * - OFF / L0     - Turn lights off
 * - B<0-255>     - Set brightness (B255)
 * - TEST         - Rainbow test pattern
 */

#include <Adafruit_NeoPixel.h>

#define LED_PIN 6           // Data pin for NeoPixels
#define NUM_LEDS 32         // Total LEDs (2 rings x 16)

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

bool lightsOn = false;
uint8_t brightness = 200;
String inputString = "";

void setup() {
  Serial.begin(115200);
  
  // Initialize NeoPixels
  strip.begin();
  strip.setBrightness(brightness);
  strip.clear();
  strip.show();
  
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("NEXUS LIGHTING - Arduino Uno READY");
  Serial.println("========================================");
  Serial.println("Commands:");
  Serial.println("  ON / L1  - Lights on");
  Serial.println("  OFF / L0 - Lights off");
  Serial.println("  B255     - Set brightness");
  Serial.println("  TEST     - Rainbow test");
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
      strip.setBrightness(brightness);
      if (lightsOn) {
        setColor(255, 255, 255);
      }
      Serial.print("OK:BRIGHTNESS=");
      Serial.println(val);
    } else {
      Serial.println("ERROR:BRIGHTNESS_RANGE_0-255");
    }
  }
  else if (cmd == "TEST") {
    runRainbowTest();
    Serial.println("OK:TEST_COMPLETE");
  }
  else if (cmd == "STATUS") {
    Serial.println("STATUS:{");
    Serial.print("  \"lights\":\"");
    Serial.print(lightsOn ? "ON" : "OFF");
    Serial.println("\",");
    Serial.print("  \"brightness\":");
    Serial.println(brightness);
    Serial.println("}");
  }
  else {
    Serial.print("ERROR:UNKNOWN_COMMAND:");
    Serial.println(cmd);
  }
}

void setColor(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = strip.Color(r, g, b);
  for (int i = 0; i < NUM_LEDS; i++) {
    strip.setPixelColor(i, color);
  }
  strip.show();
}

void runRainbowTest() {
  Serial.println("TEST:RAINBOW_START");
  
  uint8_t savedBrightness = brightness;
  strip.setBrightness(100);
  
  // Rainbow cycle
  for (int j = 0; j < 256; j += 4) {
    for (int i = 0; i < NUM_LEDS; i++) {
      strip.setPixelColor(i, Wheel((i + j) & 255));
    }
    strip.show();
    delay(10);
  }
  
  // Restore state
  strip.setBrightness(savedBrightness);
  if (lightsOn) {
    setColor(255, 255, 255);
  } else {
    setColor(0, 0, 0);
  }
}

// Rainbow color wheel
uint32_t Wheel(byte WheelPos) {
  WheelPos = 255 - WheelPos;
  if (WheelPos < 85) {
    return strip.Color(255 - WheelPos * 3, 0, WheelPos * 3);
  }
  if (WheelPos < 170) {
    WheelPos -= 85;
    return strip.Color(0, WheelPos * 3, 255 - WheelPos * 3);
  }
  WheelPos -= 170;
  return strip.Color(WheelPos * 3, 255 - WheelPos * 3, 0);
}
