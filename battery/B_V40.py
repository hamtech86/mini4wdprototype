import serial
import serial.tools.list_ports
import threading
import time
import tkinter as tk
from tkinter import ttk
import csv
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


class Analyzer:

    def __init__(self):
        self.reset()

    def reset(self):
        self.time = 0
        self.voltage = 0
        self.current = 0
        self.power = 0
        self.pwm = 0
        self.state = "IDLE"

        self.capacity = 0
        self.internal_r = 0

        self.open_voltage = None
        self.last_time = None

    def update(self, t, v, c, p, pwm, state):

        self.time = t
        self.voltage = v
        self.current = c
        self.power = p
        self.pwm = pwm

        self.state = ["IDLE","RUN","DONE","PAUSE"][state]

        if self.last_time is not None:
            dt = t - self.last_time
            if dt > 0:
                self.capacity += c * dt / 3.6

        if c < 0.1:
            self.open_voltage = v

        if self.open_voltage and c > 1:
            self.internal_r = (self.open_voltage - v) / c

        self.last_time = t


class SerialManager(threading.Thread):

    def __init__(self, analyzer):
        super().__init__()
        self.analyzer = analyzer
        self.ser = None
        self.running = True
        self.connected = False
        self.buffer = ""

    def connect(self, port):

        self.ser = serial.Serial(port, 115200, timeout=0.1)
        self.connected = True

    def disconnect(self):

        if self.ser:
            self.ser.close()
        self.connected = False

    def send(self, cmd):

        if self.connected:
            self.ser.write((cmd + "\n").encode())

    def run(self):

        while self.running:

            if not self.connected:
                time.sleep(0.1)
                continue

            data = self.ser.read(256).decode(errors="ignore")

            if data:
                self.buffer += data

                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n",1)
                    self.process(line.strip())

    def process(self, line):

        if not line.startswith("DATA"):
            return

        p = line.split(",")

        if len(p) < 7:
            return

        try:
            self.analyzer.update(
                float(p[1]),
                float(p[2]),
                float(p[3]),
                float(p[4]),
                int(p[5]),
                int(p[6])
            )
        except:
            pass


class Logger:

    def __init__(self):
        ts = int(time.time())
        self.file = open(f"{LOG_DIR}/log_{ts}.csv","w",newline="")
        self.writer = csv.writer(self.file)

        self.writer.writerow([
            "Time","Voltage","Current","Power",
            "PWM","InternalR","Capacity","State"
        ])

    def write(self, a):

        self.writer.writerow([
            a.time, a.voltage, a.current,
            a.power, a.pwm, a.internal_r,
            a.capacity, a.state
        ])

        self.file.flush()


class App:

    def __init__(self, root):

        self.root = root
        self.root.title("Rev3.5 Analyzer")

        self.analyzer = Analyzer()
        self.serial = SerialManager(self.analyzer)
        self.serial.start()

        self.logger = None

        # --- COM選択 ---
        self.port_box = ttk.Combobox(root, values=self.get_ports())
        self.port_box.pack()

        tk.Button(root, text="接続", command=self.connect).pack()
        tk.Button(root, text="切断", command=self.disconnect).pack()

        # --- 制御 ---
        tk.Button(root, text="START", command=self.start).pack()
        tk.Button(root, text="STOP", command=self.stop).pack()

        # --- 表示 ---
        self.label = tk.Label(root, text="---", font=("Arial",12))
        self.label.pack()

        self.update_ui()

    def get_ports(self):

        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self):

        port = self.port_box.get()
        self.serial.connect(port)

    def disconnect(self):

        self.serial.disconnect()

    def start(self):

        self.analyzer.reset()
        self.logger = Logger()
        self.serial.send("START")

    def stop(self):

        self.serial.send("STOP")

    def update_ui(self):

        a = self.analyzer

        if self.logger:
            self.logger.write(a)

        text = f"""
STATE: {a.state}
Voltage: {a.voltage:.3f} V
Current: {a.current:.3f} A
PWM: {a.pwm}

InternalR: {a.internal_r:.4f} Ω
Capacity: {a.capacity:.2f} mAh
"""

        self.label.config(text=text)

        self.root.after(100, self.update_ui)


root = tk.Tk()
app = App(root)
root.mainloop()

