/*
 * NEXUS Scanner - Full Hardware Test
 * ESP32 DevKitV1 (30-pin)
 * 
 * Tests: 4 servos, 1 stepper (28BYJ-48), NeoPixel rings
 * 
 * Libraries needed:
 *   - ESP32Servo (Kevin Harrington)
 *   - Adafruit NeoPixel
 */

#include <ESP32Servo.h>
#include <Adafruit_NeoPixel.h>

// ============== PIN DEFINITIONS ==============
// Servos
#define SERVO_BASE     13
#define SERVO_SHOULDER 12
#define SERVO_ELBOW    14
#define SERVO_WRIST    27

// Stepper (28BYJ-48 via ULN2003)
#define STEP_IN1 26
#define STEP_IN2 25
#define STEP_IN3 33
#define STEP_IN4 32

// NeoPixels
#define NEO_24_PIN  4    // 24-LED ring
#define NEO_16_PIN  17   // 16-LED ring

// Other
#define LED_PANEL_PIN  21
#define VACUUM_PUMP    23
#define VACUUM_VALVE   22

// ============== OBJECTS ==============
Servo servoBase;
Servo servoShoulder;
Servo servoElbow;
Servo servoWrist;

Adafruit_NeoPixel ring24(24, NEO_24_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel ring16(16, NEO_16_PIN, NEO_GRB + NEO_KHZ800);

// ============== STATE ==============
int baseAngle = 90;
int shoulderAngle = 90;
int elbowAngle = 90;
int wristAngle = 90;

bool neo24On = false;
bool neo16On = false;
uint8_t brightness = 128;
uint32_t currentColor = 0xFFFFFF;

// Stepper sequence (half-step for smoothness)
const int stepSequence[8][4] = {
  {1,0,0,0}, {1,1,0,0}, {0,1,0,0}, {0,1,1,0},
  {0,0,1,0}, {0,0,1,1}, {0,0,0,1}, {1,0,0,1}
};
int stepIndex = 0;

// ============== SETUP ==============
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== NEXUS Hardware Test ===");
  
  // Servos
  servoBase.attach(SERVO_BASE);
  servoShoulder.attach(SERVO_SHOULDER);
  servoElbow.attach(SERVO_ELBOW);
  servoWrist.attach(SERVO_WRIST);
  
  homeServos();
  
  // Stepper pins
  pinMode(STEP_IN1, OUTPUT);
  pinMode(STEP_IN2, OUTPUT);
  pinMode(STEP_IN3, OUTPUT);
  pinMode(STEP_IN4, OUTPUT);
  stepperOff();
  
  // NeoPixels
  ring24.begin();
  ring16.begin();
  ring24.setBrightness(brightness);
  ring16.setBrightness(brightness);
  ring24.clear();
  ring16.clear();
  ring24.show();
  ring16.show();
  
  // Flash on startup
  flashNeoPixels();
  
  // Other pins
  pinMode(LED_PANEL_PIN, OUTPUT);
  pinMode(VACUUM_PUMP, OUTPUT);
  pinMode(VACUUM_VALVE, OUTPUT);
  
  printHelp();
}

// ============== MAIN LOOP ==============
void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    handleCommand(cmd);
  }
}

// ============== COMMAND HANDLER ==============
void handleCommand(char cmd) {
  switch (cmd) {
    // Servo selection + adjustment
    case '1': baseAngle = constrain(baseAngle - 10, 0, 180); servoBase.write(baseAngle); Serial.printf("Base: %d\n", baseAngle); break;
    case '2': baseAngle = constrain(baseAngle + 10, 0, 180); servoBase.write(baseAngle); Serial.printf("Base: %d\n", baseAngle); break;
    case '3': shoulderAngle = constrain(shoulderAngle - 10, 0, 180); servoShoulder.write(shoulderAngle); Serial.printf("Shoulder: %d\n", shoulderAngle); break;
    case '4': shoulderAngle = constrain(shoulderAngle + 10, 0, 180); servoShoulder.write(shoulderAngle); Serial.printf("Shoulder: %d\n", shoulderAngle); break;
    case '5': elbowAngle = constrain(elbowAngle - 10, 0, 180); servoElbow.write(elbowAngle); Serial.printf("Elbow: %d\n", elbowAngle); break;
    case '6': elbowAngle = constrain(elbowAngle + 10, 0, 180); servoElbow.write(elbowAngle); Serial.printf("Elbow: %d\n", elbowAngle); break;
    case '7': wristAngle = constrain(wristAngle - 10, 0, 180); servoWrist.write(wristAngle); Serial.printf("Wrist: %d\n", wristAngle); break;
    case '8': wristAngle = constrain(wristAngle + 10, 0, 180); servoWrist.write(wristAngle); Serial.printf("Wrist: %d\n", wristAngle); break;
    
    // Auto test
    case 'a': autoTestServos(); break;
    
    // Home
    case 'h': homeServos(); Serial.println("Homed all servos to 90"); break;
    
    // Stepper
    case 'q': stepperRotate(512, true); Serial.println("Stepper CW 90°"); break;
    case 'e': stepperRotate(512, false); Serial.println("Stepper CCW 90°"); break;
    case 'f': stepperRotate(1024, true); Serial.println("Stepper FLIP 180°"); break;
    
    // NeoPixels
    case 'l': toggleNeo24(); break;
    case 'k': toggleNeo16(); break;
    case 'b': cycleBrightness(); break;
    case 'r': setColor(0xFF0000); Serial.println("Color: RED"); break;
    case 'g': setColor(0x00FF00); Serial.println("Color: GREEN"); break;
    case 'u': setColor(0x0000FF); Serial.println("Color: BLUE"); break;
    case 'w': setColor(0xFFFFFF); Serial.println("Color: WHITE"); break;
    
    // Status
    case 'p': printStatus(); break;
    case '?': printHelp(); break;
    
    default: break;
  }
}

