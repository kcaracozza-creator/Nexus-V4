/*
 * 🐕 SCOOBY DOO LIGHTING CONTROLLER 🐕
 * Arduino Uno - NeoPixel Control
 * "Ruh-roh! Time to scan some cards!"
 * 
 * Hardware:
 * - Arduino Uno (INLAND PLUS clone)
 * - NeoPixel LEDs on Pin 8
 * - External 5V PSU for LEDs
 * 
 * Commands (115200 baud):
 * - ON / L1      - Zoinks! Lights on!
 * - OFF / L0     - Lights off
 * - B<0-255>     - Set brightness
 * - C<R,G,B>     - Set color (C255,0,0 for red)
 * - TEST         - Rainbow test (like Scooby Snacks!)
 */

#include <Adafruit_NeoPixel.h>

#define LED_PIN 6           // Data pin for NeoPixels
#define NUM_LEDS 32         // Total LEDs - CHANGE THIS IF NEEDED

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

bool lightsOn = false;
uint8_t brightness = 200;
uint8_t red = 255, green = 255, blue = 255;
String inputString = "";

void setup() {
  Serial.begin(115200);
  
  // Initialize NeoPixels
  strip.begin();
  strip.setBrightness(brightness);
  strip.clear();
  strip.show();
  
  delay(1000);
  
  Serial.println("\nSCOOBY LIGHTING READY");
  Serial.println("ON/OFF/B255/C255,0,0/TEST/STATUS");
  
  // Flash green
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
    setColor(red, green, blue);
    Serial.println("OK:ON");
  }
  else if (cmd == "OFF" || cmd == "L0") {
    lightsOn = false;
    setColor(0, 0, 0);
    Serial.println("OK:OFF");
  }
  else if (cmd.startsWith("B")) {
    int val = cmd.substring(1).toInt();
    if (val >= 0 && val <= 255) {
      brightness = val;
      strip.setBrightness(brightness);
      if (lightsOn) {
        setColor(red, green, blue);
      }
      Serial.print("OK:BRIGHTNESS=");
      Serial.println(val);
    } else {
      Serial.println("ERROR:BRIGHT_0-255");
    }
  }
  else if (cmd.startsWith("C")) {
    // Format: C255,255,255
    String colorStr = cmd.substring(1);
    int comma1 = colorStr.indexOf(',');
    int comma2 = colorStr.lastIndexOf(',');
    
    if (comma1 > 0 && comma2 > comma1) {
      red = colorStr.substring(0, comma1).toInt();
      green = colorStr.substring(comma1 + 1, comma2).toInt();
      blue = colorStr.substring(comma2 + 1).toInt();
      
      if (lightsOn) {
        setColor(red, green, blue);
      }
      Serial.print("OK:COLOR=RGB(");
      Serial.print(red);
      Serial.print(",");
      Serial.print(green);
      Serial.print(",");
      Serial.print(blue);
      Serial.println(")");
    } else {
      Serial.println("ERROR:FORMAT_C255,255,255");
    }
  }
  else if (cmd == "TEST") {
    runRainbowTest();
    Serial.println("OK:TEST_DONE");
  }
  else if (cmd == "STATUS") {
    Serial.print("L:");
    Serial.print(lightsOn ? "ON" : "OFF");
    Serial.print(" B:");
    Serial.print(brightness);
    Serial.print(" RGB:");
    Serial.print(red);
    Serial.print(",");
    Serial.print(green);
    Serial.print(",");
    Serial.println(blue);
  }
  else {
    Serial.print("ERROR:UNKNOWN:");
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
    setColor(red, green, blue);
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
