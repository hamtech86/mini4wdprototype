import sys, os, csv, time, glob
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTabWidget, QComboBox, QTextEdit, QProgressBar, QFileDialog
)
from PyQt5.QtCore import QTimer, Qt
import pyqtgraph as pg
import serial

# === 設定 ===
LOG_DIR = "logs"
RAW_DIR = os.path.join(LOG_DIR, "raw")
SUMMARY_FILE = os.path.join(LOG_DIR, "summary", "summary.csv")
MASTER_FILE = os.path.join(LOG_DIR, "master", "battery_master.csv")
VOLTAGE_CUTOFF = 0.9
TIMEOUT = 3600  # 秒
UPDATE_INTERVAL = 100  # ms

# === Arduino接続 ===
SERIAL_PORT = "/dev/ttyACM0"
BAUD = 115200

try:
    ser = serial.Serial(SERIAL_PORT, BAUD)
except:
    ser = None

# === ユーティリティ ===
def format_time(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02}:{m:02}:{sec:05.2f}"

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

ensure_dir(RAW_DIR)
ensure_dir(os.path.join(LOG_DIR, "summary"))
ensure_dir(os.path.join(LOG_DIR, "master"))
ensure_dir(os.path.join(LOG_DIR, "pairing"))

# === Main App ===
class BatteryAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Analyzer Rev10")
        self.resize(1200, 800)

        # === 状態 ===
        self.running = False
        self.start_time = 0.0
        self.elapsed_offset = 0.0
        self.elapsed = 0.0
        self.stop_reason = 0  # 0:なし,1:電圧,2:timeout,3:ユーザー
        self.voltage = 0.0
        self.current = 0.0
        self.power = 0.0
        self.pwm = 0
        self.battery_id = ""
        self.device_list = ["Device1", "Device2"]  # 仮
        self.selected_device = self.device_list[0]

        # === ヘッダー ===
        self.device_combo = QComboBox()
        self.device_combo.addItems(self.device_list)
        self.device_combo.currentIndexChanged.connect(self.change_device)

        self.conn_label = QLabel("未接続")
        self.status_label = QLabel("IDLE")
        self.elapsed_label = QLabel("00:00:00.00")
        self.voltage_bar = QProgressBar()
        self.voltage_bar.setRange(0, 2000)  # 0-2V例
        self.start_btn = QPushButton("START")
        self.stop_btn = QPushButton("STOP")
        self.start_btn.clicked.connect(self.start_discharge)
        self.stop_btn.clicked.connect(self.stop_discharge)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Device:"))
        header_layout.addWidget(self.device_combo)
        header_layout.addWidget(QLabel("Connection:"))
        header_layout.addWidget(self.conn_label)
        header_layout.addWidget(QLabel("Status:"))
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(QLabel("Elapsed:"))
        header_layout.addWidget(self.elapsed_label)
        header_layout.addWidget(QLabel("Voltage:"))
        header_layout.addWidget(self.voltage_bar)
        header_layout.addWidget(self.start_btn)
        header_layout.addWidget(self.stop_btn)

        # === Tabs ===
        self.tabs = QTabWidget()
        self.mode1_tab = QWidget()
        self.mode2_tab = QWidget()
        self.mode3_tab = QWidget()
        self.mode4_tab = QWidget()
        self.mode5_tab = QWidget()
        self.tabs.addTab(self.mode1_tab, "Mode1:測定")
        self.tabs.addTab(self.mode2_tab, "Mode2:評価")
        self.tabs.addTab(self.mode3_tab, "Mode3:育成")
        self.tabs.addTab(self.mode4_tab, "Mode4:ペアリング")
        self.tabs.addTab(self.mode5_tab, "Mode5:ログ管理")

        main_layout = QVBoxLayout()
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

        # === Mode1（計器・グラフ） ===
        self.init_mode1()
        self.init_mode2()
        self.init_mode3()
        self.init_mode4()
        self.init_mode5()

        # === タイマー ===
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(UPDATE_INTERVAL)

    def change_device(self, idx):
        self.selected_device = self.device_list[idx]

    # === START / STOP ===
    def start_discharge(self):
        if ser:
            ser.write(b"START\n")
        self.running = True
        self.start_time = time.time()
        self.status_label.setText("RUNNING")
        self.stop_reason = 0

    def stop_discharge(self):
        if ser:
            ser.write(b"STOP\n")
        self.running = False
        self.elapsed_offset += time.time() - self.start_time
        self.status_label.setText("STOPPED")
        self.stop_reason = 3  # ユーザー停止

    # === Mode1 初期化 ===
    def init_mode1(self):
        layout = QVBoxLayout()
        self.mode1_tab.setLayout(layout)

        self.voltage_label = QLabel("Voltage: 0.000 V")
        self.current_label = QLabel("Current: 0.000 A")
        self.power_label = QLabel("Power: 0.000 W")
        self.time_label = QLabel("Elapsed: 0.00 s")
        layout.addWidget(self.voltage_label)
        layout.addWidget(self.current_label)
        layout.addWidget(self.power_label)
        layout.addWidget(self.time_label)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.addLegend()
        self.plot_voltage = self.plot_widget.plot([], [], pen=pg.mkPen('b', width=2), name="Voltage")
        self.plot_current = self.plot_widget.plot([], [], pen=pg.mkPen('r', width=2), name="Current", secondary=True)
        layout.addWidget(self.plot_widget)

        self.time_data = []
        self.voltage_data = []
        self.current_data = []

    # === Mode2 初期化 ===
    def init_mode2(self):
        layout = QVBoxLayout()
        self.mode2_tab.setLayout(layout)
        self.avg_voltage_label = QLabel("Avg Voltage: -")
        self.avg_current_label = QLabel("Avg Current: -")
        self.capacity_label = QLabel("Capacity: -")
        self.total_score_label = QLabel("総合評価: -")
        layout.addWidget(self.avg_voltage_label)
        layout.addWidget(self.avg_current_label)
        layout.addWidget(self.capacity_label)
        layout.addWidget(self.total_score_label)

    # === Mode3 初期化 ===
    def init_mode3(self):
        layout = QVBoxLayout()
        self.mode3_tab.setLayout(layout)
        self.st_status = QTextEdit()
        self.st_status.setReadOnly(True)
        layout.addWidget(self.st_status)

    # === Mode4 初期化 ===
    def init_mode4(self):
        layout = QVBoxLayout()
        self.mode4_tab.setLayout(layout)
        self.pair_status = QTextEdit()
        self.pair_status.setReadOnly(True)
        layout.addWidget(self.pair_status)

    # === Mode5 初期化 ===
    def init_mode5(self):
        layout = QVBoxLayout()
        self.mode5_tab.setLayout(layout)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_reload_btn = QPushButton("Reload Logs")
        self.log_reload_btn.clicked.connect(self.reload_logs)
        layout.addWidget(self.log_text)
        layout.addWidget(self.log_reload_btn)

    # === ログ再読み込み ===
    def reload_logs(self):
        self.log_text.clear()
        for f in glob.glob(os.path.join(RAW_DIR, "*.csv")):
            self.log_text.append(f)

    # === UI更新 ===
    def update_ui(self):
        if self.running:
            self.elapsed = time.time() - self.start_time + self.elapsed_offset
            if self.elapsed > TIMEOUT:
                self.running = False
                self.stop_reason = 2
                self.status_label.setText("FINISHED")
        self.elapsed_label.setText(format_time(self.elapsed))

        # 仮データ（Arduinoからの読み取りはここで追加）
        self.voltage = 1.5
        self.current = 2.0
        self.power = self.voltage * self.current
        self.voltage_label.setText(f"Voltage: {self.voltage:.3f} V")
        self.current_label.setText(f"Current: {self.current:.3f} A")
        self.power_label.setText(f"Power: {self.power:.3f} W")
        self.voltage_bar.setValue(int(self.voltage*1000))  # 0-2V表示例

        # グラフ更新
        self.time_data.append(self.elapsed)
        self.voltage_data.append(self.voltage)
        self.current_data.append(self.current)
        self.plot_voltage.setData(self.time_data, self.voltage_data)
        self.plot_current.setData(self.time_data, self.current_data)

# === 実行 ===
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = BatteryAnalyzer()
    win.show()
    sys.exit(app.exec_())

