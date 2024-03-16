import cv2
import alsaaudio as aa
import socketio
import numpy as np
import threading
import time
import zlib

SERVER_IP = '192.168.2.153'  # get your server's IP and put it here
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'

FORMAT = aa.PCM_FORMAT_S16_LE  # Use 16-bit signed little-endian format
CHANNELS = 1
RATE = 8000
CHUNK = 1024
sio = socketio.Client()

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
    if frame_data is not None:
        if frame_data['audio'] is not None:
            audio_data = np.frombuffer(frame_data['audio'], dtype=np.int16)
            # audio_data_bytes = audio_data.tobytes()
            audio_out = aa.PCM(aa.PCM_PLAYBACK, aa.PCM_NORMAL, channels=CHANNELS, rate=RATE, format=FORMAT, periodsize=CHUNK)
            try:
                for chunk in audio_data:
                    audio_out.write(chunk)
                    # time.sleep(0.1)  # Adjust timing to synchronize playback
            except aa.ALSAAudioError as e:
                print("ALSA Audio Error:", e)
            finally:
                audio_out.close()
        elif frame_data['video'] is not None:
            video_frame = np.frombuffer(frame_data['video'], dtype=np.uint8)
            video_frame = cv2.imdecode(video_frame, cv2.IMREAD_COLOR)
            cv2.imshow('Video Stream', video_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                sio.disconnect()
                cv2.destroyAllWindows()


def send_audio():
    audio_in = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NORMAL, channels=CHANNELS, rate=RATE, format=FORMAT, periodsize=CHUNK)
    while True:
        audio_chunks = []
        for i in range(0, int(RATE / CHUNK)):
            length, data = audio_in.read()
            audio_chunks.append(data)
        audio_compressed = compress_audio(np.array(audio_chunks).tobytes())
        sio.emit('send_audio', {'audio': audio_compressed, 'room': 1})
        time.sleep(.01)


def send_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break
        _, encoded_frame = cv2.imencode('.jpg', frame)
        encoded_frame = encoded_frame.tobytes()
        frame_compressed = compress_video(encoded_frame)
        sio.emit('send_frame', {'video': frame_compressed, 'room': 1})
        time.sleep(.05)

    cap.release()


if __name__ == '__main__':
    sio.connect(SOCKETIO_URL)

    try:
        # Start sending frames in a separate thread
        thread = threading.Thread(target=send_frames)
        audio_thread = threading.Thread(target=send_audio)
        audio_thread.start()
        thread.start()
        # Keep the main thread alive to handle SocketIO events
        sio.wait()
    except KeyboardInterrupt:
        pass
    thread.join()
    audio_thread.join()
