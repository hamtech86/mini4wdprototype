import serial
import time
import threading
from datetime import datetime

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
time.sleep(2)

running = False
phase = 0

log = []

# ===== 送信 =====
def send(cmd):
    ser.write((cmd + "\n").encode())
    print("TX:", cmd)

# ===== 受信 =====
def rx():
    global log
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print("RX:", line)
            log.append(line)

# ===== スコア計算 =====
def calc_score():
    start_ack = log.count("ACK_START")
    stop_ack = log.count("ACK_STOP")

    phase_hits = len([l for l in log if "ACK_PHASE" in l])
    noise = len([l for l in log if l.startswith("CMD")])

    # ===== 仮スコアモデル =====
    stability = max(0, 100 - noise * 5)
    control = min(100, start_ack * 20 + stop_ack * 20)
    response = min(100, phase_hits * 25)

    total = int((stability + control + response) / 3)

    # ===== 車重推定 =====
    if total > 80:
        weight = "LIGHT 90-110g (high RPM type)"
    elif total > 60:
        weight = "STANDARD 110-130g (balanced)"
    else:
        weight = "HEAVY 130-150g (torque type)"

    return total, weight

# ===== ブレイクイン =====
def run():
    global running

    running = True

    phases = [
        (0, 60),
        (1, 300),
        (2, 300),
        (3, 180)
    ]

    for p, t in phases:
        send(f"PHASE{p}")
        send("START")
        time.sleep(t)

    send("STOP")
    running = False

# ===== スレッド =====
threading.Thread(target=rx, daemon=True).start()

# ===== 実行 =====
input("ENTERで開始")

run()

# ===== 評価 =====
score, weight = calc_score()

print("\n=== RESULT ===")
print("SCORE:", score)
print("RECOMMENDED CAR WEIGHT:", weight)

# ===== 保存 =====
fname = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

with open(fname, "w") as f:
    f.write(f"SCORE:{score}\n")
    f.write(f"WEIGHT:{weight}\n")
    f.write("\nLOG:\n")
    f.write("\n".join(log))

print("saved:", fname)

