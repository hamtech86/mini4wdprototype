import serial

ser = serial.Serial("/dev/ttyACM0",115200)

while True:
 line = ser.readline().decode().strip()
 print(line)
