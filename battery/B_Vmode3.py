import sys
import os
import csv
import numpy as np
from PyQt5.QtWidgets import *

# =========================
# CSV読み込み
# =========================
def load_csv(path):
    t, v, i = [], [], []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            t.append(float(row[0]))
            v.append(float(row[1]))
            i.append(float(row[2]))
    return np.array(t), np.array(v), np.array(i)

# =========================
# ステータス
# =========================
def calc_stats(t, v, i):
    init_i = i[0]
    avg_i = np.mean(i)
    std_i = np.std(i)

    capacity = np.sum(i[1:] * np.diff(t)) / 3600 * 1000

    speed = min(init_i * 20, 100)
    power = min(avg_i * 20, 100)
    stamina = min(capacity / 5, 100)
    stability = max(100 - std_i * 50, 0)
    growth = min((v[-1] - v.min()) * 200, 100)

    return speed, power, stamina, stability, growth, capacity, std_i, avg_i

# =========================
# ランク
# =========================
def rank(x):
    if x >= 90: return "S"
    if x >= 75: return "A"
    if x >= 60: return "B"
    if x >= 40: return "C"
    return "D"

# =========================
# ライフステージ判定
# =========================
def life_stage(capacity, stability, avg_v):
    if capacity < 500:
        return "新規開封"
    elif capacity > 800 and stability > 70 and avg_v > 1.12:
        return "ピーク"
    else:
        return "引退"

# =========================
# 行動ガイド
# =========================
def action_guide(stage):
    if stage == "新規開封":
        return "ブレイクイン推奨（低電流→中電流）"
    if stage == "ピーク":
        return "実戦投入OK（コンディション維持）"
    return "引退推奨（練習用へ）"

# =========================
# メンテ
# =========================
def maintenance(stage):
    if stage == "新規開封":
        return "低電流慣らし（0.5〜1A）"
    if stage == "ピーク":
        return "軽い放電＋休止"
    return "保管 or 廃棄"

# =========================
# プリセット
# =========================
def preset(speed, stamina):
    ratio = speed - stamina

    if ratio > 40: return "① 超スプリント"
    if ratio > 20: return "② スプリント"
    if ratio > 10: return "③ ややスプリント"
    if ratio > -10: return "④ バランス"
    if ratio > -20: return "⑤ ややスタミナ"
    if ratio > -40: return "⑥ スタミナ"
    return "⑦ ステイヤー"

# =========================
# メイン
# =========================
class App(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Analyzer Rev13 Mode3")

        layout = QHBoxLayout()

        self.list = QListWidget()
        layout.addWidget(self.list)

        self.result = QLabel()
        self.result.setStyleSheet("font-size:14pt;")
        layout.addWidget(self.result)

        self.setLayout(layout)

        self.load_files()
        self.list.itemSelectionChanged.connect(self.analyze)

    def load_files(self):
        if not os.path.exists("logs"):
            return
        for f in os.listdir("logs"):
            self.list.addItem(f)

    def analyze(self):
        item = self.list.currentItem()
        if not item:
            return

        t, v, i = load_csv(os.path.join("logs", item.text()))

        speed, power, stamina, stability, growth, cap, std_i, avg_i = calc_stats(t, v, i)

        avg_v = np.mean(v)

        stage = life_stage(cap, stability, avg_v)
        action = action_guide(stage)
        maint = maintenance(stage)
        pre = preset(speed, stamina)

        text = f"""
【電池分析】

Speed     : {rank(speed)}
Power     : {rank(power)}
Stamina   : {rank(stamina)}
Stability : {rank(stability)}
Growth    : {rank(growth)}

容量: {cap:.1f} mAh
平均電圧: {avg_v:.3f}

--------------------------------

■ 状態：{stage}

■ 推奨行動
{action}

■ メンテナンス
{maint}

■ 仕上げプリセット
{pre}
"""

        self.result.setText(text)

# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = App()
    w.resize(900, 600)
    w.show()
    sys.exit(app.exec_())

