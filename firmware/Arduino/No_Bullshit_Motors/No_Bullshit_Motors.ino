/*
   NO BULLSHIT MOTORS - Motors and IR Sensors
   No NeoPixels, no HW201, no camera - just functionality
   
   Hardware:
   - Motor 1: DIR=Pin 3, PWM=Pin 6 (card ejection)
   - Motor 2: DIR=Pin 4, PWM=Pin 5 (conveyor/feed)
   - Line IR: Pin 8 (CARD STAGED - ready to eject)
   - Photo IR: Pin A0 (EJECTION PROOF - card cleared)
   
   Serial Commands (9600 baud):
   M1F/M1R/M1S - Motor 1 Forward/Reverse/Stop
   M2F/M2R/M2S - Motor 2 Forward/Reverse/Stop
   A - Toggle AUTO mode
   S - Status
*/

// Motor pins
#define MOTOR1_DIR_PIN 3
#define MOTOR1_PWM_PIN 6
#define MOTOR2_DIR_PIN 4
#define MOTOR2_PWM_PIN 5

// Sensors
#define LINE_IR_PIN 11    // Card prepped (ready for photo)
#define PHOTO_IR_PIN A0   // Ejection proof (card cleared)

// Constants
#define MOTOR_SPEED 200
#define REMOVAL_WAIT_TIME 3000
#define FEED_SPEED 250

// State machine
enum State {
  IDLE,
  FEEDING,
  CARD_STAGED,
  REMOVAL_RUNNING,
  EJECTING,
  READY_FOR_PHOTO
};

State currentState = IDLE;
unsigned long stateTimer = 0;
bool autoMode = false;

void setup() {
  Serial.begin(9600);
  
  // Motors
  pinMode(MOTOR1_DIR_PIN, OUTPUT);
  pinMode(MOTOR1_PWM_PIN, OUTPUT);
  pinMode(MOTOR2_DIR_PIN, OUTPUT);
  pinMode(MOTOR2_PWM_PIN, OUTPUT);
  
  // Sensors
  pinMode(LINE_IR_PIN, INPUT);
  pinMode(PHOTO_IR_PIN, INPUT);
  
  stopMotor1();
  stopMotor2();
  
  Serial.println("NO BULLSHIT MOTORS - READY");
  Serial.println("Motors: M1(2,5) M2(4,6)");
  Serial.println("Line IR: Pin 8 (Card Prepped)");
  Serial.println("Photo IR: Pin A0 (Ejection Proof)");
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
    
    else if (cmd == "P") {  // Photo complete, proceed to next card
      if (currentState == READY_FOR_PHOTO) {
        Serial.println("PHOTO DONE - NEXT CARD");
        currentState = FEEDING;
        motor2Forward();
      }
    }
    
    else if (cmd == "A") { 
      autoMode = !autoMode; 
      if (autoMode) {
        Serial.println("AUTO MODE ON");
        currentState = FEEDING;
        motor2Forward();
        Serial.println("MOTOR2 STARTED");
      } else {
        Serial.println("AUTO MODE OFF");
        currentState = IDLE;
        stopMotor1();
        stopMotor2();
      }
    }
    
    else if (cmd == "S") {
      int lineIR = digitalRead(LINE_IR_PIN);
      int photoIR = digitalRead(PHOTO_IR_PIN);
      Serial.print("STATUS: LineIR=");
      Serial.print(lineIR);
      Serial.print(" PhotoIR=");
      Serial.print(photoIR);
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
  int cardStaged = digitalRead(LINE_IR_PIN);     // Card ready to eject
  int cardEjected = digitalRead(PHOTO_IR_PIN);   // Card cleared stage
  
  switch(currentState) {
    case FEEDING:
      if (cardStaged == LOW) {  // LOW = card detected, stop and stage
        stopMotor2();
        currentState = CARD_STAGED;
        stateTimer = millis();
        Serial.println("CARD STAGED");
      }
      // Motor already running from A command, just check for stop condition
      break;
      
    case CARD_STAGED:
      // Start removal conveyor to clear last card
      motor1Forward();
      currentState = REMOVAL_RUNNING;
      stateTimer = millis();
      Serial.println("REMOVING LAST CARD");
      break;
      
    case REMOVAL_RUNNING:
      // Run removal for 3 seconds
      if (millis() - stateTimer >= REMOVAL_WAIT_TIME) {
        stopMotor1();
        Serial.println("EJECTING NEW CARD");
        currentState = EJECTING;
        motor2Forward();  // Eject the waiting card
      }
      break;
      
    case EJECTING:
      if (cardEjected == HIGH) {  // Photo IR detects card in position
        stopMotor2();
        Serial.println("READY FOR PHOTO");
        currentState = READY_FOR_PHOTO;
      }
      break;
      
    case READY_FOR_PHOTO:
      // Wait for Python "P" command
      break;
  }
}

// Motor control
void motor1Forward() { digitalWrite(MOTOR1_DIR_PIN, HIGH); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void motor1Reverse() { digitalWrite(MOTOR1_DIR_PIN, LOW); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void stopMotor1() { analogWrite(MOTOR1_PWM_PIN, 0); }

void motor2Forward() { digitalWrite(MOTOR2_DIR_PIN, LOW); analogWrite(MOTOR2_PWM_PIN, FEED_SPEED); }
void motor2Reverse() { digitalWrite(MOTOR2_DIR_PIN, HIGH); analogWrite(MOTOR2_PWM_PIN, FEED_SPEED); }
void stopMotor2() { analogWrite(MOTOR2_PWM_PIN, 0); }
