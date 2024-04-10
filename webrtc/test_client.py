from fractions import Fraction
import socketio
import threading
import requests
import json
import argparse
import asyncio
import time
import platform
import math
import cv2
import numpy
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender
from av import VideoFrame
import numpy as np
# from common import VideoStreamTrack, AudioStreamTrack


class FlagVideoStreamTrack(VideoStreamTrack):
    """
    A video track that returns an animated flag.
    """

    def __init__(self):
        super().__init__()  # don't forget this!
        self.counter = 0
        height, width = 480, 640

        # generate flag
        data_bgr = numpy.hstack(
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
        M = numpy.float32([[0.5, 0, width / 4], [0, 0.5, height / 4]])
        data_bgr = cv2.warpAffine(data_bgr, M, (width, height))

        # compute animation
        omega = 2 * math.pi / height
        id_x = numpy.tile(numpy.array(range(width), dtype=numpy.float32), (height, 1))
        id_y = numpy.tile(
            numpy.array(range(height), dtype=numpy.float32), (width, 1)
        ).transpose()

        self.frames = []
        for k in range(30):
            phase = 2 * k * math.pi / 30
            map_x = id_x + 10 * numpy.cos(omega * id_x + phase)
            map_y = id_y + 10 * numpy.sin(omega * id_x + phase)
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
        data_bgr = numpy.zeros((height, width, 3), numpy.uint8)
        data_bgr[:, :] = color
        return data_bgr
    
class CameraVideoTrack(VideoStreamTrack):
    """
    A video stream track that captures video frames from a webcam.
    """
    def __init__(self):
        super().__init__()  # Initialize the base class

    async def recv(self):
        frame = VideoFrame.from_ndarray(generate_frame(), format="bgr24")
        frame.pts = time.time()
        frame.time_base = Fraction(1, 1000)
        return frame
    
def generate_frame():
    # generate random static for now
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
relay = None
webcam = None

def create_local_tracks(play_from, decode):
    global relay, webcam

    if play_from:
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        options = {"framerate": "30", "video_size": "640x480"}
        if relay is None:
            if platform.system() == "Darwin":
                webcam = MediaPlayer(
                    "default:none", format="avfoundation", options=options
                )
            elif platform.system() == "Windows":
                webcam = MediaPlayer(
                    "video=Integrated Camera", format="dshow", options=options
                )
            else:
                webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
            relay = MediaRelay()
        return None, relay.subscribe(webcam.video)
    
def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )

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
    # elif connection_data['candidate'] is not None:
    #     print('Received candidate')
    #     pc.addIceCandidate(RTCIceCandidate(connection_data['candidate'], sdpMid=connection_data['sdpMid'], sdpMLineIndex=connection_data['sdpMLineIndex']))


# logging

def channel_log(channel, t, message):
    print("channel(%s) %s %s" % (channel.label, t, message))

def channel_send(channel, message):
    channel_log(channel, ">", message)
    channel.send(message)

# timing

time_start = None

def current_stamp():
    global time_start

    if time_start is None:
        time_start = time.time()
        return 0
    else:
        return int((time.time() - time_start) * 1000000)

import asyncio
import cv2
from aiortc import MediaStreamTrack

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
    channel = pc.createDataChannel("chat")
    channel_log(channel, "-", "created by local party")

    if offerer:
        pc.addTrack(FlagVideoStreamTrack())
    # def add_tracks():
    #     pc.addTrack(CameraVideoTrack())

    # if offerer:
    #     add_tracks()

    # async def send_pings():
    #     while True:
    #         channel_send(channel, "ping %d" % current_stamp())
    #         await asyncio.sleep(1)

    # async def consume_video():
    #     while True:
    #         frame = cv2.VideoCapture(0).read()[1]
    #         frame = cv2.resize(frame, (640, 480))
    #         _, frame = cv2.imencode('.jpg', frame)
    #         channel_send(channel, frame.tobytes())

    # audio, video = create_local_tracks(play_from=None, decode=False)

    # if video:
    #     pc.addTrack(video)

    @pc.on("track")
    def on_track(track):
        print("Track %s received" % track.kind)

        if track.kind == "video":
            print("TRACK RECEIVED:", track)
            # display track
            asyncio.ensure_future(display_track(track))
            

    @channel.on("open")
    def on_open():
        pass
        # asyncio.ensure_future(send_pings())
        # asyncio.ensure_future(consume_video())

    @channel.on("message")
    def on_message(message):
        channel_log(channel, "<", message)

        if isinstance(message, str) and message.startswith("received frame"):
            elapsed_ms = (current_stamp() - int(message[5:])) / 1000
            print(" RTT %.2f ms" % elapsed_ms)

    @pc.on("datachannel")
    def on_datachannel(channel):
        channel_log(channel, "-", "created by remote party")

        @channel.on("message")
        def on_message(message):
            channel_log(channel, "<", message)

            # if isinstance(message, str) and message.startswith("ping"):
            #     # reply
            #     channel_send(channel, "pong" + message[4:])
            if isinstance(message, bytes):
                frame = cv2.imdecode(numpy.frombuffer(message, numpy.uint8), cv2.IMREAD_COLOR)
                cv2.imshow('frame', frame)
                channel_send(channel, "received frame")
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    cv2.destroyAllWindows()

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
