#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <Ticker.h>

const char* wifi_ssid = "";
const char* wifi_psk = "";

// Flask server details redacted
#define SERVER_URL ""

int deviceid = 4;

Ticker wifiReconnectTimer;
Ticker dataSendTimer;
Ticker restartTimer;

WiFiEventHandler wifiConnectHandler;
WiFiEventHandler wifiDisconnectHandler;

String dataBuffer = "";
bool dataReady = false;

unsigned long lastSerialReadTime = 0;
const unsigned long serialTimeout = 1500;

// Sensor data
float temp = 0;
float hum = 0;
float pressure = 0;
float pm1 = 0;
float pm25 = 0;
float pm10 = 0;
int co2 = 0;

void onWifiConnect(const WiFiEventStationModeGotIP& event);
void onWifiDisconnect(const WiFiEventStationModeDisconnected& event);
void sendData();
void connectToWifi();
void restartDevice();
void parseDataString(String inputString);
void readSerialData();

void setup() {
    Serial.begin(115200);
    setup_wifi();
    wifiConnectHandler = WiFi.onStationModeGotIP(onWifiConnect);
    wifiDisconnectHandler = WiFi.onStationModeDisconnected(onWifiDisconnect);

    connectToWifi();
    dataSendTimer.attach(15, sendData);
}

void loop() {
    readSerialData();  // Read and send serial data
}

void setup_wifi() {
    delay(500);
    WiFi.begin(wifi_ssid, wifi_psk);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }
    Serial.print("Connected to ");
    Serial.println(wifi_ssid);
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
}

void onWifiConnect(const WiFiEventStationModeGotIP& event) {
    Serial.println("Connected to Wi-Fi.");
    if (restartTimer.active()) {
        restartTimer.detach();
    }
}

void onWifiDisconnect(const WiFiEventStationModeDisconnected& event) {
    Serial.println("Disconnected from Wi-Fi.");
    wifiReconnectTimer.once(2, connectToWifi);
    if (!restartTimer.active()) {
        restartTimer.once(60, restartDevice);
        Serial.println("Restart timer started. Device will restart in 60 seconds if not reconnected.");
    }
}

// Parse incoming serial data
void parseDataString(String inputString) {
    // Extract values from the formatted string (e.g., "T:22.5|H:60.5|P:1013.2|PM1:5.0|PM25:12.5|PM10:15.0|CO2:400")
    int result = sscanf(inputString.c_str(), "T:%f|H:%f|P:%f|PM1:%f|PM25:%f|PM10:%f|CO2:%d", 
                        &temp, &hum, &pressure, &pm1, &pm25, &pm10, &co2);

    if (result == 7) {
        Serial.println("Parsed Data:");
        Serial.print("Temperature: ");
        Serial.println(temp);
        Serial.print("Humidity: ");
        Serial.println(hum);
        Serial.print("Pressure: ");
        Serial.println(pressure);
        Serial.print("PM1: ");
        Serial.println(pm1);
        Serial.print("PM2.5: ");
        Serial.println(pm25);
        Serial.print("PM10: ");
        Serial.println(pm10);
        Serial.print("CO2: ");
        Serial.println(co2);
    } else {
        Serial.println("Error: Invalid data format.");
    }
}

// Send data via HTTP POST
void sendData() {
    if (dataReady) {
        String payload = "{\"deviceid\":" + String(deviceid) +
                         ",\"temp\":" + String(temp, 2) +
                         ",\"hum\":" + String(hum, 2) +
                         ",\"pressure\":" + String(pressure, 2) +
                         ",\"pm1\":" + String(pm1, 2) +
                         ",\"pm25\":" + String(pm25, 2) +
                         ",\"pm10\":" + String(pm10, 2) +
                         ",\"co2\":" + String(co2) + "}";

        WiFiClient client;
        HTTPClient http;

        http.begin(client, SERVER_URL);
        http.addHeader("Content-Type", "application/json");

        int httpResponseCode = http.POST(payload);

        if (httpResponseCode > 0) {
            Serial.print("HTTP Response Code: ");
            Serial.println(httpResponseCode);
            Serial.println("Payload Sent:");
            Serial.println(payload);
        } else {
            Serial.print("HTTP POST Failed. Error: ");
            Serial.println(http.errorToString(httpResponseCode));
        }

        http.end();
        dataBuffer = "";  // Reset buffer
        dataReady = false;  // Reset ready flag
    }
}

void restartDevice() {
    Serial.println("Device not connected for 1 minute. Restarting...");
    ESP.restart();
}

// Read and parse serial data
void readSerialData() {
    if (Serial.available()) {
        lastSerialReadTime = millis();

        while (Serial.available()) {
            char incomingChar = Serial.read();
            if (incomingChar == '\n') {
                parseDataString(dataBuffer);
                dataReady = true;
                sendData();  // Send data after parsing
                Serial.println("Data Sent:");
                Serial.println(dataBuffer);
                dataBuffer = "";  // Clear the message buffer
            } else {
                dataBuffer += incomingChar;
            }
        }
    }

    if (millis() - lastSerialReadTime > serialTimeout && dataBuffer.length() > 0) {
        Serial.println("Incomplete data. Clearing buffer.");
        dataBuffer = "";  // Clear incomplete data
    }
}

void connectToWifi() {
    Serial.println("Connecting to Wi-Fi...");
    WiFi.begin(wifi_ssid, wifi_psk);
}
