import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import serial
import serial.tools.list_ports
import threading
import csv
from datetime import datetime

# -------------------------
# グローバル
# -------------------------

ser = None
running = False
csv_file = None
csv_writer = None

# -------------------------
# COM検索
# -------------------------

def refresh_ports():
    ports = serial.tools.list_ports.comports()

    port_list = []

    for p in ports:
        port_list.append(p.device)

    combo_port["values"] = port_list

    if port_list:
        combo_port.current(0)

# -------------------------
# 接続
# -------------------------

def connect_device():

    global ser

    port = combo_port.get()

    try:
        ser = serial.Serial(
            port,
            57600,
            timeout=1
        )

        log("Connected")

        ser.write(b"INFO\n")

        threading.Thread(
            target=read_thread,
            daemon=True
        ).start()

    except Exception as e:
        log(str(e))

# -------------------------
# ログ
# -------------------------

def log(msg):

    txt.insert(
        tk.END,
        str(msg) + "\n"
    )

    txt.see(tk.END)

# -------------------------
# CSV
# -------------------------

def start_csv():

    global csv_file
    global csv_writer

    filename = datetime.now().strftime(
        "motor_%Y%m%d_%H%M%S.csv"
    )

    csv_file = open(
        filename,
        "w",
        newline=""
    )

    csv_writer = csv.writer(csv_file)

    csv_writer.writerow([
        "time",
        "acs1",
        "acs2",
        "therm",
        "vplus",
        "pwm",
        "running"
    ])

    log("CSV START")

# -------------------------
# PWM送信
# -------------------------

def send_pwm():

    if ser is None:
        return

    pwm = entry_pwm.get()

    cmd = f"PWM={pwm}\n"

    ser.write(cmd.encode())

# -------------------------
# STOP
# -------------------------

def stop_motor():

    if ser is None:
        return

    ser.write(b"STOP\n")

# -------------------------
# 受信
# -------------------------

def read_thread():

    global csv_writer

    while True:

        try:

            line = ser.readline()

            if not line:
                continue

            line = line.decode(
                errors="ignore"
            ).strip()

            log(line)

            if line.startswith("DATA"):

                parts = line.split(",")

                if len(parts) >= 7:

                    if csv_writer:

                        csv_writer.writerow([
                            datetime.now(),
                            parts[1],
                            parts[2],
                            parts[3],
                            parts[4],
                            parts[5],
                            parts[6]
                        ])

        except Exception as e:

            log(e)
            break

# -------------------------
# GUI
# -------------------------

root = tk.Tk()

root.title("Mini4WD Motor Device")

frame = ttk.Frame(root)
frame.pack(fill="both", expand=True)

ttk.Label(
    frame,
    text="COM"
).grid(row=0, column=0)

combo_port = ttk.Combobox(
    frame,
    width=15
)

combo_port.grid(
    row=0,
    column=1
)

ttk.Button(
    frame,
    text="Refresh",
    command=refresh_ports
).grid(
    row=0,
    column=2
)

ttk.Button(
    frame,
    text="Connect",
    command=connect_device
).grid(
    row=0,
    column=3
)

ttk.Label(
    frame,
    text="PWM"
).grid(
    row=1,
    column=0
)

entry_pwm = ttk.Entry(
    frame,
    width=10
)

entry_pwm.insert(0, "80")

entry_pwm.grid(
    row=1,
    column=1
)

ttk.Button(
    frame,
    text="START",
    command=send_pwm
).grid(
    row=1,
    column=2
)

ttk.Button(
    frame,
    text="STOP",
    command=stop_motor
).grid(
    row=1,
    column=3
)

ttk.Button(
    frame,
    text="CSV START",
    command=start_csv
).grid(
    row=2,
    column=0
)

txt = tk.Text(
    frame,
    width=100,
    height=30
)

txt.grid(
    row=3,
    column=0,
    columnspan=4
)

refresh_ports()

root.mainloop()



