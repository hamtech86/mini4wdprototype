#include <Wire.h>
#include <Adafruit_INA3221.h>
#include <math.h>

Adafruit_INA3221 ina;

//==================================================
// CONFIG
//==================================================

const float SHUNT_RESISTOR = 0.02f;
const float TARGET_CURRENT = 5.0f;
const float KP = 15.0f;

const float VREF = 4.98f;

const float VOLTAGE_CUTOFF = 0.90f;

const unsigned long TIMEOUT_SEC = 3600;

//==================================================
// CHANNEL STRUCT
//==================================================

struct Channel
{
    int pwmPin;
    int adcPin;
    int inaChannel;

    bool running;

    int pwmValue;

    int stopReason;

    unsigned long startTime;
};

Channel ch1;
Channel ch2;

//==================================================
// VOLTAGE
//==================================================

float readBatteryVoltage(int pin)
{
    long sum = 0;

    for (int i = 0; i < 20; i++)
    {
        sum += analogRead(pin);
    }

    float adc = sum / 20.0f;

    return (adc / 1023.0f) * VREF;
}

//==================================================
// CURRENT
//==================================================

float readCurrent(int channel)
{
    float shuntVoltage =
        ina.getShuntVoltage(channel);

    float current =
        fabs(shuntVoltage) / SHUNT_RESISTOR;

    if (current < 0.01f)
    {
        current = 0.0f;
    }

    return current;
}

//==================================================
// STATE
//==================================================

String getState(Channel &ch)
{
    if (ch.running)
    {
        return "RUN";
    }

    if (ch.stopReason == 1)
    {
        return "COMPLETE";
    }

    if (ch.stopReason == 2)
    {
        return "TIMEOUT";
    }

    return "STOP";
}

//==================================================
// UPDATE CHANNEL
//==================================================

void updateChannel(Channel &ch)
{
    float voltage =
        readBatteryVoltage(ch.adcPin);

    float current =
        readCurrent(ch.inaChannel);

    float elapsed =
        (millis() - ch.startTime) / 1000.0f;

    if (ch.running)
    {
        if (voltage <= VOLTAGE_CUTOFF)
        {
            ch.running = false;
            ch.stopReason = 1;
        }

        if (elapsed >= TIMEOUT_SEC)
        {
            ch.running = false;
            ch.stopReason = 2;
        }

        if (ch.running)
        {
            float error =
                TARGET_CURRENT - current;

            float delta =
                KP * error;

            if (delta > 10.0f)
            {
                delta = 10.0f;
            }

            if (delta < -10.0f)
            {
                delta = -10.0f;
            }

            ch.pwmValue += (int)delta;

            if (ch.pwmValue > 255)
            {
                ch.pwmValue = 255;
            }

            if (ch.pwmValue < 0)
            {
                ch.pwmValue = 0;
            }
        }
        else
        {
            ch.pwmValue = 0;
        }
    }
    else
    {
        ch.pwmValue = 0;
    }

    analogWrite(ch.pwmPin, ch.pwmValue);
}

//==================================================
// DATA OUTPUT
//==================================================

void sendData(Channel &ch, const char *name)
{
    float voltage =
        readBatteryVoltage(ch.adcPin);

    float current =
        readCurrent(ch.inaChannel);

    unsigned long elapsed =
        millis() - ch.startTime;

    Serial.print("DATA,");
    Serial.print("BATTERY_DISCHARGER_V1,");
    Serial.print(name);
    Serial.print(",");
    Serial.print(elapsed);
    Serial.print(",");
    Serial.print(current, 3);
    Serial.print(",");
    Serial.print(voltage, 3);
    Serial.print(",");
    Serial.print("0,");
    Serial.print(ch.pwmValue);
    Serial.print(",");
    Serial.print("0,");
    Serial.println(getState(ch));
}

//==================================================
// COMMANDS
//==================================================

void startChannel(Channel &ch)
{
    ch.running = true;
    ch.stopReason = 0;
    ch.pwmValue = 0;
    ch.startTime = millis();
}

void stopChannel(Channel &ch)
{
    ch.running = false;
    ch.pwmValue = 0;
}

void processCommand(String cmd)
{
    cmd.trim();

    if (cmd == "INFO")
    {
        Serial.println(
            "INFO,TYPE=BATTERY,MODEL=BATTERY_DISCHARGER_V1,FW=1.0");
    }

    else if (cmd == "START1")
    {
        startChannel(ch1);
        Serial.println("ACK,START1");
    }

    else if (cmd == "STOP1")
    {
        stopChannel(ch1);
        Serial.println("ACK,STOP1");
    }

    else if (cmd == "START2")
    {
        startChannel(ch2);
        Serial.println("ACK,START2");
    }

    else if (cmd == "STOP2")
    {
        stopChannel(ch2);
        Serial.println("ACK,STOP2");
    }

    else if (cmd == "STARTALL")
    {
        startChannel(ch1);
        startChannel(ch2);

        Serial.println("ACK,STARTALL");
    }

    else if (cmd == "STOPALL")
    {
        stopChannel(ch1);
        stopChannel(ch2);

        Serial.println("ACK,STOPALL");
    }
}

//==================================================
// SETUP
//==================================================

void setup()
{
    Serial.begin(115200);

    Wire.begin();

    if (!ina.begin())
    {
        Serial.println("ERROR,INA3221");

        while (1)
        {
        }
    }

    ch1.pwmPin = 5;
    ch1.adcPin = A0;
    ch1.inaChannel = 2;

    ch2.pwmPin = 9;
    ch2.adcPin = A2;
    ch2.inaChannel = 1;

    ch1.running = false;
    ch2.running = false;

    ch1.pwmValue = 0;
    ch2.pwmValue = 0;

    pinMode(ch1.pwmPin, OUTPUT);
    pinMode(ch2.pwmPin, OUTPUT);

    analogWrite(ch1.pwmPin, 0);
    analogWrite(ch2.pwmPin, 0);

    Serial.println(
        "INFO,TYPE=BATTERY,MODEL=BATTERY_DISCHARGER_V1,FW=1.0");
}

//==================================================
// LOOP
//==================================================

void loop()
{
    if (Serial.available())
    {
        String cmd =
            Serial.readStringUntil('\n');

        processCommand(cmd);
    }

    updateChannel(ch1);
    updateChannel(ch2);

    sendData(ch1, "CH1");
    sendData(ch2, "CH2");

    delay(100);
}
