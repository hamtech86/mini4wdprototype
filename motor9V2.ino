// ================================================================
// モーター慣らし（ブレイクイン）／定格測定スケッチ
// Arduino + L298N + LM2596 (降圧) + 分圧4:1 (A0: LM2596, A1: Motor OUT)
// ================================================================

const int pwmPin   = 6;   // ENA (PWM)
const int inHigh   = 7;   // IN1
const int inLow    = 8;   // IN2
const int vinPin   = A0;  // LM2596 出力分圧
const int voutPin  = A1;  // Motor 出力分圧

// ------------------------------------------------------------
// 【モード設定】
// 1 = ブレイクインモード（多段ステップ）
// 2 = 定格測定モード（単一動作）
// ------------------------------------------------------------
const int modeSelect = 2;

// ------------------------------------------------------------
// 共通パラメータ
// ------------------------------------------------------------
const unsigned long forcedStartTime = 800;  // 起動強制時間(ms)
const int startPWM = 170;                   // 起動時PWM
const int minPWM   = 30;                    // 最小PWM
float Kp = 12.0;                            // 比例ゲイン
const float voltageDivider = 5.0;           // 分圧比逆数 (4:1)
const int MAX_DELTA = 8;                    // PWM急変抑制
const int AVG_N_VIN = 4;
const int AVG_N_VOUT = 8;

// ------------------------------------------------------------
// ブレイクインモード設定（5ステップまで）
// ------------------------------------------------------------
struct Step {
  float voltage;
  unsigned long duration_s;
  int direction;
  unsigned long interval_s;
};

Step steps[5] = {
  {2.0, 60,  1, 30},
  {2.0, 60, -1, 30},
  {7.5, 60,  1, 60},
  {7.5, 60,  -1, 60},
  {0.0,   0,  0, 0}
};

// ------------------------------------------------------------
// 定格測定モード設定（単一ステップ）
// ------------------------------------------------------------
float ratedVoltage   = 3.0;       // 定格電圧（例：3.0V）
unsigned long ratedDuration = 60; // 測定時間（秒）
int ratedDirection   = 1;         // 1=順転, -1=逆転

// ------------------------------------------------------------
// 内部変数
// ------------------------------------------------------------
int vinBuf[AVG_N_VIN];
int voutBuf[AVG_N_VOUT];
int vinIdx = 0, voutIdx = 0;
long vinSum = 0, voutSum = 0;
int lastPwm = 0;
unsigned long forcedStartMillis = 0;

// ------------------------------------------------------------
// 関数群
// ------------------------------------------------------------
float readVinSmoothed() {
  int raw = analogRead(vinPin);
  vinSum -= vinBuf[vinIdx];
  vinBuf[vinIdx] = raw;
  vinSum += vinBuf[vinIdx];
  vinIdx = (vinIdx + 1) % AVG_N_VIN;
  float avg = (float)vinSum / AVG_N_VIN;
  return avg * (5.0 / 1023.0) * voltageDivider;
}

float readVoutSmoothed() {
  int raw = analogRead(voutPin);
  voutSum -= voutBuf[voutIdx];
  voutBuf[voutIdx] = raw;
  voutSum += voutBuf[voutIdx];
  voutIdx = (voutIdx + 1) % AVG_N_VOUT;
  float avg = (float)voutSum / AVG_N_VOUT;
  return avg * (5.0 / 1023.0) * voltageDivider;
}

void setDirection(int dir) {
  if (dir >= 0) {
    digitalWrite(inHigh, HIGH);
    digitalWrite(inLow, LOW);
  } else {
    digitalWrite(inHigh, LOW);
    digitalWrite(inLow, HIGH);
  }
}

void applyPwmWithLimit(int desiredPwm) {
  int delta = desiredPwm - lastPwm;
  if (delta > MAX_DELTA) delta = MAX_DELTA;
  if (delta < -MAX_DELTA) delta = -MAX_DELTA;
  int applied = constrain(lastPwm + delta, 0, 255);
  analogWrite(pwmPin, applied);
  lastPwm = applied;
}

