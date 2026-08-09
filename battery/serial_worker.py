import serial
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
