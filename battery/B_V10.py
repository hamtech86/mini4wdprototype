import sys
import serial
import random
import time

from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer
import pyqtgraph as pg


class BatteryLab(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Mini4WD Battery Lab V1")
        self.resize(1000, 700)

        self.serial = None
        self.dummy_mode = False
        self.anonymous_mode = False

        self.time_data = []
        self.voltage_data = []

        self.v_idle = None
        self.internal_resistance = None

        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(100)

    def init_ui(self):

        main_widget = QWidget()
        main_layout = QVBoxLayout()

        header = self.create_header()
        main_layout.addWidget(header)

        self.tabs = QTabWidget()

        self.mode1 = self.create_mode1()
        self.tabs.addTab(self.mode1, "Mode1 Discharge")

        self.tabs.addTab(QWidget(), "Mode2 Evaluation")
        self.tabs.addTab(QWidget(), "Mode3 Training")
        self.tabs.addTab(QWidget(), "Mode4 Pair")
        self.tabs.addTab(QWidget(), "Mode5 Logs")

        main_layout.addWidget(self.tabs)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def create_header(self):

        widget = QWidget()
        layout = QHBoxLayout()

        device_layout = QVBoxLayout()

        self.serial_label = QLabel("Serial : Disconnected")
        self.switch_label = QLabel("Switch : OFF")
        self.discharge_label = QLabel("Discharge : IDLE")

        device_layout.addWidget(self.serial_label)
        device_layout.addWidget(self.switch_label)
        device_layout.addWidget(self.discharge_label)

        layout.addLayout(device_layout)

        layout.addStretch()

        log_layout = QHBoxLayout()

        self.log_select = QComboBox()
        self.load_btn = QPushButton("Load")
        self.new_btn = QPushButton("+ Battery")

        self.anonymous_cb = QCheckBox("Anonymous")
        self.dummy_cb = QCheckBox("Dummy")

        self.anonymous_cb.stateChanged.connect(self.toggle_anonymous)
        self.dummy_cb.stateChanged.connect(self.toggle_dummy)

        log_layout.addWidget(self.log_select)
        log_layout.addWidget(self.load_btn)
        log_layout.addWidget(self.new_btn)
        log_layout.addWidget(self.anonymous_cb)
        log_layout.addWidget(self.dummy_cb)

        layout.addLayout(log_layout)

        widget.setLayout(layout)

        return widget

    def create_mode1(self):

        widget = QWidget()
        layout = QVBoxLayout()

        info_layout = QHBoxLayout()

        self.voltage_label = QLabel("Voltage : 0.00 V")
        self.current_label = QLabel("Current : 0.00 A")
        self.ir_label = QLabel("Internal Resistance : -- mΩ")

        info_layout.addWidget(self.voltage_label)
        info_layout.addWidget(self.current_label)
        info_layout.addWidget(self.ir_label)

        layout.addLayout(info_layout)

        self.graph = pg.PlotWidget()
        self.graph.setBackground("w")
        self.graph.setLabel('left', 'Voltage', 'V')
        self.graph.setLabel('bottom', 'Time', 's')

        self.voltage_curve = self.graph.plot(pen=pg.mkPen(width=2))

        layout.addWidget(self.graph)

        widget.setLayout(layout)

        return widget

    def toggle_dummy(self):

        self.dummy_mode = self.dummy_cb.isChecked()

        if self.dummy_mode:
            self.serial_label.setText("Serial : Dummy Mode")
        else:
            self.serial_label.setText("Serial : Disconnected")

    def toggle_anonymous(self):

        self.anonymous_mode = self.anonymous_cb.isChecked()

    def connect_serial(self):

        try:
            self.serial = serial.Serial("/dev/ttyACM0", 115200, timeout=0.1)
            self.serial_label.setText("Serial : Connected")
        except:
            self.serial_label.setText("Serial : Error")

    def read_serial(self):

        if self.serial is None:
            return None

        try:
            line = self.serial.readline().decode().strip()
            return line
        except:
            return None

    def parse_data(self, line):

        parts = line.split(",")

        if parts[0] != "DATA":
            return None

        try:

            data = {
                "time": float(parts[1]),
                "voltage": float(parts[2]),
                "current": float(parts[3]),
                "switch": int(parts[5]),
                "discharge": int(parts[6])
            }

            return data

        except:
            return None

    def generate_dummy(self):

        t = len(self.time_data) * 0.1
        voltage = 1.4 - (t * 0.001) + random.uniform(-0.005, 0.005)
        current = -5 + random.uniform(-0.2, 0.2)

        return {
            "time": t,
            "voltage": voltage,
            "current": current,
            "switch": 1,
            "discharge": 1
        }

    def update_loop(self):

        if self.dummy_mode:

            data = self.generate_dummy()

        else:

            line = self.read_serial()

            if line is None:
                return

            data = self.parse_data(line)

            if data is None:
                return

        self.update_ui(data)

    def update_ui(self, data):

        voltage = data["voltage"]
        current = data["current"]

        self.voltage_label.setText(f"Voltage : {voltage:.3f} V")
        self.current_label.setText(f"Current : {current:.3f} A")

        if data["switch"] == 1:
            self.switch_label.setText("Switch : ON")
        else:
            self.switch_label.setText("Switch : OFF")

        state_map = {
            0: "IDLE",
            1: "RUN",
            2: "PAUSE",
            3: "STOP"
        }

        self.discharge_label.setText(
            f"Discharge : {state_map.get(data['discharge'], 'UNKNOWN')}"
        )

        self.time_data.append(data["time"])
        self.voltage_data.append(voltage)

        self.voltage_curve.setData(self.time_data, self.voltage_data)

        if self.v_idle is None and abs(current) < 0.01:
            self.v_idle = voltage

        if self.v_idle and abs(current) > 0.5:

            r = (self.v_idle - voltage) / abs(current)

            self.internal_resistance = r * 1000

            self.ir_label.setText(
                f"Internal Resistance : {self.internal_resistance:.1f} mΩ"
            )


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = BatteryLab()
    window.show()

    sys.exit(app.exec())

