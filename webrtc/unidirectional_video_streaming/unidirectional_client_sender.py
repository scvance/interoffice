import asyncio
import os
import platform
import socketio
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay

ROOT = os.path.dirname(__file__)

SERVER_IP = 'localhost'
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'
relay = None
webcam = None
sio = socketio.AsyncClient()

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

async def offer(request):
    params = request
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    audio, video = create_local_tracks(
        None, decode=True
    )

    if audio:
        audio_sender = pc.addTrack(audio)

    if video:
        video_sender = pc.addTrack(video)

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await sio.emit('answer', {'sdp': pc.localDescription.sdp, 'type': pc.localDescription.type})
    # return web.Response(
    #     content_type="application/json",
    #     text=json.dumps(
    #         {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    #     ),
    # )


pcs = set()


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

async def main():
    global sio
    await sio.connect(SOCKETIO_URL)
    sio.on('offer', offer)
    await sio.wait()



if __name__ == "__main__":
    asyncio.run(main())