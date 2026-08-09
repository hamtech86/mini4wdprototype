# Filename: BatteryAnalyzer_v1_0.py
import sys
import os
import csv
import serial
import serial.tools.list_ports
import time
from collections import deque

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

SOFTWARE_VERSION = "1.0"

# -------------------------
# Serial通信用スレッド
# -------------------------
class SerialWorker(QThread):
    data_received = pyqtSignal(dict)
    switch_state_received = pyqtSignal(bool)
    
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.cmd_queue = deque()
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        except serial.SerialException:
            return

        while self.running:
            # コマンド送信
            while self.cmd_queue:
                cmd = self.cmd_queue.popleft()
                try:
                    self.ser.write((cmd+"\n").encode())
                except:
                    pass

            line = self.ser.readline().decode(errors="ignore").strip()
            if line.startswith("DATA"):
                try:
                    _, t, voltage, current, pwm, state = line.split(",")
                    data = {
                        "time": float(t),
                        "voltage": float(voltage),
                        "current": float(current),
                        "pwm": int(pwm),
                        "state": int(state)
                    }
                    self.data_received.emit(data)
                    self.switch_state_received.emit(float(voltage) > 0.1)
                except:
                    pass
        if self.ser:
            self.ser.close()

    def stop(self):
        self.running = False

    def send_cmd(self, cmd):
        self.cmd_queue.append(cmd)

