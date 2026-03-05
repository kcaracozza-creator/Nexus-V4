/*
 * NEXUS V2 — Top Lights Controller (Pro Micro / ATmega32U4)
 * 6-channel NeoPixel controller for scanner canopy LEDs
 * v3.0 — New canopy layout (2026-03-03)
 *
 * Serial Protocol (115200 baud, newline-terminated):
 *   ON              — All channels on (white at current brightness)
 *   OFF             — All channels off
 *   B:128           — Set global brightness (0-255)
 *   C:1:255:200:180 — Set channel 1 to R=255 G=200 B=180
 *   A:255:200:180   — Set ALL channels to R G B
 *   P:SCAN          — Preset (SCAN=200, PHOTO=255, GRADE=180, OFF=0)
 *   S               — Status report (JSON)
 *   T               — Test sequence (chase each channel)
 *
 * Pin Map:
 *   CH1=pin3  (24 LEDs)   CH4=pin6  (16 LEDs)
 *   CH2=pin4  ( 1 LED)    CH5=pin8  (24 LEDs)
 *   CH3=pin5  ( 8 LEDs)   CH6=pin16 (24 LEDs)
 *
 * No case light — all 6 channels behave identically.
 */

#include <Adafruit_NeoPixel.h>

#define NUM_CHANNELS 6
#define SERIAL_BAUD  115200
#define MAX_CMD_LEN  64
// No case light — all channels behave identically

// Pin and LED count definitions
const uint8_t  ch_pin[NUM_CHANNELS]  = {  3,  4,  5,  6,  8, 16 };
const uint16_t ch_leds[NUM_CHANNELS] = { 24,  1,  8, 16, 24, 24 };

// NeoPixel strips
Adafruit_NeoPixel strips[NUM_CHANNELS] = {
  Adafruit_NeoPixel(24, 3,  NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel( 1, 4,  NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel( 8, 5,  NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(16, 6,  NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(24, 8,  NEO_GRB + NEO_KHZ800),
  Adafruit_NeoPixel(24, 16, NEO_GRB + NEO_KHZ800),
};

// State
uint8_t global_brightness = 128;  // safe default (not full blast)
uint8_t ch_r[NUM_CHANNELS];
uint8_t ch_g[NUM_CHANNELS];
uint8_t ch_b[NUM_CHANNELS];
bool    ch_on[NUM_CHANNELS];

// Serial buffer
char cmd_buf[MAX_CMD_LEN];
uint8_t cmd_pos = 0;

// ─── Helpers ───────────────────────────────────────────────────────

void set_channel(uint8_t ch, uint8_t r, uint8_t g, uint8_t b) {
  if (ch >= NUM_CHANNELS) return;
  ch_r[ch] = r;
  ch_g[ch] = g;
  ch_b[ch] = b;
  ch_on[ch] = true;
  strips[ch].setBrightness(global_brightness);
  for (uint16_t i = 0; i < ch_leds[ch]; i++) {
    strips[ch].setPixelColor(i, strips[ch].Color(r, g, b));
  }
  strips[ch].show();
}

void clear_channel(uint8_t ch) {
  if (ch >= NUM_CHANNELS) return;
  ch_on[ch] = false;
  strips[ch].clear();
  strips[ch].show();
}

void all_on(uint8_t r, uint8_t g, uint8_t b) {
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    set_channel(i, r, g, b);
  }
}

void all_off() {
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    clear_channel(i);
  }
}

void send_status() {
  Serial.print("{\"device\":\"pro_micro_toplights\",\"version\":\"3.0\",\"brightness\":");
  Serial.print(global_brightness);
  Serial.print(",\"channels\":[");
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    if (i > 0) Serial.print(",");
    Serial.print("{\"ch\":");
    Serial.print(i + 1);
    Serial.print(",\"pin\":");
    Serial.print(ch_pin[i]);
    Serial.print(",\"leds\":");
    Serial.print(ch_leds[i]);
    Serial.print(",\"on\":");
    Serial.print(ch_on[i] ? "true" : "false");
    Serial.print(",\"r\":");
    Serial.print(ch_r[i]);
    Serial.print(",\"g\":");
    Serial.print(ch_g[i]);
    Serial.print(",\"b\":");
    Serial.print(ch_b[i]);
    Serial.print("}");
  }
  Serial.println("]}");
}

void test_sequence() {
  Serial.println("{\"status\":\"testing\"}");
  // Light each channel one at a time
  all_off();
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    set_channel(i, 0, 255, 0);  // green
    delay(300);
    clear_channel(i);
  }
  // Flash all white
  all_on(255, 255, 255);
  delay(500);
  Serial.println("{\"status\":\"test_complete\"}");
}

