import sys
import random
import serial
import serial.tools.list_ports

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
import pyqtgraph as pg


APP_NAME = "Mini4WD Battery Analyzer V4-Core"


# ==========================
# Serial Thread
# ==========================

class SerialThread(QThread):

    line_received = pyqtSignal(str)

    def __init__(self, port=None, dummy=False):
        super().__init__()

        self.port = port
        self.dummy = dummy
        self.running = True

    def run(self):

        if self.dummy:
            self.run_dummy()
            return

        try:
            self.ser = serial.Serial(self.port,115200,timeout=1)
        except:
            return

        while self.running:

            try:
                line = self.ser.readline().decode().strip()

                if line:
                    self.line_received.emit(line)

            except:
                pass

        self.ser.close()

    def run_dummy(self):

        t=0
        v=1.45

        while self.running:

            t+=1
            v-=random.uniform(0.0005,0.002)

            c=5+random.uniform(-0.1,0.1)
            p=v*c
            pwm=random.randint(120,140)

            line=f"DATA,{t},{v:.3f},{c:.3f},{p:.3f},{pwm},1"

            self.line_received.emit(line)

            self.msleep(200)

    def send(self,cmd):

        if self.dummy:
            return

        if hasattr(self,"ser") and self.ser.is_open:
            self.ser.write((cmd+"\n").encode())

    def stop(self):

        self.running=False


# ==========================
# Status Label
# ==========================

class StatusLabel(QLabel):

    def set_status(self,text,color):

        self.setText(text)

        self.setStyleSheet(f"""
        QLabel {{
            background:{color};
            color:white;
            padding:4px;
            border-radius:4px;
        }}
        """)


# ==========================
# Mode1
# ==========================

class Mode1(QWidget):

    def __init__(self,main):

        super().__init__()

        self.main = main

        self.time=[]
        self.voltage=[]
        self.current=[]
        self.power=[]

        self.init_ui()

    def init_ui(self):

        layout=QVBoxLayout()
        self.setLayout(layout)

        # Voltage bar

        layout.addWidget(QLabel("Battery Voltage"))

        self.voltage_bar=QProgressBar()
        self.voltage_bar.setMaximum(150)

        layout.addWidget(self.voltage_bar)

        # Buttons

        btn_layout=QHBoxLayout()

        self.btn_start=QPushButton("START")
        self.btn_pause=QPushButton("PAUSE")
        self.btn_stop=QPushButton("STOP")

        self.btn_start.clicked.connect(lambda:self.main.send_cmd("START"))
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop.clicked.connect(lambda:self.main.send_cmd("STOP"))

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(self.btn_stop)

        layout.addLayout(btn_layout)

        # Status

        grid=QGridLayout()

        self.label_voltage=QLabel("Voltage: 0")
        self.label_current=QLabel("Current: 0")
        self.label_power=QLabel("Power: 0")
        self.label_pwm=QLabel("PWM: 0")
        self.label_time=QLabel("Elapsed: 0")

        grid.addWidget(self.label_voltage,0,0)
        grid.addWidget(self.label_current,0,1)
        grid.addWidget(self.label_power,0,2)
        grid.addWidget(self.label_pwm,1,0)
        grid.addWidget(self.label_time,1,1)

        layout.addLayout(grid)

        # Graph

        self.graph=pg.PlotWidget()
        layout.addWidget(self.graph)

        self.graph.addLegend()

        self.cv=self.graph.plot(pen='y',name="Voltage")
        self.cc=self.graph.plot(pen='r',name="Current")
        self.cp=self.graph.plot(pen='g',name="Power")

    def toggle_pause(self):

        if self.main.discharge_state=="RUN":

            self.main.send_cmd("PAUSE")

        else:

            self.main.send_cmd("RESUME")

    def update_data(self,t,v,c,p,pwm):

        self.voltage_bar.setValue(int(v*100))

        self.label_voltage.setText(f"Voltage: {v:.3f} V")
        self.label_current.setText(f"Current: {c:.3f} A")
        self.label_power.setText(f"Power: {p:.3f} W")
        self.label_pwm.setText(f"PWM: {pwm}")
        self.label_time.setText(f"Elapsed: {t}s")

        self.time.append(t)
        self.voltage.append(v)
        self.current.append(c)
        self.power.append(p)

        self.cv.setData(self.time,self.voltage)
        self.cc.setData(self.time,self.current)
        self.cp.setData(self.time,self.power)


# ==========================
# Main Window
# ==========================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(APP_NAME)

        self.serial=None
        self.discharge_state="IDLE"

        self.init_ui()

    def init_ui(self):

        central=QWidget()
        self.setCentralWidget(central)

        layout=QVBoxLayout()
        central.setLayout(layout)

        # HEADER

        header=QHBoxLayout()

        # Device Status

        status_box=QVBoxLayout()

        status_box.addWidget(QLabel("Device Status"))

        self.serial_status=StatusLabel()
        self.serial_status.set_status("Disconnected","gray")

        self.discharge_status=StatusLabel()
        self.discharge_status.set_status("IDLE","gray")

        status_box.addWidget(self.serial_status)
        status_box.addWidget(self.discharge_status)

        header.addLayout(status_box)

        # Log Manager

        log_box=QVBoxLayout()

        log_box.addWidget(QLabel("Log Manager"))

        self.battery_select=QComboBox()

        self.chk_dummy=QCheckBox("Dummy Mode")

        log_box.addWidget(self.battery_select)
        log_box.addWidget(self.chk_dummy)

        header.addLayout(log_box)

        layout.addLayout(header)

        # TAB

        self.tabs=QTabWidget()
        layout.addWidget(self.tabs)

        self.mode1=Mode1(self)

        self.tabs.addTab(self.mode1,"Mode1")

        for name in ["Mode2","Mode3","Mode4","Mode5"]:

            w=QLabel("Coming Soon")
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.tabs.addTab(w,name)

        # Connect

        self.connect_device()

    # =====================

    def connect_device(self):

        ports=list(serial.tools.list_ports.comports())

        dummy=self.chk_dummy.isChecked()

        if dummy:

            self.serial=SerialThread(dummy=True)

        elif ports:

            port=ports[0].device

            self.serial=SerialThread(port)

        else:

            return

        self.serial.line_received.connect(self.process_line)

        self.serial.start()

        self.serial_status.set_status("Connected","green")

    # =====================

    def send_cmd(self,cmd):

        if self.serial:

            self.serial.send(cmd)

    # =====================

    def process_line(self,line):

        if not line.startswith("DATA"):
            return

        p=line.split(",")

        if len(p)<7:
            return

        t=float(p[1])
        v=float(p[2])
        c=float(p[3])
        pw=float(p[4])
        pwm=int(p[5])
        state=int(p[6])

        if state==0:
            self.set_discharge("IDLE","gray")

        elif state==1:
            self.set_discharge("RUN","green")

        elif state==2:
            self.set_discharge("DONE","blue")

        elif state==3:
            self.set_discharge("PAUSE","orange")

        self.mode1.update_data(t,v,c,pw,pwm)

    def set_discharge(self,text,color):

        self.discharge_state=text

        self.discharge_status.set_status(text,color)


# ==========================

app=QApplication(sys.argv)

w=MainWindow()
w.resize(1100,750)
w.show()

sys.exit(app.exec())

