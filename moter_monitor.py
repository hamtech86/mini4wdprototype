import serial
import time

PORT = "/dev/ttyACM0"
BAUD = 115200

def parse_line(line):
    data = {}
    parts = line.strip().split(",")
    for p in parts:
        if "=" in p:
            k, v = p.split("=")
            try:
                data[k] = float(v)
            except ValueError:
                data[k] = v
    return data

def main():
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # Arduino reset待ち

    print("Serial connected")

    while True:
        try:
            line = ser.readline().decode("utf-8").strip()
            if not line:
                continue

            data = parse_line(line)

            print(
                f"VA={data.get('VA',0):.2f}V  "
                f"VB={data.get('VB',0):.2f}V  "
                f"I={data.get('I',0):.2f}A  "
                f"RPM={data.get('RPM',0):.0f}  "
                f"MAG_A={data.get('MAG_A',0):.0f}  "
                f"MAG_D={data.get('MAG_D',0)}  "
                f"TH={data.get('TH',0)}"
            )

        except KeyboardInterrupt:
            print("\nExit")
            break

    ser.close()

if __name__ == "__main__":
    main()

