import serial
import threading
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt

PORT = "/dev/ttyACM0"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=1)

data_I = []
data_V = []

running = True

# ===== シリアル受信 =====
def read_serial():
    while running:
        line = ser.readline().decode(errors="ignore").strip()

        if not line:
            continue

        print(line)

        if line.startswith("LOG"):
            try:
                _, cur, volt = line.split(",")

                data_I.append(float(cur))
                data_V.append(float(volt))

                if len(data_I) > 200:
                    data_I.pop(0)
                    data_V.pop(0)

            except:
                pass

threading.Thread(target=read_serial, daemon=True).start()

# ===== UI =====
root = tk.Tk()
root.title("Mini4WD Motor Break-in")

# ===== 入力 =====
frame = ttk.Frame(root)
frame.pack()

tk.Label(frame, text="PWM").grid(row=0, column=0)
entry_pwm = tk.Entry(frame)
entry_pwm.insert(0, "200")
entry_pwm.grid(row=0, column=1)

tk.Label(frame, text="RUN(ms)").grid(row=1, column=0)
entry_run = tk.Entry(frame)
entry_run.insert(0, "10000")
entry_run.grid(row=1, column=1)

tk.Label(frame, text="COOL(ms)").grid(row=2, column=0)
entry_cool = tk.Entry(frame)
entry_cool.insert(0, "5000")
entry_cool.grid(row=2, column=1)

# ===== ボタン =====
def start():
    cmd = f"START,{entry_pwm.get()},{entry_run.get()},{entry_cool.get()}\n"
    ser.write(cmd.encode())

def stop():
    ser.write(b"STOP\n")

tk.Button(root, text="START", command=start).pack()
tk.Button(root, text="STOP", command=stop).pack()

# ===== グラフ =====
plt.ion()
fig, ax = plt.subplots()

def update_plot():
    ax.clear()

    ax.plot(data_I, label="Current")
    ax.plot(data_V, label="Voltage")

    ax.legend()
    ax.set_title("Motor Monitor")

    plt.pause(0.1)
    root.after(200, update_plot)

root.after(200, update_plot)

# ===== 終了処理 =====
def on_close():
    global running
    running = False
    ser.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()

