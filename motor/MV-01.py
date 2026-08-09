import serial
import threading
import matplotlib.pyplot as plt

# ===== 設定 =====
PORT = "/dev/ttyUSB0"  # ←環境に合わせて変更
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=1)

# ===== データ =====
data_I = []
data_V = []
data_RPM = []

result = {}
running = True

# ===== シリアル受信（別スレッドOK）=====
def read_serial():
    global running

    while running:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue

        print(line)

        if line.startswith("P:"):
            try:
                parts = line.split(",")

                rpm = float(parts[1].split(":")[1])
                current = float(parts[2].split(":")[1])

                # 電圧推定（PWMから）
                pwm = 235
                voltage = 3.0 * pwm / 255.0

                data_I.append(current)
                data_V.append(voltage)
                data_RPM.append(rpm)

                # データ数制限（重くなるの防止）
                if len(data_I) > 200:
                    data_I.pop(0)
                    data_V.pop(0)
                    data_RPM.pop(0)

            except:
                pass

        # ===== RESULT =====
        if line.startswith("STATE:"):
            result["STATE"] = line.split(":")[1]

        if line.startswith("SCORE:"):
            result["SCORE"] = line.split(":")[1]

        if line.startswith("AVG_I:"):
            result["AVG_I"] = line.split(":")[1]

        if line.startswith("PEAK_I:"):
            result["PEAK_I"] = line.split(":")[1]

        if line.startswith("STABILITY:"):
            result["STABILITY"] = line.split(":")[1]

        if line == "DONE":
            print("\n===== RESULT =====")
            for k, v in result.items():
                print(f"{k}: {v}")
            print("==================\n")

# ===== スレッド起動 =====
threading.Thread(target=read_serial, daemon=True).start()

# ===== グラフ（メインスレッドで実行）=====
plt.ion()
fig, ax = plt.subplots()

print("r: start / s: stop / q: quit")

while True:

    # ===== キーボード入力（非ブロッキング風）=====
    if ser.in_waiting:
        pass

    try:
        # 非ブロッキング入力（簡易）
        import sys
        import select

        if select.select([sys.stdin], [], [], 0)[0]:
            cmd = sys.stdin.readline().strip()

            if cmd == "q":
                running = False
                break

            ser.write(cmd.encode())

    except:
        pass

    # ===== 描画 =====
    ax.clear()

    ax.plot(data_I, label="Current")
    ax.plot(data_V, label="Voltage")
    ax.plot(data_RPM, label="RPM")

    ax.legend()
    ax.set_title("Motor Monitor")

    plt.pause(0.2)

ser.close()

