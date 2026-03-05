/*
 * NEXUS CARD SCANNER - ESP32 FIRMWARE v2.0
 * Optimized for ASUS Laptop (192.168.0.7) Integration
 * 
 * Features:
 * - Dual NeoPixel Ring Lighting (32 LEDs total)
 * - Camera Trigger Output
 * - Serial Control (115200 baud)
 * - WiFi HTTP API (optional)
 * - Real-time brightness control
 * - Color temperature presets
 * 
 * Hardware:
 * - ESP32 DevKit v1
 * - 2x NeoPixel Ring (16 LEDs each)
 * - 5V/3A Power Supply
 * - Camera trigger relay (optional)
 * 
 * Connections:
 * ┌─────────────────────────────────────────────┐
 * │ LIGHTING SYSTEM                             │
 * ├─────────────────────────────────────────────┤
 * │ Ring 1 Data    → ESP32 GPIO 16              │
 * │ Ring 2 Data    → ESP32 GPIO 17              │
 * │ Rings 5V       → External 5V PSU            │
 * │ Rings GND      → Common Ground              │
 * └─────────────────────────────────────────────┘
 * 
 * ┌─────────────────────────────────────────────┐
 * │ CAMERA TRIGGER (Optional)                   │
 * ├─────────────────────────────────────────────┤
 * │ Trigger Pin    → ESP32 GPIO 4               │
 * │ (5V pulse for camera shutter)               │
 * └─────────────────────────────────────────────┘
 * 
 * ┌─────────────────────────────────────────────┐
 * │ SERIAL COMMANDS (115200 baud)               │
 * ├─────────────────────────────────────────────┤
 * │ L1          - Lights ON (scan mode)         │
 * │ L0          - Lights OFF                    │
 * │ B<0-255>    - Set Brightness (B255 = max)   │
 * │ C<R,G,B>    - Set Color (C255,255,255)      │
 * │ T<K>        - Color Temp (T5000 = 5000K)    │
 * │ CAP         - Trigger camera capture        │
 * │ SCAN        - Full scan (lights + capture)  │
 * │ TEST        - Run LED test pattern          │
 * │ STATUS      - Print current state           │
 * │ RESET       - Reset to defaults             │
 * └─────────────────────────────────────────────┘
 * 
 * Response Format:
 * - OK:<value> on success
 * - ERROR:<message> on failure
 * - STATUS:<json> for status queries
 */

#include <Adafruit_NeoPixel.h>

// ========== HARDWARE CONFIGURATION ==========
#define RING1_PIN 16              // First NeoPixel ring
#define RING2_PIN 17              // Second NeoPixel ring
#define LEDS_PER_RING 16          // LEDs per ring
#define CAMERA_TRIGGER_PIN 4      // Camera shutter trigger (optional)

// ========== LIGHTING DEFAULTS ==========
#define DEFAULT_BRIGHTNESS 200    // 78% - prevents overexposure
#define DEFAULT_COLOR_TEMP 5000   // 5000K neutral white
#define MAX_BRIGHTNESS 255
#define MIN_BRIGHTNESS 10

// ========== NEOPIXEL OBJECTS ==========
Adafruit_NeoPixel ring1(LEDS_PER_RING, RING1_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel ring2(LEDS_PER_RING, RING2_PIN, NEO_GRB + NEO_KHZ800);

// ========== STATE VARIABLES ==========
bool lightsOn = false;
uint8_t brightness = DEFAULT_BRIGHTNESS;
uint8_t red = 255;
uint8_t green = 255;
uint8_t blue = 255;
uint16_t colorTemp = DEFAULT_COLOR_TEMP;

String inputString = "";
boolean stringComplete = false;

// ========== SETUP ==========
void setup() {
  // Serial communication
  Serial.begin(115200);
  while (!Serial) {
    ; // Wait for serial port to connect (USB CDC)
  }
  
  // Initialize camera trigger
  pinMode(CAMERA_TRIGGER_PIN, OUTPUT);
  digitalWrite(CAMERA_TRIGGER_PIN, LOW);
  
  // Initialize NeoPixel rings
  ring1.begin();
  ring2.begin();
  ring1.setBrightness(brightness);
  ring2.setBrightness(brightness);
  ring1.clear();
  ring2.clear();
  ring1.show();
  ring2.show();
  
  // Startup sequence
  Serial.println("\n\n========================================");
  Serial.println("NEXUS CARD SCANNER - ESP32 READY");
  Serial.println("========================================");
  Serial.println("Firmware Version: 2.0");
  Serial.println("Lighting: 2x16 NeoPixel Rings");
  Serial.print("Default Brightness: ");
  Serial.println(brightness);
  Serial.print("Default Color Temp: ");
  Serial.print(colorTemp);
  Serial.println("K");
  Serial.println("========================================");
  Serial.println("Ready for commands (L1, L0, B255, etc.)");
  Serial.println("========================================\n");
  
  // Visual startup indicator (quick flash)
  setAllLEDs(0, 255, 0);  // Green
  delay(200);
  setAllLEDs(0, 0, 0);    // Off
  
  inputString.reserve(128);
}

// ========== MAIN LOOP ==========
void loop() {
  // Process serial commands
  if (stringComplete) {
    processCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
}

// ========== SERIAL EVENT (Auto-called when data arrives) ==========
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    
    if (inChar == '\n' || inChar == '\r') {
      if (inputString.length() > 0) {
        stringComplete = true;
      }
    } else {
      inputString += inChar;
    }
  }
}

