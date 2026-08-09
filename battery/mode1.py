import sys
import serial
import serial.tools.list_ports
import time
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# -------------------------
# Serialワーカー（非同期読み取り）
# -------------------------
class SerialWorker(QThread):
    data_received = pyqtSignal(dict)

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        except:
            return

        while self.running:
            line = ser.readline().decode(errors="ignore").strip()
            if line.startswith("DATA"):
                parts = line.split(",")
                if len(parts) == 6:
                    try:
                        _, t, v, i, pwm, state = parts
                        data = {
                            "time": float(t),
                            "voltage": float(v),
                            "current": float(i),
                            "pwm": int(pwm),
                            "state": int(state)
                        }
                        self.data_received.emit(data)
                    except:
                        pass
        ser.close()

    def stop(self):
        self.running = False

# -------------------------
# Mode1 UI
# -------------------------
class Mode1Discharge(QWidget):
    def __init__(self):
        super().__init__()

        self.serial_worker = None
        self.voltage_log = []

        self.init_ui()

    # -------------------------
    # UI初期化
    # -------------------------
    def init_ui(self):
        layout = QVBoxLayout()

        # シリアル接続
        self.port_box = QComboBox()
        for p in serial.tools.list_ports.comports():
            self.port_box.addItem(p.device)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)
        port_layout = QHBoxLayout()
        port_layout.addWidget(self.port_box)
        port_layout.addWidget(self.connect_btn)
        layout.addLayout(port_layout)

        # 表示
        self.voltage_label = QLabel("Voltage: -- V")
        self.current_label = QLabel("Current: -- A")
        self.pwm_label = QLabel("PWM: --")
        self.time_label = QLabel("Time: 0 s")
        self.remain_label = QLabel("Remain: -- s")
        self.state_label = QLabel("State: Idle")
        layout.addWidget(self.voltage_label)
        layout.addWidget(self.current_label)
        layout.addWidget(self.pwm_label)
        layout.addWidget(self.time_label)
        layout.addWidget(self.remain_label)
        layout.addWidget(self.state_label)

        # PWMスライダー
        self.pwm_slider = QSlider(Qt.Horizontal)
        self.pwm_slider.setRange(0,255)
        self.pwm_slider.setValue(128)
        self.pwm_slider.valueChanged.connect(self.send_pwm)
        self.pwm_value_label = QLabel("PWM Output: 2.5 A")  # 目安表示
        layout.addWidget(QLabel("PWM"))
        layout.addWidget(self.pwm_slider)
        layout.addWidget(self.pwm_value_label)

        # 放電操作ボタン
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("START")
        self.stop_btn = QPushButton("STOP")
        self.start_btn.clicked.connect(self.start_discharge)
        self.stop_btn.clicked.connect(self.stop_discharge)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    # -------------------------
    # シリアル接続
    # -------------------------
    def connect_serial(self):
        port = self.port_box.currentText()
        if self.serial_worker:
            self.serial_worker.stop()
        self.serial_worker = SerialWorker(port)
        self.serial_worker.data_received.connect(self.update_display)
        self.serial_worker.start()

    # -------------------------
    # 放電操作
    # -------------------------
    def start_discharge(self):
        if self.serial_worker:
            self.serial_worker.running = True
            self.send_cmd("START")
            self.voltage_log = []

    def stop_discharge(self):
        if self.serial_worker:
            self.send_cmd("STOP")

    # -------------------------
    # PWM操作
    # -------------------------
    def send_pwm(self):
        val = self.pwm_slider.value()
        self.send_cmd(f"PWM{val}")
        # PWM目安電流表示（目安 5A × PWM/255）
        approx_current = 5.0 * val / 255.0
        self.pwm_value_label.setText(f"PWM Output: {approx_current:.2f} A")

    # -------------------------
    # シリアル送信
    # -------------------------
    def send_cmd(self, cmd):
        if self.serial_worker and self.serial_worker.isRunning():
            try:
                self.serial_worker.port_obj = serial.Serial(self.serial_worker.port, 115200, timeout=0.1)
                self.serial_worker.port_obj.write((cmd+"\n").encode())
            except:
                pass

    # -------------------------
    # 表示更新
    # -------------------------
    def update_display(self, data):
        t = data["time"]
        v = data["voltage"]
        i = data["current"]
        pwm = data["pwm"]
        state = data["state"]

        self.voltage_label.setText(f"Voltage: {v:.3f} V")
        self.current_label.setText(f"Current: {i:.2f} A")
        self.pwm_label.setText(f"PWM: {pwm}")
        self.time_label.setText(f"Time: {t:.1f} s")
        self.state_label.setText(f"State: {'Idle' if state==0 else 'Discharging' if state==1 else 'Finished'}")

        # ログ更新
        self.voltage_log.append(v)
        if len(self.voltage_log) > 20:
            self.voltage_log.pop(0)

        # 放電残り時間目安
        remain = self.predict_remain()
        if remain:
            self.remain_label.setText(f"Remain: {remain:.0f} s")
        else:
            self.remain_label.setText("Remain: -- s")

    # -------------------------
    # 残り時間予測（目安）
    # -------------------------
    def predict_remain(self):
        if len(self.voltage_log) < 5:
            return None
        dv = self.voltage_log[-1] - self.voltage_log[0]
        dt = len(self.voltage_log) * 0.2  # 200ms間隔
        if dv >= 0 or dt==0:
            return None
        slope = dv/dt
        remain = (0.9 - self.voltage_log[-1]) / slope
        return max(remain,0)

# -------------------------
# メインウィンドウ
# -------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Analyzer Mode1")
        self.tabs = QTabWidget()
        self.tabs.addTab(Mode1Discharge(), "Mode1 Discharge")
        self.setCentralWidget(self.tabs)

# -------------------------
# 実行
# -------------------------
if __name__=="__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
