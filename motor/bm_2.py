import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time
from collections import deque
from statistics import pstdev

ADC_TO_VOLT = 5.0 / 1023.0
DIVIDER_RATIO = 5.7


class MotorBreakInUI:

    def boost_5v_3s(self):
        if not self.ser:
            return
        self.send('PWM=255')
        self.boost_active = True
        self.boost_start_time = time.time()

    def stop(self):
        self.send('STOP')
        self.boost_active = False
        self.running = False

        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None

        if self.ser:
            try:
                self.ser.close()
            except:
                pass

    def toggle_log(self):
        self.log_enabled = not self.log_enabled

    def set_pwm(self):
        val = self.pwm_entry.get()
        self.send(f'PWM={val}')

    def __init__(self, root):
        self.root = root
        self.root.title('MOTOR_BREAKIN_V1')

        self.ser = None
        self.running = True

        self.acs1_zero = 0
        self.acs2_zero = 0
        self.cal_samples = []
        self.ti_history = deque(maxlen=30)

        self.device_var = tk.StringVar(value='---')
        self.state_var = tk.StringVar(value='DISCONNECTED')
        self.acs1_var = tk.StringVar(value='0')
        self.acs2_var = tk.StringVar(value='0')
        self.a3_var = tk.StringVar(value='0')
        self.a4_var = tk.StringVar(value='0')
        self.a5_var = tk.StringVar(value='0')
        self.a4v_var = tk.StringVar(value='0.00')
        self.a5v_var = tk.StringVar(value='0.00')
        self.motorv_var = tk.StringVar(value='0.00')
        self.pwm_var = tk.StringVar(value='0')
        self.ti_var = tk.StringVar(value='0')
        self.si_var = tk.StringVar(value='0')
        self.rpm_var = tk.StringVar(value='0')

        self.boost_active = False
        self.boost_start_time = 0

        self.csv_file = None
        self.log_enabled = True

        self.build_ui()

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill='both', expand=True)

        self.port_cb = ttk.Combobox(frm, width=30)
        self.port_cb.grid(row=0, column=0)

        ttk.Button(frm, text='Refresh', command=self.refresh_ports).grid(row=0, column=1)
        ttk.Button(frm, text='Connect', command=self.connect).grid(row=0, column=2)

        labels = [
            ('Device', self.device_var),
            ('State', self.state_var),
            ('ACS1', self.acs1_var),
            ('ACS2', self.acs2_var),
            ('A3', self.a3_var),
            ('A4', self.a4_var),
            ('A5', self.a5_var),
            ('A4 Voltage', self.a4v_var),
            ('A5 Voltage', self.a5v_var),
            ('Motor Voltage', self.motorv_var),
            ('PWM', self.pwm_var),
            ('TI', self.ti_var),
            ('SI', self.si_var),
            ('RPM', self.rpm_var),
        ]

        r = 1
        for name, var in labels:
            ttk.Label(frm, text=name).grid(row=r, column=0, sticky='w')
            ttk.Label(frm, textvariable=var).grid(row=r, column=1, sticky='w')
            r += 1

        ttk.Button(frm, text='START', command=lambda: self.send('START')).grid(row=r, column=0)
        ttk.Button(frm, text='STOP', command=self.stop).grid(row=r, column=1)

        tk.Button(frm, text='BOOST 5V 3s',
                  command=self.boost_5v_3s).grid(row=r, column=2)

        ttk.Button(frm, text='LOG ON/OFF',
                   command=self.toggle_log).grid(row=r+1, column=2)

        self.pwm_entry = ttk.Entry(frm)
        self.pwm_entry.insert(0, '40')
        self.pwm_entry.grid(row=r+1, column=0)

        ttk.Button(frm, text='SET PWM',
                   command=self.set_pwm).grid(row=r+1, column=1)

        self.refresh_ports()

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb['values'] = ports
        if ports:
            self.port_cb.set(ports[0])

    def connect(self):
        self.ser = serial.Serial(self.port_cb.get(), 57600, timeout=1)

        import datetime
        fname = datetime.datetime.now().strftime("motor_log_%Y%m%d_%H%M%S.csv")

        self.csv_file = open(fname, 'w')
        self.csv_file.write("raw_line\n")

        time.sleep(2)
        threading.Thread(target=self.reader, daemon=True).start()

    def send(self, cmd):
        if self.ser:
            self.ser.write((cmd + '\n').encode())

    def reader(self):
        while self.running:
            try:
                if not self.ser:
                    return

                line = self.ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue

                if line.startswith('DATA,'):
                    if self.log_enabled and self.csv_file:
                        self.csv_file.write(line + '\n')

                    p = line.split(',')
                    if len(p) < 9:
                        continue

                    acs1 = int(p[2])
                    acs2 = int(p[3])
                    a3 = int(p[4])
                    a4 = int(p[5])
                    a5 = int(p[6])

                    self.device_var.set(p[1])
                    self.acs1_var.set(str(acs1))
                    self.acs2_var.set(str(acs2))
                    self.a3_var.set(str(a3))
                    self.a4_var.set(str(a4))
                    self.a5_var.set(str(a5))
                    self.pwm_var.set(p[7])
                    self.state_var.set(p[8])

                    if self.acs1_zero == 0:
                        self.cal_samples.append((acs1, acs2))
                        if len(self.cal_samples) >= 30:
                            self.acs1_zero = sum(x for x, _ in self.cal_samples) // 30
                            self.acs2_zero = sum(y for _, y in self.cal_samples) // 30

                    a4v = a4 * ADC_TO_VOLT * DIVIDER_RATIO
                    a5v = a5 * ADC_TO_VOLT * DIVIDER_RATIO
                    motorv = a4v - a5v

                    self.a4v_var.set(f'{a4v:.2f}')
                    self.a5v_var.set(f'{a5v:.2f}')
                    self.motorv_var.set(f'{motorv:.2f}')

                    ti = abs(acs1 - self.acs1_zero)
                    self.ti_history.append(ti)

                    if len(self.ti_history) > 10:
                        self.ti_history.popleft()

                    # BOOST制御
                    if self.boost_active:
                        if time.time() - self.boost_start_time > 3:
                            self.send('PWM=40')
                            self.boost_active = False

                    # SI計算（ここが正しい位置）
                    if len(self.ti_history) >= 2:
                        si = max(0.0, 100.0 - pstdev(self.ti_history))
                    else:
                        si = 100.0

                    rpm = int(max(0, motorv * 3000))

                    self.ti_var.set(f'{ti:.1f}')
                    self.si_var.set(f'{si:.1f}')
                    self.rpm_var.set(str(rpm))

            except Exception as e:
                print(e)


root = tk.Tk()
app = MotorBreakInUI(root)
root.mainloop()

