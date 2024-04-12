from fractions import Fraction
import socketio
import threading
import requests
import json
import argparse
import asyncio
import math
import cv2
import numpy as np
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack, MediaStreamTrack
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
from av import VideoFrame

class FlagVideoStreamTrack(VideoStreamTrack):
    """
    A video track that returns an animated flag.
    """

    def __init__(self):
        super().__init__()  # don't forget this!
        self.counter = 0
        height, width = 480, 640

        # generate flag
        data_bgr = np.hstack(
            [
                self._create_rectangle(
                    width=213, height=480, color=(255, 0, 0)
                ),  # blue
                self._create_rectangle(
                    width=214, height=480, color=(255, 255, 255)
                ),  # white
                self._create_rectangle(width=213, height=480, color=(0, 0, 255)),  # red
            ]
        )

        # shrink and center it
        M = np.float32([[0.5, 0, width / 4], [0, 0.5, height / 4]])
        data_bgr = cv2.warpAffine(data_bgr, M, (width, height))

        # compute animation
        omega = 2 * math.pi / height
        id_x = np.tile(np.array(range(width), dtype=np.float32), (height, 1))
        id_y = np.tile(
            np.array(range(height), dtype=np.float32), (width, 1)
        ).transpose()

        self.frames = []
        for k in range(30):
            phase = 2 * k * math.pi / 30
            map_x = id_x + 10 * np.cos(omega * id_x + phase)
            map_y = id_y + 10 * np.sin(omega * id_x + phase)
            self.frames.append(
                VideoFrame.from_ndarray(
                    cv2.remap(data_bgr, map_x, map_y, cv2.INTER_LINEAR), format="bgr24"
                )
            )

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame = self.frames[self.counter % 30]
        frame.pts = pts
        frame.time_base = time_base
        self.counter += 1
        return frame

    def _create_rectangle(self, width, height, color):
        data_bgr = np.zeros((height, width, 3), np.uint8)
        data_bgr[:, :] = color
        return data_bgr
    
class StaticVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        frame = VideoFrame.from_ndarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
        frame.pts = pts
        frame.time_base = time_base
        return frame
    
relay = None
webcam = None

SERVER_IP = 'localhost'  # get your server's IP and put it here
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'
HTTP_URL = f'http://{SERVER_IP}:1234'

sio = socketio.AsyncClient()

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

pc = None

@sio.event
async def connect():
    print('Connected to server')


@sio.event
async def disconnect():
    print('Disconnected from server')

@sio.event
async def message(connection_data):
    global pc
    if connection_data['offer'] is not None and pc.signalingState != 'stable':
        print('Received offer')
        oferer_id = connection_data['offerer_id']

        pc = RTCPeerConnection()
        pc.addTrack(FlagVideoStreamTrack())

        await pc.setRemoteDescription(RTCSessionDescription(sdp=connection_data['offer'], type='offer'))
        await pc.setLocalDescription(await pc.createAnswer())

        run(offerer=False)

        await sio.emit('answer', {'answer': pc.localDescription.sdp, 'room_id': 0, 'receiver_id': oferer_id})
    elif connection_data['answer'] is not None and pc.signalingState == 'have-local-offer':
        print('Received answer')
        await pc.setRemoteDescription(RTCSessionDescription(sdp=connection_data['answer'], type='answer'))

# logging

# def channel_log(channel, t, message):
#     print("channel(%s) %s %s" % (channel.label, t, message))

# def channel_send(channel, message):
#     channel_log(channel, ">", message)
#     channel.send(message)

async def display_track(track: MediaStreamTrack):
    """
    Display the video track using OpenCV.
    """
    if track.kind == 'video':
        window_title = "Received Video"
        cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_title, 640, 480)
        try:
            while True:
                frame = await track.recv()
                image = frame.to_ndarray(format="bgr24")

                cv2.imshow(window_title, image)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except Exception as e:
            print(f"Error displaying video: {e}")
        finally:
            cv2.destroyAllWindows()
            await track.stop()
    else:
        print("Non-video track received, cannot display.")


# main connection method

def run(offerer=True):
    global pc

    if offerer:
        pc.addTrack(FlagVideoStreamTrack())

    if offerer:
        @pc.on("track")
        def on_track(track):
            print("Track %s received" % track.kind)

            if track.kind == "video":
                asyncio.ensure_future(display_track(track))

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            pc.close()

# setup / main loop

async def main():
    global pc
    await sio.connect(SOCKETIO_URL)
    res = requests.get(f'{HTTP_URL}/rooms')
    rooms = json.loads(res.content)
    parser = argparse.ArgumentParser(description="Data channels ping/pong")
    add_signaling_arguments(parser)
    args = parser.parse_args()
    signaling = create_signaling(args)
    pc = RTCPeerConnection()

    try:
        run(offerer=True)
        await pc.setLocalDescription(await pc.createOffer())
        await sio.emit('offer', {'offer': pc.localDescription.sdp, 'room_id': 0})
        await sio.wait()
    except KeyboardInterrupt:
        pass
    finally:
        await sio.disconnect()
        await pc.close()
        signaling.close()

if __name__ == "__main__":
    asyncio.run(main())