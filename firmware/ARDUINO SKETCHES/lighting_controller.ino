/*
 * NEXUS Card Scanner - Lighting Controller
 * Dual NeoPixel Ring (16 LEDs each) for consistent card illumination
 * 
 * Hardware:
 * - 2x NeoPixel Ring 16 LEDs
 * - ESP32 DevKit
 * - 5V Power Supply (3A+ recommended for 32 LEDs at full brightness)
 * 
 * Connections:
 * - Ring 1 Data Pin -> ESP32 GPIO 16
 * - Ring 2 Data Pin -> ESP32 GPIO 17
 * - Both Rings 5V -> External 5V Power Supply
 * - Both Rings GND -> Common Ground (ESP32 + Power Supply)
 * 
 * Control via:
 * - Serial (115200 baud)
 * - WiFi HTTP API (http://ESP32_IP/command?cmd=ON)
 * 
 * Commands:
 * - "ON" - Turn on both rings (white, full brightness)
 * - "OFF" - Turn off both rings
 * - "BRIGHT:X" - Set brightness (0-255)
 * - "COLOR:R,G,B" - Set color (e.g., "COLOR:255,255,255" for white)
 * - "TEMP:X" - Set color temperature (2700-6500K)
 * - "TEST" - Run test pattern (rainbow)
 * - "STATUS" - Print current settings
 */

#include <Adafruit_NeoPixel.h>
#include <WiFi.h>
#include <WebServer.h>

// WiFi credentials (change these!)
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Web server on port 80
WebServer server(80);

// Pin definitions (ESP32 GPIO)
#define RING1_PIN 16
#define RING2_PIN 17
#define LEDS_PER_RING 16

// Create NeoPixel objects
Adafruit_NeoPixel ring1(LEDS_PER_RING, RING1_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel ring2(LEDS_PER_RING, RING2_PIN, NEO_GRB + NEO_KHZ800);

// Lighting state
bool lightsOn = false;
uint8_t brightness = 200;  // Default 78% brightness (prevents overexposure)
uint8_t red = 255;
uint8_t green = 255;
uint8_t blue = 255;
uint16_t colorTemp = 5000;  // Default 5000K (neutral white for accurate colors)

String inputString = "";
boolean stringComplete = false;

void setup() {
  Serial.begin(115200);
  
  // Initialize NeoPixel rings
  ring1.begin();
  ring2.begin();
  
  // Set initial brightness
  ring1.setBrightness(brightness);
  ring2.setBrightness(brightness);
  
  // Turn off all LEDs
  ring1.clear();
  ring2.clear();
  ring1.show();
  ring2.show();
  
  Serial.println("NEXUS Lighting Controller - ESP32");
  Serial.println("Connecting to WiFi...");
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Setup HTTP endpoints
  server.on("/", handleRoot);
  server.on("/command", handleCommand);
  server.on("/status", handleStatus);
  server.onNotFound(handleNotFound);
  
  server.begin();
  Serial.println("HTTP server started");
  Serial.println("Commands: ON, OFF, BRIGHT:X, COLOR:R,G,B, TEMP:X, TEST, STATUS");
  
  inputString.reserve(64);
}

void loop() {
  // Handle HTTP requests
  server.handleClient();
  
  // Check for serial commands
  if (stringComplete) {
    processCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
}

// HTTP Handlers
void handleRoot() {
  String html = "<html><body><h1>NEXUS Lighting Controller</h1>";
  html += "<p>Status: " + String(lightsOn ? "ON" : "OFF") + "</p>";
  html += "<p>Brightness: " + String(brightness) + "</p>";
  html += "<p>Color: RGB(" + String(red) + "," + String(green) + "," + String(blue) + ")</p>";
  html += "<p>Temp: " + String(colorTemp) + "K</p>";
  html += "<h3>Quick Commands:</h3>";
  html += "<a href='/command?cmd=ON'><button>Turn ON</button></a> ";
  html += "<a href='/command?cmd=OFF'><button>Turn OFF</button></a><br><br>";
  html += "<a href='/command?cmd=TEST'><button>Run Test</button></a> ";
  html += "<a href='/status'><button>Get Status</button></a>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleCommand() {
  if (server.hasArg("cmd")) {
    String cmd = server.arg("cmd");
    cmd.toUpperCase();
    
    String response = processCommandHTTP(cmd);
    server.send(200, "text/plain", response);
  } else {
    server.send(400, "text/plain", "ERROR:MISSING_CMD_PARAMETER");
  }
}

void handleStatus() {
  String status = "{";
  status += "\"lights\":\"" + String(lightsOn ? "ON" : "OFF") + "\",";
  status += "\"brightness\":" + String(brightness) + ",";
  status += "\"color\":{\"r\":" + String(red) + ",\"g\":" + String(green) + ",\"b\":" + String(blue) + "},";
  status += "\"temp\":" + String(colorTemp) + ",";
  status += "\"ip\":\"" + WiFi.localIP().toString() + "\"";
  status += "}";
  server.send(200, "application/json", status);
}

void handleNotFound() {
  server.send(404, "text/plain", "ERROR:NOT_FOUND");
}

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }
}

void processCommand(String command) {
  String response = processCommandHTTP(command);
  Serial.println(response);
}