// Parse integer from string at position, advance pos past delimiter
int parse_int(const char* str, uint8_t* pos) {
  int val = 0;
  while (str[*pos] >= '0' && str[*pos] <= '9') {
    val = val * 10 + (str[*pos] - '0');
    (*pos)++;
  }
  if (str[*pos] == ':') (*pos)++;  // skip delimiter
  return val;
}

// ─── Command Handler ───────────────────────────────────────────────

void handle_command(const char* cmd) {
  // ON — all channels white
  if (strcmp(cmd, "ON") == 0) {
    all_on(255, 255, 255);
    Serial.println("{\"ok\":true,\"cmd\":\"on\"}");
    return;
  }

  // OFF — all channels off (case light stays)
  if (strcmp(cmd, "OFF") == 0) {
    all_off();
    Serial.println("{\"ok\":true,\"cmd\":\"off\"}");
    return;
  }

  // S — status
  if (strcmp(cmd, "S") == 0) {
    send_status();
    return;
  }

  // T — test
  if (strcmp(cmd, "T") == 0) {
    test_sequence();
    return;
  }

  // B:N — brightness
  if (cmd[0] == 'B' && cmd[1] == ':') {
    uint8_t pos = 2;
    int bval = parse_int(cmd, &pos);
    global_brightness = constrain(bval, 0, 255);
    // Re-apply brightness to all active channels
    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
      if (ch_on[i]) {
        strips[i].setBrightness(global_brightness);
        strips[i].show();
      }
    }
    Serial.print("{\"ok\":true,\"cmd\":\"brightness\",\"value\":");
    Serial.print(global_brightness);
    Serial.println("}");
    return;
  }

  // C:CH:R:G:B — set single channel
  if (cmd[0] == 'C' && cmd[1] == ':') {
    uint8_t pos = 2;
    int ch = parse_int(cmd, &pos) - 1;  // 1-indexed to 0-indexed
    int r  = parse_int(cmd, &pos);
    int g  = parse_int(cmd, &pos);
    int b  = parse_int(cmd, &pos);
    if (ch >= 0 && ch < NUM_CHANNELS) {
      set_channel(ch, constrain(r, 0, 255), constrain(g, 0, 255), constrain(b, 0, 255));
      Serial.print("{\"ok\":true,\"cmd\":\"channel\",\"ch\":");
      Serial.print(ch + 1);
      Serial.println("}");
    } else {
      Serial.println("{\"ok\":false,\"error\":\"bad channel\"}");
    }
    return;
  }

  // A:R:G:B — set all channels
  if (cmd[0] == 'A' && cmd[1] == ':') {
    uint8_t pos = 2;
    int r = parse_int(cmd, &pos);
    int g = parse_int(cmd, &pos);
    int b = parse_int(cmd, &pos);
    all_on(constrain(r, 0, 255), constrain(g, 0, 255), constrain(b, 0, 255));
    Serial.println("{\"ok\":true,\"cmd\":\"all_rgb\"}");
    return;
  }

  // P:PRESET — named preset
  if (cmd[0] == 'P' && cmd[1] == ':') {
    const char* preset = cmd + 2;
    if (strcmp(preset, "SCAN") == 0) {
      global_brightness = 200;
      all_on(255, 255, 255);
    } else if (strcmp(preset, "PHOTO") == 0) {
      global_brightness = 255;
      all_on(255, 255, 255);
    } else if (strcmp(preset, "GRADE") == 0) {
      global_brightness = 180;
      all_on(255, 250, 240);  // warm white for grading
    } else if (strcmp(preset, "OFF") == 0) {
      all_off();
    } else {
      Serial.println("{\"ok\":false,\"error\":\"unknown preset\"}");
      return;
    }
    Serial.print("{\"ok\":true,\"cmd\":\"preset\",\"name\":\"");
    Serial.print(preset);
    Serial.println("\"}");
    return;
  }

  Serial.println("{\"ok\":false,\"error\":\"unknown command\"}");
}

// ─── Setup & Loop ──────────────────────────────────────────────────

void setup() {
  Serial.begin(SERIAL_BAUD);

  // Initialize all strips
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    strips[i].begin();
    strips[i].setBrightness(global_brightness);
    strips[i].clear();
    strips[i].show();
    ch_r[i] = 0;
    ch_g[i] = 0;
    ch_b[i] = 0;
    ch_on[i] = false;
  }

  // Startup indicator — brief flash on CH1 so you know it booted
  set_channel(0, 0, 128, 0);  // green on ring1
  delay(500);
  clear_channel(0);

  Serial.println("{\"device\":\"pro_micro_toplights\",\"version\":\"3.0\",\"status\":\"ready\"}");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmd_pos > 0) {
        cmd_buf[cmd_pos] = '\0';
        handle_command(cmd_buf);
        cmd_pos = 0;
      }
    } else if (cmd_pos < MAX_CMD_LEN - 1) {
      cmd_buf[cmd_pos++] = c;
    }
  }
}
