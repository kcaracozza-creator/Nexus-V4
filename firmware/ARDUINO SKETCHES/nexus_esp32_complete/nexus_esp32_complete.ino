/*
 * NEXUS Card Scanner - Complete ESP32 Controller
 * Controls: NeoPixel Lighting + XY Stepper Motors + HTTP API
 * 
 * Hardware:
 * - ESP32 DevKit
 * - 2x NeoPixel Ring (16 LEDs each)
 * - 2x NEMA 17 Stepper Motors
 * - 2x A4988/DRV8825 Stepper Drivers
 * - 2x Mechanical Limit Switches (normally open)
 * - ATX Power Supply
 * 
 * Connections:
 * ┌─────────────────────────────────────────────────────┐
 * │ LIGHTING                                            │
 * ├─────────────────────────────────────────────────────┤
 * │ Ring 1 Data    → GPIO 16                            │
 * │ Ring 2 Data    → GPIO 17                            │
 * │ Both Rings 5V  → ATX +5V                            │
 * │ Both Rings GND → Common GND                         │
 * └─────────────────────────────────────────────────────┘
 * 
 * ┌─────────────────────────────────────────────────────┐
 * │ XY STEPPERS                                         │
 * ├─────────────────────────────────────────────────────┤
 * │ X-Axis STEP    → GPIO 18                            │
 * │ X-Axis DIR     → GPIO 19                            │
 * │ X-Axis ENABLE  → GPIO 5 (optional)                  │
 * │ Y-Axis STEP    → GPIO 21                            │
 * │ Y-Axis DIR     → GPIO 22                            │
 * │ Y-Axis ENABLE  → GPIO 23 (optional)                 │
 * │ Drivers VIN    → ATX +12V                           │
 * │ Drivers GND    → Common GND                         │
 * └─────────────────────────────────────────────────────┘
 * 
 * ┌─────────────────────────────────────────────────────┐
 * │ LIMIT SWITCHES (Homing)                             │
 * ├─────────────────────────────────────────────────────┤
 * │ X-Limit COM    → GPIO 25 (internal pullup)          │
 * │ X-Limit NO     → GND                                │
 * │ Y-Limit COM    → GPIO 26 (internal pullup)          │
 * │ Y-Limit NO     → GND                                │
 * └─────────────────────────────────────────────────────┘
 * 
 * HTTP Commands:
 * - http://ESP32_IP/lights?cmd=ON
 * - http://ESP32_IP/lights?cmd=TEMP:5000
 * - http://ESP32_IP/move?x=100&y=150
 * - http://ESP32_IP/home
 * - http://ESP32_IP/status
 */

#include <Adafruit_NeoPixel.h>
#include <WiFi.h>
#include <WebServer.h>
#include <AccelStepper.h>

// ========== WiFi Configuration ==========
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

WebServer server(80);

// ========== NeoPixel Configuration ==========
#define RING1_PIN 16
#define RING2_PIN 17
#define LEDS_PER_RING 16

Adafruit_NeoPixel ring1(LEDS_PER_RING, RING1_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel ring2(LEDS_PER_RING, RING2_PIN, NEO_GRB + NEO_KHZ800);

bool lightsOn = false;
uint8_t brightness = 200;
uint8_t red = 255, green = 255, blue = 255;
uint16_t colorTemp = 5000;

// ========== Stepper Configuration ==========
#define X_STEP_PIN 18
#define X_DIR_PIN 19
#define X_ENABLE_PIN 5
#define Y_STEP_PIN 21
#define Y_DIR_PIN 22
#define Y_ENABLE_PIN 23

// Limit switches (normally open, active LOW with pullup)
#define X_LIMIT_PIN 25
#define Y_LIMIT_PIN 26

// XY Motion specs (from your scanner design)
#define STEPS_PER_REV 200          // NEMA 17 typical
#define MICROSTEPS 16              // A4988 microstep setting
#define LEAD_SCREW_PITCH 8.0       // T8 lead screw (8mm per revolution)
#define STEPS_PER_MM ((STEPS_PER_REV * MICROSTEPS) / LEAD_SCREW_PITCH)  // 400 steps/mm

// Motion parameters
#define MAX_SPEED 2000             // steps/sec (50mm/s @ 400 steps/mm = 20,000)
#define ACCELERATION 1000          // steps/sec² 
#define HOMING_SPEED 800           // steps/sec (10mm/s)
#define BED_SIZE_X 380.0           // mm (from xy_scanner_controller.py)
#define BED_SIZE_Y 380.0           // mm

// Create stepper objects
AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);

// Current position (in mm)
float currentX = 0.0;
float currentY = 0.0;
bool isHomed = false;

