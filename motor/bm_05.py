
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
        self.brush_peak = 0

        self.motor=tk.StringVar(value="TT2")
        self.state=tk.StringVar(value="DISCONNECTED")
        self.score=tk.StringVar(value="0")
        
        self.growth_hist = deque(maxlen=20)

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
        
        self.lbl_rpm = ttk.Label(frm,text="RPM ---")
        self.lbl_rpm.grid(row=3,column=0,sticky="w")

        self.lbl_torque = ttk.Label(frm,text="Torque ---")
        self.lbl_torque.grid(row=3,column=1,sticky="w")

        self.lbl_weight = ttk.Label(frm,text="Weight ---")
        self.lbl_weight.grid(row=3,column=2,sticky="w")

        self.lbl_brush = ttk.Label(frm,text="Brush ---")
        self.lbl_brush.grid(row=4,column=0,sticky="w")

        self.lbl_growth = ttk.Label(frm,text="Growth ---")
        self.lbl_growth.grid(row=4,column=1,sticky="w")
        
      
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
            "rpm",
            "torque",
            "weight",
            "brush_peak",
            "growth_pct"

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

    def estimate(self, ci):

        db = MOTOR_DB[self.motor.get()]

        ref = max(db["current"], 1)

        current_ma = max(ci * 10, 50)

        rpm_est = db["rpm"] * (ref / current_ma)

        rpm_est = min(
            rpm_est,
            int(db["rpm"] * 1.25)
        )

        torque_est = db["torque"] * (current_ma / ref)

        torque_est = max(
            db["torque"] * 0.5,
            torque_est
        )

        torque_est = min(
            db["torque"] * 1.3,
            torque_est
        )

        weight_est = torque_est * 0.6

        return (
            int(rpm_est),
            round(torque_est,1),
            round(weight_est,1)
        )


    

        return (
            int(rpm_est),
            round(torque_est, 1),
            round(weight_est, 1)
            )

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

                rpm, torque, weight = self.estimate(ci)

                # ブラシピーク検出（瞬間ノイズ除外）
                self.bi_hist.append(bi)

                if len(self.bi_hist) >= 20:

                    sorted_bi = sorted(self.bi_hist)

                    peak_candidate = sorted_bi[-5]

                    if peak_candidate > self.brush_peak:
                        self.brush_peak = peak_candidate


                growth_pct = 0

                if self.brush_peak > 0:

                    growth_pct = (
                        (self.brush_peak-bi)
                        / self.brush_peak
                        *100
                    )

                    self.growth_hist.append(growth_pct)

                    growth_display = sum(
                        self.growth_hist
                    ) / len(self.growth_hist)


                    growth_pct = max(
                        0,
                        min(100, growth_pct)
                    )

    
                brush_ratio=1.0

                if self.brush_peak>0:
                    brush_ratio=bi/self.brush_peak


                if brush_ratio>0.9:
                    brush_state="初期"

                elif brush_ratio>0.6:
                    brush_state="育成中"

                elif brush_ratio>0.3:
                    brush_state="良好"

                else:
                    brush_state="摩耗域"

                if growth_pct <10:
                    growth_state="未育成"

                elif growth_pct <30:
                    growth_state="育成中"

                elif growth_pct <60:
                    growth_state="仕上がり"

                else:
                    growth_state="摩耗域"
                

                score=(
                       rpm/300 +
                       torque/10 +
                       si +
                       growth_pct/5

                )

                self.writer.writerow([
                    time.time(),
                    acs1,acs2,
                    ci,ti,bi,si,
                    rpm,
                    torque,
                    weight,
                    self.brush_peak,
                    growth_pct

                ])

                self.lbl_rpm.config(
                    text=f"推定無負荷回転数 : {rpm:,} rpm"
                )

                self.lbl_torque.config(
                    text=f"推定トルク : {torque:.1f} gcm"
                )

                self.lbl_weight.config(
                    text=f"推定対応車重 : {weight:.1f} g"
                )

                self.lbl_brush.config(
                    text=f"ブラシ状態 : {brush_state}"
                )

                self.lbl_growth.config(
                    text=f"育成率 : {growth_display:.1f}% ({growth_state})"
                )

                
                
                
                
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
