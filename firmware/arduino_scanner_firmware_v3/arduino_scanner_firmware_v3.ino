/*
   MTTGG Arduino Card Scanner Firmware v3.3 WITH-IR
   Enhanced Version for Arduino Uno - HW201 IR Sensors for Precise Control
   
   Hardware Setup:
   - Motor 1: Card ejection (Dir: Pin 2, PWM: Pin 5)
   - Motor 2: Conveyor belt (Dir: Pin 4, PWM: Pin 6)  
   - Line Sensor: Detect card position (Pin A0)
   - HW201 IR Sensor 1: Card ejection detection (Pin 7)
   - HW201 IR Sensor 2: Card position confirmation (Pin A1)
   - NeoPixel Strip: Status indication (Pin 9)
   - Manual Button: Pin 3, Emergency Stop: Pin 8
   - LED indicators: Ready(13), Scanning(12), Error(11)
   
   Communication: Simple Serial Commands (9600 baud)
   Commands: R=Remove, F=Feed, S=Status, C=Calibrate, E=Reset
   Lighting: L=Photography, D=Dim, B=Bright, X=Off, W=White, N=Normal
*/

#include <Adafruit_NeoPixel.h>

// Pin definitions
#define MOTOR1_DIR_PIN 3
#define MOTOR1_PWM_PIN 6
#define MOTOR2_DIR_PIN 4
#define MOTOR2_PWM_PIN 5
#define LINE_SENSOR_PIN A0
#define HW201_IR1_PIN 7        // IR sensor for ejection detection
#define HW201_IR2_PIN A1       // IR sensor for position confirmation
#define NEOPIXEL_PIN 9
#define NEOPIXEL_COUNT 8
#define LED_READY_PIN 13
#define LED_SCANNING_PIN 12
#define LED_ERROR_PIN 11
#define BUTTON_MANUAL_PIN 3
#define BUTTON_STOP_PIN 8

// Constants
const int LINE_SENSOR_THRESHOLD = 300;
const int SENSOR_DEBOUNCE = 50;
const int REMOVAL_TIMEOUT = 15000;
const int DELAY_BEFORE_REMOVAL_TIME = 3000;
const int EJECT_CLEAR_TIMEOUT = 1000;
const int LINE_SENSOR_SETTLE_TIME = 200;
const int SLOW_MOTOR_SPEED = 64;
const int HALF_MOTOR_SPEED = 127;
const int FULL_MOTOR_SPEED = 255;
const int FEED_TIMEOUT = 10000;
const int PROOF_OF_DISPOSAL_DELAY = 1000;