String inputString = "";
boolean stringComplete = false;

void setup() {
  Serial.begin(115200);
  Serial.println("\n\nNEXUS Scanner Controller - ESP32");
  
  // ========== Initialize NeoPixels ==========
  ring1.begin();
  ring2.begin();
  ring1.setBrightness(brightness);
  ring2.setBrightness(brightness);
  ring1.clear();
  ring2.clear();
  ring1.show();
  ring2.show();
  Serial.println("✓ NeoPixels initialized");
  
  // ========== Initialize Steppers ==========
  pinMode(X_ENABLE_PIN, OUTPUT);
  pinMode(Y_ENABLE_PIN, OUTPUT);
  digitalWrite(X_ENABLE_PIN, HIGH);  // Disable steppers initially
  digitalWrite(Y_ENABLE_PIN, HIGH);
  
  stepperX.setMaxSpeed(MAX_SPEED);
  stepperX.setAcceleration(ACCELERATION);
  stepperY.setMaxSpeed(MAX_SPEED);
  stepperY.setAcceleration(ACCELERATION);
  Serial.println("✓ Steppers initialized");
  
  // ========== Initialize Limit Switches ==========
  pinMode(X_LIMIT_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_PIN, INPUT_PULLUP);
  Serial.println("✓ Limit switches configured");
  
  // ========== Connect to WiFi ==========
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 20) {
    delay(500);
    Serial.print(".");
    wifiAttempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("IP address: http://");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n✗ WiFi connection failed");
  }
  
  // ========== Setup HTTP Endpoints ==========
  server.on("/", handleRoot);
  server.on("/lights", handleLights);
  server.on("/move", handleMove);
  server.on("/home", handleHome);
  server.on("/jog", handleJog);
  server.on("/enable", handleEnable);
  server.on("/status", handleStatus);
  server.onNotFound(handleNotFound);
  
  server.begin();
  Serial.println("✓ HTTP server started");
  Serial.println("\n========================================");
  Serial.println("NEXUS Scanner Ready!");
  Serial.println("========================================");
  Serial.println("Endpoints:");
  Serial.println("  /lights?cmd=ON");
  Serial.println("  /lights?cmd=TEMP:5000");
  Serial.println("  /move?x=100&y=150");
  Serial.println("  /home");
  Serial.println("  /status");
  Serial.println("========================================\n");
  
  inputString.reserve(128);
}

