import tkinter as tk
from tkinter import ttk
import serial
import threading
import time

# =====================
# 設定
# =====================

PORT = "/dev/ttyACM0"
BAUD = 57600

# =====================
# シリアル接続
# =====================

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
except Exception as e:
    print(e)
    ser = None

# =====================
# GUI
# =====================

root = tk.Tk()
root.title("Mini4WD Motor Break-In Device")
root.geometry("500x400")

device_var = tk.StringVar(value="---")
acs1_var = tk.StringVar(value="---")
acs2_var = tk.StringVar(value="---")
therm_var = tk.StringVar(value="---")
pwm_var = tk.StringVar(value="0")
state_var = tk.StringVar(value="DISCONNECTED")

# =====================
# 表示部
# =====================

frame = ttk.Frame(root, padding=10)
frame.pack(fill="both", expand=True)

ttk.Label(frame, text="Device ID").grid(row=0, column=0, sticky="w")
ttk.Label(frame, textvariable=device_var).grid(row=0, column=1, sticky="w")

ttk.Label(frame, text="ACS712 #1").grid(row=1, column=0, sticky="w")
ttk.Label(frame, textvariable=acs1_var).grid(row=1, column=1, sticky="w")

ttk.Label(frame, text="ACS712 #2").grid(row=2, column=0, sticky="w")
ttk.Label(frame, textvariable=acs2_var).grid(row=2, column=1, sticky="w")

ttk.Label(frame, text="Thermistor").grid(row=3, column=0, sticky="w")
ttk.Label(frame, textvariable=therm_var).grid(row=3, column=1, sticky="w")

ttk.Label(frame, text="PWM").grid(row=4, column=0, sticky="w")
ttk.Label(frame, textvariable=pwm_var).grid(row=4, column=1, sticky="w")

ttk.Label(frame, text="State").grid(row=5, column=0, sticky="w")
ttk.Label(frame, textvariable=state_var).grid(row=5, column=1, sticky="w")

# =====================
# PWM設定
# =====================

ttk.Label(frame, text="Set PWM").grid(row=6, column=0)

pwm_entry = ttk.Entry(frame, width=10)
pwm_entry.insert(0, "120")
pwm_entry.grid(row=6, column=1)

# =====================
# コマンド送信
# =====================

def send_command(cmd):

    if ser is None:
        return

    try:
        ser.write((cmd + "\n").encode())
    except:
        pass

def start_motor():
    send_command("START")

def stop_motor():
    send_command("STOP")

def set_pwm():

    value = pwm_entry.get().strip()

    if value.isdigit():
        send_command(f"PWM {value}")

# =====================
# ボタン
# =====================

ttk.Button(
    frame,
    text="START",
    command=start_motor
).grid(row=7, column=0, pady=10)

ttk.Button(
    frame,
    text="STOP",
    command=stop_motor
).grid(row=7, column=1, pady=10)

ttk.Button(
    frame,
    text="SET PWM",
    command=set_pwm
).grid(row=7, column=2, pady=10)

# =====================
# シリアル受信
# =====================

def serial_worker():

    while True:

        if ser is None:
            time.sleep(1)
            continue

        try:

            line = ser.readline().decode(
                errors="ignore"
            ).strip()

            if not line:
                continue

            print(line)

            #
            # 例
            # DATA,MOTOR_BREAKIN_V1,412,438,486,120,RUN
            #

            if line.startswith("DATA"):

                parts = line.split(",")

                if len(parts) >= 7:

                    device_var.set(parts[1])
                    acs1_var.set(parts[2])
                    acs2_var.set(parts[3])
                    therm_var.set(parts[4])
                    pwm_var.set(parts[5])
                    state_var.set(parts[6])

            elif line.startswith("ID="):

                device_var.set(
                    line.replace("ID=", "")
                )

        except:
            pass

threading.Thread(
    target=serial_worker,
    daemon=True
).start()

root.mainloop()