// NeoPixel setup
Adafruit_NeoPixel strip(NEOPIXEL_COUNT, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

// System states - Simplified without IR dependencies
enum SystemState {
  AWAITING_COMMAND,
  FEED_CARD,
  CARD_EJECTION,
  POSITION_CONFIRMATION,
  DELAY_BEFORE_REMOVAL_STATE,
  REMOVE_CARD,
  CARD_DISPOSAL,
  PROOF_OF_DISPOSAL,
  ERROR_STATE
};

// State variables
SystemState currentState = AWAITING_COMMAND;
bool systemReady = false;
bool cardInPosition = false;
bool emergencyStop = false;
unsigned long stateStartTime = 0;

// Sensor readings - Line sensor + HW201 IR sensors
int lineSensorReading = 0;
int lineSensorBaseline = 512;
bool hw201_ir1_detected = false;  // Ejection detection
bool hw201_ir2_detected = false;  // Position confirmation
unsigned long lastSensorRead = 0;
unsigned long cardEjectionStartTime = 0;
bool singleCardDetected = false;

// Lighting control variables
enum LightingMode {
  LIGHTING_OFF,
  LIGHTING_NORMAL,
  LIGHTING_DIM,
  LIGHTING_BRIGHT,
  LIGHTING_PHOTOGRAPHY,
  LIGHTING_WHITE,
  LIGHTING_RAINBOW,
  LIGHTING_STROBE
};

LightingMode currentLightingMode = LIGHTING_NORMAL;
int lightingBrightness = 128;  // 0-255
uint32_t lightingColor = 0;    // Custom RGB color
unsigned long lightingUpdateTime = 0;
bool lightingActive = true;
int strobeCounter = 0;

// --- Function Prototypes ---
void calibrateLineSensor();
void setNeoPixelReady();
void setNeoPixelError();
void startMotor1(int speed);
void stopMotor1();
void startMotor2(int speed);
void stopMotor2();
void stopAllMotors();
void resetSystem();
bool isCardInScanPosition();
void updateLEDs();
void updateNeoPixels();
void handleSerialCommands();
void setNeoPixelColor(uint32_t color);
void setLightingMode(LightingMode mode);
void updateLighting();
void setPhotographyLighting();
void setCustomColor(int red, int green, int blue);
void adjustBrightness(int brightness);
void handleLightingCommands(char command);

void setup() {
  Serial.begin(9600);
  
  // Initialize NeoPixel
  strip.begin();
  strip.clear();
  strip.show();
  
  // Configure pins
  pinMode(MOTOR1_DIR_PIN, OUTPUT);
  pinMode(MOTOR1_PWM_PIN, OUTPUT);
  pinMode(MOTOR2_DIR_PIN, OUTPUT);
  pinMode(MOTOR2_PWM_PIN, OUTPUT);
  pinMode(HW201_IR1_PIN, INPUT_PULLUP);     // IR sensor 1 (ejection)
  pinMode(HW201_IR2_PIN, INPUT_PULLUP);     // IR sensor 2 (position) - if digital
  pinMode(LED_READY_PIN, OUTPUT);
  pinMode(LED_SCANNING_PIN, OUTPUT);
  pinMode(LED_ERROR_PIN, OUTPUT);
  pinMode(BUTTON_MANUAL_PIN, INPUT_PULLUP);
  pinMode(BUTTON_STOP_PIN, INPUT_PULLUP);
  
  // Set initial motor directions (assuming HIGH is forward)
  digitalWrite(MOTOR1_DIR_PIN, HIGH);
  digitalWrite(MOTOR2_DIR_PIN, HIGH);
  analogWrite(MOTOR1_PWM_PIN, 0);
  analogWrite(MOTOR2_PWM_PIN, 0);
  
  // Initialize LEDs
  digitalWrite(LED_ERROR_PIN, LOW);
  digitalWrite(LED_SCANNING_PIN, LOW);
  digitalWrite(LED_READY_PIN, HIGH);
  
  // Calibrate line sensor
  calibrateLineSensor();
  setLightingMode(LIGHTING_NORMAL);
  
  systemReady = true;
  currentState = AWAITING_COMMAND;
  
  Serial.println(F("MTTGG Scanner WITH-IR Ready"));
}

void loop() {
  updateSensors();
  checkButtons();
  processStateMachine();
  handleSerialCommands();
  updateLEDs();
  updateLighting();
  
  delay(10);
}

void updateSensors() {
  unsigned long currentTime = millis();
  
  if (currentTime - lastSensorRead >= SENSOR_DEBOUNCE) {
    // Read line sensor
    lineSensorReading = analogRead(LINE_SENSOR_PIN);
    
    // Read HW201 IR sensors (LOW = object detected for most IR sensors)
    hw201_ir1_detected = !digitalRead(HW201_IR1_PIN);  // Ejection detection
    
    // IR2 can be analog or digital depending on connection
    #ifdef HW201_IR2_ANALOG
      hw201_ir2_detected = analogRead(HW201_IR2_PIN) < 512;  // Threshold for analog
    #else
      hw201_ir2_detected = !digitalRead(HW201_IR2_PIN);      // Digital read
    #endif
    
    lastSensorRead = currentTime;
  }
}

void checkButtons() {
  static bool lastStopButton = true;
  bool stopButton = digitalRead(BUTTON_STOP_PIN);
  
  if (lastStopButton && !stopButton) {
    emergencyStop = true;
    stopAllMotors();
    currentState = ERROR_STATE;
    stateStartTime = millis();
    setNeoPixelError();
    Serial.println(F("EMERGENCY STOP"));
  }
  lastStopButton = stopButton;
  
  static bool lastManualButton = true;
  bool manualButton = digitalRead(BUTTON_MANUAL_PIN);
  
  if (lastManualButton && !manualButton) {
    if (currentState == AWAITING_COMMAND && !emergencyStop) {
      currentState = FEED_CARD;
      stateStartTime = millis();
      Serial.println(F("MANUAL FEED"));
    } else if (currentState == ERROR_STATE) {
      resetSystem();
    }
  }
  lastManualButton = manualButton;
}

void processStateMachine() {
  unsigned long currentTime = millis();
  
  switch (currentState) {
    case AWAITING_COMMAND:
      // Handled in handleSerialCommands()
      break;
      
    case FEED_CARD:
      startMotor1(SLOW_MOTOR_SPEED);
      // Feed until IR sensor detects card or timeout
      if (hw201_ir1_detected && !singleCardDetected) {
        singleCardDetected = true;
        cardEjectionStartTime = currentTime;
        Serial.println(F("SINGLE CARD DETECTED"));
      }
      
      if (singleCardDetected && (currentTime - cardEjectionStartTime > 500)) {
        // Stop after card detected and brief delay
        stopMotor1();
        singleCardDetected = false;
        Serial.println(F("FEED COMPLETE - SINGLE CARD"));
        currentState = AWAITING_COMMAND;
      } else if (currentTime - stateStartTime > FEED_TIMEOUT) {
        stopMotor1();
        singleCardDetected = false;
        Serial.println(F("FEED TIMEOUT"));
        currentState = ERROR_STATE;
        stateStartTime = currentTime;
      }
      break;
      
    case CARD_EJECTION:
      startMotor1(FULL_MOTOR_SPEED);
      // Eject until IR sensor confirms card has passed (for single card)
      if (hw201_ir1_detected && !singleCardDetected) {
        singleCardDetected = true;
        cardEjectionStartTime = currentTime;
        Serial.println(F("CARD PASSING IR1"));
      }
      
      // Stop when card has completely passed IR sensor
      if (singleCardDetected && !hw201_ir1_detected && 
          (currentTime - cardEjectionStartTime > 200)) {
        stopMotor1();
        stateStartTime = currentTime;
        currentState = POSITION_CONFIRMATION;
        singleCardDetected = false;
        Serial.println(F("EJECTED - SINGLE CARD CONFIRMED"));
      } else if (currentTime - stateStartTime >= EJECT_CLEAR_TIMEOUT + 5000) {
        stopMotor1();
        singleCardDetected = false;
        Serial.println(F("EJECT TIMEOUT"));
        currentState = ERROR_STATE;
        stateStartTime = currentTime;
      }
      break;
      
    case POSITION_CONFIRMATION:
      // Use IR2 sensor to confirm card is in scan position
      if (hw201_ir2_detected || isCardInScanPosition()) {
        cardInPosition = true;
        currentState = DELAY_BEFORE_REMOVAL_STATE;
        stateStartTime = currentTime;
        Serial.println(F("POSITIONED - IR CONFIRMED"));
      } else if (currentTime - stateStartTime > LINE_SENSOR_SETTLE_TIME + 2000) {
        // Fallback to time-based if IR2 not working
        currentState = DELAY_BEFORE_REMOVAL_STATE;
        stateStartTime = currentTime;
        Serial.println(F("POSITION ASSUMED - IR TIMEOUT"));
      }
      break;
      
    case DELAY_BEFORE_REMOVAL_STATE:
      if (currentTime - stateStartTime > DELAY_BEFORE_REMOVAL_TIME) {
        currentState = REMOVE_CARD;
        Serial.println(F("REMOVING"));
        stateStartTime = currentTime;
      }
      break;
      
    case REMOVE_CARD:
      startMotor2(HALF_MOTOR_SPEED);
      currentState = CARD_DISPOSAL;
      stateStartTime = currentTime;
      break;
      
    case CARD_DISPOSAL:
      // Run conveyor and monitor IR sensors for confirmation
      if (!hw201_ir2_detected && (currentTime - stateStartTime >= 2000)) {
        // Card has cleared IR2 sensor, disposal likely complete
        stopMotor2();
        currentState = PROOF_OF_DISPOSAL;
        stateStartTime = currentTime;
        Serial.println(F("DISPOSED - IR CONFIRMED"));
      } else if (currentTime - stateStartTime >= 8000) {
        // Fallback timeout - longer to ensure removal
        stopMotor2();
        currentState = PROOF_OF_DISPOSAL;
        stateStartTime = currentTime;
        Serial.println(F("DISPOSED - TIMEOUT"));
      } else if (currentTime - stateStartTime >= REMOVAL_TIMEOUT) {
        stopMotor2();
        Serial.println(F("REMOVAL TIMEOUT"));
        currentState = ERROR_STATE;
        stateStartTime = currentTime;
      }
      break;

    case PROOF_OF_DISPOSAL:
      if (currentTime - stateStartTime >= PROOF_OF_DISPOSAL_DELAY) {
        currentState = AWAITING_COMMAND;
        Serial.println(F("COMPLETE"));
      }
      break;
      
    case ERROR_STATE:
      stopAllMotors();
      // Stays in error until manual reset (handled in checkButtons)
      break;

    default:
      currentState = ERROR_STATE;
      break;
  }
}

void handleSerialCommands() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    if (currentState == AWAITING_COMMAND || currentState == ERROR_STATE) {
      if (command == 'R' || command == 'r') {
        if (!emergencyStop) {
          Serial.println(F("EJECTING"));
          currentState = CARD_EJECTION;
          stateStartTime = millis();
        }
      } else if (command == 'F' || command == 'f') {
        if (!emergencyStop) {
          Serial.println(F("FEEDING"));
          currentState = FEED_CARD;
          stateStartTime = millis();
        }
      } else if (command == 'C' || command == 'c') {
        calibrateLineSensor();
        Serial.println(F("CALIBRATED"));
      } else if (command == 'E' || command == 'e') {
        resetSystem();
        Serial.println(F("SYSTEM RESET"));
      } else if (command == 'S' || command == 's') {
        Serial.print(F("STATUS: "));
        Serial.print(getStateString());
        Serial.print(F(" IR1:"));
        Serial.print(hw201_ir1_detected ? "1" : "0");
        Serial.print(F(" IR2:"));
        Serial.print(hw201_ir2_detected ? "1" : "0");
        Serial.print(F(" LINE:"));
        Serial.println(lineSensorReading);
      } else if (command == 'V' || command == 'v') {
        Serial.println(F("MTTGG Scanner v3.3 WITH-IR"));
        Serial.println(F("Motors: 4x Servo, IR: 2x HW201"));
        Serial.println(F("Lighting: Advanced NeoPixel Control"));
      } else if (command == '?') {
        Serial.println(F("Commands: S=Status, C=Calibrate, E=Reset, V=Version"));
        Serial.println(F("Lighting: L=Photo, B=Bright, D=Dim, W=White, N=Normal"));
        Serial.println(F("         A=Rainbow, T=Strobe, X=Off, 1-4=Brightness"));
        Serial.println(F("Colors: R=Red, G=Green"));
      } else {
        // Check for lighting commands
        handleLightingCommands(command);
      }
    }
  }
}

