import cv2
import pyaudio
import socketio
import numpy as np
import threading
import requests
import json
import time
import zlib

SERVER_IP = 'localhost'  # get your server's IP and put it here
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'
HTTP_URL = f'http://{SERVER_IP}:1234'

CHANNELS = 1
RATE = 44100
FORMAT = pyaudio.paInt16
CHUNK = 1024

sio = socketio.Client()
p = pyaudio.PyAudio()
audio_out = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)

curr_room = 0
video_room = 0
audio_room = 0
display_room = 0
audio_lock = threading.Lock()
audio_room_lock = threading.Lock()
video_room_lock = threading.Lock()
curr_room_lock = threading.Lock()
display_room_lock = threading.Lock()
last_frame_lock = threading.Lock()
video_lock = threading.Lock()

camera_dims = (1280, 720)

last_video_frame = time.time()
curr_image = None

def compress_audio(audio_data):
    return zlib.compress(audio_data.tobytes())

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
    if frame_data['audio'] is not None:
        try:
            audio_data = np.frombuffer(frame_data['audio'], dtype=np.int16)

            audio_lock.acquire()

            for i in range(0, len(audio_data), CHUNK):
                chunk = audio_data[i:i+CHUNK]
                audio_out.write(chunk.tobytes())
        except Exception as e:
            print("Audio Output Error:", e)
        finally:
            if audio_lock.locked():
                audio_lock.release()
    if frame_data['video'] is not None:
        client_num = frame_data['n_clients']
        client_index = frame_data['client_index']
        print('num clients: ', client_num, '\tclient index: ', client_index)
        # frame = frame_data['video']
        # frame = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
        # add_text(frame)
        # # cv2.imshow('interoffice', frame)
        # global curr_image
        # curr_image = frame
        # last_frame_lock.acquire()
        # last_video_frame = time.time()
        # last_frame_lock.release()
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
            global curr_image
            curr_image = frame
        last_frame_lock.acquire()
        last_video_frame = time.time()
        last_frame_lock.release()

def send_audio():
    global audio_room

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    while True:
        # time.sleep(10)
        audio_chunks = []
        for i in range(0, int(RATE / CHUNK) // 2):
            data = stream.read(CHUNK)
            audio_chunks.append(data)
        audio_compressed = compress_audio(np.frombuffer(b''.join(audio_chunks), dtype=np.int16))
        
        audio_room_lock.acquire()
        try:
            sio.emit('send_audio', {'audio': audio_compressed, 'room': audio_room})
        except Exception as e:
            sio.disconnect()
            sio.connect(SOCKETIO_URL)
            print("Error sending audio:", e)
        audio_room_lock.release()

    stream.stop_stream()
    stream.close()
    p.terminate()


def send_frames():
    global video_room
    cap = cv2.VideoCapture(0)
    framerate = 20
    # while True:
    #     # time.sleep(10)
    #     start_time = time.time()
    #     success, frame = cap.read()
    #     if not success:
    #         break
    #     _, encoded_frame = cv2.imencode('.jpg', frame)
    #     encoded_frame = encoded_frame.tobytes()
    #     end_time = time.time()
    #     time.sleep(max(1 / framerate - (end_time - start_time), 0))
    #     compressed_frame = zlib.compress(encoded_frame)
    #     video_room_lock.acquire()
    #     sio.emit('send_frame', {'video': compressed_frame, 'room': video_room})
    #     video_room_lock.release()

    while True:
        frame_chunk = []
        starting_time = time.time()
        while time.time() - starting_time < .1:
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
        try:
            sio.emit('send_frame', {'video': compressed_frames_stream, 'room': video_room})
        except Exception as e:
            sio.disconnect()
            sio.connect(SOCKETIO_URL)
            print("Error sending frame:", e)
        video_room_lock.release()
    cap.release()

def add_text(img):
    for index, room in enumerate(rooms):
        curr_room_lock.acquire()
        color = (255, 255, 255) if index == curr_room else (200, 200, 200)
        curr_room_lock.release()
        display_room_lock.acquire()
        cv2.putText(img, room + (' <-' if index == display_room else ''), (30, 50 + (35 * index)), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        display_room_lock.release()

def display_video():
    cv2.namedWindow('Video Stream', cv2.WINDOW_NORMAL)
    while True:
        last_frame_lock.acquire()
        last_video_time = last_video_frame
        last_frame_lock.release()

        if time.time() - last_video_time > 2:
            black = np.zeros((camera_dims[1], camera_dims[0], 3), np.uint8)
            add_text(black)
            
            global curr_image
            video_lock.acquire()
            curr_image = black
            video_lock.release()
        
        video_lock.acquire()
        if curr_image is not None:
            add_text(curr_image)
            # print(curr_image.shape)
            cv2.imshow('Video Stream', curr_image)
        video_lock.release()
        
        key = cv2.waitKey(1) & 0xFF
        if not handle_keypress(key):
            break

def handle_keypress(key):
    global curr_room
    global video_room
    global audio_room
    global display_room

    if key == 0 or key == 2:
        display_room_lock.acquire()
        display_room = (display_room - 1) % len(rooms)
        display_room_lock.release()
    elif key == 1 or key == 3:
        display_room_lock.acquire()
        display_room = (display_room + 1) % len(rooms)
        display_room_lock.release()
    elif key == 32:
        curr_room_lock.acquire()
        video_room_lock.acquire()
        audio_room_lock.acquire()
        display_room_lock.acquire()
        curr_room = display_room
        video_room = display_room
        audio_room = display_room
        curr_room_lock.release()
        video_room_lock.release()
        audio_room_lock.release()
        display_room_lock.release()
    elif key == ord('q'):
        return False

    return True
    
if __name__ == '__main__':
    sio.connect(SOCKETIO_URL)
    res = requests.get(f'{HTTP_URL}/rooms')
    rooms = json.loads(res.content)

    try:
        # Start sending frames in a separate thread
        video_thread = threading.Thread(target=send_frames)
        audio_thread = threading.Thread(target=send_audio)

        video_thread.start()
        audio_thread.start()
        display_video()
        # Keep the main thread alive to handle SocketIO events
        sio.wait()
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        p.terminate()
        sio.disconnect()
        video_thread.join()
        audio_thread.join()
        print('Exiting...')

    