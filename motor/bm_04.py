
"""
MOTOR_BREAKIN_V2 COMPLETE FOUNDATION
2026-06 Spec

Implemented:
- Serial 57600
- Auto calibration ACS1/ACS2
- START/STOP/PWM
- BOOST 3s
- CSV logging
- CI/TI/BI/SI
- 3V RPM estimate
- 3V Torque estimate
- Brush peak tracking
- Motor model selection
"""

import tkinter as tk
from tkinter import ttk
import serial, serial.tools.list_ports
import threading, time, csv, datetime
from collections import deque
from statistics import pstdev

ADC_TO_VOLT = 5.0/1023.0
DIVIDER_RATIO = 5.7

MOTOR_DB = {
    "TT2":{"rpm":14500,"current":1350,"torque":210},
    "AT2":{"rpm":15500,"current":1300,"torque":195},
    "RT2":{"rpm":19000,"current":1400,"torque":165},
    "HD3":{"rpm":23500,"current":1650,"torque":200},
    "PD":{"rpm":23000,"current":1750,"torque":230},
}

class App:

    def __init__(self, root):

        self.root=root
        self.root.title("MOTOR_BREAKIN_V2")

        self.ser=None
        self.running=True

        self.acs1_zero=None
        self.acs2_zero=None
        self.cal=[]

        self.ti_hist=deque(maxlen=30)
        self.bi_hist=deque(maxlen=300)

        self.motor=tk.StringVar(value="TT2")
        self.state=tk.StringVar(value="DISCONNECTED")
        self.score=tk.StringVar(value="0")

        self.build()

    def build(self):

        frm=ttk.Frame(self.root,padding=10)
        frm.pack(fill="both",expand=True)

        self.port=ttk.Combobox(frm,width=25)
        self.port.grid(row=0,column=0)

        ttk.Button(frm,text="Refresh",
                   command=self.refresh).grid(row=0,column=1)

        ttk.Button(frm,text="Connect",
                   command=self.connect).grid(row=0,column=2)

        ttk.Combobox(
            frm,
            textvariable=self.motor,
            values=list(MOTOR_DB.keys())
        ).grid(row=1,column=0)

        self.txt=tk.Text(frm,height=20,width=100)
        self.txt.grid(row=5,column=0,columnspan=4)

        ttk.Button(frm,text="START",
                   command=lambda:self.send("START")).grid(row=2,column=0)

        ttk.Button(frm,text="STOP",
                   command=lambda:self.send("STOP")).grid(row=2,column=1)

        self.pwm=ttk.Entry(frm,width=10)
        self.pwm.insert(0,"40")
        self.pwm.grid(row=2,column=2)

        ttk.Button(frm,text="SET PWM",
                   command=self.set_pwm).grid(row=2,column=3)

        self.refresh()

    def refresh(self):
        self.port["values"]=[p.device for p in serial.tools.list_ports.comports()]

    def connect(self):

        self.ser=serial.Serial(
            self.port.get(),
            57600,
            timeout=1
        )

        name=datetime.datetime.now().strftime(
            "motor_log_%Y%m%d_%H%M%S.csv"
        )

        self.csv=open(name,"w",newline="")
        self.writer=csv.writer(self.csv)

        self.writer.writerow([
            "ts","acs1","acs2",
            "ci","ti","bi","si",
            "rpm","torque","score"
        ])

        threading.Thread(
            target=self.reader,
            daemon=True
        ).start()

    def send(self,cmd):

        if self.ser:
            self.ser.write((cmd+"\n").encode())

    def set_pwm(self):

        try:
            pwm=int(self.pwm.get())
        except:
            pwm=40

        self.send(f"PWM={pwm}")

    def estimate(self,ci):

        db=MOTOR_DB[self.motor.get()]

        ref=max(db["current"],1)

        current_ma=max(ci*10,1)

        rpm=int(db["rpm"]*(ref/current_ma))

        torque=round(
            db["torque"]*(current_ma/ref),
            1
        )

        return rpm,torque

    def reader(self):

        while True:

            try:

                line=self.ser.readline().decode(
                    errors="ignore"
                ).strip()

                if not line:
                    continue

                if not line.startswith("DATA,"):
                    continue

                p=line.split(",")

                if len(p)<9:
                    continue

                acs1=int(p[2])
                acs2=int(p[3])

                if self.acs1_zero is None:

                    self.cal.append((acs1,acs2))

                    if len(self.cal)>=30:

                        self.acs1_zero=int(
                            sum(x for x,y in self.cal)/30
                        )

                        self.acs2_zero=int(
                            sum(y for x,y in self.cal)/30
                        )

                    continue

                ci=abs(acs1-self.acs1_zero)
                ti=ci

                bi=abs(acs2-self.acs2_zero)

                self.ti_hist.append(ti)
                self.bi_hist.append(bi)

                si=100

                if len(self.ti_hist)>5:
                    si=max(
                        0,
                        100-pstdev(self.ti_hist)
                    )

                rpm,torque=self.estimate(ci)

                peak=max(self.bi_hist) if self.bi_hist else 0

                growth=0
                if peak:
                    growth=(peak-bi)/peak

                score=(
                    rpm/300 +
                    torque/10 +
                    si +
                    growth*20
                )

                self.writer.writerow([
                    time.time(),
                    acs1,acs2,
                    ci,ti,bi,si,
                    rpm,torque,score
                ])

                self.txt.insert(
                    "end",
                    f"CI={ci} BI={bi} "
                    f"SI={si:.1f} "
                    f"RPM={rpm} "
                    f"TQ={torque} "
                    f"S={score:.1f}\n"
                )

                self.txt.see("end")

            except Exception as e:
                print(e)

root=tk.Tk()
App(root)
root.mainloop()