void updateLEDs() {
  digitalWrite(LED_READY_PIN, (currentState == AWAITING_COMMAND));
  digitalWrite(LED_SCANNING_PIN, (currentState == POSITION_CONFIRMATION || currentState == DELAY_BEFORE_REMOVAL_STATE));
  digitalWrite(LED_ERROR_PIN, (currentState == ERROR_STATE));
}

void updateNeoPixels() {
  // This function is now handled by updateLighting()
  // Keeping for compatibility
}

// --- Advanced Lighting Control Functions ---

void setLightingMode(LightingMode mode) {
  currentLightingMode = mode;
  lightingUpdateTime = millis();
  strobeCounter = 0;
  
  switch(mode) {
    case LIGHTING_OFF:
      strip.clear();
      strip.show();
      break;
    case LIGHTING_NORMAL:
      setNeoPixelReady();
      break;
    case LIGHTING_PHOTOGRAPHY:
      setPhotographyLighting();
      break;
    case LIGHTING_WHITE:
      setCustomColor(255, 255, 255);
      break;
    default:
      updateLighting();
      break;
  }
}

void updateLighting() {
  unsigned long currentTime = millis();
  
  if (!lightingActive) return;
  
  switch(currentLightingMode) {
    case LIGHTING_OFF:
      strip.clear();
      strip.show();
      break;
      
    case LIGHTING_NORMAL:
      // State-based lighting
      switch(currentState) {
        case AWAITING_COMMAND:
          setNeoPixelReady();
          break;
        case ERROR_STATE:
          if (currentTime - lightingUpdateTime > 500) {
            static bool errorToggle = false;
            if (errorToggle) setNeoPixelError();
            else strip.clear(), strip.show();
            errorToggle = !errorToggle;
            lightingUpdateTime = currentTime;
          }
          break;
        case POSITION_CONFIRMATION:
        case DELAY_BEFORE_REMOVAL_STATE:
          setNeoPixelColor(strip.Color(255, 255, 255)); // White for scanning
          break;
        default:
          setNeoPixelColor(strip.Color(0, 0, 255)); // Blue for working
          break;
      }
      break;
      
    case LIGHTING_DIM:
      for(int i=0; i<NEOPIXEL_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(32, 32, 32));
      }
      strip.show();
      break;
      
    case LIGHTING_BRIGHT:
      for(int i=0; i<NEOPIXEL_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(255, 255, 255));
      }
      strip.show();
      break;
      
    case LIGHTING_PHOTOGRAPHY:
      // Optimized for card photography - warm white
      for(int i=0; i<NEOPIXEL_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(255, 220, 180));
      }
      strip.show();
      break;
      
    case LIGHTING_WHITE:
      // Pure white
      for(int i=0; i<NEOPIXEL_COUNT; i++) {
        strip.setPixelColor(i, strip.Color(255, 255, 255));
      }
      strip.show();
      break;
      
    case LIGHTING_RAINBOW:
      // Rainbow cycle
      if (currentTime - lightingUpdateTime > 50) {
        static int rainbowIndex = 0;
        for(int i=0; i<NEOPIXEL_COUNT; i++) {
          strip.setPixelColor(i, wheel((i + rainbowIndex) & 255));
        }
        strip.show();
        rainbowIndex++;
        if (rainbowIndex >= 256) rainbowIndex = 0;
        lightingUpdateTime = currentTime;
      }
      break;
      
    case LIGHTING_STROBE:
      // Strobe effect
      if (currentTime - lightingUpdateTime > 100) {
        strobeCounter++;
        if (strobeCounter % 2 == 0) {
          for(int i=0; i<NEOPIXEL_COUNT; i++) {
            strip.setPixelColor(i, strip.Color(255, 255, 255));
          }
        } else {
          strip.clear();
        }
        strip.show();
        lightingUpdateTime = currentTime;
      }
      break;
  }
}

