import sys
import serial
import threading
import csv
import os
from datetime import datetime
from collections import deque
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QTextEdit,
    QListWidget, QListWidgetItem
)
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

PORT = "/dev/ttyACM0"
BAUD = 115200


# =========================
# CSV読み込み
# =========================
def load_csv(path):
    t, v, i = [], [], []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            t.append(float(row[0]))
            v.append(float(row[1]))
            i.append(float(row[2]))
    return t, v, i


# =========================
# スコア計算
# =========================
def calc_score(v, i):
    avg_v = np.mean(v)
    end_v = v[-1]
    stability = np.std(i)

    score = avg_v * 50 + end_v * 30 - stability * 20
    return score


# =========================
# Logger（前と同じ）
# =========================
class Logger:
    def __init__(self):
        self.file = None
        self.writer = None

    def start(self):
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"battery_log_{now}.csv"

        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        path = os.path.join(log_dir, filename)

        self.file = open(path, "w", newline="")
        self.writer = csv.writer(self.file)

        self.writer.writerow([
            "time", "voltage", "current", "power",
            "pwm", "running", "stop_reason"
        ])

        print(f"[CSV START] {path}")

    def write(self, row):
        if self.writer:
            self.writer.writerow(row)
            self.file.flush()

    def stop(self):
        if self.file:
            self.file.close()
            print("[CSV STOP]")


# =========================
# メイン
# =========================
class BatteryAnalyzer(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Battery Analyzer Rev10")

        self.ser = None
        self.logger = Logger()
        self.running = False

        self.time_data = []
        self.voltage_data = []
        self.current_data = []

        self.log_buffer = deque(maxlen=200)

        self.init_ui()

        self.thread = threading.Thread(target=self.read_loop)
        self.thread.daemon = True
        self.thread.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)

    # =========================
    def init_ui(self):
        layout = QVBoxLayout()

        header = QHBoxLayout()

        self.conn_label = QLabel("🔴 DISCONNECTED")
        self.state_label = QLabel("IDLE")

        self.btn_connect = QPushButton("CONNECT")
        self.btn_start = QPushButton("START")
        self.btn_stop = QPushButton("STOP")

        header.addWidget(self.conn_label)
        header.addWidget(self.state_label)
        header.addWidget(self.btn_connect)
        header.addWidget(self.btn_start)
        header.addWidget(self.btn_stop)

        layout.addLayout(header)

        self.tabs = QTabWidget()

        self.tab1 = QWidget()
        self.tab5 = QWidget()

        self.tabs.addTab(self.tab1, "測定")
        self.tabs.addTab(self.tab5, "比較")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

        self.init_mode1()
        self.init_mode5()

        self.btn_connect.clicked.connect(self.connect_serial)
        self.btn_start.clicked.connect(self.send_start)
        self.btn_stop.clicked.connect(self.send_stop)

    # =========================
    def init_mode1(self):
        layout = QVBoxLayout()

        self.plot = pg.PlotWidget()
        layout.addWidget(self.plot)

        self.curve = self.plot.plot(pen='b')

        self.log_text = QTextEdit()
        layout.addWidget(self.log_text)

        self.tab1.setLayout(layout)

    # =========================
    def init_mode5(self):
        layout = QHBoxLayout()

        # 左：ファイルリスト
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)

        # 右：グラフ＋ランキング
        right = QVBoxLayout()

        self.compare_plot = pg.PlotWidget()
        right.addWidget(self.compare_plot)

        self.rank_label = QLabel("ランキング")
        right.addWidget(self.rank_label)

        layout.addLayout(right)

        self.tab5.setLayout(layout)

        self.load_file_list()
        self.file_list.itemSelectionChanged.connect(self.update_comparison)

    # =========================
    def load_file_list(self):
        self.file_list.clear()

        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

        if not os.path.exists(log_dir):
            return

        for f in os.listdir(log_dir):
            item = QListWidgetItem(f)
            self.file_list.addItem(item)

    # =========================
    def update_comparison(self):
        self.compare_plot.clear()

        items = self.file_list.selectedItems()

        scores = []

        for item in items:
            path = os.path.join("logs", item.text())
            t, v, i = load_csv(path)

            self.compare_plot.plot(t, v)

            score = calc_score(v, i)
            scores.append((item.text(), score))

        scores.sort(key=lambda x: x[1], reverse=True)

        text = "ランキング\n"
        for i, (name, s) in enumerate(scores):
            text += f"{i+1}: {name} → {s:.2f}\n"

        self.rank_label.setText(text)

    # =========================
    def connect_serial(self):
        try:
            self.ser = serial.Serial(PORT, BAUD, timeout=1)
            self.conn_label.setText("🟢 CONNECTED")
        except:
            self.conn_label.setText("🔴 ERROR")

    def send_start(self):
        if self.ser:
            self.ser.write(b"START\n")

    def send_stop(self):
        if self.ser:
            self.ser.write(b"STOP\n")

    # =========================
    def read_loop(self):
        while True:
            if not self.ser:
                continue

            try:
                line = self.ser.readline().decode().strip()

                if not line:
                    continue

                if line.startswith("ACK,START"):
                    self.running = True
                    self.logger.start()

                elif line.startswith("ACK,STOP"):
                    self.running = False
                    self.logger.stop()

                elif line.startswith("DATA"):
                    parts = line.split(",")

                    t = float(parts[1])
                    v = float(parts[2])
                    i = float(parts[3])

                    self.time_data.append(t)
                    self.voltage_data.append(v)
                    self.current_data.append(i)

                    self.curve.setData(self.time_data, self.voltage_data)

                    self.log_buffer.append(line)

                    self.logger.write(parts[1:8])

            except:
                pass

    # =========================
    def update_ui(self):
        self.log_text.setText("\n".join(self.log_buffer))


# =========================
# 実行
# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BatteryAnalyzer()
    window.resize(1000, 700)
    window.show()
    sys.exit(app.exec_())

