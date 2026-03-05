/*
 * NEXUS Light Controller v4.2
 * ESP32 — WS2812B Lightbox (5-channel NeoPixel)
 * Talks to DANIELSON via USB Serial @ 115200 baud
 *
 * ARCHITECTURE:
 *   Accepts BOTH JSON commands (from deployed DANIELSON server)
 *   and text commands (legacy/direct use). Drives WS2812B NeoPixel
 *   strips, NOT PWM (v4.0 incorrectly used PWM which can't drive WS2812B).
 *
 * Hardware (GPIO → WS2812B Data Pin):
 *   GPIO 12  → Channel 0 (Top)        ← NeoPixel data line
 *   GPIO 27  → Channel 1 (Left)       ← NeoPixel data line
 *   GPIO 26  → Channel 2 (Right)      ← NeoPixel data line
 *   GPIO 25  → Channel 3 (Bottom)     ← NeoPixel data line
 *   GPIO 33  → Channel 4 (Backlight)  ← NeoPixel data line
 *
 * !! Set LEDS_PER_CHANNEL to match your actual strip length !!
 *
 * JSON Commands (from DANIELSON server):
 *   {"cmd":"ping"}
 *   {"cmd":"all_on","brightness":255}
 *   {"cmd":"all_off"}
 *   {"cmd":"set_channel","channel":0,"value":255}     channel 0-4
 *   {"cmd":"set_all","values":[255,128,255,0,64]}
 *   {"cmd":"preset","name":"scan"}
 *   {"cmd":"rgb","channel":0,"r":255,"g":200,"b":180}
 *   {"cmd":"status"}
 *
 * Text Commands (legacy/direct):
 *   L1 / LIGHTS_ON, L0 / LIGHTS_OFF, STATUS
 *   CH:1:255, CH:ALL:200, B1:255
 *   RGB:1:255:200:180, RGB:ALL:255:200:180
 *   GRAD:1:R1:G1:B1:R2:G2:B2
 *   TEMP:6500
 *   PRESET:PHOTO / PRESET:SCAN / PRESET:GRADE / PRESET:OFF
 *
 * Patent Pending - Kevin Caracozza
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

// ─── Configuration ───────────────────────────────────────────────────────────
#define DEFAULT_LEDS      30      // Default LEDs per channel
#define MAX_LEDS          256     // Max supported per channel (covers up to 16x16 matrix)
#define LED_TYPE          NEO_GRB + NEO_KHZ800

// GPIO data pins (WS2812B)
#define PIN_CH0  12    // TOP
#define PIN_CH1  27    // LEFT
#define PIN_CH2  26    // RIGHT
#define PIN_CH3  25    // BOTTOM
#define PIN_CH4  33    // BACK

#define NUM_CHANNELS  5
#define CASE_LIGHT_CH 3   // GPIO 25 — always-on case light (never turns off)

int ledsPerChannel[NUM_CHANNELS] = {8, 80, 0, 1, 40};  // 12=ring(8), 27=matrix(80), 26=dead, 25=single(1), 33=matrix(40)
#define BAUD_RATE     115200

// ─── NeoPixel strips ────────────────────────────────────────────────────────
const int CH_PINS[NUM_CHANNELS] = {PIN_CH0, PIN_CH1, PIN_CH2, PIN_CH3, PIN_CH4};

Adafruit_NeoPixel strips[NUM_CHANNELS] = {
  Adafruit_NeoPixel(MAX_LEDS, PIN_CH0, LED_TYPE),
  Adafruit_NeoPixel(MAX_LEDS, PIN_CH1, LED_TYPE),
  Adafruit_NeoPixel(MAX_LEDS, PIN_CH2, LED_TYPE),
  Adafruit_NeoPixel(MAX_LEDS, PIN_CH3, LED_TYPE),
  Adafruit_NeoPixel(MAX_LEDS, PIN_CH4, LED_TYPE),
};

const char* CH_NAMES[NUM_CHANNELS] = { "RING_8", "MATRIX_80", "DEAD_26", "SINGLE_1", "MATRIX_40" };

// Current state per channel
struct ChState {
  uint8_t r, g, b, brightness;
} ch_state[NUM_CHANNELS];

// ─── Helpers ────────────────────────────────────────────────────────────────

// Map GPIO pin number to channel index (for backward compat with old server)
int pinToChannel(int pin) {
  for (int i = 0; i < NUM_CHANNELS; i++) {
    if (CH_PINS[i] == pin) return i;
  }
  return -1;
}

// Resolve channel reference: 0-4 = index, >=10 = GPIO pin
int resolveChannel(int ref) {
  if (ref >= 0 && ref < NUM_CHANNELS) return ref;
  return pinToChannel(ref);  // Try as GPIO pin
}

void tempToRGB(uint16_t kelvin, uint8_t *r, uint8_t *g, uint8_t *b) {
  kelvin = constrain(kelvin, 2700, 7500);
  float t = (kelvin - 2700.0f) / (7500.0f - 2700.0f);
  *r = (uint8_t)(255 - t * 50);
  *g = (uint8_t)(200 + t * 55);
  *b = (uint8_t)(t * 255);
}

// ─── Strip control ──────────────────────────────────────────────────────────

void setChannelColor(int ch, uint8_t r, uint8_t g, uint8_t b, uint8_t bright) {
  if (ch < 0 || ch >= NUM_CHANNELS) return;
  ch_state[ch] = {r, g, b, bright};

  float scale = bright / 255.0f;
  uint8_t sr = (uint8_t)(r * scale);
  uint8_t sg = (uint8_t)(g * scale);
  uint8_t sb = (uint8_t)(b * scale);

  uint32_t color = strips[ch].Color(sr, sg, sb);
  // Fill only up to ledsPerChannel, blank the rest
  for (int i = 0; i < MAX_LEDS; i++) {
    strips[ch].setPixelColor(i, i < ledsPerChannel[ch] ? color : 0);
  }
  strips[ch].show();
}

void setChannelBrightness(int ch, uint8_t bright) {
  if (ch < 0 || ch >= NUM_CHANNELS) return;
  setChannelColor(ch, ch_state[ch].r, ch_state[ch].g, ch_state[ch].b, bright);
}

void setAllColor(uint8_t r, uint8_t g, uint8_t b, uint8_t bright) {
  for (int i = 0; i < NUM_CHANNELS; i++) setChannelColor(i, r, g, b, bright);
}

void applyPreset(uint8_t r0, uint8_t g0, uint8_t b0, uint8_t brights[NUM_CHANNELS]) {
  for (int i = 0; i < NUM_CHANNELS; i++)
    setChannelColor(i, r0, g0, b0, brights[i]);
}

void setChannelGradient(int ch, uint8_t r1, uint8_t g1, uint8_t b1,
                        uint8_t r2, uint8_t g2, uint8_t b2) {
  if (ch < 0 || ch >= NUM_CHANNELS) return;
  ch_state[ch] = {r1, g1, b1, 255};
  int numLeds = ledsPerChannel[ch];
  strips[ch].clear();
  for (int i = 0; i < numLeds; i++) {
    float t = (float)i / max(numLeds - 1, 1);
    uint8_t r = r1 + (uint8_t)((r2 - r1) * t);
    uint8_t g = g1 + (uint8_t)((g2 - g1) * t);
    uint8_t b = b1 + (uint8_t)((b2 - b1) * t);
    strips[ch].setPixelColor(i, strips[ch].Color(r, g, b));
  }
  strips[ch].show();
}

// ─── Presets ────────────────────────────────────────────────────────────────

void presetPhoto() {
  uint8_t br[5] = {220, 200, 200, 180, 150};
  applyPreset(255, 220, 180, br);
}

void presetScan() {
  uint8_t br[5] = {255, 255, 255, 255, 0};
  applyPreset(220, 230, 255, br);
}

void presetGrade() {
  uint8_t br[5] = {160, 140, 140, 120, 80};
  applyPreset(255, 240, 220, br);
}

void presetOff() {
  for (int i = 0; i < NUM_CHANNELS; i++) {
    if (i == CASE_LIGHT_CH) continue;  // Never turn off case light
    strips[i].clear();
    strips[i].show();
    ch_state[i] = {255, 255, 255, 0};
  }
}

// ─── Status ─────────────────────────────────────────────────────────────────

void printStatusJSON() {
  JsonDocument doc;
  doc["status"] = "ok";
  JsonArray channels = doc["channels"].to<JsonArray>();
  for (int i = 0; i < NUM_CHANNELS; i++) {
    JsonObject ch = channels.add<JsonObject>();
    ch["name"] = CH_NAMES[i];
    ch["gpio"] = CH_PINS[i];
    ch["num_leds"] = ledsPerChannel[i];
    ch["brightness"] = ch_state[i].brightness;
    ch["r"] = ch_state[i].r;
    ch["g"] = ch_state[i].g;
    ch["b"] = ch_state[i].b;
  }
  serializeJson(doc, Serial);
  Serial.println();
}

void printStatusText() {
  Serial.print("STATUS:");
  for (int i = 0; i < NUM_CHANNELS; i++) {
    Serial.print(CH_NAMES[i]);
    Serial.print("=");
    Serial.print(ch_state[i].brightness);
    Serial.print("(");
    Serial.print(ch_state[i].r); Serial.print(",");
    Serial.print(ch_state[i].g); Serial.print(",");
    Serial.print(ch_state[i].b);
    Serial.print(")");
    if (i < NUM_CHANNELS - 1) Serial.print("|");
  }
  Serial.println();
}

// ─── JSON command handler ───────────────────────────────────────────────────

void handleJSON(String raw) {
  JsonDocument doc;
  if (deserializeJson(doc, raw)) {
    Serial.println("{\"status\":\"error\",\"msg\":\"bad_json\"}");
    return;
  }

  const char* cmd = doc["cmd"] | "";

  // PING
  if (strcmp(cmd, "ping") == 0) {
    Serial.println("{\"status\":\"pong\",\"device\":\"nexus_light_v4.2\"}");

  // ALL_ON — {"cmd":"all_on","brightness":255}
  } else if (strcmp(cmd, "all_on") == 0) {
    int bright = constrain(doc["brightness"] | 255, 0, 255);
    setAllColor(255, 255, 255, bright);
    Serial.println("{\"status\":\"ok\"}");

  // ALL_OFF
  } else if (strcmp(cmd, "all_off") == 0) {
    presetOff();
    Serial.println("{\"status\":\"ok\"}");

  // SET_CHANNEL — {"cmd":"set_channel","channel":0,"value":255}
  // channel can be 0-4 (index) or GPIO pin number (12,25,26,27,33)
  } else if (strcmp(cmd, "set_channel") == 0) {
    int chRef = doc["channel"] | -1;
    int val = constrain(doc["value"] | 0, 0, 255);
    int ch = resolveChannel(chRef);
    if (ch < 0) {
      Serial.println("{\"status\":\"error\",\"msg\":\"invalid_channel\"}");
    } else {
      setChannelBrightness(ch, val);
      Serial.println("{\"status\":\"ok\"}");
    }

  // SET_ALL — {"cmd":"set_all","values":[255,128,255,0,64]}
  } else if (strcmp(cmd, "set_all") == 0) {
    JsonArray vals = doc["values"].as<JsonArray>();
    for (int i = 0; i < NUM_CHANNELS && i < (int)vals.size(); i++) {
      setChannelBrightness(i, constrain((int)vals[i], 0, 255));
    }
    Serial.println("{\"status\":\"ok\"}");

  // PRESET — {"cmd":"preset","name":"scan"}
  } else if (strcmp(cmd, "preset") == 0) {
    const char* name = doc["name"] | "scan";
    if (strcmp(name, "photo") == 0) presetPhoto();
    else if (strcmp(name, "scan") == 0) presetScan();
    else if (strcmp(name, "grade") == 0) presetGrade();
    else if (strcmp(name, "off") == 0) presetOff();
    else { Serial.println("{\"status\":\"error\",\"msg\":\"unknown_preset\"}"); return; }
    Serial.println("{\"status\":\"ok\"}");

  // RGB — {"cmd":"rgb","channel":0,"r":255,"g":200,"b":180}
  } else if (strcmp(cmd, "rgb") == 0) {
    int chRef = doc["channel"] | -1;
    int ch = resolveChannel(chRef);
    int r = constrain(doc["r"] | 255, 0, 255);
    int g = constrain(doc["g"] | 255, 0, 255);
    int b = constrain(doc["b"] | 255, 0, 255);
    if (ch < 0) {
      Serial.println("{\"status\":\"error\",\"msg\":\"invalid_channel\"}");
    } else {
      setChannelColor(ch, r, g, b, 255);
      Serial.println("{\"status\":\"ok\"}");
    }

  // SET_LEDS — {"cmd":"set_leds","channel":4,"num_leds":8}
  // or set all: {"cmd":"set_leds","num_leds":30}
  } else if (strcmp(cmd, "set_leds") == 0) {
    int num = constrain(doc["num_leds"] | DEFAULT_LEDS, 1, MAX_LEDS);
    if (doc["channel"].isNull()) {
      // Set all channels
      for (int i = 0; i < NUM_CHANNELS; i++) {
        ledsPerChannel[i] = num;
        // buffer stays at MAX_LEDS, ledsPerChannel controls how many we light
        setChannelColor(i, ch_state[i].r, ch_state[i].g, ch_state[i].b, ch_state[i].brightness);
      }
      Serial.print("{\"status\":\"ok\",\"all_channels\":");
      Serial.print(num);
      Serial.println("}");
    } else {
      int chRef = doc["channel"] | -1;
      int ch = resolveChannel(chRef);
      if (ch < 0) {
        Serial.println("{\"status\":\"error\",\"msg\":\"invalid_channel\"}");
      } else {
        ledsPerChannel[ch] = num;
        // buffer stays at MAX_LEDS, ledsPerChannel controls how many we light
        setChannelColor(ch, ch_state[ch].r, ch_state[ch].g, ch_state[ch].b, ch_state[ch].brightness);
        Serial.print("{\"status\":\"ok\",\"channel\":");
        Serial.print(ch);
        Serial.print(",\"num_leds\":");
        Serial.print(num);
        Serial.println("}");
      }
    }

  // STATUS
  } else if (strcmp(cmd, "status") == 0) {
    printStatusJSON();

  } else {
    Serial.println("{\"status\":\"error\",\"msg\":\"unknown_cmd\"}");
  }
}

// ─── Text command handler ───────────────────────────────────────────────────

void handleText(String cmd) {
  String upper = cmd;
  upper.toUpperCase();

  if (upper == "L1" || upper == "LIGHTS_ON") {
    setAllColor(255, 255, 255, 255);
    Serial.println("OK LIGHTS_ON");

  } else if (upper == "L0" || upper == "LIGHTS_OFF") {
    presetOff();
    Serial.println("OK LIGHTS_OFF");

  } else if (upper == "STATUS") {
    printStatusText();

  } else if (upper.startsWith("PRESET:")) {
    String p = upper.substring(7);
    if      (p == "PHOTO") { presetPhoto(); Serial.println("OK PRESET:PHOTO"); }
    else if (p == "SCAN")  { presetScan();  Serial.println("OK PRESET:SCAN"); }
    else if (p == "GRADE") { presetGrade(); Serial.println("OK PRESET:GRADE"); }
    else if (p == "OFF")   { presetOff();   Serial.println("OK PRESET:OFF"); }
    else { Serial.println("ERR UNKNOWN_PRESET"); }

  } else if (upper.startsWith("TEMP:")) {
    uint16_t k = upper.substring(5).toInt();
    if (k < 2700 || k > 7500) { Serial.println("ERR BAD_TEMP"); return; }
    uint8_t r, g, b;
    tempToRGB(k, &r, &g, &b);
    setAllColor(r, g, b, 200);
    Serial.print("OK TEMP:"); Serial.println(k);

  } else if (upper.startsWith("GRAD:")) {
    String rest = upper.substring(5);
    int vals[7]; int pos = 0;
    for (int i = 0; i < 7; i++) {
      int colon = rest.indexOf(':', pos);
      if (i < 6 && colon < 0) { Serial.println("ERR BAD_FORMAT"); return; }
      vals[i] = (colon >= 0) ? rest.substring(pos, colon).toInt() : rest.substring(pos).toInt();
      pos = (colon >= 0) ? colon + 1 : rest.length();
    }
    int ch = vals[0] - 1;
    if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERR BAD_CHANNEL"); return; }
    setChannelGradient(ch, vals[1], vals[2], vals[3], vals[4], vals[5], vals[6]);
    Serial.print("OK GRAD:"); Serial.println(ch + 1);

  } else if (upper.startsWith("CH:")) {
    String rest = upper.substring(3);
    int c1 = rest.indexOf(':');
    if (c1 < 0) { Serial.println("ERR BAD_FORMAT"); return; }
    String chStr = rest.substring(0, c1);
    int val = constrain(rest.substring(c1 + 1).toInt(), 0, 255);
    if (chStr == "ALL") {
      for (int i = 0; i < NUM_CHANNELS; i++) setChannelBrightness(i, val);
      Serial.print("OK CH:ALL:"); Serial.println(val);
    } else {
      int ch = chStr.toInt() - 1;
      if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERR BAD_CHANNEL"); return; }
      setChannelBrightness(ch, val);
      Serial.print("OK CH:"); Serial.print(ch+1); Serial.print(":"); Serial.println(val);
    }

  } else if (upper.startsWith("B") && upper.length() >= 3 &&
             upper.charAt(1) >= '0' && upper.charAt(1) <= '9') {
    int colon = upper.indexOf(':');
    if (colon < 0) { Serial.println("ERR BAD_FORMAT"); return; }
    int ch = upper.substring(1, colon).toInt() - 1;
    int val = constrain(upper.substring(colon + 1).toInt(), 0, 255);
    if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERR BAD_CHANNEL"); return; }
    setChannelBrightness(ch, val);
    Serial.print("OK B"); Serial.print(ch+1); Serial.print(":"); Serial.println(val);

  } else if (upper.startsWith("RGB:")) {
    String rest = upper.substring(4);
    int idx[4]; int pos = 0;
    for (int i = 0; i < 4; i++) {
      idx[i] = rest.indexOf(':', pos);
      if (i < 3 && idx[i] < 0) { Serial.println("ERR BAD_FORMAT"); return; }
      pos = (idx[i] >= 0) ? idx[i] + 1 : rest.length();
    }
    String chStr = rest.substring(0, idx[0]);
    uint8_t r = rest.substring(idx[0]+1, idx[1]).toInt();
    uint8_t g = rest.substring(idx[1]+1, idx[2]).toInt();
    uint8_t b = rest.substring(idx[2]+1).toInt();
    if (chStr == "ALL") {
      setAllColor(r, g, b, 255);
      Serial.println("OK RGB:ALL");
    } else {
      int ch = chStr.toInt() - 1;
      if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERR BAD_CHANNEL"); return; }
      setChannelColor(ch, r, g, b, 255);
      Serial.print("OK RGB:"); Serial.println(ch+1);
    }

  } else {
    Serial.print("ERR UNKNOWN: "); Serial.println(cmd);
  }
}

// ─── Main command dispatcher ────────────────────────────────────────────────

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  // Route: starts with '{' = JSON, otherwise text
  if (cmd.charAt(0) == '{') {
    handleJSON(cmd);
  } else {
    handleText(cmd);
  }
}

// ─── Setup ──────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(BAUD_RATE);
  delay(300);

  for (int i = 0; i < NUM_CHANNELS; i++) {
    strips[i].begin();
    strips[i].clear();
    strips[i].show();
    ch_state[i] = {255, 255, 255, 0};
  }

  // Boot: case light always on (GPIO 25), ring on as boot indicator
  setChannelColor(CASE_LIGHT_CH, 255, 255, 255, 255);  // Case light — always on
  setChannelColor(0, 255, 255, 255, 255);               // Ring — boot indicator
  Serial.println("{\"status\":\"ready\",\"device\":\"nexus_light_v4.5\",\"channels\":\"12=8ring,27=80matrix,25=caselight,33=40matrix\",\"max_leds\":256}");
}

// ─── Loop ───────────────────────────────────────────────────────────────────

String inputBuf = "";

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuf.length() > 0) {
        handleCommand(inputBuf);
        inputBuf = "";
      }
    } else {
      inputBuf += c;
    }
  }
}
