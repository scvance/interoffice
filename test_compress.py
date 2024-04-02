import cv2
import pyaudio
import socketio
import numpy as np
import threading
import requests
import json
import time
import zlib


def compress_video(frame):
    return zlib.compress(frame)
# Function to decompress a single frame
def decompress_frame(compressed_frame):
    return zlib.decompress(compressed_frame)

cap = cv2.VideoCapture(0)
framerate = 30
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
        time.sleep(max(1/framerate - (end_time - start_time), 0))
        frame_chunk.append(zlib.compress(encoded_frame))
    compressed_frames_stream = b''
    for frame in frame_chunk:
        compressed_frames_stream += len(frame).to_bytes(4, byteorder='big') + frame

    # Decompress each frame in the byte stream
    while len(compressed_frames_stream) > 0:
        # Extract the length of the compressed frame
        compressed_frame_length = int.from_bytes(compressed_frames_stream[:4], byteorder='big')
        compressed_frames_stream = compressed_frames_stream[4:]

        # Extract the compressed frame
        compressed_frame = compressed_frames_stream[:compressed_frame_length]
        compressed_frames_stream = compressed_frames_stream[compressed_frame_length:]

        # Decompress the compressed frame
        decompressed_frame = decompress_frame(compressed_frame)
        frame = cv2.imdecode(np.frombuffer(decompressed_frame, dtype=np.uint8), cv2.IMREAD_COLOR)
        cv2.imshow('interoffice', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()
            break
    # for frame in decompressed_frames:


cap.release()