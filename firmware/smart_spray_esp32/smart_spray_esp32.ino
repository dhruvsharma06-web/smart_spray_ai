/*
 * Smart Spray Hardware Integration - ESP32 Firmware
 * 
 * Hardware:
 *   - ESP32-WROOM-32 / ESP32 Dev Module
 *   - DHT22 (DATA = GPIO5)
 *   - Soil Moisture Sensor (AO = GPIO34)
 *   - Rain Sensor (DO = GPIO27, LOW = Rain Detected)
 *   - OLED SSD1306 I2C 128x64 (SDA = GPIO21, SCL = GPIO22, Addr = 0x3C)
 *   - 2-Channel Relay Module (ACTIVE LOW):
 *       CH2 GPIO25 = Spray Pump
 *       CH1 GPIO26 = Irrigation Pump
 *       HIGH = OFF (Default Safe State)
 *       LOW  = ON
 *
 * Network & Integration:
 *   - Device ID: device-001
 *   - FastAPI Host: http://192.168.1.43:8000
 *   - Telemetry: POST /api/sensors/telemetry every 3 seconds
 *   - Command Poll: GET /api/v1/iot/device-001/command every 500 ms
 *   - Ack: POST /api/v1/iot/device-001/ack
 *
 * Required Libraries (Arduino IDE Library Manager):
 *   1. Adafruit GFX Library
 *   2. Adafruit SSD1306
 *   3. DHT sensor library by Adafruit
 *   4. Adafruit Unified Sensor
 *   5. ArduinoJson by Benoit Blanchon (v6 or v7)
 *   6. WiFi (Built-in ESP32 core)
 *   7. HTTPClient (Built-in ESP32 core)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <time.h>

// ==========================================
// 1. Hardware Pin Definitions
// ==========================================
#define DHT_PIN          5       // DHT22 Data Pin
#define DHT_TYPE         DHT22   // DHT 22 (AM2302)
#define SOIL_PIN         34      // Analog Soil Moisture Pin AO
#define RAIN_PIN         27      // Rain Sensor Digital Pin DO (LOW = Rain)

#define RELAY_SPRAY      25      // Relay CH2: Spray Pump (GPIO25, ACTIVE LOW)
#define RELAY_IRRIGATION 26      // Relay CH1: Irrigation Pump (GPIO26, ACTIVE LOW)

#define OLED_SDA         21
#define OLED_SCL         22
#define OLED_SCREEN_WIDTH 128
#define OLED_SCREEN_HEIGHT 64
#define OLED_I2C_ADDR    0x3C

// Active-Low Relay Logic
#define RELAY_ON         LOW
#define RELAY_OFF        HIGH

// ==========================================
// 2. Wi-Fi & Backend Credentials & Constants
// ==========================================
const char* WIFI_SSID     = "FTTH-Lokesh";       // <--- Replace with your Wi-Fi SSID
const char* WIFI_PASSWORD = "Dhruv-2808";   // <--- Replace with your Wi-Fi Password

const char* DEVICE_ID     = "device-001";
const char* BACKEND_BASE  = "http://192.168.1.43:8000";

// API Endpoint URIs
const char* TELEMETRY_URL = "http://192.168.1.43:8000/api/sensors/telemetry";
const char* COMMAND_URL   = "http://192.168.1.43:8000/api/v1/iot/device-001/command";
const char* ACK_URL       = "http://192.168.1.43:8000/api/v1/iot/device-001/ack";

// Non-Blocking Intervals (ms)
const unsigned long TELEMETRY_INTERVAL   = 3000UL;   // Telemetry every 3 seconds
const unsigned long COMMAND_POLL_INTERVAL = 500UL;    // Command poll every 500 ms
const unsigned long OLED_REFRESH_INTERVAL = 500UL;    // OLED refresh every 500 ms
const unsigned long MAX_SAFETY_DURATION   = 30000UL;  // Maximum hard safety duration: 30s

// Soil Calibration Range
const int SOIL_DRY_VAL = 760;
const int SOIL_WET_VAL = 800;

// ==========================================
// 3. Global Instances & State Control
// ==========================================
DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_SSD1306 display(OLED_SCREEN_WIDTH, OLED_SCREEN_HEIGHT, &Wire, -1);

enum SystemState {
  STATE_IDLE,
  STATE_SPRAYING,
  STATE_IRRIGATING,
  STATE_EMERGENCY
};

SystemState currentState = STATE_IDLE;
bool emergencyLatched = false;

// Timers for Non-Blocking Execution
unsigned long lastTelemetryMs = 0;
unsigned long lastCommandPollMs = 0;
unsigned long lastOledRefreshMs = 0;

// Pump Execution State
unsigned long pumpStartMs = 0;
unsigned long pumpDurationMs = 0;
String activeCommand = "";

// Sensor Readings Cache
float currentTemperature = NAN;
float currentHumidity = NAN;
int currentSoilMoisture = 0;
bool currentRainDetected = false;

// Function Declarations
void initializeHardware();
void connectWiFi();
void readSensors();
void turnOffAllPumps();
void checkPumpTimeout();
void sendTelemetry();
void pollCommand();
void processCommand(const String& cmd, unsigned long durationMs);
void sendAck(const String& cmd, const String& statusStr);
void updateOLED();
String getFormattedISO8601();

// ==========================================
// 4. Setup Routine
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n==========================================");
  Serial.println("  Smart Spray ESP32 Hardware Booting...   ");
  Serial.println("==========================================");

  // STEP 1: SAFETY FIRST - Initialize Relay Pins HIGH (OFF) before doing anything else!
  pinMode(RELAY_IRRIGATION, OUTPUT);
  pinMode(RELAY_SPRAY, OUTPUT);
  digitalWrite(RELAY_IRRIGATION, RELAY_OFF);
  digitalWrite(RELAY_SPRAY, RELAY_OFF);
  Serial.println("[SAFETY] Both relay outputs set to HIGH (OFF).");

  // STEP 2: Pin Modes for Sensors
  pinMode(RAIN_PIN, INPUT);

  // STEP 3: OLED Display Initialization
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
    Serial.println("[OLED] ERROR: SSD1306 OLED allocation failed!");
  } else {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("Smart Spray Boot...");
    display.display();
  }

  // STEP 4: DHT22 Initialization
  dht.begin();
  Serial.println("[DHT22] Initialized on GPIO5.");

  // STEP 5: Wi-Fi Connection
  connectWiFi();

  // STEP 6: Synchronize NTP Time for UTC Timestamping
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("[NTP] Requested time synchronization.");

  Serial.println("[BOOT] Setup completed safely. No automatic pump activation.");
}

// ==========================================
// 5. Main Control Loop (Non-Blocking)
// ==========================================
void loop() {
  unsigned long currentMs = millis();

  // 1. Wi-Fi Connection & Safety Watchdog
  if (WiFi.status() != WL_CONNECTED) {
    if (currentState == STATE_SPRAYING || currentState == STATE_IRRIGATING) {
      Serial.println("[SAFETY WATCHDOG] Wi-Fi lost! Emergency cutoff of active pump.");
      turnOffAllPumps();
    }
    connectWiFi();
    return;
  }

  // 2. Continuous Non-Blocking Sensor Reading
  readSensors();

  // 3. Actuator Duration Timeout Watchdog
  checkPumpTimeout();

  // 4. Command Polling Loop (Every 500 ms)
  if (currentMs - lastCommandPollMs >= COMMAND_POLL_INTERVAL) {
    lastCommandPollMs = currentMs;
    pollCommand();
  }

  // 5. Telemetry Transmission Loop (Every 3000 ms)
  if (currentMs - lastTelemetryMs >= TELEMETRY_INTERVAL) {
    lastTelemetryMs = currentMs;
    sendTelemetry();
  }

  // 6. OLED Non-Blocking Refresh Loop (Every 500 ms)
  if (currentMs - lastOledRefreshMs >= OLED_REFRESH_INTERVAL) {
    lastOledRefreshMs = currentMs;
    updateOLED();
  }
}

// ==========================================
// 6. Wi-Fi Manager
// ==========================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("[WiFi] Connecting to ");
  Serial.print(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.print("[WiFi] ESP32 IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] Connection attempt failed. Will retry in main loop.");
    turnOffAllPumps();
  }
}

// ==========================================
// 7. Sensor Reader
// ==========================================
void readSensors() {
  // Read DHT22
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();

  if (!isnan(temp)) currentTemperature = temp;
  if (!isnan(hum))  currentHumidity = hum;

  // Read Soil Moisture (Analog GPIO34)
  int rawSoil = analogRead(SOIL_PIN);
  int percent = map(rawSoil, SOIL_DRY_VAL, SOIL_WET_VAL, 0, 100);
  currentSoilMoisture = constrain(percent, 0, 100);

  // Read Rain Sensor Digital Pin DO (GPIO27, LOW = Rain)
  currentRainDetected = (digitalRead(RAIN_PIN) == LOW);
}

// ==========================================
// 8. Actuator Cutoff & Safety Helper
// ==========================================
void turnOffAllPumps() {
  digitalWrite(RELAY_IRRIGATION, RELAY_OFF);
  digitalWrite(RELAY_SPRAY, RELAY_OFF);

  if (!emergencyLatched) {
    currentState = STATE_IDLE;
  } else {
    currentState = STATE_EMERGENCY;
  }
}

// ==========================================
// 9. Actuator Timeout Watchdog
// ==========================================
void checkPumpTimeout() {
  if (currentState == STATE_SPRAYING || currentState == STATE_IRRIGATING) {
    if (millis() - pumpStartMs >= pumpDurationMs) {
      Serial.print("[PUMP CONTROL] ");
      Serial.print(activeCommand);
      Serial.println(" duration completed. Shutting down pumps.");

      String finishedCmd = activeCommand;
      turnOffAllPumps();
      sendAck(finishedCmd, "COMPLETED");
      activeCommand = "";
    }
  }
}

// ==========================================
// 10. Send Telemetry HTTP POST
// ==========================================
void sendTelemetry() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(TELEMETRY_URL);
  http.addHeader("Content-Type", "application/json");

  // Create JSON Document
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = getFormattedISO8601();

  JsonObject soil = doc["soil"].to<JsonObject>();
  soil["moisture_percent"] = currentSoilMoisture;

  JsonObject env = doc["environment"].to<JsonObject>();
  if (isnan(currentTemperature)) {
    env["temperature_celsius"] = nullptr;
  } else {
    env["temperature_celsius"] = currentTemperature;
  }

  if (isnan(currentHumidity)) {
    env["humidity_percent"] = nullptr;
  } else {
    env["humidity_percent"] = currentHumidity;
  }

  env["rain_detected"] = currentRainDetected;

  doc["tank_level"] = nullptr;
  doc["pump"] = (currentState == STATE_SPRAYING || currentState == STATE_IRRIGATING);

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  int httpCode = http.POST(jsonPayload);
  if (httpCode > 0) {
    Serial.printf("[TELEMETRY] Sent OK (HTTP %d)\n", httpCode);
  } else {
    Serial.printf("[TELEMETRY] POST failed: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

// ==========================================
// 11. Poll Backend Command GET
// ==========================================
void pollCommand() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(COMMAND_URL);
  http.setTimeout(1500);

  int httpCode = http.GET();
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload);

    if (!err) {
      String cmd = doc["command"].as<String>();
      unsigned long duration = doc["duration_ms"] | 5000UL;
      if (cmd != "NONE") {
        Serial.printf("[COMMAND RECEIVED] Command: '%s', Duration: %lu ms\n", cmd.c_str(), duration);
        processCommand(cmd, duration);
      }
    } else {
      Serial.println("[COMMAND POLL] JSON Parsing Error");
    }
  } else if (httpCode != HTTP_CODE_NOT_FOUND && httpCode > 0) {
    Serial.printf("[COMMAND POLL] HTTP %d\n", httpCode);
  }
  http.end();
}

// ==========================================
// 12. Command Execution Logic
// ==========================================
void processCommand(const String& cmd, unsigned long durationMs) {
  String uppercaseCmd = cmd;
  uppercaseCmd.toUpperCase();

  // 1. EMERGENCY STOP COMMAND
  if (uppercaseCmd == "EMERGENCY_STOP") {
    Serial.println("[SAFETY GATE] EMERGENCY_STOP engaged!");
    emergencyLatched = true;
    currentState = STATE_EMERGENCY;
    turnOffAllPumps();
    sendAck("EMERGENCY_STOP", "EMERGENCY_HALTED");
    return;
  }

  // 2. RESET COMMAND
  if (uppercaseCmd == "RESET" || uppercaseCmd == "RESET_EMERGENCY_STOP") {
    Serial.println("[SAFETY GATE] Emergency Latch Cleared via RESET.");
    emergencyLatched = false;
    currentState = STATE_IDLE;
    turnOffAllPumps();
    sendAck("RESET", "COMPLETED");
    return;
  }

  // 3. STOP COMMAND
  if (uppercaseCmd == "STOP") {
    Serial.println("[COMMAND] STOP command executed.");
    turnOffAllPumps();
    sendAck("STOP", "STOPPED");
    return;
  }

  // 4. CHECK EMERGENCY LATCH FOR OPERATIONAL COMMANDS
  if (emergencyLatched) {
    Serial.printf("[SAFETY REJECTION] Command '%s' REJECTED due to ACTIVE Emergency Latch!\n", uppercaseCmd.c_str());
    sendAck(uppercaseCmd, "REJECTED_EMERGENCY_LATCHED");
    return;
  }

  // Enforce Safety Max Duration Cap (30 seconds maximum)
  unsigned long safeDuration = min(durationMs, MAX_SAFETY_DURATION);
  if (safeDuration == 0) safeDuration = 5000UL;

  // 5. SPRAY COMMAND (Relay CH2: GPIO25)
  if (uppercaseCmd == "SPRAY") {
    Serial.printf("[ACTUATOR] Actuating SPRAY Pump (GPIO25 / Relay CH2) for %lu ms...\n", safeDuration);
    // Never activate both pumps simultaneously! Explicitly turn opposite relay OFF first.
    digitalWrite(RELAY_IRRIGATION, RELAY_OFF);
    digitalWrite(RELAY_SPRAY, RELAY_ON);

    currentState = STATE_SPRAYING;
    pumpStartMs = millis();
    pumpDurationMs = safeDuration;
    activeCommand = "SPRAY";

    sendAck("SPRAY", "STARTED");
    return;
  }

  // 6. IRRIGATE COMMAND (Relay CH1: GPIO26)
  if (uppercaseCmd == "IRRIGATE") {
    Serial.printf("[ACTUATOR] Actuating IRRIGATE Pump (GPIO26 / Relay CH1) for %lu ms...\n", safeDuration);
    // Never activate both pumps simultaneously! Explicitly turn opposite relay OFF first.
    digitalWrite(RELAY_SPRAY, RELAY_OFF);
    digitalWrite(RELAY_IRRIGATION, RELAY_ON);

    currentState = STATE_IRRIGATING;
    pumpStartMs = millis();
    pumpDurationMs = safeDuration;
    activeCommand = "IRRIGATE";

    sendAck("IRRIGATE", "STARTED");
    return;
  }

  // Unknown command safeguard
  Serial.printf("[SAFETY GATE] Unknown command '%s' ignored. Pumps OFF.\n", uppercaseCmd.c_str());
  turnOffAllPumps();
}

// ==========================================
// 13. Send Command ACK HTTP POST
// ==========================================
void sendAck(const String& cmd, const String& statusStr) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(ACK_URL);
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["command"] = cmd;
  doc["status"] = statusStr;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  int httpCode = http.POST(jsonPayload);
  if (httpCode > 0) {
    Serial.printf("[ACK] ACK Sent for '%s' -> '%s' (HTTP %d)\n", cmd.c_str(), statusStr.c_str(), httpCode);
  } else {
    Serial.printf("[ACK] ACK POST failed: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}

// ==========================================
// 14. OLED UI Display Routine
// ==========================================
void updateOLED() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // Header
  display.setCursor(0, 0);
  display.print("Smart Spray");
  display.setCursor(80, 0);
  if (WiFi.status() == WL_CONNECTED) {
    display.print("WiFi:OK");
  } else {
    display.print("WiFi:OFF");
  }
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);

  // Temperature & Humidity
  display.setCursor(0, 14);
  if (isnan(currentTemperature)) {
    display.print("Temp: ERR");
  } else {
    display.printf("Temp: %.1f C", currentTemperature);
  }

  display.setCursor(0, 26);
  if (isnan(currentHumidity)) {
    display.print("Hum:  ERR");
  } else {
    display.printf("Hum:  %.1f %%", currentHumidity);
  }

  // Soil & Rain
  display.setCursor(0, 38);
  display.printf("Soil: %d %%", currentSoilMoisture);

  display.setCursor(70, 38);
  display.print("Rain: ");
  display.print(currentRainDetected ? "YES" : "NO");

  // Pump & Emergency Status Footer
  display.drawLine(0, 48, 128, 48, SSD1306_WHITE);
  display.setCursor(0, 52);
  display.print("Pump: ");

  if (emergencyLatched) {
    display.print("EMERGENCY");
  } else {
    switch (currentState) {
      case STATE_SPRAYING:   display.print("SPRAY (CH2:25)"); break;
      case STATE_IRRIGATING: display.print("IRRIG (CH1:26)"); break;
      case STATE_IDLE:       display.print("OFF / IDLE"); break;
      default:               display.print("OFF"); break;
    }
  }

  display.display();
}

// ==========================================
// 15. Timestamp Formatting Helper
// ==========================================
String getFormattedISO8601() {
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    char timeStringBuff[32];
    strftime(timeStringBuff, sizeof(timeStringBuff), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    return String(timeStringBuff);
  }
  // Fallback ISO timestamp if NTP time is not yet synchronized
  return "2026-09-20T18:30:00Z";
}
