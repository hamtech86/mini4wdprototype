import sys
import serial
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QHBoxLayout, QTabWidget,
    QComboBox, QCheckBox
)

from PyQt5.QtCore import QTimer

import pyqtgraph as pg


PORT = "/dev/ttyACM0"
BAUD = 115200


class SerialReader(threading.Thread):

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.running = True

        try:
            self.ser = serial.Serial(PORT, BAUD, timeout=1)
            print("Serial connected")
        except:
            self.ser = None
            print("Serial connection failed")

    def run(self):

        if not self.ser:
            return

        while self.running:

            try:

                line = self.ser.readline().decode(
                    "utf-8", errors="ignore"
                ).strip()

                if not line:
                    continue

                if not line.startswith("DATA"):
                    continue

                parts = line.split(",")

                if len(parts) < 7:
                    continue

                data = {
                    "time": float(parts[1]),
                    "voltage": float(parts[2]),
                    "current": float(parts[3]),
                    "power": float(parts[4]),
                    "pwm": int(parts[5]),
                    "state": int(parts[6])
                }

                self.callback(data)

            except Exception as e:
                print("Serial error:", e)

    def send(self, cmd):

        if self.ser:
            self.ser.write((cmd + "\n").encode())

    def stop(self):
        self.running = False


class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Battery Analyzer V1.4")

        self.time_data = []
        self.voltage_data = []
        self.current_data = []

        self.init_ui()

        self.reader = SerialReader(self.on_serial)
        self.reader.start()

    def init_ui(self):

        layout = QVBoxLayout()

        # -----------------
        # HEADER
        # -----------------

        header = QVBoxLayout()

        self.device_label = QLabel("Device: Connected")
        header.addWidget(self.device_label)

        self.switch_label = QLabel("Switch: OFF")
        header.addWidget(self.switch_label)

        self.state_bar = QLabel("STATUS")
        self.state_bar.setStyleSheet(
            "background-color: gray; color:white; padding:5px"
        )

        header.addWidget(self.state_bar)

        # LOG CONTROL

        log_row = QHBoxLayout()

        self.log_combo = QComboBox()
        self.log_combo.addItem("battery_log_1")

        log_row.addWidget(self.log_combo)

        load_btn = QPushButton("読み込み")
        log_row.addWidget(load_btn)

        new_btn = QPushButton("新規追加")
        log_row.addWidget(new_btn)

        self.anon_check = QCheckBox("アノニマス")
        log_row.addWidget(self.anon_check)

        header.addLayout(log_row)

        layout.addLayout(header)

        # -----------------
        # TABS
        # -----------------

        tabs = QTabWidget()

        tabs.addTab(self.mode1_ui(), "Mode1")
        tabs.addTab(self.mode2_ui(), "Mode2")

        layout.addWidget(tabs)

        self.setLayout(layout)

    # -----------------
    # MODE1
    # -----------------

    def mode1_ui(self):

        widget = QWidget()
        layout = QVBoxLayout()

        btn_row = QHBoxLayout()

        start_btn = QPushButton("放電")
        start_btn.clicked.connect(
            lambda: self.reader.send("START")
        )

        pause_btn = QPushButton("一時停止")
        pause_btn.clicked.connect(
            lambda: self.reader.send("PAUSE")
        )

        stop_btn = QPushButton("停止")
        stop_btn.clicked.connect(
            lambda: self.reader.send("STOP")
        )

        btn_row.addWidget(start_btn)
        btn_row.addWidget(pause_btn)
        btn_row.addWidget(stop_btn)

        layout.addLayout(btn_row)

        self.time_label = QLabel("Time: 0 s")
        layout.addWidget(self.time_label)

        self.voltage_label = QLabel("Voltage: 0 V")
        layout.addWidget(self.voltage_label)

        self.current_label = QLabel("Current: 0 A")
        layout.addWidget(self.current_label)

        # GRAPH

        self.graph = pg.PlotWidget()
        self.graph.addLegend()

        self.voltage_curve = self.graph.plot(
            pen="g", name="Voltage"
        )

        self.current_curve = self.graph.plot(
            pen="y", name="Current"
        )

        layout.addWidget(self.graph)

        widget.setLayout(layout)

        return widget

    # -----------------
    # MODE2
    # -----------------

    def mode2_ui(self):

        widget = QWidget()

        layout = QVBoxLayout()

        label = QLabel("評価モード（予定）")

        layout.addWidget(label)

        widget.setLayout(layout)

        return widget

    # -----------------
    # SERIAL RECEIVE
    # -----------------

    def on_serial(self, data):

        t = data["time"]
        v = data["voltage"]
        c = data["current"]
        state = data["state"]

        self.time_data.append(t)
        self.voltage_data.append(v)
        self.current_data.append(c)

        self.time_label.setText(f"Time: {t:.1f} s")
        self.voltage_label.setText(f"Voltage: {v:.3f} V")
        self.current_label.setText(f"Current: {c:.3f} A")

        self.voltage_curve.setData(
            self.time_data,
            self.voltage_data
        )

        self.current_curve.setData(
            self.time_data,
            self.current_data
        )

        # STATUS BAR

        if state == 0:
            self.state_bar.setText("STOP")
            self.state_bar.setStyleSheet(
                "background-color: gray; color:white"
            )

        elif state == 1:
            self.state_bar.setText("DISCHARGE")
            self.state_bar.setStyleSheet(
                "background-color: green; color:white"
            )

        elif state == 2:
            self.state_bar.setText("COMPLETE")
            self.state_bar.setStyleSheet(
                "background-color: blue; color:white"
            )

        elif state == 3:
            self.state_bar.setText("PAUSE")
            self.state_bar.setStyleSheet(
                "background-color: orange; color:white"
            )


if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = MainWindow()
    w.resize(800, 600)
    w.show()

    sys.exit(app.exec_())