void setPhotographyLighting() {
  // Optimized lighting for DSLR card photography
  // Warm white with high CRI equivalent
  for(int i=0; i<NEOPIXEL_COUNT; i++) {
    strip.setPixelColor(i, strip.Color(255, 220, 180));
  }
  strip.setBrightness(255); // Maximum brightness
  strip.show();
}

void setCustomColor(int red, int green, int blue) {
  // Apply brightness scaling
  red = (red * lightingBrightness) / 255;
  green = (green * lightingBrightness) / 255;
  blue = (blue * lightingBrightness) / 255;
  
  for(int i=0; i<NEOPIXEL_COUNT; i++) {
    strip.setPixelColor(i, strip.Color(red, green, blue));
  }
  strip.show();
}

void adjustBrightness(int brightness) {
  lightingBrightness = constrain(brightness, 0, 255);
  updateLighting(); // Refresh with new brightness
}

void handleLightingCommands(char command) {
  switch(command) {
    case 'L': case 'l':
      setLightingMode(LIGHTING_PHOTOGRAPHY);
      Serial.println(F("PHOTOGRAPHY LIGHTING"));
      break;
      
    case 'D': case 'd':
      setLightingMode(LIGHTING_DIM);
      Serial.println(F("DIM LIGHTING"));
      break;
      
    case 'B': case 'b':
      setLightingMode(LIGHTING_BRIGHT);
      Serial.println(F("BRIGHT LIGHTING"));
      break;
      
    case 'X': case 'x':
      setLightingMode(LIGHTING_OFF);
      Serial.println(F("LIGHTING OFF"));
      break;
      
    case 'W': case 'w':
      setLightingMode(LIGHTING_WHITE);
      Serial.println(F("WHITE LIGHTING"));
      break;
      
    case 'N': case 'n':
      setLightingMode(LIGHTING_NORMAL);
      Serial.println(F("NORMAL LIGHTING"));
      break;
      
    case 'A': case 'a':
      setLightingMode(LIGHTING_RAINBOW);
      Serial.println(F("RAINBOW LIGHTING"));
      break;
      
    case 'T': case 't':
      setLightingMode(LIGHTING_STROBE);
      Serial.println(F("STROBE LIGHTING"));
      break;
      
    case '1':
      adjustBrightness(64);   // 25%
      Serial.println(F("BRIGHTNESS 25%"));
      break;
      
    case '2':
      adjustBrightness(128);  // 50%
      Serial.println(F("BRIGHTNESS 50%"));
      break;
      
    case '3':
      adjustBrightness(192);  // 75%
      Serial.println(F("BRIGHTNESS 75%"));
      break;
      
    case '4':
      adjustBrightness(255);  // 100%
      Serial.println(F("BRIGHTNESS 100%"));
      break;
      
    case 'R': case 'r':
      // Red color
      setCustomColor(255, 0, 0);
      Serial.println(F("RED COLOR"));
      break;
      
    case 'G': case 'g':
      // Green color
      setCustomColor(0, 255, 0);
      Serial.println(F("GREEN COLOR"));
      break;
      
    default:
      Serial.print(F("UNKNOWN LIGHTING: "));
      Serial.println(command);
      break;
  }
}

