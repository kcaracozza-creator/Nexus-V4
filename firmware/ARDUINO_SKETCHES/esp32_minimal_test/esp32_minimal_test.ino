/*
 * ESP32 MINIMAL TEST - Verify hardware works
 */

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n========================================");
  Serial.println("ESP32 MINIMAL TEST");
  Serial.println("========================================");
  Serial.println("If you see this, ESP32 is working!");
  Serial.println("========================================\n");
}

void loop() {
  Serial.println("Alive...");
  delay(2000);
}