// ========== COMMAND PROCESSOR ==========
void processCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  
  if (cmd.length() == 0) return;
  
  Serial.print("CMD: ");
  Serial.println(cmd);
  
  // ===== LIGHTS CONTROL =====
  if (cmd == "L1" || cmd == "ON") {
    turnLightsOn();
    Serial.println("OK:LIGHTS_ON");
  }
  else if (cmd == "L0" || cmd == "OFF") {
    turnLightsOff();
    Serial.println("OK:LIGHTS_OFF");
  }
  
  // ===== BRIGHTNESS CONTROL =====
  else if (cmd.startsWith("B")) {
    int val = cmd.substring(1).toInt();
    if (val >= MIN_BRIGHTNESS && val <= MAX_BRIGHTNESS) {
      setBrightness(val);
      Serial.print("OK:BRIGHTNESS=");
      Serial.println(val);
    } else {
      Serial.print("ERROR:BRIGHTNESS_OUT_OF_RANGE (");
      Serial.print(MIN_BRIGHTNESS);
      Serial.print("-");
      Serial.print(MAX_BRIGHTNESS);
      Serial.println(")");
    }
  }
  
  // ===== COLOR CONTROL =====
  else if (cmd.startsWith("C")) {
    // Format: C255,255,255
    String colorStr = cmd.substring(1);
    int comma1 = colorStr.indexOf(',');
    int comma2 = colorStr.lastIndexOf(',');
    
    if (comma1 > 0 && comma2 > comma1) {
      int r = colorStr.substring(0, comma1).toInt();
      int g = colorStr.substring(comma1 + 1, comma2).toInt();
      int b = colorStr.substring(comma2 + 1).toInt();
      
      if (r >= 0 && r <= 255 && g >= 0 && g <= 255 && b >= 0 && b <= 255) {
        setColor(r, g, b);
        Serial.print("OK:COLOR=RGB(");
        Serial.print(r);
        Serial.print(",");
        Serial.print(g);
        Serial.print(",");
        Serial.print(b);
        Serial.println(")");
      } else {
        Serial.println("ERROR:COLOR_VALUES_OUT_OF_RANGE");
      }
    } else {
      Serial.println("ERROR:COLOR_FORMAT (use C255,255,255)");
    }
  }
  
  // ===== COLOR TEMPERATURE =====
  else if (cmd.startsWith("T")) {
    int temp = cmd.substring(1).toInt();
    if (temp >= 2700 && temp <= 6500) {
      setColorTemperature(temp);
      Serial.print("OK:COLOR_TEMP=");
      Serial.print(temp);
      Serial.println("K");
    } else {
      Serial.println("ERROR:TEMP_OUT_OF_RANGE (2700-6500K)");
    }
  }
  
  // ===== CAMERA TRIGGER =====
  else if (cmd == "CAP" || cmd == "CAPTURE") {
    triggerCamera();
    Serial.println("OK:CAMERA_TRIGGERED");
  }
  
  // ===== FULL SCAN SEQUENCE =====
  else if (cmd == "SCAN") {
    fullScanSequence();
    Serial.println("OK:SCAN_COMPLETE");
  }
  
  // ===== TEST PATTERN =====
  else if (cmd == "TEST") {
    runTestPattern();
    Serial.println("OK:TEST_COMPLETE");
  }
  
  // ===== STATUS QUERY =====
  else if (cmd == "STATUS") {
    printStatus();
  }
  
  // ===== RESET =====
  else if (cmd == "RESET") {
    resetToDefaults();
    Serial.println("OK:RESET_TO_DEFAULTS");
  }
  
  // ===== UNKNOWN COMMAND =====
  else {
    Serial.print("ERROR:UNKNOWN_COMMAND (");
    Serial.print(cmd);
    Serial.println(")");
  }
}

// ========== LIGHTING FUNCTIONS ==========

void turnLightsOn() {
  lightsOn = true;
  updateLights();
}

void turnLightsOff() {
  lightsOn = false;
  ring1.clear();
  ring2.clear();
  ring1.show();
  ring2.show();
}

void setBrightness(uint8_t val) {
  brightness = constrain(val, MIN_BRIGHTNESS, MAX_BRIGHTNESS);
  ring1.setBrightness(brightness);
  ring2.setBrightness(brightness);
  if (lightsOn) {
    updateLights();
  }
}

void setColor(uint8_t r, uint8_t g, uint8_t b) {
  red = r;
  green = g;
  blue = b;
  if (lightsOn) {
    updateLights();
  }
}