// Rainbow color wheel function
uint32_t wheel(byte wheelPos) {
  wheelPos = 255 - wheelPos;
  if(wheelPos < 85) {
    return strip.Color(255 - wheelPos * 3, 0, wheelPos * 3);
  }
  if(wheelPos < 170) {
    wheelPos -= 85;
    return strip.Color(0, wheelPos * 3, 255 - wheelPos * 3);
  }
  wheelPos -= 170;
  return strip.Color(wheelPos * 3, 255 - wheelPos * 3, 0);
}

// --- Helper Functions ---

void calibrateLineSensor() {
  int total = 0;
  for (int i = 0; i < 20; i++) {
    total += analogRead(LINE_SENSOR_PIN);
    delay(20);
  }
  lineSensorBaseline = total / 20;
  Serial.print(F("Baseline set to: "));
  Serial.println(lineSensorBaseline);
}

void setNeoPixelColor(uint32_t color) {
  for(int i=0; i<NEOPIXEL_COUNT; i++) {
    strip.setPixelColor(i, color);
  }
  strip.show();
}

void setNeoPixelReady() {
  setNeoPixelColor(strip.Color(0, 255, 0)); // Green
}

void setNeoPixelError() {
  setNeoPixelColor(strip.Color(255, 0, 0)); // Red
}

