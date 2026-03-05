/*
 * NEXUS LIGHTBOX CONTROLLER - ESP32 Firmware v2.0
 * =================================================
 * 5-channel WS2812B control with per-channel brightness and gradient.
 *
 * Hardware:
 *   Channel 0 → GPIO 27 — 80 LEDs
 *   Channel 1 → GPIO 26 — 80 LEDs
 *   Channel 2 → GPIO 25 — 80 LEDs
 *   Channel 3 → GPIO 33 — 80 LEDs
 *   Channel 4 → GPIO 32 — 80 LEDs
 *
 * Serial: 115200 baud, newline terminated
 *
 * Commands:
 *   L1                              All channels on (last color/brightness)
 *   L0                              All channels off
 *   B<0-255>                        Set ALL channels brightness
 *   B<ch>:<0-255>                   Set single channel brightness (ch 0-4)
 *   RGB:<ch>:<r>:<g>:<b>            Solid color on channel
 *   GRAD:<ch>:<r1>:<g1>:<b1>:<r2>:<g2>:<b2>   Gradient on channel (start→end color)
 *   PRESET:SCAN                     Scan mode — cool white, full brightness
 *   PRESET:PHOTO                    Photo mode — neutral white, reduced brightness
 *   PRESET:OFF                      All off
 *   STATUS                          JSON dump of all channel states
 *
 * Responses:
 *   OK:<detail>
 *   ERROR:<reason>
 */

#include <Adafruit_NeoPixel.h>

// ================================================================
// HARDWARE CONFIG
// ================================================================
#define NUM_CHANNELS    5
#define LEDS_PER_CH     80

const uint8_t CH_PINS[NUM_CHANNELS] = {27, 26, 25, 33, 32};

// ================================================================
// PRESETS
// ================================================================
// SCAN: cool white 6000K — max detail, high contrast
#define SCAN_R    200
#define SCAN_G    220
#define SCAN_B    255
#define SCAN_BRI  230

// PHOTO: neutral white 5000K — accurate color rendering
#define PHOTO_R   255
#define PHOTO_G   240
#define PHOTO_B   210
#define PHOTO_BRI 180

