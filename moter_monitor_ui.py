import sys
import serial
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout
)
from PyQt5.QtCore import QTimer

PORT = "/dev/ttyACM0"
BAUD = 115200

class MotorMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini4WD Motor Measurement Mode")

        self.ser = serial.Serial(PORT, BAUD, timeout=1)

        self.start_btn = QPushButton("測定開始（3V）")
        self.stop_btn  = QPushButton("測定停止")

        self.label = QLabel("Waiting...")

        layout = QVBoxLayout()
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_measure)
        self.stop_btn.clicked.connect(self.stop_measure)

        self.timer = QTimer()
        self.timer.timeout.connect(self.read_serial)

    def start_measure(self):
        self.ser.write(b"START\n")
        self.timer.start(500)

    def stop_measure(self):
        self.timer.stop()
        self.ser.write(b"STOP\n")

    def read_serial(self):
        line = self.ser.readline().decode(errors="ignore").strip()
        if line:
            self.label.setText(line)

    def closeEvent(self, event):
        self.ser.write(b"STOP\n")
        self.ser.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MotorMonitor()
    w.show()
    sys.exit(app.exec_())

