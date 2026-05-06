import io
import os
import time
import json
import math
from datetime import datetime, timezone

import requests
import serial
import board
import adafruit_lis3dh
from PIL import Image
from picamera2 import Picamera2
from smbus2 import SMBus

# ========= CONFIG (env-overridable) =========
UPLOAD_URL = os.environ.get("UPLOAD_URL", "https://porchpirate-api-bgbbhgdpargxgsby.eastus-01.azurewebsites.net")
CAPTURE_CMD_URL = os.environ.get("CAPTURE_CMD_URL", "https://porchpirate-api-bgbbhgdpargxgsby.eastus-01.azurewebsites.net")
CAPTURE_ACK_URL = os.environ.get("CAPTURE_ACK_URL", "https://porchpirate-api-bgbbhgdpargxgsby.eastus-01.azurewebsites.net")
DEVICE_ID = os.environ.get("DEVICE_ID", "pi-1")
UPDATE_KEY = os.environ.get("UPDATE_KEY", "")

POLL_SEC = float(os.environ.get("POLL_SEC", "1.5"))
TIMEOUT_SEC = float(os.environ.get("TIMEOUT_SEC", "15"))

MAX_WIDTH = int(os.environ.get("MAX_WIDTH", "640"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "55"))
CAMERA_FRONT_INDEX = int(os.environ.get("CAMERA_FRONT_INDEX", "0"))
CAMERA_REAR_INDEX = int(os.environ.get("CAMERA_REAR_INDEX", "1"))

UPS_ADDR = int(os.environ.get("UPS_ADDR", "0x2D"), 16)
I2C_BUS = int(os.environ.get("I2C_BUS", "1"))

GPS_PORT = os.environ.get("GPS_PORT", "/dev/ttyUSB2")
GPS_BAUD = int(os.environ.get("GPS_BAUD", "115200"))
GPS_TIMEOUT = float(os.environ.get("GPS_TIMEOUT", "1"))

