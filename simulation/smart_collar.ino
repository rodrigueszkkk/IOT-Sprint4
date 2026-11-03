// ================================================================================
// CLYVO VET - SMART COLLAR TELEMETRY NODE (IoT Edge)
// Disciplina: Disruptive Architectures: IoT, IoB & Generative AI - Sprint 4
// Na Sprint 4 o JSON abaixo é repassado pela ponte gateway/serial_bridge.py para a API
// (POST /api/telemetry), onde o modelo de ML e a IA Generativa processam cada leitura.
// Alunos: Kaiky Pereira (RM 564578), Leandro Guarido (RM 561760), Gabriel Solano (RM 562325)
// ================================================================================
// 100% NATIVO - SEM NENHUMA BIBLIOTECA EXTERNA (Compilação instantânea e garantida)
// Compatível com: Wokwi Simulator, Tinkercad e Arduino UNO / ESP32 Físico
// ================================================================================

// Definição de Pinos
#define PIN_PULSE_SENSOR    A0  // Potenciômetro: Frequência Cardíaca (50 a 180 BPM)
#define PIN_TEMP_SENSOR     A1  // Sensor Analógico: Temperatura Corporal (35.0 a 42.0 °C)
#define PIN_ACTIVITY_SENSOR 3   // Botão Azul: Acelerômetro / Movimento Pós-Cirúrgico
#define PIN_EMERGENCY_BTN   7   // Botão Vermelho: Botão SOS / Pânico do Tutor

#define PIN_LED_GREEN       10  // LED Verde: Estável (Sinais Normais)
#define PIN_LED_YELLOW      11  // LED Amarelo: Atenção (Variação Moderada)
#define PIN_LED_RED         12  // LED Vermelho: Crítico (Emergência Pós-Operatória)
#define PIN_BUZZER          13  // Buzzer: Alarme Sonoro de Emergência

// Metadados do Paciente (Vinculado ao PetHealthEcosystem / MySQL)
const char* DEVICE_ID = "CLYVO-COLLAR-01";
const int PET_ID = 1;
const char* PET_NAME = "Thor";
const bool NEEDS_POST_OP_CARE = true;

// Controle de Intervalo de Envio (3 segundos)
unsigned long previousMillis = 0;
const long telemetryInterval = 3000;

// ================================================================================
// CONTROLE MANUAL RÁPIDO (OPCIONAL PARA TESTES):
// Se quiser forçar um valor fixo, basta alterar aqui:
// Exemplo: float TEMPERATURA_MANUAL = 40.0; (coloque 0.0 para usar o sensor analógico)
// Exemplo: int   BPM_MANUAL         = 155;  (coloque 0 para usar o sensor analógico)
float TEMPERATURA_MANUAL = 0.0; 
int   BPM_MANUAL         = 0;
// ================================================================================

void setup() {
  Serial.begin(9600);

  // Configuração dos Pinos dos Sensores
  pinMode(PIN_PULSE_SENSOR, INPUT);
  pinMode(PIN_TEMP_SENSOR, INPUT);
  pinMode(PIN_ACTIVITY_SENSOR, INPUT_PULLUP);
  pinMode(PIN_EMERGENCY_BTN, INPUT_PULLUP);

  // Configuração dos Pinos dos Atuadores
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  // Estado Inicial: LED Verde ligado imediatamente para feedback visual instantâneo
  digitalWrite(PIN_LED_GREEN, HIGH);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  Serial.println("==================================================");
  Serial.println("  CLYVO VET - SMART COLLAR TELEMETRY NODE (IoT)   ");
  Serial.println("  Iniciando monitoramento de sinais vitais...     ");
  Serial.println("==================================================");
}

