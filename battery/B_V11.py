import sys
import os
import json
import time
import random

from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer
import pyqtgraph as pg

import serial


LOG_DIR = "battery_logs"


class BatteryLab(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Mini4WD Battery Lab V2")

        self.serial = None
        self.connected = False

        self.dummy_mode = False

        self.recording = False
        self.current_log = []

        self.time_data = []
        self.voltage_data = []

        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(100)

    def init_ui(self):

        main = QWidget()
        layout = QVBoxLayout()

        header = self.create_header()
        layout.addWidget(header)

        self.tabs = QTabWidget()

        self.mode1 = self.create_mode1()
        self.mode2 = self.create_mode2()
        self.mode5 = self.create_mode5()

        self.tabs.addTab(self.mode1, "Mode1 Discharge")
        self.tabs.addTab(self.mode2, "Mode2 Evaluation")
        self.tabs.addTab(QWidget(), "Mode3 Pair")
        self.tabs.addTab(QWidget(), "Mode4 Training")
        self.tabs.addTab(self.mode5, "Mode5 Logs")

        layout.addWidget(self.tabs)

        main.setLayout(layout)

        self.setCentralWidget(main)

    def create_header(self):

        w = QWidget()
        l = QHBoxLayout()

        self.serial_label = QLabel("Serial: Disconnected")

        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.clicked.connect(self.connect_serial)

        self.dummy_cb = QCheckBox("Dummy Mode")
        self.dummy_cb.stateChanged.connect(self.toggle_dummy)

        l.addWidget(self.serial_label)
        l.addWidget(self.connect_btn)
        l.addWidget(self.dummy_cb)

        w.setLayout(l)

        return w

    def create_mode1(self):

        w = QWidget()
        l = QVBoxLayout()

        info = QHBoxLayout()

        self.voltage_label = QLabel("Voltage:0")
        self.current_label = QLabel("Current:0")
        self.power_label = QLabel("Power:0")

        info.addWidget(self.voltage_label)
        info.addWidget(self.current_label)
        info.addWidget(self.power_label)

        l.addLayout(info)

        ctrl = QHBoxLayout()

        self.start_btn = QPushButton("START")
        self.stop_btn = QPushButton("STOP")

        self.start_btn.clicked.connect(self.start_record)
        self.stop_btn.clicked.connect(self.stop_record)

        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.stop_btn)

        l.addLayout(ctrl)

        self.graph = pg.PlotWidget()

        self.curve = self.graph.plot()

        l.addWidget(self.graph)

        w.setLayout(l)

        return w

    def create_mode2(self):

        w = QWidget()
        l = QVBoxLayout()

        self.speed_label = QLabel("Speed:")
        self.stamina_label = QLabel("Stamina:")
        self.health_label = QLabel("Health:")
        self.type_label = QLabel("Type:")

        l.addWidget(self.speed_label)
        l.addWidget(self.stamina_label)
        l.addWidget(self.health_label)
        l.addWidget(self.type_label)

        w.setLayout(l)

        return w

    def create_mode5(self):

        w = QWidget()
        l = QVBoxLayout()

        self.log_list = QListWidget()

        l.addWidget(self.log_list)

        self.refresh_logs()

        w.setLayout(l)

        return w

    def refresh_logs(self):

        self.log_list.clear()

        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

        for f in os.listdir(LOG_DIR):
            self.log_list.addItem(f)

    def toggle_dummy(self):

        self.dummy_mode = self.dummy_cb.isChecked()

    def connect_serial(self):

        try:

            self.serial = serial.Serial("/dev/ttyACM0", 115200)

            self.connected = True

            self.serial_label.setText("Serial: Connected")

        except:

            self.serial_label.setText("Serial: Error")

    def start_record(self):

        self.recording = True

        self.current_log = []

        self.time_data = []
        self.voltage_data = []

    def stop_record(self):

        self.recording = False

        if len(self.current_log) > 0:

            self.save_log()

            self.evaluate_battery()

    def save_log(self):

        if not os.path.exists(LOG_DIR):

            os.makedirs(LOG_DIR)

        name = time.strftime("BAT_%Y%m%d_%H%M%S.json")

        path = os.path.join(LOG_DIR, name)

        with open(path, "w") as f:

            json.dump(self.current_log, f)

        self.refresh_logs()

    def evaluate_battery(self):

        power = [x["power"] for x in self.current_log]

        if len(power) < 5:
            return

        speed = sum(power[:5]) / 5

        energy = 0

        for p in power:
            energy += p

        stamina = energy / len(power)

        health = max(0, 100 - stamina)

        if speed > stamina * 1.2:
            t = "SPRINTER"
        elif stamina > speed * 1.2:
            t = "STAYER"
        else:
            t = "CLASSIC"

        self.speed_label.setText(f"Speed:{speed:.2f}")
        self.stamina_label.setText(f"Stamina:{stamina:.2f}")
        self.health_label.setText(f"Health:{health:.1f}")
        self.type_label.setText(f"Type:{t}")

    def parse_line(self, line):

        p = line.split(",")

        if p[0] != "DATA":
            return None

        try:

            return {
                "time": float(p[1]),
                "voltage": float(p[2]),
                "current": float(p[3]),
                "power": float(p[4]),
                "pwm": int(p[5]),
                "state": p[6]
            }

        except:

            return None

    def dummy_data(self):

        t = len(self.time_data)

        v = 1.4 - t * 0.001 + random.uniform(-0.005, 0.005)

        i = 2 + random.uniform(-0.1, 0.1)

        p = v * i

        return {

            "time": t,
            "voltage": v,
            "current": i,
            "power": p,
            "pwm": 120,
            "state": "DISCHARGE"
        }

    def read_serial(self):

        if not self.connected:
            return None

        try:

            line = self.serial.readline().decode().strip()

            return line

        except:

            return None

    def update_loop(self):

        if self.dummy_mode:

            data = self.dummy_data()

        else:

            line = self.read_serial()

            if line is None:
                return

            data = self.parse_line(line)

            if data is None:
                return

        self.update_ui(data)

    def update_ui(self, data):

        v = data["voltage"]
        i = data["current"]
        p = data["power"]

        self.voltage_label.setText(f"Voltage:{v:.3f}")
        self.current_label.setText(f"Current:{i:.3f}")
        self.power_label.setText(f"Power:{p:.3f}")

        self.time_data.append(data["time"])
        self.voltage_data.append(v)

        self.curve.setData(self.time_data, self.voltage_data)

        if self.recording:

            self.current_log.append(data)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    win = BatteryLab()

    win.show()

    sys.exit(app.exec())

