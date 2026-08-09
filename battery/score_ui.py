import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QProgressBar, QComboBox
)
from PyQt5.QtCore import Qt

class BatteryScoreUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Analyzer")

        # --- 上部情報 ---
        self.batteryLabel = QLabel("Battery: NC-01")
        self.rankLabel = QLabel("RANK: A ⚡")
        self.scoreLabel = QLabel("SCORE: 82")

        self.modeBox = QComboBox()
        self.modeBox.addItems(["Sprint", "Balance", "Stayer"])

        # --- スコアバー ---
        self.burstBar = self.make_bar("Burst", 88)
        self.sustainBar = self.make_bar("Sustain", 62)
        self.stabilityBar = self.make_bar("Stability", 74)
        self.healthBar = self.make_bar("Health", 80)

        # --- ガイド ---
        self.guideLabel = QLabel("✔ レース投入OK\n✔ 追い充電可")
        self.guideLabel.setStyleSheet("color: green")

        # --- ボタン ---
        self.dischargeBtn = QPushButton("放電開始")
        self.measureBtn = QPushButton("測定")

        # --- レイアウト ---
        main = QVBoxLayout()
        main.addWidget(self.batteryLabel)
        main.addWidget(self.modeBox)
        main.addWidget(self.rankLabel)
        main.addWidget(self.scoreLabel)

        main.addLayout(self.burstBar)
        main.addLayout(self.sustainBar)
        main.addLayout(self.stabilityBar)
        main.addLayout(self.healthBar)

        main.addWidget(self.guideLabel)

        btns = QHBoxLayout()
        btns.addWidget(self.dischargeBtn)
        btns.addWidget(self.measureBtn)
        main.addLayout(btns)

        self.setLayout(main)

    def make_bar(self, name, value):
        label = QLabel(f"{name}")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(value)
        bar.setTextVisible(True)

        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(bar)
        return layout

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = BatteryScoreUI()
    ui.show()
    sys.exit(app.exec_())