void loop() {
  unsigned long currentMillis = millis();

  // Executa imediatamente na inicialização (sem delay) e depois a cada 3 segundos
  if (previousMillis == 0 || currentMillis - previousMillis >= telemetryInterval) {
    previousMillis = currentMillis;

    // 1. Leitura da Temperatura Corporal (ou valor manual se definido)
    float temperature;
    if (TEMPERATURA_MANUAL > 0.0) {
      temperature = TEMPERATURA_MANUAL;
    } else {
      int rawTemp = analogRead(PIN_TEMP_SENSOR);
      temperature = 35.0 + ((float)rawTemp / 1023.0) * 7.0;
    }

    // 2. Leitura da Frequência Cardíaca (ou valor manual se definido)
    int heartRate;
    if (BPM_MANUAL > 0) {
      heartRate = BPM_MANUAL;
    } else {
      int rawPulse = analogRead(PIN_PULSE_SENSOR);
      heartRate = map(rawPulse, 0, 1023, 50, 180);
    }

    // 3. Leitura dos Sensores Digitais (INPUT_PULLUP: LOW = Pressionado/Ativo)
    bool isMoving = (digitalRead(PIN_ACTIVITY_SENSOR) == LOW);
    bool emergencyPressed = (digitalRead(PIN_EMERGENCY_BTN) == LOW);

    // 4. Algoritmo de Borda: Cálculo de Risco Vital
    String statusStr = "ESTAVEL";
    int riskScore = 0;

    // Regras Clínicas: Temperatura Canina/Felina (Normal: 37.5°C a 39.2°C)
    if (temperature > 39.5 || temperature < 37.2) {
      riskScore += 2; // Hipertermia grave ou hipotermia
    } else if (temperature > 39.2) {
      riskScore += 1; // Febre moderada
    }

    // Regras Clínicas: Batimentos Cardíacos (Normal repouso: 70 a 130 BPM)
    if (heartRate > 150 || heartRate < 60) {
      riskScore += 2; // Taquicardia severa ou bradicardia
    } else if (heartRate > 130) {
      riskScore += 1; // Frequência elevada
    }

    // Risco Pós-Operatório: Animal recém-operado não pode correr/se agitar
    if (NEEDS_POST_OP_CARE && isMoving) {
      riskScore += 2;
    }

    // Botão de Pânico do Tutor
    if (emergencyPressed) {
      riskScore += 4;
    }

    // 5. Atuação Física em Tempo Real (LEDs e Buzzer)
    if (riskScore >= 3) {
      statusStr = "CRITICO";
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_YELLOW, LOW);
      digitalWrite(PIN_LED_RED, HIGH);
      tone(PIN_BUZZER, 1000, 200); // Apito de emergência
    } else if (riskScore >= 1) {
      statusStr = "ATENCAO";
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_YELLOW, HIGH);
      digitalWrite(PIN_LED_RED, LOW);
      noTone(PIN_BUZZER);
    } else {
      statusStr = "ESTAVEL";
      digitalWrite(PIN_LED_GREEN, HIGH);
      digitalWrite(PIN_LED_YELLOW, LOW);
      digitalWrite(PIN_LED_RED, LOW);
      noTone(PIN_BUZZER);
    }

    // 6. Serialização JSON Padronizada para Envio ao Gateway / Nuvem / IA
    Serial.print("{\"deviceId\":\"");
    Serial.print(DEVICE_ID);
    Serial.print("\",\"petId\":");
    Serial.print(PET_ID);
    Serial.print(",\"petName\":\"");
    Serial.print(PET_NAME);
    Serial.print("\",\"temperatura\":");
    Serial.print(temperature, 1);
    Serial.print(",\"bpm\":");
    Serial.print(heartRate);
    Serial.print(",\"movimento\":");
    Serial.print(isMoving ? "true" : "false");
    Serial.print(",\"sos\":");
    Serial.print(emergencyPressed ? "true" : "false");
    Serial.print(",\"status\":\"");
    Serial.print(statusStr);
    Serial.print("\",\"riskScore\":");
    Serial.print(riskScore);
    Serial.println("}");
  }
}