void loop() {
  server.handleClient();
  
  // Run steppers (non-blocking)
  stepperX.run();
  stepperY.run();
  
  // Check for serial commands
  if (stringComplete) {
    processSerialCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
}

// ========== HTTP Handlers ==========

void handleRoot() {
  String html = "<html><head><title>NEXUS Scanner</title></head><body>";
  html += "<h1>NEXUS Card Scanner Controller</h1>";
  html += "<h2>Lighting</h2>";
  html += "<p>Status: " + String(lightsOn ? "ON" : "OFF") + "</p>";
  html += "<p>Brightness: " + String(brightness) + " | Color Temp: " + String(colorTemp) + "K</p>";
  html += "<a href='/lights?cmd=ON'><button>Lights ON</button></a> ";
  html += "<a href='/lights?cmd=OFF'><button>Lights OFF</button></a><br><br>";
  html += "<a href='/lights?cmd=TEMP:5000'><button>5000K (Neutral)</button></a> ";
  html += "<a href='/lights?cmd=BRIGHT:200'><button>Brightness 200</button></a><br><br>";
  
  html += "<h2>XY Motion</h2>";
  html += "<p>Position: X=" + String(currentX, 1) + "mm, Y=" + String(currentY, 1) + "mm</p>";
  html += "<p>Homed: " + String(isHomed ? "YES" : "NO") + "</p>";
  html += "<a href='/home'><button>HOME</button></a><br><br>";
  html += "<a href='/move?x=190&y=190'><button>Move to Center</button></a> ";
  html += "<a href='/move?x=0&y=0'><button>Move to Origin</button></a><br><br>";
  html += "<a href='/jog?x=10&y=0'><button>Jog +X</button></a> ";
  html += "<a href='/jog?x=-10&y=0'><button>Jog -X</button></a> ";
  html += "<a href='/jog?x=0&y=10'><button>Jog +Y</button></a> ";
  html += "<a href='/jog?x=0&y=-10'><button>Jog -Y</button></a><br><br>";
  html += "<a href='/enable?state=1'><button>Enable Motors</button></a> ";
  html += "<a href='/enable?state=0'><button>Disable Motors</button></a><br><br>";
  
  html += "<h2>System</h2>";
  html += "<a href='/status'><button>Get Status (JSON)</button></a>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleLights() {
  if (server.hasArg("cmd")) {
    String cmd = server.arg("cmd");
    String response = processLightCommand(cmd);
    server.send(200, "text/plain", response);
  } else {
    server.send(400, "text/plain", "ERROR:MISSING_CMD");
  }
}

void handleMove() {
  if (server.hasArg("x") && server.hasArg("y")) {
    float targetX = server.arg("x").toFloat();
    float targetY = server.arg("y").toFloat();
    
    if (targetX < 0 || targetX > BED_SIZE_X || targetY < 0 || targetY > BED_SIZE_Y) {
      server.send(400, "text/plain", "ERROR:OUT_OF_BOUNDS");
      return;
    }
    
    moveTo(targetX, targetY);
    String response = "OK:MOVING_TO X=" + String(targetX, 1) + " Y=" + String(targetY, 1);
    server.send(200, "text/plain", response);
  } else {
    server.send(400, "text/plain", "ERROR:MISSING_X_OR_Y");
  }
}

void handleJog() {
  if (server.hasArg("x") && server.hasArg("y")) {
    float jogX = server.arg("x").toFloat();
    float jogY = server.arg("y").toFloat();
    
    float newX = currentX + jogX;
    float newY = currentY + jogY;
    
    // Clamp to bed limits
    newX = constrain(newX, 0, BED_SIZE_X);
    newY = constrain(newY, 0, BED_SIZE_Y);
    
    moveTo(newX, newY);
    String response = "OK:JOGGED_TO X=" + String(newX, 1) + " Y=" + String(newY, 1);
    server.send(200, "text/plain", response);
  } else {
    server.send(400, "text/plain", "ERROR:MISSING_X_OR_Y");
  }
}

void handleHome() {
  Serial.println("Homing XY axes...");
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  
  homeAxis('X');
  homeAxis('Y');
  
  isHomed = true;
  currentX = 0.0;
  currentY = 0.0;
  
  Serial.println("Homing complete!");
  server.send(200, "text/plain", "OK:HOMED X=0 Y=0");
}

void handleEnable() {
  if (server.hasArg("state")) {
    int state = server.arg("state").toInt();
    digitalWrite(X_ENABLE_PIN, state == 0 ? HIGH : LOW);
    digitalWrite(Y_ENABLE_PIN, state == 0 ? HIGH : LOW);
    String response = state == 1 ? "OK:MOTORS_ENABLED" : "OK:MOTORS_DISABLED";
    server.send(200, "text/plain", response);
  } else {
    server.send(400, "text/plain", "ERROR:MISSING_STATE");
  }
}

void handleStatus() {
  String json = "{";
  json += "\"lights\":{\"on\":" + String(lightsOn ? "true" : "false");
  json += ",\"brightness\":" + String(brightness);
  json += ",\"temp\":" + String(colorTemp) + "},";
  json += "\"position\":{\"x\":" + String(currentX, 2);
  json += ",\"y\":" + String(currentY, 2);
  json += ",\"homed\":" + String(isHomed ? "true" : "false") + "},";
  json += "\"limits\":{\"x\":" + String(digitalRead(X_LIMIT_PIN) == LOW ? "true" : "false");
  json += ",\"y\":" + String(digitalRead(Y_LIMIT_PIN) == LOW ? "true" : "false") + "},";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\"";
  json += "}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  server.send(404, "text/plain", "ERROR:NOT_FOUND");
}

// ========== Motion Control Functions ==========

void moveTo(float x_mm, float y_mm) {
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  
  long targetX_steps = (long)(x_mm * STEPS_PER_MM);
  long targetY_steps = (long)(y_mm * STEPS_PER_MM);
  
  stepperX.moveTo(targetX_steps);
  stepperY.moveTo(targetY_steps);
  
  // Wait for motion to complete
  while (stepperX.isRunning() || stepperY.isRunning()) {
    stepperX.run();
    stepperY.run();
    server.handleClient();  // Keep HTTP responsive
    yield();  // ESP32 watchdog
  }
  
  currentX = x_mm;
  currentY = y_mm;
  
  Serial.print("Moved to X=");
  Serial.print(currentX, 1);
  Serial.print("mm Y=");
  Serial.print(currentY, 1);
  Serial.println("mm");
}

void homeAxis(char axis) {
  AccelStepper* stepper;
  int limitPin;
  
  if (axis == 'X') {
    stepper = &stepperX;
    limitPin = X_LIMIT_PIN;
    Serial.print("Homing X-axis... ");
  } else {
    stepper = &stepperY;
    limitPin = Y_LIMIT_PIN;
    Serial.print("Homing Y-axis... ");
  }
  
  stepper->setMaxSpeed(HOMING_SPEED);
  stepper->move(-999999);  // Move towards home (negative direction)
  
  // Move until limit switch triggers
  while (digitalRead(limitPin) == HIGH) {
    stepper->run();
    server.handleClient();
    yield();
  }
  
  stepper->stop();
  stepper->setCurrentPosition(0);
  stepper->setMaxSpeed(MAX_SPEED);
  
  // Back off slightly
  stepper->move(50);  // Back off 50 steps (~0.125mm)
  while (stepper->isRunning()) {
    stepper->run();
    yield();
  }
  
  stepper->setCurrentPosition(0);
  Serial.println("✓");
}

// ========== Lighting Functions ==========

String processLightCommand(String command) {
  command.trim();
  command.toUpperCase();
  
  if (command == "ON") {
    lightsOn = true;
    setColor(red, green, blue);
    return "OK:LIGHTS_ON";
    
  } else if (command == "OFF") {
    lightsOn = false;
    ring1.clear();
    ring2.clear();
    ring1.show();
    ring2.show();
    return "OK:LIGHTS_OFF";
    
  } else if (command.startsWith("BRIGHT:")) {
    int newBrightness = command.substring(7).toInt();
    if (newBrightness >= 0 && newBrightness <= 255) {
      brightness = newBrightness;
      ring1.setBrightness(brightness);
      ring2.setBrightness(brightness);
      if (lightsOn) setColor(red, green, blue);
      return "OK:BRIGHTNESS_" + String(brightness);
    }
    return "ERROR:BRIGHTNESS_RANGE";
    
  } else if (command.startsWith("TEMP:")) {
    int newTemp = command.substring(5).toInt();
    if (newTemp >= 2700 && newTemp <= 6500) {
      colorTemp = newTemp;
      tempToRGB(colorTemp, red, green, blue);
      if (lightsOn) setColor(red, green, blue);
      return "OK:TEMP_" + String(colorTemp) + "K";
    }
    return "ERROR:TEMP_RANGE";
  }
  
  return "ERROR:UNKNOWN_COMMAND";
}

void setColor(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = ring1.Color(r, g, b);
  for (int i = 0; i < LEDS_PER_RING; i++) {
    ring1.setPixelColor(i, color);
    ring2.setPixelColor(i, color);
  }
  ring1.show();
  ring2.show();
}

void tempToRGB(uint16_t kelvin, uint8_t &r, uint8_t &g, uint8_t &b) {
  float temp = kelvin / 100.0;
  
  // Red
  if (temp <= 66) {
    r = 255;
  } else {
    float redCalc = temp - 60;
    redCalc = 329.698727446 * pow(redCalc, -0.1332047592);
    r = constrain(redCalc, 0, 255);
  }
  
  // Green
  if (temp <= 66) {
    float greenCalc = temp;
    greenCalc = 99.4708025861 * log(greenCalc) - 161.1195681661;
    g = constrain(greenCalc, 0, 255);
  } else {
    float greenCalc = temp - 60;
    greenCalc = 288.1221695283 * pow(greenCalc, -0.0755148492);
    g = constrain(greenCalc, 0, 255);
  }
  
  // Blue
  if (temp >= 66) {
    b = 255;
  } else if (temp <= 19) {
    b = 0;
  } else {
    float blueCalc = temp - 10;
    blueCalc = 138.5177312231 * log(blueCalc) - 305.0447927307;
    b = constrain(blueCalc, 0, 255);
  }
}

// ========== Serial Command Processing ==========

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }
}

void processSerialCommand(String command) {
  command.trim();
  if (command.startsWith("LIGHT:")) {
    String lightCmd = command.substring(6);
    Serial.println(processLightCommand(lightCmd));
  } else if (command == "HOME") {
    homeAxis('X');
    homeAxis('Y');
    isHomed = true;
    currentX = currentY = 0;
    Serial.println("OK:HOMED");
  } else if (command.startsWith("MOVE:")) {
    // Format: MOVE:X100,Y150
    int xIdx = command.indexOf('X');
    int yIdx = command.indexOf('Y');
    if (xIdx > 0 && yIdx > 0) {
      float x = command.substring(xIdx + 1, yIdx).toFloat();
      float y = command.substring(yIdx + 1).toFloat();
      moveTo(x, y);
      Serial.println("OK:MOVED");
    } else {
      Serial.println("ERROR:INVALID_MOVE_FORMAT");
    }
  } else {
    Serial.println("ERROR:UNKNOWN_COMMAND");
  }
}