void startMotor1(int speed) {
  // Assuming HIGH is correct direction for M1
  digitalWrite(MOTOR1_DIR_PIN, HIGH); 
  analogWrite(MOTOR1_PWM_PIN, speed);
}

void stopMotor1() {
  analogWrite(MOTOR1_PWM_PIN, 0);
}

void startMotor2(int speed) {
  // Assuming HIGH is correct direction for M2
  digitalWrite(MOTOR2_DIR_PIN, HIGH);
  analogWrite(MOTOR2_PWM_PIN, speed);
}

void stopMotor2() {
  analogWrite(MOTOR2_PWM_PIN, 0);
}

void stopAllMotors() {
  analogWrite(MOTOR1_PWM_PIN, 0);
  analogWrite(MOTOR2_PWM_PIN, 0);
}

void resetSystem() {
  emergencyStop = false;
  currentState = AWAITING_COMMAND;
  stopAllMotors();
  setNeoPixelReady();
  Serial.println(F("SYSTEM RESET AND READY"));
}

bool isCardInScanPosition() {
  // Logic: When a card is present, the line sensor reading should be significantly different
  // from the baseline. Assuming a reflective sensor and a reflective card, the reading should go up.
  return (lineSensorReading > lineSensorBaseline + LINE_SENSOR_THRESHOLD) || 
         (lineSensorReading < lineSensorBaseline - LINE_SENSOR_THRESHOLD);
}

const char* getStateString() {
  switch (currentState) {
    case CARD_EJECTION: return "EJECTING";
    case POSITION_CONFIRMATION: return "CONFIRMING";
    case DELAY_BEFORE_REMOVAL_STATE: return "WAITING";
    case REMOVE_CARD: return "REMOVING";
    case CARD_DISPOSAL: return "DISPOSING";
    case PROOF_OF_DISPOSAL: return "PROVING";
    case AWAITING_COMMAND: return "READY";
    case FEED_CARD: return "FEEDING";
    case ERROR_STATE: return "ERROR";
    default: return "UNKNOWN";
  }
}