import time
from fractions import Fraction
import socketio
import threading
import requests
import json
import argparse
import asyncio
import math
import cv2
import platform
import numpy as np
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack, \
    MediaStreamTrack, RTCConfiguration
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
audio = None
video = None

pc = None

@sio.event
async def connect():
    print('Connected to server')


@sio.event
async def disconnect():
    print('Disconnected from server')

@sio.event
async def message(connection_data):
    global pc, audio, video
    if connection_data['offer'] is not None and pc.signalingState != 'stable':
        print('Received offer')
        oferer_id = connection_data['offerer_id']

        pc = RTCPeerConnection()
        # pc.addTrack(FlagVideoStreamTrack())
            # print("Video track added")
        await pc.setRemoteDescription(RTCSessionDescription(sdp=connection_data['offer'], type='offer'))
        if audio:
            audio_sender = pc.addTrack(audio)
        if video:
            video_sender = pc.addTrack(video)
            # pc.add_listener('track', lambda x: display_track(video))
        await pc.setLocalDescription(await pc.createAnswer())
        @pc.on("track")
        async def on_track(track):
            print("Track %s received" % track.kind)
            if track.kind == "video":
                await display_track(track)

        await run(offerer=False)

        await sio.emit('answer', {'answer': pc.localDescription.sdp, 'room_id': 0, 'receiver_id': oferer_id})
    elif connection_data['answer'] is not None and pc.signalingState == 'have-local-offer':
        print('Received answer')
        await pc.setRemoteDescription(RTCSessionDescription(sdp=connection_data['answer'], type='answer'))
    elif connection_data['candidate'] is not None:
        print('Received candidate')
        await pc.addIceCandidate(connection_data['candidate'])

# logging

# def channel_log(channel, t, message):
#     print("channel(%s) %s %s" % (channel.label, t, message))

# def channel_send(channel, message):
#     channel_log(channel, ">", message)
#     channel.send(message)

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

async def display_track(track: MediaStreamTrack):
    """
    Display the video track using OpenCV.
    """
    if track.kind == 'video':
        print("Displaying video track")
        print(track)
        # breakpoint()
        window_title = "Received Video"
        cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_title, 640, 480)
        # breakpoint()
        try:
            while True:
                frame = None
                try:
                    # breakpoint()
                    frame = await asyncio.wait_for(track.recv(), timeout=3)
                except asyncio.TimeoutError:
                    print("Timeout on video track")
                    # continue
                print(frame)
                print(track.readyState)
                if frame != None:
                    # breakpoint()
                    image = frame.to_ndarray(format="bgr24")

                    cv2.imshow(window_title, image)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("Quitting")
                # while True:
                #     frame = await track.recv()
                #     print(frame)
                #     image = frame.to_ndarray(format="bgr24")
                #
                #     cv2.imshow(window_title, image)
                #     if cv2.waitKey(1) & 0xFF == ord('q'):
                #         break
        except Exception as e:
            print(f"Error displaying video: {e}")
        finally:
            cv2.destroyAllWindows()
            track.stop()
    else:
        print("Non-video track received, cannot display.")


# main connection method

async def run(offerer=True):
    global pc
    global audio
    global video


    if offerer:
        # pc.add_listener("track", lambda event: asyncio.ensure_future(display_track(event)))
        if audio:
            pc.addTransceiver(audio, direction='recvonly')
        if video:
            pc.addTransceiver(video, direction='recvonly')
            print("adding a video")
        await pc.setLocalDescription(await pc.createOffer())
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE connection state is %s" % pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        print("on_icecandidate")
        await sio.emit("icecandidate", {"candidate": candidate, "room_id": 0, "offerer": offerer})

    @pc.on("track")
    async def on_track(track):
        print("Track %s received" % track.kind)
        if track.kind == "video":
            await display_track(track)
    # if offerer:
    #     if audio:
    #         audio_sender = pc.addTransceiver(audio)
    #     if video:
    #         video_sender = pc.addTransceiver(video)
    #         print("Video track added")
        # else:
        #     pc.addTrack(FlagVideoStreamTrack())

    # if offerer:
    #     @pc.on("track")
    #     def on_track(track):
    #         # pc.addTransceiver("video")
    #         # pc.addTransceiver("audio")
    #         print("Track %s received" % track.kind)
    #
    #         if track.kind == "video":
    #             asyncio.ensure_future(display_track(track))

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
    pc = RTCPeerConnection()
    # pc.addTransceiver(audio, direction='recvonly')

    try:
        await run(offerer=True)
        await sio.emit('offer', {'offer': pc.localDescription.sdp, 'room_id': 0})
        await sio.wait()
    except KeyboardInterrupt:
        pass
    finally:
        await sio.disconnect()
        await pc.close()
# async def receive(track):
#     while True:
#         frame = await track.recv()
#         image = frame.to_ndarray(format="bgr24")
#
#         cv2.imshow('interoffice', image)
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break
#     print(frame)

if __name__ == "__main__":
    # loop = asyncio.get_event_loop()
    #
    # # Your code to create audio and video tracks goes here
    # # Assuming create_local_tracks is a function that creates the tracks
    #
    # # Create the video track
    # audio, video = create_local_tracks(None, True)
    #
    # # Run the receive function using the event loop
    # loop.run_until_complete(receive(video))
    # while True:
    #     time.sleep(1)
    audio, video = create_local_tracks(None, True)
    asyncio.run(main())