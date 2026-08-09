import sys
import os
import csv
import time
from collections import deque

import serial
import serial.tools.list_ports

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

    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        except serial.SerialException:
            return

        while self.running:
            line = ser.readline().decode(errors="ignore").strip()
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
        ser.close()

    def stop(self):
        self.running = False

# -------------------------
# Mode1 放電＋評価テストUI
# -------------------------
class Mode1Widget(QWidget):
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
        self.anonymous_mode = False

        self.init_ui()

        # Serialスレッド
        self.serial_thread = None

    def init_ui(self):
        layout = QVBoxLayout()

        # -----------------
        # Mode選択
        # -----------------
        mode_layout = QHBoxLayout()
        self.mode_radio_discharge = QRadioButton("Discharge Mode")
        self.mode_radio_test = QRadioButton("Test Mode")
        self.mode_radio_discharge.setChecked(True)
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_radio_discharge)
        mode_layout.addWidget(self.mode_radio_test)
        layout.addLayout(mode_layout)

        # -----------------
        # Port選択
        # -----------------
        port_layout = QHBoxLayout()
        self.port_box = QComboBox()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_box.addItem(p.device)
        self.port_box.setCurrentText("/dev/ttyACM0")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)
        self.port_status_label = QLabel("Status: Not connected")
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.port_box)
        port_layout.addWidget(self.connect_btn)
        port_layout.addWidget(self.port_status_label)
        layout.addLayout(port_layout)

        # -----------------
        # スイッチ状態
        # -----------------
        self.switch_label = QLabel("Switch: --")
        layout.addWidget(self.switch_label)

        # -----------------
        # バッテリー選択 & メモ
        # -----------------
        id_layout = QHBoxLayout()
        self.id_combo = QComboBox()
        self.refresh_battery_list()
        self.id_combo.currentIndexChanged.connect(self.battery_selected)
        self.new_id_btn = QPushButton("New Battery")
        self.new_id_btn.clicked.connect(self.add_new_battery)
        self.memo_edit = QLineEdit()
        self.memo_edit.setPlaceholderText("Memo")
        self.anonymous_check = QCheckBox("Anonymous Mode")
        self.anonymous_check.stateChanged.connect(self.set_anonymous)
        id_layout.addWidget(QLabel("Battery ID:"))
        id_layout.addWidget(self.id_combo)
        id_layout.addWidget(self.new_id_btn)
        id_layout.addWidget(QLabel("Memo:"))
        id_layout.addWidget(self.memo_edit)
        id_layout.addWidget(self.anonymous_check)
        layout.addLayout(id_layout)

        # -----------------
        # バッテリー電圧・ゲージ
        # -----------------
        self.voltage_label = QLabel("Battery[V]: --")
        layout.addWidget(self.voltage_label)
        self.battery_progress = QProgressBar()
        self.battery_progress.setRange(0, 100)
        layout.addWidget(self.battery_progress)

        # -----------------
        # PWM
        # -----------------
        self.pwm_label = QLabel("PWM: 128 (Output A: 2.50)")
        layout.addWidget(self.pwm_label)
        self.pwm_slider = QSlider(Qt.Horizontal)
        self.pwm_slider.setRange(0, 255)
        self.pwm_slider.setValue(128)
        self.pwm_slider.valueChanged.connect(self.send_pwm)
        layout.addWidget(self.pwm_slider)

        # -----------------
        # 放電状態
        # -----------------
        self.status_label = QLabel("Status: --")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # -----------------
        # Current
        # -----------------
        self.current_label = QLabel("Current[A]: --")
        layout.addWidget(self.current_label)

        # -----------------
        # 放電開始 / 停止
        # -----------------
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("Start")
        start_btn.clicked.connect(self.start_discharge)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.stop_discharge)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        layout.addLayout(btn_layout)

        # -----------------
        # 時間・残り時間
        # -----------------
        self.time_label = QLabel("Time: -- s")
        self.remain_label = QLabel("Remain: -- s")
        layout.addWidget(self.time_label)
        layout.addWidget(self.remain_label)

        # -----------------
        # グラフ
        # -----------------
        self.figure = Figure(figsize=(6,4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax2 = self.ax.twinx()
        self.ax.set_xlabel("Sample")
        self.ax.set_ylabel("Voltage/Current")
        self.ax2.set_ylabel("PWM")
        layout.addWidget(self.canvas)

        self.setLayout(layout)

        # -----------------
        # タイマー更新
        # -----------------
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(200)

    # -------------------------
    # バッテリー管理
    # -------------------------
    def refresh_battery_list(self):
        self.id_combo.clear()
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        files = [f.replace(".csv","") for f in os.listdir(self.log_dir) if f.endswith(".csv")]
        self.id_combo.addItems(files)

    def battery_selected(self):
        self.battery_id = self.id_combo.currentText()
        self.load_battery_log()

    def add_new_battery(self):
        text, ok = QInputDialog.getText(self,"New Battery","Enter Battery ID (NCXXX):")
        if ok and text:
            self.battery_id = text
            self.memo = ""
            self.memo_edit.setText("")
            self.anonymous_check.setChecked(False)
            self.voltage_log.clear()
            self.current_log.clear()
            self.pwm_log.clear()
            self.refresh_battery_list()
            self.id_combo.setCurrentText(self.battery_id)

    def set_anonymous(self,state):
        self.anonymous_mode = state==Qt.Checked

    def load_battery_log(self):
        self.voltage_log.clear()
        self.current_log.clear()
        self.pwm_log.clear()
        path = os.path.join(self.log_dir,self.battery_id+".csv")
        if os.path.exists(path):
            with open(path,"r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.voltage_log.append(float(row["voltage"]))
                    self.current_log.append(float(row["current"]))
                    self.pwm_log.append(int(row["pwm"]))

    def save_battery_log(self):
        if not self.battery_id:
            return
        path = os.path.join(self.log_dir,self.battery_id+".csv")
        with open(path,"w",newline="") as f:
            fieldnames = ["voltage","current","pwm"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for v,c,p in zip(self.voltage_log,self.current_log,self.pwm_log):
                writer.writerow({"voltage":v,"current":c,"pwm":p})

    # -------------------------
    # Serial接続
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
        self.port_status_label.setText(f"Status: Connected ({port})")

    def handle_serial(self, data):
        self.voltage_log.append(data["voltage"])
        self.current_log.append(data["current"])
        self.pwm_log.append(data["pwm"])
        self.discharge_active = data["state"]==1
        if self.discharge_active and self.start_time is None:
            self.start_time = time.time()

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

            percent = int(min(max((voltage-0.9)/0.5*100,0),100))
            self.battery_progress.setValue(percent)

            self.voltage_label.setText(f"Battery[V]: {voltage:.3f}")
            self.current_label.setText(f"Current[A]: {current:.2f}")
            output_a = pwm/255*5.0
            self.pwm_label.setText(f"PWM: {pwm} (Output A: {output_a:.2f})")

            if voltage <= 0.9:
                self.status_label.setText("Status: Finish")
                color = "green"
            elif voltage <= 0.95:
                self.status_label.setText("Status: Warning")
                color = "blue"
            elif self.discharge_active:
                self.status_label.setText("Status: Discharging")
                color = "orange"
            else:
                self.status_label.setText("Status: Idle")
                color = "gray"
            self.status_label.setStyleSheet(f"background-color:{color}; color:white;")

            if self.start_time:
                elapsed = time.time() - self.start_time
                self.time_label.setText(f"Time: {elapsed:.1f} s")
            else:
                self.time_label.setText("Time: -- s")

            remain = self.predict_time()
            if remain:
                self.remain_label.setText(f"Remain: {remain:.0f} s")
            else:
                self.remain_label.setText("Remain: -- s")

            # グラフ更新
            self.ax.clear()
            self.ax2.clear()
            self.ax.plot(list(self.voltage_log),label="Voltage[V]",color="orange")
            self.ax.plot(list(self.current_log),label="Current[A]",color="blue")
            self.ax2.plot(list(self.pwm_log),label="PWM",color="green")
            self.ax.legend(loc="upper left")
            self.ax2.legend(loc="upper right")
            self.canvas.draw()

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
    # 放電制御
    # -------------------------
    def start_discharge(self):
        self.send_cmd("START")
        self.start_time = time.time()

    def stop_discharge(self):
        self.send_cmd("STOP")
        self.save_battery_log()

    def send_pwm(self):
        val = self.pwm_slider.value()
        self.send_cmd(f"PWM{val}")

    def send_cmd(self,cmd):
        if self.serial_thread:
            try:
                ser = serial.Serial(self.serial_thread.port,115200,timeout=0.1)
                ser.write((cmd+"\n").encode())
                ser.close()
            except:
                pass

# -------------------------
# Mode2 評価UI
# -------------------------
class Mode2Widget(QWidget):
    def __init__(self, mode1_widget:Mode1Widget):
        super().__init__()
        self.mode1 = mode1_widget
        layout = QVBoxLayout()
        self.eval_label = QLabel("Evaluation Mode (Single Battery)")
        layout.addWidget(self.eval_label)

        self.result_label = QLabel("Score: -- | Balance: -- | Vurst: --")
        layout.addWidget(self.result_label)

        self.race_label = QLabel("Race suitability:")
        layout.addWidget(self.race_label)

        self.curve_label = QLabel("Growth curve: Opened → Peak → Peak Out")
        layout.addWidget(self.curve_label)

        self.setLayout(layout)

        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_eval)
        self.ui_timer.start(500)

    def update_eval(self):
        # Mode1のログを参照して簡易評価
        if self.mode1.voltage_log:
            v = list(self.mode1.voltage_log)
            current = list(self.mode1.current_log)
            # 簡易スコア計算例
            score = max(v)-min(v)
            balance = 100-(max(current)-min(current))*20
            vurst = (v[-1]-v[0])*50
            self.result_label.setText(f"Score: {score:.2f} | Balance: {balance:.1f} | Vurst: {vurst:.2f}")

# -------------------------
# Main Window
# -------------------------
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        tabs = QTabWidget()
        self.mode1 = Mode1Widget()
        self.mode2 = Mode2Widget(self.mode1)
        tabs.addTab(self.mode1,"Mode1 Discharge/Test")
        tabs.addTab(self.mode2,"Mode2 Evaluation")
        self.setCentralWidget(tabs)
        self.setWindowTitle("Battery Analyzer")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())
