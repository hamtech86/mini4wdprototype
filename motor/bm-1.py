# ============================================================
# Mini4WD Break-in Test UI
# Python + CustomTkinter
# ============================================================

import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time

# ============================================================
# Config
# ============================================================

BAUDRATE = 115200
EXPECTED_FW = "M4_BREAKIN_V1"

# ============================================================
# Globals
# ============================================================

ser = None
running = False

# ============================================================
# UI Setup
# ============================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Mini4WD Break-in UI")
app.geometry("1000x700")

# ============================================================
# Top Frame
# ============================================================

top_frame = ctk.CTkFrame(app)
top_frame.pack(fill="x", padx=10, pady=10)

title_label = ctk.CTkLabel(
    top_frame,
    text="Mini4WD Break-in Device",
    font=("Arial", 24, "bold")
)
title_label.pack(side="left", padx=10, pady=10)

status_label = ctk.CTkLabel(
    top_frame,
    text="DISCONNECTED",
    text_color="red",
    font=("Arial", 16, "bold")
)
status_label.pack(side="right", padx=10)

# ============================================================
# Serial Frame
# ============================================================

serial_frame = ctk.CTkFrame(app)
serial_frame.pack(fill="x", padx=10, pady=10)

ports = [p.device for p in serial.tools.list_ports.comports()]

port_combo = ctk.CTkComboBox(
    serial_frame,
    values=ports,
    width=200
)
port_combo.pack(side="left", padx=10, pady=10)

# ============================================================
# PWM Frame
# ============================================================

control_frame = ctk.CTkFrame(app)
control_frame.pack(fill="x", padx=10, pady=10)

pwm_label = ctk.CTkLabel(
    control_frame,
    text="PWM: 80"
)
pwm_label.pack(pady=5)

def pwm_changed(value):
    pwm_label.configure(text=f"PWM: {int(value)}")

pwm_slider = ctk.CTkSlider(
    control_frame,
    from_=0,
    to=255,
    number_of_steps=255,
    command=pwm_changed
)

pwm_slider.set(80)
pwm_slider.pack(fill="x", padx=20)

# ============================================================
# Sensor Frame
# ============================================================

sensor_frame = ctk.CTkFrame(app)
sensor_frame.pack(fill="x", padx=10, pady=10)

current_in_label = ctk.CTkLabel(sensor_frame, text="Input Current: --- A")
current_in_label.pack(anchor="w", padx=10, pady=2)

motor_current_label = ctk.CTkLabel(sensor_frame, text="Motor Current: --- A")
motor_current_label.pack(anchor="w", padx=10, pady=2)

voltage_label = ctk.CTkLabel(sensor_frame, text="Motor Voltage: --- V")
voltage_label.pack(anchor="w", padx=10, pady=2)

temp_label = ctk.CTkLabel(sensor_frame, text="Temperature: --- C")
temp_label.pack(anchor="w", padx=10, pady=2)

state_label = ctk.CTkLabel(sensor_frame, text="State: ---")
state_label.pack(anchor="w", padx=10, pady=2)

error_label = ctk.CTkLabel(sensor_frame, text="Error: ---")
error_label.pack(anchor="w", padx=10, pady=2)

# ============================================================
# Serial Monitor
# ============================================================

monitor_frame = ctk.CTkFrame(app)
monitor_frame.pack(fill="both", expand=True, padx=10, pady=10)

monitor_text = ctk.CTkTextbox(
    monitor_frame,
    font=("Consolas", 12)
)

monitor_text.pack(fill="both", expand=True, padx=10, pady=10)

# ============================================================
# Serial Functions
# ============================================================

def log(text):
    monitor_text.insert("end", text + "\n")
    monitor_text.see("end")

def send_command(cmd):

    global ser

    if ser is None:
        return

    ser.write((cmd + "\n").encode())

    log("> " + cmd)

# ============================================================
# Connect
# ============================================================

def connect_device():

    global ser
    global running

    port = port_combo.get()

    try:

        ser = serial.Serial(port, BAUDRATE, timeout=1)

        time.sleep(2)

        send_command("GET_FW")

        timeout = time.time() + 3

        detected_fw = None

        while time.time() < timeout:

            if ser.in_waiting:

                line = ser.readline().decode(errors="ignore").strip()

                log(line)

                if line.startswith("#FW,"):

                    detected_fw = line.split(",")[1]

                    break

        if detected_fw != EXPECTED_FW:

            status_label.configure(
                text="FW MISMATCH",
                text_color="orange"
            )

            return

        status_label.configure(
            text="CONNECTED",
            text_color="green"
        )

        running = True

        thread = threading.Thread(target=serial_loop)
        thread.daemon = True
        thread.start()

    except Exception as e:

        log(str(e))

        status_label.configure(
            text="ERROR",
            text_color="red"
        )

# ============================================================
# Serial Loop
# ============================================================

def serial_loop():

    global running

    while running:

        try:

            if ser.in_waiting:

                line = ser.readline().decode(errors="ignore").strip()

                if not line:
                    continue

                log(line)

                # System Message
                if line.startswith("#"):
                    continue

                # CSV
                parts = line.split(",")

                if len(parts) < 13:
                    continue

                mode = parts[2]
                state = parts[3]
                pwm = parts[4]

                current_in = parts[5]
                current_motor = parts[6]

                voltage_motor = parts[10]

                temp_c = parts[11]

                error = parts[12]

                current_in_label.configure(
                    text=f"Input Current: {current_in} A"
                )

                motor_current_label.configure(
                    text=f"Motor Current: {current_motor} A"
                )

                voltage_label.configure(
                    text=f"Motor Voltage: {voltage_motor} V"
                )

                temp_label.configure(
                    text=f"Temperature: {temp_c} C"
                )

                state_label.configure(
                    text=f"State: {state}"
                )

                error_label.configure(
                    text=f"Error: {error}"
                )

        except Exception as e:

            log(str(e))

            running = False

# ============================================================
# Buttons
# ============================================================

button_frame = ctk.CTkFrame(app)
button_frame.pack(fill="x", padx=10, pady=10)

connect_button = ctk.CTkButton(
    button_frame,
    text="CONNECT",
    command=connect_device
)

connect_button.pack(side="left", padx=10, pady=10)

def start_motor():

    pwm = int(pwm_slider.get())

    send_command(f"SET_PWM,{pwm}")

    time.sleep(0.1)

    send_command("START")

start_button = ctk.CTkButton(
    button_frame,
    text="START",
    fg_color="green",
    command=start_motor
)

start_button.pack(side="left", padx=10)

stop_button = ctk.CTkButton(
    button_frame,
    text="STOP",
    fg_color="red",
    command=lambda: send_command("STOP")
)

stop_button.pack(side="left", padx=10)

cal_button = ctk.CTkButton(
    button_frame,
    text="CAL_ZERO",
    command=lambda: send_command("CAL_ZERO")
)

cal_button.pack(side="left", padx=10)

# ============================================================
# Main
# ============================================================

app.mainloop()