# -------------------------
# Mode1/Mode2統合UI
# -------------------------
class BatteryModeWidget(QWidget):
    def __init__(self):
        super().__init__()

        # データログ
        self.voltage_log = deque(maxlen=500)
        self.current_log = deque(maxlen=500)
        self.pwm_log = deque(maxlen=500)
        self.start_time = None
        self.discharge_active = False

        # ログ管理
        self.log_base_dir = "logs"
        os.makedirs(self.log_base_dir, exist_ok=True)
        self.battery_id = ""
        self.memo = ""

        # Serial
        self.serial_thread = None

        self.init_ui()

    # -------------------------
    def init_ui(self):
        main_layout = QVBoxLayout()

        # バッテリー選択 / アノニマス / メモ
        select_layout = QHBoxLayout()
        self.battery_combo = QComboBox()
        self.load_battery_list()
        self.anonymous_check = QCheckBox("Anonymous")
        self.memo_edit = QLineEdit()
        self.memo_edit.setPlaceholderText("Memo")
        select_layout.addWidget(QLabel("Battery:"))
        select_layout.addWidget(self.battery_combo)
        select_layout.addWidget(self.anonymous_check)
        select_layout.addWidget(QLabel("Memo:"))
        select_layout.addWidget(self.memo_edit)
        main_layout.addLayout(select_layout)

        # Mode選択
        mode_layout = QHBoxLayout()
        self.mode_radio_discharge = QRadioButton("Discharge Mode")
        self.mode_radio_test = QRadioButton("Test Mode")
        self.mode_radio_discharge.setChecked(True)
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_radio_discharge)
        mode_layout.addWidget(self.mode_radio_test)
        main_layout.addLayout(mode_layout)

        # Port選択
        port_layout = QHBoxLayout()
        self.port_box = QComboBox()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_box.addItem(p.device)
        self.port_box.setCurrentText("/dev/ttyACM0")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.port_box)
        port_layout.addWidget(self.connect_btn)
        self.conn_status_label = QLabel("Status: Disconnected")
        port_layout.addWidget(self.conn_status_label)
        main_layout.addLayout(port_layout)

        # スイッチ状態
        self.switch_label = QLabel("Switch: --")
        main_layout.addWidget(self.switch_label)

        # Battery voltage + progress
        self.voltage_label = QLabel("Battery[V]: --")
        self.battery_progress = QProgressBar()
        self.battery_progress.setRange(0, 100)
        main_layout.addWidget(self.voltage_label)
        main_layout.addWidget(self.battery_progress)

        # PWM
        self.pwm_label = QLabel("PWM: -- (Output A: --)")
        self.pwm_slider = QSlider(Qt.Horizontal)
        self.pwm_slider.setRange(0, 255)
        self.pwm_slider.setValue(128)
        self.pwm_slider.valueChanged.connect(self.send_pwm)
        main_layout.addWidget(self.pwm_label)
        main_layout.addWidget(self.pwm_slider)

        # Status
        self.status_label = QLabel("Status: --")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Current
        self.current_label = QLabel("Current[A]: --")
        main_layout.addWidget(self.current_label)

        # 放電開始/停止
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_discharge)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_discharge)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        main_layout.addLayout(btn_layout)

        # 時間表示
        self.time_label = QLabel("Time: -- s")
        self.remain_label = QLabel("Remain: -- s")
        main_layout.addWidget(self.time_label)
        main_layout.addWidget(self.remain_label)

        # グラフ
        self.figure = Figure(figsize=(6,4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax2 = self.ax.twinx()
        self.ax.set_xlabel("Sample")
        self.ax.set_ylabel("Voltage / Current")
        self.ax2.set_ylabel("PWM")
        main_layout.addWidget(self.canvas)

        self.setLayout(main_layout)

        # UI更新タイマー
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(200)

    # -------------------------
    def load_battery_list(self):
        self.battery_combo.clear()
        files = [f.replace(".csv","") for f in os.listdir(self.log_base_dir) if f.endswith(".csv")]
        self.battery_combo.addItems(files)

    # -------------------------
    def connect_serial(self):
        port = self.port_box.currentText()
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread.wait()
        self.serial_thread = SerialWorker(port)
        self.serial_thread.data_received.connect(self.handle_serial)
        self.serial_thread.switch_state_received.connect(self.update_switch)
        self.serial_thread.start()
        self.conn_status_label.setText("Status: Connected")

    # -------------------------
    def handle_serial(self, data):
        self.voltage_log.append(data["voltage"])
        self.current_log.append(data["current"])
        self.pwm_log.append(data["pwm"])
        self.discharge_active = data["state"] == 1
        if self.discharge_active and self.start_time is None:
            self.start_time = time.time()

    # -------------------------
    def update_switch(self, state_on):
        self.switch_label.setText(f"Switch: {'ON' if state_on else 'OFF'}")

    # -------------------------
    def update_ui(self):
        if self.voltage_log:
            voltage = self.voltage_log[-1]
            current = self.current_log[-1]
            pwm = self.pwm_log[-1]

            # Battery gauge
            percent = int(min(max((voltage-0.9)/0.5*100,0),100))
            self.battery_progress.setValue(percent)
            self.voltage_label.setText(f"Battery[V]: {voltage:.3f}")
            self.current_label.setText(f"Current[A]: {current:.2f}")
            output_a = pwm/255*5.0
            self.pwm_label.setText(f"PWM: {pwm} (Output A: {output_a:.2f})")

            # Status
            if voltage <= 0.9:
                self.status_label.setText("Status: Finish")
                status_color = "green"
            elif voltage <= 0.95:
                self.status_label.setText("Status: Warning")
                status_color = "blue"
            elif self.discharge_active:
                self.status_label.setText("Status: Discharging")
                status_color = "orange"
            else:
                self.status_label.setText("Status: Idle")
                status_color = "gray"
            self.status_label.setStyleSheet(f"background-color: {status_color}; color:white;")

            # Time
            if self.start_time:
                elapsed = time.time() - self.start_time
                self.time_label.setText(f"Time: {elapsed:.1f} s")
            else:
                self.time_label.setText("Time: -- s")

            # Remaining
            remain = self.predict_time()
            if remain:
                self.remain_label.setText(f"Remain: {remain:.0f} s")
            else:
                self.remain_label.setText("Remain: -- s")

            # Graph
            self.ax.clear()
            self.ax2.clear()
            self.ax.plot(list(self.voltage_log), label="Voltage[V]", color="orange")
            self.ax.plot(list(self.current_log), label="Current[A]", color="blue")
            self.ax2.plot(list(self.pwm_log), label="PWM", color="green")
            self.ax.legend(loc="upper left")
            self.ax2.legend(loc="upper right")
            self.canvas.draw()

    # -------------------------
    def predict_time(self):
        if len(self.voltage_log)<10:
            return None
        dv = self.voltage_log[-1]-self.voltage_log[0]
        dt = len(self.voltage_log)*0.2
        if dv>=0:
            return None
        slope = dv/dt
        remain = (0.9-self.voltage_log[-1])/slope
        return abs(remain)

    # -------------------------
    def start_discharge(self):
        if self.serial_thread:
            self.serial_thread.send_cmd("START")
            self.start_time = time.time()

    def stop_discharge(self):
        if self.serial_thread:
            self.serial_thread.send_cmd("STOP")

    def send_pwm(self):
        val = self.pwm_slider.value()
        if self.serial_thread:
            self.serial_thread.send_cmd(f"PWM{val}")

# -------------------------
# Main Window
# -------------------------
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        tabs = QTabWidget()
        tabs.addTab(BatteryModeWidget(),"Mode1/2 Battery")
        self.setCentralWidget(tabs)
        self.setWindowTitle(f"Battery Analyzer v{SOFTWARE_VERSION}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())