// ============== SERVO FUNCTIONS ==============
void homeServos() {
  baseAngle = shoulderAngle = elbowAngle = wristAngle = 90;
  servoBase.write(90);
  servoShoulder.write(90);
  servoElbow.write(90);
  servoWrist.write(90);
}

void autoTestServos() {
  Serial.println("Auto test starting...");
  
  // Test each servo
  Servo* servos[] = {&servoBase, &servoShoulder, &servoElbow, &servoWrist};
  const char* names[] = {"Base", "Shoulder", "Elbow", "Wrist"};
  
  for (int s = 0; s < 4; s++) {
    Serial.printf("Testing %s...\n", names[s]);
    for (int a = 90; a <= 120; a += 5) { servos[s]->write(a); delay(50); }
    for (int a = 120; a >= 60; a -= 5) { servos[s]->write(a); delay(50); }
    for (int a = 60; a <= 90; a += 5) { servos[s]->write(a); delay(50); }
  }
  
  Serial.println("Auto test complete.");
}

// ============== STEPPER FUNCTIONS ==============
void stepperStep(bool cw) {
  if (cw) {
    stepIndex = (stepIndex + 1) % 8;
  } else {
    stepIndex = (stepIndex + 7) % 8;
  }
  
  digitalWrite(STEP_IN1, stepSequence[stepIndex][0]);
  digitalWrite(STEP_IN2, stepSequence[stepIndex][1]);
  digitalWrite(STEP_IN3, stepSequence[stepIndex][2]);
  digitalWrite(STEP_IN4, stepSequence[stepIndex][3]);
}

void stepperRotate(int steps, bool cw) {
  for (int i = 0; i < steps; i++) {
    stepperStep(cw);
    delayMicroseconds(1200);
  }
  stepperOff();
}

void stepperOff() {
  digitalWrite(STEP_IN1, LOW);
  digitalWrite(STEP_IN2, LOW);
  digitalWrite(STEP_IN3, LOW);
  digitalWrite(STEP_IN4, LOW);
}

// ============== NEOPIXEL FUNCTIONS ==============
void toggleNeo24() {
  neo24On = !neo24On;
  if (neo24On) {
    ring24.fill(currentColor);
  } else {
    ring24.clear();
  }
  ring24.show();
  Serial.printf("24-ring: %s\n", neo24On ? "ON" : "OFF");
}

void toggleNeo16() {
  neo16On = !neo16On;
  if (neo16On) {
    ring16.fill(currentColor);
  } else {
    ring16.clear();
  }
  ring16.show();
  Serial.printf("16-ring: %s\n", neo16On ? "ON" : "OFF");
}

void cycleBrightness() {
  if (brightness == 64) brightness = 128;
  else if (brightness == 128) brightness = 255;
  else brightness = 64;
  
  ring24.setBrightness(brightness);
  ring16.setBrightness(brightness);
  ring24.show();
  ring16.show();
  Serial.printf("Brightness: %d%%\n", brightness * 100 / 255);
}

void setColor(uint32_t color) {
  currentColor = color;
  if (neo24On) { ring24.fill(color); ring24.show(); }
  if (neo16On) { ring16.fill(color); ring16.show(); }
}

void flashNeoPixels() {
  ring24.fill(0x00FF00);
  ring16.fill(0x00FF00);
  ring24.show();
  ring16.show();
  delay(200);
  ring24.clear();
  ring16.clear();
  ring24.show();
  ring16.show();
}

// ============== INFO ==============
void printStatus() {
  Serial.println("\n=== STATUS ===");
  Serial.printf("Servos: B=%d S=%d E=%d W=%d\n", baseAngle, shoulderAngle, elbowAngle, wristAngle);
  Serial.printf("NeoPixels: 24=%s 16=%s Bright=%d%%\n", neo24On?"ON":"OFF", neo16On?"ON":"OFF", brightness*100/255);
  Serial.println();
}

void printHelp() {
  Serial.println("\n=== COMMANDS ===");
  Serial.println("1/2 - Base -/+");
  Serial.println("3/4 - Shoulder -/+");
  Serial.println("5/6 - Elbow -/+");
  Serial.println("7/8 - Wrist -/+");
  Serial.println("a - Auto test all servos");
  Serial.println("h - Home (all 90)");
  Serial.println("q/e - Stepper CW/CCW 90");
  Serial.println("f - Stepper flip 180");
  Serial.println("l/k - Toggle 24/16 ring");
  Serial.println("b - Cycle brightness");
  Serial.println("r/g/u/w - Red/Green/Blue/White");
  Serial.println("p - Print status");
  Serial.println("? - Help\n");
}
