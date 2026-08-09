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
# Mode2 評価モード
# -------------------------
class Mode2_Evaluate(QWidget):
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

        # スコア
        self.scores = {"持続性":0, "バランス":0, "総合":0}

        self.init_ui()
        self.serial_thread = None

    # -------------------------
    # UI構築
    # -------------------------
    def init_ui(self):
        layout = QVBoxLayout()

        # モード選択
        mode_layout = QHBoxLayout()
        self.mode_radio_discharge = QRadioButton("Discharge Mode")
        self.mode_radio_test = QRadioButton("Test Mode")
        self.mode_radio_discharge.setChecked(True)
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_radio_discharge)
        mode_layout.addWidget(self.mode_radio_test)
        layout.addLayout(mode_layout)

        # ポート選択
        top_layout = QHBoxLayout()
        self.port_box = QComboBox()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_box.addItem(p.device)
        self.port_box.setCurrentText("/dev/ttyACM0")
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.connect_serial)
        top_layout.addWidget(QLabel("Port:"))
        top_layout.addWidget(self.port_box)
        top_layout.addWidget(connect_btn)
        layout.addLayout(top_layout)

        # スイッチ状態
        self.switch_label = QLabel("Switch: --")
        layout.addWidget(self.switch_label)

        # バッテリーID & メモ & アノニマス
        id_layout = QHBoxLayout()
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("Battery ID (NCXXX)")
        self.memo_edit = QLineEdit()
        self.memo_edit.setPlaceholderText("Memo")
        self.anon_checkbox = QCheckBox("Anonymous Mode")
        id_layout.addWidget(QLabel("Battery ID:"))
        id_layout.addWidget(self.id_edit)
        id_layout.addWidget(QLabel("Memo:"))
        id_layout.addWidget(self.memo_edit)
        id_layout.addWidget(self.anon_checkbox)
        layout.addLayout(id_layout)

        # バッテリー電圧
        self.voltage_label = QLabel("Battery[V]: --")
        layout.addWidget(self.voltage_label)
        self.battery_progress = QProgressBar()
        self.battery_progress.setRange(0, 100)
        layout.addWidget(self.battery_progress)

        # Current
        self.current_label = QLabel("Current[A]: --")
        layout.addWidget(self.current_label)

        # 放電状態LED表示
        self.status_label = QLabel("Status: --")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # スコア表示
        self.score_label = QLabel("Scores - 持続性: --  バランス: --  総合: --")
        layout.addWidget(self.score_label)

        # 推奨行動
        self.guide_label = QLabel("Guide: --")
        layout.addWidget(self.guide_label)

        # 放電開始/停止
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("Start Evaluation")
        start_btn.clicked.connect(self.start_discharge)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.stop_discharge)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        layout.addLayout(btn_layout)

        # 時間表示
        self.time_label = QLabel("Time: -- s")
        layout.addWidget(self.time_label)
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
            self.serial_thread.wait()
        self.serial_thread = SerialWorker(port)
        self.serial_thread.data_received.connect(self.handle_serial)
        self.serial_thread.switch_state_received.connect(self.update_switch)
        self.serial_thread.start()

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

        self.calculate_scores()

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

            # StatusLED表示
            if voltage <= 0.9:
                self.status_label.setText("Status: Finish")
                status_color = "green"
            elif voltage <= 0.95:
                self.status_label.setText("Status: Warning")
                status_color = "blue"
            elif self.discharge_active:
                self.status_label.setText("Status: Evaluating")
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

            # スコア表示
            self.score_label.setText(
                f"Scores - 持続性: {self.scores['持続性']:.1f}  "
                f"バランス: {self.scores['バランス']:.1f}  "
                f"総合: {self.scores['総合']:.1f}"
            )

            # 推奨行動
            guide_text = self.generate_guide()
            self.guide_label.setText(f"Guide: {guide_text}")

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
    # スコア計算
    # -------------------------
    def calculate_scores(self):
        # 持続性: 3分=180s 基準
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.scores["持続性"] = min(elapsed/180*100,100)
        else:
            self.scores["持続性"] = 0

        # バランス: 電圧変動の標準偏差
        if len(self.voltage_log) > 5:
            mean_v = sum(self.voltage_log)/len(self.voltage_log)
            std_v = (sum([(v-mean_v)**2 for v in self.voltage_log])/len(self.voltage_log))**0.5
            self.scores["バランス"] = max(0, 100 - std_v*100)
        else:
            self.scores["バランス"] = 0

        # 総合スコア
        self.scores["総合"] = (self.scores["持続性"]*0.5 + self.scores["バランス"]*0.5)

    # -------------------------
    # 推奨行動生成
    # -------------------------
    def generate_guide(self):
        guide = []
        if self.scores["持続性"] < 50:
            guide.append("充電/休止推奨")
        if self.scores["バランス"] < 50:
            guide.append("使用ペア注意")
        if self.scores["総合"] > 80:
            guide.append("レース投入可")
        if not guide:
            guide.append("様子見")
        return ", ".join(guide)

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

    def send_cmd(self):
        val = 128  # 評価モードではPWM固定
        self.send_cmd(f"PWM{val}")

    def send_cmd(self, cmd):
        if self.serial_thread:
            try:
                ser = serial.Serial(self.serial_thread.port, 115200, timeout=0.1)
                ser.write((cmd+"\n").encode())
                ser.close()
            except:
                pass

# -------------------------
# Main Window
# -------------------------
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        tabs = QTabWidget()
        tabs.addTab(Mode2_Evaluate(),"Mode2 Evaluate")
        self.setCentralWidget(tabs)
        self.setWindowTitle("Battery Evaluator Mode2")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())
