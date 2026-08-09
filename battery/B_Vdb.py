import sys
import os 
import csv 
import datetime
from PyQt5 import QtWidgets, QtCore, QtGui 
import pyqtgraph as pg
import serial

==================== 設定 ====================

LOG_DIR = "logs" RAW_DIR = os.path.join(LOG_DIR, "raw") SUMMARY_FILE = os.path.join(LOG_DIR, "summary", "summary.csv") MASTER_FILE = os.path.join(LOG_DIR, "master", "battery_master.csv") ARDUINO_PORT = "/dev/ttyACM0" BAUDRATE = 115200 UPDATE_INTERVAL = 100

==================== 初期化 ====================

def ensure_dirs(): os.makedirs(RAW_DIR, exist_ok=True) os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True) os.makedirs(os.path.dirname(MASTER_FILE), exist_ok=True)

ensure_dirs()

==================== シリアル ====================

try: ser = serial.Serial(ARDUINO_PORT, BAUDRATE, timeout=0.1) except: ser = None

==================== データ ====================

data_buffer = []

==================== MASTER 更新 ====================

def update_master(battery_id): now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') rows = [] found = False

if os.path.exists(MASTER_FILE):
    with open(MASTER_FILE, 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)

header = ["battery_id","group","brand","capacity_nominal","notes","created_at","last_tested_at"]

if not rows:
    rows.append(header)

for i in range(1, len(rows)):
    if rows[i][0] == battery_id:
        rows[i][6] = now
        found = True

if not found:
    rows.append([battery_id, "", "", "", "", now, now])

with open(MASTER_FILE, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

==================== RAW保存 ====================

def save_raw(battery_id, mode): filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{battery_id}{mode}.csv" path = os.path.join(RAW_DIR, filename)

with open(path, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["time","voltage","current","power","pwm","running","stop_reason"])
    writer.writerows(data_buffer)

return path

==================== SUMMARY保存 ====================

def save_summary(battery_id, mode): if not data_buffer: return

voltages = [d[1] for d in data_buffer]
currents = [d[2] for d in data_buffer]

avg_v = sum(voltages)/len(voltages)
avg_i = sum(currents)/len(currents)

capacity = sum([currents[i]*(data_buffer[i][0] - data_buffer[i-1][0] if i>0 else 0) for i in range(len(data_buffer))]) * 1000 / 3600

voltage_drop = voltages[0] - min(voltages)

import statistics
stability = 1 - (statistics.stdev(currents)/avg_i if len(currents)>1 else 0)

score = int((avg_v*20 + avg_i*20 + stability*60))

rank = "S" if score>90 else "A" if score>75 else "B" if score>60 else "C" if score>40 else "D"

header = ["datetime","battery_id","mode","avg_voltage","avg_current","capacity_mAh","voltage_drop","stability","score","rank"]
exists = os.path.exists(SUMMARY_FILE)

with open(SUMMARY_FILE, 'a', newline='') as f:
    writer = csv.writer(f)
    if not exists:
        writer.writerow(header)
    writer.writerow([
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        battery_id, mode, avg_v, avg_i, capacity, voltage_drop, stability, score, rank
    ])

==================== UI ====================

class App(QtWidgets.QMainWindow): def init(self): super().init() self.setWindowTitle("Battery Analyzer Rev10.6") self.resize(1000,700)

self.anonymous = False
    self.mode = "QUICK"

    central = QtWidgets.QWidget()
    self.setCentralWidget(central)
    layout = QtWidgets.QVBoxLayout(central)

    # ===== ヘッダー =====
    header = QtWidgets.QHBoxLayout()

    self.id_input = QtWidgets.QLineEdit()
    self.id_input.setPlaceholderText("Battery ID")

    self.mode_select = QtWidgets.QComboBox()
    self.mode_select.addItems(["QUICK","FULL"])

    self.anon_check = QtWidgets.QCheckBox("Anonymous")

    self.start_btn = QtWidgets.QPushButton("START")
    self.stop_btn = QtWidgets.QPushButton("STOP")

    header.addWidget(self.id_input)
    header.addWidget(self.mode_select)
    header.addWidget(self.anon_check)
    header.addWidget(self.start_btn)
    header.addWidget(self.stop_btn)

    layout.addLayout(header)

    # ===== 表示 =====
    self.label = QtWidgets.QLabel("---")
    layout.addWidget(self.label)

    self.plot = pg.PlotWidget()
    self.curve_v = self.plot.plot(pen='b')
    self.curve_i = self.plot.plot(pen='r')
    layout.addWidget(self.plot)

    # ===== イベント =====
    self.start_btn.clicked.connect(self.start)
    self.stop_btn.clicked.connect(self.stop)

    self.timer = QtCore.QTimer()
    self.timer.timeout.connect(self.update_loop)
    self.timer.start(UPDATE_INTERVAL)

    self.x=[]
    self.v=[]
    self.i=[]

def start(self):
    global data_buffer
    data_buffer.clear()
    self.mode = self.mode_select.currentText()
    self.anonymous = self.anon_check.isChecked()

    if ser:
        ser.write(f"START,{self.mode}\n".encode())

def stop(self):
    if ser:
        ser.write(b"STOP\n")

    battery_id = self.id_input.text().strip()

    if not self.anonymous and battery_id:
        save_raw(battery_id, self.mode)
        save_summary(battery_id, self.mode)
        update_master(battery_id)

def update_loop(self):
    if ser and ser.in_waiting:
        try:
            line = ser.readline().decode().strip()
            if line.startswith("DATA"):
                parts = line.split(",")
                d = list(map(float, parts[1:8]))
                data_buffer.append(d)

                t,v,i,p,_,_,_ = d

                self.label.setText(f"{t:.2f}s {v:.3f}V {i:.3f}A")

                self.x.append(t)
                self.v.append(v)
                self.i.append(i)

                self.curve_v.setData(self.x,self.v)
                self.curve_i.setData(self.x,self.i)
        except:
            pass

==================== 実行 ====================

if name == "main": app = QtWidgets.QApplication(sys.argv) w = App() w.show() sys.exit(app.exec_())

