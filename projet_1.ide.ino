#include <WiFi.h>
#include <HardwareSerial.h>

// --- CONFIGURATION ---
#define RX_PIN 16 
#define TX_PIN 17 
#define LED_PIN 2

const char* DEV_EUI = "70B3D57ED007365A";
const char* APP_EUI = "0000000000000000";
const char* APP_KEY = "216BA94D7850858799D991941BF7263D";

HardwareSerial loraSerial(2);

// Petite fonction pour faire clignoter la LED
void blink(int n, int ms) {
  for(int i=0; i<n; i++) {
    digitalWrite(LED_PIN, HIGH); delay(ms);
    digitalWrite(LED_PIN, LOW); delay(ms);
  }
}

bool sendATCommand(String command, String expectedResponse, int timeout) {
  loraSerial.println(command);
  long startTime = millis();
  String response = "";
  while (millis() - startTime < timeout) {
    if (loraSerial.available()) response += (char)loraSerial.read();
    if (response.indexOf(expectedResponse) != -1) return true;
  }
  return false;
}

String bytesToHexStr(byte* bytes, int len) {
  String hexStr = "";
  for (int i = 0; i < len; i++) {
    if (bytes[i] < 0x10) hexStr += '0';
    hexStr += String(bytes[i], HEX);
  }
  hexStr.toUpperCase();
  return hexStr;
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  blink(5, 50); // Flash démarrage

  loraSerial.begin(9600, SERIAL_8N1, RX_PIN, TX_PIN);
  delay(1000);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  // Config LoRa
  sendATCommand("AT", "OK", 1000);
  sendATCommand("AT+ID=DevEui," + String(DEV_EUI), "OK", 1000);
  sendATCommand("AT+ID=AppEui," + String(APP_EUI), "OK", 1000);
  sendATCommand("AT+KEY=AppKey," + String(APP_KEY), "OK", 1000);
  sendATCommand("AT+DR=EU868", "OK", 1000);
  sendATCommand("AT+MODE=LWOTAA", "OK", 1000);
  
  // Join (LED allumée fixe tant que ça cherche)
  digitalWrite(LED_PIN, HIGH);
  if (!sendATCommand("AT+JOIN", "Network joined", 20000)) {
    digitalWrite(LED_PIN, LOW);
    blink(10, 500); // Echec Join : Clignote lent
  } else {
    digitalWrite(LED_PIN, LOW);
    blink(2, 200); // Succès Join : 2 flashs
  }
}

void loop() {
  digitalWrite(LED_PIN, HIGH); // LED ON = Scan en cours
  int n = WiFi.scanNetworks();
  
  byte payload[25]; 
  memset(payload, 0, 25);
  int validApCount = 0; 
  
  if (n > 0) {
    for (int i = 0; i < n; i++) {
      if (validApCount >= 3) break;

      uint8_t* mac = WiFi.BSSID(i);
      
      // --- REMISE EN PLACE DU FILTRE ---
      // Si le 1er octet a son 2ème bit à 1 (ex: x2, x6, xA, xE), c'est un téléphone/random.
      // On l'ignore pour chercher les vraies bornes fixes.
      if (mac[0] & 0x02) {
         // Optionnel : Tu peux décommenter la ligne suivante pour voir les rejetés dans le Serial si tu rebranches le PC
         // Serial.printf("Rejeté (Random): %s\n", WiFi.BSSIDstr(i).c_str());
         continue; 
      }
      
      int cursor = validApCount * 7;
      memcpy(&payload[cursor], mac, 6);
      payload[cursor + 6] = (byte)WiFi.RSSI(i);
      validApCount++;
    }
  }
  
  digitalWrite(LED_PIN, LOW); // Scan fini
  
  // --- ENVOI LORA ---
  if (validApCount > 0) {
    // Cas normal : On a trouvé des Wifi
    String hexPayload = bytesToHexStr(payload, validApCount * 7);
    blink(10, 50); // Stroboscope = Envoi Wifi
    sendATCommand("AT+MSGHEX=" + hexPayload, "Done", 10000);
  } else {
    // Cas vide : On force l'envoi d'un octet "00" pour dire "Je suis vivant mais seul"
    blink(2, 1000); // 2 Clignotements lents = Pas de Wifi
    sendATCommand("AT+MSGHEX=00", "Done", 10000); 
  }
  
  WiFi.scanDelete();
  
  // Pause plus longue (60s) pour éviter d'être bloqué par le réseau (Duty Cycle)
  delay(15000); 
}