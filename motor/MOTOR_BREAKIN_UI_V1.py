
# MOTOR_BREAKIN_UI_V1.py
# シリアルポート自動探索版（DEVICE_ID確認）

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime

TARGET_DEVICE_ID = "MOTOR_BREAKIN_V1"
BAUDRATE = 57600

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Motor Break-In UI")

        self.ser = None
        self.running = True

        self.device_var = tk.StringVar(value="---")
        self.state_var = tk.StringVar(value="DISCONNECTED")
        self.pwm_var = tk.StringVar(value="0")
        self.ti_var = tk.StringVar(value="0.0")
        self.si_var = tk.StringVar(value="0.0")
        self.rpm_var = tk.StringVar(value="0")

        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Device").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, textvariable=self.device_var).grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="State").grid(row=1, column=0, sticky="w")
        ttk.Label(frm, textvariable=self.state_var).grid(row=1, column=1, sticky="w")

        ttk.Label(frm, text="PWM").grid(row=2, column=0, sticky="w")
        ttk.Label(frm, textvariable=self.pwm_var).grid(row=2, column=1, sticky="w")

        ttk.Label(frm, text="TI").grid(row=3, column=0, sticky="w")
        ttk.Label(frm, textvariable=self.ti_var).grid(row=3, column=1, sticky="w")

        ttk.Label(frm, text="SI").grid(row=4, column=0, sticky="w")
        ttk.Label(frm, textvariable=self.si_var).grid(row=4, column=1, sticky="w")

        ttk.Label(frm, text="RPM").grid(row=5, column=0, sticky="w")
        ttk.Label(frm, textvariable=self.rpm_var).grid(row=5, column=1, sticky="w")

        self.pwm_entry = ttk.Entry(frm)
        self.pwm_entry.insert(0, "40")
        self.pwm_entry.grid(row=6, column=1)

        ttk.Button(frm, text="START", command=self.start_motor).grid(row=7,column=0)
        ttk.Button(frm, text="STOP", command=self.stop_motor).grid(row=7,column=1)
        ttk.Button(frm, text="SET PWM", command=self.set_pwm).grid(row=7,column=2)

        self.connect_device()

    def connect_device(self):
        for p in serial.tools.list_ports.comports():
            try:
                s = serial.Serial(p.device, BAUDRATE, timeout=1)
                time.sleep(2)
                s.write(b"ID\n")
                resp = s.readline().decode(errors="ignore").strip()

                if TARGET_DEVICE_ID in resp:
                    self.ser = s
                    self.device_var.set(TARGET_DEVICE_ID)
                    self.state_var.set("CONNECTED")
                    threading.Thread(target=self.reader, daemon=True).start()
                    return

                s.close()

            except Exception:
                pass

        messagebox.showwarning("Device", "MOTOR_BREAKIN_V1 が見つかりません")

    def send(self, text):
        if self.ser:
            self.ser.write((text + "\n").encode())

    def start_motor(self):
        self.send("START")

    def stop_motor(self):
        self.send("STOP")

    def set_pwm(self):
        self.send(f"PWM={self.pwm_entry.get()}")

    def reader(self):
        with open("motor_log.csv", "a", newline="") as f:
            writer = csv.writer(f)

            while self.running:
                try:
                    line = self.ser.readline().decode(errors="ignore").strip()

                    if not line.startswith("DATA"):
                        continue

                    p = line.split(",")

                    if len(p) < 9:
                        continue

                    acs1 = int(p[2])
                    acs2 = int(p[3])
                    pwm = int(p[7])
                    state = p[8]

                    ti = abs(500 - acs1) / 10.0
                    si = max(0, 100 - abs(500 - acs2) / 5.0)
                    rpm = int((pwm / 255.0) * 23500)

                    self.ti_var.set(f"{ti:.1f}")
                    self.si_var.set(f"{si:.1f}")
                    self.rpm_var.set(str(rpm))
                    self.pwm_var.set(str(pwm))
                    self.state_var.set(state)

                    writer.writerow([
                        datetime.now().isoformat(),
                        line,
                        ti,
                        si,
                        rpm
                    ])

                except Exception:
                    pass

root = tk.Tk()
app = App(root)
root.mainloop()
