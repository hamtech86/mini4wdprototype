# Filename: BatteryAnalyzer_v1_3.py
import sys, os, csv, serial, time
from collections import deque
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import serial.tools.list_ports

SOFTWARE_VERSION = "1.3"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# ------------------------- Serial Worker -------------------------
class SerialWorker(QThread):
    data_received = pyqtSignal(dict)
    switch_state_received = pyqtSignal(bool)
    connect_state_changed = pyqtSignal(bool)

    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.cmd_queue = deque()
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True
            self.connect_state_changed.emit(True)
        except serial.SerialException:
            self.running = False
            self.connect_state_changed.emit(False)
            return

        while self.running:
            while self.cmd_queue:
                cmd = self.cmd_queue.popleft()
                try: self.ser.write((cmd+"\n").encode())
                except: pass
            line = self.ser.readline().decode(errors="ignore").strip()
            
            print("受信:",line)
            
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
                except: pass
        if self.ser: self.ser.close()
        self.connect_state_changed.emit(False)

    def stop(self):
        self.running = False

    def send_cmd(self, cmd):
        self.cmd_queue.append(cmd)

# ------------------------- Mode1: 放電 -------------------------
class Mode1Widget(QWidget):
    def __init__(self, serial_worker):
        super().__init__()
        self.serial_thread = serial_worker
        self.voltage_log = deque(maxlen=500)
        self.current_log = deque(maxlen=500)
        self.pwm_log = deque(maxlen=500)
        self.start_time = None
        self.discharge_active = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Mode1: Discharge"))

        # Voltage / Current / PWM labels with green text on black
        self.voltage_label = QLabel("Battery[V]: --")
        self.voltage_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.voltage_label)

        self.current_label = QLabel("Current[A]: --")
        self.current_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.current_label)

        self.pwm_label = QLabel("PWM: --")
        self.pwm_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.pwm_label)

        # Battery progress
        self.battery_progress = QProgressBar()
        self.battery_progress.setRange(0,100)
        layout.addWidget(self.battery_progress)

        # Status LED
        self.status_label = QLabel("Status: --")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_discharge)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_discharge)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # Time / Remain
        self.time_label = QLabel("Time: -- s")
        self.remain_label = QLabel("Remain: -- s")
        layout.addWidget(self.time_label)
        layout.addWidget(self.remain_label)

        # Graph
        self.figure = Figure(figsize=(6,4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax2 = self.ax.twinx()
        self.ax.set_xlabel("Sample")
        self.ax.set_ylabel("Voltage / Current")
        self.ax2.set_ylabel("PWM")
        layout.addWidget(self.canvas)

        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(200)

        self.setLayout(layout)

    def handle_serial(self, data):
        self.voltage_log.append(data["voltage"])
        self.current_log.append(data["current"])
        self.pwm_log.append(data["pwm"])
        self.discharge_active = data["state"]==1
        if self.discharge_active and self.start_time is None:
            self.start_time = time.time()

    def update_ui(self):
        if not self.voltage_log: return
        voltage = self.voltage_log[-1]
        current = self.current_log[-1]
        pwm = self.pwm_log[-1]

        self.voltage_label.setText(f"Battery[V]: {voltage:.3f}")
        self.current_label.setText(f"Current[A]: {current:.2f}")
        output_a = pwm/255*5.0
        self.pwm_label.setText(f"PWM: {pwm} (Output A: {output_a:.2f})")

        percent = int(min(max((voltage-0.9)/0.5*100,0),100))
        self.battery_progress.setValue(percent)

        # Status LED
        if voltage<=0.9: text,color="Finish","green"
        elif voltage<=0.95: text,color="Warning","blue"
        elif self.discharge_active: text,color="Discharging","orange"
        else: text,color="Idle","gray"
        self.status_label.setText(f"Status: {text}")
        self.status_label.setStyleSheet(f"background-color:{color}; color:white;")

        elapsed = time.time()-self.start_time if self.start_time else None
        self.time_label.setText(f"Time: {elapsed:.1f} s" if elapsed else "Time: -- s")
        remain = self.predict_time()
        self.remain_label.setText(f"Remain: {remain:.0f} s" if remain else "Remain: -- s")

        # Graph
        self.ax.clear(); self.ax2.clear()
        self.ax.plot(list(self.voltage_log),label="Voltage[V]",color="orange")
        self.ax.plot(list(self.current_log),label="Current[A]",color="blue")
        self.ax2.plot(list(self.pwm_log),label="PWM",color="green")
        self.ax.legend(loc="upper left"); self.ax2.legend(loc="upper right")
        self.canvas.draw()

    def predict_time(self):
        if len(self.voltage_log)<10: return None
        dv = self.voltage_log[-1]-self.voltage_log[0]; dt=len(self.voltage_log)*0.2
        if dv>=0: return None
        slope = dv/dt
        return abs((0.9-self.voltage_log[-1])/slope)

    def start_discharge(self):
        if self.serial_thread: self.serial_thread.send_cmd("START"); self.start_time=time.time()

    def stop_discharge(self):
        if self.serial_thread: self.serial_thread.send_cmd("STOP")

# ------------------------- Mode2: 評価 -------------------------
class Mode2Widget(QWidget):
    def __init__(self, serial_worker):
        super().__init__()
        self.serial_thread = serial_worker
        self.voltage_log = deque(maxlen=500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Mode2: Evaluation"))

        self.score_label = QLabel("Score - Output: -- / Duration: -- / Balance: --")
        self.score_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.score_label)

        self.race_label = QLabel("Race Aptitude: Sprint / Classic / Stayer: -- / -- / --")
        self.race_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.race_label)

        self.figure = Figure(figsize=(6,4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Voltage[V]")
        layout.addWidget(self.canvas)

        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(200)

        self.setLayout(layout)

    def handle_serial(self,data):
        self.voltage_log.append(data["voltage"])

    def update_ui(self):
        if not self.voltage_log: return
        output_score = int(max(self.voltage_log)*100/5)
        duration_score = int(min(len(self.voltage_log)/900*100,100))
        balance_score = int(100 - abs(max(self.voltage_log)-min(self.voltage_log))*100/5)
        self.score_label.setText(f"Score - Output: {output_score} / Duration: {duration_score} / Balance: {balance_score}")
        self.ax.clear()
        self.ax.plot(list(self.voltage_log),color="orange")
        self.ax.set_title("Growth Curve: Open → Peak → Decline")
        self.canvas.draw()

# ------------------------- Main Window -------------------------
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.serial_worker = SerialWorker()
        self.serial_worker.start()

        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connect)
        self.conn_label = QLabel("Disconnected")
        self.conn_label.setStyleSheet("color:white; background-color:red;")
        self.battery_combo = QComboBox()
        self.new_btn = QPushButton("Add Battery")
        self.new_btn.clicked.connect(self.add_battery)
        self.anonymous_check = QCheckBox("Anonymous")
        self.memo_edit = QLineEdit()
        self.memo_edit.setPlaceholderText("Memo")

        header_layout.addWidget(self.connect_btn)
        header_layout.addWidget(self.conn_label)
        header_layout.addWidget(QLabel("Battery:")); header_layout.addWidget(self.battery_combo)
        header_layout.addWidget(self.new_btn)
        header_layout.addWidget(self.anonymous_check)
        header_layout.addWidget(QLabel("Memo:")); header_layout.addWidget(self.memo_edit)
        header_widget.setLayout(header_layout)

        # Tabs
        self.tabs = QTabWidget()
        self.mode1_tab = Mode1Widget(self.serial_worker)
        self.mode2_tab = Mode2Widget(self.serial_worker)
        self.tabs.addTab(self.mode1_tab,"Mode1 Discharge")
        self.tabs.addTab(self.mode2_tab,"Mode2 Evaluation")

        # Layout
        central_layout = QVBoxLayout()
        central_layout.addWidget(header_widget)
        central_layout.addWidget(self.tabs)
        central_widget = QWidget()
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)
        self.setWindowTitle(f"Battery Analyzer v{SOFTWARE_VERSION}")

        # Connect Serial signals
        self.serial_worker.data_received.connect(self.mode1_tab.handle_serial)
        self.serial_worker.data_received.connect(self.mode2_tab.handle_serial)

        self.serial_worker.connect_state_changed.connect(self.update_conn_label)

    def toggle_connect(self):
        # Restart SerialWorker
        if self.serial_worker.running:
            self.serial_worker.stop()
            self.serial_worker.wait()
        port = "/dev/ttyACM0"
        self.serial_worker = SerialWorker(port)
        self.serial_worker.start()
        self.serial_worker.data_received.connect(self.mode1_tab.handle_serial)
        self.serial_worker.data_received.connect(self.mode2_tab.handle_serial)
        self.serial_worker.connect_state_changed.connect(self.update_conn_label)

    def update_conn_label(self, connected):
        if connected:
            self.conn_label.setText("Connected")
            self.conn_label.setStyleSheet("color:white; background-color:green;")
        else:
            self.conn_label.setText("Disconnected")
            self.conn_label.setStyleSheet("color:white; background-color:red;")

    def add_battery(self):
        text, ok = QInputDialog.getText(self,"New Battery","Enter Battery ID (NCXXX):")
        if ok and text:
            path = os.path.join(LOG_DIR,f"{text}.csv")
            if not os.path.exists(path):
                with open(path,"w",newline="") as f:
                    writer = csv.writer(f); writer.writerow(["Time","Voltage","Current","PWM"])
            if self.battery_combo.findText(text)==-1:
                self.battery_combo.addItem(text)

if __name__=="__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec_())