float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  if (in_max - in_min == 0) return out_min;
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

// ------------------------------------------------------------
// setup
// ------------------------------------------------------------
void setup() {
  pinMode(pwmPin, OUTPUT);
  pinMode(inHigh, OUTPUT);
  pinMode(inLow, OUTPUT);
  Serial.begin(115200);
  Serial.println("=== Motor Controller Start ===");

  for (int i = 0; i < AVG_N_VIN; ++i) vinBuf[i] = analogRead(vinPin);
  for (int i = 0; i < AVG_N_VOUT; ++i) voutBuf[i] = analogRead(voutPin);
  for (int i = 0; i < AVG_N_VIN; ++i) vinSum += vinBuf[i];
  for (int i = 0; i < AVG_N_VOUT; ++i) voutSum += voutBuf[i];

  lastPwm = minPWM;
  analogWrite(pwmPin, lastPwm);
}

// ------------------------------------------------------------
// loop
// ------------------------------------------------------------
void loop() {
  if (modeSelect == 1) {
    runBreakInMode();
  } else if (modeSelect == 2) {
    runRatedMode();
  }

  Serial.println("=== All steps complete ===");
  while (1) delay(1000);
}

// ------------------------------------------------------------
// ブレイクインモード（多段ステップ）
// ------------------------------------------------------------
void runBreakInMode() {
  Serial.println("[MODE] Break-in Mode");

  for (int i = 0; i < 5; ++i) {
    Step s = steps[i];
    if (s.voltage <= 0.0 || s.duration_s == 0) continue;

    Serial.print("Step "); Serial.print(i+1);
    Serial.print("  Target: "); Serial.print(s.voltage);
    Serial.print("V  Dir: "); Serial.print(s.direction);
    Serial.print("  Duration: "); Serial.print(s.duration_s);
    Serial.println("s");

    runMotorStep(s.voltage, s.duration_s, s.direction);
    delay(s.interval_s * 1000UL);
  }
}

// ------------------------------------------------------------
// 定格測定モード
// ------------------------------------------------------------
void runRatedMode() {
  Serial.println("[MODE] Rated Measurement Mode");
  Serial.print("Target: "); Serial.print(ratedVoltage);
  Serial.print("V  Dir: "); Serial.print(ratedDirection);
  Serial.print("  Duration: "); Serial.print(ratedDuration);
  Serial.println("s");

  runMotorStep(ratedVoltage, ratedDuration, ratedDirection);
}

// ------------------------------------------------------------
// 共通モーターステップ処理
// ------------------------------------------------------------
void runMotorStep(float targetV, unsigned long duration_s, int dir) {
  setDirection(dir);
  forcedStartMillis = millis();

  unsigned long start = millis();
  unsigned long end = start + duration_s * 1000UL;
  bool switchedToVoutControl = false;

  while (millis() < end) {
    float vin = readVinSmoothed();
    float vout = readVoutSmoothed();
    int desiredPwm = lastPwm;

    if (millis() - forcedStartMillis < forcedStartTime) {
      desiredPwm = startPWM;
    } else {
      float switchThreshold = min(targetV, 3.0);
      if (vout >= switchThreshold) switchedToVoutControl = true;

      if (!switchedToVoutControl) {
        float vinClamped = constrain(vin, 0.0, 11.0);
        desiredPwm = (int)mapFloat(vinClamped, 0.0, 11.0, (float)minPWM, (float)startPWM);
      } else {
        float error = targetV - vout;
        float raw = Kp * error + minPWM;
        desiredPwm = (int)raw;
        desiredPwm = constrain(desiredPwm, minPWM, 255);
      }
    }

    applyPwmWithLimit(desiredPwm);

    Serial.print("V_in="); Serial.print(vin, 2);
    Serial.print("V | V_out="); Serial.print(vout, 2);
    Serial.print("V | PWM="); Serial.print(lastPwm);
    Serial.println();
    delay(25);
  }

  analogWrite(pwmPin, 0);
  Serial.println("Step complete, motor stopped.");
}
