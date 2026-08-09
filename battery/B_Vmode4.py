import sys, os, csv, datetime
from PyQt5 import QtWidgets, QtCore, QtGui

# ------------------------
# CSVパス定義
# ------------------------
RAW_LOG_DIR = "logs/raw/"
SUMMARY_LOG = "logs/summary/summary.csv"
BATTERY_MASTER = "logs/master/battery_master.csv"
PAIRING_LOG = "logs/pairing/pairing.csv"

# ------------------------
# バッテリー情報クラス
# ------------------------
class Battery:
    def __init__(self, data):
        self.battery_id = data.get('battery_id','')
        self.group = data.get('group','')
        self.brand = data.get('brand','')
        self.capacity_nominal = float(data.get('capacity_nominal',0))
        self.notes = data.get('notes','')
        self.created_at = data.get('created_at','')
        self.speed = float(data.get('speed',0))
        self.power = float(data.get('power',0))
        self.stamina = float(data.get('stamina',0))
        self.stability = float(data.get('stability',0))
        self.growth = float(data.get('growth',0))
        self.avg_voltage = float(data.get('avg_voltage',0))
        self.avg_current = float(data.get('avg_current',0))
        self.capacity = float(data.get('capacity_mAh',0))
        self.internal_resistance = float(data.get('internal_resistance',0))
        self.rank = data.get('rank','')
        self.type = data.get('type','')
        self.stop_reason = data.get('stop_reason','')

# ------------------------
# Mode4: ペアリングタブ
# ------------------------
class Mode4Tab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.batteries = []
        self.load_summary()
        self.init_ui()

    def load_summary(self):
        if not os.path.exists(SUMMARY_LOG):
            return
        with open(SUMMARY_LOG,'r',encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.batteries.append(Battery(row))

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()

        # ボタン
        btn_layout = QtWidgets.QHBoxLayout()
        self.auto_pair_btn = QtWidgets.QPushButton("自動ペアリング")
        self.save_pair_btn = QtWidgets.QPushButton("ペア保存")
        btn_layout.addWidget(self.auto_pair_btn)
        btn_layout.addWidget(self.save_pair_btn)
        layout.addLayout(btn_layout)

        # ペア候補テーブル
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['Battery 1','Battery 2','ΔCapacity','ΔR','Score','距離適性'])
        layout.addWidget(self.table)

        # ステータス比較
        self.status_layout = QtWidgets.QGridLayout()
        self.status_labels = {}
        for i,label in enumerate(['Speed','Power','Stamina','Stability','Growth']):
            l1 = QtWidgets.QLabel(f"{label} L:")
            l2 = QtWidgets.QLabel(f"{label} R:")
            l_sync = QtWidgets.QLabel("0%")
            self.status_labels[label] = (l1,l2,l_sync)
            self.status_layout.addWidget(l1, i,0)
            self.status_layout.addWidget(l2, i,1)
            self.status_layout.addWidget(l_sync, i,2)
        layout.addLayout(self.status_layout)

        self.setLayout(layout)

        # イベント
        self.auto_pair_btn.clicked.connect(self.generate_pairs)
        self.save_pair_btn.clicked.connect(self.save_selected_pair)
        self.table.cellClicked.connect(self.update_status_view)

    def generate_pairs(self):
        self.table.setRowCount(0)
        pairs = []
        for i,b1 in enumerate(self.batteries):
            for j,b2 in enumerate(self.batteries):
                if i>=j: continue
                delta_c = abs(b1.capacity - b2.capacity)
                delta_r = abs(b1.internal_resistance - b2.internal_resistance)
                if delta_r>0.03 or delta_c>150:
                    continue
                score = max(0,100 - (delta_r*1000 + delta_c*0.5))
                dist_score = self.distance_type_score(b1,b2)
                pairs.append((b1,b2,delta_c,delta_r,score,dist_score))
        pairs.sort(key=lambda x: x[4], reverse=True)
        self.pairs = pairs
        for row_idx,p in enumerate(pairs):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx,0,QtWidgets.QTableWidgetItem(p[0].battery_id))
            self.table.setItem(row_idx,1,QtWidgets.QTableWidgetItem(p[1].battery_id))
            self.table.setItem(row_idx,2,QtWidgets.QTableWidgetItem(f"{p[2]:.1f}"))
            self.table.setItem(row_idx,3,QtWidgets.QTableWidgetItem(f"{p[3]:.3f}"))
            self.table.setItem(row_idx,4,QtWidgets.QTableWidgetItem(f"{p[4]:.1f}"))
            self.table.setItem(row_idx,5,QtWidgets.QTableWidgetItem(p[5]))

    def distance_type_score(self,b1,b2):
        avg_speed = (b1.speed + b2.speed)/2
        avg_stamina = (b1.stamina + b2.stamina)/2
        if avg_speed>70 and avg_stamina<50:
            return "短距離向き"
        elif avg_speed<50 and avg_stamina>70:
            return "長距離向き"
        else:
            return "バランス型"

    def update_status_view(self,row,col):
        if not hasattr(self,'pairs'): return
        if row>=len(self.pairs): return
        b1,b2,_,_,_,_ = self.pairs[row]
        for key,(l1,l2,l_sync) in self.status_labels.items():
            val1 = getattr(b1,key.lower())
            val2 = getattr(b2,key.lower())
            l1.setText(f"{key} L: {val1:.1f}")
            l2.setText(f"{key} R: {val2:.1f}")
            sync = 100 - abs(val1-val2)
            l_sync.setText(f"{sync:.0f}%")
            if sync>80:
                l_sync.setStyleSheet("color:green")
            elif sync>60:
                l_sync.setStyleSheet("color:orange")
            else:
                l_sync.setStyleSheet("color:red")

    def save_selected_pair(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        if not os.path.exists(os.path.dirname(PAIRING_LOG)):
            os.makedirs(os.path.dirname(PAIRING_LOG))
        with open(PAIRING_LOG,'a',newline='',encoding='utf-8') as f:
            writer = csv.writer(f)
            for r in rows:
                row_idx = r.row()
                b1,b2,delta_c,delta_r,score,dist = self.pairs[row_idx]
                writer.writerow([
                    b1.battery_id,
                    b2.battery_id,
                    f"{delta_c:.1f}",
                    f"{delta_r:.3f}",
                    f"{score:.1f}",
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ])
        QtWidgets.QMessageBox.information(self,"保存","ペア保存完了")

# ------------------------
# 単体テスト用
# ------------------------
if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    tab_widget = QtWidgets.QTabWidget()
    # 今後Mode1~5タブを統合
    tab_widget.addTab(Mode4Tab(),"Mode4: ペアリング")
    tab_widget.resize(1000,700)
    tab_widget.show()
    sys.exit(app.exec_())

