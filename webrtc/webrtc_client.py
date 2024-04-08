# client.py
import aiohttp
import asyncio
import json
import cv2
import numpy as np
import alsaaudio as aa
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaStreamTrack
from webrtc.common import VideoStreamTrack, AudioStreamTrack

#  server settings
SERVER_IP = '192.168.2.153'
HTTP_URL = f'http://{SERVER_IP}:8080'

# audio settings
FORMAT = aa.PCM_FORMAT_S16_LE
CHANNELS = 1
RATE = 8000
CHUNK = 1024

async def main():
    # Create an RTCPeerConnection object
    peer_connection = RTCPeerConnection()

    # Create tracks for video and audio
    video_track = VideoStreamTrack()
    audio_track = AudioStreamTrack()

    # Add tracks to peer connection
    peer_connection.addTrack(video_track)
    peer_connection.addTrack(audio_track)

    # Create an offer
    offer = await peer_connection.createOffer()
    await peer_connection.setLocalDescription(offer)

    # Extract the SDP string from the local description
    offer_sdp = peer_connection.localDescription.sdp

    # Send the offer SDP to the server
    async with aiohttp.ClientSession() as session:
        async with session.post(f'{HTTP_URL}/offer', json={"sdp": offer_sdp, "type": "offer"}) as resp:
            data = await resp.json()
            answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])

        # Set the remote description
        await peer_connection.setRemoteDescription(answer)

        async def consume_video():
            # Set up video capture from camera
            cap = cv2.VideoCapture(0)
            while True:
                ret, frame = cap.read()
                if ret:
                    # Convert frame to bytes
                    frame_bytes = cv2.imencode('.jpg', frame)[1].tobytes()

                    # Send frame as bytes to server
                    await video_track.on_frame(frame_bytes)
                # Receive frame from server
                frame = await video_track.recv()
                cv2.imshow('interoffice', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    cv2.destroyAllWindows()
                    break

        async def consume_audio():
            # Set up audio capture from microphone
            audio_in = aa.PCM(aa.PCM_CAPTURE, aa.PCM_NORMAL, channels=CHANNELS, rate=RATE, format=FORMAT,
                              periodsize=CHUNK)
            while True:
                length, audio_frame = audio_in.read()
                # Send audio frame to server
                await audio_track.on_frame(audio_frame)

        # Start consuming video and audio frames
        video_task = asyncio.ensure_future(consume_video())
        audio_task = asyncio.ensure_future(consume_audio())

        # Wait for tasks to complete
        await asyncio.gather(video_task, audio_task)

asyncio.run(main())