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

# -------------------------
# Serial通信用スレッド
# -------------------------
class SerialWorker(QThread):
    data_received = pyqtSignal(dict)
    switch_state_received = pyqtSignal(bool)
    connection_state = pyqtSignal(bool)

    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.connection_state.emit(True)
        except serial.SerialException:
            self.connection_state.emit(False)
            return

        while self.running:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line:
                    # デバッグ用出力
                    print("Serial:", line)

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
                    except Exception as e:
                        print("Parse error:", e, line)
            except Exception as e:
                print("Serial read error:", e)

        if self.ser:
            self.ser.close()
            self.connection_state.emit(False)

    def stop(self):
        self.running = False
        self.wait()

# -------------------------
# Mode1 放電UI
# -------------------------
class Mode1_Discharge(QWidget):
    def __init__(self):
        super().__init__()

        # データログ
        self.voltage_log = deque(maxlen=500)
        self.current_log = deque(maxlen=500)
        self.pwm_log = deque(maxlen=500)
        self.start_time = None
        self.discharge_active = False

        # ログ管理
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        self.battery_id = ""
        self.memo = ""

        # PWM初期値
        self.pwm_value = 128

        self.init_ui()
        self.serial_thread = None

    # -------------------------
    # UI構築
    # -------------------------
    def init_ui(self):
        layout = QVBoxLayout()

        # Mode選択
        mode_layout = QHBoxLayout()
        self.mode_radio_discharge = QRadioButton("Discharge Mode")
        self.mode_radio_test = QRadioButton("Test Mode")
        self.mode_radio_discharge.setChecked(True)
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_radio_discharge)
        mode_layout.addWidget(self.mode_radio_test)
        layout.addLayout(mode_layout)

        # Port選択
        top_layout = QHBoxLayout()
        self.port_box = QComboBox()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_box.addItem(p.device)
        self.port_box.setCurrentText("/dev/ttyACM0")
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.connect_serial)
        self.connection_label = QLabel("Disconnected")
        top_layout.addWidget(QLabel("Port:"))
        top_layout.addWidget(self.port_box)
        top_layout.addWidget(connect_btn)
        top_layout.addWidget(self.connection_label)
        layout.addLayout(top_layout)

        # スイッチ状態
        self.switch_label = QLabel("Switch: --")
        layout.addWidget(self.switch_label)

        # バッテリーID & メモ
        id_layout = QHBoxLayout()
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("Battery ID (NCXXX)")
        self.memo_edit = QLineEdit()
        self.memo_edit.setPlaceholderText("Memo")
        self.anonymous_checkbox = QCheckBox("Anonymous Mode")
        id_layout.addWidget(QLabel("Battery ID:"))
        id_layout.addWidget(self.id_edit)
        id_layout.addWidget(self.anonymous_checkbox)
        id_layout.addWidget(QLabel("Memo:"))
        id_layout.addWidget(self.memo_edit)
        layout.addLayout(id_layout)

        # バッテリー電圧
        self.voltage_label = QLabel("Battery[V]: --")
        layout.addWidget(self.voltage_label)
        self.battery_progress = QProgressBar()
        self.battery_progress.setRange(0, 100)
        layout.addWidget(self.battery_progress)

        # PWM
        self.pwm_label = QLabel(f"PWM: {self.pwm_value} (Output A: {self.pwm_value/255*5:.2f})")
        layout.addWidget(self.pwm_label)
        self.pwm_slider = QSlider(Qt.Horizontal)
        self.pwm_slider.setRange(0, 255)
        self.pwm_slider.setValue(self.pwm_value)
        self.pwm_slider.valueChanged.connect(self.send_pwm)
        layout.addWidget(self.pwm_slider)

        # 放電状態LED表示
        self.status_label = QLabel("Status: --")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Current
        self.current_label = QLabel("Current[A]: --")
        layout.addWidget(self.current_label)

        # 放電開始/停止
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("Start")
        start_btn.clicked.connect(self.start_discharge)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.stop_discharge)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        layout.addLayout(btn_layout)

        # 時間表示
        self.time_label = QLabel("Time: -- s")
        layout.addWidget(self.time_label)

        # 予測残り時間
        self.remain_label = QLabel("Remain: -- s")
        layout.addWidget(self.remain_label)

        # グラフ
        self.figure = Figure(figsize=(6,4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax2 = self.ax.twinx()
        self.ax.set_xlabel("Sample")
        self.ax.set_ylabel("Voltage/Current")
        self.ax2.set_ylabel("PWM")
        layout.addWidget(self.canvas)

        self.setLayout(layout)

        # 更新タイマー
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(200)

    # -------------------------
    # Serial接続
    # -------------------------
    def connect_serial(self):
        port = self.port_box.currentText()
        if self.serial_thread:
            self.serial_thread.stop()
        self.serial_thread = SerialWorker(port)
        self.serial_thread.data_received.connect(self.handle_serial)
        self.serial_thread.switch_state_received.connect(self.update_switch)
        self.serial_thread.connection_state.connect(self.update_connection_status)
        self.serial_thread.start()

    def update_connection_status(self, connected):
        self.connection_label.setText("Connected" if connected else "Disconnected")
        color = "green" if connected else "red"
        self.connection_label.setStyleSheet(f"color:{color}")

    # -------------------------
    # Serialデータ受信
    # -------------------------
    def handle_serial(self, data):
        self.voltage_log.append(data["voltage"])
        self.current_log.append(data["current"])
        self.pwm_log.append(data["pwm"])

        self.discharge_active = data["state"] == 1
        if self.discharge_active and self.start_time is None:
            self.start_time = time.time()

    # -------------------------
    # スイッチ状態更新
    # -------------------------
    def update_switch(self, state_on):
        self.switch_label.setText(f"Switch: {'ON' if state_on else 'OFF'}")

    # -------------------------
    # UI更新
    # -------------------------
    def update_ui(self):
        if self.voltage_log:
            voltage = self.voltage_log[-1]
            current = self.current_log[-1]
            pwm = self.pwm_log[-1]

            # バッテリーゲージ
            percent = int(min(max((voltage-0.9)/0.5*100,0),100))
            self.battery_progress.setValue(percent)

            # Voltage / Current 表示
            self.voltage_label.setText(f"Battery[V]: {voltage:.3f}")
            self.current_label.setText(f"Current[A]: {current:.2f}")
            output_a = pwm/255*5.0
            self.pwm_label.setText(f"PWM: {pwm} (Output A: {output_a:.2f})")

            # StatusLED表示
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
            self.status_label.setStyleSheet(f"background-color: {status_color}; color: white;")

            # 経過時間
            if self.start_time:
                elapsed = time.time() - self.start_time
                self.time_label.setText(f"Time: {elapsed:.1f} s")
            else:
                self.time_label.setText("Time: -- s")

            # 残り時間予測
            remain = self.predict_time()
            if remain:
                self.remain_label.setText(f"Remain: {remain:.0f} s")
            else:
                self.remain_label.setText("Remain: -- s")

            # グラフ更新
            self.ax.clear()
            self.ax2.clear()
            self.ax.plot(list(self.voltage_log), label="Voltage[V]", color="orange")
            self.ax.plot(list(self.current_log), label="Current[A]", color="blue")
            self.ax2.plot(list(self.pwm_log), label="PWM", color="green")
            self.ax.legend(loc="upper left")
            self.ax2.legend(loc="upper right")
            self.canvas.draw()

    # -------------------------
    # 残り時間予測
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
    # 放電制御コマンド
    # -------------------------
    def start_discharge(self):
        self.send_cmd("START")
        self.start_time = time.time()

    def stop_discharge(self):
        self.send_cmd("STOP")

    def send_pwm(self):
        val = self.pwm_slider.value()
        self.pwm_value = val
        self.send_cmd(f"PWM{val}")

    def send_cmd(self,cmd):
        if self.serial_thread and self.serial_thread.ser and self.serial_thread.ser.is_open:
            try:
                self.serial_thread.ser.write((cmd+"\n").encode())
            except:
                pass

# -------------------------
# Main Window
# -------------------------
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        tabs = QTabWidget()
        tabs.addTab(Mode1_Discharge(),"Mode1 Discharge")
        self.setCentralWidget(tabs)
        self.setWindowTitle("Battery Analyzer")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())
