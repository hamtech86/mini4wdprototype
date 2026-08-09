import serial
import threading
import tkinter as tk
from tkinter import ttk
import queue

PORT = '/dev/ttyACM0'
BAUD = 115200

ser = None
running = False

q = queue.Queue()

# ===== シリアル受信 =====
def read_serial():
    global running
    while running:
        try:
            line = ser.readline().decode(errors='ignore').strip()
            if line:
                q.put(line)
        except:
            pass

# ===== UI更新 =====
def update_ui():
    while not q.empty():
        line = q.get()
        text.insert(tk.END, line + "\n")
        text.see(tk.END)
    root.after(100, update_ui)

# ===== 送信 =====
def send(cmd):
    if ser:
        ser.write((cmd + '\n').encode())

# ===== ボタン =====
def start():
    send('r')

def stop():
    send('s')

def quit_app():
    global running
    running = False
    try:
        ser.close()
    except:
        pass
    root.destroy()

# ===== 接続 =====
def connect():
    global ser, running
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        running = True
        threading.Thread(target=read_serial, daemon=True).start()
        status_label.config(text='CONNECTED')
    except Exception as e:
        status_label.config(text=f'ERROR: {e}')

# ===== UI =====
root = tk.Tk()
root.title('Mini4WD Motor Tool')
root.geometry('700x500')

frame = ttk.Frame(root)
frame.pack(pady=10)

ttk.Button(frame, text='Connect', command=connect).grid(row=0, column=0, padx=5)
ttk.Button(frame, text='Start', command=start).grid(row=0, column=1, padx=5)
ttk.Button(frame, text='Stop', command=stop).grid(row=0, column=2, padx=5)
ttk.Button(frame, text='Quit', command=quit_app).grid(row=0, column=3, padx=5)

status_label = ttk.Label(root, text='DISCONNECTED')
status_label.pack()

text = tk.Text(root)
text.pack(expand=True, fill='both')

update_ui()

root.mainloop()

