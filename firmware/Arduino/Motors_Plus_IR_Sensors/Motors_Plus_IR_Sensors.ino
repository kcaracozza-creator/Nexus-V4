/*
   MOTORS + IR SENSORS TEST
   Building up the system step by step
   
   Hardware:
   - Motor 1: DIR=Pin 2, PWM=Pin 5 (card ejection)
   - Motor 2: DIR=Pin 4, PWM=Pin 6 (conveyor)
   - Stage IR (HW201): Pin 9 (detects card on stage)
   - Line IR: Pin 8 (proof of removal - ONLY removal sensor)
   - Removal Logic: Line IR trigger OR timeout (no Photo IR needed)
   
   Serial Commands (9600 baud):
   M1F/M1R/M1S - Motor 1 Forward/Reverse/Stop
   M2F/M2R/M2S - Motor 2 Forward/Reverse/Stop
   S - Status (shows all sensor readings)
*/

// Motor pins
#define MOTOR1_DIR_PIN 2
#define MOTOR1_PWM_PIN 5
#define MOTOR2_DIR_PIN 4
#define MOTOR2_PWM_PIN 6

// IR Sensor pins
#define STAGE_IR_PIN 9      // HW201 - Card on stage
#define LINE_IR_PIN 8       // Proof of removal (ONLY IR for removal)

#define MOTOR_SPEED 200

void setup() {
  Serial.begin(9600);
  
  // Motor pins
  pinMode(MOTOR1_DIR_PIN, OUTPUT);
  pinMode(MOTOR1_PWM_PIN, OUTPUT);
  pinMode(MOTOR2_DIR_PIN, OUTPUT);
  pinMode(MOTOR2_PWM_PIN, OUTPUT);
  
  // IR sensor pins
  pinMode(STAGE_IR_PIN, INPUT);
  pinMode(LINE_IR_PIN, INPUT);
  
  stopMotor1();
  stopMotor2();
  
  Serial.println("MOTORS + IR SENSORS READY");
  Serial.println("Motors: M1(2,5) M2(4,6)");
  Serial.println("IRs: Stage(9) Line(8)");
  Serial.println("Removal: Line IR + Timer fallback");
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    // Motor commands
    if (cmd == "M1F") { motor1Forward(); Serial.println("MOTOR1 FWD"); }
    else if (cmd == "M1R") { motor1Reverse(); Serial.println("MOTOR1 REV"); }
    else if (cmd == "M1S") { stopMotor1(); Serial.println("MOTOR1 STOP"); }
    else if (cmd == "M2F") { motor2Forward(); Serial.println("MOTOR2 FWD"); }
    else if (cmd == "M2R") { motor2Reverse(); Serial.println("MOTOR2 REV"); }
    else if (cmd == "M2S") { stopMotor2(); Serial.println("MOTOR2 STOP"); }
    
    // Status - show all sensor readings
    else if (cmd == "S") {
      int stageIR = digitalRead(STAGE_IR_PIN);
      int lineIR = digitalRead(LINE_IR_PIN);
      
      Serial.print("STATUS: Stage=");
      Serial.print(stageIR);
      Serial.print(" Line=");
      Serial.println(lineIR);
    }
  }
}

// Motor control functions
void motor1Forward() { digitalWrite(MOTOR1_DIR_PIN, HIGH); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void motor1Reverse() { digitalWrite(MOTOR1_DIR_PIN, LOW); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void stopMotor1() { analogWrite(MOTOR1_PWM_PIN, 0); }

void motor2Forward() { digitalWrite(MOTOR2_DIR_PIN, HIGH); analogWrite(MOTOR2_PWM_PIN, MOTOR_SPEED); }
void motor2Reverse() { digitalWrite(MOTOR2_DIR_PIN, LOW); analogWrite(MOTOR2_PWM_PIN, MOTOR_SPEED); }
void stopMotor2() { analogWrite(MOTOR2_PWM_PIN, 0); }
