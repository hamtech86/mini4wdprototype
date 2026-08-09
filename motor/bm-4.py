import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime

# =========================
# Serial
# =========================

ser = None
BAUDRATE = 57200

# =========================
# CSV
# =========================

csv_file = None
csv_writer = None

# =========================
# Utility
# =========================

def get_ports():
    return [p.device for p in serial.tools.list_ports.comports()]

def adc_to_voltage(raw):
    return (raw * 5.0 / 1023.0) * 5.7

# =========================
# GUI
# =========================

root = tk.Tk()
root.title("Motor Break-In V1")
root.geometry("900x600")

# =========================
# Variables
# =========================

port_var = tk.StringVar()

device_var = tk.StringVar(value="---")
state_var = tk.StringVar(value="DISCONNECTED")

acs1_var = tk.StringVar(value="0")
acs2_var = tk.StringVar(value="0")

a3_var = tk.StringVar(value="0")
a4_var = tk.StringVar(value="0")
a5_var = tk.StringVar(value="0")

a4v_var = tk.StringVar(value="0.00")
a5v_var = tk.StringVar(value="0.00")

motor_v_var = tk.StringVar(value="0.00")

pwm_var = tk.StringVar(value="0")

# =========================
# Main Frame
# =========================

main = ttk.Frame(root, padding=10)
main.pack(fill="both", expand=True)

# =========================
# Connection
# =========================

ttk.Label(main, text="Port").grid(row=0, column=0, sticky="w")

port_combo = ttk.Combobox(
    main,
    textvariable=port_var,
    width=20
)
port_combo.grid(row=0, column=1)

# =========================
# Refresh
# =========================

def refresh_ports():

    ports = get_ports()

    port_combo["values"] = ports

    if ports:
        port_combo.set(ports[0])

# =========================
# Connect
# =========================

def connect_serial():

    global ser

    try:

        if ser:
            ser.close()

        ser = serial.Serial(
            port_var.get(),
            BAUDRATE,
            timeout=1
        )

        state_var.set("CONNECTED")

    except Exception as e:

        state_var.set("ERROR")

        print(e)

# =========================
# Disconnect
# =========================

def disconnect_serial():

    global ser

    try:

        if ser:
            ser.close()

        ser = None

        state_var.set("DISCONNECTED")

    except:
        pass

ttk.Button(
    main,
    text="Refresh",
    command=refresh_ports
).grid(row=0, column=2)

ttk.Button(
    main,
    text="Connect",
    command=connect_serial
).grid(row=0, column=3)

ttk.Button(
    main,
    text="Disconnect",
    command=disconnect_serial
).grid(row=0, column=4)

# =========================
# Status
# =========================

row = 2

fields = [
    ("Device", device_var),
    ("State", state_var),
    ("ACS1", acs1_var),
    ("ACS2", acs2_var),
    ("A3", a3_var),
    ("A4", a4_var),
    ("A5", a5_var),
    ("A4 Voltage", a4v_var),
    ("A5 Voltage", a5v_var),
    ("Motor Voltage", motor_v_var),
    ("PWM", pwm_var),
]

for label, var in fields:

    ttk.Label(main, text=label).grid(
        row=row,
        column=0,
        sticky="w"
    )

    ttk.Label(
        main,
        textvariable=var
    ).grid(
        row=row,
        column=1,
        sticky="w"
    )

    row += 1

# =========================
# Command
# =========================

def send_command(cmd):

    global ser

    if ser is None:
        return

    try:

        ser.write(
            (cmd + "\n").encode()
        )

    except:
        pass

def start_motor():
    send_command("START")

def stop_motor():
    send_command("STOP")

ttk.Button(
    main,
    text="START",
    command=start_motor
).grid(row=15, column=0)

ttk.Button(
    main,
    text="STOP",
    command=stop_motor
).grid(row=15, column=1)

# =========================
# CSV
# =========================

def start_csv():

    global csv_file
    global csv_writer

    filename = datetime.now().strftime(
        "motor_log_%Y%m%d_%H%M%S.csv"
    )

    csv_file = open(
        filename,
        "w",
        newline=""
    )

    csv_writer = csv.writer(csv_file)

    csv_writer.writerow([
        "timestamp",
        "device",
        "acs1",
        "acs2",
        "a3",
        "a4",
        "a5",
        "motor_voltage",
        "pwm",
        "state"
    ])

    print("CSV START")

def stop_csv():

    global csv_file

    if csv_file:

        csv_file.close()

        csv_file = None

        print("CSV STOP")

ttk.Button(
    main,
    text="CSV START",
    command=start_csv
).grid(row=16, column=0)

ttk.Button(
    main,
    text="CSV STOP",
    command=stop_csv
).grid(row=16, column=1)

# =========================
# Log
# =========================

log_text = tk.Text(
    main,
    height=15
)

log_text.grid(
    row=20,
    column=0,
    columnspan=5,
    sticky="nsew"
)

# =========================
# Serial Worker
# =========================

def serial_worker():

    global csv_writer

    while True:

        if ser is None:

            time.sleep(0.1)
            continue

        try:

            line = ser.readline().decode(
                errors="ignore"
            ).strip()
            
            print("RX:",line)

            if not line:
                continue

            log_text.insert(
                tk.END,
                line + "\n"
            )

            log_text.see(tk.END)

            if line.startswith("DATA"):

                parts = line.split(",")

                if len(parts) < 9:
                    continue

                device = parts[1]

                acs1 = int(parts[2])
                acs2 = int(parts[3])

                a3 = int(parts[4])
                a4 = int(parts[5])
                a5 = int(parts[6])

                pwm = parts[7]
                state = parts[8]

                a4_v = adc_to_voltage(a4)
                a5_v = adc_to_voltage(a5)

                motor_v = a4_v - a5_v

                device_var.set(device)

                acs1_var.set(str(acs1))
                acs2_var.set(str(acs2))

                a3_var.set(str(a3))
                a4_var.set(str(a4))
                a5_var.set(str(a5))

                a4v_var.set(f"{a4_v:.2f}")
                a5v_var.set(f"{a5_v:.2f}")

                motor_v_var.set(
                    f"{motor_v:.2f}"
                )

                pwm_var.set(pwm)
                state_var.set(state)

                if csv_writer:

                    csv_writer.writerow([
                        datetime.now().isoformat(),
                        device,
                        acs1,
                        acs2,
                        a3,
                        a4,
                        a5,
                        motor_v,
                        pwm,
                        state
                    ])

        except Exception as e:

            print(e)

            time.sleep(0.1)

threading.Thread(
    target=serial_worker,
    daemon=True
).start()

refresh_ports()

root.mainloop()