# ----- accelerometer / motion config -----
MOTION_UPLOAD_INTERVAL = float(os.environ.get("MOTION_UPLOAD_INTERVAL", "15"))  # seconds between auto uploads while moving
PICKUP_THRESHOLD = float(os.environ.get("PICKUP_THRESHOLD", "0.75"))            # sudden change = pickup
MOVEMENT_THRESHOLD = float(os.environ.get("MOVEMENT_THRESHOLD", "0.5"))         # continuous change = moving
SETTLE_TIME = float(os.environ.get("SETTLE_TIME", "5"))                         # seconds of stillness to call it at rest
ACCEL_SAMPLE_SEC = float(os.environ.get("ACCEL_SAMPLE_SEC", "0.1"))             # how often to sample accel
# ============================================


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compress_jpeg(jpeg_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    if image.width > MAX_WIDTH:
        new_height = int(image.height * (MAX_WIDTH / image.width))
        image = image.resize((MAX_WIDTH, new_height))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return output.getvalue()


def poll_capture_command(headers: dict) -> str:
    res = requests.get(
        CAPTURE_CMD_URL,
        params={"deviceId": DEVICE_ID},
        headers=headers,
        timeout=TIMEOUT_SEC,
    )
    res.raise_for_status()
    body = res.json()
    if body.get("pending") and body.get("requestId"):
        return str(body["requestId"])
    return ""


def ack_capture(headers: dict, request_id: str) -> None:
    res = requests.post(
        CAPTURE_ACK_URL,
        json={"deviceId": DEVICE_ID, "requestId": request_id},
        headers={**headers, "Content-Type": "application/json"},
        timeout=TIMEOUT_SEC,
    )
    res.raise_for_status()


def read_u16(bus: SMBus, reg_low: int) -> int:
    low = bus.read_byte_data(UPS_ADDR, reg_low)
    high = bus.read_byte_data(UPS_ADDR, reg_low + 1)
    return (high << 8) | low


def read_s16(bus: SMBus, reg_low: int) -> int:
    val = read_u16(bus, reg_low)
    if val & 0x8000:
        val -= 0x10000
    return val


def read_battery_status(bus: SMBus) -> dict:
    voltage_mv = read_u16(bus, 0x20)
    current_ma = read_s16(bus, 0x22)
    percent = read_u16(bus, 0x24)
    capacity_mah = read_u16(bus, 0x26)
    discharge_time_min = read_u16(bus, 0x28)
    charge_time_min = read_u16(bus, 0x2A)
    return {
        "voltage_mv": voltage_mv,
        "voltage_v": round(voltage_mv / 1000.0, 3),
        "current_ma": current_ma,
        "percent": percent,
        "capacity_mah": capacity_mah,
        "discharge_time_min": discharge_time_min,
        "charge_time_min": charge_time_min,
    }


def send_at(ser: serial.Serial, command: str, wait: float = 1.0) -> str:
    ser.reset_input_buffer()
    ser.write((command + "\r\n").encode())
    time.sleep(wait)
    response = b""
    while ser.in_waiting:
        response += ser.read(ser.in_waiting)
    return response.decode(errors="ignore")


def dm_to_decimal(dm: str, direction: str):
    if not dm:
        return None
    value = float(dm)
    degrees = int(value // 100)
    minutes = value - degrees * 100
    decimal = degrees + minutes / 60.0
    if direction in ("S", "W"):
        decimal = -decimal
    return decimal


def parse_cgpsinfo(response: str):
    for line in response.splitlines():
        if "+CGPSINFO:" in line:
            data = line.split(":", 1)[1].strip()
            parts = [p.strip() for p in data.split(",")]
            if len(parts) < 4:
                return None, None
            lat_dm = parts[0]
            lat_dir = parts[1]
            lon_dm = parts[2]
            lon_dir = parts[3]
            if not lat_dm or not lon_dm:
                return None, None
            lat = dm_to_decimal(lat_dm, lat_dir)
            lon = dm_to_decimal(lon_dm, lon_dir)
            return lat, lon
    return None, None


def init_gps():
    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=GPS_TIMEOUT)
        print(f"{utc_ts()} GPS serial opened on {GPS_PORT}")
        at_response = send_at(ser, "AT", 0.5)
        if "OK" not in at_response:
            print(f"{utc_ts()} GPS modem did not respond cleanly to AT: {at_response.strip()}")
        gps_on_response = send_at(ser, "AT+CGPS=1", 1.0)
        print(f"{utc_ts()} GPS on response: {gps_on_response.strip()}")
        return ser
    except Exception as exc:
        print(f"{utc_ts()} GPS init failed on {GPS_PORT}: {exc}")
        return None


def get_gps_fix(ser: serial.Serial):
    if ser is None:
        return None, None
    try:
        response = send_at(ser, "AT+CGPSINFO", 1.0)
        return parse_cgpsinfo(response)
    except Exception as exc:
        print(f"{utc_ts()} GPS read failed: {exc}")
        return None, None


def build_telemetry(bus: SMBus, gps_ser: serial.Serial, motion_state: str = "RESTING") -> dict:
    lat, lon = get_gps_fix(gps_ser)
    telemetry = {
        "deviceId": DEVICE_ID,
        "ts": utc_ts(),
        "battery": read_battery_status(bus),
        "motionState": motion_state,
    }
    if lat is not None and lon is not None:
        telemetry["lat"] = lat
        telemetry["lon"] = lon
    return telemetry


def init_camera(index: int) -> Picamera2:
    cam = Picamera2(index)
    config = cam.create_still_configuration(main={"size": (1280, 720)})
    cam.configure(config)
    cam.start()
    time.sleep(0.8)
    return cam


def capture_from_camera(cam: Picamera2) -> bytes:
    buf = io.BytesIO()
    cam.capture_file(buf, format="jpeg")
    return compress_jpeg(buf.getvalue())


# ---------- accelerometer ----------
def init_accelerometer():
    try:
        i2c = board.I2C()
        lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c)
        # Calibrate baseline
        time.sleep(0.5)
        x, y, z = lis3dh.acceleration
        baseline = math.sqrt(x * x + y * y + z * z)
        print(f"{utc_ts()} Accelerometer ready. Baseline: {baseline:.2f} m/s^2")
        return lis3dh, baseline
    except Exception as exc:
        print(f"{utc_ts()} Accelerometer init failed: {exc}")
        return None, 0.0


def get_total_acceleration(lis3dh) -> float:
    x, y, z = lis3dh.acceleration
    return math.sqrt(x * x + y * y + z * z)


# ---------- upload helper ----------
def do_upload(headers, bus, gps_ser, cam_front, cam_rear, motion_state, trigger):
    telemetry = build_telemetry(bus, gps_ser, motion_state=motion_state)
    telemetry["trigger"] = trigger  # "command" or "motion"

    front_payload = capture_from_camera(cam_front)
    rear_payload = capture_from_camera(cam_rear) if cam_rear else None

    files = {
        "image": ("front.jpg", front_payload, "image/jpeg"),
        "image_front": ("front.jpg", front_payload, "image/jpeg"),
    }
    if rear_payload:
        files["image_rear"] = ("rear.jpg", rear_payload, "image/jpeg")

    data = {
        "deviceId": DEVICE_ID,
        "ts": telemetry["ts"],
        "telemetry": json.dumps(telemetry),
    }

    res = requests.post(
        UPLOAD_URL,
        data=data,
        files=files,
        headers=headers,
        timeout=TIMEOUT_SEC,
    )
    res.raise_for_status()
    print(json.dumps(telemetry, indent=2))
    print(f"Upload [{trigger}] -> {res.status_code} {res.text[:200]}")
    print()
    return res


