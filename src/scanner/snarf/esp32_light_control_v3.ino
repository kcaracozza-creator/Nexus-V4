/**
 * NEXUS Light Control V3 - ESP32 Firmware
 * ========================================
 * Controls photography lights/LEDs for scanner station via USB serial.
 *
 * Hardware:
 * - ESP32 connected via USB to SNARF
 * - LED/Light outputs for light box photography
 * - PWM support for brightness control
 *
 * Serial Commands (115200 baud):
 * - LIGHTS_ON\n  - Turn on photography lights
 * - LIGHTS_OFF\n - Turn off photography lights
 * - STATUS\n     - Get current light status
 *
 * Patent Pending - Kevin Caracozza
 * Version: 3.0 (Feb 2026)
 */

// ============================================================================
// Pin Configuration
// ============================================================================

// Main photography lights (adjust pins based on your wiring)
#define LIGHT_PIN_1    25    // GPIO25 - Main light 1
#define LIGHT_PIN_2    26    // GPIO26 - Main light 2
#define LIGHT_PIN_3    27    // GPIO27 - Main light 3 (optional)
#define LIGHT_PIN_4    14    // GPIO14 - Main light 4 (optional)

// PWM Configuration
#define PWM_FREQ       5000   // 5 kHz PWM frequency
#define PWM_RESOLUTION 8      // 8-bit resolution (0-255)
#define PWM_CHANNEL_1  0
#define PWM_CHANNEL_2  1
#define PWM_CHANNEL_3  2
#define PWM_CHANNEL_4  3

// Brightness levels (0-255)
#define BRIGHTNESS_FULL  255
#define BRIGHTNESS_OFF   0

// ============================================================================
// Global State
// ============================================================================

bool lightsOn = false;
uint8_t currentBrightness = BRIGHTNESS_OFF;

// ============================================================================
// Setup
// ============================================================================

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  // Configure LED PWM channels
  ledcSetup(PWM_CHANNEL_1, PWM_FREQ, PWM_RESOLUTION);
  ledcSetup(PWM_CHANNEL_2, PWM_FREQ, PWM_RESOLUTION);
  ledcSetup(PWM_CHANNEL_3, PWM_FREQ, PWM_RESOLUTION);
  ledcSetup(PWM_CHANNEL_4, PWM_FREQ, PWM_RESOLUTION);

  // Attach PWM channels to GPIO pins
  ledcAttachPin(LIGHT_PIN_1, PWM_CHANNEL_1);
  ledcAttachPin(LIGHT_PIN_2, PWM_CHANNEL_2);
  ledcAttachPin(LIGHT_PIN_3, PWM_CHANNEL_3);
  ledcAttachPin(LIGHT_PIN_4, PWM_CHANNEL_4);

  // Initialize lights to OFF
  setLights(BRIGHTNESS_OFF);

  // Startup confirmation
  Serial.println("NEXUS_LIGHT_V3_READY");

  // Brief startup blink to confirm hardware
  setLights(BRIGHTNESS_FULL);
  delay(100);
  setLights(BRIGHTNESS_OFF);
  delay(100);
}

// ============================================================================
// Main Loop
// ============================================================================

void loop() {
  // Check for incoming serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();  // Remove whitespace/newlines

    handleCommand(command);
  }

  delay(10);  // Small delay to prevent serial buffer overflow
}

// ============================================================================
// Command Handler
// ============================================================================

void handleCommand(String cmd) {
  cmd.toUpperCase();  // Case-insensitive commands

  if (cmd == "LIGHTS_ON") {
    lightsOn = true;
    currentBrightness = BRIGHTNESS_FULL;
    setLights(BRIGHTNESS_FULL);
    Serial.println("OK:LIGHTS_ON");

  } else if (cmd == "LIGHTS_OFF") {
    lightsOn = false;
    currentBrightness = BRIGHTNESS_OFF;
    setLights(BRIGHTNESS_OFF);
    Serial.println("OK:LIGHTS_OFF");

  } else if (cmd == "STATUS") {
    String status = lightsOn ? "ON" : "OFF";
    Serial.print("STATUS:");
    Serial.print(status);
    Serial.print(",BRIGHTNESS:");
    Serial.println(currentBrightness);

  } else if (cmd.startsWith("BRIGHTNESS:")) {
    // Optional: Set custom brightness level
    // Example: BRIGHTNESS:128
    int brightness = cmd.substring(11).toInt();
    if (brightness >= 0 && brightness <= 255) {
      currentBrightness = brightness;
      setLights(brightness);
      lightsOn = (brightness > 0);
      Serial.print("OK:BRIGHTNESS:");
      Serial.println(brightness);
    } else {
      Serial.println("ERROR:INVALID_BRIGHTNESS");
    }

  } else if (cmd == "PING") {
    // Connectivity test
    Serial.println("PONG");

  } else if (cmd == "VERSION") {
    Serial.println("NEXUS_LIGHT_V3.0");

  } else {
    Serial.print("ERROR:UNKNOWN_CMD:");
    Serial.println(cmd);
  }
}

// ============================================================================
// Light Control Functions
// ============================================================================

void setLights(uint8_t brightness) {
  // Set all light channels to the same brightness
  ledcWrite(PWM_CHANNEL_1, brightness);
  ledcWrite(PWM_CHANNEL_2, brightness);
  ledcWrite(PWM_CHANNEL_3, brightness);
  ledcWrite(PWM_CHANNEL_4, brightness);
}

void setLight(uint8_t channel, uint8_t brightness) {
  // Set individual light channel (if needed for debugging)
  if (channel >= 0 && channel <= 3) {
    ledcWrite(channel, brightness);
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

void blinkPattern(int times, int delayMs) {
  // Utility function for status indication
  for (int i = 0; i < times; i++) {
    setLights(BRIGHTNESS_FULL);
    delay(delayMs);
    setLights(BRIGHTNESS_OFF);
    delay(delayMs);
  }
}
