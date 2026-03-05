/*
 * Card Shuffler/Sorter Arduino Controller
 * Controls roller feed, stopper servo, card sensor, and gripper
 * 
 * Hardware:
 * - 2x Servo motors (roller feed + stopper)
 * - IR sensor (card detection)
 * - Vacuum pump or servo gripper
 * - Optional: Z-axis servo for lift/lower
 * 
 * Wiring:
 * - Roller Servo: Pin 9
 * - Stopper Servo: Pin 10
 * - Card Sensor (IR): Pin A0
 * - Gripper/Vacuum: Pin 11
 * - Z-Axis Servo: Pin 12 (optional)
 */

#include <Servo.h>

// Servo objects
Servo rollerServo;
Servo stopperServo;
Servo zAxisServo;  // Optional lift mechanism

// Pin definitions
#define ROLLER_SERVO_PIN 9
#define STOPPER_SERVO_PIN 10
#define Z_AXIS_SERVO_PIN 12
#define CARD_SENSOR_PIN A0
#define GRIPPER_PIN 11  // Relay for vacuum or servo signal

// Card sensor threshold (IR reflective sensor)
#define CARD_DETECT_THRESHOLD 500

// Z-axis positions
#define Z_LIFTED 120   // Card lifted for transport
#define Z_LOWERED 60   // Card in scanning position
#define Z_HOME 90      // Neutral position

// Current states
bool gripperActive = false;
int zPosition = Z_HOME;

void setup() {
  Serial.begin(115200);
  
  // Attach servos
  rollerServo.attach(ROLLER_SERVO_PIN);
  stopperServo.attach(STOPPER_SERVO_PIN);
  zAxisServo.attach(Z_AXIS_SERVO_PIN);
  
  // Setup pins
  pinMode(CARD_SENSOR_PIN, INPUT);
  pinMode(GRIPPER_PIN, OUTPUT);
  
  // Initialize to safe positions
  rollerServo.write(0);     // Idle
  stopperServo.write(0);    // Closed
  zAxisServo.write(Z_HOME);
  digitalWrite(GRIPPER_PIN, LOW);
  
  Serial.println("SHUFFLER_READY");
  Serial.println("Commands: SERVO, CARD_DETECT, GRIPPER_ON, GRIPPER_OFF, LIFT_CARD, LOWER_CARD");
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    processCommand(command);
  }
}

void processCommand(String cmd) {
  
  if (cmd.startsWith("SERVO ")) {
    // SERVO <pin> <angle>
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    
    int pin = cmd.substring(firstSpace + 1, secondSpace).toInt();
    int angle = cmd.substring(secondSpace + 1).toInt();
    
    setServo(pin, angle);
    Serial.println("OK_SERVO");
    
  } else if (cmd == "CARD_DETECT") {
    // Check if card is present
    bool detected = checkCardPresent();
    Serial.println(detected ? "DETECTED" : "NOT_DETECTED");
    
  } else if (cmd == "GRIPPER_ON") {
    // Activate vacuum or close gripper
    digitalWrite(GRIPPER_PIN, HIGH);
    gripperActive = true;
    Serial.println("GRIPPER_ACTIVE");
    
  } else if (cmd == "GRIPPER_OFF") {
    // Deactivate vacuum or open gripper
    digitalWrite(GRIPPER_PIN, LOW);
    gripperActive = false;
    Serial.println("GRIPPER_RELEASED");
    
  } else if (cmd == "LIFT_CARD") {
    // Raise Z-axis for transport
    zAxisServo.write(Z_LIFTED);
    zPosition = Z_LIFTED;
    delay(300);
    Serial.println("CARD_LIFTED");
    
  } else if (cmd == "LOWER_CARD") {
    // Lower Z-axis for scanning
    zAxisServo.write(Z_LOWERED);
    zPosition = Z_LOWERED;
    delay(300);
    Serial.println("CARD_LOWERED");
    
  } else if (cmd == "Z_HOME") {
    // Return Z to neutral
    zAxisServo.write(Z_HOME);
    zPosition = Z_HOME;
    delay(300);
    Serial.println("Z_HOME");
    
  } else if (cmd == "STATUS") {
    // Report status
    Serial.print("GRIPPER:");
    Serial.print(gripperActive ? "ON" : "OFF");
    Serial.print(" Z:");
    Serial.print(zPosition);
    Serial.print(" CARD:");
    Serial.println(checkCardPresent() ? "YES" : "NO");
    
  } else {
    Serial.println("ERROR_UNKNOWN_COMMAND");
  }
}

void setServo(int pin, int angle) {
  // Constrain angle
  angle = constrain(angle, 0, 180);
  
  if (pin == ROLLER_SERVO_PIN) {
    rollerServo.write(angle);
  } else if (pin == STOPPER_SERVO_PIN) {
    stopperServo.write(angle);
  } else if (pin == Z_AXIS_SERVO_PIN) {
    zAxisServo.write(angle);
    zPosition = angle;
  }
}

bool checkCardPresent() {
  // Read IR sensor
  int sensorValue = analogRead(CARD_SENSOR_PIN);
  
  // Card blocks IR beam = low reading
  // No card = high reading
  return sensorValue < CARD_DETECT_THRESHOLD;
}

// Debugging: Print sensor value every second
unsigned long lastPrint = 0;
void debugSensor() {
  if (millis() - lastPrint > 1000) {
    int val = analogRead(CARD_SENSOR_PIN);
    Serial.print("Sensor: ");
    Serial.println(val);
    lastPrint = millis();
  }
}
