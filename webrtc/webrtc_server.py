# server.py
import aiohttp
import asyncio
from aiohttp import web
from aiohttp.web_ws import WebSocketResponse
from aiohttp import WSMsgType
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaStreamTrack
import numpy as np
import cv2
import pyaudio
import audioop
from webrtc.common import VideoStreamTrack, AudioStreamTrack

routes = web.RouteTableDef()

connected_clients = set()
video_track = None
audio_track = None


@routes.get('/')
async def index(request):
    return web.Response(text="Hello, World!")


@routes.post("/offer")
async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    peer_connection = RTCPeerConnection()
    connected_clients.add(peer_connection)

    await peer_connection.setRemoteDescription(offer)

    if not peer_connection.getTransceivers():
        global video_track, audio_track
        video_track = VideoStreamTrack()
        audio_track = AudioStreamTrack()
        peer_connection.addTrack(video_track)
        peer_connection.addTrack(audio_track)

    answer = await peer_connection.createAnswer()
    await peer_connection.setLocalDescription(answer)
    return web.json_response(
        {"sdp": peer_connection.localDescription.sdp, "type": peer_connection.localDescription.type}
    )


async def cleanup(app):
    for client in connected_clients:
        await client.close()

if __name__ == "__main__":
    app = web.Application()
    app.add_routes(routes)
    app.on_shutdown.append(cleanup)
    web.run_app(app)

