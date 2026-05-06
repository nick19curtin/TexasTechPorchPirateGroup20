# Porch Punisher — Raspberry Pi Firmware

**Texas Tech University | ECE Microcontroller Lab 2026 | Group 20**

> A smart package-theft deterrent that detects motion, captures dual-camera imagery, tracks GPS location, and streams telemetry to the cloud in real time.

---

## Team

| Name | Role |
|------|------|
| Nick Curtin | Software / Firmware / Modeling|
| Mark Barrera | Hardware / Integration / Modeling |
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

| # | Component | Qty | Unit Cost | Item Total | Source |
|---|-----------|:---:|----------:|----------:|--------|
| 1 | Waveshare UPS HAT (E) | 1 | $45.00 | $45.00 | Stockroom |
| 2 | 21700 5000mAh Batteries | 4 | $6.00 | $24.00 | Stockroom |
| 3 | SIM 7600NA-H 4G HAT | 1 | $90.00 | $90.00 | Personal |
| 4 | EIOT Club Prepaid SIM Plan | 1 | $20.00 | $20.00 | Personal |
| 5 | Raspberry Pi Cameras | 1 | $40.00 | $40.00 | Stockroom |
| 6 | Limit Switch | 2 | $1.02 | $2.04 | Stockroom |
| 7 | Potentiometer | 2 | $2.06 | $4.12 | Stockroom |
| 8 | Accelerometer (LIS3DH) | 1 | $4.95 | $4.95 | Stockroom |
| 9 | 1W LEDs | 1 | $7.69 | $7.69 | Stockroom |
| 10 | LED Driver | 1 | $8.98 | $8.98 | Stockroom |
| 11 | MOSFET (STP9NK50ZFP) | 2 | $2.80 | $5.60 | Stockroom |
| 12 | Terminal Block | 1 | $0.96 | $0.96 | Personal |
| 13 | 18650 3200mAh 10A Battery | 4 | $2.54 | $10.16 | Personal |
| 14 | 3S 12V 10A BMS Board | 1 | $2.74 | $2.74 | Personal |
| 15 | 1S 3.7V 4A BMS Board | 1 | $0.60 | $0.60 | Personal |
| 16 | 18650 Battery Holders | 4 | $0.60 | $2.40 | Personal |
| 17 | Accelerometer PCB (JLCPCB) | 1 | $4.62 | $4.62 | Personal |
| 18 | CC/CV Charger Module | 1 | $9.99 | $9.99 | Stockroom |
| 19 | Schottky Diode (SB530-E3/73) | 2 | $1.20 | $2.40 | Stockroom |
| 20 | Timing PCB (JLCPCB) | 1 | $10.81 | $10.81 | Personal |
| 21 | Servo Motor | 1 | $9.99 | $9.99 | Personal |
| 22 | DC Motor (PAN14EE12AA1) | 1 | $5.14 | $5.14 | Stockroom |
| 23 | 2kg of Filament (3D Print) | 1 | $25.49 | $25.49 | Stockroom |
| 24 | Boxes | 1 | $15.99 | $15.99 | Stockroom |
| 25 | Heat Thread Inserts | 1 | $9.98 | $9.98 | Stockroom |
| 26 | Female to Female Headers | 1 | $3.99 | $3.99 | Stockroom |
| 27 | 555 Timers (NE555P) | 2 | $0.59 | $1.18 | Stockroom |
| 28 | 1000 RPM Motor | 1 | $14.99 | $14.99 | Stockroom |
| 29 | 3000 RPM Motor | 1 | $15.99 | $15.99 | Stockroom |
| 30 | Glitter | 2 | $14.95 | $29.90 | Stockroom |
| 31 | Camera Extensions | 1 | $9.99 | $9.99 | Personal |

| Category | Total |
|----------|------:|
| Stockroom | $277.42 |
| Personal | $162.27 |
| **Project Total** | **$439.69** |

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