// ================================================================
// NEOPIXEL OBJECTS
// ================================================================
Adafruit_NeoPixel strips[NUM_CHANNELS] = {
  Adafruit_NeoPixel(LEDS_PER_CH, CH_PINS[0], NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(LEDS_PER_CH, CH_PINS[1], NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(LEDS_PER_CH, CH_PINS[2], NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(LEDS_PER_CH, CH_PINS[3], NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(LEDS_PER_CH, CH_PINS[4], NEO_GRB + NEO_KHZ800),
};

// ================================================================
// STATE
// ================================================================
struct ChannelState {
  uint8_t brightness;
  uint8_t r1, g1, b1;   // solid color OR gradient start
  uint8_t r2, g2, b2;   // gradient end (same as start if solid)
  bool gradient;
  bool on;
};

ChannelState chState[NUM_CHANNELS];

bool globalOn = false;
String inputBuffer = "";

// ================================================================
// SETUP
// ================================================================
void setup() {
  Serial.begin(115200);

  for (int i = 0; i < NUM_CHANNELS; i++) {
    strips[i].begin();
    strips[i].setBrightness(0);
    strips[i].clear();
    strips[i].show();

    chState[i] = {255, 255, 255, 255, 255, 255, 255, false, false};
  }

  // Boot flash — quick green pulse to confirm alive
  for (int i = 0; i < NUM_CHANNELS; i++) {
    strips[i].setBrightness(40);
    fillSolid(i, 0, 80, 0);
    strips[i].show();
  }
  delay(200);
  for (int i = 0; i < NUM_CHANNELS; i++) {
    strips[i].clear();
    strips[i].show();
  }

  Serial.println("OK:NEXUS_LIGHTS_V2_READY");
  inputBuffer.reserve(128);
}

// ================================================================
// MAIN LOOP
// ================================================================
void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }
}

// ================================================================
// COMMAND PARSER
// ================================================================
void processCommand(String cmd) {

  // ---- L1 — all on ----
  if (cmd == "L1") {
    globalOn = true;
    for (int i = 0; i < NUM_CHANNELS; i++) {
      chState[i].on = true;
      renderChannel(i);
    }
    Serial.println("OK:L1");
    return;
  }

  // ---- L0 — all off ----
  if (cmd == "L0") {
    globalOn = false;
    for (int i = 0; i < NUM_CHANNELS; i++) {
      chState[i].on = false;
      strips[i].setBrightness(0);
      strips[i].clear();
      strips[i].show();
    }
    Serial.println("OK:L0");
    return;
  }

  // ---- B<0-255> — all channels brightness ----
  // ---- B<ch>:<0-255> — single channel brightness ----
  if (cmd.startsWith("B")) {
    String rest = cmd.substring(1);
    int colon = rest.indexOf(':');

    if (colon < 0) {
      // Global brightness
      int val = constrain(rest.toInt(), 0, 255);
      for (int i = 0; i < NUM_CHANNELS; i++) {
        chState[i].brightness = val;
        if (chState[i].on) renderChannel(i);
      }
      Serial.print("OK:B_ALL="); Serial.println(val);
    } else {
      // Per-channel brightness
      int ch  = rest.substring(0, colon).toInt();
      int val = constrain(rest.substring(colon + 1).toInt(), 0, 255);
      if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERROR:CH_RANGE"); return; }
      chState[ch].brightness = val;
      if (chState[ch].on) renderChannel(ch);
      Serial.print("OK:B_CH"); Serial.print(ch); Serial.print("="); Serial.println(val);
    }
    return;
  }

  // ---- RGB:<ch>:<r>:<g>:<b> — solid color ----
  if (cmd.startsWith("RGB:")) {
    int vals[4];
    if (!parseColons(cmd.substring(4), vals, 4)) { Serial.println("ERROR:RGB_FORMAT"); return; }
    int ch = vals[0];
    if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERROR:CH_RANGE"); return; }

    chState[ch].r1 = constrain(vals[1], 0, 255);
    chState[ch].g1 = constrain(vals[2], 0, 255);
    chState[ch].b1 = constrain(vals[3], 0, 255);
    chState[ch].r2 = chState[ch].r1;
    chState[ch].g2 = chState[ch].g1;
    chState[ch].b2 = chState[ch].b1;
    chState[ch].gradient = false;
    chState[ch].on = true;
    renderChannel(ch);

    Serial.print("OK:RGB_CH"); Serial.print(ch);
    Serial.print("="); Serial.print(vals[1]); Serial.print(",");
    Serial.print(vals[2]); Serial.print(","); Serial.println(vals[3]);
    return;
  }

  // ---- GRAD:<ch>:<r1>:<g1>:<b1>:<r2>:<g2>:<b2> — gradient ----
  if (cmd.startsWith("GRAD:")) {
    int vals[7];
    if (!parseColons(cmd.substring(5), vals, 7)) { Serial.println("ERROR:GRAD_FORMAT"); return; }
    int ch = vals[0];
    if (ch < 0 || ch >= NUM_CHANNELS) { Serial.println("ERROR:CH_RANGE"); return; }

    chState[ch].r1 = constrain(vals[1], 0, 255);
    chState[ch].g1 = constrain(vals[2], 0, 255);
    chState[ch].b1 = constrain(vals[3], 0, 255);
    chState[ch].r2 = constrain(vals[4], 0, 255);
    chState[ch].g2 = constrain(vals[5], 0, 255);
    chState[ch].b2 = constrain(vals[6], 0, 255);
    chState[ch].gradient = true;
    chState[ch].on = true;
    renderChannel(ch);

    Serial.print("OK:GRAD_CH"); Serial.println(ch);
    return;
  }

  // ---- PRESET:SCAN ----
  if (cmd == "PRESET:SCAN") {
    applyPreset(SCAN_BRI, SCAN_R, SCAN_G, SCAN_B);
    Serial.println("OK:PRESET_SCAN");
    return;
  }

  // ---- PRESET:PHOTO ----
  if (cmd == "PRESET:PHOTO") {
    applyPreset(PHOTO_BRI, PHOTO_R, PHOTO_G, PHOTO_B);
    Serial.println("OK:PRESET_PHOTO");
    return;
  }

  // ---- PRESET:OFF ----
  if (cmd == "PRESET:OFF") {
    globalOn = false;
    for (int i = 0; i < NUM_CHANNELS; i++) {
      chState[i].on = false;
      strips[i].setBrightness(0);
      strips[i].clear();
      strips[i].show();
    }
    Serial.println("OK:PRESET_OFF");
    return;
  }

  // ---- STATUS ----
  if (cmd == "STATUS") {
    Serial.print("{\"global_on\":");
    Serial.print(globalOn ? "true" : "false");
    Serial.print(",\"channels\":[");
    for (int i = 0; i < NUM_CHANNELS; i++) {
      Serial.print("{\"ch\":");   Serial.print(i);
      Serial.print(",\"on\":");   Serial.print(chState[i].on ? "true" : "false");
      Serial.print(",\"bri\":");  Serial.print(chState[i].brightness);
      Serial.print(",\"r1\":");   Serial.print(chState[i].r1);
      Serial.print(",\"g1\":");   Serial.print(chState[i].g1);
      Serial.print(",\"b1\":");   Serial.print(chState[i].b1);
      Serial.print(",\"r2\":");   Serial.print(chState[i].r2);
      Serial.print(",\"g2\":");   Serial.print(chState[i].g2);
      Serial.print(",\"b2\":");   Serial.print(chState[i].b2);
      Serial.print(",\"grad\":"); Serial.print(chState[i].gradient ? "true" : "false");
      Serial.print("}");
      if (i < NUM_CHANNELS - 1) Serial.print(",");
    }
    Serial.println("]}");
    return;
  }

  Serial.print("ERROR:UNKNOWN_CMD:");
  Serial.println(cmd);
}

// ================================================================
// RENDER
// ================================================================
void renderChannel(int ch) {
  ChannelState& s = chState[ch];
  strips[ch].setBrightness(s.on ? s.brightness : 0);

  if (!s.on) {
    strips[ch].clear();
    strips[ch].show();
    return;
  }

  if (s.gradient) {
    fillGradient(ch, s.r1, s.g1, s.b1, s.r2, s.g2, s.b2);
  } else {
    fillSolid(ch, s.r1, s.g1, s.b1);
  }
  strips[ch].show();
}

void fillSolid(int ch, uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = strips[ch].Color(r, g, b);
  for (int i = 0; i < LEDS_PER_CH; i++) {
    strips[ch].setPixelColor(i, color);
  }
}

void fillGradient(int ch, uint8_t r1, uint8_t g1, uint8_t b1,
                          uint8_t r2, uint8_t g2, uint8_t b2) {
  for (int i = 0; i < LEDS_PER_CH; i++) {
    float t = (float)i / (LEDS_PER_CH - 1);
    uint8_t r = (uint8_t)(r1 + t * (r2 - r1));
    uint8_t g = (uint8_t)(g1 + t * (g2 - g1));
    uint8_t b = (uint8_t)(b1 + t * (b2 - b1));
    strips[ch].setPixelColor(i, strips[ch].Color(r, g, b));
  }
}

void applyPreset(uint8_t bri, uint8_t r, uint8_t g, uint8_t b) {
  globalOn = true;
  for (int i = 0; i < NUM_CHANNELS; i++) {
    chState[i].brightness = bri;
    chState[i].r1 = r; chState[i].g1 = g; chState[i].b1 = b;
    chState[i].r2 = r; chState[i].g2 = g; chState[i].b2 = b;
    chState[i].gradient = false;
    chState[i].on = true;
    renderChannel(i);
  }
}

// ================================================================
// UTILITY — parse N colon-separated integers from string
// ================================================================
bool parseColons(String s, int* out, int count) {
  int idx = 0;
  String remaining = s;
  for (int i = 0; i < count; i++) {
    int colon = remaining.indexOf(':');
    if (i < count - 1 && colon < 0) return false;
    out[i] = (colon >= 0) ? remaining.substring(0, colon).toInt()
                           : remaining.toInt();
    if (colon >= 0) remaining = remaining.substring(colon + 1);
    idx++;
  }
  return true;
}
