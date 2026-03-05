/*
 * NEXUS Robo V3 - Lightbox WS2812B LED Controller
 * =================================================
 * Controls 5 independent WS2812B NeoPixel channels for photography lighting.
 * Communicates via USB Serial (115200 baud) with SNARF.
 *
 * Hardware (GPIO → WS2812B Data Pin):
 *   GPIO 12  → Channel 1 (Top)
 *   GPIO 27  → Channel 2 (Left)
 *   GPIO 26  → Channel 3 (Right)
 *   GPIO 25  → Channel 4 (Bottom / Fill)
 *   GPIO 33  → Channel 5 (Backlight / Diffuse)
 *
 * !! Set LEDS_PER_CHANNEL to match your actual strip length !!
 *
 * Serial Commands (115200 baud, newline terminated):
 *   LIGHTS_ON              - All channels full white
 *   LIGHTS_OFF             - All channels off
 *   STATUS                 - Report current brightness per channel
 *   CH:1:255               - Set channel 1 brightness 0-255 (white)
 *   CH:ALL:200             - Set all channels to brightness 200
 *   RGB:1:255:200:180      - Set channel 1 to specific R,G,B
 *   RGB:ALL:255:200:180    - Set all channels to specific R,G,B
 *   TEMP:6500              - Set color temperature in Kelvin (2700-7500)
 *   PRESET:PHOTO           - Photography mode (warm white, balanced)
 *   PRESET:SCAN            - Scan mode (cool white, maximum flat light)
 *   PRESET:GRADE           - Grading mode (daylight, low glare)
 *   PRESET:OFF             - All off
 *
 * Patent Pending - Kevin Caracozza
 */

#include <Adafruit_NeoPixel.h>

// ─── Configuration — SET THESE TO MATCH YOUR HARDWARE ────────────────────────
#define LEDS_PER_CHANNEL  30      // ← Change to actual LEDs per strip
#define LED_TYPE          NEO_GRB + NEO_KHZ800

// GPIO data pins
#define PIN_CH1  12
#define PIN_CH2  27
#define PIN_CH3  26
#define PIN_CH4  25
#define PIN_CH5  33

#define NUM_CHANNELS  5
#define BAUD_RATE     115200

// ─── NeoPixel strips ──────────────────────────────────────────────────────────
Adafruit_NeoPixel strips[NUM_CHANNELS] = {
  Adafruit_NeoPixel(LEDS_PER_CHANNEL, PIN_CH1, LED_TYPE),
  Adafruit_NeoPixel(LEDS_PER_CHANNEL, PIN_CH2, LED_TYPE),
  Adafruit_NeoPixel(LEDS_PER_CHANNEL, PIN_CH3, LED_TYPE),
  Adafruit_NeoPixel(LEDS_PER_CHANNEL, PIN_CH4, LED_TYPE),
  Adafruit_NeoPixel(LEDS_PER_CHANNEL, PIN_CH5, LED_TYPE),
};

const char* CH_NAMES[NUM_CHANNELS] = { "TOP", "LEFT", "RIGHT", "BOTTOM", "BACK" };

// Current state per channel
struct ChState {
  uint8_t r, g, b, brightness;  // 0-255
} ch_state[NUM_CHANNELS];

// ─── Color temperature → RGB (simplified) ────────────────────────────────────
void tempToRGB(uint16_t kelvin, uint8_t *r, uint8_t *g, uint8_t *b) {
  // Simplified Kelvin to RGB, tuned for 2700K–7500K
  kelvin = constrain(kelvin, 2700, 7500);
  float t = (kelvin - 2700.0f) / (7500.0f - 2700.0f);  // 0=warm, 1=cool

  *r = (uint8_t)(255 - t * 50);          // Red drops slightly as temp rises
  *g = (uint8_t)(200 + t * 55);          // Green rises a bit
  *b = (uint8_t)(t * 255);               // Blue rises strongly
}

// ─── Strip helpers ────────────────────────────────────────────────────────────
void setChannelColor(int ch, uint8_t r, uint8_t g, uint8_t b, uint8_t bright) {
  if (ch < 0 || ch >= NUM_CHANNELS) return;
  ch_state[ch] = {r, g, b, bright};

  float scale = bright / 255.0f;
  uint8_t sr = (uint8_t)(r * scale);
  uint8_t sg = (uint8_t)(g * scale);
  uint8_t sb = (uint8_t)(b * scale);

  strips[ch].fill(strips[ch].Color(sr, sg, sb));
  strips[ch].show();
}

void setChannelBrightness(int ch, uint8_t bright) {
  if (ch < 0 || ch >= NUM_CHANNELS) return;
  setChannelColor(ch, ch_state[ch].r, ch_state[ch].g, ch_state[ch].b, bright);
}

