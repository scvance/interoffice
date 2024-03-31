import RPi.GPIO as GPIO
import cv2
import threading
import time
import numpy as np

curr_room = 0
curr_room_lock = threading.Lock()
### Rotary Encoder Stuff
clk = 17
dt = 18
button_pin = 27
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setmode(GPIO.BCM)
GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
last_video_frame = time.time()

rooms = ["Evan's office", "Sam's office", "Meeting room", "Break room"]

def check_room():
    global curr_room
    display_room = curr_room
    # check the rotary encoder and update the room. clockwise is positive, counterclockwise is negative
    counter = 0
    clkLastState = GPIO.input(clk)
    sensitivity = 2
    try:
        while True:
            clkState = GPIO.input(clk)
            dtState = GPIO.input(dt)

            if clkState != clkLastState:
                if dtState != clkState:
                    counter += 1
                else:
                    counter -= 1
            # Check if the counter has reached the sensitivity threshold
            if abs(counter) >= sensitivity:
                display_room = display_room + 1 if counter > 0 else display_room - 1
                display_room %= len(rooms)
                counter = 0
            # only update the curr_room if a button is pressed
            if GPIO.input(button_pin) == GPIO.HIGH:
                curr_room_lock.acquire()
                curr_room = display_room
                curr_room_lock.release()
            clkLastState = clkState
            if time.time() - last_video_frame > 5:
                # put up a black screen and the room list if the video hasn't updated in 5 seconds
                black = np.zeros((480, 640, 3), np.uint8)
                for index, room in enumerate(rooms):
                    color = (255, 255, 255) if index == display_room else (200, 200, 200)
                    cv2.putText(black, room, (30, 50 + (35 * index)), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                cv2.imshow('Video Stream', black)
                cv2.waitKey(1)
    except KeyboardInterrupt:
        GPIO.cleanup()

check_room()