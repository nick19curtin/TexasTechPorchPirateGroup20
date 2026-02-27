from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

from datetime import datetime
import time
import subprocess
import os

# Create directory if needed
save_dir = "/home/nigelhoward03/Desktop/Videos"
os.makedirs(save_dir, exist_ok=True)

# Timestamp filename
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
h264path = f"{save_dir}/video_{timestamp}.h264"

# Initialize camera
picam2 = Picamera2()

# 720p video configuration
video_config = picam2.create_video_configuration(
    main={"size": (1280, 720 )},
    controls={"FrameRate": 30}
)
picam2.configure(video_config)

# Encoder (bitrate ~5 Mbps is good for 720p)
encoder = H264Encoder(bitrate=5_000_000)

# File output (raw .h264)
output = FileOutput(h264path)

# Start camera
picam2.start()
time.sleep(1)

print("Recording to:", h264path)

# Start recording
picam2.start_recording(encoder, output)

time.sleep(10)  # record 10 seconds

# Stop recording
picam2.stop_recording()
picam2.stop()

mp4_path = h264path.replace(".h264", "_compressed.mp4")

subprocess.run([
    "ffmpeg",
    "-y",
    "-framerate", "30",
    "-i", h264path,

    "-vf", "scale=854:480,fps=15",

    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "30",
    "-movflags", "+faststart",
    "-an",
    mp4_path
])

print("Compressed file:", mp4_path)

print("Done.")