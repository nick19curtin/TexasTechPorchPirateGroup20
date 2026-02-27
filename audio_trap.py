import pygame
import time

pygame.mixer.init()
pygame.mixer.music.load("/home/nigelhoward03/Downloads/u_xg7ssi08yr-screaming-man-389826.mp3")
pygame.mixer.music.play()
while pygame.mixer.music.get_busy():
    time.sleep(0.1)