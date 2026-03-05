/*
 * SCOOBY DOO LIGHTING - 3 CHANNEL VERSION
 * Arduino Uno - Triple NeoPixel control
 * Ring 1: Pin 10 (24 LEDs)
 * Ring 2: Pin 9 (16 LEDs)
 * Ring 3: Pin 6 (16 LEDs)
 */

#include <Adafruit_NeoPixel.h>

#define RING1_PIN 10
#define RING2_PIN 9
#define RING3_PIN 6
#define RING1_LEDS 24
#define RING2_LEDS 16
#define RING3_LEDS 16

Adafruit_NeoPixel ring1(RING1_LEDS, RING1_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel ring2(RING2_LEDS, RING2_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel ring3(RING3_LEDS, RING3_PIN, NEO_GRB + NEO_KHZ800);

bool lightsOn = false;
uint8_t brightness = 200;
uint8_t red = 255, green = 255, blue = 255;
String inputString = "";

void setup() {
  Serial.begin(115200);
  
  ring1.begin();
  ring2.begin();
  ring3.begin();
  ring1.setBrightness(brightness);
  ring2.setBrightness(brightness);
  ring3.setBrightness(brightness);
  ring1.clear();
  ring2.clear();
  ring3.clear();
  ring1.show();
  ring2.show();
  ring3.show();
  
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("SCOOBY 3-CHANNEL READY");
  Serial.println("========================================");
  Serial.println("Ring 1: Pin 10 (24 LEDs)");
  Serial.println("Ring 2: Pin 9 (16 LEDs)");
  Serial.println("Ring 3: Pin 6 (16 LEDs)");
  Serial.println("Total: 56 LEDs");
  Serial.println("Commands:");
  Serial.println("  ON/OFF - Lights on/off");
  Serial.println("  B255   - Set brightness (0-255)");
  Serial.println("  C255,0,0 - Set color (R,G,B)");
  Serial.println("  TEST   - Rainbow test");
  Serial.println("  STATUS - Show current settings");
  Serial.println("========================================\n");
  
  // Flash green on all 3 rings
  setColor(0, 255, 0);
  delay(200);
  setColor(0, 0, 0);
  
  Serial.println("Arduino Ready");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputString.length() > 0) {
        processCommand(inputString);
        inputString = "";
      }
    } else if (c >= 32 && c <= 126) {  // Only printable characters
      inputString += c;
      // Give time for rest of command to arrive
      if (inputString.length() == 1) {
        delay(5);  // Small delay after first character
      }
    }
  }
  
  // Keep lights refreshed if they're supposed to be on
  if (lightsOn) {
    ring1.show();
    ring2.show();
    ring3.show();
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
      ring1.setBrightness(brightness);
      ring2.setBrightness(brightness);
      ring3.setBrightness(brightness);
      // Auto-turn on lights and show the change
      if (!lightsOn) {
        lightsOn = true;
      }
      setColor(red, green, blue);
      Serial.print("OK:B=");
      Serial.println(val);
    }
  }
  else if (cmd.startsWith("C")) {
    String colorStr = cmd.substring(1);
    int comma1 = colorStr.indexOf(',');
    int comma2 = colorStr.lastIndexOf(',');
    
    if (comma1 > 0 && comma2 > comma1) {
      red = colorStr.substring(0, comma1).toInt();
      green = colorStr.substring(comma1 + 1, comma2).toInt();
      blue = colorStr.substring(comma2 + 1).toInt();
      
      // Auto-turn on lights and show the color
      if (!lightsOn) {
        lightsOn = true;
      }
      setColor(red, green, blue);
      Serial.println("OK:COLOR");
    }
  }
  else if (cmd == "TEST") {
    runRainbowTest();
    Serial.println("OK:TEST");
  }
  else if (cmd == "STATUS") {
    Serial.print("STATUS: Lights=");
    Serial.print(lightsOn ? "ON" : "OFF");
    Serial.print(" | Brightness=");
    Serial.print(brightness);
    Serial.print(" | Color=RGB(");
    Serial.print(red);
    Serial.print(",");
    Serial.print(green);
    Serial.print(",");
    Serial.print(blue);
    Serial.println(")");
  }
  else {
    Serial.println("ERR:UNKNOWN_CMD");
  }
}

void setColor(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = ring1.Color(r, g, b);
  
  // Ring 1 - 24 LEDs
  for (int i = 0; i < RING1_LEDS; i++) {
    ring1.setPixelColor(i, color);
  }
  
  // Ring 2 - 16 LEDs
  for (int i = 0; i < RING2_LEDS; i++) {
    ring2.setPixelColor(i, color);
  }
  
  // Ring 3 - 16 LEDs
  for (int i = 0; i < RING3_LEDS; i++) {
    ring3.setPixelColor(i, color);
  }
  
  ring1.show();
  ring2.show();
  ring3.show();
}

void runRainbowTest() {
  uint8_t savedBrightness = brightness;
  ring1.setBrightness(100);
  ring2.setBrightness(100);
  ring3.setBrightness(100);
  
  Serial.println("Running rainbow test on all 3 rings...");
  
  for (int j = 0; j < 256; j += 4) {
    // Ring 1 - 24 LEDs
    for (int i = 0; i < RING1_LEDS; i++) {
      uint32_t c = Wheel((i + j) & 255);
      ring1.setPixelColor(i, c);
    }
    
    // Ring 2 - 16 LEDs
    for (int i = 0; i < RING2_LEDS; i++) {
      uint32_t c = Wheel((i + j) & 255);
      ring2.setPixelColor(i, c);
    }
    
    // Ring 3 - 16 LEDs
    for (int i = 0; i < RING3_LEDS; i++) {
      uint32_t c = Wheel((i + j) & 255);
      ring3.setPixelColor(i, c);
    }
    
    ring1.show();
    ring2.show();
    ring3.show();
    delay(10);
  }
  
  ring1.setBrightness(savedBrightness);
  ring2.setBrightness(savedBrightness);
  ring3.setBrightness(savedBrightness);
  if (lightsOn) {
    setColor(red, green, blue);
  } else {
    setColor(0, 0, 0);
  }
}

uint32_t Wheel(byte WheelPos) {
  WheelPos = 255 - WheelPos;
  if (WheelPos < 85) {
    return ring1.Color(255 - WheelPos * 3, 0, WheelPos * 3);
  }
  if (WheelPos < 170) {
    WheelPos -= 85;
    return ring1.Color(0, WheelPos * 3, 255 - WheelPos * 3);
  }
  WheelPos -= 170;
  return ring1.Color(WheelPos * 3, 255 - WheelPos * 3, 0);
}
