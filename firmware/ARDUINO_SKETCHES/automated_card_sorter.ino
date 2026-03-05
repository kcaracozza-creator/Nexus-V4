/*
 * Automated Card Sorter - Arduino Controller
 * Controls XY carriage, vacuum pickup, hopper dispenser, and bin sorting
 * 
 * Hardware:
 * - 2x NEMA 17 Stepper Motors (X/Y axes)
 * - 2x A4988/DRV8825 Stepper Drivers
 * - 2x T8 Lead Screws (Creality X003EAOXL1)
 * - 1x Vacuum pump + solenoid valve
 * - 1x Vacuum sensor (pressure switch)
 * - 1x Servo motor (hopper dispenser)
 * - 4x Limit switches (X/Y min/max)
 * 
 * Pin Assignments:
 * X-Axis: STEP=2, DIR=3, EN=4
 * Y-Axis: STEP=5, DIR=6, EN=7
 * Vacuum Solenoid: Pin 8
 * Vacuum Sensor: Pin 9
 * Hopper Servo: Pin 10
 * Limit Switches: 11, 12, 13, 14
 */

#include <Servo.h>

// Motor pins
#define X_STEP_PIN 2
#define X_DIR_PIN 3
#define X_ENABLE_PIN 4

#define Y_STEP_PIN 5
#define Y_DIR_PIN 6
#define Y_ENABLE_PIN 7

// Vacuum system
#define VACUUM_SOLENOID_PIN 8
#define VACUUM_SENSOR_PIN 9

// Hopper dispenser
#define HOPPER_SERVO_PIN 10
Servo hopperServo;

// Limit switches
#define X_LIMIT_MIN_PIN 11
#define X_LIMIT_MAX_PIN 12
#define Y_LIMIT_MIN_PIN 13
#define Y_LIMIT_MAX_PIN 14

// Status LED
#define STATUS_LED 13

// Motor configuration - Creality X003EAOXL1
#define STEPS_PER_REV 200
#define MICROSTEPS 16
#define LEAD_SCREW_PITCH 8.0

// Movement limits
#define X_MAX_STEPS 15200  // ~380mm
#define Y_MAX_STEPS 15200  // ~380mm

// Current position
long x_position = 0;
long y_position = 0;
bool is_homed = false;

// Vacuum state
bool vacuum_active = false;

// Hopper state
int hopper_count = 0;  // Cards dispensed this session

void setup() {
  Serial.begin(115200);
  
  // Configure motor pins
  pinMode(X_STEP_PIN, OUTPUT);
  pinMode(X_DIR_PIN, OUTPUT);
  pinMode(X_ENABLE_PIN, OUTPUT);
  pinMode(Y_STEP_PIN, OUTPUT);
  pinMode(Y_DIR_PIN, OUTPUT);
  pinMode(Y_ENABLE_PIN, OUTPUT);
  
  // Configure vacuum pins
  pinMode(VACUUM_SOLENOID_PIN, OUTPUT);
  pinMode(VACUUM_SENSOR_PIN, INPUT_PULLUP);
  digitalWrite(VACUUM_SOLENOID_PIN, LOW);  // Vacuum OFF initially
  
  // Configure hopper servo
  hopperServo.attach(HOPPER_SERVO_PIN);
  hopperServo.write(0);  // Retracted position
  
  // Configure limit switches
  pinMode(X_LIMIT_MIN_PIN, INPUT_PULLUP);
  pinMode(X_LIMIT_MAX_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_MIN_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_MAX_PIN, INPUT_PULLUP);
  
  pinMode(STATUS_LED, OUTPUT);
  
  // Disable motors initially
  digitalWrite(X_ENABLE_PIN, HIGH);
  digitalWrite(Y_ENABLE_PIN, HIGH);
  
  // Startup blink
  for (int i = 0; i < 3; i++) {
    digitalWrite(STATUS_LED, HIGH);
    delay(100);
    digitalWrite(STATUS_LED, LOW);
    delay(100);
  }
  
  Serial.println("AUTOMATED_SORTER_READY");
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    processCommand(command);
  }
  
  // Heartbeat LED
  if (is_homed) {
    digitalWrite(STATUS_LED, (millis() / 1000) % 2);
  }
}

void processCommand(String cmd) {
  if (cmd == "INIT") {
    Serial.println("OK_INITIALIZED");
    
  } else if (cmd == "HOME") {
    homeAxes();
    
  } else if (cmd.startsWith("MOVE ")) {
    // MOVE X Y SPEED
    int firstSpace = cmd.indexOf(' ', 5);
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    
    long steps_x = cmd.substring(5, firstSpace).toInt();
    long steps_y = cmd.substring(firstSpace + 1, secondSpace).toInt();
    int speed = cmd.substring(secondSpace + 1).toInt();
    
    moveRelative(steps_x, steps_y, speed);
    
  } else if (cmd == "VACUUM ON") {
    vacuumOn();
    
  } else if (cmd == "VACUUM OFF") {
    vacuumOff();
    
  } else if (cmd == "CHECK_VACUUM") {
    checkVacuum();
    
  } else if (cmd == "DISPENSE") {
    dispenseCard();
    
  } else if (cmd == "STATUS") {
    Serial.print("POS X:");
    Serial.print(x_position);
    Serial.print(" Y:");
    Serial.print(y_position);
    Serial.print(" VACUUM:");
    Serial.print(vacuum_active ? "ON" : "OFF");
    Serial.print(" CARDS:");
    Serial.println(hopper_count);
    
  } else {
    Serial.println("ERROR_UNKNOWN_COMMAND");
  }
}

