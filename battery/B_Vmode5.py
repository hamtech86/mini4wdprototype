import sys
import os
import csv
from datetime import datetime
from PyQt5.QtWidgets import *
import pyqtgraph as pg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "logs", "raw")
SUMMARY_FILE = os.path.join(BASE_DIR, "logs", "summary", "summary.csv")
MASTER_FILE = os.path.join(BASE_DIR, "logs", "master", "battery_master.csv")

os.makedirs(os.path.dirname(MASTER_FILE), exist_ok=True)


# =========================
# マスタ読み込み
# =========================
def load_master():
    data = {}
    if not os.path.exists(MASTER_FILE):
        return data

    with open(MASTER_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row["battery_id"]] = row
    return data


# =========================
# マスタ保存
# =========================
def save_master(data):
    with open(MASTER_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["battery_id","label","group","notes","created_at"])

        for k, v in data.items():
            writer.writerow([
                k,
                v.get("label",""),
                v.get("group",""),
                v.get("notes",""),
                v.get("created_at","")
            ])


# =========================
# UI
# =========================
class App(QWidget):

    def __init__(self):
        super().__init__()

        self.master = load_master()

        self.setWindowTitle("Battery Analyzer Rev17")

        layout = QHBoxLayout()

        # ------------------------
        # 左：summary
        # ------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["日時","ID","Score"])

        layout.addWidget(self.table, 2)

        # ------------------------
        # 右
        # ------------------------
        right = QVBoxLayout()

        # 詳細
        self.detail = QLabel("詳細")
        right.addWidget(self.detail)

        # グラフ
        self.plot = pg.PlotWidget()
        right.addWidget(self.plot)

        # ------------------------
        # マスタ編集
        # ------------------------
        form = QFormLayout()

        self.id_edit = QLineEdit()
        self.label_edit = QLineEdit()
        self.group_edit = QLineEdit()
        self.notes_edit = QTextEdit()

        form.addRow("ID", self.id_edit)
        form.addRow("ラベル", self.label_edit)
        form.addRow("グループ", self.group_edit)
        form.addRow("メモ", self.notes_edit)

        right.addLayout(form)

        self.btn_save = QPushButton("保存")
        right.addWidget(self.btn_save)

        layout.addLayout(right, 3)

        self.setLayout(layout)

        # イベント
        self.table.itemSelectionChanged.connect(self.select_row)
        self.btn_save.clicked.connect(self.save_master_data)

        self.load_summary()

    # =========================
    def load_summary(self):
        if not os.path.exists(SUMMARY_FILE):
            return

        with open(SUMMARY_FILE) as f:
            reader = csv.DictReader(f)

            for row_idx, row in enumerate(reader):
                self.table.insertRow(row_idx)

                self.table.setItem(row_idx, 0, QTableWidgetItem(row["datetime"]))
                self.table.setItem(row_idx, 1, QTableWidgetItem(row["battery_id"]))
                self.table.setItem(row_idx, 2, QTableWidgetItem(row["score"]))

    # =========================
    def select_row(self):
        row = self.table.currentRow()
        if row < 0:
            return

        battery_id = self.table.item(row, 1).text()

        self.id_edit.setText(battery_id)

        data = self.master.get(battery_id, {})

        self.label_edit.setText(data.get("label",""))
        self.group_edit.setText(data.get("group",""))
        self.notes_edit.setText(data.get("notes",""))

    # =========================
    def save_master_data(self):
        bid = self.id_edit.text()

        if not bid:
            return

        self.master[bid] = {
            "label": self.label_edit.text(),
            "group": self.group_edit.text(),
            "notes": self.notes_edit.toPlainText(),
            "created_at": self.master.get(bid, {}).get(
                "created_at",
                datetime.now().strftime("%Y-%m-%d")
            )
        }

        save_master(self.master)

        QMessageBox.information(self, "保存", "保存しました")

# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = App()
    w.resize(1200, 700)
    w.show()
    sys.exit(app.exec_())

