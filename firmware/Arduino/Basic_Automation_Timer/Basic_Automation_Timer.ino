/*
   BASIC AUTOMATION - Motors + Stage IR + Timer
   Simple card scanning automation without finicky sensors
   
   Hardware:
   - Motor 1: DIR=Pin 2, PWM=Pin 5 (card ejection)
   - Motor 2: DIR=Pin 4, PWM=Pin 6 (conveyor)
   - Stage IR (HW201): Pin 9 (detects card on stage)
   - Line IR: Pin 8 (ejection proof - stops ejection motor)
   
   Workflow:
   1. Wait for card on Stage IR
   2. Stop conveyor, signal ready for photo
   3. After photo complete command, eject card
   4. Line IR detects card passing → stop ejection
   5. Wait timer (assume card clears) then ready for next
   
   Serial Commands (9600 baud):
   M1F/M1R/M1S - Motor 1 Forward/Reverse/Stop
   M2F/M2R/M2S - Motor 2 Forward/Reverse/Stop
   A - Start AUTO mode (full automation)
   S - Status
   P - Photo complete (triggers ejection)
*/

// Motor pins
#define MOTOR1_DIR_PIN 2
#define MOTOR1_PWM_PIN 5
#define MOTOR2_DIR_PIN 4
#define MOTOR2_PWM_PIN 6

// Sensor
#define STAGE_IR_PIN 9
#define LINE_IR_PIN 8     // Ejection proof

// Timing constants
#define MOTOR_SPEED 200
#define REMOVAL_WAIT_TIME 1500 // 1.5 seconds wait after Line IR triggers
#define FEED_SPEED 150         // Conveyor speed

// State machine
enum State {
  IDLE,
  FEEDING,
  CARD_READY,
  WAITING_FOR_PHOTO,
  EJECTING,
  WAITING_REMOVAL
};

State currentState = IDLE;
unsigned long stateTimer = 0;
bool autoMode = false;

void setup() {
  Serial.begin(9600);
  
  pinMode(MOTOR1_DIR_PIN, OUTPUT);
  pinMode(MOTOR1_PWM_PIN, OUTPUT);
  pinMode(MOTOR2_DIR_PIN, OUTPUT);
  pinMode(MOTOR2_PWM_PIN, OUTPUT);
  pinMode(STAGE_IR_PIN, INPUT);
  pinMode(LINE_IR_PIN, INPUT);
  
  stopMotor1();
  stopMotor2();
  
  Serial.println("BASIC AUTOMATION READY");
  Serial.println("Motors: M1(2,5) M2(4,6)");
  Serial.println("Stage IR: Pin 9");
  Serial.println("Line IR: Pin 8 (Ejection Proof)");
}

void loop() {
  // Handle serial commands
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "M1F") { motor1Forward(); Serial.println("MOTOR1 FWD"); }
    else if (cmd == "M1R") { motor1Reverse(); Serial.println("MOTOR1 REV"); }
    else if (cmd == "M1S") { stopMotor1(); Serial.println("MOTOR1 STOP"); }
    else if (cmd == "M2F") { motor2Forward(); Serial.println("MOTOR2 FWD"); }
    else if (cmd == "M2R") { motor2Reverse(); Serial.println("MOTOR2 REV"); }
    else if (cmd == "M2S") { stopMotor2(); Serial.println("MOTOR2 STOP"); }
    else if (cmd == "A") { 
      autoMode = !autoMode; 
      if (autoMode) {
        Serial.println("AUTO MODE ON");
        currentState = FEEDING;
        motor2Forward();
      } else {
        Serial.println("AUTO MODE OFF");
        currentState = IDLE;
        stopMotor1();
        stopMotor2();
      }
    }
    else if (cmd == "P") {
      if (currentState == WAITING_FOR_PHOTO) {
        Serial.println("PHOTO COMPLETE - EJECTING");
        currentState = EJECTING;
        stateTimer = millis();
        motor1Forward();
      }
    }
    else if (cmd == "S") {
      int stageIR = digitalRead(STAGE_IR_PIN);
      int lineIR = digitalRead(LINE_IR_PIN);
      Serial.print("STATUS: Stage=");
      Serial.print(stageIR);
      Serial.print(" Line=");
      Serial.print(lineIR);
      Serial.print(" State=");
      Serial.println(currentState);
    }
  }
  
  // Auto mode state machine
  if (autoMode) {
    runAutoMode();
  }
}

void runAutoMode() {
  int cardPresent = digitalRead(STAGE_IR_PIN);
  int lineTriggered = digitalRead(LINE_IR_PIN);
  
  switch(currentState) {
    case FEEDING:
      // Wait for card to reach stage
      if (cardPresent == LOW) { // Card detected
        stopMotor2();
        currentState = CARD_READY;
        Serial.println("CARD READY");
      }
      break;
      
    case CARD_READY:
      // Signal ready for photo
      Serial.println("READY_FOR_PHOTO");
      currentState = WAITING_FOR_PHOTO;
      break;
      
    case WAITING_FOR_PHOTO:
      // Wait for "P" command from Python
      break;
      
    case EJECTING:
      // Eject until Line IR triggers (card passing)
      if (lineTriggered == LOW) { // Card detected by Line IR
        stopMotor1();
        currentState = WAITING_REMOVAL;
        stateTimer = millis();
        Serial.println("LINE IR TRIGGERED - WAITING CLEAR");
      }
      break;
      
    case WAITING_REMOVAL:
      // Wait for card to clear, then feed next
      if (millis() - stateTimer >= REMOVAL_WAIT_TIME) {
        Serial.println("CARD CLEARED - NEXT");
        currentState = FEEDING;
        motor2Forward();
      }
      break;
  }
}

// Motor control
void motor1Forward() { digitalWrite(MOTOR1_DIR_PIN, HIGH); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void motor1Reverse() { digitalWrite(MOTOR1_DIR_PIN, LOW); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void stopMotor1() { analogWrite(MOTOR1_PWM_PIN, 0); }

void motor2Forward() { digitalWrite(MOTOR2_DIR_PIN, HIGH); analogWrite(MOTOR2_PWM_PIN, FEED_SPEED); }
void motor2Reverse() { digitalWrite(MOTOR2_DIR_PIN, LOW); analogWrite(MOTOR2_PWM_PIN, FEED_SPEED); }
void stopMotor2() { analogWrite(MOTOR2_PWM_PIN, 0); }
