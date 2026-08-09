import serial
import threading
import tkinter as tk
from tkinter import ttk

PORT = "/dev/ttyACM0"
BAUD = 115200

ser = None
running = False

# ===== データ =====
data = {
    "AVG_I": 0,
    "PEAK_I": 0,
    "RPM": 0,
    "V_MOTOR": 0,
    "STATE": "",
    "SCORE": 0
}

# ===== 接続 =====
def connect():
    global ser
    ser = serial.Serial(PORT, BAUD, timeout=1)
    log("Connected")

# ===== ログ =====
def log(msg):
    txt.insert(tk.END, msg + "\n")
    txt.see(tk.END)

# ===== 送信 =====
def send(cmd):
    if ser:
        ser.write((cmd + "\n").encode())

# ===== 測定開始 =====
def start():
    global running
    running = True
    send("d")
    log("START CMD")

# ===== 読み取りスレッド =====
def reader():
    global running

    while True:
        if ser and ser.in_waiting:
            line = ser.readline().decode(errors='ignore').strip()
            log(line)

            if ":" in line:
                key, val = line.split(":")

                if key in data:
                    try:
                        data[key] = float(val)
                    except:
                        data[key] = val

            if "DONE" in line:
                running = False
                analyze()

# ===== 解析 =====
def analyze():
    avgI = data["AVG_I"]
    rpm = data["RPM"]
    v = data["V_MOTOR"]

    # ===== 推定 =====
    torque = avgI * 0.002   # 仮係数
    no_load_rpm = rpm * (12.0 / max(v, 1))  # 電圧補正

    # 推奨車重
    weight = torque * 200   # 仮モデル

    # ===== 表示 =====
    result.set(
        f"無負荷回転数: {int(no_load_rpm)} rpm\n"
        f"トルク: {torque:.2f}\n"
        f"推奨車重: {int(weight)} g\n"
        f"状態: {data['STATE']} (Score {int(data['SCORE'])})"
    )

# ===== ブレイクインプリセット =====
def set_brush(mode):
    if mode == "copper":
        log("銅ブラシ: 高電圧・短時間")
    elif mode == "carbon":
        log("カーボン: 低電圧・長時間")

# ===== UI =====
root = tk.Tk()
root.title("Mini4WD Motor Analyzer V1")

frame = ttk.Frame(root, padding=10)
frame.grid()

btn_connect = ttk.Button(frame, text="Connect", command=connect)
btn_connect.grid(row=0, column=0)

btn_start = ttk.Button(frame, text="Start", command=start)
btn_start.grid(row=0, column=1)

btn_copper = ttk.Button(frame, text="銅ブラシ", command=lambda: set_brush("copper"))
btn_copper.grid(row=1, column=0)

btn_carbon = ttk.Button(frame, text="カーボン", command=lambda: set_brush("carbon"))
btn_carbon.grid(row=1, column=1)

result = tk.StringVar()
label = ttk.Label(frame, textvariable=result, width=40)
label.grid(row=2, column=0, columnspan=2)

txt = tk.Text(frame, width=60, height=20)
txt.grid(row=3, column=0, columnspan=2)

# ===== スレッド開始 =====
threading.Thread(target=reader, daemon=True).start()

root.mainloop()

