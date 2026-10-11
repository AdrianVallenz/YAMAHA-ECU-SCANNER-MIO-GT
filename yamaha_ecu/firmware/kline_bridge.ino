/*
 * ==============================================================================
 * YAMAHA K-LINE HARDWARE BRIDGE FIRMWARE
 * Kompatibel dengan: Arduino Nano (ATmega328P), ESP32, atau STM32 BluePill
 * Ditujukan untuk: Yamaha Mio GT 2015 (ECU 54P / 2BJ YMJET-FI)
 * ==============================================================================
 *
 * Skema Koneksi Pinout K-Line Transceiver (IC L9637D / MC33660):
 *
 *               +12V Aki Motor (Pin 1 DLC Putih)
 *                     |
 *              [IC L9637D / MC33660]
 *   VCC (5V) -------- Pin 6 (Vs)
 *   GND ------------ Pin 5 (GND) -------- Ground Motor (Pin 2 DLC Putih)
 *   K-LINE --------- Pin 7 (K) ---------- K-Line Motor (Pin 3 DLC Putih)
 *   MCU RX (Pin 2) - Pin 1 (RX)
 *   MCU TX (Pin 3) - Pin 4 (TX)
 *
 *   USB PC <====== Serial Baud 115200 ======> MCU Hardware Serial
 * ==============================================================================
 */

#include <Arduino.h>
#include <SoftwareSerial.h>

// Konfigurasi Pin Serial K-Line (Untuk Arduino Nano)
// Jika menggunakan ESP32, gunakan HardwareSerial Serial2
const int KLINE_RX_PIN = 10; // Hubungkan ke RX L9637D
const int KLINE_TX_PIN = 11; // Hubungkan ke TX L9637D

SoftwareSerial klineSerial(KLINE_RX_PIN, KLINE_TX_PIN);

const long PC_BAUDRATE = 115200;
const long KLINE_BAUDRATE = 10400; // Standar Yamaha Y-DIS K-Line

void sendFastInitPulse() {
    // Fast Init: 25ms LOW kemudian 25ms HIGH
    pinMode(KLINE_TX_PIN, OUTPUT);
    digitalWrite(KLINE_TX_PIN, LOW);
    delay(25);
    digitalWrite(KLINE_TX_PIN, HIGH);
    delay(25);
    klineSerial.begin(KLINE_BAUDRATE);
}

void setup() {
    // Serial ke Komputer (PC / Laptop)
    Serial.begin(PC_BAUDRATE);
    
    // Serial ke K-Line ECU
    klineSerial.begin(KLINE_BAUDRATE);

    Serial.println(F("[YAMAHA_BRIDGE] Firmware Siap. Menunggu perintah..."));
}

void loop() {
    // 1. Meneruskan data dari Komputer ke K-Line ECU
    if (Serial.available()) {
        uint8_t b = Serial.read();
        
        // Perintah khusus dari PC untuk trigger Fast Init
        if (b == 0xFF) {
            sendFastInitPulse();
            Serial.write(0xAA); // ACK Fast Init Selesai
        } else {
            klineSerial.write(b);
        }
    }

    // 2. Meneruskan respon dari K-Line ECU ke Komputer
    if (klineSerial.available()) {
        uint8_t ecuByte = klineSerial.read();
        Serial.write(ecuByte);
    }
}