String processCommandHTTP(String command) {
  command.trim();
  command.toUpperCase();
  
  if (command == "ON") {
    lightsOn = true;
    setColor(red, green, blue);
    return "OK:LIGHTS_ON";
    
  } else if (command == "OFF") {
    lightsOn = false;
    ring1.clear();
    ring2.clear();
    ring1.show();
    ring2.show();
    return "OK:LIGHTS_OFF";
    
  } else if (command.startsWith("BRIGHT:")) {
    int newBrightness = command.substring(7).toInt();
    if (newBrightness >= 0 && newBrightness <= 255) {
      brightness = newBrightness;
      ring1.setBrightness(brightness);
      ring2.setBrightness(brightness);
      if (lightsOn) {
        setColor(red, green, blue);
      }
      return "OK:BRIGHTNESS_" + String(brightness);
    } else {
      return "ERROR:BRIGHTNESS_OUT_OF_RANGE";
    }
    
  } else if (command.startsWith("COLOR:")) {
    String colorStr = command.substring(6);
    int comma1 = colorStr.indexOf(',');
    int comma2 = colorStr.lastIndexOf(',');
    
    if (comma1 > 0 && comma2 > comma1) {
      red = colorStr.substring(0, comma1).toInt();
      green = colorStr.substring(comma1 + 1, comma2).toInt();
      blue = colorStr.substring(comma2 + 1).toInt();
      
      if (lightsOn) {
        setColor(red, green, blue);
      }
      return "OK:COLOR_" + String(red) + "," + String(green) + "," + String(blue);
    } else {
      return "ERROR:INVALID_COLOR_FORMAT";
    }
    
  } else if (command.startsWith("TEMP:")) {
    int newTemp = command.substring(5).toInt();
    if (newTemp >= 2700 && newTemp <= 6500) {
      colorTemp = newTemp;
      tempToRGB(colorTemp, red, green, blue);
      if (lightsOn) {
        setColor(red, green, blue);
      }
      return "OK:TEMP_" + String(colorTemp) + "K (RGB:" + String(red) + "," + String(green) + "," + String(blue) + ")";
    } else {
      return "ERROR:TEMP_OUT_OF_RANGE (2700-6500K)";
    }
    
  } else if (command == "TEST") {
    runTestPattern();
    return "OK:TEST_COMPLETE";
    
  } else if (command == "STATUS") {
    String status = "STATUS:";
    status += lightsOn ? "ON" : "OFF";
    status += ",BRIGHT:" + String(brightness);
    status += ",COLOR:" + String(red) + "," + String(green) + "," + String(blue);
    status += ",TEMP:" + String(colorTemp) + "K";
    return status;
    
  } else {
    return "ERROR:UNKNOWN_COMMAND";
  }
}

void setColor(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = ring1.Color(r, g, b);
  
  // Set all LEDs on both rings to the same color
  for (int i = 0; i < LEDS_PER_RING; i++) {
    ring1.setPixelColor(i, color);
    ring2.setPixelColor(i, color);
  }
  
  ring1.show();
  ring2.show();
}

void tempToRGB(uint16_t kelvin, uint8_t &r, uint8_t &g, uint8_t &b) {
  // Simplified color temperature to RGB conversion
  // Based on: http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/
  
  float temp = kelvin / 100.0;
  
  // Calculate Red
  if (temp <= 66) {
    r = 255;
  } else {
    float redCalc = temp - 60;
    redCalc = 329.698727446 * pow(redCalc, -0.1332047592);
    r = constrain(redCalc, 0, 255);
  }
  
  // Calculate Green
  if (temp <= 66) {
    float greenCalc = temp;
    greenCalc = 99.4708025861 * log(greenCalc) - 161.1195681661;
    g = constrain(greenCalc, 0, 255);
  } else {
    float greenCalc = temp - 60;
    greenCalc = 288.1221695283 * pow(greenCalc, -0.0755148492);
    g = constrain(greenCalc, 0, 255);
  }
  
  // Calculate Blue
  if (temp >= 66) {
    b = 255;
  } else if (temp <= 19) {
    b = 0;
  } else {
    float blueCalc = temp - 10;
    blueCalc = 138.5177312231 * log(blueCalc) - 305.0447927307;
    b = constrain(blueCalc, 0, 255);
  }
}

void runTestPattern() {
  Serial.println("TEST:RAINBOW_START");
  
  for (int j = 0; j < 256; j++) {
    for (int i = 0; i < LEDS_PER_RING; i++) {
      uint32_t color = Wheel((i * 256 / LEDS_PER_RING + j) & 255);
      ring1.setPixelColor(i, color);
      ring2.setPixelColor(i, color);
    }
    ring1.show();
    ring2.show();
    delay(10);
  }
  
  // Return to white
  setColor(255, 255, 255);
  Serial.println("TEST:RAINBOW_END");
}

// Input a value 0 to 255 to get a color value (for rainbow effect)
uint32_t Wheel(byte WheelPos) {
  WheelPos = 255 - WheelPos;
  if (WheelPos < 85) {
    return ring1.Color(255 - WheelPos * 3, 0, WheelPos * 3);
  }
  if (WheelPos < 170) {
    WheelPos -= 85;
    return ring1.Color(0, WheelPos * 3, 255 - WheelPos * 3);
  }
  WheelPos -= 170;
  return ring1.Color(WheelPos * 3, 255 - WheelPos * 3, 0);
}
