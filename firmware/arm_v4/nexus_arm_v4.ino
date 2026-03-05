/*
 * NEXUS Arm Controller v4.4
 * ESP32 #2 - Robotic Arm System
 *
 * v4.4 CHANGES:
 *   - Switched from FastLED to Adafruit NeoPixel library (matches LIGHT ESP32)
 *   - 80-LED NeoPixel ring on GPIO 27
 *     Ring layout: LED 0 = top (12 o'clock), numbering goes clockwise
 *     Zones (quadrants of 20 LEDs each):
 *       TOP    = LEDs 0-19   (12 to 3 o'clock)
 *       RIGHT  = LEDs 20-39  (3 to 6 o'clock)
 *       BOTTOM = LEDs 40-59  (6 to 9 o'clock)
 *       LEFT   = LEDs 60-79  (9 to 12 o'clock)
 *       HALF_TOP    = LEDs 60-79 + 0-19 (top half)
 *       HALF_BOTTOM = LEDs 20-59 (bottom half)
 *       ALL    = LEDs 0-79
 *     Commands: ring_zone, ring_pixel, ring_range, ring_gradient,
 *               ring_chase, ring_brightness, ring_test, ring_scan, ring_grade
 *
 * Pin Map:
 *   GPIO 32  -> Base stepper PUL+  (PUL- -> GND on TB6600, do NOT wire to ESP32)
 *   GPIO 33  -> Base stepper DIR+  (DIR- -> GND on TB6600, do NOT wire to ESP32)
 *   GPIO 27  -> 80x NeoPixel ring (WS2812B)
 *
 * PCA9685 (SDA GPIO 21 / SCL GPIO 22 / Addr 0x40):
 *   CH 0 -> Shoulder servo (MG995)   <- command channel 1
 *   CH 1 -> Elbow servo    (MG995)   <- command channel 2
 *   CH 2 -> Wrist servo 1  (MG90)    <- command channel 3
 *   CH 3 -> Wrist servo 2  (MG90)    <- command channel 4
 *   CH 4 -> Vacuum pump relay        <- command channel 5
 *   CH 5 -> Solenoid relay           <- command channel 6
 *
 * Libraries needed:
 *   ArduinoJson, Adafruit PWM Servo Driver, Adafruit NeoPixel
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// -- Stepper (SINGLE-ENDED — PUL- and DIR- hardwired to GND on TB6600) -------
#define STEPPER_PUL   32    // PUL+ only
#define STEPPER_DIR   33    // DIR+ only
#define STEPPER_MIN_DELAY_US 400

// -- NeoPixel Ring ------------------------------------------------------------
#define NEOPIXEL_PIN    27
#define NEOPIXEL_COUNT  80
#define NEOPIXEL_BRIGHTNESS 200
#define RING_QUADRANT   (NEOPIXEL_COUNT / 4)  // 20 LEDs per quadrant

Adafruit_NeoPixel ring(NEOPIXEL_COUNT, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

// Ring layout (clockwise from top):
//   TOP    = LEDs  0-19  (12 to 3 o'clock)
//   RIGHT  = LEDs 20-39  (3 to 6 o'clock)
//   BOTTOM = LEDs 40-59  (6 to 9 o'clock)
//   LEFT   = LEDs 60-79  (9 to 12 o'clock)

void fillRange(uint16_t start, uint16_t count, uint32_t color) {
  for (uint16_t i = 0; i < count; i++) {
    ring.setPixelColor((start + i) % NEOPIXEL_COUNT, color);
  }
}

void fillAll(uint32_t color) {
  for (uint16_t i = 0; i < NEOPIXEL_COUNT; i++) {
    ring.setPixelColor(i, color);
  }
}

void fillZone(const char* zone, uint32_t color) {
  if (strcmp(zone, "all") == 0) {
    fillAll(color);
  } else if (strcmp(zone, "top") == 0) {
    fillRange(0, RING_QUADRANT, color);
  } else if (strcmp(zone, "right") == 0) {
    fillRange(RING_QUADRANT, RING_QUADRANT, color);
  } else if (strcmp(zone, "bottom") == 0) {
    fillRange(RING_QUADRANT * 2, RING_QUADRANT, color);
  } else if (strcmp(zone, "left") == 0) {
    fillRange(RING_QUADRANT * 3, RING_QUADRANT, color);
  } else if (strcmp(zone, "half_top") == 0) {
    fillRange(RING_QUADRANT * 3, RING_QUADRANT * 2, color);  // left + top
  } else if (strcmp(zone, "half_bottom") == 0) {
    fillRange(RING_QUADRANT, RING_QUADRANT * 2, color);      // right + bottom
  }
}

// -- PCA9685 ------------------------------------------------------------------
Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(0x40);

#define SERVO_MIN  102
#define SERVO_MAX  512
#define RELAY_ON   0
#define RELAY_OFF  4096

// -- Serial -------------------------------------------------------------------
String inputBuffer = "";
bool emergencyStop = false;

// -- Helpers ------------------------------------------------------------------
uint16_t angleToPWM(int angle) {
  return map(constrain(angle, 0, 180), 0, 180, SERVO_MIN, SERVO_MAX);
}

void setServo(uint8_t ch, int angle) {
  pca.setPWM(ch - 1, 0, angleToPWM(angle));
}

void setRelay(uint8_t ch, bool on) {
  pca.setPWM(ch - 1, 0, on ? RELAY_ON : RELAY_OFF);
}

void stepperPulse(int steps, int dir, int delayUs) {
  digitalWrite(STEPPER_DIR, dir > 0 ? HIGH : LOW);
  delayMicroseconds(5);
  for (int i = 0; i < abs(steps); i++) {
    if (emergencyStop) break;
    digitalWrite(STEPPER_PUL, HIGH);
    delayMicroseconds(delayUs);
    digitalWrite(STEPPER_PUL, LOW);
    delayMicroseconds(delayUs);
  }
}

// -- Setup --------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  // 1. NeoPixel
  ring.begin();
  ring.setBrightness(NEOPIXEL_BRIGHTNESS);
  ring.clear();
  ring.show();

  // 2. Stepper pins (single-ended)
  pinMode(STEPPER_PUL, OUTPUT);
  pinMode(STEPPER_DIR, OUTPUT);
  digitalWrite(STEPPER_PUL, LOW);
  digitalWrite(STEPPER_DIR, LOW);

  // 3. PCA9685
  Wire.begin(21, 22);
  pca.begin();
  pca.setOscillatorFrequency(27000000);
  pca.setPWMFreq(50);
  delay(10);

  // Home all servos, relays off
  for (int i = 1; i <= 4; i++) setServo(i, 90);
  setRelay(5, false);
  setRelay(6, false);

  // Boot indicator — chase around the ring
  for (uint16_t i = 0; i < NEOPIXEL_COUNT; i++) {
    ring.setPixelColor(i, ring.Color(200, 200, 200));
    if (i % 4 == 0) ring.show();
  }
  ring.show();
  delay(300);
  ring.clear();
  ring.show();

  Serial.println("{\"status\":\"ready\",\"device\":\"nexus_arm_v4.4\",\"ring\":80}");
}

// -- Loop ---------------------------------------------------------------------
void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleCommand(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

// -- Commands -----------------------------------------------------------------
void handleCommand(String raw) {
  raw.trim();
  if (raw.length() == 0) return;

  JsonDocument doc;
  if (deserializeJson(doc, raw)) {
    Serial.println("{\"status\":\"error\",\"msg\":\"bad_json\"}");
    return;
  }

  const char* cmd = doc["cmd"] | "";

  // PING
  if (strcmp(cmd, "ping") == 0) {
    Serial.println("{\"status\":\"pong\",\"device\":\"nexus_arm_v4.4\",\"ring\":80}");

  // STOP
  } else if (strcmp(cmd, "stop") == 0) {
    emergencyStop = true;
    Serial.println("{\"status\":\"ok\",\"msg\":\"stopped\"}");

  // MOVE BASE — {"cmd":"move_base","steps":200,"dir":1,"speed":800}
  } else if (strcmp(cmd, "move_base") == 0) {
    emergencyStop = false;
    int steps = doc["steps"] | 0;
    int dir   = doc["dir"]   | 1;
    int speed = constrain(doc["speed"] | 800, STEPPER_MIN_DELAY_US, 10000);
    stepperPulse(steps, dir, speed);
    Serial.println("{\"status\":\"ok\"}");

  // SERVO — {"cmd":"servo","channel":1,"angle":90}
  } else if (strcmp(cmd, "servo") == 0) {
    int ch    = doc["channel"] | -1;
    int angle = doc["angle"]   | 90;
    if (ch < 1 || ch > 4) {
      Serial.println("{\"status\":\"error\",\"msg\":\"servo_channel_1_to_4\"}");
    } else {
      setServo(ch, angle);
      Serial.println("{\"status\":\"ok\"}");
    }

  // RELAY — {"cmd":"relay","channel":5,"state":1}
  } else if (strcmp(cmd, "relay") == 0) {
    int ch  = doc["channel"] | -1;
    bool on = doc["state"]   | 0;
    if (ch < 5 || ch > 6) {
      Serial.println("{\"status\":\"error\",\"msg\":\"relay_channel_5_or_6\"}");
    } else {
      setRelay(ch, on);
      Serial.println("{\"status\":\"ok\"}");
    }

  // -- LIGHTBOX (legacy, fills all) -------------------------------------------
  // {"cmd":"lightbox","r":255,"g":255,"b":255}
  } else if (strcmp(cmd, "lightbox") == 0) {
    int r = constrain(doc["r"] | 255, 0, 255);
    int g = constrain(doc["g"] | 255, 0, 255);
    int b = constrain(doc["b"] | 255, 0, 255);
    fillAll(ring.Color(r, g, b));
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // {"cmd":"lightbox_off"}
  } else if (strcmp(cmd, "lightbox_off") == 0) {
    ring.clear();
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // -- RING ZONE --------------------------------------------------------------
  // {"cmd":"ring_zone","zone":"top","r":255,"g":255,"b":255}
  // Zones: all, top, right, bottom, left, half_top, half_bottom
  // Optional "clear":true to black out everything else first
  } else if (strcmp(cmd, "ring_zone") == 0) {
    const char* zone = doc["zone"] | "all";
    int r = constrain(doc["r"] | 255, 0, 255);
    int g = constrain(doc["g"] | 255, 0, 255);
    int b = constrain(doc["b"] | 255, 0, 255);
    bool clear = doc["clear"] | false;
    if (clear) ring.clear();
    fillZone(zone, ring.Color(r, g, b));
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // -- RING PIXEL -------------------------------------------------------------
  // {"cmd":"ring_pixel","index":0,"r":255,"g":0,"b":0}
  } else if (strcmp(cmd, "ring_pixel") == 0) {
    int idx = constrain(doc["index"] | 0, 0, NEOPIXEL_COUNT - 1);
    int r = constrain(doc["r"] | 255, 0, 255);
    int g = constrain(doc["g"] | 255, 0, 255);
    int b = constrain(doc["b"] | 255, 0, 255);
    ring.setPixelColor(idx, ring.Color(r, g, b));
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // -- RING RANGE -------------------------------------------------------------
  // {"cmd":"ring_range","start":0,"count":20,"r":255,"g":255,"b":255}
  } else if (strcmp(cmd, "ring_range") == 0) {
    int start = constrain(doc["start"] | 0, 0, NEOPIXEL_COUNT - 1);
    int count = constrain(doc["count"] | 1, 1, NEOPIXEL_COUNT);
    int r = constrain(doc["r"] | 255, 0, 255);
    int g = constrain(doc["g"] | 255, 0, 255);
    int b = constrain(doc["b"] | 255, 0, 255);
    bool clear = doc["clear"] | false;
    if (clear) ring.clear();
    fillRange(start, count, ring.Color(r, g, b));
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // -- RING GRADIENT ----------------------------------------------------------
  // {"cmd":"ring_gradient","r1":255,"g1":0,"b1":0,"r2":0,"g2":0,"b2":255}
  } else if (strcmp(cmd, "ring_gradient") == 0) {
    int r1 = constrain(doc["r1"] | 255, 0, 255);
    int g1 = constrain(doc["g1"] | 255, 0, 255);
    int b1 = constrain(doc["b1"] | 255, 0, 255);
    int r2 = constrain(doc["r2"] | 0, 0, 255);
    int g2 = constrain(doc["g2"] | 0, 0, 255);
    int b2 = constrain(doc["b2"] | 0, 0, 255);
    for (uint16_t i = 0; i < NEOPIXEL_COUNT; i++) {
      uint8_t r = r1 + (int)(r2 - r1) * i / (NEOPIXEL_COUNT - 1);
      uint8_t g = g1 + (int)(g2 - g1) * i / (NEOPIXEL_COUNT - 1);
      uint8_t b = b1 + (int)(b2 - b1) * i / (NEOPIXEL_COUNT - 1);
      ring.setPixelColor(i, ring.Color(r, g, b));
    }
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // -- RING CHASE — animated spinner -----------------------------------------
  // {"cmd":"ring_chase","r":255,"g":255,"b":255,"tail":10,"laps":2,"speed":20}
  } else if (strcmp(cmd, "ring_chase") == 0) {
    int r = constrain(doc["r"] | 255, 0, 255);
    int g = constrain(doc["g"] | 255, 0, 255);
    int b = constrain(doc["b"] | 255, 0, 255);
    int tail = constrain(doc["tail"] | 10, 1, NEOPIXEL_COUNT);
    int laps = constrain(doc["laps"] | 2, 1, 10);
    int spd  = constrain(doc["speed"] | 20, 5, 200);
    for (int lap = 0; lap < laps; lap++) {
      for (uint16_t head = 0; head < NEOPIXEL_COUNT; head++) {
        ring.clear();
        for (int t = 0; t < tail; t++) {
          uint16_t idx = (head + NEOPIXEL_COUNT - t) % NEOPIXEL_COUNT;
          uint8_t fade = 255 - (255 * t / tail);
          ring.setPixelColor(idx, ring.Color(r * fade / 255, g * fade / 255, b * fade / 255));
        }
        ring.show();
        delay(spd);
      }
    }
    ring.clear();
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // -- RING BRIGHTNESS --------------------------------------------------------
  // {"cmd":"ring_brightness","value":200}
  } else if (strcmp(cmd, "ring_brightness") == 0) {
    int val = constrain(doc["value"] | 200, 0, 255);
    ring.setBrightness(val);
    ring.show();
    Serial.println("{\"status\":\"ok\"}");

  // -- RING TEST — lights each quadrant sequentially --------------------------
  // {"cmd":"ring_test"}
  } else if (strcmp(cmd, "ring_test") == 0) {
    Serial.println("{\"status\":\"ok\",\"msg\":\"ring_test_start\"}");
    const char* zones[] = {"top", "right", "bottom", "left", "half_top", "half_bottom", "all"};
    for (int i = 0; i < 7; i++) {
      ring.clear();
      fillZone(zones[i], ring.Color(200, 200, 200));
      ring.show();
      delay(600);
      JsonDocument resp;
      resp["zone"] = zones[i];
      serializeJson(resp, Serial);
      Serial.println();
    }
    ring.clear();
    ring.show();
    Serial.println("{\"status\":\"ok\",\"msg\":\"ring_test_done\"}");

  // -- SCAN PRESET — full white ring for even card illumination ---------------
  // {"cmd":"ring_scan"}
  } else if (strcmp(cmd, "ring_scan") == 0) {
    fillAll(ring.Color(255, 255, 255));
    ring.setBrightness(NEOPIXEL_BRIGHTNESS);
    ring.show();
    Serial.println("{\"status\":\"ok\",\"msg\":\"scan_mode\"}");

  // -- GRADE PRESET — alternating for surface detail --------------------------
  // {"cmd":"ring_grade"}
  } else if (strcmp(cmd, "ring_grade") == 0) {
    for (uint16_t i = 0; i < NEOPIXEL_COUNT; i++) {
      ring.setPixelColor(i, (i % 2 == 0) ? ring.Color(255, 255, 255) : 0);
    }
    ring.setBrightness(NEOPIXEL_BRIGHTNESS);
    ring.show();
    Serial.println("{\"status\":\"ok\",\"msg\":\"grade_mode\"}");

  // HOME
  } else if (strcmp(cmd, "home") == 0) {
    emergencyStop = false;
    for (int i = 1; i <= 4; i++) setServo(i, 90);
    setRelay(5, false);
    setRelay(6, false);
    fillAll(ring.Color(200, 200, 200));
    ring.show();
    Serial.println("{\"status\":\"ok\",\"msg\":\"homed\"}");

  // PCA_TEST
  } else if (strcmp(cmd, "pca_test") == 0) {
    Serial.println("{\"status\":\"ok\",\"msg\":\"pca_test_start\"}");
    for (int ch = 0; ch < 6; ch++) {
      pca.setPWM(ch, 0, 307);
      delay(800);
      pca.setPWM(ch, 0, 0);
      delay(200);
      JsonDocument resp;
      resp["pca_ch"] = ch;
      resp["pulse"]  = 307;
      serializeJson(resp, Serial);
      Serial.println();
    }
    Serial.println("{\"status\":\"ok\",\"msg\":\"pca_test_done\"}");

  // PCA_RAW
  } else if (strcmp(cmd, "pca_raw") == 0) {
    int ch  = constrain(doc["channel"] | 0, 0, 15);
    int val = constrain(doc["value"]   | 0, 0, 4096);
    pca.setPWM(ch, 0, val);
    JsonDocument resp;
    resp["status"]  = "ok";
    resp["pca_ch"]  = ch;
    resp["value"]   = val;
    serializeJson(resp, Serial);
    Serial.println();

  // STEPPER_TEST
  } else if (strcmp(cmd, "stepper_test") == 0) {
    Serial.println("{\"status\":\"ok\",\"msg\":\"stepping_fwd_100\"}");
    stepperPulse(100, 1, 1000);
    delay(500);
    Serial.println("{\"status\":\"ok\",\"msg\":\"stepping_rev_100\"}");
    stepperPulse(100, -1, 1000);
    Serial.println("{\"status\":\"ok\",\"msg\":\"stepper_test_done\"}");

  } else {
    Serial.println("{\"status\":\"error\",\"msg\":\"unknown_cmd\"}");
  }
}
