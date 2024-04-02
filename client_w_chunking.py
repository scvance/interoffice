import cv2
import alsaaudio as aa
import socketio
import numpy as np
import threading
import requests
import json
import time
import zlib
import RPi.GPIO as GPIO

# SERVER_IP = '172.20.10.2' # this is the ip on hotspot
SERVER_IP = '192.168.2.153'  # get your server's IP and put it here
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'
HTTP_URL = f'http://{SERVER_IP}:1234'

FORMAT = aa.PCM_FORMAT_S16_LE  # Use 16-bit signed little-endian format
CHANNELS = 1
RATE = 8000
CHUNK = 1024

sio = socketio.Client()
audio_lock = threading.Lock()
audio_out = aa.PCM(aa.PCM_PLAYBACK, aa.PCM_NORMAL, channels=CHANNELS, rate=RATE, format=FORMAT, periodsize=CHUNK)

curr_room = 0
video_room = 0
audio_room = 0
display_room = 0
audio_room_lock = threading.Lock()
video_room_lock = threading.Lock()
curr_room_lock = threading.Lock()
display_room_lock = threading.Lock()
last_frame_lock = threading.Lock()
### Rotary Encoder Stuff
clk = 17
dt = 18
button_pin = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
last_video_frame = time.time()

cv2.namedWindow('interoffice', cv2.WINDOW_NORMAL)
cv2.setWindowProperty('interoffice', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

frame_width = None
frame_height = None

def setup_frames():
    global frame_width
    global frame_height
    cap = cv2.VideoCapture(0)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    screen_width, screen_height = 1600, 1200
    frame_aspect_ratio = frame_width / frame_height
    screen_aspect_ratio = screen_width / screen_height
    if frame_aspect_ratio != screen_aspect_ratio:
        if frame_aspect_ratio > screen_aspect_ratio:
            new_height = int(screen_width / frame_aspect_ratio)
            frame_height = new_height
        else:
            new_width = int(screen_height * frame_aspect_ratio)
            frame_width = new_width



# Compress and decompress functions for audio frames
def compress_audio(audio_data):
    return zlib.compress(audio_data)


def decompress_audio(compressed_audio):
    return zlib.decompress(compressed_audio)

def compress_video(frame):
    return zlib.compress(frame)

@sio.event
def connect():
    print('Connected to server')


@sio.event
def disconnect():
    print('Disconnected from server')


@sio.event
def message(frame_data=None):
    global last_video_frame
    if frame_data is not None:
        if frame_data['audio'] is not None:
            audio_data = np.frombuffer(frame_data['audio'], dtype=np.int16)
            try:
                audio_lock.acquire()
                for chunk in audio_data:
                    audio_out.write(chunk)
            except aa.ALSAAudioError as e:
                print("ALSA Audio Error:", e)
            finally:
                audio_lock.release()
        elif frame_data['video'] is not None:
            print("num clients: ", frame_data['n_clients'], "\tclient index: ", frame_data['client_index'])
            # take the decompressed joined chunk of frames and decode it into the 10 frames
            compressed_frames_stream = frame_data['video']
            while len(compressed_frames_stream) > 0:
                # Extract the length of the compressed frame
                compressed_frame_length = int.from_bytes(compressed_frames_stream[:4], byteorder='big')
                compressed_frames_stream = compressed_frames_stream[4:]

                # Extract the compressed frame
                compressed_frame = compressed_frames_stream[:compressed_frame_length]
                compressed_frames_stream = compressed_frames_stream[compressed_frame_length:]

                # Decompress the compressed frame
                decompressed_frame = zlib.decompress(compressed_frame)
                frame = cv2.imdecode(np.frombuffer(decompressed_frame, dtype=np.uint8), cv2.IMREAD_COLOR)

                add_text(frame)
                cv2.imshow('interoffice', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    sio.disconnect()
                    cv2.destroyAllWindows()
            last_frame_lock.acquire()
            last_video_frame = time.time()
            last_frame_lock.release()



def send_audio():
    global audio_room
    audio_in = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NORMAL, channels=CHANNELS, rate=RATE, format=FORMAT, periodsize=CHUNK)
    while True:
        audio_chunks = []
        for i in range(0, int(RATE / CHUNK) // 2):
            length, data = audio_in.read()
            audio_chunks.append(data)
        audio_compressed = compress_audio(np.array(audio_chunks).tobytes())
        audio_room_lock.acquire()
        sio.emit('send_audio', {'audio': audio_compressed, 'room': audio_room})
        audio_room_lock.release()


def send_frames():
    global video_room
    cap = cv2.VideoCapture(0)
    framerate = cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) != 0 else 60
    while True:
        frame_chunk = []
        while len(frame_chunk) < 3:
            start_time = time.time()
            success, frame = cap.read()
            if not success:
                break
            _, encoded_frame = cv2.imencode('.jpg', frame)
            encoded_frame = encoded_frame.tobytes()
            end_time = time.time()
            time.sleep(max(1 / framerate - (end_time - start_time), 0))
            frame_chunk.append(zlib.compress(encoded_frame))
        compressed_frames_stream = b''
        for frame in frame_chunk:
            compressed_frames_stream += len(frame).to_bytes(4, byteorder='big') + frame
        video_room_lock.acquire()
        sio.emit('send_frame', {'video': compressed_frames_stream, 'room': video_room})
        video_room_lock.release()
        time.sleep(0.05)
    cap.release()


def check_room():
    global curr_room
    global video_room
    global audio_room
    global display_room
    global last_video_frame
    # check the rotary encoder and update the room. clockwise is positive, counterclockwise is negative
    counter = 0
    clkLastState = GPIO.input(clk)
    sensitivity = 2
    while True:
        time.sleep(.001)
        clkState = GPIO.input(clk)
        dtState = GPIO.input(dt)

        if clkState != clkLastState:
            if dtState != clkState:
                counter += 1
            else:
                counter -= 1
        # Check if the counter has reached the sensitivity threshold
        if abs(counter) >= sensitivity:
            display_room_lock.acquire()
            display_room = display_room + 1 if counter > 0 else display_room - 1
            display_room %= len(rooms)
            display_room_lock.release()
            counter = 0
        # only update the curr_room if a button is pressed
        if GPIO.input(button_pin) == GPIO.LOW and curr_room != display_room:
            video_room_lock.acquire()
            audio_room_lock.acquire()
            curr_room = display_room
            video_room = curr_room
            audio_room = curr_room
            video_room_lock.release()
            audio_room_lock.release()
            print("changed curr_room! ", rooms[curr_room])
        clkLastState = clkState
        last_frame_lock.acquire()
        last_video_time = last_video_frame
        last_frame_lock.release()
        if time.time() - last_video_time > 2:
            # put up a black screen and the room list if the video hasn't updated in 2 seconds
            black = np.zeros((480, 640, 3), np.uint8)
            add_text(black)
            cv2.imshow('interoffice', black)
            cv2.waitKey(1)

def add_text(img):
    for index, room in enumerate(rooms):
        curr_room_lock.acquire()
        color = (255, 255, 255) if index == curr_room else (200, 200, 200)
        curr_room_lock.release()
        display_room_lock.acquire()
        cv2.putText(img, room + (' <-' if index == display_room else ''), (30, 50 + (35 * index)), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        display_room_lock.release()

if __name__ == '__main__':
    setup_frames()
    sio.connect(SOCKETIO_URL)
    res = requests.get(f'{HTTP_URL}/rooms')
    rooms = json.loads(res.content)

    try:
        # Start sending frames in a separate thread
        rotary_thread = threading.Thread(target=check_room)
        thread = threading.Thread(target=send_frames)
        audio_thread = threading.Thread(target=send_audio)
        thread.start()
        audio_thread.start()
        rotary_thread.start()
        # Keep the main thread alive to handle SocketIO events
        sio.wait()
    except KeyboardInterrupt:
        GPIO.cleanup()

    thread.join()
    audio_thread.join()
    rotary_thread.join()
    sio.disconnect()