void setColorTemperature(uint16_t kelvin) {
  colorTemp = kelvin;
  
  // Convert color temperature to RGB
  // Simplified algorithm (Tanner Helland approximation)
  float temp = kelvin / 100.0;
  float r, g, b;
  
  // Red
  if (temp <= 66) {
    r = 255;
  } else {
    r = temp - 60;
    r = 329.698727446 * pow(r, -0.1332047592);
    r = constrain(r, 0, 255);
  }
  
  // Green
  if (temp <= 66) {
    g = temp;
    g = 99.4708025861 * log(g) - 161.1195681661;
  } else {
    g = temp - 60;
    g = 288.1221695283 * pow(g, -0.0755148492);
  }
  g = constrain(g, 0, 255);
  
  // Blue
  if (temp >= 66) {
    b = 255;
  } else if (temp <= 19) {
    b = 0;
  } else {
    b = temp - 10;
    b = 138.5177312231 * log(b) - 305.0447927307;
    b = constrain(b, 0, 255);
  }
  
  red = (uint8_t)r;
  green = (uint8_t)g;
  blue = (uint8_t)b;
  
  if (lightsOn) {
    updateLights();
  }
}

void setAllLEDs(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = ring1.Color(r, g, b);
  for (int i = 0; i < LEDS_PER_RING; i++) {
    ring1.setPixelColor(i, color);
    ring2.setPixelColor(i, color);
  }
  ring1.show();
  ring2.show();
}

void updateLights() {
  if (lightsOn) {
    setAllLEDs(red, green, blue);
  } else {
    ring1.clear();
    ring2.clear();
    ring1.show();
    ring2.show();
  }
}

// ========== CAMERA FUNCTIONS ==========

void triggerCamera() {
  // Send 100ms pulse to camera trigger
  digitalWrite(CAMERA_TRIGGER_PIN, HIGH);
  delay(100);
  digitalWrite(CAMERA_TRIGGER_PIN, LOW);
}

void fullScanSequence() {
  // Complete card scan sequence
  Serial.println("SCAN:START");
  
  // Turn on lights
  turnLightsOn();
  Serial.println("SCAN:LIGHTS_ON");
  delay(300);  // Let exposure adjust
  
  // Trigger camera
  triggerCamera();
  Serial.println("SCAN:CAMERA_TRIGGERED");
  delay(100);
  
  // Optional: turn off lights (or leave on for next card)
  // turnLightsOff();
  
  Serial.println("SCAN:COMPLETE");
}

// ========== TEST & DIAGNOSTIC FUNCTIONS ==========

void runTestPattern() {
  Serial.println("TEST:STARTING");
  
  // Save current state
  bool savedLightsOn = lightsOn;
  uint8_t savedBrightness = brightness;
  
  // Test brightness
  brightness = 50;
  ring1.setBrightness(50);
  ring2.setBrightness(50);
  
  // Red
  Serial.println("TEST:RED");
  setAllLEDs(255, 0, 0);
  delay(500);
  
  // Green
  Serial.println("TEST:GREEN");
  setAllLEDs(0, 255, 0);
  delay(500);
  
  // Blue
  Serial.println("TEST:BLUE");
  setAllLEDs(0, 0, 255);
  delay(500);
  
  // White
  Serial.println("TEST:WHITE");
  setAllLEDs(255, 255, 255);
  delay(500);
  
  // Rainbow
  Serial.println("TEST:RAINBOW");
  for (int j = 0; j < 256; j += 4) {
    for (int i = 0; i < LEDS_PER_RING; i++) {
      uint32_t color = Wheel((i + j) & 255);
      ring1.setPixelColor(i, color);
      ring2.setPixelColor(i, color);
    }
    ring1.show();
    ring2.show();
    delay(10);
  }
  
  // Restore state
  brightness = savedBrightness;
  ring1.setBrightness(brightness);
  ring2.setBrightness(brightness);
  lightsOn = savedLightsOn;
  updateLights();
  
  Serial.println("TEST:COMPLETE");
}

void printStatus() {
  Serial.println("STATUS:{");
  Serial.print("  \"lights\": \"");
  Serial.print(lightsOn ? "ON" : "OFF");
  Serial.println("\",");
  Serial.print("  \"brightness\": ");
  Serial.print(brightness);
  Serial.println(",");
  Serial.print("  \"color\": {\"r\":");
  Serial.print(red);
  Serial.print(", \"g\":");
  Serial.print(green);
  Serial.print(", \"b\":");
  Serial.print(blue);
  Serial.println("},");
  Serial.print("  \"colorTemp\": ");
  Serial.print(colorTemp);
  Serial.println(",");
  Serial.print("  \"firmware\": \"2.0\"");
  Serial.println("\n}");
}

void resetToDefaults() {
  brightness = DEFAULT_BRIGHTNESS;
  colorTemp = DEFAULT_COLOR_TEMP;
  setColorTemperature(colorTemp);
  turnLightsOff();
}

// ========== UTILITY FUNCTIONS ==========

// Rainbow color wheel (0-255)
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
