/*
 * XY Scanner Controller - Dual Lead Screw System
 * Controls two stepper motors for automated card positioning
 * 
 * Hardware:
 * - 2x NEMA 17 Stepper Motors
 * - 2x A4988/DRV8825 Stepper Drivers
 * - 2x T8 Lead Screws (2mm pitch)
 * - 2x Linear Rails
 * - 4x Limit Switches (X min/max, Y min/max)
 * - Arduino Uno/Mega
 * 
 * Wiring:
 * X Axis:
 *   - STEP: Pin 2
 *   - DIR:  Pin 3
 *   - EN:   Pin 4
 *   - Limit Min: Pin 9
 *   - Limit Max: Pin 10
 * 
 * Y Axis:
 *   - STEP: Pin 5
 *   - DIR:  Pin 6
 *   - EN:   Pin 7
 *   - Limit Min: Pin 11
 *   - Limit Max: Pin 12
 */

// Pin definitions
#define X_STEP_PIN 2
#define X_DIR_PIN 3
#define X_ENABLE_PIN 4
#define X_LIMIT_MIN_PIN 9
#define X_LIMIT_MAX_PIN 10

#define Y_STEP_PIN 5
#define Y_DIR_PIN 6
#define Y_ENABLE_PIN 7
#define Y_LIMIT_MIN_PIN 11
#define Y_LIMIT_MAX_PIN 12

// LED for status
#define STATUS_LED 13

// Motor configuration - Creality X003EAOXL1 Kit
#define STEPS_PER_REV 200
#define MICROSTEPS 16
#define LEAD_SCREW_PITCH 8.0  // T8 4-start = 8mm lead per revolution

// Movement limits (in steps) - 400mm Creality screws
#define X_MAX_STEPS 15200  // ~380mm usable (400mm screw)
#define Y_MAX_STEPS 15200  // ~380mm usable (400mm screw)

// Current position (in steps)
long x_position = 0;
long y_position = 0;

// Homed flag
bool is_homed = false;

// Emergency stop flag
volatile bool emergency_stop = false;

void setup() {
  Serial.begin(115200);
  
  // Configure pins
  pinMode(X_STEP_PIN, OUTPUT);
  pinMode(X_DIR_PIN, OUTPUT);
  pinMode(X_ENABLE_PIN, OUTPUT);
  pinMode(Y_STEP_PIN, OUTPUT);
  pinMode(Y_DIR_PIN, OUTPUT);
  pinMode(Y_ENABLE_PIN, OUTPUT);
  
  pinMode(X_LIMIT_MIN_PIN, INPUT_PULLUP);
  pinMode(X_LIMIT_MAX_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_MIN_PIN, INPUT_PULLUP);
  pinMode(Y_LIMIT_MAX_PIN, INPUT_PULLUP);
  
  pinMode(STATUS_LED, OUTPUT);
  
  // Disable motors initially
  digitalWrite(X_ENABLE_PIN, HIGH);
  digitalWrite(Y_ENABLE_PIN, HIGH);
  
  // Blink LED to show ready
  for (int i = 0; i < 3; i++) {
    digitalWrite(STATUS_LED, HIGH);
    delay(100);
    digitalWrite(STATUS_LED, LOW);
    delay(100);
  }
  
  Serial.println("XY_SCANNER_READY");
  Serial.println("Commands: INIT, HOME, MOVE, STATUS, STOP");
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    processCommand(command);
  }
  
  // Blink status LED when homed
  if (is_homed) {
    digitalWrite(STATUS_LED, (millis() / 1000) % 2);
  }
}

void processCommand(String cmd) {
  if (cmd == "INIT") {
    Serial.println("OK_INITIALIZED");
    
  } else if (cmd == "HOME") {
    homeAxes();
    
  } else if (cmd.startsWith("HOME ")) {
    // HOME with speed parameter
    int speed = cmd.substring(5).toInt();
    homeAxes(speed);
    
  } else if (cmd.startsWith("MOVE ")) {
    // MOVE X Y SPEED
    int firstSpace = cmd.indexOf(' ', 5);
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    
    long steps_x = cmd.substring(5, firstSpace).toInt();
    long steps_y = cmd.substring(firstSpace + 1, secondSpace).toInt();
    int speed = cmd.substring(secondSpace + 1).toInt();
    
    moveRelative(steps_x, steps_y, speed);
    
  } else if (cmd == "STATUS") {
    Serial.print("POSITION X:");
    Serial.print(x_position);
    Serial.print(" Y:");
    Serial.print(y_position);
    Serial.print(" HOMED:");
    Serial.println(is_homed ? "YES" : "NO");
    
  } else if (cmd == "STOP") {
    emergencyStop();
    
  } else {
    Serial.println("ERROR_UNKNOWN_COMMAND");
  }
}

