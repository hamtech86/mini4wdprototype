import sys
from PyQt5.QtWidgets import QApplication
from score_ui import BatteryScoreUI
from serial_worker import SerialWorker

class MainApp(BatteryScoreUI):
    def __init__(self):
        super().__init__()

        # --- シリアル開始 ---
        self.worker = SerialWorker(port="/dev/ttyUSB0")
        self.worker.data_received.connect(self.update_from_serial)
        self.worker.start()

        # 内部データ保持
        self.data = {}

    def update_from_serial(self, new_data):
        self.data.update(new_data)

        if "Vbat" in new_data:
            self.batteryLabel.setText(f"Battery Voltage: {new_data['Vbat']:.2f} V")

        if "Current" in new_data:
            self.scoreLabel.setText(f"Current: {new_data['Current']:.2f} A")

    def closeEvent(self, event):
        self.worker.stop()
        self.worker.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainApp()
    win.show()
    sys.exit(app.exec_())import serial
from PyQt5.QtCore import QThread, pyqtSignal

class SerialWorker(QThread):
    data_received = pyqtSignal(dict)

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True

    def run(self):
        ser = serial.Serial(self.port, self.baudrate, timeout=1)

        while self.running:
            line = ser.readline().decode(errors="ignore").strip()
            if "=" in line:
                key, value = line.split("=")
                try:
                    data = {key: float(value)}
                    self.data_received.emit(data)
                except ValueError:
                    pass

        ser.close()

    def stop(self):
        self.running = False
