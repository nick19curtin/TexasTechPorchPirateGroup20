# Attempting to do software motion detection interrupt with OpenCV
from picamera2 import Picamera2
import cv2
import numpy as np
import time

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main = {"size": (640, 480), "format": "XRGB8888"}))
picam2.start()
time.sleep(2)

prev_gray = None

def capture_image():
    filename = f"image_{int(time.time())}.jpg"
    # switching to still config for better quality
    picam2.switch_mode_and_capture_file(picam2.create_still_configuration(main = {"size": (4608, 2592), "format": "RGB888"}), filename )
    print("Image captured: ", filename)
    

while True:
    frame = picam2.capture_array()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    
    if prev_gray is None:
        prev_gray = gray
        continue


    frame_delta = cv2.absdiff(prev_gray, gray)
    thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
    motion_level = np.sum(thresh) / 255
    
    if motion_level > 5000:
        capture_image()
        
    prev_gray = gray 
    
                                    