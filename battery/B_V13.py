import sys
import os
import json
import time
import random

from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer
import pyqtgraph as pg
import serial


LOG_DIR="battery_logs"
DB_FILE="battery_db.json"


class BatteryLab(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Mini4WD Battery Lab V3")

        self.serial=None
        self.connected=False

        self.dummy_mode=False
        self.anonymous_mode=False

        self.recording=False

        self.current_log=[]

        self.time_data=[]
        self.voltage_data=[]

        self.load_db()

        self.init_ui()

        self.timer=QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(100)

    # -----------------------------
    # DB
    # -----------------------------

    def load_db(self):

        if not os.path.exists(DB_FILE):

            self.db={"batteries":[]}

            self.save_db()

        else:

            with open(DB_FILE) as f:
                self.db=json.load(f)

    def save_db(self):

        with open(DB_FILE,"w") as f:
            json.dump(self.db,f,indent=2)

    def add_battery(self):

        bid=f"A{len(self.db['batteries'])+1:02}"

        self.db["batteries"].append({
            "id":bid,
            "memo":"",
            "tests":[]
        })

        self.save_db()
        self.refresh_battery_list()

    # -----------------------------
    # UI
    # -----------------------------

    def init_ui(self):

        main=QWidget()
        layout=QVBoxLayout()

        layout.addWidget(self.create_header())

        self.tabs=QTabWidget()

        self.mode1=self.create_mode1()
        self.mode2=self.create_mode2()
        self.mode3=self.create_mode3()
        self.mode5=self.create_mode5()

        self.tabs.addTab(self.mode1,"Mode1 Discharge")
        self.tabs.addTab(self.mode2,"Mode2 Evaluation")
        self.tabs.addTab(self.mode3,"Mode3 Pair")
        self.tabs.addTab(QWidget(),"Mode4 Training")
        self.tabs.addTab(self.mode5,"Mode5 Batteries")

        layout.addWidget(self.tabs)

        main.setLayout(layout)

        self.setCentralWidget(main)

    # -----------------------------
    # Header (V1仕様)
    # -----------------------------

    def create_header(self):

        widget=QWidget()
        layout=QHBoxLayout()

        # 左：デバイス状態
        device_layout=QVBoxLayout()

        self.serial_label=QLabel("Serial : Disconnected")
        self.switch_label=QLabel("Switch : OFF")
        self.discharge_label=QLabel("Discharge : IDLE")

        device_layout.addWidget(self.serial_label)
        device_layout.addWidget(self.switch_label)
        device_layout.addWidget(self.discharge_label)

        layout.addLayout(device_layout)

        layout.addStretch()

        # 右：ログ管理

        log_layout=QHBoxLayout()

        self.log_select=QComboBox()
        self.load_btn=QPushButton("Load")

        self.new_btn=QPushButton("+ Battery")
        self.new_btn.clicked.connect(self.add_battery)

        self.anonymous_cb=QCheckBox("Anonymous")
        self.dummy_cb=QCheckBox("Dummy")

        self.dummy_cb.stateChanged.connect(self.toggle_dummy)
        self.anonymous_cb.stateChanged.connect(self.toggle_anonymous)

        log_layout.addWidget(self.log_select)
        log_layout.addWidget(self.load_btn)
        log_layout.addWidget(self.new_btn)
        log_layout.addWidget(self.anonymous_cb)
        log_layout.addWidget(self.dummy_cb)

        layout.addLayout(log_layout)

        widget.setLayout(layout)

        return widget

    # -----------------------------
    # Mode1
    # -----------------------------

    def create_mode1(self):

        w=QWidget()
        l=QVBoxLayout()

        info=QHBoxLayout()

        self.voltage_label=QLabel("Voltage:0")
        self.current_label=QLabel("Current:0")
        self.power_label=QLabel("Power:0")

        info.addWidget(self.voltage_label)
        info.addWidget(self.current_label)
        info.addWidget(self.power_label)

        l.addLayout(info)

        ctrl=QHBoxLayout()

        self.start_btn=QPushButton("START")
        self.stop_btn=QPushButton("STOP")

        self.start_btn.clicked.connect(self.start_record)
        self.stop_btn.clicked.connect(self.stop_record)

        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.stop_btn)

        l.addLayout(ctrl)

        self.graph=pg.PlotWidget()
        self.curve=self.graph.plot()

        l.addWidget(self.graph)

        w.setLayout(l)

        return w

    # -----------------------------
    # Mode2
    # -----------------------------

    def create_mode2(self):

        w=QWidget()
        l=QVBoxLayout()

        self.speed_label=QLabel("Speed:")
        self.stamina_label=QLabel("Stamina:")
        self.health_label=QLabel("Health:")
        self.type_label=QLabel("Type:")

        l.addWidget(self.speed_label)
        l.addWidget(self.stamina_label)
        l.addWidget(self.health_label)
        l.addWidget(self.type_label)

        w.setLayout(l)

        return w

    # -----------------------------
    # Mode3 ペア評価
    # -----------------------------

    def create_mode3(self):

        w=QWidget()
        l=QVBoxLayout()

        self.pair_list=QListWidget()

        btn=QPushButton("Generate Pair Ranking")
        btn.clicked.connect(self.generate_pairs)

        l.addWidget(btn)
        l.addWidget(self.pair_list)

        w.setLayout(l)

        return w

    def generate_pairs(self):

        self.pair_list.clear()

        bats=self.db["batteries"]

        scores=[]

        for i in range(len(bats)):

            for j in range(i+1,len(bats)):

                s=random.uniform(0,100)

                scores.append((s,bats[i]["id"],bats[j]["id"]))

        scores.sort(reverse=True)

        for s,a,b in scores[:10]:

            self.pair_list.addItem(f"{a} + {b} : {s:.1f}")

    # -----------------------------
    # Mode5
    # -----------------------------

    def create_mode5(self):

        w=QWidget()
        l=QVBoxLayout()

        self.battery_list=QListWidget()

        l.addWidget(self.battery_list)

        self.refresh_battery_list()

        w.setLayout(l)

        return w

    def refresh_battery_list(self):

        self.battery_list.clear()

        for b in self.db["batteries"]:

            self.battery_list.addItem(b["id"])

    # -----------------------------
    # Serial
    # -----------------------------

    def toggle_dummy(self):

        self.dummy_mode=self.dummy_cb.isChecked()

    def toggle_anonymous(self):

        self.anonymous_mode=self.anonymous_cb.isChecked()

    def read_serial(self):

        if not self.connected:
            return None

        try:
            line=self.serial.readline().decode().strip()
            return line
        except:
            return None

    # -----------------------------
    # Dummy
    # -----------------------------

    def dummy_data(self):

        t=len(self.time_data)

        v=1.4-t*0.001+random.uniform(-0.005,0.005)
        i=2+random.uniform(-0.1,0.1)

        p=v*i

        return {
            "time":t,
            "voltage":v,
            "current":i,
            "power":p,
            "pwm":120,
            "state":"DISCHARGE"
        }

    # -----------------------------
    # Loop
    # -----------------------------

    def update_loop(self):

        if self.dummy_mode:

            data=self.dummy_data()

        else:

            return

        self.update_ui(data)

    def update_ui(self,data):

        v=data["voltage"]
        i=data["current"]
        p=data["power"]

        self.voltage_label.setText(f"Voltage:{v:.3f}")
        self.current_label.setText(f"Current:{i:.3f}")
        self.power_label.setText(f"Power:{p:.3f}")

        self.time_data.append(data["time"])
        self.voltage_data.append(v)

        self.curve.setData(self.time_data,self.voltage_data)

        if self.recording:
            self.current_log.append(data)

    # -----------------------------
    # Record
    # -----------------------------

    def start_record(self):

        self.recording=True

        self.current_log=[]
        self.time_data=[]
        self.voltage_data=[]

    def stop_record(self):

        self.recording=False

        if len(self.current_log)>0:

            self.evaluate_battery()

    def evaluate_battery(self):

        power=[x["power"] for x in self.current_log]

        if len(power)<5:
            return

        speed=sum(power[:5])/5

        energy=sum(power)

        stamina=energy/len(power)

        health=max(0,100-stamina)

        if speed>stamina*1.2:
            t="SPRINTER"
        elif stamina>speed*1.2:
            t="STAYER"
        else:
            t="CLASSIC"

        self.speed_label.setText(f"Speed:{speed:.2f}")
        self.stamina_label.setText(f"Stamina:{stamina:.2f}")
        self.health_label.setText(f"Health:{health:.1f}")
        self.type_label.setText(f"Type:{t}")


if __name__=="__main__":

    app=QApplication(sys.argv)

    win=BatteryLab()

    win.show()

    sys.exit(app.exec())