def main() -> None:
    headers = {}
    if UPDATE_KEY:
        headers["x-update-key"] = UPDATE_KEY

    gps_ser = init_gps()
    cam_front = init_camera(CAMERA_FRONT_INDEX)
    cam_rear = None
    try:
        cam_rear = init_camera(CAMERA_REAR_INDEX)
    except Exception as exc:
        print(f"{utc_ts()} rear camera init failed ({CAMERA_REAR_INDEX}): {exc}")

    lis3dh, baseline = init_accelerometer()

    print(f"Polling capture commands for {DEVICE_ID} every {POLL_SEC}s")
    print(f"Motion auto-upload every {MOTION_UPLOAD_INTERVAL}s while moving (settle: {SETTLE_TIME}s)")

    last_handled_request_id = ""

    # Motion state machine
    motion_state = "RESTING"  # RESTING, PICKED_UP, MOVING
    last_movement_time = time.time()
    last_motion_upload = 0.0
    prev_acceleration = baseline
    last_poll_time = 0.0

    try:
        with SMBus(I2C_BUS) as bus:
            while True:
                try:
                    now = time.time()

                    # ----- accelerometer sampling / state machine -----
                    if lis3dh is not None:
                        try:
                            current = get_total_acceleration(lis3dh)
                            difference = abs(current - baseline)
                            change_rate = abs(current - prev_acceleration)

                            if motion_state == "RESTING":
                                if change_rate > PICKUP_THRESHOLD:
                                    motion_state = "PICKED_UP"
                                    last_movement_time = now
                                    last_motion_upload = 0.0  # force immediate upload
                                    print(f"{utc_ts()} PACKAGE PICKED UP -> auto-upload starting")

                            elif motion_state == "PICKED_UP":
                                if difference > MOVEMENT_THRESHOLD:
                                    motion_state = "MOVING"
                                    last_movement_time = now
                                    print(f"{utc_ts()} Package MOVING")
                                elif now - last_movement_time > SETTLE_TIME:
                                    motion_state = "RESTING"
                                    print(f"{utc_ts()} Package settled -> auto-upload stopped")

                            elif motion_state == "MOVING":
                                if difference > MOVEMENT_THRESHOLD:
                                    last_movement_time = now
                                elif now - last_movement_time > SETTLE_TIME:
                                    motion_state = "RESTING"
                                    print(f"{utc_ts()} Package put down -> auto-upload stopped")

                            prev_acceleration = current
                        except Exception as exc:
                            print(f"{utc_ts()} accel read failed: {exc}")

                    # ----- motion-driven auto upload -----
                    if motion_state in ("PICKED_UP", "MOVING"):
                        if now - last_motion_upload >= MOTION_UPLOAD_INTERVAL:
                            try:
                                do_upload(
                                    headers, bus, gps_ser,
                                    cam_front, cam_rear,
                                    motion_state=motion_state,
                                    trigger="motion",
                                )
                            except Exception as exc:
                                print(f"{utc_ts()} motion upload failed: {exc}")
                            last_motion_upload = now

                    # ----- server-driven capture command (rate-limited by POLL_SEC) -----
                    if now - last_poll_time >= POLL_SEC:
                        last_poll_time = now
                        try:
                            request_id = poll_capture_command(headers)
                        except Exception as exc:
                            print(f"{utc_ts()} poll failed: {exc}")
                            request_id = ""

                        if request_id and request_id != last_handled_request_id:
                            try:
                                do_upload(
                                    headers, bus, gps_ser,
                                    cam_front, cam_rear,
                                    motion_state=motion_state,
                                    trigger="command",
                                )
                                ack_capture(headers, request_id)
                                last_handled_request_id = request_id
                                print(f"Capture {request_id} ack'd")
                            except Exception as exc:
                                print(f"{utc_ts()} command capture failed: {exc}")

                    # short sleep so accel polls at ~ACCEL_SAMPLE_SEC
                    time.sleep(ACCEL_SAMPLE_SEC)

                except Exception as exc:
                    print(utc_ts(), "main loop iteration failed:", exc)
                    time.sleep(POLL_SEC)
    finally:
        try:
            cam_front.stop()
        except Exception:
            pass
        if cam_rear:
            try:
                cam_rear.stop()
            except Exception:
                pass
        if gps_ser:
            try:
                gps_ser.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()