import sys
import math
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel,
    QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout,
    QLineEdit, QComboBox
)

def calculate_required_torque():
    try:
        weight_g = float(weight_input.text())
        tire_diameter_mm = float(tire_diameter_input.text())
        slope_deg = float(slope_input.text())

        # ギア比取得
        gear_ratio = float(gear_combo.currentText().split(":")[0])

        # 単位変換
        mass = weight_g / 1000.0  # g → kg
        radius = (tire_diameter_mm / 1000.0) / 2.0  # mm → m
        theta = math.radians(slope_deg)

        g = 9.80665

        # 必要トルク計算
        force = mass * g * math.sin(theta)
        tire_torque = force * radius
        motor_torque = tire_torque / gear_ratio

        # mN·m 表示
        motor_torque_mNm = motor_torque * 1000

        required_torque_label.setText(f"{motor_torque_mNm:.2f} mN·m")

    except ValueError:
        required_torque_label.setText("入力エラー")

# ===== アプリ =====
app = QApplication(sys.argv)
window = QWidget()
window.setWindowTitle("Mini4WD Motor Manager")
window.resize(1000, 650)

main_layout = QHBoxLayout()

# =============================
# 左側：入力
# =============================
left_layout = QVBoxLayout()

group_motor_setting = QGroupBox("モーターセッティング")
group_motor_setting.setLayout(QFormLayout())

# --- マシン ---
group_machine = QGroupBox("マシンセッティング")
machine_layout = QFormLayout()

weight_input = QLineEdit()
weight_input.setPlaceholderText("例：150")

gear_combo = QComboBox()
gear_combo.addItems(["3.5 : 1", "3.7 : 1", "4.0 : 1"])

tire_diameter_input = QLineEdit()
tire_diameter_input.setPlaceholderText("例：24")

tire_type_combo = QComboBox()
tire_type_combo.addItems([
    "ローフリクション",
    "スーパーハード",
    "ハード",
    "ノーマル",
    "ソフト"
])

machine_layout.addRow("車重 [g]", weight_input)
machine_layout.addRow("ギア比", gear_combo)
machine_layout.addRow("タイヤ径 [mm]", tire_diameter_input)
machine_layout.addRow("タイヤ種類", tire_type_combo)

group_machine.setLayout(machine_layout)

# --- コース ---
group_course = QGroupBox("コースセッティング")
course_layout = QFormLayout()

course_material_combo = QComboBox()
course_material_combo.addItems([
    "通常プラコース",
    "低摩擦コース",
    "高摩擦コース"
])

slope_input = QLineEdit()
slope_input.setPlaceholderText("例：30")

course_layout.addRow("コース材質", course_material_combo)
course_layout.addRow("想定傾斜角 [度]", slope_input)

group_course.setLayout(course_layout)

left_layout.addWidget(group_motor_setting)
left_layout.addWidget(group_machine)
left_layout.addWidget(group_course)
left_layout.addStretch()

# =============================
# 右側：結果
# =============================
right_layout = QVBoxLayout()

group_result = QGroupBox("必要トルク算出結果")
result_layout = QFormLayout()

required_torque_label = QLabel("---- mN·m")
result_layout.addRow("必要トルク", required_torque_label)

group_result.setLayout(result_layout)
right_layout.addWidget(group_result)
right_layout.addStretch()

# ===== レイアウト =====
main_layout.addLayout(left_layout, 2)
main_layout.addLayout(right_layout, 1)
window.setLayout(main_layout)

# ===== 自動再計算 =====
weight_input.textChanged.connect(calculate_required_torque)
tire_diameter_input.textChanged.connect(calculate_required_torque)
slope_input.textChanged.connect(calculate_required_torque)
gear_combo.currentIndexChanged.connect(calculate_required_torque)

window.show()
sys.exit(app.exec_())

