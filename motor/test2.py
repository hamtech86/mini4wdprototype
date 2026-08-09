# ============================================================
# START / STOP Test
# ============================================================

import serial
import time

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

PORT = "/dev/ttyACM0"
BAUDRATE = 115200

# ------------------------------------------------------------
# OPEN
# ------------------------------------------------------------

print("Opening serial...")

ser = serial.Serial(PORT, BAUDRATE, timeout=1)

time.sleep(2)

# 起動時ゴミデータ除去
ser.reset_input_buffer()

print("Connected")

# ------------------------------------------------------------
# FW CHECK
# ------------------------------------------------------------

ser.write(b"GET_FW\n")

time.sleep(0.5)

while ser.in_waiting:

    line = ser.readline().decode(errors="ignore").strip()

    print("RX:", line)

# ------------------------------------------------------------
# SET PWM
# ------------------------------------------------------------

PWM = 160

cmd = f"SET_PWM,{PWM}\n"

print("TX:", cmd.strip())

ser.write(cmd.encode())

time.sleep(0.5)

while ser.in_waiting:

    line = ser.readline().decode(errors="ignore").strip()

    print("RX:", line)

# ------------------------------------------------------------
# START
# ------------------------------------------------------------

print("TX: START")

ser.write(b"START\n")

# ------------------------------------------------------------
# RECEIVE CSV
# ------------------------------------------------------------

start_time = time.time()

while time.time() - start_time < 10:

    if ser.in_waiting:

        line = ser.readline().decode(errors="ignore").strip()

        print("RX:", line)

# ------------------------------------------------------------
# STOP
# ------------------------------------------------------------

print("TX: STOP")

ser.write(b"STOP\n")

time.sleep(1)

while ser.in_waiting:

    line = ser.readline().decode(errors="ignore").strip()

    print("RX:", line)

# ------------------------------------------------------------
# CLOSE
# ------------------------------------------------------------

ser.close()

print("Done")