void homeAxes(int speed = 800) {
  Serial.println("HOMING_STARTED");
  
  emergency_stop = false;
  
  // Enable motors
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  delay(10);
  
  // Home X axis first
  Serial.println("HOMING_X");
  digitalWrite(X_DIR_PIN, LOW);  // Move toward min limit
  
  while (digitalRead(X_LIMIT_MIN_PIN) == HIGH && !emergency_stop) {
    digitalWrite(X_STEP_PIN, HIGH);
    delayMicroseconds(speed);
    digitalWrite(X_STEP_PIN, LOW);
    delayMicroseconds(speed);
  }
  
  if (emergency_stop) {
    Serial.println("ERROR_EMERGENCY_STOP");
    return;
  }
  
  // Back off from limit
  digitalWrite(X_DIR_PIN, HIGH);
  for (int i = 0; i < 200; i++) {
    digitalWrite(X_STEP_PIN, HIGH);
    delayMicroseconds(speed);
    digitalWrite(X_STEP_PIN, LOW);
    delayMicroseconds(speed);
  }
  
  x_position = 0;
  Serial.println("HOMED_X");
  
  // Home Y axis
  Serial.println("HOMING_Y");
  digitalWrite(Y_DIR_PIN, LOW);  // Move toward min limit
  
  while (digitalRead(Y_LIMIT_MIN_PIN) == HIGH && !emergency_stop) {
    digitalWrite(Y_STEP_PIN, HIGH);
    delayMicroseconds(speed);
    digitalWrite(Y_STEP_PIN, LOW);
    delayMicroseconds(speed);
  }
  
  if (emergency_stop) {
    Serial.println("ERROR_EMERGENCY_STOP");
    return;
  }
  
  // Back off from limit
  digitalWrite(Y_DIR_PIN, HIGH);
  for (int i = 0; i < 200; i++) {
    digitalWrite(Y_STEP_PIN, HIGH);
    delayMicroseconds(speed);
    digitalWrite(Y_STEP_PIN, LOW);
    delayMicroseconds(speed);
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
  
  // Check limits
  long new_x = x_position + steps_x;
  long new_y = y_position + steps_y;
  
  if (new_x < 0 || new_x > X_MAX_STEPS || new_y < 0 || new_y > Y_MAX_STEPS) {
    Serial.println("ERROR_OUT_OF_BOUNDS");
    return;
  }
  
  emergency_stop = false;
  
  // Enable motors
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  delay(10);
  
  // Set directions
  digitalWrite(X_DIR_PIN, steps_x >= 0 ? HIGH : LOW);
  digitalWrite(Y_DIR_PIN, steps_y >= 0 ? HIGH : LOW);
  
  long abs_x = abs(steps_x);
  long abs_y = abs(steps_y);
  long max_steps = max(abs_x, abs_y);
  
  // Bresenham's line algorithm for coordinated motion
  long error_x = 0;
  long error_y = 0;
  long step_x = 0;
  long step_y = 0;
  
  for (long i = 0; i < max_steps && !emergency_stop; i++) {
    bool step_x_now = false;
    bool step_y_now = false;
    
    // X axis
    if (abs_x > 0) {
      error_x += abs_x;
      if (error_x >= max_steps) {
        error_x -= max_steps;
        step_x_now = true;
      }
    }
    
    // Y axis
    if (abs_y > 0) {
      error_y += abs_y;
      if (error_y >= max_steps) {
        error_y -= max_steps;
        step_y_now = true;
      }
    }
    
    // Execute steps
    if (step_x_now) {
      digitalWrite(X_STEP_PIN, HIGH);
    }
    if (step_y_now) {
      digitalWrite(Y_STEP_PIN, HIGH);
    }
    
    delayMicroseconds(speed);
    
    digitalWrite(X_STEP_PIN, LOW);
    digitalWrite(Y_STEP_PIN, LOW);
    
    delayMicroseconds(speed);
    
    // Check limit switches
    if ((steps_x > 0 && digitalRead(X_LIMIT_MAX_PIN) == LOW) ||
        (steps_x < 0 && digitalRead(X_LIMIT_MIN_PIN) == LOW) ||
        (steps_y > 0 && digitalRead(Y_LIMIT_MAX_PIN) == LOW) ||
        (steps_y < 0 && digitalRead(Y_LIMIT_MIN_PIN) == LOW)) {
      Serial.println("ERROR_LIMIT_SWITCH");
      break;
    }
  }
  
  if (emergency_stop) {
    Serial.println("ERROR_EMERGENCY_STOP");
  } else {
    x_position = new_x;
    y_position = new_y;
    Serial.println("MOVE_DONE");
  }
}

void emergencyStop() {
  emergency_stop = true;
  
  // Disable motors immediately
  digitalWrite(X_ENABLE_PIN, HIGH);
  digitalWrite(Y_ENABLE_PIN, HIGH);
  
  Serial.println("EMERGENCY_STOP_ACTIVATED");
}