void setAllColor(uint8_t r, uint8_t g, uint8_t b, uint8_t bright) {
  for (int i = 0; i < NUM_CHANNELS; i++) setChannelColor(i, r, g, b, bright);
}

void applyPresetValues(uint8_t r0, uint8_t g0, uint8_t b0,
                       uint8_t brights[NUM_CHANNELS]) {
  for (int i = 0; i < NUM_CHANNELS; i++)
    setChannelColor(i, r0, g0, b0, brights[i]);
}

// ─── Presets ─────────────────────────────────────────────────────────────────
void presetPhoto() {
  // Warm white (4000K), balanced
  uint8_t br[5] = {220, 200, 200, 180, 150};
  applyPresetValues(255, 220, 180, br);
}

void presetScan() {
  // Cool white (6500K), flat maximum, no backlight
  uint8_t br[5] = {255, 255, 255, 255, 0};
  applyPresetValues(220, 230, 255, br);
}

void presetGrade() {
  // Daylight (5500K), lower intensity for accurate color
  uint8_t br[5] = {160, 140, 140, 120, 80};
  applyPresetValues(255, 240, 220, br);
}

void presetOff() {
  for (int i = 0; i < NUM_CHANNELS; i++) {
    strips[i].clear();
    strips[i].show();
    ch_state[i] = {255, 255, 255, 0};
  }
}

// ─── Status report ────────────────────────────────────────────────────────────
void printStatus() {
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

// ─── Command parser ───────────────────────────────────────────────────────────
void handleCommand(String cmd) {
  cmd.trim();

  String upper = cmd;
  upper.toUpperCase();

  if (upper == "LIGHTS_ON") {
    setAllColor(255, 255, 255, 255);
    Serial.println("OK LIGHTS_ON");

  } else if (upper == "LIGHTS_OFF") {
    presetOff();
    Serial.println("OK LIGHTS_OFF");

  } else if (upper == "STATUS") {
    printStatus();

  } else if (upper.startsWith("PRESET:")) {
    String p = upper.substring(7);
    if      (p == "PHOTO") { presetPhoto(); Serial.println("OK PRESET:PHOTO"); }
    else if (p == "SCAN")  { presetScan();  Serial.println("OK PRESET:SCAN"); }
    else if (p == "GRADE") { presetGrade(); Serial.println("OK PRESET:GRADE"); }
    else if (p == "OFF")   { presetOff();   Serial.println("OK PRESET:OFF"); }
    else                   { Serial.println("ERR UNKNOWN_PRESET"); }

  } else if (upper.startsWith("TEMP:")) {
    uint16_t k = upper.substring(5).toInt();
    if (k < 2700 || k > 7500) { Serial.println("ERR BAD_TEMP (2700-7500)"); return; }
    uint8_t r, g, b;
    tempToRGB(k, &r, &g, &b);
    setAllColor(r, g, b, 200);
    Serial.print("OK TEMP:"); Serial.println(k);

  } else if (upper.startsWith("CH:")) {
    // CH:N:VAL  or  CH:ALL:VAL
    String rest = upper.substring(3);
    int c1 = rest.indexOf(':');
    if (c1 < 0) { Serial.println("ERR BAD_FORMAT"); return; }
    String chStr  = rest.substring(0, c1);
    int val = rest.substring(c1 + 1).toInt();
    val = constrain(val, 0, 255);

    if (chStr == "ALL") {
      for (int i = 0; i < NUM_CHANNELS; i++) setChannelBrightness(i, val);
      Serial.print("OK CH:ALL:"); Serial.println(val);
    } else {
      int ch = chStr.toInt() - 1;
      if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERR BAD_CHANNEL"); return; }
      setChannelBrightness(ch, val);
      Serial.print("OK CH:"); Serial.print(ch+1); Serial.print(":"); Serial.println(val);
    }

  } else if (upper.startsWith("RGB:")) {
    // RGB:N:R:G:B  or  RGB:ALL:R:G:B
    String rest = upper.substring(4);
    // Parse 4 colon-separated fields
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

  } else if (cmd.length() > 0) {
    Serial.print("ERR UNKNOWN: "); Serial.println(cmd);
  }
}

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);
  delay(300);

  for (int i = 0; i < NUM_CHANNELS; i++) {
    strips[i].begin();
    strips[i].clear();
    strips[i].show();
    ch_state[i] = {255, 255, 255, 0};
  }

  // Startup flash to confirm firmware alive
  setAllColor(0, 80, 255, 60);
  delay(300);
  presetOff();

  Serial.println("NEXUS-LIGHTBOX-V3 READY");
  Serial.println("WS2812B | GPIOs: 12(TOP) 27(LEFT) 26(RIGHT) 25(BOTTOM) 33(BACK)");
  Serial.println("LEDS_PER_CHANNEL: " + String(LEDS_PER_CHANNEL));
}

// ─── Loop ────────────────────────────────────────────────────────────────────
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
