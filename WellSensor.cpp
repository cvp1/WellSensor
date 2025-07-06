#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <NewPing.h>

// WiFi Configuration
const char* ssid = "Ranch";
const char* password = "Sheridan1068!";

// Sensor Configuration
#define TRIGGER_PIN  5
#define ECHO_PIN     18
#define MAX_DISTANCE 600  // Maximum distance in cm

// Tank Configuration (customize for your 1550 gallon tank)
#define TANK_HEIGHT_CM 183    // ~6 feet in cm
#define TANK_CAPACITY_GALLONS 1550
#define SENSOR_HEIGHT_CM 200  // Height of sensor above tank bottom

// Timing Configuration
#define READING_INTERVAL 30000  // 30 seconds between readings
#define APP_SEND_INTERVAL 300000  // 5 minutes between app updates

// Your App Configuration
const char* app_server = "https://192.168.86.90";  // Replace with your app URL
const char* api_endpoint = "/api/tank-data";      // Replace with your API endpoint

// Initialize sensor and web server
NewPing sonar(TRIGGER_PIN, ECHO_PIN, MAX_DISTANCE);
WebServer server(80);

// Global variables
float currentDistance = 0;
float waterLevel = 0;
float gallons = 0;
unsigned long lastReading = 0;
unsigned long lastAppUpdate = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Starting ESP32 Tank Monitor...");
  
  // Initialize WiFi
  connectToWiFi();
  
  // Setup web server endpoints
  setupWebServer();
  
  // Initial sensor reading
  takeSensorReading();
  
  Serial.println("Tank Monitor Ready!");
  Serial.print("Local IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // Handle web server requests
  server.handleClient();
  
  // Take sensor readings
  if (millis() - lastReading >= READING_INTERVAL) {
    takeSensorReading();
    lastReading = millis();
  }
  
  // Send data to your app
  if (millis() - lastAppUpdate >= APP_SEND_INTERVAL) {
    sendDataToApp();
    lastAppUpdate = millis();
  }
  
  delay(100);  // Small delay to prevent watchdog issues
}

void connectToWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void takeSensorReading() {
  // Take multiple readings for accuracy
  float total = 0;
  int validReadings = 0;
  
  for (int i = 0; i < 5; i++) {
    float distance = sonar.ping_cm();
    
    if (distance > 0 && distance < MAX_DISTANCE) {
      total += distance;
      validReadings++;
    }
    delay(100);
  }
  
  if (validReadings > 0) {
    currentDistance = total / validReadings;
    
    // Calculate water level and gallons
    calculateWaterLevel();
    
    // Log readings
    Serial.println("=== Sensor Reading ===");
    Serial.print("Distance to water: ");
    Serial.print(currentDistance);
    Serial.println(" cm");
    Serial.print("Water level: ");
    Serial.print(waterLevel);
    Serial.println(" cm");
    Serial.print("Gallons: ");
    Serial.println(gallons);
    Serial.println("=====================");
  } else {
    Serial.println("Error: No valid sensor readings");
  }
}

void calculateWaterLevel() {
  // Water level = sensor height - distance to water - tank bottom offset
  waterLevel = SENSOR_HEIGHT_CM - currentDistance;
  
  // Ensure water level is within tank bounds
  if (waterLevel < 0) waterLevel = 0;
  if (waterLevel > TANK_HEIGHT_CM) waterLevel = TANK_HEIGHT_CM;
  
  // Calculate gallons based on water level percentage
  float fillPercentage = waterLevel / TANK_HEIGHT_CM;
  gallons = fillPercentage * TANK_CAPACITY_GALLONS;
}

void setupWebServer() {
  // Endpoint for your app to get current readings
  server.on("/status", HTTP_GET, []() {
    DynamicJsonDocument doc(1024);
    
    doc["distance_cm"] = currentDistance;
    doc["water_level_cm"] = waterLevel;
    doc["gallons"] = gallons;
    doc["fill_percentage"] = (gallons / TANK_CAPACITY_GALLONS) * 100;
    doc["timestamp"] = millis();
    doc["tank_capacity"] = TANK_CAPACITY_GALLONS;
    doc["wifi_rssi"] = WiFi.RSSI();
    
    String response;
    serializeJson(doc, response);
    
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", response);
  });
  
  // Endpoint to force a new reading
  server.on("/reading", HTTP_GET, []() {
    takeSensorReading();
    server.sendRedirect("/status");
  });
  
  // Basic web interface for testing
  server.on("/", HTTP_GET, []() {
    String html = "<html><body>";
    html += "<h1>Tank Water Level Monitor</h1>";
    html += "<p>Distance: " + String(currentDistance) + " cm</p>";
    html += "<p>Water Level: " + String(waterLevel) + " cm</p>";
    html += "<p>Gallons: " + String(gallons) + "</p>";
    html += "<p>Fill: " + String((gallons/TANK_CAPACITY_GALLONS)*100) + "%</p>";
    html += "<p><a href='/reading'>Take New Reading</a></p>";
    html += "<p><a href='/status'>JSON Data</a></p>";
    html += "</body></html>";
    
    server.send(200, "text/html", html);
  });
  
  server.begin();
  Serial.println("Web server started");
}

void sendDataToApp() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // Construct full URL
    String url = String(app_server) + String(api_endpoint);
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    
    // Create JSON payload
    DynamicJsonDocument doc(1024);
    doc["device_id"] = "tank_monitor_01";
    doc["distance_cm"] = currentDistance;
    doc["water_level_cm"] = waterLevel;
    doc["gallons"] = gallons;
    doc["fill_percentage"] = (gallons / TANK_CAPACITY_GALLONS) * 100;
    doc["timestamp"] = millis();
    doc["battery_voltage"] = 12.0;  // You can add battery monitoring later
    doc["wifi_rssi"] = WiFi.RSSI();
    
    String jsonString;
    serializeJson(doc, jsonString);
    
    // Send POST request
    int httpResponseCode = http.POST(jsonString);
    
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.print("App update sent successfully. Response: ");
      Serial.println(httpResponseCode);
    } else {
      Serial.print("Error sending to app: ");
      Serial.println(httpResponseCode);
    }
    
    http.end();
  } else {
    Serial.println("WiFi not connected - cannot send to app");
  }
}

// Optional: Add deep sleep for battery conservation
void goToSleep(int sleepMinutes) {
  Serial.println("Going to sleep for " + String(sleepMinutes) + " minutes");
  esp_sleep_enable_timer_wakeup(sleepMinutes * 60 * 1000000);  // Convert to microseconds
  esp_deep_sleep_start();
}