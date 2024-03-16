import cv2
import sounddevice as sd
import socketio
import numpy as np
import threading
import time
import zlib

SERVER_IP = '192.168.2.153'  # get your server's IP and put it here
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'

FORMAT = 'int16'  # Sounddevice uses string format for specifying data types
CHANNELS = 1
RATE = 8000
sio = socketio.Client()

compressor = zlib.compressobj(level=6, strategy=zlib.Z_DEFAULT_STRATEGY)
# Compress and decompress functions for video frames
def compress_video(frame):
    return zlib.compress(frame) # compressor.compress(encoded_frame.tobytes()) # + compressor.flush()


def decompress_video(compressed_frame):
    return cv2.imdecode(np.frombuffer(zlib.decompress(compressed_frame), dtype=np.uint8), cv2.IMREAD_COLOR)


# Compress and decompress functions for audio frames
def compress_audio(audio_data):
    return zlib.compress(audio_data)


def decompress_audio(compressed_audio):
    return zlib.decompress(compressed_audio)


@sio.event
def connect():
    print('Connected to server')


@sio.event
def disconnect():
    print('Disconnected from server')


@sio.event
def message(frame_data=None):
    try:
        if frame_data is not None:
            if frame_data['audio'] is not None:
                # audio_data = decompress_audio(frame_data['audio'])
                audio_data = np.frombuffer(frame_data['audio'], dtype=np.int16)
                sd.play(audio_data, samplerate=RATE)
                sd.wait()
            elif frame_data['video'] is not None:
                video_frame = np.frombuffer(frame_data['video'], dtype=np.uint8) # decompress_video(frame_data['video'])
                video_frame = cv2.imdecode(video_frame, cv2.IMREAD_COLOR)
                cv2.imshow('Video Stream', video_frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    sio.disconnect()
                    cv2.destroyAllWindows()

    except Exception as e:
        pass


def send_audio():
    while True:
        audio = sd.rec(int(RATE), samplerate=RATE, channels=CHANNELS, dtype=FORMAT)
        sd.wait()  # Wait until recording is finished
        audio_compressed = compress_audio(audio.tobytes())
        sio.emit('send_audio', {'audio': audio_compressed, 'room': 1})
        time.sleep(.05)


def send_frames():
    cap = cv2.VideoCapture(0)
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)
    while True:
        success, frame = cap.read()
        if not success:
            break
        _, encoded_frame = cv2.imencode('.jpg', frame)
        encoded_frame = encoded_frame.tobytes()
        frame_compressed = compress_video(encoded_frame)
        sio.emit('send_frame', {'video': frame_compressed, 'room': 1})
        # Adjust frame rate here according to your requirements
        time.sleep(0.05)

    cap.release()


if __name__ == '__main__':
    sio.connect(SOCKETIO_URL)

    try:
        # Start sending frames in a separate thread
        thread = threading.Thread(target=send_frames)
        audio_thread = threading.Thread(target=send_audio)
        thread.start()
        audio_thread.start()
        # Keep the main thread alive to handle SocketIO events
        sio.wait()
    except KeyboardInterrupt:
        pass

    # Wait for the send_frames thread to finish before exiting
    thread.join()
