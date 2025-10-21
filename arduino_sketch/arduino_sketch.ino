#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define RST_PIN 9
#define SS_PIN 10
#define LED_GRANTED 7
#define LED_DENIED 6
#define LED_MASTER 5

MFRC522 mfrc522(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2);  // Адрес твоего LCD

void setup() {
  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();
  
  // Инициализация LCD
  lcd.init();
  lcd.backlight();
  lcd.clear();
  
  // Настройка светодиодов
  pinMode(LED_GRANTED, OUTPUT);
  pinMode(LED_DENIED, OUTPUT);
  pinMode(LED_MASTER, OUTPUT);
  
  // Стартовая заставка
  showStartupAnimation();
  
  Serial.println("READY");
  displayMessage("System Ready", "Show NFC Tag...");
}

void loop() {
  // Считывание NFC метки
  if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
    String uid = getUID();
    Serial.println("UID:" + uid);
    displayMessage("Card Detected", "Processing...");
    
    // Ждем ответ от Python
    waitForResponse();
    
    mfrc522.PICC_HaltA();
    delay(2000); // Защита от повторного считывания
    displayMessage("System Ready", "Show NFC Tag...");
  }
  
  // Обработка входящих сообщений от Python
  if (Serial.available() > 0) {
    String response = Serial.readStringUntil('\n');
    response.trim();
    processResponse(response);
  }
}

String getUID() {
  String content = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    content.concat(String(mfrc522.uid.uidByte[i] < 0x10 ? "0" : ""));
    content.concat(String(mfrc522.uid.uidByte[i], HEX));
  }
  content.toUpperCase();
  return content;
}

void waitForResponse() {
  unsigned long startTime = millis();
  while (millis() - startTime < 5000) {
    if (Serial.available() > 0) {
      String response = Serial.readStringUntil('\n');
      response.trim();
      processResponse(response);
      break;
    }
    delay(100);
  }
}

void processResponse(String response) {
  Serial.print("Server: ");
  Serial.println(response);
  
  if (response.startsWith("ACCESS_GRANTED")) {
    // Доступ разрешен
    String userName = extractUserName(response);
    digitalWrite(LED_GRANTED, HIGH);
    displayMessage("ACCESS GRANTED", userName);
    Serial.println(">>> ACCESS GRANTED - Door opened");
    delay(3000);
    digitalWrite(LED_GRANTED, LOW);
  }
  else if (response.startsWith("ACCESS_DENIED")) {
    // Доступ запрещен
    digitalWrite(LED_DENIED, HIGH);
    displayMessage("ACCESS DENIED", "Unknown Card");
    Serial.println(">>> ACCESS DENIED");
    delay(3000);
    digitalWrite(LED_DENIED, LOW);
  }
  else if (response.startsWith("MASTER_KEY")) {
    // Мастер-ключ
    String mode = extractMode(response);
    digitalWrite(LED_MASTER, HIGH);
    displayMessage("MASTER KEY", "Mode: " + mode);
    Serial.println(">>> MASTER KEY - Registration mode");
    delay(3000);
    digitalWrite(LED_MASTER, LOW);
  }
  else if (response.startsWith("REGISTERED")) {
    // Успешная регистрация
    String userName = extractUserName(response);
    digitalWrite(LED_GRANTED, HIGH);
    displayMessage("REGISTERED", userName);
    Serial.println(">>> NEW USER REGISTERED");
    delay(2000);
    digitalWrite(LED_GRANTED, LOW);
  }
  else if (response.startsWith("ERROR")) {
    // Ошибка
    digitalWrite(LED_DENIED, HIGH);
    displayMessage("ERROR", response);
    Serial.println(">>> ERROR: " + response);
    delay(3000);
    digitalWrite(LED_DENIED, LOW);
  }
}

String extractUserName(String response) {
  // Извлекаем имя пользователя из ответа "ACCESS_GRANTED:John" -> "John"
  int colonIndex = response.indexOf(':');
  if (colonIndex != -1 && colonIndex + 1 < response.length()) {
    return response.substring(colonIndex + 1);
  }
  return "User";
}

String extractMode(String response) {
  // Извлекаем режим из "MASTER_KEY:ACTIVE" -> "ACTIVE"
  int colonIndex = response.indexOf(':');
  if (colonIndex != -1 && colonIndex + 1 < response.length()) {
    return response.substring(colonIndex + 1);
  }
  return "UNKNOWN";
}

void displayMessage(String line1, String line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(centerText(line1));
  lcd.setCursor(0, 1);
  lcd.print(centerText(line2));
}

String centerText(String text) {
  // Центрирование текста на 16-символьном дисплее
  if (text.length() >= 16) return text.substring(0, 16);
  
  int spaces = (16 - text.length()) / 2;
  String centered = "";
  for (int i = 0; i < spaces; i++) {
    centered += " ";
  }
  centered += text;
  return centered;
}

void showStartupAnimation() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(" NFC ACCESS ");
  lcd.setCursor(0, 1);
  lcd.print(" CONTROL SYSTEM ");
  delay(2000);
  
  // Анимация загрузки
  for (int i = 0; i < 3; i++) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Starting system");
    lcd.setCursor(i * 5, 1);
    lcd.print("===>");
    delay(500);
  }
}