void homeAxes() {
  Serial.println("HOMING_STARTED");
  
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  delay(10);
  
  // Home X axis
  Serial.println("HOMING_X");
  digitalWrite(X_DIR_PIN, LOW);
  
  while (digitalRead(X_LIMIT_MIN_PIN) == HIGH) {
    digitalWrite(X_STEP_PIN, HIGH);
    delayMicroseconds(800);
    digitalWrite(X_STEP_PIN, LOW);
    delayMicroseconds(800);
  }
  
  // Back off
  digitalWrite(X_DIR_PIN, HIGH);
  for (int i = 0; i < 200; i++) {
    digitalWrite(X_STEP_PIN, HIGH);
    delayMicroseconds(800);
    digitalWrite(X_STEP_PIN, LOW);
    delayMicroseconds(800);
  }
  
  x_position = 0;
  Serial.println("HOMED_X");
  
  // Home Y axis
  Serial.println("HOMING_Y");
  digitalWrite(Y_DIR_PIN, LOW);
  
  while (digitalRead(Y_LIMIT_MIN_PIN) == HIGH) {
    digitalWrite(Y_STEP_PIN, HIGH);
    delayMicroseconds(800);
    digitalWrite(Y_STEP_PIN, LOW);
    delayMicroseconds(800);
  }
  
  // Back off
  digitalWrite(Y_DIR_PIN, HIGH);
  for (int i = 0; i < 200; i++) {
    digitalWrite(Y_STEP_PIN, HIGH);
    delayMicroseconds(800);
    digitalWrite(Y_STEP_PIN, LOW);
    delayMicroseconds(800);
  }
  
  y_position = 0;
  Serial.println("HOMED_Y");
  
  is_homed = true;
  Serial.println("HOMED_COMPLETE");
}

void moveRelative(long steps_x, long steps_y, int speed) {
  if (!is_homed) {
    Serial.println("ERROR_NOT_HOMED");
    return;
  }
  
  long new_x = x_position + steps_x;
  long new_y = y_position + steps_y;
  
  if (new_x < 0 || new_x > X_MAX_STEPS || new_y < 0 || new_y > Y_MAX_STEPS) {
    Serial.println("ERROR_OUT_OF_BOUNDS");
    return;
  }
  
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  delay(10);
  
  digitalWrite(X_DIR_PIN, steps_x >= 0 ? HIGH : LOW);
  digitalWrite(Y_DIR_PIN, steps_y >= 0 ? HIGH : LOW);
  
  long abs_x = abs(steps_x);
  long abs_y = abs(steps_y);
  long max_steps = max(abs_x, abs_y);
  
  // Coordinated motion
  long error_x = 0;
  long error_y = 0;
  
  for (long i = 0; i < max_steps; i++) {
    bool step_x_now = false;
    bool step_y_now = false;
    
    if (abs_x > 0) {
      error_x += abs_x;
      if (error_x >= max_steps) {
        error_x -= max_steps;
        step_x_now = true;
      }
    }
    
    if (abs_y > 0) {
      error_y += abs_y;
      if (error_y >= max_steps) {
        error_y -= max_steps;
        step_y_now = true;
      }
    }
    
    if (step_x_now) digitalWrite(X_STEP_PIN, HIGH);
    if (step_y_now) digitalWrite(Y_STEP_PIN, HIGH);
    
    delayMicroseconds(speed);
    
    digitalWrite(X_STEP_PIN, LOW);
    digitalWrite(Y_STEP_PIN, LOW);
    
    delayMicroseconds(speed);
  }
  
  x_position = new_x;
  y_position = new_y;
  Serial.println("MOVE_DONE");
}

void vacuumOn() {
  digitalWrite(VACUUM_SOLENOID_PIN, HIGH);
  vacuum_active = true;
  Serial.println("VACUUM_ON");
}

void vacuumOff() {
  digitalWrite(VACUUM_SOLENOID_PIN, LOW);
  vacuum_active = false;
  Serial.println("VACUUM_OFF");
}

void checkVacuum() {
  // Read vacuum sensor (LOW = vacuum present, card held)
  bool card_held = (digitalRead(VACUUM_SENSOR_PIN) == LOW);
  
  if (card_held && vacuum_active) {
    Serial.println("CARD_HELD");
  } else {
    Serial.println("NO_CARD");
  }
}

void dispenseCard() {
  // Actuate hopper servo to dispense one card
  Serial.println("DISPENSING");
  
  // Move servo to dispense position
  hopperServo.write(90);  // Advance one card
  delay(300);              // Wait for card to drop
  
  // Retract
  hopperServo.write(0);
  delay(200);
  
  hopper_count++;
  Serial.println("CARD_READY");
}
