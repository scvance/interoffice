# client.py

import cv2
import socketio
import numpy as np
import time
import threading

SERVER_IP = '192.168.2.153' # get your ip for the server and put it here
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'

sio = socketio.Client()

@sio.event
def connect():
    print('Connected to server')

@sio.event
def disconnect():
    print('Disconnected from server')


@sio.event
def message(frame_data = None):
    # receive the data from the server
    # print("called")
    try:
        if frame_data is not None:
            frame = np.frombuffer(frame_data['frame_data'], dtype=np.uint8)
            image = cv2.imdecode(frame, cv2.IMREAD_COLOR)
            cv2.imshow('Video Stream', image)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                sio.disconnect()
                cv2.destroyAllWindows()

    except Exception as e:
        print(f'Error: {e}')
        
def send_frames():
    # print("sending frames")
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break

        _, encoded_frame = cv2.imencode('.jpg', frame)
        sio.emit('send_frame', {'frame': encoded_frame.tobytes(), 'room': 1}) # room is hard coded rn, but will not be eventually
        time.sleep(0.1)

    cap.release()

if __name__ == '__main__':
    sio.connect(SOCKETIO_URL)

    try:
        # Start sending frames in a separate thread
        thread = threading.Thread(target=send_frames)
        thread.start()

        # Keep the main thread alive to handle SocketIO events
        sio.wait()
    except KeyboardInterrupt:
        pass

    # Wait for the send_frames thread to finish before exiting
    thread.join()
