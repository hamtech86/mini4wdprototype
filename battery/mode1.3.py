class Mode1Widget(QWidget):
    def __init__(self, serial_worker):
        super().__init__()
        self.serial_thread = serial_worker
        self.voltage_log = deque(maxlen=500)
        self.current_log = deque(maxlen=500)
        self.pwm_log = deque(maxlen=500)
        self.start_time = None
        self.discharge_active = False
        self.paused = False
        self.pause_start = None
        self.accumulated_pause = 0
        self.finish_time = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        # Voltage/Current/PWM表示
        self.voltage_label = QLabel("Battery[V]: --")
        self.voltage_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.voltage_label)
        self.current_label = QLabel("Current[A]: --")
        self.current_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.current_label)
        self.pwm_label = QLabel("PWM: --")
        self.pwm_label.setStyleSheet("color:lime; background-color:black;")
        layout.addWidget(self.pwm_label)

        # 物理スイッチ表示
        self.switch_label = QLabel("Switch: --")
        layout.addWidget(self.switch_label)

        # Status
        self.status_label = QLabel("Status: --")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # 一時停止/再開 & 放電開始/停止
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_discharge)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_discharge)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.pause_btn)
        layout.addLayout(btn_layout)

        # 時間表示
        self.time_label = QLabel("Time: -- s")
        layout.addWidget(self.time_label)

        # グラフ
        self.figure = Figure(figsize=(6,4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax2 = self.ax.twinx()
        layout.addWidget(self.canvas)

        # タイマー更新
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(200)
        self.setLayout(layout)

    def toggle_pause(self):
        if not self.discharge_active:
            return
        if self.paused:
            # Resume
            self.paused = False
            self.accumulated_pause += time.time() - self.pause_start
            self.pause_btn.setText("Pause")
        else:
            # Pause
            self.paused = True
            self.pause_start = time.time()
            self.pause_btn.setText("Resume")

    def handle_serial(self, data):
        self.voltage_log.append(data["voltage"])
        self.current_log.append(data["current"])
        self.pwm_log.append(data["pwm"])
        self.discharge_active = data["state"]==1
        # 物理スイッチ表示
        self.switch_label.setText(f"Switch: {'ON' if self.discharge_active else 'OFF'}")
        if self.discharge_active and self.start_time is None:
            self.start_time = time.time()
            self.accumulated_pause = 0
            self.finish_time = None
        if self.voltage_log[-1]<=0.9 and self.discharge_active:
            self.discharge_active=False
            self.finish_time = time.time()-self.start_time - self.accumulated_pause

    def update_ui(self):
        if not self.voltage_log:
            return
        voltage = self.voltage_log[-1]
        current = self.current_log[-1]
        pwm = self.pwm_log[-1]

        self.voltage_label.setText(f"Battery[V]: {voltage:.3f}")
        self.current_label.setText(f"Current[A]: {current:.2f}")
        self.pwm_label.setText(f"PWM: {pwm}")

        # Status表示
        if voltage<=0.9:
            text,color="Finish","green"
        elif voltage<=0.95:
            text,color="Warning","blue"
        elif self.discharge_active:
            text,color="Discharging","orange"
        else:
            text,color="Idle","gray"
        self.status_label.setText(f"Status: {text}")
        self.status_label.setStyleSheet(f"background-color:{color}; color:white;")

        # 経過時間
        if self.start_time:
            if self.paused:
                elapsed = self.pause_start - self.start_time - self.accumulated_pause
            elif self.finish_time:
                elapsed = self.finish_time
            else:
                elapsed = time.time() - self.start_time - self.accumulated_pause
            self.time_label.setText(f"Time: {elapsed:.1f} s")
        else:
            self.time_label.setText("Time: -- s")

        # グラフ更新
        self.ax.clear(); self.ax2.clear()
        self.ax.plot(list(self.voltage_log),label="Voltage[V]",color="orange")
        self.ax.plot(list(self.current_log),label="Current[A]",color="blue")
        self.ax2.plot(list(self.pwm_log),label="PWM",color="green")
        self.ax.legend(loc="upper left"); self.ax2.legend(loc="upper right")
        self.canvas.draw()
