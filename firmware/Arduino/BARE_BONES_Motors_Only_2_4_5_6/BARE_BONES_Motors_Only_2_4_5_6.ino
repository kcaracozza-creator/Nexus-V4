/*
   BARE BONES - MOTORS ONLY TEST
   Just 2 motors, nothing else. Zero frills.
   
   Motor Pins (INLAND/L298N Standard):
   - Motor 1: DIR=Pin 2, PWM=Pin 5 (card ejection)
   - Motor 2: DIR=Pin 4, PWM=Pin 6 (conveyor)
   
   Serial Commands (9600 baud):
   M1F/M1R/M1S - Motor 1 Forward/Reverse/Stop
   M2F/M2R/M2S - Motor 2 Forward/Reverse/Stop
   S - Status check
*/

// Motor pins - INLAND shield standard
#define MOTOR1_DIR_PIN 2
#define MOTOR1_PWM_PIN 5
#define MOTOR2_DIR_PIN 4
#define MOTOR2_PWM_PIN 6

#define MOTOR_SPEED 200  // 80% speed

void setup() {
  Serial.begin(9600);
  
  pinMode(MOTOR1_DIR_PIN, OUTPUT);
  pinMode(MOTOR1_PWM_PIN, OUTPUT);
  pinMode(MOTOR2_DIR_PIN, OUTPUT);
  pinMode(MOTOR2_PWM_PIN, OUTPUT);
  
  stopMotor1();
  stopMotor2();
  
  Serial.println("BARE BONES - MOTORS ONLY");
  Serial.println("M1: Pins 2,5 | M2: Pins 4,6");
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "M1F") { motor1Forward(); Serial.println("MOTOR1 FWD"); }
    else if (cmd == "M1R") { motor1Reverse(); Serial.println("MOTOR1 REV"); }
    else if (cmd == "M1S") { stopMotor1(); Serial.println("MOTOR1 STOP"); }
    else if (cmd == "M2F") { motor2Forward(); Serial.println("MOTOR2 FWD"); }
    else if (cmd == "M2R") { motor2Reverse(); Serial.println("MOTOR2 REV"); }
    else if (cmd == "M2S") { stopMotor2(); Serial.println("MOTOR2 STOP"); }
    else if (cmd == "S") { Serial.println("READY"); }
  }
}

void motor1Forward() { digitalWrite(MOTOR1_DIR_PIN, HIGH); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void motor1Reverse() { digitalWrite(MOTOR1_DIR_PIN, LOW); analogWrite(MOTOR1_PWM_PIN, MOTOR_SPEED); }
void stopMotor1() { analogWrite(MOTOR1_PWM_PIN, 0); }

void motor2Forward() { digitalWrite(MOTOR2_DIR_PIN, HIGH); analogWrite(MOTOR2_PWM_PIN, MOTOR_SPEED); }
void motor2Reverse() { digitalWrite(MOTOR2_DIR_PIN, LOW); analogWrite(MOTOR2_PWM_PIN, MOTOR_SPEED); }
void stopMotor2() { analogWrite(MOTOR2_PWM_PIN, 0); }
