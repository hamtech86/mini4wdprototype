import serial
import time
import threading

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
time.sleep(2)

pwm = 170
running = False

def send(cmd):
    ser.write((cmd + "\n").encode())
    print("TX:", cmd)

# ===== 生存信号スレッド =====
def keep_alive():
    while True:
        if running:
            send("ALIVE")
        time.sleep(0.3)   # ←ここが重要（生存周期）

# ===== ブレイクイン =====
def run(seconds):
    global running

    running = True

    send(f"PWM{pwm}")

    print("START BREAKIN")

    start = time.time()
    while time.time() - start < seconds:
        time.sleep(1)

    running = False
    send("STOP")

    print("END BREAKIN")

# ===== スレッド開始 =====
threading.Thread(target=keep_alive, daemon=True).start()

# ===== 実行 =====
input("ENTERで開始")

run(600)   # 10分例

