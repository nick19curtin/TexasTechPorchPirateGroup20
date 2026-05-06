# Porch Punisher — Raspberry Pi Firmware

**Texas Tech University | ECE Microcontroller Lab 2026 | Group 20**

> A smart package-theft deterrent that detects motion, captures dual-camera imagery, tracks GPS location, and streams telemetry to the cloud in real time.

---

## Team

| Name | Role |
|------|------|
| Nick Curtin | Software / Firmware |
| Mark Barrera | Hardware / Integration |
| Nigel Howard | Hardware / Integration |

**Web App:** [PorchPirateProjectWebApp](https://github.com/nick19curtin/PorchPirateProjectWebApp)  
**Live Site:** [porchpiratedb.z13.web.core.windows.net](https://porchpiratedb.z13.web.core.windows.net/)

---

## How It Works

1. The device sits inside or beneath a decoy package on a porch.
2. The **LIS3DH accelerometer** continuously monitors for sudden movement — a "pickup" event.
3. Once motion is detected, the device enters `PICKED_UP` → `MOVING` states and begins auto-uploading photos and telemetry every 15 seconds.
4. Each upload includes:
   - A **front camera** image and **rear camera** image (JPEG, compressed to 640 px wide)
   - **GPS coordinates** from the LTE modem
   - **Battery status** (voltage, current, percentage, capacity, estimated runtime)
   - **Motion state** (`RESTING`, `PICKED_UP`, or `MOVING`)
5. The web dashboard can also trigger an on-demand **remote capture command**, which the Pi polls for every 1.5 seconds.
6. When the package is put down and stillness is detected for 5 seconds, the device returns to `RESTING` and stops auto-uploading.

---

## Hardware Bill of Materials

| # | Component | Purpose | Est. Price |
|---|-----------|---------|-----------|
| 1 | [Raspberry Pi 4 Model B (4 GB)](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/) | Main compute unit running Python firmware | ~$55 |
| 2 | [Raspberry Pi Camera Module 3](https://www.raspberrypi.com/products/camera-module-3/) × 2 | Front and rear 12 MP cameras (1280×720 capture) | ~$25 each |
| 3 | [Adafruit LIS3DH Triple-Axis Accelerometer](https://www.adafruit.com/product/2809) | Pickup / motion detection over I²C | ~$5 |
| 4 | Waveshare UPS HAT (I²C, addr 0x2D) | Li-ion battery management — voltage, current, %, runtime | ~$25 |
| 5 | SIM7600G-H 4G LTE HAT | GPS fix via AT+CGPSINFO; USB serial at 115200 baud | ~$65 |
| 6 | SIM Card (data plan) | Live upload to Azure; GPS-assisted lock | ~$10/mo |
| 7 | 18650 Li-ion Battery Pack (3.7 V, 4000–6000 mAh) | Powers device via UPS HAT | ~$15 |
| 8 | MicroSD Card (32 GB, Class 10) | OS and firmware storage | ~$8 |
| 9 | Dual CSI Camera Cable Set | Connects both cameras to Pi 4 CSI ports | ~$6 |
| 10 | Enclosure / Decoy Box | Hides hardware inside a package-shaped container | ~$10 |

**Estimated Total Hardware Cost: ~$249**

> Prices are approximate retail at time of writing (2026). The SIM7600G-H and cameras are the primary cost drivers.

---

## Software Dependencies

```
picamera2       # Raspberry Pi camera interface
adafruit-lis3dh # LIS3DH accelerometer driver
adafruit-blinka # CircuitPython board/I2C abstraction
smbus2          # Raw I2C reads for UPS HAT registers
pyserial        # AT command interface to LTE/GPS modem
Pillow          # JPEG compress + resize before upload
requests        # HTTP POST to Azure API
```

Install into the provided venv:

```bash
cd PorchPirateProjectWebApp-Pi
python -m venv venv
source venv/bin/activate
pip install picamera2 adafruit-circuitpython-lis3dh smbus2 pyserial Pillow requests
```

---

## Configuration

All settings are env-overridable — no code changes needed for deployment:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_ID` | `pi-1` | Unique identifier sent with every upload |
| `UPLOAD_URL` | Azure endpoint | API endpoint for image + telemetry POST |
| `CAPTURE_CMD_URL` | Azure endpoint | API endpoint polled for remote capture commands |
| `CAPTURE_ACK_URL` | Azure endpoint | API endpoint to acknowledge a handled command |
| `UPDATE_KEY` | *(empty)* | Optional auth key sent as `x-update-key` header |
| `POLL_SEC` | `1.5` | Seconds between command-poll requests |
| `MOTION_UPLOAD_INTERVAL` | `15` | Seconds between auto-uploads while moving |
| `PICKUP_THRESHOLD` | `0.75` | Acceleration change rate (m/s²) that signals a pickup |
| `MOVEMENT_THRESHOLD` | `0.5` | Sustained acceleration delta that signals movement |
| `SETTLE_TIME` | `5` | Seconds of stillness before returning to RESTING |
| `MAX_WIDTH` | `640` | Max image width (px) before JPEG downscale |
| `JPEG_QUALITY` | `55` | JPEG quality (1–95); lower = smaller upload |
| `CAMERA_FRONT_INDEX` | `0` | Picamera2 index for the front-facing camera |
| `CAMERA_REAR_INDEX` | `1` | Picamera2 index for the rear-facing camera |
| `UPS_ADDR` | `0x2D` | I²C address of the UPS HAT |
| `I2C_BUS` | `1` | I²C bus number |
| `GPS_PORT` | `/dev/ttyUSB2` | Serial port of the LTE/GPS modem |
| `GPS_BAUD` | `115200` | Baud rate for the modem |

Example `.env` usage:

```bash
export DEVICE_ID="pi-garage"
export UPDATE_KEY="my-secret-key"
python PorchPunisher.py
```

---

## Wiring Summary

```
Raspberry Pi 4
├── CSI Port 0  ──────────────────── Front Camera (Camera Module 3)
├── CSI Port 1  ──────────────────── Rear Camera  (Camera Module 3)
├── I²C (GPIO 2/3, Bus 1)
│   ├── 0x18  ──── LIS3DH Accelerometer
│   └── 0x2D  ──── UPS HAT (battery monitor)
├── USB Port    ──────────────────── SIM7600 LTE HAT → /dev/ttyUSB2
└── GPIO Header ──────────────────── UPS HAT (power + I²C)
```

---

## Running on Boot

To start `PorchPunisher.py` automatically as a systemd service:

```bash
sudo nano /etc/systemd/system/porchpunisher.service
```

```ini
[Unit]
Description=Porch Punisher firmware
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/home/pi/PorchPirateProjectWebApp-Pi/venv/bin/python /home/pi/PorchPirateProjectWebApp-Pi/PorchPunisher.py
WorkingDirectory=/home/pi/PorchPirateProjectWebApp-Pi
Restart=always
RestartSec=5
Environment=DEVICE_ID=pi-1
Environment=UPDATE_KEY=your-key-here

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable porchpunisher
sudo systemctl start porchpunisher
```

---

## Motion State Machine

```
            ┌─────────────────────────────┐
            │           RESTING           │◄──── settled for SETTLE_TIME s
            └──────────────┬──────────────┘
                           │ change_rate > PICKUP_THRESHOLD
                           ▼
            ┌─────────────────────────────┐
            │          PICKED_UP          │ → auto-upload immediately
            └────┬───────────────────┬────┘
                 │ difference >      │ no movement for
                 │ MOVEMENT_THRESHOLD│ SETTLE_TIME s
                 ▼                   ▼
  ┌──────────────────────┐     ┌──────────────┐
  │        MOVING        │────►│   RESTING    │
  │ (upload every 15 s)  │     └──────────────┘
  └──────────────────────┘
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
